from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from casepath_api.causal_workspace_v1 import CausalWorkspaceService, effective_assessment
from casepath_api.claim_workspace_v1 import ClaimWorkspaceService, ClaimWorkspaceError
from casepath_api.claim_workspace_intake_v1 import compile_intake_assessment
from casepath_api.claim_loop_router import create_claim_loop_router
from casepath_api.storage import Storage
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root
from casepath_api.workspace_operational_projection_v1 import derive_workspace_operational_projection_v1

CLAIM = "clm_f69b1747447bc221"


@pytest.fixture
def system(tmp_path):
    storage = Storage(str(tmp_path / "claims.db"))
    workspace = ClaimWorkspaceService(storage, corpus=PublicCorpus(default_workspace_corpus_root()))
    workspace.seed(timestamp="2026-10-01T08:00:00+00:00")
    _start(workspace, CLAIM)
    return storage, workspace, CausalWorkspaceService(workspace)


def _start(workspace, claim, process_model="casepath.causal-process/1.0.0"):
    state = workspace.store.recover(claim)
    return workspace.start(claim, expected_revision=state["revision"],
                           idempotency_key="start.causal." + claim, process_model=process_model)["state"]


def _body(service, operation, claim=CLAIM):
    view = service.view(claim)
    return dict(operation=operation, actor="Test handler", reason="Review the process dependency.",
                expected_revision=view["workspace_revision"], expected_state_sha256=view["workspace_state_sha256"])


def _edit(service, operation, claim=CLAIM):
    body = _body(service, operation, claim)
    preview = service.preview(claim, **body)
    return service.apply(claim, **body, preview_sha256=preview["preview_sha256"],
                         idempotency_key=f"causal.edit.{claim}.{body['expected_revision']}")


def _doc(view, name):
    return next(doc for doc in view["effective_assessment"]["documents"] if doc["document_type"] == name)


def test_condition_apply_recomputes_documents_drafts_queue_and_replays(system):
    storage, workspace, service = system
    initial = workspace.store.recover(CLAIM)
    intake = deepcopy(initial["intake_assessment"])
    body = _body(service, {"type": "conditions.set", "flag": "family_home", "verdict": "false"})
    preview = service.preview(CLAIM, **body)
    assert workspace.store.recover(CLAIM) == initial  # preview is read-only
    assert _doc(preview, "spouse_notice_copy")["route_state"] == "not_needed"
    request = {**body, "preview_sha256": preview["preview_sha256"], "idempotency_key": "causal.apply.branch.0001"}
    result = service.apply(CLAIM, **request)
    assert "spouse_notice_copy" in result["impact"]["removed_document_types"]
    assert "termination_notice" in result["impact"]["unchanged_document_types"]
    state = workspace.store.recover(CLAIM)
    assert state["intake_assessment"] == intake
    assert state["causal_process"]["conditions"]["family_home"]["verdict"] == "false"
    projection = derive_workspace_operational_projection_v1(workspace_state=state, loop_state=None)
    assert projection["readiness_scope"] == "working_process"
    assert projection["next_state"]["title"] == result["process"]["effective_assessment"]["next_step"]
    assert next(row for row in projection["evidence_items"] if row["evidence_item_id"] == "process_document.spouse_notice_copy")["evidence_class"] == "irrelevant"
    triage = workspace._triage_snapshot([state])[CLAIM]
    assert triage["next_step"] == result["process"]["effective_assessment"]["next_step"]
    workspace.record_draft(CLAIM, expected_revision=state["revision"], expected_state_sha256=state["state_sha256"], idempotency_key="causal.draft.branch.0001")
    draft = workspace.drafts(CLAIM)["latest"]
    assert draft["source_assessment_sha256"] == effective_assessment(state)["assessment_sha256"]
    assert "spouse_notice_copy" not in {row["document_type"] for row in draft["requested"]}
    replay = service.apply(CLAIM, **request)
    assert replay["replayed"] is True
    assert replay["event_sha256"] == result["event_sha256"]
    assert replay["process"] == result["process"]
    restarted = ClaimWorkspaceService(storage, corpus=workspace.corpus)
    assert CausalWorkspaceService(restarted).view(CLAIM) == service.view(CLAIM)
    assert restarted.store.recover(CLAIM) == workspace.store.recover(CLAIM)


def test_node_removal_reconsiders_dependents_but_preserves_other_requirements(system):
    _, _, service = system
    before = service.view(CLAIM)
    result = _edit(service, {"type": "node.remove", "node_id": "lt_family"})
    after = result["process"]
    assert all(row["node_id"] != "lt_family" for row in after["graph"]["nodes"])
    assert _doc(after, "spouse_notice_copy")["route_state"] == "not_needed"
    assert _doc(after, "proof_of_receipt") == _doc(before, "proof_of_receipt")
    assert result["impact"]["removed_node_ids"] == ["lt_family"]


def test_scoped_undo_preserves_source_reviews_handler_notes_owner_and_draft_history(system):
    storage, workspace, service = system
    initial = service.view(CLAIM)
    changed = _edit(service, {"type": "conditions.set", "flag": "family_home", "verdict": "false"})
    target = changed["process"]["undo"]
    source = next(row for row in workspace.detail(CLAIM)["artifacts"]
                  if "tenant" in row["file_name"].lower() and row["media_type"] == "application/pdf")
    _edit(service, {"type": "document.review", "document_type": "termination_notice",
                    "artifact_id": source["artifact_id"], "quote": "30. Juni", "review": "sufficient",
                    "note": "Checked this original notice after the branch correction."})
    state = workspace.store.recover(CLAIM)
    workspace.assign(CLAIM, owner="Mira Keller", expected_revision=state["revision"], idempotency_key="undo.owner.0001")
    state = workspace.store.recover(CLAIM)
    workspace.store.append(claim_id=CLAIM, event_type="WORKSPACE_HANDLER_OBSERVATION_RECORDED",
        idempotency_key="undo.handler.note.0001", expected_revision=state["revision"], timestamp="2026-10-07T08:00:00+00:00",
        command={"kind": "condition", "target": "family_home", "verdict": "unresolved", "note": "Keep the original receipt question open.",
                 "quote": None, "source_id": None, "action_id": None, "request_expected_revision": state["revision"]})
    state = workspace.store.recover(CLAIM)
    workspace.record_draft(CLAIM, expected_revision=state["revision"], expected_state_sha256=state["state_sha256"], idempotency_key="undo.draft.0001")
    before = workspace.store.recover(CLAIM)
    notes = workspace.store.handler_observations(CLAIM, revision=before["revision"], expected_state_sha256=before["state_sha256"])
    drafts = workspace.drafts(CLAIM)["items"]
    assert service.view(CLAIM)["undo"] == target
    body = _body(service, {"type": "process.undo", "target_revision": target["target_revision"]})
    preview = service.preview(CLAIM, **body)
    assert workspace.store.recover(CLAIM) == before
    request = {**body, "preview_sha256": preview["preview_sha256"], "idempotency_key": "undo.branch.0001"}
    applied = service.apply(CLAIM, **request)
    after = workspace.store.recover(CLAIM)
    assert after["owner"] == "Mira Keller"
    assert after["intake_assessment"] == before["intake_assessment"]
    assert workspace.store.handler_observations(CLAIM, revision=after["revision"], expected_state_sha256=after["state_sha256"]) == notes
    assert workspace.drafts(CLAIM)["items"] == drafts
    assert workspace.drafts(CLAIM)["latest"] is None
    assert _doc(applied["process"], "spouse_notice_copy")["route_state"] == _doc(initial, "spouse_notice_copy")["route_state"]
    assert _doc(applied["process"], "termination_notice")["route_state"] == "established"
    assert applied["process"]["graph"]["conditions"]["family_home"]["verdict"] == "true"
    assert applied["process"]["history"][-1]["operation"]["type"] == "process.undo"
    replayed = service.apply(CLAIM, **request)
    assert replayed["replayed"] is True
    assert replayed["event_sha256"] == applied["event_sha256"]
    assert replayed["process"] == applied["process"]
    restarted = CausalWorkspaceService(ClaimWorkspaceService(storage, corpus=workspace.corpus))
    assert restarted.view(CLAIM) == service.view(CLAIM)
    with pytest.raises(ValueError, match="last process edit"):
        service.preview(CLAIM, **_body(service, body["operation"]))
    queue = workspace._triage_snapshot([after])[CLAIM]
    assert queue["next_step"] == applied["process"]["effective_assessment"]["next_step"]


def test_prerequisite_validation_and_revised_history_are_granular(system):
    _, _, service = system
    _edit(service, {"type": "node.add", "node": {"node_id": "review_permission", "label": "Confirm permission", "kind": "prerequisite", "entry": True}})
    result = _edit(service, {"type": "edge.add", "edge": {"edge_id": "permission.before.deadline", "source_node_id": "review_permission", "target_node_id": "lt_deadline", "relation": "requires"}})
    step = next(row for row in result["process"]["evaluation"]["nodes"] if row["node_id"] == "lt_deadline")
    assert step["execution_state"] == "blocked"
    _edit(service, {"type": "node.validate", "node_id": "review_permission", "status": "validated"})
    before = service.view(CLAIM)
    assert next(row for row in before["graph"]["nodes"] if row["node_id"] == "lt_deadline")["validation"]["status"] == "unvalidated"
    after = _edit(service, {"type": "node.update", "node_id": "review_permission", "changes": {"label": "Confirm consent with the claimant"}})["process"]
    node = next(row for row in after["graph"]["nodes"] if row["node_id"] == "review_permission")
    assert node["validation"]["status"] == "revised"
    assert len(after["history"]) == len(before["history"]) + 1
    assert after["history"][-1]["reason"] == "Review the process dependency."
    assert after["history"][-1]["actor"] == "Test handler"


def test_stale_preview_conflicting_key_and_forged_impact_fail_closed(system):
    _, workspace, service = system
    body = _body(service, {"type": "conditions.set", "flag": "family_home", "verdict": "false"})
    preview = service.preview(CLAIM, **body)
    with pytest.raises(ValueError, match="preview"):
        service.apply(CLAIM, **body, preview_sha256="0" * 64, idempotency_key="causal.forged.preview.1")
    result = service.apply(CLAIM, **body, preview_sha256=preview["preview_sha256"], idempotency_key="causal.valid.preview.1")
    with pytest.raises(ValueError, match="stale"):
        service.apply(CLAIM, **body, preview_sha256=preview["preview_sha256"], idempotency_key="causal.stale.preview.1")
    changed_body = _body(service, {"type": "conditions.set", "flag": "family_home", "verdict": "true"})
    changed = service.preview(CLAIM, **changed_body)
    with pytest.raises(ClaimWorkspaceError, match="idempotency"):
        service.apply(CLAIM, **changed_body, preview_sha256=changed["preview_sha256"], idempotency_key="causal.valid.preview.1")
    assert workspace.store.recover(CLAIM)["revision"] == result["process"]["workspace_revision"]


def test_fragment_versions_are_explicit_and_claims_remain_pinned(system):
    _, workspace, service = system
    _edit(service, {"type": "node.validate", "node_id": "lt_family", "status": "validated"})
    view = service.view(CLAIM)
    kwargs = dict(name="Family-home service", node_ids=["lt_family"], actor="Test handler", reason="Keep the reviewed process step.", expected_revision=view["workspace_revision"], expected_state_sha256=view["workspace_state_sha256"], idempotency_key="fragment.family.v1")
    saved = service.save_fragment(CLAIM, **kwargs)
    assert service.save_fragment(CLAIM, **kwargs)["fragment"] == saved["fragment"]
    other = next(claim for claim in workspace.corpus.bindings if claim != CLAIM and workspace.corpus.binding(claim)["static_template_sha256"] == workspace.corpus.binding(CLAIM)["static_template_sha256"] and compile_intake_assessment(workspace.corpus, claim)["claim_type"] == "lease_termination_dispute")
    _start(workspace, other)
    before = service.view(other)
    applied = _edit(service, {"type": "fragment.apply", "fragment_sha256": saved["fragment"]["fragment_sha256"]}, other)
    pinned = deepcopy(applied["process"]["graph"])
    assert pinned["conditions"] == before["graph"]["conditions"]
    assert pinned["fragment_instances"][0]["version"] == 1
    _edit(service, {"type": "node.update", "node_id": "lt_family", "changes": {"meaning": "Inspect separate service for each spouse."}})
    _edit(service, {"type": "node.validate", "node_id": "lt_family", "status": "validated"})
    view = service.view(CLAIM)
    second = service.save_fragment(CLAIM, name="Family-home service", node_ids=["lt_family"], actor="Test handler", reason="Clarify the review.", expected_revision=view["workspace_revision"], expected_state_sha256=view["workspace_state_sha256"], idempotency_key="fragment.family.v2", fragment_id=saved["fragment"]["fragment_id"])
    assert second["fragment"]["version"] == 2
    assert service.view(other)["graph"] == pinned
    assert workspace.store.state_at_revision(other, applied["process"]["workspace_revision"])["causal_process"] == pinned


def test_process_routes_reject_extra_authority_and_bind_preview(system):
    storage, workspace, service = system
    app = FastAPI()
    app.include_router(create_claim_loop_router(lambda: storage, workspace_service_getter=lambda: workspace))
    client = TestClient(app)
    route = f"/api/claim-loops/v1/workspace/claims/{CLAIM}/process"
    assert client.get(route).json()["graph"]["claim_id"] == CLAIM
    body = _body(service, {"type": "node.validate", "node_id": "lt_family", "status": "validated"})
    assert client.post(route + "/preview", json={**body, "claim_ready": True}).status_code == 422
    preview = client.post(route + "/preview", json=body)
    assert preview.status_code == 200
    applied = client.post(route + "/apply", json={**body, "preview_sha256": preview.json()["preview_sha256"]}, headers={"X-CasePath-Idempotency-Key": "http.causal.apply.0001"})
    assert applied.status_code == 200, applied.text
    assert applied.json()["process"]["claim_decision_authorized"] is False


def test_document_review_is_source_bound_replayable_and_reopens_completion(system):
    storage, workspace, service = system
    source = next(row for row in workspace.detail(CLAIM)["artifacts"]
                  if "tenant" in row["file_name"].lower() and row["media_type"] == "application/pdf")
    _edit(service, {"type": "node.add", "node": {"node_id": "review_notice", "label": "Check this notice", "entry": True, "document_types": ["termination_notice"]}})
    operation = {"type": "document.review", "document_type": "termination_notice",
                 "artifact_id": source["artifact_id"], "quote": "30. Juni",
                 "note": "I checked the printed end date in the original notice.", "review": "sufficient"}
    body = _body(service, operation)
    preview = service.preview(CLAIM, **body)
    assert _doc(preview, "termination_notice")["route_state"] == "established"
    reviewed = service.apply(CLAIM, **body, preview_sha256=preview["preview_sha256"], idempotency_key="document.review.notice.0001")
    completed = _edit(service, {"type": "node.complete", "node_id": "review_notice", "completed": True})
    node = next(row for row in completed["process"]["evaluation"]["nodes"] if row["node_id"] == "review_notice")
    assert node["effective_completed"] is True
    operation["review"] = "insufficient"
    operation["note"] = "The end date alone does not establish that this notice is complete."
    revised = _edit(service, operation)
    assert "review_notice" in revised["impact"]["inconsistent_completed_node_ids"]
    assert _doc(revised["process"], "termination_notice")["route_state"] == "needed_now"
    assert CausalWorkspaceService(ClaimWorkspaceService(storage, corpus=workspace.corpus)).view(CLAIM) == service.view(CLAIM)
    foreign = next(row for row in workspace.corpus.bindings if row != CLAIM)
    foreign_artifact = workspace.detail(foreign)["artifacts"][0]["artifact_id"]
    with pytest.raises(ValueError):
        service.preview(CLAIM, **_body(service, {**operation, "artifact_id": foreign_artifact}))
    with pytest.raises(ValueError, match="absent"):
        service.preview(CLAIM, **_body(service, {**operation, "quote": "invented source passage"}))
    assert reviewed["process"]["claim_decision_authorized"] is False


def test_document_http_surface_rejects_caller_authored_evidence(system):
    storage, workspace, service = system
    app = FastAPI()
    app.include_router(create_claim_loop_router(lambda: storage, workspace_service_getter=lambda: workspace))
    client = TestClient(app)
    source = next(row for row in workspace.detail(CLAIM)["artifacts"] if row["media_type"] == "application/pdf")
    base = _body(service, {})
    del base["operation"]
    body = {**base, "document_type": "termination_notice", "artifact_id": source["artifact_id"],
            "quote": "", "note": "Received the original notice for review.", "review": "received"}
    route = f"/api/claim-loops/v1/workspace/claims/{CLAIM}/process/documents"
    assert client.post(route + "/preview", json={**body, "held_files": []}).status_code == 422
    preview = client.post(route + "/preview", json=body)
    assert preview.status_code == 200, preview.text
    response = client.post(route + "/apply", json={**body, "preview_sha256": preview.json()["preview_sha256"]}, headers={"X-CasePath-Idempotency-Key": "http.document.review.0001"})
    assert response.status_code == 200, response.text
    assert _doc(response.json()["process"], "termination_notice")["route_state"] == "held_not_reviewed"


def test_agent_snapshot_and_source_acquisition_follow_current_process(tmp_path):
    from test_workspace_claim_loop_v1 import _system, _ensure
    from casepath_api.agent_work.authority import ExistingCasePathAuthority
    _, workspace, _, facade = _system(tmp_path, corpus=PublicCorpus(default_workspace_corpus_root()))
    workspace.seed(timestamp="2026-10-01T08:00:00+00:00")
    started = _start(workspace, CLAIM)
    original = _ensure(facade, CLAIM, started)
    service = CausalWorkspaceService(workspace)
    _edit(service, {"type": "node.remove", "node_id": "lt_family"})
    authority = ExistingCasePathAuthority(lambda: workspace, lambda: facade)
    snapshot = authority.snapshot(CLAIM)
    assert all(row["node_ids"] for row in snapshot["checklist"])
    assert all(row["evidence_item_id"] != "process_document.spouse_notice_copy" for row in snapshot["evidence"])
    assert all("relation" in edge and "condition" in edge and "activation" in edge for edge in snapshot["branches"])
    assert {row["evidence_item_id"] for row in snapshot["evidence"]} == {row["item_id"] for row in snapshot["checklist"]}
    action = original["loop_state"]["selected_action"]
    # An unrelated correction does not disable an existing supported source read.
    intent = facade.mint_evidence_intent(CLAIM, action_id=action["action_id"], expected_revision=original["revision"], idempotency_key="source.after.correction.0001")
    assert intent["intent"]["claim_id"] == CLAIM

    # A human document review remains auditable through the actual six-role
    # executor, including the exact saved requirement roster after node removal.
    from casepath_api.agent_work.runtime import AgentWorkExecutor
    from casepath_api.agent_work.store import WorkStore
    source = next(row for row in workspace.detail(CLAIM)["artifacts"]
                  if "tenant" in row["file_name"].lower() and row["media_type"] == "application/pdf")
    reviewed = _edit(service, {"type": "document.review", "document_type": "termination_notice",
                   "artifact_id": source["artifact_id"], "quote": "30. Juni", "review": "sufficient",
                   "note": "I checked the printed end date in the original notice."})
    assert _doc(reviewed["process"], "termination_notice")["review_state"] == "sufficient"
    store = WorkStore(tmp_path / "work.sqlite3")
    run, _ = store.create(CLAIM, "agent.after.document.review.0001", {"facts_worker": "reference", "context": authority.context(CLAIM)})
    result = AgentWorkExecutor(store, authority).execute(run["run_id"])
    assert result["status"] == "completed", store.events(run["run_id"])[-3:]
    assert len(store.objects(run["run_id"], "role_completion")) == 6
    assert service.view(CLAIM)["claim_decision_authorized"] is False
    store.close()


def test_process_completion_is_distinct_from_claim_decision(system):
    _, workspace, service = system
    for node in list(service.view(CLAIM)["graph"]["nodes"]):
        _edit(service, {"type": "node.remove", "node_id": node["node_id"]})
    _edit(service, {"type": "node.add", "node": {"node_id": "complete_review", "label": "Review the process", "entry": True}})
    complete = _edit(service, {"type": "node.complete", "node_id": "complete_review", "completed": True})["process"]
    assert complete["process_status"] == complete["evaluation"]["process_status"] == "complete"
    assert complete["evaluation"]["next_step"] == "Process complete. Review the claim outcome separately."
    assert complete["claim_decision_authorized"] is False
    assert workspace.store.recover(CLAIM)["readiness_state"] == "blocked"


def test_boot_history_accepts_checked_process_and_fragment_event_types(system):
    from pathlib import Path
    import runpy
    from casepath_api.validate_journal import validate_journal
    storage, workspace, service = system
    _edit(service, {"type": "node.validate", "node_id": "lt_family", "status": "validated"})
    state = workspace.store.recover(CLAIM)
    service.save_fragment(CLAIM, name="Reviewed family step", node_ids=["lt_family"], actor="Handler",
        reason="Keep this reviewed structure.", expected_revision=state["revision"],
        expected_state_sha256=state["state_sha256"], idempotency_key="boot.fragment.0001")
    validator = runpy.run_path(str(Path(__file__).parents[2] / "casepath/tools/validate_local_runtime_history.py"))
    with storage.connect() as connection:
        checked = validator["validate_event_journal"](connection)
    assert len(checked) == 153
    assert validate_journal(Path(storage.path))["event_count"] == len(checked)


def test_http_start_persists_one_graph_for_draft_queue_and_agent(tmp_path):
    from test_workspace_claim_loop_v1 import _system, _ensure
    from casepath_api.agent_work.authority import ExistingCasePathAuthority
    storage, workspace, _, facade = _system(tmp_path, corpus=PublicCorpus(default_workspace_corpus_root()))
    workspace.seed(timestamp="2026-10-01T08:00:00+00:00")
    app = FastAPI()
    app.include_router(create_claim_loop_router(lambda: storage, workspace_service_getter=lambda: workspace))
    client = TestClient(app)
    response = client.post(f"/api/claim-loops/v1/workspace/claims/{CLAIM}/start", json={"expected_revision": 1},
                           headers={"X-CasePath-Idempotency-Key": "http.start.causal.0001"})
    assert response.status_code == 200, response.text
    state = response.json()["state"]
    assert "causal_process" in state
    service = CausalWorkspaceService(workspace)
    view = service.view(CLAIM)
    assert view["process_adopted"] is True
    assert view["effective_assessment"] == view["evaluation"]
    assert effective_assessment(state)["assessment_sha256"] == view["effective_assessment"]["assessment_sha256"]
    workspace.record_draft(CLAIM, expected_revision=state["revision"], expected_state_sha256=state["state_sha256"], idempotency_key="http.start.draft.0001")
    assert workspace.drafts(CLAIM)["latest"]["source_assessment_sha256"] == view["effective_assessment"]["assessment_sha256"]
    saved = workspace.store.recover(CLAIM)
    assert workspace._triage_snapshot([saved])[CLAIM]["next_step"] == view["evaluation"]["next_step"]
    projection = derive_workspace_operational_projection_v1(workspace_state=saved, loop_state=None)
    assert projection["current_process"]["overlay_sha256"] == view["graph"]["graph_sha256"]
    _ensure(facade, CLAIM, saved)
    snapshot = ExistingCasePathAuthority(lambda: workspace, lambda: facade).snapshot(CLAIM)
    assert snapshot["process"]["assessment_sha256"] == view["evaluation"]["assessment_sha256"]
    assert snapshot["process"]["graph_sha256"] == view["graph"]["graph_sha256"]
    restarted = ClaimWorkspaceService(storage, corpus=workspace.corpus)
    assert restarted.store.recover(CLAIM) == saved
    assert CausalWorkspaceService(restarted).view(CLAIM) == service.view(CLAIM)
    # A retry returns the accepted original start even after later work.
    assert workspace.start(CLAIM, expected_revision=1, idempotency_key="http.start.causal.0001")["state"] == state


def test_legacy_start_remains_original_until_explicit_process_adoption(tmp_path):
    storage = Storage(str(tmp_path / "claims.db"))
    workspace = ClaimWorkspaceService(storage, corpus=PublicCorpus(default_workspace_corpus_root()))
    workspace.seed(timestamp="2026-10-01T08:00:00+00:00")
    original = _start(workspace, CLAIM, process_model=None)
    service = CausalWorkspaceService(workspace)
    view = service.view(CLAIM)
    assert view["process_adopted"] is False
    assert view["evaluation_mode"] == "proposal"
    assert view["effective_assessment"] == original["intake_assessment"]["claim_assessment"]
    assert workspace.store.recover(CLAIM) == original
    applied = _edit(service, {"type": "conditions.set", "flag": "family_home", "verdict": "false"})
    assert applied["process"]["process_adopted"] is True
    assert applied["process"]["effective_assessment"] == applied["process"]["evaluation"]
    assert workspace.store.recover(CLAIM)["intake_assessment"] == original["intake_assessment"]


def test_new_prerequisite_fragment_imports_reviewable_boundary_and_blocks_target(system):
    _, workspace, service = system
    _edit(service, {"type": "node.add", "node": {"node_id": "reuse_permission", "label": "Confirm permission", "entry": True, "kind": "prerequisite"}})
    _edit(service, {"type": "edge.add", "edge": {"edge_id": "reuse.permission.deadline", "source_node_id": "reuse_permission", "target_node_id": "lt_deadline", "relation": "requires"}})
    _edit(service, {"type": "node.validate", "node_id": "reuse_permission", "status": "validated"})
    _edit(service, {"type": "edge.validate", "edge_id": "reuse.permission.deadline", "status": "validated"})
    state = workspace.store.recover(CLAIM)
    saved = service.save_fragment(CLAIM, name="Permission prerequisite", node_ids=["reuse_permission"], actor="Handler",
        reason="Reuse the reviewed dependency.", expected_revision=state["revision"],
        expected_state_sha256=state["state_sha256"], idempotency_key="reuse.prerequisite.0001")
    other = next(claim for claim in workspace.corpus.bindings if claim != CLAIM
                 and (intake := compile_intake_assessment(workspace.corpus, claim))["claim_type"] == "lease_termination_dispute"
                 and intake["claim_assessment"]["conditions"]["termination_received"]["verdict"] == "true")
    _start(workspace, other)
    operation = {"type": "fragment.apply", "fragment_sha256": saved["fragment"]["fragment_sha256"]}
    body = _body(service, operation, other)
    preview = service.preview(other, **body)
    assert "reuse.permission.deadline" in preview["impact"]["added_edge_ids"]
    assert all(node["node_id"] != "reuse_permission" for node in service.view(other)["graph"]["nodes"])
    applied = _edit(service, operation, other)["process"]
    edge = next(edge for edge in applied["graph"]["edges"] if edge["edge_id"] == "reuse.permission.deadline")
    assert edge["validation"]["status"] == "unvalidated"
    assert edge["provenance"]["kind"] == "reused"
    deadline = next(node for node in applied["evaluation"]["nodes"] if node["node_id"] == "lt_deadline")
    assert deadline["execution_state"] == "blocked"
    assert "reuse_permission" in deadline["blocked_by"]
    # Once both endpoints exist, reuse cannot recreate a deliberately removed
    # boundary or override a differently interpreted existing relationship.
    _edit(service, {"type": "edge.update", "edge_id": edge["edge_id"], "changes": {"relation": "enables"}}, other)
    with pytest.raises(ValueError, match="boundary conflicts"):
        service.preview(other, **_body(service, operation, other))
    _edit(service, {"type": "edge.remove", "edge_id": edge["edge_id"]}, other)
    with pytest.raises(ValueError, match="boundary conflicts"):
        service.preview(other, **_body(service, operation, other))
