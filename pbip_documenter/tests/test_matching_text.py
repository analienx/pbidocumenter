"""Tests for matching text helpers."""

import math
import typing

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
    def test_normalize_text(self: typing.Any) -> typing.Any:
        assert normalize_text("Sales-Report (V2)!") == "sales report v2"

    def test_extract_keywords_removes_report_stopwords(self: typing.Any) -> typing.Any:
        keywords = extract_keywords("Sales Report Dashboard")
        assert keywords == ["sales"]

    def test_extract_ngrams(self: typing.Any) -> typing.Any:
        assert extract_ngrams(["sales", "pipeline", "weekly"], 2) == [
            "sales pipeline",
            "pipeline weekly",
        ]

    def test_calculate_token_overlap(self: typing.Any) -> typing.Any:
        score = calculate_token_overlap(["sales", "finance"], ["sales", "ops"])
        assert score == 1 / 3

    def test_calculate_token_frequency_score(self: typing.Any) -> typing.Any:
        score = calculate_token_frequency_score(["sales", "pipeline"], ["sales", "weekly"])
        assert score == 0.5

    def test_build_search_context_includes_variants(self: typing.Any) -> typing.Any:
        context = build_search_context("Sales", "Commercial", "Executive App")
        assert "Sales" in context
        assert "Commercial" in context
        assert "Executive App" in context
        assert "sales" in context.lower()

    def test_build_search_context_handles_non_string_values(self: typing.Any) -> typing.Any:
        context = build_search_context("Sales", math.nan, 123.0)
        assert "Sales" in context
        assert "123.0" in context

    def test_sanitize_for_display_truncates(self: typing.Any) -> typing.Any:
        text = sanitize_for_display("x" * 250, max_length=20)
        assert text == ("x" * 17) + "..."
