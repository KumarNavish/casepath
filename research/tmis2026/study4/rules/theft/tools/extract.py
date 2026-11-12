"""Extract text from the downloaded source documents and locate passages in it.

Run with `python3 -I tools/extract.py <raw dir> <out dir> [passages.json]`. The raw directory holds the downloads
(sources/raw/); the extracted full texts are written to <out dir>, which must lie OUTSIDE the repository (the insurers'
documents are their copyright: only quoted passages are kept in the repository).

For PDFs the text comes from `pdftotext` (poppler); for the Fedlex XML, from the Akoma Ntoso elements. Matching is
reported at two levels:
  exact  - the passage occurs after collapsing whitespace and joining words hyphenated across a line break;
  letters - the passage occurs when only letters and digits are compared (layout artefacts, quotes, dashes ignored).
"""
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
import xml.etree.ElementTree as ET


def pdf_text(path):
    out = subprocess.run(["pdftotext", "-enc", "UTF-8", str(path), "-"], capture_output=True, check=True)
    return out.stdout.decode("utf-8")


def xml_text(path):
    """Plain text of an Akoma Ntoso file, one line per paragraph-like element."""
    root = ET.parse(path).getroot()
    lines = []
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag in ("p", "num", "heading"):
            text = "".join(el.itertext()).strip()
            if text:
                lines.append(text)
    return "\n".join(lines)


def normalise(text):
    text = unicodedata.normalize("NFC", text).replace("­", "").replace(" ", " ").replace(" ", " ")
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)  # hyphenation across a line break
    return re.sub(r"\s+", " ", text).strip()


def letters(text):
    return "".join(ch for ch in unicodedata.normalize("NFC", text).lower() if ch.isalnum())


def locate(passage, text):
    n = normalise(text)
    if normalise(passage) in n:
        return "exact"
    if letters(passage) in letters(text):
        return "letters"
    return "absent"


def main():
    raw, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    texts = {}
    for path in sorted(raw.iterdir()):
        if path.suffix == ".pdf":
            texts[path.stem] = pdf_text(path)
        elif path.suffix == ".xml":
            texts[path.stem] = xml_text(path)
        else:
            continue
        (out / f"{path.stem}.txt").write_text(texts[path.stem], encoding="utf-8")
    if len(sys.argv) > 3:
        passages = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))["passages"]
        rows = []
        for p in passages:
            rows.append({"id": p["id"], **{k: locate(p["text"], t) for k, t in texts.items()}})
        (out / "passage_matches.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
        for k in texts:
            counts = {}
            for r in rows:
                counts[r[k]] = counts.get(r[k], 0) + 1
            print(k, counts)


if __name__ == "__main__":
    main()
