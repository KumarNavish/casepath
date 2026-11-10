"""The two mould claims of the running example, rendered as PDFs with the product's own renderer.

The texts are the case-1 family of `../../en2/source/seed_en.py` (variants "yes" and "open"), unchanged: the files
differ in one paragraph of the claim form only. Every name, address and firm is invented. Both cases get the same
title, so that nothing but that paragraph differs.

    from claims import files   # files("stated" | "open") -> [(file name, PDF bytes)]
"""
HEALTH = {
    "stated": "Our daughter has been coughing for weeks; the paediatrician suspects a link with the mould. "
              "I do not have a medical report yet.",
    "open": "Our daughter has been coughing for a few weeks; we do not know whether it has anything to do with the mould "
            "and have not seen a doctor.",
}
TITLE = "Synthetic claim: mould in the bathroom and the child's room"

P = lambda t: {"type": "paragraph", "label": "", "text": t}
F = lambda l, t: {"type": "field", "label": l, "text": t}


def doc(kind, title, date, layout, sender, recipient, blocks):
    return {"kind": kind, "title": title, "date": date, "layout": layout, "sender": sender, "recipient": recipient,
            "language": "en", "features": ["signature"], "meets_needs": [], "blocks": blocks}


def specs(variant):
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


def files(variant):
    from casepath.quality.synthetic import render_digital  # the product's own PDF renderer
    return [(name, render_digital(spec, {"title": TITLE})) for name, spec in specs(variant)]
