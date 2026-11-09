"""V6 Robust quotation matching (one matcher for every citation check of the v2 designs).

A quotation is located by exact match after a fixed normalisation of both quotation and source:
Unicode NFKC, case-folding, unified quotation marks and dashes, removal of line-break hyphenation
("-" + line break between letters), and collapsing every whitespace run to one space. The match is mapped
back to the ORIGINAL source span, which then replaces the quotation, so the product's byte-exact admission
(validate_interpretation) checks the very characters of the source.
"""
from __future__ import annotations

import re
import unicodedata

QUOTES = {c: '"' for c in "“”„‟«»″〝〞"}
QUOTES.update({c: "'" for c in "‘’‚‛‹›′`´"})
DASHES = {c: "-" for c in "‐‑‒–—―−﹘﹣－"}
HYPHEN_BREAK = re.compile(r"(?<=\w)-[ \t]*\r?\n[ \t]*(?=\w)")


def _norm_chars(text: str):
    """Return (normalised string, list mapping each normalised char to its source index)."""
    # remove line-break hyphenation first, remembering original indices
    keep = [True] * len(text)
    for m in HYPHEN_BREAK.finditer(text):
        for i in range(m.start(), m.end()):
            keep[i] = False
    out, index, last_space = [], [], False
    for i, ch in enumerate(text):
        if not keep[i]:
            continue
        for c in unicodedata.normalize("NFKC", ch).casefold():
            c = QUOTES.get(c, DASHES.get(c, c))
            if c.isspace():
                if last_space or not out:
                    continue
                c, last_space = " ", True
            else:
                last_space = False
            out.append(c)
            index.append(i)
    while out and out[-1] == " ":
        out.pop()
        index.pop()
    return "".join(out), index


def normalise(text: str) -> str:
    return _norm_chars(text)[0]


def locate(quote: str, source: str):
    """Original span of source matching quote under the normalisation, or None."""
    if not quote or not source:
        return None
    if quote in source:
        return quote
    q = normalise(quote)
    if not q:
        return None
    s, index = _norm_chars(source)
    pos = s.find(q)
    if pos < 0:
        return None
    return source[index[pos]:index[pos + len(q) - 1] + 1]


def contains(source: str, quote: str) -> bool:
    return locate(quote, source) is not None
