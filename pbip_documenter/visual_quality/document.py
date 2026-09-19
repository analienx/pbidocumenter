"""Independent OOXML preflight; a rendered-page inspection is still required."""

from __future__ import annotations

from pathlib import Path

from docx import Document

from .evidence import digest, image_evidence


def inspect_document(path: Path, renders: Path | None = None) -> dict:
    doc = Document(path)
    findings: list[dict] = []
    if not doc.sections:
        findings.append({"rule": "document_section_missing"})
    for index, section in enumerate(doc.sections, 1):
        left, right = section.left_margin, section.right_margin
        available = section.page_width - left - right
        if min(left.inches, right.inches, section.top_margin.inches,
               section.bottom_margin.inches) < 0.40:
            findings.append({"rule": "document_margin_too_small", "section": index})
        if available <= 0:
            findings.append({"rule": "invalid_printable_width", "section": index})
    for index, paragraph in enumerate(doc.paragraphs, 1):
        if not paragraph.text.strip():
            continue
        for run in paragraph.runs:
            if run.font.size and run.font.size.pt < 8:
                findings.append({"rule": "small_direct_font", "paragraph": index,
                                 "point_size": run.font.size.pt})
    for index, table in enumerate(doc.tables, 1):
        if not table.rows or not table.columns:
            findings.append({"rule": "empty_table", "table": index})
        for row in table.rows:
            if any(cell.text.strip() == "" for cell in row.cells) and len(row.cells) > 1:
                # Blank cells can be intentional layout; this is an advisory, not a blocker.
                break
    for index, picture in enumerate(doc.inline_shapes, 1):
        if doc.sections and picture.width > max(s.page_width - s.left_margin - s.right_margin
                                                for s in doc.sections):
            findings.append({"rule": "figure_wider_than_printable_page", "figure": index})
    source_sha = digest(path)
    pages: list[dict] = []
    if renders is not None:
        from .evidence import load
        manifest = renders / "capture-manifest.json"
        names = load(manifest).get("page_order", []) if manifest.is_file() else []
        if not names or not isinstance(names, list) or len(names) != len(set(names)):
            findings.append({"rule": "document_render_page_inventory_missing"})
        else:
            pages, errors = image_evidence(renders, source_sha, names)
            findings.extend(errors)
    return {"surface": "document", "source_sha256": source_sha, "pages": pages,
            "static_findings": findings, "render_pass": bool(pages) and not any(
                item["rule"].startswith(("render_", "page_", "document_render_")) for item in findings),
            "static_pass": not any(item["rule"] not in {"document_render_page_inventory_missing",
                         "render_manifest_missing", "render_source_stale", "page_render_missing",
                         "page_render_invalid", "page_render_unbound", "render_manifest_invalid"}
                         for item in findings)}
