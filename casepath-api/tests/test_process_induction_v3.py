import json

from casepath_api import process_induction_v3 as pi


def test_form_noun_phrase_is_admitted_as_operational_obligation():
    passage = {
        "authority_id": "form-bike",
        "article": "attachment line",
        "exact_text": "Detaillierter Kostenvoranschlag (mit Foto des beschädigten oder gestohlenen Fahrrads oder Teils)",
    }

    def call(system, user):
        assert "FORM AND CHECKLIST RULE" in system
        return json.dumps({"propositions": [{
            "kind": "obligation",
            "statement": "A detailed estimate with a photograph must be supplied for the bicycle or part.",
            "quote": passage["exact_text"],
            "party": None,
            "governs": "a damaged or stolen bicycle or part",
        }]})

    result = pi.extract_propositions(passage, call)
    assert len(result["propositions"]) == 1
    assert result["propositions"][0]["kind"] == "obligation"
    assert result["dropped"] == []
def test_threshold_and_alternative_proof_are_preserved():
    text = ("15 an im Versicherungsvertrag aufgeführten Wertsachen / Einzelobjekte mit einem "
            "Versicherungswert von mind. CHF 1'000, wenn im Schadenfall keine Quittung oder ein "
            "Wertgutachten eines Sachverständigen vorgewiesen werden kann.")
    passage = {"authority_id": "policy-15", "article": "B10.15", "exact_text": text}

    def call(system, user):
        return json.dumps({"propositions": [
            {"kind": "condition", "statement": "The item is scheduled and insured for at least CHF 1,000.",
             "quote": "im Versicherungsvertrag aufgeführten Wertsachen / Einzelobjekte mit einem Versicherungswert von mind. CHF 1'000",
             "party": None, "governs": "the exclusion"},
            {"kind": "exception", "statement": "Cover fails if neither a receipt nor an expert valuation can be produced.",
             "quote": "wenn im Schadenfall keine Quittung oder ein Wertgutachten eines Sachverständigen vorgewiesen werden kann",
             "party": None, "governs": "scheduled valuables and single objects"},
        ]})

    result = pi.extract_propositions(passage, call)
    assert [p["kind"] for p in result["propositions"]] == ["condition", "exception"]
    assert result["dropped"] == []


def test_non_verbatim_form_claim_is_dropped():
    passage = {"authority_id": "x", "article": None, "exact_text": "Police report"}
    result = pi.extract_propositions(passage, lambda *_: json.dumps({"propositions": [{
        "kind": "obligation", "statement": "Supply a police report", "quote": "police report",
        "party": None, "governs": None,
    }]}))
    assert result["propositions"] == []
    assert result["dropped"][0]["reason"].startswith("quote is not")
