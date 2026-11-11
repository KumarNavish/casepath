"""'Stand am': a file as it stood at a moment of the case, holding only the pages chosen (all dated up to the cut).

The original page numbers are kept, so citations, page images and segments stay valid and nothing is read again.
The PDF gets an incremental update whose page tree lists only the kept pages: every viewer then shows those pages only.
ponytail: the later pages' bytes stay inside the file (a viewer never shows them); rewrite the PDF if that must not be.
"""
import re

from .pdfread import Document, Name, PdfError, Ref, Stream


def parse_pages(spec, total):
    """'5-10, 12' → [5, 6, 7, 8, 9, 10, 12], within 1..total."""
    pages = set()
    for part in str(spec or "").replace(" ", "").split(","):
        match = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if not match:
            raise ValueError(f"not a page range: {part!r}")
        first, last = int(match.group(1)), int(match.group(2) or match.group(1))
        if not 1 <= first <= last <= total:
            raise ValueError(f"pages {part} are outside 1–{total}")
        pages.update(range(first, last + 1))
    if not pages:
        raise ValueError("no pages chosen")
    return sorted(pages)


def _pdf(value):
    if isinstance(value, Name):
        return "/" + re.sub(r"[^A-Za-z0-9_.+-]", lambda m: "".join(f"#{b:02X}" for b in m.group().encode("latin-1")), value)
    if isinstance(value, Ref):
        return f"{value[0]} {value[1]} R"
    if value is True or value is False:
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return f"{value:g}" if isinstance(value, float) else str(value)
    if isinstance(value, bytes):
        return "<" + value.hex() + ">"
    if isinstance(value, list):
        return "[" + " ".join(_pdf(v) for v in value) + "]"
    if isinstance(value, dict):
        return "<<" + " ".join(f"{_pdf(Name(k))} {_pdf(v)}" for k, v in value.items()) + ">>"
    return str(value)  # a bare keyword


def _page_refs(doc, node_ref, refs, seen):
    node = doc.resolve(node_ref)
    if not isinstance(node, dict) or id(node) in seen:
        return
    seen.add(id(node))
    kids = doc.resolve(node.get("Kids"))
    if node.get("Type") == "Pages" or isinstance(kids, list) and node.get("Type") != "Page":
        for kid in kids or []:
            _page_refs(doc, kid, refs, seen)
    else:
        refs.append(node_ref)


def cut_pdf(data, keep):
    """The PDF with a page tree of the kept pages (1-based, original numbering) appended as an incremental update."""
    doc = Document(data)
    trailer = doc._trailer()
    root = doc.resolve(trailer.get("Root"))
    pages_node = doc.resolve(root.get("Pages"))
    refs = []
    _page_refs(doc, root.get("Pages"), refs, set())
    if len(refs) != len(doc.pages) or not all(isinstance(r, Ref) for r in refs):
        raise PdfError("the page tree cannot be cut")
    pages_no = max(doc.objects) + 1
    catalog_no = pages_no + 1
    tree = {"Type": Name("Pages"), "Kids": [refs[p - 1] for p in keep], "Count": len(keep),
            **{k: pages_node[k] for k in ("Resources", "MediaBox", "Rotate") if k in pages_node}}
    catalog = {**root, "Pages": Ref((pages_no, 0))}
    out = bytearray(data if data.endswith(b"\n") else data + b"\n")
    offsets = []
    for number, value in ((pages_no, tree), (catalog_no, catalog)):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{_pdf(value)}\nendobj\n".encode("latin-1")
    previous = re.findall(rb"startxref\s+(\d+)", data)
    xref = len(out)
    out += (f"xref\n{pages_no} 2\n" + "".join(f"{o:010d} 00000 n \n" for o in offsets)
            + f"trailer\n<< /Size {catalog_no + 1} /Root {catalog_no} 0 R"
            + (f" /Prev {int(previous[-1])}" if previous else "") + f" >>\nstartxref\n{xref}\n%%EOF\n").encode("latin-1")
    return bytes(out)


def cut_extraction(extraction, keep):
    """The read text, page images and documents of the kept pages only; numbering unchanged."""
    kept = set(keep)
    blocks = re.findall(r"\[page (\d+)\]\n(.*?)(?=\n\n\[page \d+\]\n|\Z)", extraction.get("text", ""), re.S)
    text = "\n\n".join(f"[page {n}]\n{body}" for n, body in blocks if int(n) in kept)
    out = {**extraction, "text": text, "readable": bool(text), "kept_pages": sorted(kept)}
    for key in ("pages_transcribed", "pages_without_text", "instruction_like"):
        if isinstance(extraction.get(key), list):
            out[key] = [n for n in extraction[key] if (n if isinstance(n, int) else n.get("page")) in kept]
    for key in ("unread_reasons", "page_images"):
        if isinstance(extraction.get(key), dict):
            out[key] = {k: v for k, v in extraction[key].items() if int(k) in kept}
    if extraction.get("segments") is not None:
        out["segments"] = [{**s, "last_page": max(p for p in kept if s["first_page"] <= p <= s["last_page"])}
                           for s in extraction["segments"] if s["first_page"] in kept]
    return out


def extract_pdf(data, keep):
    """A new PDF holding only the kept pages (1-based) and the objects they use, so it is small.

    Links and annotations are left out: they can point at other pages and would pull the whole file back in.
    """
    doc = Document(data)
    numbers, order = {}, []

    def walk(value):
        if isinstance(value, Ref):
            if value[0] not in numbers and value[0] in doc.objects:
                numbers[value[0]] = len(numbers) + 3 + len(keep)
                order.append(value[0])
                walk(doc.objects[value[0]])
        elif isinstance(value, Stream):
            walk(value.dict)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key not in ("Parent", "P"):
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    def renumber(value):
        if isinstance(value, Ref):
            return Ref((numbers[value[0]], 0)) if value[0] in numbers else None
        if isinstance(value, dict):
            return {k: renumber(v) for k, v in value.items()}
        if isinstance(value, list):
            return [renumber(v) for v in value]
        return value

    pages = [{k: v for k, v in doc.pages[p - 1].items() if k not in ("Parent", "Annots", "StructParents", "B")} for p in keep]
    for page in pages:
        walk(page)
    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}

    def write(number, body):
        offsets[number] = len(out)
        out.extend(f"{number} 0 obj\n".encode("latin-1") + body + b"\nendobj\n")

    write(1, _pdf({"Type": Name("Catalog"), "Pages": Ref((2, 0))}).encode("latin-1"))
    write(2, _pdf({"Type": Name("Pages"), "Kids": [Ref((3 + i, 0)) for i in range(len(pages))], "Count": len(pages)}).encode("latin-1"))
    for i, page in enumerate(pages):
        write(3 + i, _pdf({**renumber(page), "Parent": Ref((2, 0))}).encode("latin-1"))
    for old in order:
        obj = doc.objects[old]
        if isinstance(obj, Stream):
            head = _pdf({**renumber(obj.dict), "Length": len(obj.raw)}).encode("latin-1")
            write(numbers[old], head + b"\nstream\n" + obj.raw + b"\nendstream")
        else:
            write(numbers[old], _pdf(renumber(obj)).encode("latin-1"))
    size = 3 + len(keep) + len(order)
    xref = len(out)
    out += f"xref\n0 {size}\n0000000000 65535 f \n".encode("latin-1")
    out += "".join(f"{offsets[n]:010d} 00000 n \n" for n in range(1, size)).encode("latin-1")
    out += f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("latin-1")
    return bytes(out)
