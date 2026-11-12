"""Check every quoted passage of the insurers' snapshots against the public document downloaded to sources/raw/.

Run with `python3 -I tools/verify_sources.py <rule set dir>`. For each block of sources/css-avb.txt and
sources/css-form.txt it reports the page of the downloaded PDF on which the passage occurs and the match level
(exact after collapsing whitespace and soft hyphens; letters = only letters and digits agree; absent). The VVG snapshot
is checked against the Fedlex XML the same way. Writes nothing; prints one line per passage and exits 1 on any
'absent'. Needs `pdftotext`.
"""
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract import letters, normalise  # noqa: E402
from statute import flat  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402

RAW = {"css-avb": "css-avb-hausrat.pdf", "css-form": "css-schadenanzeige.pdf"}


def pages(pdf):
    count = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout).group(1))
    return [subprocess.run(["pdftotext", "-enc", "UTF-8", "-f", str(n), "-l", str(n), str(pdf), "-"],
                           capture_output=True, check=True).stdout.decode("utf-8") for n in range(1, count + 1)]


def blocks(snapshot):
    """(locator, text) of every passage block: a '[locator] ...' line followed by one line of passage text."""
    lines = snapshot.read_text(encoding="utf-8").splitlines()
    return [(lines[i][1:lines[i].index("]")], lines[i + 1]) for i in range(len(lines) - 1) if lines[i].startswith("[")]


def level(passage, text):
    if normalise(passage) in normalise(text):
        return "exact"
    return "letters" if letters(passage) in letters(text) else "absent"


def main():
    root = Path(sys.argv[1])
    bad = 0
    for sid, raw in RAW.items():
        texts = pages(root / "sources" / "raw" / raw)
        for loc, passage in blocks(root / "sources" / f"{sid}.txt"):
            found = [(n + 1, level(passage, t)) for n, t in enumerate(texts)]
            hits = [(n, lv) for n, lv in found if lv != "absent"]
            if not hits:  # a passage running over a page break
                whole = "\n".join(texts)
                hits = [("across pages", level(passage, whole))]
            bad += all(lv == "absent" for _, lv in hits)
            print(f"{sid}\t[{loc}]\t{hits}\t{passage[:70]}")
    statute = flat(ET.parse(root / "sources" / "raw" / "vvg-20240101-de.xml").getroot())  # whole act, notes omitted
    for line in (root / "sources" / "vvg.txt").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith(("#", "Art. ")):
            lv = level(line, statute)
            bad += lv == "absent"
            print(f"vvg\t{lv}\t{line[:70]}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
