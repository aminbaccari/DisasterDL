"""Verbatim-quote matching, shared by the relevance judges and the grounded-answer generator."""

import re
import unicodedata


def normalise(text: str) -> str:
    """Lower-case, NFKC-normalised text without quotation marks and with collapsed whitespace."""
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"[‘’“”\"'`]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def quote_found(quote: str, text: str) -> bool:
    """True when ``quote`` appears in ``text``, ignoring case, quotation marks and whitespace.

    Long quotes may be trimmed by a model, so 90% of their words appearing in order as one span
    is accepted too.
    """
    q, t = normalise(quote), normalise(text)
    if not q:
        return False
    if q in t:
        return True
    words = q.split()
    if len(words) < 6:
        return False
    k = max(5, int(len(words) * 0.9))
    return any(" ".join(words[i : i + k]) in t for i in range(len(words) - k + 1))
