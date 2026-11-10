"""Readable case text, exact-quote location and plain keyword search.

Quotes are matched after the changes PDF extraction typically introduces:
collapsed whitespace, soft hyphens and words split across a line break. The
match is otherwise exact and case-sensitive, so a citation either points to
the words in the document or is rejected.
"""
import re
import unicodedata

PAGE = re.compile(r"\[page (\d+)\]\n")
WORD = re.compile(r"\w+", re.UNICODE)


def normalise(text):
    text = text.replace("­", "")
    text = re.sub(r"(\w)-[ \t]*\n[ \t]*(\w)", r"\1\2", text)
    return re.sub(r"\s+", " ", text).strip()


TYPOGRAPHY = {**{c: '"' for c in "“”„‟«»″〝〞"}, **{c: "'" for c in "‘’‚‛‹›′`´"}, **{c: "-" for c in "‐‑‒–—―−"}}


def _typographic(text):
    """Text with typography folded (NFKC, then quotation marks, apostrophes and dashes unified), and for each folded
    character the index of the character it came from."""
    out, index = [], []
    for i, ch in enumerate(text):
        for c in unicodedata.normalize("NFKC", ch):
            out.append(TYPOGRAPHY.get(c, c))
            index.append(i)
    return re.sub(r"\s", " ", "".join(out)), index


def _fold(text):
    return text.casefold().replace("ß", "ss")


class Evidence:
    def __init__(self, files):
        self.files = {}
        for row in files:
            pages = []
            raw = row.get("text") or ""
            marks = list(PAGE.finditer(raw))
            raws = []
            if marks:
                for index, mark in enumerate(marks):
                    end = marks[index + 1].start() if index + 1 < len(marks) else len(raw)
                    raws.append((int(mark.group(1)), raw[mark.end():end]))
            elif raw.strip():
                raws.append((None, raw))
            pages = [(page, normalise(chunk)) for page, chunk in raws]
            self.files[row["id"]] = {**{k: v for k, v in row.items() if k != "text"}, "pages_text": pages, "pages_raw": raws}

    def catalogue(self):
        return [{"file": fid, "name": f.get("name"), "kind": f.get("kind"), "readable": bool(f["pages_text"]),
                 "pages": f.get("pages"), "pages_without_text": len(f.get("pages_without_text") or []),
                 **({"contains_text_addressed_to_an_ai": True} if f.get("instruction_like") else {}),
                 "note": f.get("note"),
                 **({"documents": [{k: s.get(k) for k in ("first_page", "last_page", "kind", "date", "sender", "recipient", "title", "summary")}
                                   for s in f["segments"]]} if f.get("segments") else {})} for fid, f in self.files.items()]

    def read(self, file_id, from_page=None, to_page=None, limit=24000):
        source = self.files[file_id]
        chosen = [(p, t) for p, t in source["pages_text"]
                  if p is None or ((from_page is None or p >= from_page) and (to_page is None or p <= to_page))]
        parts, used, next_page = [], 0, None
        for page, text in chosen:
            block = (f"[page {page}] " if page is not None else "") + text
            if used + len(block) > limit:
                if not parts:
                    parts.append(block[:limit])
                next_page = page
                break
            parts.append(block)
            used += len(block)
        return {"file": file_id, "text": "\n\n".join(parts), "truncated": next_page is not None, "next_page": next_page,
                "note": source.get("note")}

    def locate(self, file_id, quote):
        """The quotation's place in the file: an exact match after normalisation, or else a match that ignores only
        typography (quotation marks, apostrophes, dashes, ligatures and other compatibility forms). Letter case is
        not folded: a quotation is the file's words. The located quote is the file's own text."""
        source = self.files.get(file_id)
        needle = normalise(quote or "")
        if source is None or len(needle) < 8:
            return None
        for page, text in source["pages_text"]:
            start = text.find(needle)
            if start >= 0:
                return {"file": file_id, "page": page, "start": start, "end": start + len(needle), "quote": needle}
        folded_needle, _ = _typographic(needle)
        for page, text in source["pages_text"]:
            folded, index = _typographic(text)
            start = folded.find(folded_needle)
            if start >= 0 and folded_needle:
                begin, end = index[start], index[start + len(folded_needle) - 1] + 1
                return {"file": file_id, "page": page, "start": begin, "end": end, "quote": text[begin:end]}
        return None

    def context(self, located, width=300):
        for page, text in self.files[located["file"]]["pages_text"]:
            if page == located["page"]:
                return text[max(0, located["start"] - width):located["end"] + width]
        return ""

    def search(self, query, limit=8, window=600):
        terms = {_fold(t) for t in WORD.findall(query) if len(t) > 2}
        if not terms:
            return []
        hits = []
        for file_id, source in self.files.items():
            for page, text in source["pages_text"]:
                for start in range(0, max(len(text), 1), window // 2):
                    chunk = text[start:start + window]
                    words = {_fold(w) for w in WORD.findall(chunk)}
                    score = len(terms & words)
                    if score:
                        hits.append((score, file_id, page, start, chunk))
        hits.sort(key=lambda h: (-h[0], h[1], h[2] or 0, h[3]))
        seen, results = set(), []
        for score, file_id, page, start, chunk in hits:
            key = (file_id, page, start // window)
            if key in seen:
                continue
            seen.add(key)
            results.append({"file": file_id, "page": page, "matched_terms": score, "passage": chunk})
            if len(results) == limit:
                break
        return results
