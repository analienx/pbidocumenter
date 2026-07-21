"""Power BI Design Specification generator package.

The package root intentionally performs no dependency installation or heavy
imports. Historical convenience exports are resolved lazily for compatibility.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORT_GROUPS = {
    "pbip_documenter.config": ("VERSION", "C", "FONT", "FONT_CODE", "CW", "BEAUTIFY", "WIREFRAME_V2"),
    "pbip_documenter.services.document_service": ("build_doc",),
    "pbip_documenter.docx_render.typography": (
        "h1",
        "h2",
        "h3",
        "h4",
        "body",
        "bullet_item",
        "callout",
        "suggested",
        "suggested_bullet",
        "placeholder",
        "page_break",
        "add_image",
        "_run",
        "_hr",
        "_split_num",
        "_remove_unnecessary_breaks",
        "_is_page_break_paragraph",
    ),
    "pbip_documenter.docx_render.tables": (
        "doc_control_table",
        "kpi_strip",
        "prop_table",
        "obs_card",
        "data_table",
        "code_block",
        "_section_break_after_table",
        "_OBS_CARD_COUNTER",
    ),
    "pbip_documenter.docx_render.styles": (
        "_shading",
        "_margins",
        "_set_w",
        "_no_borders",
        "_set_borders",
        "_set_table_borders",
    ),
    "pbip_documenter.docx_render.diagrams": (
        "DML_NS",
        "_dns",
        "_dsub",
        "_emu",
        "_escape_dml",
        "_box_edge_point",
        "_dml_shape",
        "_dml_join_label",
        "_dml_header_label",
        "_dml_connector",
        "_insert_diagram",
        "_diagram_legend",
        "_min_text_height",
    ),
    "pbip_documenter.docx_render.wireframe": (
        "insert_page_layout",
        "_pick_rep_field",
        "_infer_custom_visual_type",
        "_optimize_row",
        "_DIAGRAM_ID_COUNTER",
    ),
    "pbip_documenter.docx_render.template": ("_clear_template_body", "_update_template_header"),
    "pbip_documenter.docx_render.msip": ("MSIP_CUSTOM_XML", "inject_msip_label"),
    "pbip_documenter.analysis.registries": (
        "CONNECTOR_MAP",
        "_NON_CONN",
        "_NS_CAT",
        "_TYPE_ABBREV",
        "_VD",
        "_DECO_VTS",
        "_SLICER_VTS",
        "_BTN_VTS",
        "_UNKNOWN",
    ),
    "pbip_documenter.analysis.connectors": ("_is_conn", "_label_from_fn", "_scan_all_sources", "_detect_connectors"),
    "pbip_documenter.analysis.dax": ("_transforms", "_dax_pattern"),
    "pbip_documenter.analysis.observations": ("generate_observations",),
    "pbip_documenter.analysis.lineage": ("insert_lineage_diagram",),
    "pbip_documenter.analysis.schema": ("insert_star_schema",),
    "pbip_documenter.bootstrap": ("main",),
}

_EXPORTS = {name: (module_name, name) for module_name, names in _EXPORT_GROUPS.items() for name in names}
__all__ = tuple(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Resolve legacy package-level exports only when they are requested."""
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted((*globals(), *__all__))
