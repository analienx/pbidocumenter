"""Text normalization and tokenization helpers for matching."""

import math
import re
import typing
from typing import Any

# Common English stopwords to filter out during tokenization
DEFAULT_STOPWORDS: set[typing.Any] = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "he",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "that",
    "the",
    "to",
    "was",
    "will",
    "with",
    "this",
    "but",
    "they",
    "have",
    "had",
    "what",
    "said",
    "each",
    "which",
    "she",
    "do",
    "how",
    "their",
    "if",
    "about",
    "into",
    "than",
    "only",
    "some",
    "time",
    "very",
    "when",
    "much",
    "would",
    "there",
    "all",
    "any",
    "both",
    "few",
    "more",
    "most",
    "other",
    "such",
    "no",
    "nor",
    "not",
    "own",
    "same",
    "so",
    "too",
    "can",
    "just",
    "should",
    "now",
    "use",
    "using",
    "used",
    "based",
    "per",
    "via",
}

# Report-specific stopwords that don't add semantic value
REPORT_STOPWORDS: set[typing.Any] = {
    "report",
    "reports",
    "dashboard",
    "dashboards",
    "pbix",
    "pbip",
    "powerbi",
    "power",
    "bi",
    "v1",
    "v2",
    "v3",
    "version",
    "draft",
    "final",
    "copy",
    "backup",
    "old",
    "new",
    "test",
    "testing",
}

# Jira-specific prefixes to strip before matching
JIRA_PREFIXES: list[typing.Any] = [
    r"^clone\s*[-:]?\s*",
    r"^sit\s+",
    r"^uat\s+",
    r"^sdlc\s+",
    r"^pbi\s+",
    r"^fr\s*[-:]?\s*",
    r"^cr\s+\d+\s*[-:]?\s*",
]

# Common words that appear frequently in Jira (low value for matching)
COMMON_JIRA_WORDS: set[typing.Any] = {
    "approval",
    "approvals",
    "create",
    "update",
    "test",
    "deployment",
    "design",
    "data",
    "analysis",
    "load",
    "from",
    "for",
    "and",
    "the",
    "issues",
    "issue",
    "error",
    "fix",
    "bug",
    "feature",
    "story",
    "production",
    "prod",
    "uat",
    "sit",
    "dev",
    "development",
}

# Domain-specific rare keywords that should get high weight
RARE_DOMAIN_KEYWORDS: set[typing.Any] = {
    "womens",
    "derm",
    "atr",
    "je",
    "ess",
    "snowflake",
    "jira",
    "pi",
    "midas",
    "megalinq",
    "omny",
    "iqvia",
    "scemt",
    "connective",
}


def normalize_text(text: str) -> typing.Any:
    """
    Normalize text for comparison.

    Steps:
    - Lowercase
    - Remove special characters except alphanumeric and spaces
    - Collapse multiple spaces
    - Strip leading/trailing whitespace

    Args:
        text: Input text to normalize

    Returns:
        Normalized text string
    """
    if not text:
        return ""

    # Lowercase
    text = text.lower()

    # Keep alphanumeric and spaces, replace others with space
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)

    # Strip
    return text.strip()


def tokenize(text: str, min_length: int = 2) -> typing.Any:
    """
    Tokenize text into individual words.

    Args:
        text: Input text (should be normalized first)
        min_length: Minimum token length to include

    Returns:
        List of tokens
    """
    if not text:
        return []

    tokens = text.split()
    return [t for t in tokens if len(t) >= min_length]


def remove_stopwords(
    tokens: list[str],
    additional_stopwords: set[str] | None = None,
    include_report_stopwords: bool = True,
) -> typing.Any:
    """
    Remove stopwords from token list.

    Args:
        tokens: List of tokens
        additional_stopwords: Additional stopwords to remove
        include_report_stopwords: Whether to include report-specific stopwords

    Returns:
        Filtered token list
    """
    stopwords = DEFAULT_STOPWORDS.copy()

    if include_report_stopwords:
        stopwords.update(REPORT_STOPWORDS)

    if additional_stopwords:
        stopwords.update(additional_stopwords)

    return [t for t in tokens if t not in stopwords]


def extract_keywords(
    text: str,
    min_length: int = 3,
    additional_stopwords: set[str] | None = None,
    include_report_stopwords: bool = True,
) -> typing.Any:
    """
    Extract meaningful keywords from text.

    Combines normalization, tokenization, and stopword removal.

    Args:
        text: Input text
        min_length: Minimum token length
        additional_stopwords: Additional stopwords to remove
        include_report_stopwords: Whether to include report-specific stopwords

    Returns:
        List of keywords
    """
    normalized = normalize_text(text)
    tokens = tokenize(normalized, min_length=min_length)
    return remove_stopwords(
        tokens,
        additional_stopwords=additional_stopwords,
        include_report_stopwords=include_report_stopwords,
    )


def extract_ngrams(tokens: list[str], n: int = 2) -> typing.Any:
    """
    Extract n-grams from tokens.

    Args:
        tokens: List of tokens
        n: N-gram size (2 for bigrams, 3 for trigrams)

    Returns:
        List of n-grams as joined strings
    """
    if len(tokens) < n:
        return []

    ngrams: list[typing.Any] = []
    for i in range(len(tokens) - n + 1):
        ngram = " ".join(tokens[i : i + n])
        ngrams.append(ngram)

    return ngrams


def calculate_token_overlap(tokens_a: list[str], tokens_b: list[str]) -> typing.Any:
    """
    Calculate Jaccard similarity between two token sets.

    Args:
        tokens_a: First token list
        tokens_b: Second token list

    Returns:
        Jaccard similarity score (0.0 to 1.0)
    """
    set_a = set(tokens_a)
    set_b = set(tokens_b)

    if not set_a and not set_b:
        return 1.0  # Both empty = perfect match

    if not set_a or not set_b:
        return 0.0  # One empty, one not = no match

    intersection = len(set_a & set_b)
    union = len(set_a | set_b)

    return intersection / union if union > 0 else 0.0


def calculate_token_frequency_score(
    query_tokens: list[str],
    document_tokens: list[str],
) -> typing.Any:
    """
    Calculate frequency-based score for query tokens in document.

    Args:
        query_tokens: Tokens from the query
        document_tokens: Tokens from the document

    Returns:
        Score from 0.0 to 1.0 based on token presence
    """
    if not query_tokens:
        return 1.0  # Empty query matches everything

    doc_set = set(document_tokens)
    matches = sum(1 for t in query_tokens if t in doc_set)

    return matches / len(query_tokens)


def _coerce_text(value: Any) -> typing.Any:
    """Convert nullable/scalar values to safe text for matching."""
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def build_search_context(
    report_name: str,
    workspace_name: object = "",
    app_name: object = "",
    include_variants: bool = True,
) -> typing.Any:
    """
    Build searchable context from Power BI report metadata.

    Args:
        report_name: Report name
        workspace_name: Workspace name
        app_name: App name
        include_variants: Whether to include word variants

    Returns:
        Combined searchable text
    """
    parts: list[typing.Any] = [_coerce_text(report_name)]

    workspace_name = _coerce_text(workspace_name)
    app_name = _coerce_text(app_name)

    if workspace_name:
        parts.append(workspace_name)

    if app_name:
        parts.append(app_name)

    context = " ".join(filter(None, parts))

    if include_variants:
        # Add common variants (e.g., "Sales Report" -> "Sales")
        variants = _generate_variants(report_name)
        if variants:
            context += " " + " ".join(variants)

    return context


def _generate_variants(text: str) -> typing.Any:
    """Generate common word variants from text."""
    variants: list[typing.Any] = []

    # Handle common suffixes/prefixes
    words = normalize_text(text).split()

    for word in words:
        # Skip very short words
        if len(word) <= 2:
            continue

        # Add singular/plural variants
        if word.endswith("s") and len(word) > 3:
            variants.append(word[:-1])  # Remove 's'
        elif word.endswith("es") and len(word) > 4:
            variants.append(word[:-2])  # Remove 'es'
        else:
            variants.append(word + "s")  # Add 's'

    return list(set(variants))


def strip_jira_prefixes(text: str) -> typing.Any:
    """Strip common Jira prefixes like 'CLONE -', 'SIT', etc."""
    text = text.lower()
    for pattern in JIRA_PREFIXES:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text.strip()


def strip_report_suffixes(text: str) -> typing.Any:
    """Strip common report suffixes like '.Report', '- Copy', etc."""
    text = text.lower()
    # Remove file extensions
    text = re.sub(r"\.report$", "", text)
    text = re.sub(r"\.pbix$", "", text)
    # Remove copy suffixes
    text = re.sub(r"\s*[-_]\s*copy$", "", text)
    text = re.sub(r"\s*\(\s*copy\s*\)$", "", text)
    return text.strip()


def calculate_name_similarity(query_name: str, candidate_name: str) -> typing.Any:
    """
    Calculate fuzzy name similarity between two names.

    Returns a score from 0.0 to 1.0 where:
    - 1.0 = exact match
    - 0.8-0.99 = high similarity (containment or near match)
    - 0.4-0.79 = medium similarity (partial overlap)
    - < 0.4 = low similarity
    """
    if not query_name or not candidate_name:
        return 0.0

    q_norm = normalize_text(query_name)
    c_norm = normalize_text(candidate_name)

    # Strip prefixes/suffixes for comparison
    q_clean = strip_jira_prefixes(strip_report_suffixes(q_norm))
    c_clean = strip_jira_prefixes(strip_report_suffixes(c_norm))

    # Exact match (after cleaning)
    if q_clean == c_clean:
        return 1.0

    # Containment: one name contains the other (strong signal)
    if q_clean in c_clean or c_clean in q_clean:
        # Calculate containment ratio
        len_ratio = min(len(q_clean), len(c_clean)) / max(len(q_clean), len(c_clean))
        return 0.7 + (0.25 * len_ratio)  # 0.7 to 0.95

    # Token-based similarity with rarity weighting
    q_tokens = extract_keywords(q_clean, include_report_stopwords=True)
    c_tokens = extract_keywords(c_clean, include_report_stopwords=True)

    if not q_tokens or not c_tokens:
        return 0.0

    # Calculate weighted intersection
    score = 0.0
    for token in q_tokens:
        if token in c_tokens:
            # Rare domain keywords get higher weight
            if token in RARE_DOMAIN_KEYWORDS:
                score += 0.35
            # Common words get lower weight
            elif token in COMMON_JIRA_WORDS:
                score += 0.05
            # Regular words get medium weight
            else:
                score += 0.15

    # Normalize by query token count (allow max of 1.0 for full rare keyword match)
    max_possible = sum(0.35 if t in RARE_DOMAIN_KEYWORDS else 0.15 for t in q_tokens) or 1.0
    return min(score / max_possible, 1.0)


def calculate_rarity_weighted_overlap(query_tokens: list[str], candidate_tokens: list[str]) -> typing.Any:
    """
    Calculate token overlap with rarity weighting.

    Rare domain-specific keywords (like 'snowflake', 'jira') get much higher
    weight than common words (like 'data', 'analysis', 'report').
    """
    if not query_tokens or not candidate_tokens:
        return 0.0

    query_set = set(query_tokens)
    candidate_set = set(candidate_tokens)

    intersection = query_set & candidate_set

    if not intersection:
        return 0.0

    # Calculate weighted score
    total_weight = 0.0
    matched_weight = 0.0

    for token in query_set:
        # Assign weight based on rarity
        if token in RARE_DOMAIN_KEYWORDS:
            weight = 3.0
        elif token in COMMON_JIRA_WORDS:
            weight = 0.5
        elif len(token) >= 6:  # Longer words are often more specific
            weight = 1.5
        else:
            weight = 1.0

        total_weight += weight
        if token in candidate_set:
            matched_weight += weight

    return matched_weight / total_weight if total_weight > 0 else 0.0


def extract_acronyms(text: str) -> typing.Any:
    """Extract acronyms (2-6 letter all-caps words) from text."""
    words = text.split()
    acronyms: list[typing.Any] = []
    for word in words:
        # Clean the word
        clean = re.sub(r"[^A-Z]", "", word)
        if 2 <= len(clean) <= 6 and clean.isupper():
            acronyms.append(clean)
    return acronyms


def sanitize_for_display(text: str, max_length: int = 200) -> typing.Any:
    """
    Sanitize text for display in matching results.

    Args:
        text: Input text
        max_length: Maximum length before truncation

    Returns:
        Sanitized text
    """
    if not text:
        return ""

    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text)

    # Truncate if too long
    if len(text) > max_length:
        text = text[: max_length - 3] + "..."

    return text.strip()
