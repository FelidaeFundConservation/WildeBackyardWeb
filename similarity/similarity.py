import difflib
from collections import Counter

# Minimum combined score to show a "Did you mean?" suggestion.
# Empirically derived: all garbage/random input scores below 0.15;
# all plausible species name inputs (including heavy typos) score above 0.30.
SUGGEST_THRESHOLD = 0.30

# Minimum combined score to treat the match as confident (auto-select / bold suggestion).
# One-word typos and multi-word misspellings typically score 0.45–0.70;
# exact and case-only variations always score 1.0.
CONFIDENT_THRESHOLD = 0.60


def get_levenshtein_ratio(s1, s2):
    """Measures character-level similarity (edit distance)."""
    return difflib.SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def get_jaccard_similarity(s1, s2):
    """Measures character-level overlap using 3-character n-grams."""

    def get_ngrams(text, n=3):
        text = text.lower()
        return {text[i : i + n] for i in range(len(text) - n + 1)}

    set1, set2 = get_ngrams(s1), get_ngrams(s2)
    if not set1 or not set2:
        return 0
    return len(set1.intersection(set2)) / len(set1.union(set2))


def get_cosine_similarity(s1, s2):
    """Measures word-frequency vector similarity."""
    words1, words2 = Counter(s1.lower().split()), Counter(s2.lower().split())
    all_words = set(words1.keys()).union(set(words2.keys()))

    v1 = [words1[w] for w in all_words]
    v2 = [words2[w] for w in all_words]

    dot_product = sum(a * b for a, b in zip(v1, v2))
    mag1, mag2 = sum(a * a for a in v1) ** 0.5, sum(b * b for b in v2) ** 0.5

    return dot_product / (mag1 * mag2) if mag1 * mag2 != 0 else 0


def find_best_match(candidate, choices):
    """Return the highest-scoring match from *choices* for *candidate*.

    Returns a dict with keys:
        choice  – the matched string from choices
        scores  – (levenshtein, jaccard, cosine) tuple
        total   – arithmetic mean of the three scores (0–1)
    """
    results = []
    for choice in choices:
        lev = get_levenshtein_ratio(candidate, choice)
        jac = get_jaccard_similarity(candidate, choice)
        cos = get_cosine_similarity(candidate, choice)
        total = (lev + jac + cos) / 3
        results.append({"choice": choice, "scores": (lev, jac, cos), "total": total})
    return max(results, key=lambda x: x["total"])


def suggest_species(candidate, choices):
    """Return a suggestion if the best match exceeds SUGGEST_THRESHOLD.

    Returns a dict with keys:
        choice     – best-matching string from choices
        total      – combined score (0–1)
        confident  – True if total >= CONFIDENT_THRESHOLD (safe to auto-select)

    Returns None if no match exceeds SUGGEST_THRESHOLD (garbage / unrecognisable input).
    """
    if not candidate or not choices:
        return None
    best = find_best_match(candidate, choices)
    if best["total"] < SUGGEST_THRESHOLD:
        return None
    return {
        "choice": best["choice"],
        "total": best["total"],
        "confident": best["total"] >= CONFIDENT_THRESHOLD,
    }
