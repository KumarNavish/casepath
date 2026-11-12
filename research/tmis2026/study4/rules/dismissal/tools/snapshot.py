"""Write the cited-article snapshots sources/<id>.txt from the raw Fedlex XML.

Run from the regime directory: `python3 -I tools/snapshot.py`.
Only the articles cited by rules.json are stored (the list is below and
check.py confirms every stored article is cited and every cited one stored).
"""
import hashlib
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REGIME = HERE.parent
RAW = REGIME / "sources" / "raw"
ARTICLES = ["art_335", "art_335_b", "art_335_c", "art_336", "art_336_a", "art_336_b",
            "art_336_c", "art_337", "art_337_c"]
SNAPSHOTS = {
    "co-sr220-en": ("co_20261001_en.xml", "en", "English (official translation, not authoritative)"),
    "co-sr220-de": ("co_20261001_de.xml", "de", "German (authoritative text)"),
}
URL = "https://fedlex.data.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/27/317_321_377/20261001/{l}/xml/fedlex-data-admin-ch-eli-cc-27-317_321_377-20261001-{l}-xml.xml"


def main():
    for sid, (raw, lang, label) in SNAPSHOTS.items():
        path = RAW / raw
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        body = subprocess.run([sys.executable, "-I", str(HERE / "extract.py"), str(path), "2026-10-01", lang, *ARTICLES],
                              check=True, capture_output=True, text=True).stdout
        header = (f"# Swiss Code of Obligations (SR 220), Title Ten, cited articles only\n"
                  f"# Language: {label}\n"
                  f"# Consolidated version applicable from 2026-10-01 (jolux:dateApplicability)\n"
                  f"# Extracted from: {URL.format(l=lang)}\n"
                  f"# Raw download sha256: {digest}\n"
                  f"# Footnotes (amendment history) omitted; superscripts written inline (cbis = c-bis).\n\n")
        (REGIME / "sources" / f"{sid}.txt").write_text(header + body, encoding="utf-8")
        print(sid, "written")


if __name__ == "__main__":
    main()
