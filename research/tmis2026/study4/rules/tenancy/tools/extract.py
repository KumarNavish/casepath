"""Extract articles from a Fedlex Akoma Ntoso XML file as plain text.

Run with `python3 -I extract.py <xml> <out.txt> <art-id> [<art-id> ...]`.
An art-id is the article's eId without the `art_` prefix, e.g. `266_l`;
`all:<from>:<to>` dumps every article whose eId lies in document order
between the two (inclusive). Footnotes (authorialNote) are dropped.
The input is untrusted data: it is only parsed, never executed.
"""
import re
import sys
import xml.etree.ElementTree as ET

NS = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}"


def text_of(el):
    """Inline text of an element without footnotes."""
    parts = []

    def walk(e):
        if e.tag == NS + "authorialNote":
            if e.tail:
                parts.append(e.tail)
            return
        if e.text:
            parts.append(e.text)
        for c in e:
            walk(c)
        if e.tail:
            parts.append(e.tail)
    if el.text:
        parts.append(el.text)
    for c in el:
        walk(c)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def label(art):
    num = art.find(NS + "num")
    return text_of(num) if num is not None else art.get("eId")


def render_list(block, prefix=""):
    """Lines of a (possibly nested) list; a nested item's number is prefixed by its parent's, e.g. `e.1.`."""
    out = []
    for sub in block:
        if sub.tag == NS + "listIntroduction" or sub.tag == NS + "listWrapUp":
            out.append(text_of(sub))
        elif sub.tag == NS + "item":
            inum = sub.find(NS + "num")
            n = (prefix + text_of(inum)) if inum is not None else prefix
            ptext = " ".join(text_of(p) for p in sub if p.tag == NS + "p")
            nested = [c for c in sub if c.tag == NS + "blockList"]
            if nested:
                inner = render_list(nested[0], prefix=n)
                head = inner[0] if inner and not nested[0][0].tag == NS + "item" else ""
                rest = inner[1:] if head else inner
                out.append((n + " " + " ".join(x for x in (ptext, head) if x)).rstrip())
                out.extend(rest)
            else:
                out.append((n + " " + ptext).rstrip())
    return out


def render(art, headings):
    lines = [f"=== {label(art)} ==="]
    if headings:
        lines.append("[marginal heading: " + " / ".join(headings) + "]")
    for para in art.iter(NS + "paragraph"):
        num = para.find(NS + "num")
        n = text_of(num) if num is not None else ""
        content = para.find(NS + "content")
        body = []
        if content is not None:
            for child in content:
                if child.tag == NS + "p":
                    body.append(text_of(child))
                elif child.tag == NS + "blockList":
                    body.extend(render_list(child))
        first = True
        for b in body:
            if not b:
                continue
            lines.append((f"{n} " if (first and n) else "") + b)
            first = False
    return "\n".join(lines)


def main():
    src, out, *wanted = sys.argv[1:]
    root = ET.parse(src).getroot()
    parent = {c: p for p in root.iter() for c in p}
    arts = [a for a in root.iter(NS + "article")]
    order = [a.get("eId") for a in arts]
    ids = []
    for w in wanted:
        if w.startswith("all:"):
            _, a, b = w.split(":")
            i, j = order.index("art_" + a), order.index("art_" + b)
            ids.extend(order[i:j + 1])
        else:
            ids.append("art_" + w)
    by_id = {a.get("eId"): a for a in arts}
    blocks = []
    for i in ids:
        if i not in by_id:
            sys.exit(f"article not found: {i}")
        art = by_id[i]
        heads, p = [], parent.get(art)
        while p is not None and p.tag == NS + "level":
            h = p.find(NS + "heading")
            if h is not None and p.get("{http://fedlex.admin.ch/}role") == "marginal":
                heads.insert(0, text_of(h))
            p = parent.get(p)
        blocks.append(render(art, heads))
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n\n".join(blocks) + "\n")


if __name__ == "__main__":
    main()
