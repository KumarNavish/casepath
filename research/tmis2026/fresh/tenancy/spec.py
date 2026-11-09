"""Fixed design of the fresh tenancy claims: flag combinations, plain-language fact descriptions,
suppliable document types with their required contents, and the silence-policy clause.

Nothing here is read by a compared design except the rule pack written by generate.py
(the admitted templates plus the silence-policy clause)."""
from __future__ import annotations

# 18 families = 18 dispute-family x true-flag combinations, none used by the 150 Study 1 claims
# (checked in generate.py). The routing flags termination_received / claim_received are true in
# every claim (the dispute's defining event) and are not part of the combination.
FAMILIES = [
    ("rent_increase_dispute", ("reference_rate", "renovation")),
    ("lease_termination_dispute", ("family_home",)),
    ("lease_termination_dispute", ("retaliation_screen",)),
    ("lease_termination_dispute", ("arrears", "extension_relevant")),
    ("lease_termination_dispute", ("arrears", "family_home")),
    ("lease_termination_dispute", ("family_home", "retaliation_screen")),
    ("lease_termination_dispute", ("arrears", "extension_relevant", "family_home")),
    ("lease_termination_dispute", ("extension_relevant", "family_home", "retaliation_screen")),
    ("lease_termination_dispute", ("arrears", "family_home", "retaliation_screen")),
    ("defect_mold_heating", ("mold",)),
    ("defect_mold_heating", ("heating",)),
    ("defect_mold_heating", ("health_effects",)),
    ("defect_mold_heating", ("health_effects", "mold")),
    ("defect_mold_heating", ("heating", "mold")),
    ("defect_mold_heating", ("deposit_considered", "heating")),
    ("defect_mold_heating", ("health_effects", "heating", "specialist_needed")),
    ("defect_mold_heating", ("deposit_considered", "heating", "mold")),
    ("defect_mold_heating", ("deposit_considered", "health_effects", "mold")),
]
ROUTING = {"lease_termination_dispute": "termination_received", "rent_increase_dispute": "claim_received"}

DISPUTE = {
    "lease_termination_dispute": "The landlord is ending the tenant's lease and the tenant wants help to contest the termination.",
    "rent_increase_dispute": "The landlord is raising the rent and the tenant wants help to contest the increase.",
    "defect_mold_heating": "There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help.",
}

# Plain-language meaning of each fact, for the writer (state / open / avoid) and the blind checker.
FACTS = {
    "termination_received": {
        "fact": "The tenant has received a written notice of termination of the lease from the landlord.",
        "open": "say you are not sure whether what you received is a formal termination notice or whether one has actually been issued",
    },
    "claim_received": {
        "fact": "The tenant has received a written notification of a rent increase from the landlord.",
        "open": "say you are not sure whether a formal rent-increase notification has actually been sent to you",
    },
    "family_home": {
        "fact": "The flat is the family home of a married couple or registered partners: the tenant's spouse or registered partner lives there too.",
        "open": "say you are not sure whether the flat legally counts as your family home (for example because your spouse is officially registered elsewhere)",
    },
    "arrears": {
        "fact": "The termination is because of unpaid rent (rent arrears).",
        "open": "say the landlord mentioned late payments but you do not know whether the termination is actually based on rent arrears",
    },
    "retaliation_screen": {
        "fact": "The tenant believes the termination is retaliation because the tenant recently asserted tenancy rights against the landlord (for example complained about defects or challenged the rent).",
        "open": "say you wonder whether the termination could be a reaction to something you raised with the landlord earlier, but you have not made up your mind",
    },
    "extension_relevant": {
        "fact": "The tenant wants an extension of the tenancy because moving out by the end date would be a hardship (for example a difficult housing search, children's school, illness).",
        "open": "say you have not yet decided whether you will ask for more time (an extension) before moving out",
    },
    "reference_rate": {
        "fact": "The landlord justifies the rent increase with a rise in the mortgage reference interest rate.",
        "open": "say you do not yet know whether the increase is based on the mortgage reference interest rate",
    },
    "renovation": {
        "fact": "The landlord justifies the rent increase with renovation or value-enhancing investment work on the building.",
        "open": "say you do not yet know whether renovation work is one of the reasons for the increase",
    },
    "mold": {
        "fact": "There is mould growth or a persistent damp/moisture problem in the flat.",
        "open": "say there are dark spots on a wall but you are not sure whether it is mould or damp at all",
    },
    "heating": {
        "fact": "The heating does not work properly (rooms stay cold, radiators fail).",
        "open": "say some rooms feel cold but you are not sure whether the heating is actually faulty",
    },
    "health_effects": {
        "fact": "A household member has health problems that the tenant attributes to the defect.",
        "open": "say a household member has been unwell lately but you have not yet clarified whether it has anything to do with the defect",
    },
    "specialist_needed": {
        "fact": "A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).",
        "open": "say it has not yet been decided whether an expert needs to inspect the cause",
    },
    "deposit_considered": {
        "fact": "The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.",
        "open": "say you are not sure yet whether you will pay the rent into the official deposit account",
    },
}

# Defect families without a mould or heating flag need a defect that implies neither.
OTHER_DEFECTS = [
    "the roller shutters in the living room and bedroom are broken and cannot be raised",
    "the electrical sockets in the kitchen keep failing and the oven no longer works",
    "the ventilation fan in the windowless bathroom is defective and rattles loudly day and night",
    "the front door of the flat no longer locks properly",
]

# Suppliable documents: plain-text attachments a tenant plausibly holds at intake. Field ids are
# REQUIRED_FIELDS of casepath_api.autonomous_policy_v1 (checked in generate.py); the text is the
# content instruction given to the writer and the content item shown to the blind checker.
SUPPLIABLE = {
    "lease_termination_dispute": ["lease_contract", "termination_notice", "payment_deadline_letter"],
    "rent_increase_dispute": ["lease_contract", "rent_increase_notice", "stated_calculation", "current_rent_evidence",
                              "prior_rent_adjustment"],
    "defect_mold_heating": ["lease_contract", "defect_notification", "written_repair_deadline", "landlord_response_history"],
}
DOC_LABEL = {
    "lease_contract": "the tenancy agreement (lease contract)",
    "termination_notice": "the landlord's termination notice",
    "payment_deadline_letter": "the landlord's earlier payment reminder setting a deadline to pay the arrears",
    "rent_increase_notice": "the landlord's rent-increase notification",
    "stated_calculation": "the landlord's letter explaining how the increase was calculated",
    "current_rent_evidence": "the tenant's current rent statement from the property manager",
    "prior_rent_adjustment": "the notice of the previous rent adjustment",
    "defect_notification": "the tenant's letter to the landlord reporting the defect",
    "written_repair_deadline": "the tenant's letter to the landlord setting a deadline for the repair",
    "landlord_response_history": "the landlord's reply to the tenant about the defect",
}
FIELD_TEXT = {
    "lease_contract": {
        "contracting_parties": "the names of the landlord ({landlord}) and the tenant ({tenant})",
        "property": "the address and description of the rented flat ({address})",
        "tenancy_terms": "the agreed terms: start date {lease_start}, net rent CHF {rent} per month and the notice period of three months",
    },
    "termination_notice": {
        "issuer": "the issuing landlord's name and signature ({landlord})",
        "addressee": "the addressee: the tenant {tenant}",
        "termination_date": "the date on which the tenancy ends ({end_date})",
        "stated_grounds": "the stated ground for the termination ({grounds})",
        "form_contents": "the statement that the notice is given on the officially approved cantonal form, with the information on how to challenge it at the conciliation authority",
    },
    "payment_deadline_letter": {
        "cure_period": "a deadline of 30 days to pay",
        "claimed_arrears": "the amount of rent claimed as unpaid (CHF {arrears_amount})",
        "termination_warning": "the warning that the lease will be terminated if the amount is not paid in time",
    },
    "rent_increase_notice": {
        "notified_amount": "the new monthly rent (CHF {new_rent}, up from CHF {rent})",
        "effective_date": "the date from which the new rent applies ({effective_date})",
        "addressee": "the addressee: the tenant {tenant}",
        "form_contents": "the statement that the increase is notified on the officially approved cantonal form, with the information on how to challenge it",
    },
    "stated_calculation": {
        "increase_reasons": "the reasons for the increase ({increase_reasons})",
        "calculation_inputs": "the figures used in the calculation ({calculation_inputs})",
    },
    "current_rent_evidence": {
        "current_rent": "the current net rent of CHF {rent} per month",
        "rent_components": "the breakdown into net rent and a monthly advance for heating and service costs of CHF {utilities}",
    },
    "prior_rent_adjustment": {
        "adjustment_date": "the date of the previous adjustment ({prior_date})",
        "adjusted_amount": "the rent set at that time (CHF {prior_rent})",
        "calculation_basis": "the basis of that adjustment (the mortgage reference rate of {prior_rate} % at the time)",
    },
    "defect_notification": {
        "reported_defect": "a description of the defect ({defect})",
        "recipient": "the recipient: the landlord or property manager {landlord}",
        "notification_date": "the date of the letter ({notified_on})",
    },
    "written_repair_deadline": {
        "repair_deadline": "a firm deadline for the repair ({repair_deadline})",
        "recipient": "the recipient: the landlord or property manager {landlord}",
        "notice_contents": "the statement that the tenant will pay the rent into the official deposit if the defect is not repaired by then",
    },
    "landlord_response_history": {
        "landlord_response": "the landlord's position on the defect ({landlord_position})",
        "proposed_work": "the work the landlord proposes ({proposed_work})",
        "access_arrangements": "a proposed date for workers to access the flat ({access_date})",
    },
}

SILENCE_CLAUSE = ("Silence policy: a branch fact that the claim never mentions is presumed absent; the dispute's "
                  "defining event (for a termination dispute, that a termination notice was received; for a rent "
                  "dispute, that a rent-increase notification was received) is presumed to have occurred; a fact "
                  "that the claim raises but leaves open is unresolved, and the documents that depend on it are held "
                  "behind a question.")

PERSONAS = {
    "en": ["Taylor Brooks", "Morgan Ellis", "Jordan Reid", "Casey Hughes", "Alex Turner", "Sam Whitfield",
           "Robin Clarke", "Jamie Foster", "Chris Lawson", "Dana Pierce", "Lee Harper", "Avery Collins",
           "Riley Bennett", "Quinn Marshall", "Drew Palmer", "Emerson Hale", "Parker Dunn", "Rowan Price",
           "Kim Sutton", "Charlie Wade"],
    "de-CH": ["Andrea Keller", "Reto Brunner", "Simone Baumann", "Urs Meier", "Corinne Huber", "Marco Frei",
              "Nadine Zimmermann", "Patrick Steiner", "Barbara Gerber", "Lukas Schmid", "Monika Wyss",
              "Stefan Moser", "Daniela Graf", "Thomas Hofmann", "Claudia Roth", "Beat Widmer", "Sandra Kälin",
              "Martin Egli", "Petra Lüthi", "Adrian Bühler"],
}
LANDLORDS = ["Immobilien Seeblick AG", "Verwaltung Rhein & Partner", "Wohnbau Limmat GmbH", "Hausverwaltung Aare AG",
             "Regimo Liegenschaften AG", "Familie Gasser (private landlord)", "Livit-Partner Verwaltungen AG",
             "Privera Wohnen AG", "Peter Ammann (private landlord)", "Wincasa Nord AG"]
PLACES = [("Zürich", "ZH"), ("Bern", "BE"), ("Basel", "BS"), ("Luzern", "LU"), ("St. Gallen", "SG"),
          ("Winterthur", "ZH"), ("Aarau", "AG"), ("Biel", "BE"), ("Thun", "BE"), ("Zug", "ZG"), ("Olten", "SO"),
          ("Baden", "AG"), ("Schaffhausen", "SH"), ("Chur", "GR"), ("Frauenfeld", "TG")]
STREETS = ["Bahnhofstrasse", "Seestrasse", "Gartenweg", "Lindenstrasse", "Kirchgasse", "Mattenweg", "Birkenweg",
           "Rosenstrasse", "Feldstrasse", "Hofackerstrasse", "Sonnenbergstrasse", "Weiherweg"]
CHANNELS = {"email": 34, "portal": 22, "chat": 11, "phone_note": 5}  # Study 1 proportions (70/46/24/10 of 150)
