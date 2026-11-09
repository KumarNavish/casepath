"""Seed one synthetic mould case for UI rendering. All names and places are invented."""
import sys
from casepath_internal.store import CaseStore
from casepath_internal.extract import extract
from casepath_internal.synthetic import render_digital

USER = "Sachbearbeitung (Demo)"
CASE = {"title": "Synthetischer Fall: Schimmel im Bad und im Kinderzimmer"}

def doc(kind, title, date, layout, sender, recipient, blocks, features=()):
    return {"kind": kind, "title": title, "date": date, "layout": layout, "sender": sender, "recipient": recipient,
            "language": "de", "features": list(features), "meets_needs": [], "blocks": blocks}

P = lambda t: {"type": "paragraph", "label": "", "text": t}
F = lambda l, t: {"type": "field", "label": l, "text": t}

report = doc("form", "Schadenmeldung Rechtsschutz", "2026-11-03", "form", "Anna Beispiel\nMustergasse 12\n3000 Bern",
             "Rechtsschutz Schadenservice (synthetisch)", [
    F("Versicherte Person", "Anna Beispiel"), F("Gegenpartei", "Muster Immobilien AG (Vermieterin)"),
    F("Rechtsgebiet", "Mietrecht"),
    P("Seit Anfang Oktober bildet sich im Badezimmer und im Kinderzimmer schwarzer Schimmel an der Aussenwand."),
    P("Ich habe den Hauswart am 14. Oktober telefonisch informiert. Schriftlich habe ich der Verwaltung noch nichts geschickt."),
    P("Unsere Tochter hustet seit Wochen; die Kinderärztin vermutet einen Zusammenhang mit dem Schimmel. Einen Arztbericht habe ich noch nicht."),
    P("Fotos des Schimmels lege ich bei. Was muss ich jetzt tun?")], ["signature"])
lease = doc("contract", "Mietvertrag für Wohnräume", "2021-03-01", "plain", "Muster Immobilien AG\nBeispielstrasse 1\n3000 Bern",
            "Anna Beispiel", [
    F("Vermieterin", "Muster Immobilien AG, Beispielstrasse 1, 3000 Bern"), F("Mieterin", "Anna Beispiel"),
    F("Mietobjekt", "3½-Zimmer-Wohnung, 2. OG links, Mustergasse 12, 3000 Bern"), F("Mietbeginn", "1. April 2021"),
    F("Nettomietzins", "CHF 1'850.– pro Monat"),
    P("Mängel, die die Mieterin nicht selbst zu beseitigen hat, sind der Vermieterin schriftlich anzuzeigen."),
    P("Eine telefonische Meldung an den Hauswart ersetzt die schriftliche Anzeige an die Vermieterin nicht.")], ["signature"])
photos = doc("photo_sheet", "Fotodokumentation Schimmel", "2026-11-02", "plain", "Anna Beispiel", "", [
    P("Foto 1: Badezimmer, Aussenwand neben dem Fenster, schwarzer Schimmel auf etwa 40 x 30 cm."),
    P("Foto 2: Kinderzimmer, Ecke hinter dem Bett an der Aussenwand, Schimmelflecken bis etwa 1 m Höhe."),
    P("Foto 3: Kinderzimmer, Fensterlaibung mit Kondenswasser und Verfärbung.")])

store = CaseStore(sys.argv[1])
case = store.create_case(CASE["title"], {"synthetic": True}, USER)
for name, spec in (("schadenmeldung.pdf", report), ("mietvertrag.pdf", lease), ("fotodokumentation.pdf", photos)):
    data = render_digital(spec, CASE)
    row = extract(name, "application/pdf", data)
    store.add_file(case["id"], name, row["media_type"], row["kind"], data, row, USER)
store.close()
print(case["id"])
