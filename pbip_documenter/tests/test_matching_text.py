"""Tests for matching text helpers."""

import math

from pbip_documenter.inventory.matching.text import (
    build_search_context,
    calculate_token_frequency_score,
    calculate_token_overlap,
    extract_keywords,
    extract_ngrams,
    normalize_text,
    sanitize_for_display,
)


class TestMatchingText:
    def test_normalize_text(self):
        assert normalize_text("Sales-Report (V2)!") == "sales report v2"

    def test_extract_keywords_removes_report_stopwords(self):
        keywords = extract_keywords("Sales Report Dashboard")
        assert keywords == ["sales"]

    def test_extract_ngrams(self):
        assert extract_ngrams(["sales", "pipeline", "weekly"], 2) == [
            "sales pipeline",
            "pipeline weekly",
        ]

    def test_calculate_token_overlap(self):
        score = calculate_token_overlap(["sales", "finance"], ["sales", "ops"])
        assert score == 1 / 3

    def test_calculate_token_frequency_score(self):
        score = calculate_token_frequency_score(["sales", "pipeline"], ["sales", "weekly"])
        assert score == 0.5

    def test_build_search_context_includes_variants(self):
        context = build_search_context("Sales", "Commercial", "Executive App")
        assert "Sales" in context
        assert "Commercial" in context
        assert "Executive App" in context
        assert "sales" in context.lower()

    def test_build_search_context_handles_non_string_values(self):
        context = build_search_context("Sales", math.nan, 123.0)
        assert "Sales" in context
        assert "123.0" in context

    def test_sanitize_for_display_truncates(self):
        text = sanitize_for_display("x" * 250, max_length=20)
        assert text == ("x" * 17) + "..."
