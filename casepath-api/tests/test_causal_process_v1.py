"""Executable product behavior; no provider calls or claim journal writes."""
from copy import deepcopy

import pytest

from casepath_api.causal_process_v1 import apply_edit, evaluate, impact, refresh_document, seal_graph


def receipt(review="sufficient", artifact_id="existing-file"):
    return {"artifact_id": artifact_id, "file_name": "proof.pdf", "sha256": "a" * 64,
            "media_type": "application/pdf", "source_quote": "Exact source passage", "review": review,
            "reviewed_by": "Reviewer", "note": "Checked the source against this requirement."}


def graph():
    def node(name, docs=(), **fields):
        return {"node_id": name, "label": name.title(), "document_types": list(docs), **fields}

    def edge(name, source, target, condition=None, relation="branches_to"):
        return {"edge_id": name, "source_node_id": source, "target_node_id": target,
                "relation": relation, "condition": condition or {"const": "true"}}

    return seal_graph({
        "family": "example", "claim_id": "claim", "conditions": {"branch": {"verdict": "true"}},
        "nodes": [node("root", entry=True, completed=True), node("left", ["left_doc", "shared"]),
                  node("right", ["right_doc"]), node("down", ["down_doc"]),
                  node("independent", ["shared"], entry=True)],
        "edges": [edge("left_path", "root", "left", {"flag": "branch"}),
                  edge("right_path", "root", "right", {"not": {"flag": "branch"}}),
                  edge("down_path", "left", "down")],
        "document_catalog": [{"document_type": name, "label": name, "requirement_class": "mandatory"}
                             for name in ["left_doc", "right_doc", "down_doc", "shared"]],
        "assessment_context": {"noticed": [{"text": "original observation"}], "language": "en",
                               "candidate_deadline": None, "conflicts": [], "question_cards": []},
    })


def by_id(rows, key):
    return {row[key]: row for row in rows}


def test_a_remove_node_reconsiders_descendants_preserves_shared_documents():
    before = graph()
    after = apply_edit(before, {"type": "node.remove", "node_id": "left", "reason": "Wrong route"})
    result = evaluate(after)
    documents = by_id(result["documents"], "document_type")
    assert documents["left_doc"]["route_state"] == "not_needed"
    assert documents["down_doc"]["route_state"] == "not_needed"
    assert documents["shared"]["request"] is True
    assert by_id(result["nodes"], "node_id")["down"]["activation"] == "false"
    changes = impact(before, after)
    assert "left" in changes["removed_node_ids"]
    assert "independent" in changes["unchanged_node_ids"]
    assert "shared" in changes["unchanged_requirement_document_types"]
    assert "shared" in changes["document_source_changes"]
    assert before == graph()


def test_b_change_branch_changes_downstream_documents_action_and_questions():
    before = graph()
    after = apply_edit(before, {"type": "conditions.set", "flag": "branch", "verdict": "false"})
    result = evaluate(after)
    documents = by_id(result["documents"], "document_type")
    assert documents["left_doc"]["route_state"] == "not_needed"
    assert documents["right_doc"]["route_state"] == "needed_now"
    assert impact(before, after)["next_action_changed"] is True
    unresolved = evaluate(apply_edit(after, {"type": "conditions.set", "flag": "branch", "verdict": "unresolved"}))
    assert by_id(unresolved["documents"], "document_type")["right_doc"]["route_state"] == "held_behind_question"
    assert any(card["id"] == "branch" for card in unresolved["question_cards"])


def test_c_new_prerequisite_blocks_until_completed_and_exposes_requirements():
    before = graph()
    added = apply_edit(before, {"type": "node.add", "node": {
        "node_id": "verify", "label": "Verify prerequisite", "entry": True, "document_types": ["right_doc"]}})
    blocked = apply_edit(added, {"type": "edge.add", "edge": {
        "edge_id": "prerequisite", "source_node_id": "verify", "target_node_id": "left", "relation": "requires"}})
    result = evaluate(blocked)
    assert by_id(result["nodes"], "node_id")["left"]["execution_state"] == "blocked"
    assert by_id(result["documents"], "document_type")["right_doc"]["route_state"] == "needed_now"
    # Trusted helper receives the receipt after server verification of the source.
    blocked = refresh_document(blocked, "right_doc", receipt(), "Reviewer", "Reviewed source")
    completed = apply_edit(blocked, {"type": "node.complete", "node_id": "verify", "completed": True})
    assert by_id(evaluate(completed)["nodes"], "node_id")["left"]["execution_state"] == "ready"


def test_d_validation_is_local_including_edges_and_roots():
    before = graph()
    after = apply_edit(before, {"type": "node.validate", "node_id": "left", "status": "validated", "actor": "Reviewer"})
    nodes = by_id(after["nodes"], "node_id")
    assert nodes["left"]["validation"]["status"] == "validated"
    assert nodes["root"]["validation"]["status"] == "unvalidated"
    assert nodes["right"]["validation"]["status"] == "unvalidated"
    assert "down" in impact(before, after)["unchanged_affected_node_ids"]
    after = apply_edit(after, {"type": "edge.validate", "edge_id": "left_path", "status": "validated"})
    assert by_id(after["edges"], "edge_id")["left_path"]["validation"]["status"] == "validated"
    assert by_id(after["edges"], "edge_id")["right_path"]["validation"]["status"] == "unvalidated"


def test_e_modifying_validated_node_keeps_history_and_flags_inconsistent_completion():
    before = apply_edit(graph(), {"type": "node.validate", "node_id": "left", "status": "validated"})
    before = apply_edit(before, {"type": "node.complete", "node_id": "left", "completed": True})
    after = apply_edit(before, {"type": "node.update", "node_id": "left",
                                "changes": {"condition": {"const": "false"}}, "reason": "Branch does not apply"})
    node = by_id(evaluate(after)["nodes"], "node_id")["left"]
    assert node["validation"]["status"] == "revised"
    assert node["completed"] is True
    assert node["inconsistent_completion"] is True
    assert after["history"][-1]["before"]["validation"]["status"] == "validated"
    changes = impact(before, after)
    assert changes["inconsistent_completed_node_ids"] == ["left"]
    assert "down" in changes["changed_node_ids"]
    assert "down_doc" in changes["removed_document_types"]


def test_rejected_node_and_relationship_withdraw_dependent_requests():
    for operation in ({"type": "node.validate", "node_id": "left", "status": "rejected"},
                      {"type": "edge.validate", "edge_id": "left_path", "status": "rejected"}):
        result = evaluate(apply_edit(graph(), operation))
        assert by_id(result["documents"], "document_type")["down_doc"]["route_state"] == "not_needed"


@pytest.mark.parametrize("operation", [
    {"type": "edge.add", "edge": {"edge_id": "cycle", "source_node_id": "down", "target_node_id": "root", "relation": "enables"}},
    {"type": "edge.add", "edge": {"edge_id": "missing", "source_node_id": "missing", "target_node_id": "root", "relation": "enables"}},
    {"type": "node.update", "node_id": "left", "changes": {"condition": {"flag": "missing"}}},
    {"type": "node.update", "node_id": "left", "changes": {"condition": {"eval": "True"}}},
    {"type": "node.update", "node_id": "left", "changes": {"condition": {"all": []}}},
    {"type": "node.update", "node_id": "left", "changes": {"document_types": ["missing"]}},
    {"type": "node.update", "node_id": "left", "changes": {"validation": {"status": "validated"}}},
    {"type": "conditions.set", "flag": "branch", "verdict": "yes"},
    {"type": "conditions.set", "flag": "branch", "verdict": {}},
    {"type": "node.validate", "node_id": "left", "status": {}},
    {"type": "node.add", "after_node_id": "absent", "node": {"node_id": "new", "label": "New"}},
    {"type": "edge.add", "edge": {"edge_id": "bad", "source_node_id": "root", "target_node_id": "left", "relation": []}},
    {"type": "unknown"},
])
def test_invalid_operations_are_rejected_atomically(operation):
    original = graph()
    saved = deepcopy(original)
    with pytest.raises(ValueError):
        apply_edit(original, operation)
    assert original == saved


def test_composed_conditions_are_tristate_and_output_is_deterministic():
    original = graph()
    original["conditions"]["other"] = {"verdict": "unresolved"}
    edited = apply_edit(seal_graph(original), {"type": "node.update", "node_id": "left", "changes": {
        "condition": {"all": [{"flag": "branch"}, {"any": [{"flag": "other"}, {"const": "false"}]}]}}})
    result = evaluate(edited)
    assert by_id(result["nodes"], "node_id")["left"]["activation"] == "unresolved"
    assert result == evaluate(edited)
    assert result["noticed"] == [{"text": "original observation"}]


def test_document_availability_is_shared_but_never_claims_sufficiency():
    seeded = graph()
    seeded["document_catalog"][-1]["held_files"] = [{"artifact_id": "file", "file_name": "file.pdf"}]
    edited = apply_edit(seal_graph(seeded), {"type": "document.set", "document": {
        "document_type": "shared", "label": "Shared evidence"}})
    shared = by_id(evaluate(edited)["documents"], "document_type")["shared"]
    assert shared["route_state"] == "held_not_reviewed"
    assert shared["required_at_node_ids"] == ["left", "independent"]
    assert shared["request"] is False


def test_add_connected_node_is_atomic_and_document_edits_cannot_forge_evidence():
    original = graph()
    added = apply_edit(original, {"type": "node.add", "after_node_id": "root", "node": {
        "node_id": "connected", "label": "Connected step", "document_types": ["right_doc"]}})
    assert by_id(evaluate(added)["nodes"], "node_id")["connected"]["execution_state"] == "ready"
    assert added["history"][-1]["relationship_changes"]["added"]
    for field, value in [("held_files", [{"artifact_id": "forged"}]), ("authority", {"article": "forged"})]:
        with pytest.raises(ValueError):
            apply_edit(original, {"type": "document.set", "document": {"document_type": "shared", field: value}})


def test_completed_step_reopens_when_a_document_is_added():
    original = apply_edit(graph(), {"type": "node.update", "node_id": "left", "changes": {"document_types": []}})
    original = apply_edit(original, {"type": "node.complete", "node_id": "left", "completed": True})
    after = apply_edit(original, {"type": "node.update", "node_id": "left", "changes": {"document_types": ["left_doc"]}})
    assert "left" in impact(original, after)["inconsistent_completed_node_ids"]


def test_causes_blocks_invalidates_completes_and_supersedes_have_distinct_effects():
    for relation in ["causes", "completes", "blocks", "invalidates", "supersedes"]:
        original = apply_edit(graph(), {"type": "node.update", "node_id": "independent", "changes": {"document_types": []}})
        added = apply_edit(original, {"type": "edge.add", "edge": {
            "edge_id": "effect", "source_node_id": "independent", "target_node_id": "right", "relation": relation}})
        incomplete = by_id(evaluate(added)["nodes"], "node_id")["right"]
        completed = apply_edit(added, {"type": "node.complete", "node_id": "independent", "completed": True})
        changed = by_id(evaluate(completed)["nodes"], "node_id")["right"]
        if relation in {"causes", "completes"}:
            assert incomplete["activation"] == "false"
            assert changed["activation"] == "true"
            assert changed["effective_completed"] is (relation == "completes")
        elif relation == "blocks":
            assert "independent" in incomplete["blocked_by"]
        else:
            assert changed["activation"] == "false"


def test_actual_product_catalogs_seed_without_validating_process_or_evidence():
    from casepath_api.assessment_grammar_v1 import compile_assessment
    from casepath_api.causal_process_v1 import build_graph
    from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root

    corpus = PublicCorpus(default_workspace_corpus_root())
    for claim_id, family in [("clm_f69b1747447bc221", "lease_termination_dispute"),
                             ("clm_7ac806bd30792cfb", "defect_mold_heating"),
                             ("clm_6f04d0907ecb96bb", "rent_increase_dispute")]:
        assessment = compile_assessment(corpus, claim_id, {"claim_type": family})
        seeded = build_graph(corpus, claim_id, assessment)
        result = evaluate(seeded)
        assert result["family"] == family
        assert len(result["steps"]) == len(assessment["steps"])
        assert {row["document_type"] for row in result["documents"]} == {row["document_type"] for row in assessment["documents"]}
        assert all(row["validation"]["status"] == "unvalidated" for row in result["nodes"] + result["edges"])
        assert result["noticed"] == assessment["noticed"]
        assert result["candidate_deadline"] == assessment["candidate_deadline"]
        assert result["conflicts"] == assessment["conflicts"]
        assert result["focus_node_id"]


def test_complex_conditions_and_graph_size_are_bounded():
    expression = {"const": "true"}
    for _ in range(10):
        expression = {"not": expression}
    with pytest.raises(ValueError):
        apply_edit(graph(), {"type": "node.update", "node_id": "left", "changes": {"condition": expression}})
    original = graph()
    original["nodes"] = [{"node_id": str(index), "label": "Step"} for index in range(101)]
    with pytest.raises(ValueError):
        seal_graph(original)


def test_unresolved_process_condition_reopens_a_question_without_inventing_a_fact():
    original = graph()
    after = apply_edit(original, {"type": "node.update", "node_id": "left",
                                 "changes": {"condition": {"const": "unresolved"}}})
    result = evaluate(after)
    assert "process:left" in impact(original, after)["reopened_question_ids"]
    assert result["conditions"] == original["conditions"]
    assert by_id(result["documents"], "document_type")["left_doc"]["route_state"] == "held_behind_question"


def test_unresolved_relationship_question_names_only_its_dependent_documents():
    after = apply_edit(graph(), {"type": "edge.update", "edge_id": "left_path",
                                "changes": {"condition": {"const": "unresolved"}}})
    questions = by_id(evaluate(after)["question_cards"], "id")
    assert "edge:left_path" in questions
    assert questions["edge:left_path"]["edge_id"] == "left_path"
    assert questions["edge:left_path"]["document_types"] == ["left_doc", "down_doc"]
    assert questions["edge:left_path"]["affected_node_ids"] == ["left", "down"]


@pytest.mark.parametrize("change", [{"label": "Renamed document"}, {"reason": "New process reason"},
                                   {"condition": {"all": [{"const": "true"}, {"const": "true"}]}}])
def test_document_definition_changes_are_visible_even_when_requirements_are_unchanged(change):
    original = graph()
    after = apply_edit(original, {"type": "document.set", "document": {"document_type": "left_doc", **change}})
    changes = impact(original, after)
    assert "left_doc" in changes["changed_document_types"]
    assert "left_doc" in changes["unchanged_requirement_document_types"]
    assert "left_doc" not in changes["changed_requirement_document_types"]
    assert changes["document_definition_changes"][0]["document_type"] == "left_doc"
    assert changes["document_definition_changes"][0]["fields"] == list(change)


def test_empty_graph_accepts_a_new_explicit_entry_node():
    original = graph()
    for node in list(original["nodes"]):
        original = apply_edit(original, {"type": "node.remove", "node_id": node["node_id"]})
    assert evaluate(original)["nodes"] == []
    after = apply_edit(original, {"type": "node.add", "node": {"node_id": "new_entry", "label": "Start here", "entry": True}})
    assert evaluate(after)["focus_node_id"] == "new_entry"


def test_known_completed_route_wins_over_an_unresolved_alternative_at_a_merge():
    original = apply_edit(graph(), {"type": "node.update", "node_id": "left", "changes": {"document_types": []}})
    original = apply_edit(original, {"type": "node.complete", "node_id": "left", "completed": True})
    original = apply_edit(original, {"type": "edge.update", "edge_id": "right_path",
                                    "changes": {"condition": {"const": "unresolved"}}})
    original = apply_edit(original, {"type": "edge.add", "edge": {
        "edge_id": "alternate_merge", "source_node_id": "right", "target_node_id": "down", "relation": "enables"}})
    result = evaluate(original)
    merged = by_id(result["nodes"], "node_id")["down"]
    assert merged["activation"] == "true"
    assert merged["execution_state"] == "ready"
    assert by_id(result["documents"], "document_type")["down_doc"]["route_state"] == "needed_now"
    assert "down_doc" not in by_id(result["question_cards"], "id")["edge:right_path"]["document_types"]


@pytest.mark.parametrize("changes", [{"meaning": "Perform a different verification"}, {"kind": "decision"}])
def test_changed_action_meaning_or_kind_reopens_its_recorded_completion(changes):
    original = apply_edit(graph(), {"type": "node.update", "node_id": "independent", "changes": {"document_types": []}})
    original = apply_edit(original, {"type": "node.complete", "node_id": "independent", "completed": True})
    after = apply_edit(original, {"type": "node.update", "node_id": "independent", "changes": changes})
    assert by_id(after["nodes"], "node_id")["independent"]["completed"] is False
    assert after["history"][-1]["before"]["completed"] is True
    assert by_id(evaluate(after)["nodes"], "node_id")["independent"]["execution_state"] == "ready"
    renamed = apply_edit(original, {"type": "node.update", "node_id": "independent", "changes": {"label": "Renamed step"}})
    assert by_id(renamed["nodes"], "node_id")["independent"]["completed"] is True


def test_checked_document_reviews_support_completion_and_reopen_when_insufficient():
    original = graph()
    received = refresh_document(original, "shared", receipt("received"), "Reviewer", "Received source")
    node = by_id(evaluate(apply_edit(received, {"type": "node.complete", "node_id": "independent", "completed": True}))["nodes"], "node_id")["independent"]
    assert node["inconsistent_completion"] is True
    reviewed = refresh_document(received, "shared", receipt(), "Reviewer", "Reviewed source")
    document = by_id(evaluate(reviewed)["documents"], "document_type")["shared"]
    assert document["route_state"] == "established"
    assert document["review_state"] == "sufficient"
    assert document["required_at_node_ids"] == ["left", "independent"]
    completed = apply_edit(reviewed, {"type": "node.complete", "node_id": "independent", "completed": True})
    assert by_id(evaluate(completed)["nodes"], "node_id")["independent"]["inconsistent_completion"] is False
    insufficient = refresh_document(completed, "shared", receipt("insufficient"), "Reviewer", "The source is incomplete")
    result = evaluate(insufficient)
    assert by_id(result["documents"], "document_type")["shared"]["route_state"] == "needed_now"
    assert by_id(result["nodes"], "node_id")["independent"]["inconsistent_completion"] is True
    assert insufficient["history"][-1]["operation"]["type"] == "document.review"
    assert original == graph()


def test_document_definition_change_requires_a_new_source_review():
    original = refresh_document(graph(), "shared", receipt(), "Reviewer", "Reviewed source")
    original = apply_edit(original, {"type": "node.validate", "node_id": "independent", "status": "validated"})
    after = apply_edit(original, {"type": "document.set", "document": {"document_type": "shared", "reason": "Different required content"}})
    document = by_id(evaluate(after)["documents"], "document_type")["shared"]
    assert document["route_state"] == "held_not_reviewed"
    assert document["review_state"] == "review_needed"
    restored = refresh_document(after, "shared", receipt(), "Reviewer", "Checked the revised requirement")
    assert by_id(evaluate(restored)["documents"], "document_type")["shared"]["route_state"] == "established"
    assert by_id(restored["nodes"], "node_id")["independent"]["validation"]["status"] == "revised"


@pytest.mark.parametrize("patch", [{"sha256": "bad"}, {"reviewed_by": "Impersonated"}, {"source_quote": ""}, {"review": "approved"}])
def test_checked_review_receipt_is_structurally_strict(patch):
    with pytest.raises(ValueError):
        refresh_document(graph(), "shared", {**receipt(), **patch}, "Reviewer", "Reviewed source")


def test_undo_restores_only_the_last_process_edit_and_keeps_later_source_reviews():
    from casepath_api.causal_process_v1 import undo_target
    initial = graph()
    changed = apply_edit(initial, {"type": "conditions.set", "flag": "branch", "verdict": "false"})
    reviewed = refresh_document(changed, "shared", receipt(), "Reviewer", "Checked the shared source")
    target = undo_target(reviewed)
    assert target["target_revision"] == changed["revision"]
    undone = apply_edit(reviewed, {"type": "process.undo", "target_revision": target["target_revision"],
                                  "actor": "Reviewer", "reason": "Restore the prior branch"})
    assert undone["conditions"]["branch"]["verdict"] == "true"
    assert undone["document_catalog"] == reviewed["document_catalog"]
    assert undone["assessment_context"] == initial["assessment_context"]
    assert undone["history"][:-1] == reviewed["history"]
    assert undone["revision"] == reviewed["revision"] + 1
    assert by_id(undone["nodes"], "node_id")["left"]["validation"]["status"] == "revised"
    assert by_id(undone["nodes"], "node_id")["independent"] == by_id(initial["nodes"], "node_id")["independent"]
    assert undo_target(undone) is None
    with pytest.raises(ValueError, match="last process edit"):
        apply_edit(undone, {"type": "process.undo", "target_revision": target["target_revision"]})


@pytest.mark.parametrize("operation", [
    {"type": "node.add", "after_node_id": "root", "node": {"node_id": "added", "label": "Added"}},
    {"type": "node.update", "node_id": "left", "changes": {"label": "Updated", "meaning": "New work"}},
    {"type": "node.remove", "node_id": "left"},
    {"type": "node.validate", "node_id": "left", "status": "rejected"},
    {"type": "node.complete", "node_id": "root", "completed": False},
    {"type": "edge.add", "edge": {"edge_id": "extra", "source_node_id": "root", "target_node_id": "down", "relation": "requires"}},
    {"type": "edge.update", "edge_id": "left_path", "changes": {"relation": "requires"}},
    {"type": "edge.remove", "edge_id": "left_path"},
    {"type": "edge.validate", "edge_id": "left_path", "status": "rejected"},
    {"type": "document.set", "document": {"document_type": "shared", "reason": "Revised content"}},
    {"type": "document.set", "document": {"document_type": "new_doc", "label": "New document"}},
])
def test_undo_compensates_each_supported_graph_edit(operation):
    original = graph()
    changed = apply_edit(original, operation)
    undone = apply_edit(changed, {"type": "process.undo", "target_revision": changed["revision"]})
    def semantics(value):
        return {field: sorted(({key: item for key, item in row.items() if key not in {"validation", "provenance"}}
                               for row in value[field]), key=lambda row: str(row))
                for field in ("nodes", "edges", "document_catalog")}
    assert semantics(undone) == semantics(original)
    assert undone["history"][-1]["operation"]["type"] == "process.undo"
    assert len(undone["history"]) == 2


def test_undo_rejects_a_stale_target_and_preserves_review_of_a_new_document():
    first = apply_edit(graph(), {"type": "conditions.set", "flag": "branch", "verdict": "false"})
    latest = apply_edit(first, {"type": "node.update", "node_id": "right", "changes": {"label": "Latest"}})
    with pytest.raises(ValueError, match="last process edit"):
        apply_edit(latest, {"type": "process.undo", "target_revision": first["revision"]})
    created = apply_edit(graph(), {"type": "document.set", "document": {"document_type": "new", "label": "New"}})
    reviewed = refresh_document(created, "new", receipt(), "Reviewer", "Keep this source review")
    with pytest.raises(ValueError, match="source reviews"):
        apply_edit(reviewed, {"type": "process.undo", "target_revision": created["revision"]})
    assert reviewed["document_catalog"][-1]["held_files"]


def test_consecutive_undo_keeps_the_compensating_history_and_import_boundary():
    from casepath_api.causal_process_v1 import undo_target
    first = apply_edit(graph(), {"type": "conditions.set", "flag": "branch", "verdict": "false"})
    second = apply_edit(first, {"type": "node.update", "node_id": "left", "changes": {"label": "New label"}})
    undone = apply_edit(second, {"type": "process.undo", "target_revision": second["revision"]})
    assert undo_target(undone)["target_revision"] == first["revision"]
    restored = apply_edit(undone, {"type": "process.undo", "target_revision": first["revision"]})
    assert restored["conditions"] == graph()["conditions"]
    assert len(restored["history"]) == 4
    imported = deepcopy(first)
    imported["history"].append({"type": "fragment.apply", "fragment_sha256": "a" * 64})
    assert undo_target(seal_graph(imported)) is None


def test_undo_document_definition_preserves_the_latest_checked_source_receipt():
    changed = apply_edit(graph(), {"type": "document.set", "document": {
        "document_type": "shared", "reason": "A changed requirement"}})
    reviewed = refresh_document(changed, "shared", receipt(), "Reviewer", "Reviewed the changed requirement")
    undone = apply_edit(reviewed, {"type": "process.undo", "target_revision": changed["revision"]})
    documents = by_id(undone["document_catalog"], "document_type")
    assert documents["shared"]["held_files"] == by_id(reviewed["document_catalog"], "document_type")["shared"]["held_files"]
    assert documents["shared"]["reason"] == by_id(graph()["document_catalog"], "document_type")["shared"]["reason"]
    # The retained review established the changed definition, not the restored one.
    assert by_id(evaluate(undone)["documents"], "document_type")["shared"]["route_state"] == "held_not_reviewed"


def test_undo_rejects_changed_target_fields_without_mutating_the_graph():
    changed = apply_edit(graph(), {"type": "node.update", "node_id": "left", "changes": {"label": "Reviewed label"}})
    changed["nodes"][1]["label"] = "A different label"
    changed = seal_graph(changed)
    before = deepcopy(changed)
    with pytest.raises(ValueError, match="edited fields changed"):
        apply_edit(changed, {"type": "process.undo", "target_revision": 1})
    assert changed == before
