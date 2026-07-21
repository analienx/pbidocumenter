"""Deterministic context packaging and optional AI/fallback text generation."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from pbip_documenter.augmentation.config import AISettings
from pbip_documenter.cache.paths import CachePaths
from pbip_documenter.inventory.matching.service import MatchingService, MatchResult
from pbip_documenter.inventory.matching.text import sanitize_for_display


def _get_jira_base_url() -> str:
    """Get Jira base URL from environment or settings."""
    # Try to load from settings file first
    settings_path = Path("inventory.settings.json")
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            if settings.get("JIRA_BASE_URL"):
                return settings["JIRA_BASE_URL"]
        except (OSError, json.JSONDecodeError):
            pass

    # Fall back to environment variable (no default; caller must set it)
    return os.environ.get("JIRA_BASE_URL", "")


@dataclass
class GeneratedSection:
    text: str
    source: str
    assumptions: list[str]
    missing_information: list[str]
    traceability_notes: list[str]


@dataclass
class AugmentationBundle:
    report_context: dict[str, Any]
    matches: list[MatchResult]
    requirement: GeneratedSection
    design: GeneratedSection
    warning: str | None


def build_augmentation_bundle(summary: dict[str, Any], cache_root: Path = Path("cache")) -> AugmentationBundle | None:
    local_only = os.environ.get("PBIP_DOCUMENTER_LOCAL_ONLY", "1").lower() not in ("0", "false", "no")
    if local_only:
        return None
    report = summary.get("report") or {}
    semantic_model = summary.get("semantic_model") or {}
    report_name = report.get("display_name") or summary.get("project_name") or ""
    if not report_name:
        return None

    powerbi_reports = _load_curated_dataframe(cache_root, "powerbi", "reports.parquet")
    jira_issues = _load_curated_dataframe(cache_root, "jira", "issues.parquet")
    if powerbi_reports.empty or jira_issues.empty:
        return None

    jira_base_url = _get_jira_base_url()
    matching_service = MatchingService(
        powerbi_reports=powerbi_reports,
        jira_issues=jira_issues,
        jira_base_url=jira_base_url,
    )
    matches = matching_service.match_report(report_name, limit=3)

    top_match = matches[0] if matches else None
    report_context = {
        "report_name": report_name,
        "workspace_name": top_match.workspace_name if top_match else None,
        "workspace_id": top_match.workspace_id if top_match else None,
        "workspace_url": top_match.workspace_url if top_match else None,
        "app_name": top_match.app_name if top_match else None,
        "app_id": top_match.app_id if top_match else None,
        "app_url": top_match.app_url if top_match else None,
        "report_id": top_match.report_id if top_match else None,
        "web_url": top_match.web_url if top_match else None,
        "embed_url": top_match.embed_url if top_match else None,
        "dataset_mode": report.get("dataset_mode"),
        "page_names": [p.get("display_name", "?") for p in report.get("pages", [])],
        "table_names": [t.get("name", "?") for t in semantic_model.get("tables", [])],
        "measure_count": sum(len(t.get("measures", [])) for t in semantic_model.get("tables", [])),
        "source_count": len(set(semantic_model.get("data_sources", []))),
        "matched_jira": [
            {
                "issue_key": m.jira_issue_key,
                "summary": m.jira_summary,
                "jira_url": m.jira_url,
                "confidence": m.confidence,
                "score": round(m.score, 4),
                "evidence": m.evidence,
            }
            for m in matches
        ],
    }

    warning = _build_warning(matches)
    requirement = _generate_section("requirement", report_context, matches)
    design = _generate_section("design", report_context, matches)

    return AugmentationBundle(
        report_context=report_context,
        matches=matches,
        requirement=requirement,
        design=design,
        warning=warning,
    )


def _load_curated_dataframe(cache_root: Path, source: str, filename: str) -> pd.DataFrame:
    path = CachePaths(cache_root).get_curated_path(source, filename)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _build_warning(matches: list[MatchResult]) -> str | None:
    if not matches:
        return "No Jira match found in local cache. Requirement and design text use PBIP-only fallback content."
    top = matches[0]
    if top.confidence == "low":
        return (
            f"Top Jira match {top.jira_issue_key or 'unknown'} has low confidence. "
            "Review requirement and design text before publication."
        )
    return None


def _generate_section(kind: str, report_context: dict[str, Any], matches: list[MatchResult]) -> GeneratedSection:
    ai_settings = AISettings.load()
    if _should_use_ai(ai_settings, matches):
        ai_result = _try_generate_with_ai(kind, report_context, matches, ai_settings)
        if ai_result:
            return ai_result
    return _generate_fallback(kind, report_context, matches)


def _should_use_ai(ai_settings: AISettings, matches: list[MatchResult]) -> bool:
    if not ai_settings.enabled:
        return False
    if not ai_settings.provider or not ai_settings.model:
        return False
    if not matches:
        return False
    return _confidence_rank(matches[0].confidence) >= _confidence_rank(ai_settings.confidence_threshold_generate)


def _try_generate_with_ai(
    kind: str,
    report_context: dict[str, Any],
    matches: list[MatchResult],
    ai_settings: AISettings,
) -> GeneratedSection | None:
    return None


def _generate_fallback(kind: str, report_context: dict[str, Any], matches: list[MatchResult]) -> GeneratedSection:
    pages = report_context.get("page_names") or []
    top = matches[0] if matches else None
    base_lines = []

    if kind == "requirement":
        base_lines.append(
            f"This solution provides the {report_context.get('report_name', 'Power BI report')} reporting capability "
            f"for business users to review curated metrics and operational signals across {len(pages)} page(s)."
        )
        if top and top.jira_summary:
            base_lines.append(f"The strongest cached Jira reference is {top.jira_issue_key}: {top.jira_summary}.")
        base_lines.append(
            f"The report is packaged in workspace {report_context.get('workspace_name') or '[workspace not found in cache]'}"
            f" and surfaced through {report_context.get('app_name') or '[app not found in cache]'} when available."
        )
        base_lines.append(
            f"The semantic model currently exposes {len(report_context.get('table_names') or [])} tables and "
            f"{report_context.get('measure_count') or 0} measures derived from {report_context.get('source_count') or 0} source(s)."
        )
    else:
        base_lines.append(
            f"The design uses a {report_context.get('dataset_mode') or 'Power BI'} semantic model with "
            f"{len(report_context.get('table_names') or [])} tables supporting {len(pages)} report page(s)."
        )
        if pages:
            base_lines.append(f"Named report pages detected in PBIP metadata: {', '.join(pages[:8])}.")
        base_lines.append(
            "The generated specification should be reviewed against deployment, access, refresh, and support procedures "
            "that are not fully represented in PBIP metadata."
        )
        if top and top.jira_summary:
            base_lines.append(
                f"Design intent was cross-checked against cached Jira item {top.jira_issue_key}: {top.jira_summary}."
            )

    assumptions = [
        "Generated from local PBIP metadata and cached inventory artifacts only.",
        "Any operational, compliance, or release-management statements require human confirmation.",
    ]
    missing_information = [
        "Business owner and support owner confirmation.",
        "Approved deployment path, refresh schedule, and access model.",
    ]
    traceability_notes = []
    if top:
        traceability_notes.append(
            f"Matched Jira {top.jira_issue_key} with {top.confidence} confidence ({top.score:.2f})."
        )
        traceability_notes.extend(top.evidence[:4])
    else:
        traceability_notes.append("No Jira cache match available; fallback content is PBIP-derived only.")

    return GeneratedSection(
        text=" ".join(base_lines),
        source="fallback",
        assumptions=assumptions,
        missing_information=missing_information,
        traceability_notes=[sanitize_for_display(item, 300) for item in traceability_notes],
    )


def _confidence_rank(value: str) -> int:
    return {"low": 1, "medium": 2, "high": 3}.get((value or "").lower(), 0)
