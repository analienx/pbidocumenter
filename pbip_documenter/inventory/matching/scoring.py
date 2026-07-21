"""Scoring helpers for explainable report-to-Jira matching."""

from dataclasses import dataclass

from pbip_documenter.inventory.matching.text import (
    RARE_DOMAIN_KEYWORDS,
    calculate_name_similarity,
    calculate_rarity_weighted_overlap,
    calculate_token_frequency_score,
    calculate_token_overlap,
    extract_ngrams,
)


@dataclass
class ScoreDetail:
    """Explainable score breakdown for a single match candidate."""

    token_overlap: float
    token_frequency: float
    bigram_overlap: float
    name_similarity: float
    rarity_weighted_overlap: float
    exact_name_match: bool
    final_score: float
    confidence: str
    evidence: list[str]


def score_match(
    query_tokens: list[str],
    candidate_tokens: list[str],
    query_name: str = "",
    candidate_name: str = "",
) -> ScoreDetail:
    """Score a potential match and return explainable evidence."""
    # Traditional token-based scores
    token_overlap = calculate_token_overlap(query_tokens, candidate_tokens)
    token_frequency = calculate_token_frequency_score(query_tokens, candidate_tokens)

    # Bigram overlap for phrase matching
    query_bigrams = extract_ngrams(query_tokens, n=2)
    candidate_bigrams = extract_ngrams(candidate_tokens, n=2)
    if query_bigrams and candidate_bigrams:
        bigram_overlap = calculate_token_overlap(query_bigrams, candidate_bigrams)
    else:
        bigram_overlap = 0.0

    # NEW: Fuzzy name similarity (replaces binary exact match)
    name_similarity = calculate_name_similarity(query_name, candidate_name)

    # NEW: Rarity-weighted overlap (prioritizes rare domain keywords)
    rarity_weighted = calculate_rarity_weighted_overlap(query_tokens, candidate_tokens)

    # Legacy exact name match flag (for backward compatibility)
    exact_name_match = name_similarity >= 0.95

    # NEW SCORING FORMULA:
    # - Name similarity: 35% (fuzzy match on full names)
    # - Rarity-weighted overlap: 30% (domain-specific keywords)
    # - Token overlap: 20% (Jaccard similarity)
    # - Bigram overlap: 10% (phrase matching)
    # - Token frequency: 5% (coverage)
    final_score = (
        (name_similarity * 0.35)
        + (rarity_weighted * 0.30)
        + (token_overlap * 0.20)
        + (bigram_overlap * 0.10)
        + (token_frequency * 0.05)
    )
    final_score = min(final_score, 1.0)

    confidence = _classify_confidence(final_score)
    evidence = _build_evidence(
        query_tokens=query_tokens,
        candidate_tokens=candidate_tokens,
        token_overlap=token_overlap,
        bigram_overlap=bigram_overlap,
        name_similarity=name_similarity,
        rarity_weighted=rarity_weighted,
        exact_name_match=exact_name_match,
    )

    return ScoreDetail(
        token_overlap=token_overlap,
        token_frequency=token_frequency,
        bigram_overlap=bigram_overlap,
        name_similarity=name_similarity,
        rarity_weighted_overlap=rarity_weighted,
        exact_name_match=exact_name_match,
        final_score=final_score,
        confidence=confidence,
        evidence=evidence,
    )


def _classify_confidence(score: float) -> str:
    """Convert numeric score to confidence label."""
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def _build_evidence(
    query_tokens: list[str],
    candidate_tokens: list[str],
    token_overlap: float,
    bigram_overlap: float,
    name_similarity: float,
    rarity_weighted: float,
    exact_name_match: bool,
) -> list[str]:
    """Build human-readable evidence for the score."""
    evidence: list[str] = []

    # Name similarity - strongest signal (35% weight)
    if name_similarity >= 0.95:
        evidence.append("Exact name match (100%)")
    elif name_similarity >= 0.80:
        evidence.append(f"Very similar names ({name_similarity:.0%})")
    elif name_similarity >= 0.50:
        evidence.append(f"Similar names ({name_similarity:.0%})")

    # Rarity-weighted overlap - domain keyword priority (30% weight)
    if rarity_weighted >= 0.70:
        evidence.append(f"Strong domain keyword overlap ({rarity_weighted:.0%})")
    elif rarity_weighted >= 0.40:
        evidence.append(f"Domain keyword overlap ({rarity_weighted:.0%})")

    # Shared tokens
    shared_tokens = sorted(set(query_tokens) & set(candidate_tokens))
    if shared_tokens:
        # Highlight rare/shared domain keywords
        rare_shared = [t for t in shared_tokens if t.lower() in RARE_DOMAIN_KEYWORDS]
        if rare_shared:
            evidence.append(f"Key domain terms: {', '.join(rare_shared[:5])}")
        elif len(shared_tokens) <= 8:
            evidence.append(f"Shared keywords: {', '.join(shared_tokens)}")
        else:
            evidence.append(f"Shared keywords: {', '.join(shared_tokens[:8])}")

    if bigram_overlap >= 0.50:
        evidence.append(f"Matching phrases ({bigram_overlap:.0%})")
    elif bigram_overlap > 0:
        evidence.append(f"Some phrase overlap ({bigram_overlap:.0%})")

    if token_overlap >= 0.50:
        evidence.append(f"Strong token overlap ({token_overlap:.0%})")
    elif token_overlap > 0:
        evidence.append(f"Moderate token overlap ({token_overlap:.0%})")

    if not evidence:
        evidence.append("No meaningful keyword overlap")

    return evidence
