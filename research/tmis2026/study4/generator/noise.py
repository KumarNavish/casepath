"""Seeded scan noise (SPEC.md step 2c item 5), reversible.

degrade(text, seed) -> (degraded, ops). `ops` lists every edit on the clean text in order
({"at": offset in the clean text, "orig": clean substring, "new": replacement}); restore(degraded, ops) gives the
clean text back exactly. The clean text is also kept beside the degraded one (assemble.py), so reversal is a check,
not the only copy.

Edits, each drawn independently per position with a per-file random generator:
- character confusions: rn -> m, m -> rn, l -> 1, 1 -> l, O -> 0, 0 -> O (probability `p_confusion` per candidate);
- lost diacritics: a letter with a diacritic loses it (ä -> a, é -> e; `p_diacritic` per such letter);
- broken lines: the text is re-broken at a per-file line width (55 to 72 characters), a space past the width
  becoming a line break; a long word that crosses the width is hyphenated with "-\\n" (`p_hyphen`);
- dropped characters: a letter is dropped with probability `p_drop` (default 0.4%, so under 1% of characters).
Existing line breaks are kept.
"""
import random
import unicodedata

DEFAULTS = {"p_confusion": 0.04, "p_diacritic": 0.5, "p_drop": 0.004, "p_hyphen": 0.6}
CONFUSE = {"m": "rn", "l": "1", "1": "l", "O": "0", "0": "O"}


def strip_diacritic(ch):
    base = "".join(c for c in unicodedata.normalize("NFD", ch) if not unicodedata.combining(c))
    return base if base != ch and len(base) == 1 else None


def degrade(text, seed, params=None):
    p = dict(DEFAULTS, **(params or {}))
    rng = random.Random(seed)
    width = rng.randrange(55, 73)
    out, ops = [], []
    i, col, n = 0, 0, len(text)

    def edit(at, orig, new):
        ops.append({"at": at, "orig": orig, "new": new})
        out.append(new)

    while i < n:
        ch = text[i]
        if ch == "\n":
            out.append(ch)
            col, i = 0, i + 1
            continue
        if ch == " " and col >= width:
            edit(i, " ", "\n")
            col, i = 0, i + 1
            continue
        # hyphenate a long word that crosses the width: at least 3 letters before and after the break
        if ch.isalpha() and col >= width + 2:
            j = i
            while j < n and text[j].isalpha():
                j += 1
            k = i
            while k > 0 and text[k - 1].isalpha():
                k -= 1
            if i - k >= 3 and j - i >= 3 and rng.random() < p["p_hyphen"]:
                edit(i, "", "-\n")
                col = 0
        if text.startswith("rn", i) and rng.random() < p["p_confusion"]:
            edit(i, "rn", "m")
            col, i = col + 1, i + 2
            continue
        if ch in CONFUSE and rng.random() < p["p_confusion"]:
            edit(i, ch, CONFUSE[ch])
            col, i = col + len(CONFUSE[ch]), i + 1
            continue
        base = strip_diacritic(ch) if ch.isalpha() else None
        if base is not None and rng.random() < p["p_diacritic"]:
            edit(i, ch, base)
            col, i = col + 1, i + 1
            continue
        if ch.isalpha() and rng.random() < p["p_drop"]:
            edit(i, ch, "")
            i += 1
            continue
        out.append(ch)
        col, i = col + 1, i + 1
    return "".join(out), {"seed": seed, "width": width, "params": p, "ops": ops}


def restore(degraded, record):
    """Undo the edits of `degrade`, checking each one."""
    out, pos, delta = [], 0, 0  # pos: position in degraded; delta: degraded offset minus clean offset
    for op in record["ops"]:
        d_at = op["at"] + delta
        out.append(degraded[pos:d_at])
        if degraded[d_at:d_at + len(op["new"])] != op["new"]:
            raise ValueError(f"noise record does not match the degraded text at {d_at}")
        out.append(op["orig"])
        pos = d_at + len(op["new"])
        delta += len(op["new"]) - len(op["orig"])
    out.append(degraded[pos:])
    return "".join(out)


def stats(record, clean):
    ops = record["ops"]
    letters = sum(c.isalpha() for c in clean) or 1
    return {"edits": len(ops),
            "dropped": sum(1 for o in ops if o["new"] == "" and o["orig"]),
            "dropped_share_of_characters": round(sum(1 for o in ops if o["new"] == "" and o["orig"]) / max(1, len(clean)), 5),
            "confusions": sum(1 for o in ops if o["orig"] in ("rn",) or (o["orig"] in CONFUSE and o["new"] == CONFUSE[o["orig"]])),
            "diacritics": sum(1 for o in ops if len(o["orig"]) == 1 and o["orig"].isalpha() and o["new"] and o["new"] != CONFUSE.get(o["orig"]) and o["orig"] != o["new"]),
            "line_breaks": sum(1 for o in ops if o["new"] == "\n"),
            "hyphenations": sum(1 for o in ops if o["new"] == "-\n"),
            "letters": letters}
