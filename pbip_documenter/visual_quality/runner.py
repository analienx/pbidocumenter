"""Independent visual-quality gate and resumable render/review/repair protocol."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .document import inspect_document
from .evidence import load, review_template, verify_review
from .policy import POLICY_VERSION
from .report import inspect_report_surface


def snapshot(surface: str, source: Path, renders: Path | None) -> dict:
    if surface == "report":
        return inspect_report_surface(source, renders)
    if surface == "document":
        return inspect_document(source, renders)
    raise ValueError(f"Unsupported surface: {surface}")


def audit(surface: str, source: Path, renders: Path | None, review: Path | None,
          fixer_id: str) -> dict:
    result = snapshot(surface, source, renders)
    issues = list(result["static_findings"])
    pages = result["pages"]
    if not result["render_pass"]:
        issues.append({"rule": "render_required_or_stale"})
    if review is None or not review.is_file():
        issues.append({"rule": "independent_review_missing"})
    elif not result["render_pass"]:
        issues.append({"rule": "review_unusable_without_render"})
    else:
        issues.extend(verify_review(surface, result["source_sha256"], pages,
                                    load(review), fixer_id))
    result.update(policy_version=POLICY_VERSION, findings=issues, passed=not issues,
                  reviewer_required=True)
    return result


def save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def request(surface: str, source: Path, renders: Path, fixer_id: str) -> dict:
    state = snapshot(surface, source, renders)
    if not state["render_pass"]:
        raise ValueError("Fresh source-bound rendered pages are required before requesting review")
    return review_template(surface, state["source_sha256"], state["pages"], fixer_id)


def _adapter(spec: dict, name: str, paths: dict[str, str]) -> None:
    config = spec.get(name)
    if not isinstance(config, dict) or not isinstance(config.get("argv"), list) or not config["argv"]:
        raise RuntimeError(f"{name} adapter is not configured; no silent approval or fallback")
    tokens = []
    for value in config["argv"]:
        if not isinstance(value, str):
            raise ValueError(f"{name} argv must contain strings")
        for key, replacement in paths.items():
            value = value.replace("{" + key + "}", replacement)
        tokens.append(value)
    subprocess.run(tokens, check=True, shell=False, cwd=paths["workspace"],
                   timeout=int(config.get("timeout_seconds", 600)))


def iterate(spec: dict) -> dict:
    """Execute bounded rounds; missing adapters or no progress remain explicitly blocked."""
    surface = spec["surface"]
    source, renders = Path(spec["source"]).resolve(), Path(spec["renders"]).resolve()
    workspace = Path(spec["workspace"]).resolve()
    review, issue_file = workspace / "visual-review.json", workspace / "quality-findings.json"
    request_file, history_file = workspace / "review-request.json", workspace / "iteration-history.json"
    workspace.mkdir(parents=True, exist_ok=True)
    previous = load(history_file).get("rounds", []) if history_file.is_file() else []
    history = {"schema": 1, "policy_version": POLICY_VERSION, "surface": surface,
               "source": str(source), "rounds": previous, "outcome": "blocked"}
    rounds = int(spec.get("max_rounds", 5))
    if not 1 <= rounds <= 25:
        raise ValueError("max_rounds must be between 1 and 25")
    fixer_id = spec["fixer_id"]
    for index in range(rounds):
        context = {"source": str(source), "renders": str(renders),
                   "review": str(review), "request": str(request_file),
                   "findings": str(issue_file), "workspace": str(workspace),
                   "round": str(len(history["rounds"]) + 1)}
        try:
            _adapter(spec, "renderer", context)
            save(request_file, request(surface, source, renders, fixer_id))
            review.unlink(missing_ok=True)  # Reject a review left over from an earlier round.
            _adapter(spec, "reviewer", context)
            result = audit(surface, source, renders, review, fixer_id)
            save(issue_file, result)
            entry = {"iteration": len(history["rounds"]) + 1,
                     "source_sha256": result["source_sha256"], "passed": result["passed"],
                     "findings": result["findings"]}
            history["rounds"].append(entry)
            if result["passed"]:
                history["outcome"] = "passed"
                break
            if index + 1 == rounds:
                history["reason"] = "iteration_budget_exhausted; resume with a new budget"
                break
            before = result["source_sha256"]
            _adapter(spec, "fixer", context)
            after = snapshot(surface, source, None)["source_sha256"]
            if before == after:
                history["reason"] = "fixer_made_no_source_change"
                break
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            history["reason"] = f"adapter_or_evidence_blocker: {type(exc).__name__}: {exc}"
            break
        finally:
            save(history_file, history)
    return history
