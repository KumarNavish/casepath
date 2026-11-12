"""Write the snapshot of the cited articles of a Fedlex Akoma Ntoso file.

Run with `python3 -I tools/statute.py <fedlex xml> <out .txt> <header line>... -- <article eId>...`.
Each paragraph becomes one block: a locator line ("Art. 39 Abs. 2") and the paragraph's text on one line, list
introductions and numbered items joined with single spaces ("Der Vertrag kann verfügen: 1. dass ..."). Authorial notes
(footnotes on amendments) are left out. The output is the statute text exactly as Fedlex serves it, only re-flowed.
"""
import re
import sys
import xml.etree.ElementTree as ET

NS = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}"


def local(tag):
    return tag.rsplit("}", 1)[-1]


def flat(el):
    """Text of an element without authorial notes, whitespace collapsed."""
    parts = []

    def walk(node):
        if local(node.tag) == "authorialNote":
            if node.tail:
                parts.append(node.tail)
            return
        if node.text:
            parts.append(node.text)
        for child in node:
            walk(child)
        if node.tail and node is not el:
            parts.append(node.tail)
    walk(el)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def paragraph_text(par):
    content = next(c for c in par if local(c.tag) == "content")
    pieces = []
    for node in content.iter():
        tag = local(node.tag)
        if tag == "listIntroduction":
            pieces.append(flat(node))
        elif tag == "item":
            num = next((flat(c) for c in node if local(c.tag) == "num"), "")
            body = " ".join(flat(c) for c in node if local(c.tag) == "p")
            pieces.append(f"{num} {body}".strip())
        elif tag == "p" and not any(local(a.tag) == "item" for a in ancestors(content, node)):
            pieces.append(flat(node))
    return " ".join(p for p in pieces if p)


def ancestors(root, target):
    path = []

    def find(node, trail):
        if node is target:
            path.extend(trail)
            return True
        return any(find(child, trail + [node]) for child in node)
    find(root, [])
    return path


def main():
    args = sys.argv[1:]
    split = args.index("--")
    xml_path, out_path, headers, articles = args[0], args[1], args[2:split], args[split + 1:]
    root = ET.parse(xml_path).getroot()
    by_id = {el.get("eId"): el for el in root.iter() if el.get("eId")}
    lines = [f"# {h}" for h in headers]
    for eid in articles:
        art = by_id[eid]
        label = "Art. " + eid.split("_", 1)[1].replace("_", "")
        paragraphs = [c for c in art if local(c.tag) == "paragraph"]
        for par in paragraphs:
            num = next((flat(c) for c in par if local(c.tag) == "num"), "")
            lines.append("")
            lines.append(f"{label} Abs. {num}" if num else label)
            lines.append(paragraph_text(par))
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
