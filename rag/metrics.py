"""Retrieval metrics. Standard library only."""
import re


def _norm(text):
    return " ".join(text.split()).lower()


ENTRY_HEADING = re.compile(r"(?:^|\s)##\s+((?:FL|ST|FI)-\d{2})\b")
ENTRY_PREFIX = re.compile(r"^((?:FL|ST|FI)-\d{2})\b")


def entry_ids(result):
    """Knowledge base entry ids whose heading is inside this chunk.

    Fixed chunks keep the heading as '## FI-09 Title'. Section chunks drop the '##' and
    carry the heading in 'section', so both places are read. An id mentioned in the body
    (for example 'translation of FI-09') does not count.
    """
    ids = ENTRY_HEADING.findall(result.get("text", ""))
    prefix = ENTRY_PREFIX.match(result.get("section", "") or "")
    if prefix:
        ids.append(prefix.group(1))
    return sorted(set(ids))


def is_hit(result, expected_source="", expected_phrase="", expected_entry_ids=()):
    """A result is a hit if it matches the expected entry id (any of several), or else
    the expected source and, when a phrase is given, the chunk text containing it.

    Matching on entry id is the strict form: a fixed chunk covering three entries counts
    as a hit for each of them, which favours the fixed strategy.
    """
    if expected_entry_ids:
        return bool(set(entry_ids(result)) & set(expected_entry_ids))
    if result["source"] != expected_source:
        return False
    if expected_phrase and _norm(expected_phrase) not in _norm(result["text"]):
        return False
    return True


def first_hit_rank(results, expected_source="", expected_phrase="", expected_entry_ids=()):
    """1-based rank of the first hit, or None if there is no hit."""
    for i, result in enumerate(results, start=1):
        if is_hit(result, expected_source, expected_phrase, expected_entry_ids):
            return i
    return None


def summarize(ranks, ks=(1, 3, 5)):
    """ranks is a list of rank-or-None, one per query."""
    n = len(ranks)
    if n == 0:
        return {"n_queries": 0}
    summary = {"n_queries": n}
    for k in ks:
        summary[f"hit@{k}"] = sum(1 for r in ranks if r is not None and r <= k) / n #type:ignore
    summary["mrr"] = sum(1 / r for r in ranks if r) / n #type:ignore
    return summary
