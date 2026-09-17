import json

from casepath_api import evidence_document_mapper_v2 as dm


def test_source_named_sim_report_is_preserved():
    catalogue = ["Report of the SIM-card theft to the insurer or to the mobile provider within 24 hours"]
    entries = [{
        "capability_id": "sim.c1",
        "purpose": "satisfy_requirement",
        "condition": "financial loss from SIM-card misuse following theft",
        "requirement": "establish whether notification occurred within 24 hours",
        "must_show": "when theft occurred and when CSS or the provider was notified",
        "source_propositions": [{
            "proposition_id": "p1",
            "statement": "Theft must be reported to CSS or the provider within 24 hours.",
            "quote": "nicht innert 24 Stunden bei der CSS oder dem Provider gemeldet",
        }],
    }]

    def call(system, user):
        assert "source-defined route" in system
        capability_id = json.loads(user)["entries"][0]["capability_id"]
        return json.dumps({"requirements": [{
            "capability_id": capability_id,
            "routes": [{"route_id": "r1", "document_types": catalogue,
                        "why": "The named report establishes the source-defined notification timing."}],
        }]})

    result = dm.map_entries(entries, catalogue, call)
    assert result["problems"] == []
    assert result["requirements"][0]["routes"][0]["document_types"] == catalogue
def test_unknown_document_is_rejected_without_silent_substitution():
    entries = [{"capability_id": "c", "purpose": "satisfy_requirement",
                "condition": None, "requirement": "x", "must_show": "x",
                "source_propositions": []}]
    result = dm.map_entries(entries, ["allowed"], lambda *_: json.dumps({
        "requirements": [{"capability_id": "c", "routes": [{
            "route_id": "r", "document_types": ["invented"], "why": "x"}]}]}))
    assert result["requirements"] == [{"capability_id": "c", "routes": []}]
    assert result["problems"][0]["unknown_documents"] == ["invented"]


def test_missing_mapping_row_fails_closed():
    entries = [{"capability_id": "c", "purpose": "resolve_applicability",
                "condition": "x", "requirement": "x", "must_show": "whether x",
                "source_propositions": []}]
    result = dm.map_entries(entries, ["allowed"], lambda *_: json.dumps({"requirements": []}))
    assert result["requirements"] == [{"capability_id": "c", "routes": []}]
    assert result["problems"][0]["row_count"] == 0
