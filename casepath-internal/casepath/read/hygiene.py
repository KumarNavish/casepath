"""Reading less: text that repeats across a file's documents is left out of what a model reads.

Most received documents are printed e-mails, each with the same long disclaimer, a signature with legal notices, and
the earlier messages of the thread quoted below. A model reading them pays for that text again and again. Before a
case's text goes to a model, by code:

- a block of lines that appears, identical after whitespace is normalised, in at least three documents is left out of
  every document but the first that contains it (in reading order), when it is long enough to be a block (at least
  ``MIN_BLOCK`` characters), never a short repeated sentence;
- a quoted earlier message (below «-----Original Message-----», «Von: … Gesendet: …», «Am … schrieb …:») is left out
  when its text is already present as its own document of the case.

The original stays intact: the case view shows it, and every quote is located in it, never in the shortened text.
What was left out is marked «[…]». A document is a segment of a file (the reading's document list) or a whole file
without one. Model-free.
"""
import re

MIN_BLOCK = 120  # characters: a disclaimer or a signature with notices, not a repeated sentence
MIN_DOCS = 3
MARK = "[…]"
QUOTED_SHARE = 0.8  # of a quoted message's lines found in one other document

QUOTE_HEAD = re.compile(r"^(?:-{2,}\s*(?:Original Message|Ursprüngliche Nachricht|Originalnachricht|Message d'origine|Messaggio originale|"
                        r"Forwarded message|Weitergeleitete Nachricht)\s*-{2,}|Am\s.{4,120}\sschrieb\s.{1,120}:|On\s.{4,120}\swrote:|"
                        r"Le\s.{4,120}\sa écrit\s?:)\s*$", re.I)
FROM_LINE = re.compile(r"^(?:Von|From|De|Da)\s*:", re.I)
HEADER_LINE = re.compile(r"^(?:Von|From|An|To|Cc|Bcc|Gesendet|Sent|Datum|Date|Betreff|Subject|Objet|Envoyé|Oggetto|Inviato|Da|A)\s*:", re.I)


def _norm(line):
    return re.sub(r"\s+", " ", line.replace("­", "")).strip()


def _unquote(line):
    return _norm(re.sub(r"^(?:\s*>)+", "", line))


def documents(files):
    """The documents of the case in reading order: [(file id, first page, last page)] from each file's segments, or the
    whole file. ``files``: {id: {"pages_raw": [(page, text)], "segments": [...]}} as Evidence holds them."""
    out = []
    for fid, f in files.items():
        pages = [p for p, _ in f.get("pages_raw") or ()]
        # a range «nicht gegliedert» is no document: its pages count one each, as pages no segment names
        segments = [s for s in f.get("segments") or () if s.get("first_page") is not None and not s.get("unsegmented")]
        if segments and all(p is not None for p in pages):
            covered = set()
            for s in segments:
                last = s.get("last_page") or s["first_page"]
                out.append((fid, s["first_page"], last))
                covered |= set(range(s["first_page"], last + 1))
            rest = [p for p in pages if p not in covered]  # pages no segment names stay one document each
            out += [(fid, p, p) for p in rest]
        else:
            out.append((fid, None, None))
    return out


def _lines(f, first, last):
    """[(page, index in page, normalised line)] of one document."""
    rows = []
    for page, raw in f.get("pages_raw") or ():
        if first is not None and (page is None or not first <= page <= last):
            continue
        for i, line in enumerate(raw.split("\n")):
            norm = _norm(line)
            if norm:
                rows.append((page, i, norm))
    return rows


def _quoted_section(lines):
    """The index in ``lines`` where a quoted earlier message begins, or None. A mail's own header at its top is not one."""
    body = next((k for k, (_, _, text) in enumerate(lines) if not HEADER_LINE.match(text)), len(lines))
    for k, (_, _, text) in enumerate(lines):
        if k <= body:
            continue
        if QUOTE_HEAD.match(text):
            return k
        if FROM_LINE.match(text) and any(HEADER_LINE.match(t) and not FROM_LINE.match(t) for _, _, t in lines[k + 1:k + 5]):
            return k
        if text.startswith(">") and k > 0 and all(t.startswith(">") or not t for _, _, t in lines[k:k + 3]):
            return k
    return None


def clean(files):
    """{file id: [(page, raw text as the model reads it)]} and what was left out:
    {"chars", "removed", "blocks", "quoted"}. Pages with nothing left out keep their raw text unchanged."""
    docs = documents(files)
    lines = [_lines(files[fid], first, last) for fid, first, last in docs]
    joined = [" ".join(t for _, _, t in rows) for rows in lines]
    by_line = {}
    for d, rows in enumerate(lines):
        for _, _, text in rows:
            by_line.setdefault(text, set()).add(d)
    drop = [set() for _ in docs]  # indices into lines[d]
    blocks = quoted = 0
    # 1. blocks repeated in at least three documents: left out after the first document that has them
    for d, rows in enumerate(lines):
        i = 0
        while i < len(rows):
            common = set(by_line.get(rows[i][2], ()))
            if len(common) < MIN_DOCS:
                i += 1
                continue
            j = i + 1
            while j < len(rows) and len(common & by_line.get(rows[j][2], set())) >= MIN_DOCS:
                common &= by_line[rows[j][2]]
                j += 1
            text = " ".join(t for _, _, t in rows[i:j])
            holders = sorted(x for x in common if text in joined[x])
            if len(text) >= MIN_BLOCK and len(holders) >= MIN_DOCS and d != holders[0]:
                drop[d] |= set(range(i, j))
                blocks += 1
            i = j if len(text) >= MIN_BLOCK else i + 1
    # 2. a quoted earlier message whose text is its own document of the case
    own_lines = [set(t for _, _, t in rows) | {_unquote(t) for _, _, t in rows} for rows in lines]
    for d, rows in enumerate(lines):
        start = _quoted_section(rows)
        if start is None:
            continue
        body = [_unquote(t) for _, _, t in rows[start:] if not HEADER_LINE.match(_unquote(t)) and not QUOTE_HEAD.match(_unquote(t))]
        body = [t for t in body if len(t) >= 20]
        size = sum(len(t) for t in body)
        if not size:
            continue
        for other in range(len(docs)):
            if other == d:
                continue
            found = sum(len(t) for t in body if t in own_lines[other])
            if found / size >= QUOTED_SHARE:
                drop[d] |= set(range(start, len(rows)))
                quoted += 1
                break
    # the pages as the model reads them
    out, removed, total = {}, 0, 0
    gone = {}
    for d, rows in enumerate(lines):
        for k in drop[d]:
            page, index, text = rows[k]
            gone.setdefault((docs[d][0], page), set()).add(index)
    for fid, f in files.items():
        pages = []
        for page, raw in f.get("pages_raw") or ():
            total += len(_norm(raw))
            cut = gone.get((fid, page))
            if not cut:
                pages.append((page, raw))
                continue
            kept, marked = [], False
            for i, line in enumerate(raw.split("\n")):
                if i in cut:
                    if not marked:
                        kept.append(MARK)
                        marked = True
                    continue
                marked = marked and not _norm(line)
                kept.append(line)
            pages.append((page, "\n".join(kept)))
            removed += len(_norm(raw)) - len(_norm(pages[-1][1]))
        out[fid] = pages
    return out, {"chars": total, "removed": removed, "blocks": blocks, "quoted": quoted}
