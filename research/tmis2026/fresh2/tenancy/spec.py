"""Fixed design of the fresh2 tenancy claims (Study 3 confirmatory data).

The fact meanings, suppliable document types, required content items and the silence-policy
clause are those of fresh/tenancy/spec.py, imported unchanged, so that the rule pack and the
reference engine are identical to Study 2. New here: the 24 families, persona details and the
claim design (open facts, explicitness of each stated fact, attachments).

No compared design reads this file.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parents[2] / "fresh" / "tenancy" / "spec.py"
_s = importlib.util.spec_from_file_location("fresh_tenancy_spec", _path)
_fresh = importlib.util.module_from_spec(_s)
_s.loader.exec_module(_fresh)
DISPUTE, DOC_LABEL, FACTS, FIELD_TEXT = _fresh.DISPUTE, _fresh.DOC_LABEL, _fresh.FACTS, _fresh.FIELD_TEXT
OTHER_DEFECTS, ROUTING, SILENCE_CLAUSE, SUPPLIABLE = (_fresh.OTHER_DEFECTS, _fresh.ROUTING, _fresh.SILENCE_CLAUSE,
                                                      _fresh.SUPPLIABLE)

# 24 families = dispute family x true-flag combination, none used by the 150 Study 1 claims or the 72 fresh/
# claims (checked in build.py). Only 16 combinations with the dispute's defining event true remain unused
# (13 defect, 3 termination, 0 rent increase). The other 8 families are the first ones in which the defining
# event is FALSE: the landlord has announced a termination or an increase, but nothing has been received in
# writing. Under the engine every document is then not needed, whatever the branch flags, so these 8 families
# test whether a design honours an explicit denial of the defining event (and holds everything when that event
# is left open); their branch flags change no reference.
# Entry: (dispute family, active branch flags, routing flag true?)
FAMILIES = [
    ("defect_mold_heating", ("health_effects", "heating"), None),
    ("defect_mold_heating", ("health_effects", "specialist_needed"), None),
    ("defect_mold_heating", ("deposit_considered", "health_effects"), None),
    ("defect_mold_heating", ("deposit_considered", "mold"), None),
    ("defect_mold_heating", ("health_effects", "heating", "mold"), None),
    ("defect_mold_heating", ("deposit_considered", "health_effects", "heating"), None),
    ("defect_mold_heating", ("heating", "mold", "specialist_needed"), None),
    ("defect_mold_heating", ("deposit_considered", "heating", "specialist_needed"), None),
    ("defect_mold_heating", ("health_effects", "heating", "mold", "specialist_needed"), None),
    ("defect_mold_heating", ("deposit_considered", "health_effects", "heating", "mold"), None),
    ("defect_mold_heating", ("deposit_considered", "health_effects", "mold", "specialist_needed"), None),
    ("defect_mold_heating", ("deposit_considered", "heating", "mold", "specialist_needed"), None),
    ("defect_mold_heating", ("deposit_considered", "health_effects", "heating", "mold", "specialist_needed"), None),
    ("lease_termination_dispute", ("arrears", "retaliation_screen"), True),
    ("lease_termination_dispute", ("arrears", "extension_relevant", "retaliation_screen"), True),
    ("lease_termination_dispute", ("arrears", "extension_relevant", "family_home", "retaliation_screen"), True),
    ("lease_termination_dispute", (), False),
    ("lease_termination_dispute", ("arrears",), False),
    ("lease_termination_dispute", ("extension_relevant",), False),
    ("lease_termination_dispute", ("family_home", "retaliation_screen"), False),
    ("rent_increase_dispute", (), False),
    ("rent_increase_dispute", ("reference_rate",), False),
    ("rent_increase_dispute", ("renovation",), False),
    ("rent_increase_dispute", ("reference_rate", "renovation"), False),
]

# Meaning of a branch flag when the defining event has not happened yet (announced only).
ANNOUNCED = {
    "arrears": "The termination the landlord announced is because of unpaid rent (rent arrears).",
    "retaliation_screen": "The tenant believes the announced termination is retaliation for recently asserted tenancy rights.",
    "extension_relevant": "The tenant would need an extension of the tenancy because moving out would be a hardship.",
    "family_home": "The flat is the family home of a married couple or registered partners.",
    "reference_rate": "The landlord justifies the announced rent increase with a rise in the mortgage reference interest rate.",
    "renovation": "The landlord justifies the announced rent increase with renovation or value-enhancing investment work.",
}
ROUTING_FALSE = {
    "termination_received": "The landlord has announced (orally or informally) that the lease will be ended, but the tenant has NOT received any written termination notice.",
    "claim_received": "The landlord has announced (orally, at a tenants' meeting or by notice board) a rent increase, but the tenant has NOT received any written rent-increase notification.",
}

# How a stated fact is expressed (assigned per claim by build.py; recorded in the scenario file).
STYLES = {"plain": 0.5, "passing": 0.3, "implied": 0.2}

# Sender names: first name x surname, each combination used at most once.
PERSONAS = {
    "en": (["Harriet", "Owen", "Priya", "Felix", "Greta", "Tomasz", "Maeve", "Ibrahim", "Sofia", "Jonah", "Nadia",
            "Luca", "Eleanor", "Kwame", "Ingrid", "Rafael", "Hannah", "Dmitri", "Aoife", "Samuel", "Chloe", "Yusuf",
            "Beatrix", "Arjun"],
           ["Ndlovu", "Castellano", "Ramaswamy", "Okafor", "Lindqvist", "Wilk", "Gallagher", "Haddad", "Ferreira",
            "Whitaker", "Petrova", "Bianchi", "Voss", "Mensah", "Solberg", "Ortega", "Kowalczyk", "Volkov", "Brennan",
            "Achterberg", "Marchetti", "Demir", "Holm", "Mehta"]),
    "de-CH": (["Regula", "Fabian", "Seraina", "Dominik", "Jasmin", "Matthias", "Franziska", "Cédric", "Tanja",
               "Severin", "Livia", "Raphael", "Brigitte", "Nicola", "Yvonne", "Pascal", "Michèle", "Ueli", "Karin",
               "Simon", "Esther", "Jonas", "Anita", "Kevin"],
              ["Ammann", "Lehmann", "Caduff", "Rüegg", "Kuhn", "Bachmann", "Vogt", "Rohner", "Imhof", "Zürcher",
               "Aebischer", "Furrer", "Schnyder", "Gisler", "Stalder", "Kunz", "Bosshard", "Habegger", "Odermatt",
               "Wälti", "Christen", "Siegrist", "Rüfenacht", "Portmann"]),
}
LANDLORDS = ["Immo Jura Verwaltungen AG", "Gerance Bärenplatz AG", "Wohnwerk Thur GmbH", "Liegenschaften Sternen AG",
             "Verwaltung Emme & Söhne", "Stiftung Wohnen Zentral", "Erbengemeinschaft Probst (private landlord)",
             "Hausverwaltung Pilatus AG", "Ruth Messerli (private landlord)", "Domicil Plus Immobilien AG",
             "Baugenossenschaft Sonnhalde", "Verwaltung Lindenhof Treuhand GmbH"]
PLACES = [("Solothurn", "SO"), ("Burgdorf", "BE"), ("Wil", "SG"), ("Liestal", "BL"), ("Rapperswil-Jona", "SG"),
          ("Uster", "ZH"), ("Kriens", "LU"), ("Langenthal", "BE"), ("Wettingen", "AG"), ("Dübendorf", "ZH"),
          ("Herisau", "AR"), ("Brugg", "AG"), ("Wädenswil", "ZH"), ("Kreuzlingen", "TG"), ("Emmen", "LU"),
          ("Muttenz", "BL"), ("Grenchen", "SO"), ("Steffisburg", "BE")]
STREETS = ["Allmendstrasse", "Obere Gasse", "Bündtenweg", "Rebbergstrasse", "Schulhausstrasse", "Eichholzweg",
           "Dorfbachstrasse", "Hinterfeld", "Ahornweg", "Bergstrasse", "Mühlemattstrasse", "Zelgweg", "Brunnenrain"]
CHANNELS = {"email": 45, "portal": 29, "chat": 15, "phone_note": 7}  # Study 1 proportions (70/46/24/10 of 150), 96 claims
