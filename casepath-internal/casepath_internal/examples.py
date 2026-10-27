"""A made-up example case for trying CasePath without any real case data.

    python -m casepath_internal.examples <data-dir> <catalogue-dir>

It copies the synthetic example workflow into the catalogue and creates one
case with a customer e-mail, a management letter (PDF) and a photo. Everything
in it is invented; it is labelled synthetic wherever it appears.
"""
import io
import json
from pathlib import Path
import shutil
import sys

from .extract import extract
from .synthetic import render_digital

WORKFLOW = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "example-defect.json"
TOLD = "Ich habe die Verwaltung am 3. Februar schriftlich über den Schimmel informiert."
VENT = "Ich lüfte dreimal täglich, trotzdem kommt der Schimmel an der Aussenwand zurück."
REPLY = "Wir haben Ihre Meldung vom 3. Februar erhalten und werden die Angelegenheit prüfen."
EMAIL = (f"From: Lea Brunner <lea.brunner@example.ch>\r\nTo: schaden@example-rechtsschutz.ch\r\nDate: Mon, 10 Feb 2025 09:14:00 +0100\r\n"
         f"Subject: Schimmel im Badezimmer, Kramgasse 5\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nGuten Tag\r\n\r\n"
         f"Im Badezimmer meiner Wohnung bildet sich seit Dezember schwarzer Schimmel. {TOLD} {VENT} "
         f"Die Verwaltung hat bisher nur den Eingang bestätigt.\r\n\r\nFreundliche Grüsse\r\nLea Brunner\r\n").encode()
LETTER = {"kind": "letter", "title": "Ihre Meldung betreffend Schimmel", "date": "2025-02-07", "layout": "letterhead",
          "sender": "Immo Aare AG\nBubenbergplatz 9\n3011 Bern", "recipient": "Frau Lea Brunner\nKramgasse 5\n3011 Bern",
          "language": "de", "features": ["logo", "signature"], "meets_needs": [],
          "blocks": [{"type": "paragraph", "label": "", "text": "Sehr geehrte Frau Brunner"},
                     {"type": "paragraph", "label": "", "text": REPLY + " Bitte lüften Sie weiterhin regelmässig."},
                     {"type": "signature", "label": "", "text": "Freundliche Grüsse\nImmo Aare AG"}]}


def photo():
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (640, 480), (214, 210, 200))
    draw = ImageDraw.Draw(image)
    for i in range(160):
        x, y = (i * 37) % 600 + 10, 40 + (i * 53) % 260
        draw.ellipse([x, y, x + 6 + i % 9, y + 5 + i % 7], fill=(40 + i % 30, 45, 40))
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=80)
    return out.getvalue()


def files(title="Beispiel"):
    return [("Meldung Lea Brunner.eml", "message/rfc822", EMAIL),
            ("Antwort Immo Aare AG.pdf", "application/pdf", render_digital(LETTER, {"title": title})),
            ("Badezimmer Aussenwand.jpg", "image/jpeg", photo())]


def seed(store, catalogue_dir, user, title="Beispiel (synthetisch): Schimmel im Badezimmer, Kramgasse 5"):
    Path(catalogue_dir).mkdir(parents=True, exist_ok=True)
    target = Path(catalogue_dir) / WORKFLOW.name
    if not target.exists():
        shutil.copyfile(WORKFLOW, target)
    workflow = json.loads(WORKFLOW.read_text())
    case = store.create_case(title, {"synthetic": True}, user)
    for name, media_type, data in files(title):
        row = extract(name, media_type, data)
        store.add_file(case["id"], name, row["media_type"], row["kind"], data, row, user)
    store.select_workflow(case["id"], workflow["id"], workflow["version"], user)
    return case


def main(argv=None):
    from .store import CaseStore
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) not in (2, 3):
        sys.exit("usage: python -m casepath_internal.examples <data-dir> <catalogue-dir> [user]")
    case = seed(CaseStore(argv[0]), argv[1], argv[2] if len(argv) == 3 else "example")
    print(f"example case {case['id']}")


if __name__ == "__main__":
    main()
