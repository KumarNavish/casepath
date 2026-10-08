from copy import deepcopy
from types import SimpleNamespace

import pytest

from casepath_api.agent_work.live_projection import live_work
from casepath_api.agent_desk_v1 import AgentDeskServiceV1

CLAIM = "clm_test"
RUN = "work." + "a" * 32


def packet(events, **extra):
    events = [{"claim_id": CLAIM, "run_id": RUN, "sequence": i, "event_sha256": f"{i:064x}",
               "timestamp": "2026-10-08T12:00:00+00:00", "message": "Recorded work", "sources": [],
               "links": [], "object_id": "object", **e} for i, e in enumerate(events, 1)]
    return {"summary": {"claim_id": CLAIM, "run_id": RUN, "status": "running", "currentness": "current",
                        "last_sequence": len(events), "current_role": {"id": "canonical_facts"}, **extra}, "events": events}


def source_events():
    span = {"source_id": "message", "source_sha256": "a" * 64, "text_sha256": "b" * 64,
            "start": 9, "end": 17, "quote": "30. Juni", "extraction": "message_body"}
    return [{"operation": "SOURCE_OPENED", "object_id": "message", "after": {"filename": "Customer message"}},
            {"operation": "SOURCE_SPAN_SELECTED", "object_id": "span:one", "sources": [span]},
            {"operation": "ASSERTION_PROPOSED", "object_id": "assertion:one", "after": {"span_id": "span:one"},
             "sources": [span], "links": ["span:one"]}]


def process_events(node_id="notice", *, needed_now=False):
    requirement_id = "process_document." + node_id
    requirement = {"evidence_item_id": requirement_id, "title": "Notice copy", "evidence_class": "conditional",
                   "mandatory_now": needed_now, "process_node_ids": [node_id]}
    return [{"operation": "PROCESS_NODE_PROPOSED", "object_id": "node:" + node_id, "after": {"node_id": node_id, "title": "Check notice"}},
            {"operation": "OBLIGATION_PROPOSED", "object_id": "obligation:" + requirement_id, "after": requirement, "links": ["node:" + node_id]},
            {"operation": "DOCUMENT_REQUIREMENT_PROPOSED", "object_id": "document:" + requirement_id, "after": requirement},
            {"operation": "SOURCE_LINK_ADDED", "object_id": "link:" + node_id, "after": {"requirement_id": requirement_id,
             "process_node_id": node_id, "rule_explanation": "Check the notice before establishing its date."},
             "links": ["node:" + node_id, "obligation:" + requirement_id]}]


@pytest.mark.parametrize("status,document_sequence,process_sequence", [
    ("completed", 7, 4), ("running", 11, 8), ("failed", 11, 8),
])
def test_completed_review_prefers_required_now_over_later_optional_without_changing_recency(
    status, document_sequence, process_sequence,
):
    events = source_events() + process_events(needed_now=True) + process_events("later") + [
        {"operation": "SOURCE_OPENED", "object_id": f"integrity-{i}", "after": {"filename": "Integrity read"}}
        for i in range(9)
    ]
    value = packet(events, status=status, current_role=None)
    before = deepcopy(value)
    projection = live_work(CLAIM, value)
    stages = {s["id"]: s for s in projection["stages"]}
    lookup = {m["sequence"]: m for m in projection["milestones"]}
    assert stages["documents"]["milestone_sequence"] == document_sequence
    assert stages["process"]["milestone_sequence"] == process_sequence
    assert stages["documents"]["latest_milestone_sequence"] == 11
    assert stages["process"]["latest_milestone_sequence"] == 8
    assert stages["sources"]["latest_milestone_sequence"] == 20
    assert [s["count"] for s in projection["stages"]] == [10, 1, 2, 2]
    assert projection["last_sequence"] == 20 and len(lookup) <= 12
    for milestone in lookup.values():
        event = value["events"][milestone["sequence"] - 1]
        assert milestone["event_sha256"] == event["event_sha256"]
        assert milestone["timestamp"] == event["timestamp"]
        assert milestone["object_id"] == event["object_id"]
    # A required document never borrows the separately recorded source passage.
    assert lookup[stages["sources"]["milestone_sequence"]]["sources"][0]["quote"] == "30. Juni"
    assert lookup[process_sequence]["sources"] == lookup[document_sequence]["sources"] == []
    assert lookup[process_sequence]["connections"] == []
    assert value == before
    if status == "completed":
        assert lookup[document_sequence]["connections"] == [
            {"from": "node:notice", "to": "obligation:process_document.notice", "relation": "required_by_process"}
        ]
        assert stages["process"]["detail_label"] == "Step with a required document"
        assert stages["documents"]["detail_label"] == "Required in this review"


@pytest.mark.parametrize("links", [[], ["node:notice"], ["obligation:process_document.notice"]])
def test_required_document_selection_needs_both_recorded_link_endpoints(links):
    events = process_events(needed_now=True) + process_events("later")
    events[3]["links"] = links
    stages = {s["id"]: s for s in live_work(CLAIM, packet(events, status="completed"))["stages"]}
    assert stages["documents"]["milestone_sequence"] == 8
    assert stages["process"]["milestone_sequence"] == 5
    assert "detail_label" not in stages["documents"]


def test_later_recorded_document_state_prevents_selecting_an_outdated_required_link():
    events = process_events(needed_now=True) + process_events("later")
    events.append({"operation": "DOCUMENT_STATE_CHANGED", "object_id": "document:process_document.notice",
                   "after": {**events[2]["after"], "mandatory_now": False}})
    stages = {s["id"]: s for s in live_work(CLAIM, packet(events, status="completed"))["stages"]}
    assert stages["documents"]["milestone_sequence"] == 9
    assert stages["process"]["milestone_sequence"] == 5
    assert "detail_label" not in stages["documents"]


def test_exact_source_statement_and_process_requirement_stay_separate():
    value = packet(source_events() + process_events())
    before = deepcopy(value)
    projection = live_work(CLAIM, value)
    assert value == before
    assertion = next(m for m in projection["milestones"] if m["type"] == "ASSERTION_PROPOSED")
    assert assertion["sources"][0]["quote"] == "30. Juni"
    assert assertion["sources"][0]["start"] == 9
    assert assertion["sources"][0]["artifact_id"] == "message"
    assert assertion["connections"] == [{"from": "span:one", "to": "assertion:one", "relation": "exact_quotation"}]
    process = next(m for m in projection["milestones"] if m["type"] == "PROCESS_NODE_PROPOSED")
    assert process["sources"] == process["connections"] == []
    document = projection["milestones"][-1]
    assert document["nodes"] == [{"node_id": "notice", "label": "Check notice"}]
    assert document["documents"][0]["document_type"] == "notice"
    assert document["documents"][0]["needed_now"] is False
    assert document["connections"] == [{"from": "node:notice", "to": "obligation:process_document.notice", "relation": "required_by_process"}]
    value["events"][-1]["links"] = []
    assert live_work(CLAIM, value)["milestones"][-1]["connections"] == []


@pytest.mark.parametrize("state,needed_now,expected", [
    ("missing", True, "The saved step requires this document now."),
    ("conditional", False, "The saved step lists this document; it is not required now."),
    ("unknown", False, "The saved step lists this document; it is not required now."),
    ("irrelevant", False, "The saved step lists this document; it is not required now."),
])
def test_link_summary_uses_recorded_timing_and_preserves_the_raw_journal(state, needed_now, expected):
    events = process_events()
    for event in events:
        if event["operation"] in {"OBLIGATION_PROPOSED", "DOCUMENT_REQUIREMENT_PROPOSED"}:
            event["after"] = {**event["after"], "evidence_class": state, "mandatory_now": needed_now}
    # Existing work events collapse optional/later/conditional into conditional.
    # The projection must not re-infer timing or show raw IDs from this prose.
    events[-1]["after"]["rule_explanation"] = "'Notice copy' is a optional evidence item for process step(s) notice_raw_id."
    value = packet(events)
    before = deepcopy(value)
    milestone = live_work(CLAIM, value)["milestones"][-1]
    assert milestone["summary"] == expected
    assert "notice_raw_id" not in milestone["summary"]
    assert "a optional" not in milestone["summary"]
    assert milestone["documents"][0]["needed_now"] is needed_now
    assert milestone["connections"][0]["relation"] == "required_by_process"
    assert value == before


def test_link_without_a_recorded_document_cannot_claim_a_current_requirement():
    events = process_events()
    value = packet([events[0], events[-1]])
    milestone = live_work(CLAIM, value)["milestones"][-1]
    assert milestone["summary"] == "The saved step is linked to this document."
    assert milestone["documents"] == []
    assert milestone["connections"][0]["relation"] == "required_by_process"


def test_bounded_projection_keeps_latest_each_stage_and_counts_unique_objects():
    events = source_events() + process_events() * 20
    projection = live_work(CLAIM, packet(events))
    assert len(projection["milestones"]) <= 12
    assert {m["stage"] for m in projection["milestones"]} == {"sources", "findings", "process", "documents"}
    assert [s["count"] for s in projection["stages"]] == [1, 1, 1, 1]
    assert projection["last_sequence"] == len(events)


def test_later_integrity_reads_and_branches_retain_an_inspectable_passage_and_step():
    events = source_events() + process_events() + [
        {"operation": "SOURCE_OPENED", "object_id": "later-file", "after": {"filename": "Later integrity read.pdf"}},
        {"operation": "BRANCH_PROPOSED", "object_id": "branch:notice", "after": {"condition": "unresolved"}},
    ]
    projection = live_work(CLAIM, packet(events))
    source, process = [next(s for s in projection["stages"] if s["id"] == key) for key in ("sources", "process")]
    lookup = {m["sequence"]: m for m in projection["milestones"]}
    assert source["latest_milestone_sequence"] == 8 and source["milestone_sequence"] == 2
    assert lookup[source["milestone_sequence"]]["sources"][0]["quote"] == "30. Juni"
    assert source["count"] == 2
    assert process["latest_milestone_sequence"] == 9 and process["milestone_sequence"] == 4
    assert lookup[process["milestone_sequence"]]["nodes"] == [{"node_id": "notice", "label": "Check notice"}]
    assert projection["last_sequence"] == 9
    assert lookup[9]["connections"] == lookup[9]["nodes"] == []
    assert len(projection["milestones"]) <= 12


def test_recorded_outputs_do_not_mean_completed_roles_or_claim_authority():
    value = packet(source_events() + process_events())
    projection = live_work(CLAIM, value)
    assert not any(s["state"] == "complete" for s in projection["stages"])
    assert projection["scope"] == "recorded_review_work_not_claim_authority"
    value = packet(source_events() + [{"operation": "AGENT_COMPLETED", "role": "canonical_facts"}], status="completed", current_role=None)
    projection = live_work(CLAIM, value)
    assert next(s for s in projection["stages"] if s["id"] == "findings")["state"] == "complete"
    assert next(s for s in projection["stages"] if s["id"] == "sources")["state"] == "recorded"


@pytest.mark.parametrize("status,currentness,paused,phrase", [
    ("interrupted", "current", True, "Review paused"), ("failed", "current", False, "could not finish"),
    ("running", "historical", False, "Earlier review"), ("running", "unconfirmed", False, "needs verification"),
])
def test_terminal_and_stale_states_never_appear_to_be_working(status, currentness, paused, phrase):
    projection = live_work(CLAIM, packet(source_events(), status=status, currentness=currentness), paused=paused)
    assert phrase in projection["headline"]
    assert projection["active_stage"] is None
    assert not any(s["state"] == "working" for s in projection["stages"])


def test_provider_metadata_never_exposes_response_content_or_reasoning():
    value = packet(source_events() + [{"operation": "PROVIDER_RESPONSE_RECEIVED", "after": {
        "response_model": "small/model", "content": "PRIVATE RESPONSE", "reasoning": "PRIVATE REASONING"}}], facts_worker="external_facts", provider_requests=1, provider_cost_usd=0.001)
    projection = live_work(CLAIM, value)
    assert projection["reader"] == {"kind": "model", "model": "small/model", "provider_requests": 1, "provider_cost_usd": 0.001}
    assert "PRIVATE" not in str(projection)


def test_projection_rejects_cross_claim_or_run_packets():
    assert live_work(CLAIM, None) is None
    value = packet(source_events())
    value["events"][0]["claim_id"] = "another"
    with pytest.raises(ValueError, match="crosses"):
        live_work(CLAIM, value)
    value = packet(source_events())
    value["events"][0]["run_id"] = "another"
    with pytest.raises(ValueError, match="crosses"):
        live_work(CLAIM, value)


def configured_service(**overrides):
    state = {"claim_id": CLAIM, "owner": "Handler", "state_sha256": "a" * 64, "revision": 7}
    capability = {"external_configuration_status": "ready", "facts_workers": ["reference", "external_facts"],
                  "external": {"model": "small/model", "cost_limit_usd": 0.01},
                  "external_budget": {"can_start": True, "total_cost_limit_usd": 0.03, "reason": None}, **overrides}
    reads = []
    service = object.__new__(AgentDeskServiceV1)
    service.work = SimpleNamespace(facts_worker=True, capabilities=lambda: capability,
        context=lambda claim: reads.append(claim) or {"context": dict(state), "context_sha256": "b" * 64})
    return service, state, reads


def test_live_review_control_is_disabled_without_provider_and_never_reads_context_for_desk():
    service, state, reads = configured_service()
    assert service._live_review(state, None, requested=False) == {"available": False}
    service.work.facts_worker = None
    assert service._live_review(state, None) == {"available": False}
    assert reads == []


@pytest.mark.parametrize("changes,summary,paused,reason", [
    ({"owner": None}, None, False, "accountable_handler_required"), ({}, None, True, "paused_by_handler"),
    ({}, {"status": "running"}, False, "inspect_existing_work"),
    ({}, {"status": "interrupted"}, False, "inspect_existing_work"),
    ({}, {"status": "blocked", "pending_calls": ["unknown-effect"]}, False, "inspect_existing_work"),
])
def test_live_review_respects_handler_and_existing_execution(changes, summary, paused, reason):
    service, state, reads = configured_service()
    value = service._live_review({**state, **changes}, summary, paused=paused)
    assert value["available"] and value["can_start"] is False and value["reason"] == reason
    assert value["context_sha256"] is None and reads == []


def test_live_review_binds_eligible_context_and_exposes_only_bounded_public_configuration():
    service, state, reads = configured_service()
    value = service._live_review(state, {"status": "completed"})
    assert value["can_start"] and value["context_sha256"] == "b" * 64
    assert value["model"] == "small/model" and value["run_cost_limit_usd"] == 0.01
    assert value["automatic_retry"] is False and reads == [CLAIM]
    assert "owner" not in value and "state_sha256" not in value
    service.work.context = lambda claim: {"context": {**state, "revision": 8}, "context_sha256": "c" * 64}
    value = service._live_review(state, None)
    assert value["can_start"] is False and value["reason"] == "claim_changed" and value["context_sha256"] is None
    service, state, reads = configured_service(external_budget={"can_start": False, "reason": "budget_exhausted"})
    assert service._live_review(state, None)["reason"] == "budget_exhausted" and reads == []


def test_live_projection_is_sealed_with_actual_completed_reference_work(tmp_path):
    from casepath_api.agent_work.authority import ExistingCasePathAuthority
    from casepath_api.agent_work.service import AgentWorkService
    from casepath_api.agent_work.runtime import AgentWorkExecutor
    from casepath_api.agent_work.store import WorkStore
    from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root, digest_value
    from test_workspace_claim_loop_v1 import _system
    _, workspace, _, facade = _system(tmp_path, corpus=PublicCorpus(default_workspace_corpus_root()))
    workspace.seed()
    work = AgentWorkService(WorkStore(tmp_path / "live-work.sqlite3"), ExistingCasePathAuthority(lambda: workspace, lambda: facade))
    desk = AgentDeskServiceV1(workspace, work)
    claim = "clm_f69b1747447bc221"
    try:
        assert desk.claim(claim)["live_work"] is None
        context = work.context(claim)
        run = work.start(claim, idempotency_key="live-projection-local-check", expected_context_sha256=context["context_sha256"], dispatch=False)
        AgentWorkExecutor(work.store, work.authority).execute(run["summary"]["run_id"])
        agent = desk.claim(claim)
        assert agent["projection_sha256"] == digest_value({k: v for k, v in agent.items() if k != "projection_sha256"})
        live = agent["live_work"]
        assert live["run_id"] == agent["run"]["run_id"] and live["status"] == "completed"
        assert live["reader"]["provider_requests"] == 0 and live["reader"]["kind"] == "reference"
        assert all(stage["state"] == "complete" for stage in live["stages"])
        assert live["last_sequence"] == agent["run"]["last_sequence"]
        assert any(m["sources"] for m in live["milestones"])
        assert any(m["connections"] for m in live["milestones"])
        lookup = {m["sequence"]: m for m in live["milestones"]}
        assert lookup[next(s for s in live["stages"] if s["id"] == "sources")["milestone_sequence"]]["sources"]
        assert lookup[next(s for s in live["stages"] if s["id"] == "process")["milestone_sequence"]]["nodes"]
        assert agent["live_review"] == {"available": False}
    finally:
        work.shutdown()
