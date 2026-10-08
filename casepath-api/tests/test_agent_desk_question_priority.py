from casepath_api.foundation.common import canonical_json_bytes, digest_value
from test_agent_desk_v1 import CLAIM, control_body, desk


def _start(desk):
    state = desk.workspace.store.recover(CLAIM)
    desk.workspace.start(CLAIM, expected_revision=state["revision"],
        idempotency_key="question.priority.start", process_model="casepath.causal-process/1.0.0")


def _prepare_draft(desk):
    state = desk.workspace.store.recover(CLAIM)
    desk.workspace.record_draft(CLAIM, expected_revision=state["revision"],
        expected_state_sha256=state["state_sha256"], idempotency_key="question.priority.draft")


def _review(desk, question):
    agent = desk.claim(CLAIM)
    body = {"question_id": question["question_id"], "answer_id": question["proposal"]["answer_id"],
        "actor": "Test handler", "reason": "", "expected_revision": agent["workspace_revision"],
        "expected_state_sha256": agent["workspace_state_sha256"]}
    preview = desk.preview_decision(CLAIM, **body)
    args = {**body, "preview_sha256": preview["preview_sha256"],
        "idempotency_key": "question.priority.review." + question["question_id"]}
    return desk.apply_decision(CLAIM, **args, dispatch=False), args


def _desk_row(desk):
    return next(row for group in desk.desk()["groups"] for row in group["claims"] if row["claim_id"] == CLAIM)


def test_pending_question_priority_preserves_source_questions_and_previews(desk):
    _start(desk)
    operations = [
        {"type": "node.add", "node": {"node_id": "review_lease_copy", "label": "Review the lease copy",
            "entry": True, "document_types": []}},
        {"type": "node.complete", "node_id": "review_lease_copy", "completed": True},
        {"type": "node.update", "node_id": "review_lease_copy", "changes": {"document_types": ["lease_contract"]}},
    ]
    for index, operation in enumerate(operations):
        state = desk.workspace.store.recover(CLAIM)
        body = {"operation": operation, "actor": "Test handler", "reason": "Review the changed lease prerequisite.",
            "expected_revision": state["revision"], "expected_state_sha256": state["state_sha256"]}
        preview = desk.process.preview(CLAIM, **body)
        desk.process.apply(CLAIM, **body, preview_sha256=preview["preview_sha256"],
            idempotency_key="question.priority.process." + str(index))
    _prepare_draft(desk)
    state = desk.workspace.store.recover(CLAIM)
    original = desk._questions(state)
    original_bytes = {q["question_id"]: canonical_json_bytes(q) for q in original}
    body = {"question_id": "draft:request", "answer_id": "approve", "actor": "Test handler", "reason": "",
        "expected_revision": state["revision"], "expected_state_sha256": state["state_sha256"]}
    preview_before = desk.preview_decision(CLAIM, **body)

    questions = desk.claim(CLAIM)["questions"]
    conflicts = [q for q in original if q["kind"] == "source_conflict"]
    completions = [q for q in original if q["kind"] == "inconsistent_completion"]
    grounded = [q for q in original if q["kind"] == "condition" and q["proposal"]["answer_id"] in {"true", "false"}]
    drafts = [q for q in original if q["kind"] == "draft_approval"]
    unresolved = [q for q in original if q["kind"] == "condition" and q["proposal"]["answer_id"] == "unresolved"]
    validations = [q for q in original if q["kind"] in {"step_validation", "relationship_validation"}]
    assert all([conflicts, completions, grounded, drafts, unresolved, validations])
    assert questions == conflicts + completions + grounded + drafts + unresolved + validations
    assert {q["question_id"]: canonical_json_bytes(q) for q in questions} == original_bytes
    assert all(q["question_sha256"] == digest_value({k: v for k, v in q.items() if k != "question_sha256"}) for q in questions)
    assert desk._questions(state) == original
    assert desk.preview_decision(CLAIM, **body) == preview_before
    row = _desk_row(desk)
    assert row["why"] == questions[0]["why"]
    assert row["question_count"] == len(questions)
    assert desk.workspace.store.recover(CLAIM) == state
    assert desk.work.store.list_runs(CLAIM) == []


def test_draft_precedes_unknown_conditions_in_claim_and_desk_until_reviewed(desk):
    _start(desk)
    desk.control(CLAIM, **control_body(desk, "pause"), idempotency_key="question.priority.pause")
    for question in desk.claim(CLAIM)["questions"]:
        if question["kind"] == "source_conflict" or (
            question["kind"] == "condition" and question["proposal"]["answer_id"] in {"true", "false"}
        ):
            _review(desk, question)
    _prepare_draft(desk)
    agent = desk.claim(CLAIM)
    assert agent["questions"][0]["kind"] == "draft_approval"
    assert any(q["kind"] == "condition" and q["proposal"]["answer_id"] == "unresolved" for q in agent["questions"])
    row = _desk_row(desk)
    assert row["ask"] == agent["questions"][0]["prompt"]
    assert row["why"] == agent["questions"][0]["why"]
    assert row["question_count"] == len(agent["questions"])

    accepted, args = _review(desk, agent["questions"][0])
    remaining = accepted["agent"]["questions"]
    assert all(q["kind"] != "draft_approval" for q in remaining)
    assert remaining[0]["kind"] == "condition" and remaining[0]["proposal"]["answer_id"] == "unresolved"
    row = _desk_row(desk)
    assert row["ask"] == remaining[0]["prompt"] and row["question_count"] == len(remaining)
    repeated = desk.apply_decision(CLAIM, **args, dispatch=False)
    assert repeated["replayed"] is True and repeated["event_sha256"] == accepted["event_sha256"]
    assert repeated["agent"]["questions"] == remaining
    assert desk.workspace.drafts(CLAIM)["latest"]["status"] == "draft_not_sent"
    assert desk.work.store.list_runs(CLAIM) == []
