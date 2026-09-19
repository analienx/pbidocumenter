"""Versioned, surface-independent visual review policy.

Each check must be answered against a fresh, source-bound rendered page.
Passing geometry or confirming a screenshot exists cannot satisfy these checks.
"""

POLICY_VERSION = "1.0.0"
COMMON = (
    "information_hierarchy", "purpose_and_story", "typography_hierarchy",
    "text_legibility", "color_contrast", "palette_consistency", "color_semantics",
    "spacing_and_padding", "alignment_and_grid", "whitespace_balance",
    "density_and_clutter", "clipping_and_overflow", "accessibility",
)
REPORT = COMMON + (
    "chart_type_suitability", "visual_encoding", "axis_tick_density",
    "axis_precision", "axis_title_necessity", "category_label_density",
    "visual_size_for_content", "scrollbars_in_key_visuals", "table_fit",
    "metric_format_and_units", "slicer_usability", "rendered_data_integrity",
)
DOCUMENT = COMMON + (
    "page_margins", "paragraph_spacing", "heading_navigation",
    "table_pagination_and_fit", "figure_size_and_fidelity",
    "figure_caption_and_reference", "page_breaks_and_orphans",
    "header_footer_consistency", "page_numbering", "document_report_consistency",
)
# The reviewer may mark these non-applicable only with a written explanation.
OPTIONAL = {
    "report": {"axis_tick_density", "axis_precision", "axis_title_necessity",
               "category_label_density", "scrollbars_in_key_visuals", "table_fit",
               "slicer_usability"},
    "document": {"table_pagination_and_fit", "figure_size_and_fidelity",
                 "figure_caption_and_reference", "document_report_consistency"},
}
REQUIRED = {"report": REPORT, "document": DOCUMENT}
STATUSES = {"pass", "fail", "not_applicable"}
SEVERITIES = {"critical", "high", "medium", "low"}

# Specific decisions the external image reviewer must make for EVERY rendered page.
CRITERIA = {
    "information_hierarchy": "Can a reader identify the main message, metrics and next action in five seconds?",
    "purpose_and_story": "Does every major graphic answer a distinct business question without contradicting adjacent graphics?",
    "typography_hierarchy": "Are title, section, visual title, label, axis and footnote font sizes consistently differentiated?",
    "text_legibility": "Can all labels and numbers be read at the target viewing size without zoom or truncated text?",
    "color_contrast": "Is foreground/background contrast sufficient for small labels, marks and tables, including pale fills?",
    "palette_consistency": "Does the page use a restrained palette consistent with other pages and the chosen theme?",
    "color_semantics": "Are colors assigned consistently to the same categories and states; is meaning available without color alone?",
    "spacing_and_padding": "Are inner chart padding, tick-to-title space, card padding and outer gutters consistent and sufficient?",
    "alignment_and_grid": "Do peer panels, edges, baselines and card contents align deliberately without accidental offsets?",
    "whitespace_balance": "Is empty space intentional rather than caused by unnecessarily tall tables or small charts?",
    "density_and_clutter": "Does the amount of data, decoration, legend, gridline and annotation fit the available space?",
    "clipping_and_overflow": "Are any marks, headings, labels, tables, legends or annotations cropped or obscured?",
    "accessibility": "Are labels meaningful and readable, with redundant encodings for states and non-decorative graphics?",
    "chart_type_suitability": "Does the chosen chart encode its analytical task; avoid scatter plots with degenerate axes or composition bars for trends?",
    "visual_encoding": "Are comparisons, magnitudes, zero baselines, percentages and color assignments semantically correct?",
    "axis_tick_density": "Are tick counts appropriate to plot width and can adjacent tick labels be distinguished without overlap?",
    "axis_precision": "Do different ticks render distinct values with a sensible precision, avoiding repeated 10% or 33.863%?",
    "axis_title_necessity": "Is each axis title useful and short? Remove redundant field names; preserve indispensable units and meaning.",
    "category_label_density": "Are categories legible without unnecessary scrolling, vertical letter stacks or truncated legends?",
    "visual_size_for_content": "Are panels proportionate to their actual data, and are chart marks large enough to interpret?",
    "scrollbars_in_key_visuals": "Can all essential chart categories and time periods be seen without horizontal or vertical scrolling?",
    "table_fit": "Do visible table columns, row counts, captions and panel width agree; is wide unused space justified?",
    "metric_format_and_units": "Are currencies, percentage points, percentages, abbreviations and decimals consistently and correctly formatted?",
    "slicer_usability": "Can the viewer understand the filters and current selections without a cluttered header?",
    "rendered_data_integrity": "Does each visual display data rather than blanks, broken visual icons or an error/loading state?",
    "page_margins": "Is body content consistently inside safe printable margins on every page and orientation?",
    "paragraph_spacing": "Do line height, paragraph spacing and keep-with-next behavior create readable text blocks?",
    "heading_navigation": "Are heading levels, numbering and section titles consistent and meaningful across page breaks?",
    "table_pagination_and_fit": "Are tables legible, with aligned columns, no split header/row and repeating headings where needed?",
    "figure_size_and_fidelity": "Are PBIR report captures, wireframes, M/DAX and schema diagrams readable at actual Word page size?",
    "figure_caption_and_reference": "Do figures have accurate captions, numbering, source context and references near their first mention?",
    "page_breaks_and_orphans": "Are there no orphaned headings, stranded captions, near-empty pages or clipped content after breaks?",
    "header_footer_consistency": "Are repeated headers/footers aligned, within page bounds and free of collisions?",
    "page_numbering": "Is page numbering present, correctly ordered and consistent across sections and orientations?",
    "document_report_consistency": "Do embedded screenshots, diagrams and visual inventories describe the same report revision and fields?",
}
assert set(REPORT + DOCUMENT) == set(CRITERIA), "Every required observation needs explicit criteria"
