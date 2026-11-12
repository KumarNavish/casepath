"""Extract named articles from a Fedlex Akoma Ntoso consolidated-text XML file.

Run with `python3 -I extract.py <xml> <date> <lang> <article-eId>... > out.txt`.
The XML is untrusted data: it is parsed with the standard library only, no
entity expansion beyond XML's own, and nothing in it is executed. Footnotes
(authorialNote) are dropped; superscripts are written inline (c<sup>bis</sup>
-> cbis); whitespace runs collapse to one space.
"""
import re
import sys
import xml.etree.ElementTree as ET

NS = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}"


def local(tag):
    return tag.split("}", 1)[-1] if isinstance(tag, str) else ""


def text_of(el):
    """Text of an element without footnotes."""
    out = []

    def walk(e):
        if local(e.tag) == "authorialNote":
            if e.tail:
                out.append(e.tail)
            return
        if e.text:
            out.append(e.text)
        for c in e:
            walk(c)
        if e.tail:
            out.append(e.tail)
    if el.text:
        out.append(el.text)
    for c in el:
        walk(c)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def article_lines(art, parents):
    lines = []
    num = art.find(NS + "num")
    lines.append(text_of(num) if num is not None else art.get("eId"))
    trail, node = [], parents.get(art)
    while node is not None:
        if local(node.tag) == "level" and node.get("{http://fedlex.admin.ch/}role") == "marginal":
            h = node.find(NS + "heading")
            n = node.find(NS + "num")
            if h is not None:
                trail.append(((text_of(n) + " ") if n is not None else "") + text_of(h))
        node = parents.get(node)
    if trail:
        lines.append("[Marginal headings: " + " / ".join(reversed(trail)) + "]")
    heading = art.find(NS + "heading")
    if heading is not None:
        lines.append(text_of(heading))
    for para in art.iter(NS + "paragraph"):
        pnum = para.find(NS + "num")
        prefix = (text_of(pnum) + " ") if pnum is not None else ""
        content = para.find(NS + "content")
        if content is None:
            continue
        intro = content.find(".//" + NS + "listIntroduction")
        items = content.findall(".//" + NS + "item")
        if intro is not None or items:
            if intro is not None:
                lines.append(prefix + text_of(intro))
                prefix = ""
            for item in items:
                inum = item.find(NS + "num")
                body = " ".join(text_of(p) for p in item.findall(NS + "p"))
                lines.append((prefix + (text_of(inum) + " " if inum is not None else "") + body).strip())
                prefix = ""
            for p in content.findall(NS + "p"):
                lines.append(text_of(p))
        else:
            body = " ".join(text_of(p) for p in content.findall(NS + "p"))
            lines.append((prefix + body).strip())
    return lines


def main():
    path, date, lang, *wanted = sys.argv[1:]
    root = ET.parse(path).getroot()
    found = {a.get("eId"): a for a in root.iter(NS + "article")}
    parents = {c: p for p in root.iter() for c in p}
    for eid in wanted:
        if eid not in found:
            raise SystemExit(f"article {eid} not found")
        print("\n".join(article_lines(found[eid], parents)))
        print()


if __name__ == "__main__":
    main()
