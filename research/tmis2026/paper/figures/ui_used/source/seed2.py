"""Second synthetic mould case, used to show Knowledge applied and refined. All names invented."""
import sys
from casepath_internal.store import CaseStore
from casepath_internal.extract import extract
from casepath_internal.synthetic import render_digital
USER = "Sachbearbeitung (Demo)"
CASE = {"title": "Synthetischer Fall: Schimmel an der Aussenwand im Schlafzimmer"}
def doc(kind, title, date, layout, sender, recipient, blocks):
    return {"kind": kind, "title": title, "date": date, "layout": layout, "sender": sender, "recipient": recipient,
            "language": "de", "features": ["signature"], "meets_needs": [], "blocks": blocks}
P = lambda t: {"type": "paragraph", "label": "", "text": t}
F = lambda l, t: {"type": "field", "label": l, "text": t}
report = doc("form", "Schadenmeldung Rechtsschutz", "2026-11-05", "form", "Marco Muster\nBeispielweg 4\n4000 Basel",
             "Rechtsschutz Schadenservice (synthetisch)", [
    F("Versicherte Person", "Marco Muster"), F("Gegenpartei", "Beispiel Verwaltungen GmbH (Vermieterin)"), F("Rechtsgebiet", "Mietrecht"),
    P("Im Schlafzimmer wächst seit dem Sommer Schimmel an der Aussenwand hinter dem Schrank."),
    P("Am 2. Oktober habe ich der Vermieterin per Einschreiben eine schriftliche Mängelanzeige geschickt."),
    P("Die Verwaltung schreibt zurück, der Schimmel komme von falschem Lüften. Ich lüfte morgens und abends und führe seit drei Wochen ein Lüftungsprotokoll, das ich beilege."),
    P("Gesundheitliche Beschwerden haben wir keine.")])
notice = doc("letter", "Mängelanzeige Schimmel Schlafzimmer", "2026-10-02", "letterhead", "Marco Muster\nBeispielweg 4\n4000 Basel",
             "Beispiel Verwaltungen GmbH\nMusterplatz 2\n4000 Basel", [
    P("Sehr geehrte Damen und Herren"),
    P("Hiermit zeige ich Ihnen schriftlich an, dass sich im Schlafzimmer meiner Wohnung an der Aussenwand Schimmel bildet, und bitte Sie, den Mangel zu beheben."),
    {"type": "signature", "label": "", "text": "Freundliche Grüsse\nMarco Muster"}])
log = doc("protocol", "Lüftungsprotokoll", "2026-11-04", "plain", "Marco Muster", "", [
    P("Lüftungsprotokoll 14.10.–3.11.2026, Schlafzimmer: täglich 7.00 und 21.00 Uhr je 10 Minuten Stosslüften; Raumtemperatur 20–21 °C."),
    P("Es fehlen Messwerte zur Luftfeuchtigkeit; ein Hygrometer ist erst bestellt.")])
store = CaseStore(sys.argv[1])
case = store.create_case(CASE["title"], {"synthetic": True}, USER)
for name, spec in (("schadenmeldung.pdf", report), ("maengelanzeige.pdf", notice), ("lueftungsprotokoll.pdf", log)):
    data = render_digital(spec, CASE); row = extract(name, "application/pdf", data)
    store.add_file(case["id"], name, row["media_type"], row["kind"], data, row, USER)
store.close(); print(case["id"])
