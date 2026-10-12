#!/usr/bin/env python3
"""Reproduce PDF page renders inspected by the reviewer; output is ignored."""
import json
from pathlib import Path

import fitz
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
CORPUS = ROOT / "casepath-api/casepath_api/corpora/synthetic-150"
records = json.loads((OUT / "source_receipts.json").read_text())
renders = OUT / "native-pages"
renders.mkdir(exist_ok=True)
pages = []
for record in records:
    for j, artifact in enumerate(record["artifacts"][1:], 1):
        if artifact["media_type"] != "application/pdf":
            continue
        with fitz.open(CORPUS / artifact["path"]) as document:
            for i, page in enumerate(document):
                target = renders / f'{record["number"]:03}-attachment-{j}-page-{i+1}.png'
                page.get_pixmap(matrix=fitz.Matrix(1, 1)).save(target)
                pages.append((target, f'{record["number"]} {record["claim_id"]} attachment{j} p{i+1}/{len(document)}'))
for n in range(0, len(pages), 3):
    sheet = Image.new("RGB", (1800, 885), "#eee")
    draw = ImageDraw.Draw(sheet)
    for column, (target, label) in enumerate(pages[n:n+3]):
        draw.text((column*600+10, 8), label, fill="black")
        sheet.paste(Image.open(target), (column*600, 36))
    sheet.save(renders / f"sheet-{n//3+1:02}.png")
print(f"Rendered {len(pages)} physical pages in {(len(pages)+2)//3} sheets")
