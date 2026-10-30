"""Conservative, source-grounded PBIP validation for the agent-first CLI.

This is a *structural* validation of supported PBIP/PBIR/TMDL inputs. It is
not a full TMDL grammar compiler and never implies complete Power BI support.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from copiloter import PbipProject, TmdlParser, build_project_summary

SCHEMA_VERSION = "1.0"


REMEDIATION_HINTS = {
    "PATH_NOT_FOUND": "Choose an existing local PBIP project folder.",
    "NO_PROJECTS": "Pass a .pbip wrapper directory or a recognizable .Report / .SemanticModel project.",
    "INVALID_PROJECT": "Check the PBIP project structure and required component folders.",
    "PBIR_INVALID": "Repair the named PBIR page or visual JSON, then rerun validate.",
    "PBIP_INVALID": "Repair the .pbip JSON file before generating.",
    "PBIR_REFERENCE_INVALID": "Repair definition.pbir JSON before generating.",
    "REPORT_FORMAT_UNKNOWN": "Ensure the report contains a supported PBIR pages tree or legacy report.json.",
    "TMDL_TABLE_UNPARSED": "Inspect the named TMDL file for a recognized table declaration.",
    "TMDL_RELATIONSHIPS_UNPARSED": "Inspect relationships.tmdl and confirm syntax with Power BI tooling.",
    "TMDL_PARSER_WARNING": "Review parser uncertainty; validate with Power BI Desktop or official model tooling.",
    "SOURCE_UNREADABLE": "Verify the source file is accessible and UTF-8 encoded.",
    "SOURCE_EMPTY": "Restore the missing content of this required source file.",
    "TEMPLATE_NOT_FOUND": "Provide an existing .docx template or omit --template.",
    "LOGO_NOT_FOUND": "Provide an existing logo file or omit --logo.",
    "MULTIPLE_PROJECTS": "Use --output-dir for batch generation or pass one project with --output.",
    "OUTPUT_EXISTS": "Choose another path or remove --no-overwrite to replace the existing output.",
    "SOURCE_CHANGED": "Stop edits to the PBIP while generating, then retry.",
    "TEMPLATE_INVALID": "Choose a valid Word .docx template.",
    "LOGO_INVALID": "Choose a PNG, JPEG or supported raster logo.",
    "OUTPUT_INVALID": "Provide a filename ending in .docx.",
    "OUTPUT_DIRECTORY_INVALID": "Choose an existing directory or a new path, not a file.",
}


def diagnostic(code: str, severity: str, message: str, file: str | None = None) -> dict[str, str]:
    item = {"code": code, "severity": severity, "message": message}
    if file is not None:
        item["file"] = file
    hint = REMEDIATION_HINTS.get(code)
    if hint:
        item["hint"] = hint
    return item


def _text(path: Path, project_root: Path, issues: list[dict[str, str]]) -> str | None:
    location = str(path.relative_to(project_root)) if path.is_relative_to(project_root) else path.name
    try:
        content = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        issues.append(diagnostic("SOURCE_UNREADABLE", "error", "Unable to read source text as UTF-8", location))
        return None
    if not content.strip():
        issues.append(diagnostic("SOURCE_EMPTY", "error", "Required source file is empty", location))
        return None
    return content


def validate_project(project: PbipProject, *, strict: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a stable validation result and the shared extractor's summary."""
    root = project.project_dir.resolve()
    findings: list[dict[str, str]] = []
    if not project.is_valid:
        findings.append(diagnostic("INVALID_PROJECT", "error", "Not a recognizable PBIP/PBIR project"))
        return _result(project, findings, strict, None), {}

    # Preserve PBIR extraction diagnostics, including malformed page/visual
    # definitions. The same errors block the existing Word generator.
    summary = build_project_summary(project)
    report = summary.get("report") or {}
    for warning in report.get("warnings") or []:
        value = str(warning)
        if value.startswith("ERROR:"):
            findings.append(diagnostic("PBIR_INVALID", "error", value[6:].strip()))
        else:
            findings.append(diagnostic("PBIR_WARNING", "warning", value))

    if project.report_dir and project.report_format == "unknown":
        findings.append(diagnostic("REPORT_FORMAT_UNKNOWN", "error", "Report definition format could not be identified"))

    if project.pbip_file:
        file = project.pbip_file
        try:
            value = json.loads(file.read_text(encoding="utf-8-sig"))
            if not isinstance(value, dict):
                findings.append(diagnostic("PBIP_INVALID", "error", "PBIP root must be a JSON object", file.name))
        except (OSError, UnicodeError, ValueError):
            findings.append(diagnostic("PBIP_INVALID", "error", "Cannot parse PBIP root JSON", file.name))

    if project.pbir_file:
        file = project.pbir_file
        try:
            value = json.loads(file.read_text(encoding="utf-8-sig"))
            if not isinstance(value, dict):
                findings.append(diagnostic("PBIR_REFERENCE_INVALID", "error", "PBIR reference must be a JSON object", file.name))
        except (OSError, UnicodeError, ValueError):
            findings.append(diagnostic("PBIR_REFERENCE_INVALID", "error", "Cannot parse PBIR reference JSON", file.name))

    model = summary.get("semantic_model") or {}
    if project.semantic_model_dir:
        definition = project.semantic_model_dir / "definition"
        table_dir = definition / "tables"
        tables = sorted(table_dir.glob("*.tmdl")) if table_dir.is_dir() else []
        if not definition.is_dir():
            findings.append(diagnostic("TMDL_DEFINITION_MISSING", "warning", "No TMDL definition directory; model may use another serialization"))
        elif not tables:
            findings.append(diagnostic("TMDL_TABLES_MISSING", "warning", "No table TMDL files found"))
        for table in tables:
            content = _text(table, root, findings)
            if content is None:
                continue
            parsed = TmdlParser.parse_table(content)
            if not parsed.get("name"):
                findings.append(diagnostic("TMDL_TABLE_UNPARSED", "error", "No recognized table declaration", str(table.relative_to(root))))
        relationships = definition / "relationships.tmdl"
        if relationships.is_file():
            content = _text(relationships, root, findings)
            if content and "relationship " in content and not TmdlParser.parse_relationships(content):
                findings.append(diagnostic("TMDL_RELATIONSHIPS_UNPARSED", "error", "Relationship declarations could not be parsed", str(relationships.relative_to(root))))
        for warning in model.get("parser_warnings") or []:
            findings.append(diagnostic("TMDL_PARSER_WARNING", "warning", str(warning)))

    if project.warnings:
        for warning in project.warnings:
            findings.append(diagnostic("PROJECT_WARNING", "info", str(warning)))

    # Strict mode is intentionally transparent: parser warnings indicate
    # uncertainty, not proof of malformed TMDL. Treat such warnings as
    # validation failures rather than pretending to compile all TMDL syntax.
    return _result(project, findings, strict, summary), summary


def _result(
    project: PbipProject, findings: list[dict[str, str]], strict: bool, summary: dict[str, Any] | None
) -> dict[str, Any]:
    blocking = any(f["severity"] == "error" or (strict and f["severity"] == "warning") for f in findings)
    model = (summary or {}).get("semantic_model") or {}
    counts = {severity: sum(f["severity"] == severity for f in findings) for severity in ("error", "warning", "info")}
    return {
        "project": project.name,
        "path": str(project.project_dir.resolve()),
        "diagnostic_counts": counts,
        "valid": not blocking,
        "strict": strict,
        "parser": {
            "mode": model.get("parser_mode", "python_fallback" if project.semantic_model_dir else "none"),
            "confidence": model.get("parser_confidence"),
            "full_tmdl_grammar_verified": False,
        },
        "diagnostics": findings,
    }


def inventory(summary: dict[str, Any], *, details: bool = False) -> dict[str, Any]:
    """Publish non-secret counts and optional names, never raw DAX or connection strings."""
    model = summary.get("semantic_model") or {}
    report = summary.get("report") or {}
    tables = model.get("tables") or []
    pages = report.get("pages") or []
    result: dict[str, Any] = {
        "tables": len(tables),
        "measures": sum(len(table.get("measures") or []) for table in tables),
        "relationships": len(model.get("relationships") or []),
        "roles": len(model.get("roles") or []),
        "report_pages": len(pages),
        "report_visuals": report.get("total_visuals", 0),
        "completeness": (summary.get("completeness") or {}).get("score"),
    }
    if details:
        result["table_names"] = sorted(str(t.get("name")) for t in tables if t.get("name"))
        result["page_names"] = [str(p.get("display_name") or p.get("name") or "") for p in pages]
    return result


def _source_files(project: PbipProject) -> list[Path]:
    """Collect supported PBIP sources, excluding artifacts and symlink escapes."""
    root = project.project_dir.resolve()
    result: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part.startswith(".") and part != ".platform" for part in relative.parts):
            continue
        if not path.resolve().is_relative_to(root):
            continue
        suffix = path.suffix.lower()
        if suffix not in {".pbip", ".pbir", ".pbism", ".tmdl"}:
            if path.name != ".platform" and not (
                suffix == ".json"
                and ("definition" in relative.parts or path.name == "diagramLayout.json")
            ):
                continue
        result.append(path)
    return sorted(result, key=lambda path: path.relative_to(root).as_posix())


def source_fingerprint(project: PbipProject) -> str:
    """SHA256 over PBIP source paths and bytes, excluding unrelated files."""
    digest = hashlib.sha256()
    root = project.project_dir.resolve()
    for file in _source_files(project):
        digest.update(file.relative_to(root).as_posix().encode("utf-8"))
        digest.update(bytes([0]))
        with file.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()
