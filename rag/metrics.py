"""Retrieval metrics. Standard library only."""


def _norm(text):
    return " ".join(text.split()).lower()


def is_hit(result, expected_source, expected_phrase=""):
    """A result is a hit if it comes from the expected source and, when a phrase
    is given, the chunk text contains that phrase."""
    if result["source"] != expected_source:
        return False
    if expected_phrase and _norm(expected_phrase) not in _norm(result["text"]):
        return False
    return True


def first_hit_rank(results, expected_source, expected_phrase=""):
    """1-based rank of the first hit, or None if there is no hit."""
    for i, result in enumerate(results, start=1):
        if is_hit(result, expected_source, expected_phrase):
            return i
    return None


def summarize(ranks, ks=(1, 3, 5)):
    """ranks is a list of rank-or-None, one per query."""
    n = len(ranks)
    if n == 0:
        return {"n_queries": 0}
    summary = {"n_queries": n}
    for k in ks:
        summary[f"hit@{k}"] = sum(1 for r in ranks if r is not None and r <= k) / n
    summary["mrr"] = sum(1 / r for r in ranks if r) / n
    return summary
