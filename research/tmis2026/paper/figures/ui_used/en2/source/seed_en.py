"""English synthetic mould cases for UI rendering. All names, places and firms are invented.

    python seed_en.py <data-dir> yes|open|no|case2
"""
import sys
from casepath_internal.store import CaseStore
from casepath_internal.extract import extract
from casepath_internal.synthetic import render_digital

USER = "Case handler (demo)"
HEALTH = {
    "yes": "Our daughter has been coughing for weeks; the paediatrician suspects a link with the mould. I do not have a medical report yet.",
    "open": "Our daughter has been coughing for a few weeks; we do not know whether it has anything to do with the mould and have not seen a doctor.",
    "no": "Nobody in our household has any health complaints.",
}
TITLES = {"yes": "Synthetic case: mould in the bathroom and the child's room",
          "open": "Synthetic case: mould in the bathroom and the child's room (health not known)",
          "no": "Synthetic case: mould in the bathroom and the child's room (no health complaints)",
          "case2": "Synthetic case: mould on the outer wall of the bedroom"}
P = lambda t: {"type": "paragraph", "label": "", "text": t}
F = lambda l, t: {"type": "field", "label": l, "text": t}

def doc(kind, title, date, layout, sender, recipient, blocks):
    return {"kind": kind, "title": title, "date": date, "layout": layout, "sender": sender, "recipient": recipient,
            "language": "en", "features": ["signature"], "meets_needs": [], "blocks": blocks}

def case1(variant):
    claim = doc("form", "Legal protection claim", "2026-11-03", "form", "Anna Example\n12 Sample Lane\n3000 Bern",
                "Legal protection claims service (synthetic)", [
        F("Insured person", "Anna Example"), F("Opposing party", "Sample Properties Ltd (landlord)"), F("Legal area", "Tenancy law"),
        P("Since early October, black mould has been growing on the outer wall of the bathroom and of the child's room."),
        P("I told the caretaker by phone on 14 October. I have not yet sent anything to the management in writing."),
        P(HEALTH[variant]),
        P("I attach photos of the mould. What should I do now?")])
    lease = doc("contract", "Residential lease (excerpt)", "2021-03-01", "plain", "Sample Properties Ltd\n1 Example Street\n3000 Bern",
                "Anna Example", [
        F("Landlord", "Sample Properties Ltd, 1 Example Street, 3000 Bern"), F("Tenant", "Anna Example"),
        F("Premises", "3.5-room flat, 2nd floor left, 12 Sample Lane, 3000 Bern"), F("Start of tenancy", "1 April 2021"),
        F("Net rent", "CHF 1,850 per month"),
        P("Defects that the tenant does not have to remedy herself must be reported to the landlord in writing."),
        P("A report by telephone to the caretaker does not replace written notice to the landlord.")])
    photos = doc("photo_sheet", "Photo documentation: mould", "2026-11-02", "plain", "Anna Example", "", [
        P("Photo 1: bathroom, outer wall next to the window, black mould over about 40 x 30 cm."),
        P("Photo 2: child's room, corner behind the bed on the outer wall, mould stains up to about 1 m high."),
        P("Photo 3: child's room, window reveal with condensation and discoloration.")])
    return [("claim.pdf", claim), ("lease.pdf", lease), ("photos.pdf", photos)]

def case2():
    claim = doc("form", "Legal protection claim", "2026-11-05", "form", "Mark Sample\n4 Example Way\n4000 Basel",
                "Legal protection claims service (synthetic)", [
        F("Insured person", "Mark Sample"), F("Opposing party", "Example Management Ltd (landlord)"), F("Legal area", "Tenancy law"),
        P("Since the summer, mould has been growing on the outer wall of the bedroom behind the wardrobe."),
        P("On 2 October I sent the landlord a written notice of the defect by registered post."),
        P("The management replies that the mould comes from wrong ventilation. I air the flat morning and evening and have kept a ventilation log for three weeks, which I attach."),
        P("Nobody in our household has any health complaints.")])
    notice = doc("letter", "Notice of defect: mould in the bedroom", "2026-10-02", "letterhead", "Mark Sample\n4 Example Way\n4000 Basel",
                 "Example Management Ltd\n2 Sample Square\n4000 Basel", [
        P("Dear Sir or Madam"),
        P("I hereby give you written notice that mould is forming on the outer wall of the bedroom of my flat, and ask you to remedy the defect."),
        {"type": "signature", "label": "", "text": "Yours faithfully\nMark Sample"}])
    log = doc("protocol", "Ventilation log", "2026-11-04", "plain", "Mark Sample", "", [
        P("Ventilation log 14.10.-3.11.2026, bedroom: daily at 7.00 and 21.00, 10 minutes of full airing each time; room temperature 20-21 °C."),
        P("Humidity readings are missing; a hygrometer has only just been ordered.")])
    return [("claim.pdf", claim), ("notice-of-defect.pdf", notice), ("ventilation-log.pdf", log)]

variant = sys.argv[2]
files = case2() if variant == "case2" else case1(variant)
store = CaseStore(sys.argv[1])
case = store.create_case(TITLES[variant], {"synthetic": True}, USER)
for name, spec in files:
    data = render_digital(spec, {"title": TITLES[variant]})
    row = extract(name, "application/pdf", data)
    store.add_file(case["id"], name, row["media_type"], row["kind"], data, row, USER)
store.close()
print(case["id"])
