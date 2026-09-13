from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import pytest

from casepath_api.canonicalizer import MODEL_MODE_REFERENCE
from casepath_api.claim_loop import (
    ClaimLoopError,
    derive_evidence_action_v1,
    reduce_claim_loop_event,
)
from casepath_api.claim_loop_service import ClaimLoopService
from casepath_api.claim_workspace_v1 import ClaimWorkspaceService
from casepath_api.foundation.common import digest_value
from casepath_api.multi_agent import (
    AI_AGENT_IDS,
    DETERMINISTIC_GATE_IDS,
    DeterministicStructuredAgent,
    NemotronMultiAgentOrchestrator,
)
from casepath_api.native_claim_loop_bridge_v1 import (
    NATIVE_SOURCE_SET_ADAPTER_ID,
    NativeClaimLoopBridgeV1,
    NativeClaimLoopBridgeError,
    NativeSourceCorrectionAdapterV1,
    NativeSourceSetAdapterV1,
    NativeSourceSetInterpreterV1,
    _observation_packet,
)
from casepath_api.pipeline_v15 import ClaimPipeline
from casepath_api.storage import Storage
from casepath_api.workspace_claim_loop_v1 import (
    DeterministicTemplateCyclePipelineRouter,
    WORKSPACE_CLAIM_LOOP_SESSION_ID,
    WorkspaceClaimLoopServiceV1,
    WorkspaceEvidenceWithdrawalCorrectionAdapterV1,
)
from casepath_api.workspace_corpus import PublicCorpus, default_public_corpus_root
from casepath_api.workspace_evidence_authority_v1 import (
    LoopbackSourceByteAcquisitionAdapterV1,
    ServerInterpretedWorkspaceEvidenceV1,
)


CLAIM_ID = "clm_r56_source036_replay"
NOW = "2026-05-12T09:30:00+02:00"


def _material(cycle_id: str, source_rows: list[tuple[str, str]], *, answered: bool):
    text_views = []
    receipts = []
    pointers = []
    alias = 0
    for source_id, text in source_rows:
        raw = text.encode()
        raw_sha = sha256(raw).hexdigest()
        view_id = source_id + ".text"
        # Multiple units in the postal record exercise repeated exact spans
        # from the same complete source view.
        chunks = text.splitlines(keepends=True)
        units = []
        cursor = 0
        view_sha = sha256(raw).hexdigest()
        for chunk in chunks:
            ref = f"t{alias}"
            alias += 1
            units.append({"ref": ref, "text": chunk})
            pointers.append(
                {
                    "ref": ref,
                    "kind": "text",
                    "source_id": source_id,
                    "view_id": view_id,
                    "first_observed_at": NOW,
                    "text": chunk,
                    "text_sha256": sha256(chunk.encode()).hexdigest(),
                    "view_text_sha256": view_sha,
                    "char_start": cursor,
                    "char_end": cursor + len(chunk),
                    "pointer_id": "pointer." + digest_value(
                        {"view_id": view_id, "ref": ref, "text": chunk}
                    ),
                }
            )
            cursor += len(chunk)
        text_views.append(
            {
                "source_id": source_id,
                "view_id": view_id,
                "first_observed_at": NOW,
                "units": units,
            }
        )
        receipts.append(
            {
                "artifact_id": source_id,
                "media_type": "text/plain; charset=utf-8",
                "raw_sha256": raw_sha,
                "size_bytes": len(raw),
            }
        )
    original = pointers[0]
    evidence = []
    if answered:
        wanted = [
            row
            for row in pointers
            if "Demand reference" in row["text"]
            or "Item handed over" in row["text"]
            or "Event status" in row["text"]
            or "Demand dated" in row["text"]
        ]
        evidence = [{**deepcopy(row), "role": "support"} for row in wanted]
    need_material = {
        "need_id": "receipt-status",
        "description": "Establish the demand date and its recorded delivery event.",
        "answer": (
            "Demand dated 26.04.2026; item handed over/delivered to addressee "
            "on 28.04.2026 at 09:14."
            if answered
            else None
        ),
        "state": "received" if answered else "missing",
        "until": None,
        "until_status": None,
        "warrants": [deepcopy(original)],
        "evidence": evidence,
    }
    need = {**need_material, "proposal_item_sha256": digest_value(need_material)}
    proposal_material = {
        "contract": "casepath.native-live-provisional-proposal/1.0.0",
        "observed_at": NOW,
        "input_identity": "input." + digest_value([cycle_id, source_rows]),
        "source_prefix_sha256": digest_value(receipts),
        "needs": [need],
        "authority": "FALLIBLE_MODEL_PROPOSAL_OVER_ADMITTED_SOURCE_BYTES",
        "canonical_fact_effect": None,
        "readiness_effect": None,
        "customer_send": False,
    }
    proposal = {
        **proposal_material,
        "proposal_sha256": digest_value(proposal_material),
    }
    return {
        "contract": "casepath.native-live-bridge-material/1.0.0",
        "claim_id": CLAIM_ID,
        "cycle_id": cycle_id,
        "observed_at": NOW,
        "input_identity": proposal["input_identity"],
        "source_prefix_sha256": proposal["source_prefix_sha256"],
        "source_document": {
            "text_views": text_views,
            "image_views": [],
            "observed_at": NOW,
            "prior_self": [],
        },
        "source_receipts": receipts,
        "native_image_receipts": [],
        "provisional_proposal": proposal,
        "terminal_event_sha256": "a" * 64,
        "intent_event_sha256": "b" * 64,
    }


def _add_neighbor(material: dict, *, answered: bool) -> dict:
    value = deepcopy(material)
    first = value["provisional_proposal"]["needs"][0]
    neighbor_material = {
        "need_id": "notice-status",
        "description": "Establish whether a termination notice was recorded.",
        "answer": "No termination notice was recorded." if answered else None,
        "state": "received" if answered else "missing",
        "until": None,
        "until_status": None,
        "warrants": deepcopy(first["warrants"]),
        "evidence": deepcopy(first["evidence"]) if answered else [],
    }
    neighbor = {
        **neighbor_material,
        "proposal_item_sha256": digest_value(neighbor_material),
    }
    value["provisional_proposal"]["needs"].append(neighbor)
    proposal = value["provisional_proposal"]
    proposal_material = {
        key: row for key, row in proposal.items() if key != "proposal_sha256"
    }
    proposal["proposal_sha256"] = digest_value(proposal_material)
    return value


def _set_proposed_action(material: dict, action: dict | None) -> dict:
    value = deepcopy(material)
    need = value["provisional_proposal"]["needs"][0]
    need["proposed_action"] = deepcopy(action)
    need_payload = {
        key: row for key, row in need.items() if key != "proposal_item_sha256"
    }
    need["proposal_item_sha256"] = digest_value(need_payload)
    proposal = value["provisional_proposal"]
    proposal_payload = {
        key: row for key, row in proposal.items() if key != "proposal_sha256"
    }
    proposal["proposal_sha256"] = digest_value(proposal_payload)
    return value


def _set_need_temporality(
    material: dict,
    *,
    state: str,
    answer: str | None,
    until: str | None,
) -> dict:
    value = deepcopy(material)
    need = value["provisional_proposal"]["needs"][0]
    need["answer"] = answer
    need["state"] = state
    need["until"] = until
    need["until_status"] = (
        "active_at_observation" if until is not None else None
    )
    need_payload = {
        key: row for key, row in need.items() if key != "proposal_item_sha256"
    }
    need["proposal_item_sha256"] = digest_value(need_payload)
    proposal = value["provisional_proposal"]
    proposal_payload = {
        key: row for key, row in proposal.items() if key != "proposal_sha256"
    }
    proposal["proposal_sha256"] = digest_value(proposal_payload)
    return value


def _add_image_context(material: dict, image_path: Path, *, role: str = "context") -> dict:
    value = deepcopy(material)
    parent = value["source_receipts"][-1]
    image_raw = b"\x89PNG\r\n\x1a\nrole-preserving-native-context"
    image_path.write_bytes(image_raw)
    image_sha = sha256(image_raw).hexdigest()
    source_id = parent["artifact_id"]
    pointer = {
        "ref": "p0",
        "kind": "native_image",
        "source_id": source_id,
        "view_id": source_id + ".page.0001.pixels",
        "page_index": 0,
        "first_observed_at": NOW,
        "image_sha256": image_sha,
        "raw_artifact_sha256": parent["raw_sha256"],
        "pointer_id": "pointer." + digest_value([source_id, image_sha]),
        "role": role,
    }
    value["source_document"]["image_views"] = [
        {
            "ref": "p0",
            "source_id": source_id,
            "view_id": pointer["view_id"],
            "page_index": 0,
            "first_observed_at": NOW,
        }
    ]
    value["native_image_receipts"] = [
        {
            "image_id": "p0",
            "image_path": str(image_path),
            "media_type": "image/png",
            "page_index": 0,
            "raw_artifact_sha256": parent["raw_sha256"],
            "sha256": image_sha,
            "size_bytes": len(image_raw),
            "source_id": source_id,
            "view_id": pointer["view_id"],
        }
    ]
    need = value["provisional_proposal"]["needs"][0]
    need["evidence"].append(pointer)
    need_payload = {
        key: row for key, row in need.items() if key != "proposal_item_sha256"
    }
    need["proposal_item_sha256"] = digest_value(need_payload)
    proposal = value["provisional_proposal"]
    proposal_payload = {
        key: row for key, row in proposal.items() if key != "proposal_sha256"
    }
    proposal["proposal_sha256"] = digest_value(proposal_payload)
    return value


def _system(tmp_path: Path, materials):
    storage = Storage(str(tmp_path / "casepath.sqlite3"))
    default_pipeline = ClaimPipeline(
        storage,
        model_mode=MODEL_MODE_REFERENCE,
        agent_orchestrator=NemotronMultiAgentOrchestrator(
            storage, agent_runner=DeterministicStructuredAgent()
        ),
        pace_seconds=0,
    )
    router = DeterministicTemplateCyclePipelineRouter(storage, default_pipeline)
    adapter = NativeSourceSetAdapterV1()
    correction_adapter = NativeSourceCorrectionAdapterV1()
    loop = ClaimLoopService(
        storage,
        adapters={adapter.adapter_id: adapter},
        artifact_interpreter=NativeSourceSetInterpreterV1(),
        cycle_pipeline=router,
        correction_adapters={correction_adapter.adapter_id: correction_adapter},
        authorized_owned_sessions=(WORKSPACE_CLAIM_LOOP_SESSION_ID,),
        reconciliation_scope="authorized_only",
        clock=lambda: NOW,
    )
    bridge = NativeClaimLoopBridgeV1(
        native_material=lambda claim_id, cycle_id: materials[cycle_id],
        claim_loop=loop,
        pipeline_router=router,
        adapter=adapter,
        correction_adapter=correction_adapter,
    )
    return bridge, loop, adapter


def test_native_ensure_uses_the_workspace_loop_identity(tmp_path: Path) -> None:
    material = _material(
        "cycle-workspace",
        [("source-original", "Please establish the demand receipt date.\n")],
        answered=False,
    )
    bridge, loop, _adapter = _system(
        tmp_path, {"cycle-workspace": material}
    )
    assessment = "c" * 64
    create_key = "workspace-loop." + assessment
    expected_loop_id = "loop." + digest_value(
        {
            "contract": "casepath.claim-loop-create-resource/1.0.0",
            "session_id": WORKSPACE_CLAIM_LOOP_SESSION_ID,
            "idempotency_key": create_key,
        }
    )
    workspace_binding = {
        "binding_sha256": "d" * 64,
        "intake_assessment_sha256": assessment,
        "original_message_artifact_id": "source-original",
        "original_message_sha256": "e" * 64,
        "original_message_size_bytes": 55,
        "static_template_sha256": "f" * 64,
    }
    bridge.workspace_binding = lambda claim_id: {
        "claim_id": claim_id,
        "assessment_sha256": assessment,
        "loop_id": expected_loop_id,
        "create_idempotency_key": create_key,
        "workspace_binding": workspace_binding,
    }

    result = bridge.ensure(
        claim_id=CLAIM_ID,
        cycle_id="cycle-workspace",
        idempotency_key="native-workspace-ensure-1",
    )

    assert result["loop_id"] == expected_loop_id
    state = loop.state(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID, loop_id=expected_loop_id
    )
    assert (
        state.accepted_artifacts["observable_package"]["workspace_binding"]
        == workspace_binding
    )


def test_workspace_view_reads_the_same_native_loop_with_provisional_provenance(
    tmp_path: Path,
) -> None:
    storage = Storage(str(tmp_path / "shared.sqlite3"))
    corpus = PublicCorpus(default_public_corpus_root())
    workspace = ClaimWorkspaceService(storage, corpus=corpus)
    workspace.seed(timestamp="2026-09-08T19:00:00+00:00")
    claim_id = sorted(corpus.bindings)[0]
    initial = workspace.store.recover(claim_id)
    started = workspace.start(
        claim_id,
        idempotency_key="native.shared.start.0001",
        expected_revision=initial["revision"],
        timestamp="2026-09-08T19:01:00+00:00",
    )["state"]
    default_pipeline = ClaimPipeline(
        storage,
        model_mode=MODEL_MODE_REFERENCE,
        agent_orchestrator=NemotronMultiAgentOrchestrator(
            storage, agent_runner=DeterministicStructuredAgent()
        ),
        pace_seconds=0,
    )
    router = DeterministicTemplateCyclePipelineRouter(storage, default_pipeline)
    native_adapter = NativeSourceSetAdapterV1()
    native_correction = NativeSourceCorrectionAdapterV1()
    native_loop = ClaimLoopService(
        storage,
        adapters={native_adapter.adapter_id: native_adapter},
        artifact_interpreter=NativeSourceSetInterpreterV1(),
        cycle_pipeline=router,
        correction_adapters={native_correction.adapter_id: native_correction},
        authorized_owned_sessions=(WORKSPACE_CLAIM_LOOP_SESSION_ID,),
        reconciliation_scope="authorized_only",
        clock=lambda: NOW,
    )
    browser_adapter = LoopbackSourceByteAcquisitionAdapterV1(tmp_path / "browser")
    browser_interpreter = ServerInterpretedWorkspaceEvidenceV1(browser_adapter)
    browser_correction = WorkspaceEvidenceWithdrawalCorrectionAdapterV1()
    browser_loop = ClaimLoopService(
        storage,
        adapters={browser_adapter.adapter_id: browser_adapter},
        artifact_interpreter=browser_interpreter,
        cycle_pipeline=router,
        correction_adapters={browser_correction.adapter_id: browser_correction},
        authorized_owned_sessions=(WORKSPACE_CLAIM_LOOP_SESSION_ID,),
        reconciliation_scope="authorized_only",
        clock=lambda: NOW,
    )
    facade = WorkspaceClaimLoopServiceV1(
        workspace=workspace,
        claim_loop=browser_loop,
        pipeline_router=router,
        adapter=browser_adapter,
        interpreter=browser_interpreter,
        correction_adapter=browser_correction,
        native_claim_loop=native_loop,
    )
    material = _material(
        "cycle-shared",
        [("source-original", "Please establish the source-relative date.\n")],
        answered=False,
    )
    arrived = _material(
        "cycle-shared-arrived",
        [
            ("source-original", "Please establish the source-relative date.\n"),
            ("source-answer", "Demand dated: 26.04.2026\n"),
        ],
        answered=True,
    )
    material["claim_id"] = claim_id
    arrived["claim_id"] = claim_id
    action = {
        "audience": "provider",
        "enabled": True,
        "requested_contents": [
            "Offer an alternative service window.",
            "Confirm whether the prior reservation was cancelled.",
        ],
    }
    material = _set_proposed_action(material, action)
    arrived = _set_proposed_action(arrived, action)
    arrived_need = arrived["provisional_proposal"]["needs"][0]
    arrived_need["state"] = "partial"
    arrived_need_payload = {
        key: value
        for key, value in arrived_need.items()
        if key != "proposal_item_sha256"
    }
    arrived_need["proposal_item_sha256"] = digest_value(arrived_need_payload)
    arrived_proposal = arrived["provisional_proposal"]
    arrived_proposal_payload = {
        key: value
        for key, value in arrived_proposal.items()
        if key != "proposal_sha256"
    }
    arrived_proposal["proposal_sha256"] = digest_value(arrived_proposal_payload)
    cleared = _set_proposed_action(arrived, None)
    cleared["cycle_id"] = "cycle-shared-cleared"
    bridge = NativeClaimLoopBridgeV1(
        native_material=lambda _claim_id, cycle_id: {
            "cycle-shared": material,
            "cycle-shared-arrived": arrived,
            "cycle-shared-cleared": cleared,
        }[cycle_id],
        claim_loop=native_loop,
        pipeline_router=router,
        adapter=native_adapter,
        correction_adapter=native_correction,
        workspace_binding=facade.native_binding,
    )

    integrated = bridge.ensure(
        claim_id=claim_id,
        cycle_id="cycle-shared",
        idempotency_key="native.shared.ensure.0001",
    )
    bridge.observe(
        claim_id=claim_id,
        loop_id=integrated["loop_id"],
        cycle_id="cycle-shared-arrived",
        need_id="receipt-status",
        idempotency_key="native.shared.observe.0001",
    )
    view = facade.view(claim_id)
    detail = facade.detail(claim_id)
    queue = facade.queue(
        now="2026-09-08T19:02:00+00:00", query=claim_id, limit=25
    )

    assert integrated["loop_id"] == view["loop_state"]["loop_id"]
    assert integrated["loop_id"] == facade.native_binding(claim_id)["loop_id"]
    assert view["provisional_source_binding"] == {
        "cycle_id": "cycle-shared",
        "proposal_sha256": material["provisional_proposal"]["proposal_sha256"],
        "source_prefix_sha256": material["source_prefix_sha256"],
        "authority": "fallible_proposal_only",
    }
    assert view["input_contract"] is None
    assert view["authority"] == "claim_loop_events"
    assert view["workspace_revision"] == started["revision"]
    assert len(view["loop_state"]["observations"]) == 1
    assert detail["state"]["claim_id"] == claim_id
    queue_row = next(row for row in queue["items"] if row["claim_id"] == claim_id)
    assert view["operational_projection"]["readiness_scope"] == "provisional_plan"
    assert queue_row["operational_projection"]["readiness_scope"] == (
        "provisional_plan"
    )
    assert queue_row["operational_projection"]["provisional_next_action"] == action
    assert queue_row["next_safe_action"] == (
        "Proposed next step (provider): Offer an alternative service window. (+1 more)"
    )
    assert queue_row["principal_blocker"] != (
        "No unresolved inquiry remains in the admitted provisional plan"
    )

    bridge.observe(
        claim_id=claim_id,
        loop_id=integrated["loop_id"],
        cycle_id="cycle-shared-cleared",
        need_id="receipt-status",
        idempotency_key="native.shared.observe.clear.0001",
    )
    cleared_queue = facade.queue(
        now="2026-09-08T19:03:00+00:00", query=claim_id, limit=25
    )
    cleared_row = next(
        row for row in cleared_queue["items"] if row["claim_id"] == claim_id
    )
    assert cleared_row["operational_projection"]["provisional_next_action"] is None
    assert not cleared_row["next_safe_action"].startswith("Proposed next step")


def test_browser_native_investigation_controls_keep_provider_and_plan_boundaries(
    tmp_path: Path,
) -> None:
    del tmp_path
    script = Path(__file__).parents[2] / "casepath" / "assets" / "claims-workspace-v1.js"
    node_program = f"""
const ui = require({json.dumps(str(script))});
const empty = ui.evidenceInvestigationMarkup({{kind:'empty',message:'No review.'}});
if (!empty.includes('Investigate admitted sources')) process.exit(2);
const qualified = ui.evidenceInvestigationMarkup({{
  kind:'qualified', cycleId:'native-cycle.test', observedLabel:'Sep 8, 2026',
  providerQualification:{{kind:'openrouter',model:'openai/gpt-5.4-mini',provider:'OpenAI',inputTokens:1200,outputTokens:80,reasoningTokens:20,cachedInputTokens:0,costUsd:0.0042}},
  needs:[],requests:[],outcomes:[],hasNewerPendingAttempt:false
}});
if (!qualified.includes('Qualified provider call:')) process.exit(3);
if (!qualified.includes('Open provisional plan in evidence journal')) process.exit(4);
if (!qualified.includes('fallible proposal')) process.exit(5);
"""
    subprocess.run(["node", "-e", node_program], check=True)
    source = script.read_text(encoding="utf-8")
    assert "Verified: 6 roles · 3 gates · zero provider calls." not in source
    # Presentation placement is not authority. Exercise the actual renderer,
    # including visible follow-up contents, retired requests, escaping and scope.
    renderer_test = Path(__file__).parents[2] / "casepath-qa" / "native-proposal-presentation-v1.test.cjs"
    subprocess.run(["node", "--test", str(renderer_test)], check=True)


def test_r56_joint_arrival_runs_real_six_role_cycle_and_preserves_each_source(
    tmp_path: Path,
) -> None:
    original = "We need the receipt date for demand ZA-47-2026.\n"
    postal = (
        "SYNTHETIC RESEARCH RECORD\n"
        "Demand reference: ZA-47-2026\n"
        "Item handed over: 28.04.2026 at 09:14\n"
        "Event status: Delivered to addressee\n"
    )
    register = "SYNTHETIC NOTICE REGISTER\nDemand dated: 26.04.2026\n"
    materials = {
        "cycle-initial": _material("cycle-initial", [("original", original)], answered=False),
        "cycle-return": _material(
            "cycle-return",
            [("original", original), ("postal", postal), ("register", register)],
            answered=True,
        ),
    }
    bridge, loop, _ = _system(tmp_path, materials)
    ensured = bridge.ensure(
        claim_id=CLAIM_ID,
        cycle_id="cycle-initial",
        idempotency_key="r56.native.ensure.0001",
    )
    observed = bridge.observe(
        claim_id=CLAIM_ID,
        loop_id=ensured["loop_id"],
        cycle_id="cycle-return",
        need_id="receipt-status",
        idempotency_key="r56.native.observe.0001",
    )
    assert observed["source_set_size"] == 4
    assert observed["source_artifact_count"] == 2
    assert observed["parent_source_count"] == 2
    snapshot = loop.state(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
        loop_id=ensured["loop_id"],
    )
    state = snapshot.model_dump(mode="json")
    assert len(state["observations"][0]["source_refs"]) == 4
    assert {
        row["source_id"]
        for row in state["observations"][0]["source_refs"]
    } == {"postal.text", "register.text"}
    cycle = state["six_agent_cycle_receipt"]
    assert tuple(cycle["agent_ids"]) == tuple(AI_AGENT_IDS)
    assert tuple(cycle["deterministic_gate_ids"]) == tuple(DETERMINISTIC_GATE_IDS)
    package = loop._cycle_observable_package(
        accepted=snapshot.accepted_artifacts,
        projection_ledger=snapshot.projection_ledger,
    )
    replayed = {row["artifact_id"]: row for row in package["artifacts"]}
    postal_rows = [
        row for row in replayed.values() if row.get("parent_artifact_id") == "postal"
    ]
    register_rows = [
        row for row in replayed.values() if row.get("parent_artifact_id") == "register"
    ]
    assert len(postal_rows) == 1
    assert len(register_rows) == 1
    assert all(row["extracted_pages"][0]["text"] == postal for row in postal_rows)
    assert register_rows[0]["extracted_pages"][0]["text"] == register


def test_source_set_stage_rejects_missing_tampered_and_cross_identity_refs(
    tmp_path: Path,
) -> None:
    original = "Need receipt.\n"
    source = "Demand dated: 26.04.2026\n"
    material = _material(
        "cycle", [("original", original), ("record", source)], answered=True
    )
    packet = _observation_packet(
        claim_id=CLAIM_ID, material=material, need_id="receipt-status"
    )
    adapter = NativeSourceSetAdapterV1()
    adapter.stage("action.valid", packet)
    adapter.unstage("action.valid")

    missing = deepcopy(packet)
    missing["source_artifacts"] = []
    with pytest.raises(ClaimLoopError, match="differs|absent|registry"):
        adapter.stage("action.missing", missing)

    tampered = deepcopy(packet)
    tampered["source_artifacts"][0]["extracted_pages"][0]["text"] += "changed"
    with pytest.raises(ClaimLoopError, match="differs|hash"):
        adapter.stage("action.tampered", tampered)

    crossed = deepcopy(packet)
    crossed["source_refs"][0]["source_id"] = "other-claim.text"
    with pytest.raises(ClaimLoopError, match="differs"):
        adapter.stage("action.crossed", crossed)


def test_native_image_roles_are_byte_verified_and_need_text_fact_support(
    tmp_path: Path,
) -> None:
    base = _material(
        "image-cycle",
        [
            ("original", "Please establish the demand receipt date.\n"),
            ("record", "Demand dated: 26.04.2026\n"),
        ],
        answered=True,
    )
    material = _add_image_context(base, tmp_path / "page.png")
    packet = _observation_packet(
        claim_id=CLAIM_ID, material=material, need_id="receipt-status"
    )
    assert len(packet["native_image_receipts"]) == 1
    assert all(row["locator_kind"] == "text_quote" for row in packet["source_refs"])
    assert all(row["source_id"] != "record.page.0001.pixels" for row in packet["source_refs"])
    adapter = NativeSourceSetAdapterV1()
    adapter.stage("action.image.valid", packet)
    adapter.unstage("action.image.valid")

    tampered_hash = deepcopy(packet)
    tampered_hash["native_image_receipts"][0]["sha256"] = "f" * 64
    with pytest.raises(ClaimLoopError, match="receipt|bytes"):
        adapter.stage("action.image.hash", tampered_hash)

    missing = deepcopy(packet)
    Path(missing["native_image_receipts"][0]["image_path"]).unlink()
    with pytest.raises(ClaimLoopError, match="unavailable"):
        adapter.stage("action.image.missing", missing)

    support_material = _add_image_context(
        base, tmp_path / "page-support.png", role="support"
    )
    support_packet = _observation_packet(
        claim_id=CLAIM_ID,
        material=support_material,
        need_id="receipt-status",
    )
    assert [
        row["role"]
        for row in support_packet["evidence"]
        if row["kind"] == "native_image"
    ] == ["support"]
    adapter.stage("action.image.support", support_packet)
    adapter.unstage("action.image.support")

    wrong_parent = deepcopy(support_packet)
    wrong_parent["native_image_receipts"][0]["raw_artifact_sha256"] = "f" * 64
    with pytest.raises(ClaimLoopError, match="receipt|parent"):
        adapter.stage("action.image.wrong-parent", wrong_parent)

    image_only = deepcopy(support_material)
    need = image_only["provisional_proposal"]["needs"][0]
    need["evidence"] = [
        row for row in need["evidence"] if row["kind"] == "native_image"
    ]
    with pytest.raises(NativeClaimLoopBridgeError, match="no text source"):
        _observation_packet(
            claim_id=CLAIM_ID,
            material=image_only,
            need_id="receipt-status",
        )


def test_single_source_packet_remains_supported(tmp_path: Path) -> None:
    material = _material(
        "cycle", [("record", "Demand dated: 26.04.2026\n")], answered=True
    )
    packet = _observation_packet(
        claim_id=CLAIM_ID, material=material, need_id="receipt-status"
    )
    assert len(packet["source_refs"]) == 1
    adapter = NativeSourceSetAdapterV1()
    adapter.stage("action.single", packet)
    adapter.unstage("action.single")


def test_contested_native_answer_remains_conflicting_and_actionable(tmp_path: Path) -> None:
    original = "We need the receipt date for demand ZA-47-2026.\n"
    contrary = "Demand reference: ZA-47-2026\nDelivery event disputed in source record.\n"
    initial = _material("initial", [("original", original)], answered=False)
    contested = _material(
        "contested", [("original", original), ("contrary", contrary)], answered=True
    )
    need = contested["provisional_proposal"]["needs"][0]
    need["state"] = "contested"
    need_material = {
        key: value for key, value in need.items() if key != "proposal_item_sha256"
    }
    need["proposal_item_sha256"] = digest_value(need_material)
    proposal = contested["provisional_proposal"]
    proposal_material = {
        key: value for key, value in proposal.items() if key != "proposal_sha256"
    }
    proposal["proposal_sha256"] = digest_value(proposal_material)
    bridge, loop, _ = _system(tmp_path, {"initial": initial, "contested": contested})
    ensured = bridge.ensure(
        claim_id=CLAIM_ID,
        cycle_id="initial",
        idempotency_key="contested.native.ensure.0001",
    )
    bridge.observe(
        claim_id=CLAIM_ID,
        loop_id=ensured["loop_id"],
        cycle_id="contested",
        need_id="receipt-status",
        idempotency_key="contested.native.observe.0001",
    )
    state = loop.state(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID, loop_id=ensured["loop_id"]
    )
    observation = state.observations[0]
    fact = next(row for row in state.facts if row["fact_id"] == observation.fact_id)
    evidence = next(
        row
        for row in state.checklist["items"]
        if row["item_id"] == observation.evidence_item_id
    )
    assert observation.fact_state == "conflicting"
    assert observation.evidence_status == "provided_insufficient"
    # The durable observation retains the conflict.  The process projection is
    # deliberately fail-closed at unknown because insufficient evidence must
    # not replace the current fact as if the dispute were resolved.
    assert fact["state"] == "unknown"
    assert evidence["status"] == "provided_insufficient"
    assert state.selected_action is not None
    assert state.selected_action.fact_id == fact["fact_id"]


def test_scoped_native_correction_preserves_neighbor_and_old_source_bytes(
    tmp_path: Path,
) -> None:
    original = "Need demand receipt and notice status.\n"
    initial_action = {
        "audience": "provider",
        "enabled": True,
        "requested_contents": ["Confirm the scheduled service delivery."],
    }
    corrected_action = {
        "audience": "provider",
        "enabled": True,
        "requested_contents": ["Offer an alternative service window."],
    }
    initial = _add_neighbor(
        _set_proposed_action(
            _material("initial", [("original", original)], answered=False),
            initial_action,
        ),
        answered=False,
    )
    arrived = _add_neighbor(
        _set_proposed_action(
            _material(
                "arrived",
                [
                    ("original", original),
                    (
                        "record-v1",
                        "Demand reference: ZA-47-2026\nDemand dated: 26.04.2026\n",
                    ),
                ],
                answered=True,
            ),
            initial_action,
        ),
        answered=True,
    )
    correction = _material(
        "correction",
        [
            ("original", original),
            (
                "record-v1",
                "Demand reference: ZA-47-2026\nDemand dated: 26.04.2026\n",
            ),
            (
                "record-v2",
                "Demand reference: ZA-47-2026\nDemand dated: 27.04.2026\n"
                "All other recorded fields remain unchanged.\n",
            ),
        ],
        answered=True,
    )
    first = correction["provisional_proposal"]["needs"][0]
    correction_rows = [
        row
        for row in first["evidence"]
        if row["source_id"] == "record-v2" and "Demand dated" in row["text"]
    ]
    supporting_rows = [
        row
        for row in first["evidence"]
        if row["source_id"] == "record-v1" and "Demand reference" in row["text"]
    ]
    original_pointer = deepcopy(first["warrants"][0])
    first["evidence"] = [
        {**original_pointer, "role": "context"},
        *[{**row, "role": "support"} for row in supporting_rows],
        *[{**row, "role": "correction"} for row in correction_rows],
    ]
    first["answer"] = (
        "Demand dated 27.04.2026; the later record changes no sibling assertion."
    )
    first["description"] = (
        "Refined wording: establish the demand date from the later record."
    )
    first["proposed_action"] = corrected_action
    first_material = {
        key: value for key, value in first.items() if key != "proposal_item_sha256"
    }
    first["proposal_item_sha256"] = digest_value(first_material)
    proposal = correction["provisional_proposal"]
    proposal_material = {
        key: value for key, value in proposal.items() if key != "proposal_sha256"
    }
    proposal["proposal_sha256"] = digest_value(proposal_material)
    materials = {
        "initial": initial,
        "arrived": arrived,
        "correction": correction,
    }
    bridge, loop, _ = _system(tmp_path, materials)
    ensured = bridge.ensure(
        claim_id=CLAIM_ID,
        cycle_id="initial",
        idempotency_key="correct.native.ensure.0001",
    )
    for index, need_id in enumerate(("receipt-status", "notice-status")):
        bridge.observe(
            claim_id=CLAIM_ID,
            loop_id=ensured["loop_id"],
            cycle_id="arrived",
            need_id=need_id,
            idempotency_key=f"correct.native.observe.{index:04d}",
        )
    before = loop.state(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID, loop_id=ensured["loop_id"]
    )
    target_fact_id = before.observations[0].fact_id
    neighbor_before = [row for row in before.facts if row["fact_id"] != target_fact_id]
    original_refs = tuple(before.observations[0].source_refs)
    result = bridge.correct(
        claim_id=CLAIM_ID,
        loop_id=ensured["loop_id"],
        cycle_id="correction",
        need_id="receipt-status",
        idempotency_key="correct.native.apply.0001",
    )
    after = loop.state(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID, loop_id=ensured["loop_id"]
    )
    target_after = next(row for row in after.facts if row["fact_id"] == target_fact_id)
    assert target_after["value"] == first["answer"]
    assert digest_value(
        [row for row in after.facts if row["fact_id"] != target_fact_id]
    ) == digest_value(neighbor_before)
    assert tuple(after.observations[0].source_refs) == original_refs
    assert len(after.corrections) == 1
    assert (
        after.corrections[0].source_ref.model_dump(mode="json")
        == result["correction_source_ref"]
    )
    assert result["correction_role_ref_count"] == 1
    assert result["context_text_ref_count"] == 2
    assert result["source_change_kind"] == "answer_extension"
    assert result["prior_source_fact_replacement_established"] is False
    assert result["description_refined"] is True
    assert result["proposed_action"] == corrected_action
    assert after.six_agent_cycle_receipt.cycle_kind == "correction"
    event_count = len(
        loop.store.events(
            session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
            loop_id=ensured["loop_id"],
        )
    )
    # Simulate a lost response: the same completed key must return the exact
    # original bridge result before trying to derive another correction from
    # the state that the first correction already changed.
    assert bridge.correct(
        claim_id=CLAIM_ID,
        loop_id=ensured["loop_id"],
        cycle_id="correction",
        need_id="receipt-status",
        idempotency_key="correct.native.apply.0001",
    ) == result
    assert len(
        loop.store.events(
            session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
            loop_id=ensured["loop_id"],
        )
    ) == event_count

    different_need = deepcopy(correction)
    different_need_row = different_need["provisional_proposal"]["needs"][0]
    different_need_row["need_id"] = "different-need"
    different_need_payload = {
        key: value
        for key, value in different_need_row.items()
        if key != "proposal_item_sha256"
    }
    different_need_row["proposal_item_sha256"] = digest_value(
        different_need_payload
    )
    materials["different-need"] = different_need
    with pytest.raises(
        NativeClaimLoopBridgeError,
        match="idempotency key was reused with different correction input",
    ):
        bridge.correct(
            claim_id=CLAIM_ID,
            loop_id=ensured["loop_id"],
            cycle_id="different-need",
            need_id="different-need",
            idempotency_key="correct.native.apply.0001",
        )

    different_source = deepcopy(correction)
    different_source["source_prefix_sha256"] = "c" * 64
    different_source["provisional_proposal"]["source_prefix_sha256"] = "c" * 64
    materials["different-source"] = different_source
    with pytest.raises(
        NativeClaimLoopBridgeError,
        match="idempotency key was reused with different correction input",
    ):
        bridge.correct(
            claim_id=CLAIM_ID,
            loop_id=ensured["loop_id"],
            cycle_id="different-source",
            need_id="receipt-status",
            idempotency_key="correct.native.apply.0001",
        )

    different_payload = deepcopy(correction)
    different_payload_row = different_payload["provisional_proposal"]["needs"][0]
    different_payload_row["answer"] = "A different proposed correction value."
    different_payload_material = {
        key: value
        for key, value in different_payload_row.items()
        if key != "proposal_item_sha256"
    }
    different_payload_row["proposal_item_sha256"] = digest_value(
        different_payload_material
    )
    materials["different-payload"] = different_payload
    with pytest.raises(
        NativeClaimLoopBridgeError,
        match="idempotency key was reused with different correction input",
    ):
        bridge.correct(
            claim_id=CLAIM_ID,
            loop_id=ensured["loop_id"],
            cycle_id="different-payload",
            need_id="receipt-status",
            idempotency_key="correct.native.apply.0001",
        )
    correction_event = loop.store.events(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID, loop_id=ensured["loop_id"]
    )[-1]
    assert correction_event.event_type == "CORRECTION_APPLIED"
    assert (
        correction_event.command["correction_source_artifact"]["parent_artifact_id"]
        == "record-v2"
    )
    for mutation in ("missing", "wrong-target", "tampered-source"):
        command = deepcopy(correction_event.command)
        if mutation == "missing":
            command.pop("correction_source_binding")
        elif mutation == "wrong-target":
            binding = command["correction_source_binding"]
            binding["target_fact_id"] = "fact.native.wrong-target"
            binding["binding_sha256"] = digest_value(
                {key: value for key, value in binding.items() if key != "binding_sha256"}
            )
        else:
            command["correction_source_artifact"]["extracted_pages"][0]["text"] += (
                "tampered"
            )
            binding = command["correction_source_binding"]
            binding["correction_source_artifact_sha256"] = digest_value(
                command["correction_source_artifact"]
            )
            binding["binding_sha256"] = digest_value(
                {key: value for key, value in binding.items() if key != "binding_sha256"}
            )
        with pytest.raises(ClaimLoopError, match="correction authority binding"):
            reduce_claim_loop_event(
                before,
                event_type="CORRECTION_APPLIED",
                command=command,
                sequence=before.revision + 1,
                event_sha256="f" * 64,
                timestamp=correction_event.created_at,
            )

    restarted_correction = NativeSourceCorrectionAdapterV1()
    restarted = ClaimLoopService(
        loop.storage,
        adapters={
            NATIVE_SOURCE_SET_ADAPTER_ID: NativeSourceSetAdapterV1(),
        },
        artifact_interpreter=NativeSourceSetInterpreterV1(),
        correction_adapters={
            restarted_correction.adapter_id: restarted_correction,
        },
        cycle_pipeline=loop.cycle_pipeline,
        authorized_owned_sessions=(WORKSPACE_CLAIM_LOOP_SESSION_ID,),
        reconciliation_scope="authorized_only",
        clock=lambda: NOW,
    )
    replayed = restarted.state(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID, loop_id=ensured["loop_id"]
    )
    assert replayed.state_sha256 == after.state_sha256
    restarted_bridge = NativeClaimLoopBridgeV1(
        native_material=lambda _claim_id, cycle_id: materials[cycle_id],
        claim_loop=restarted,
        pipeline_router=loop.cycle_pipeline,
        adapter=restarted.adapters[NATIVE_SOURCE_SET_ADAPTER_ID],
        correction_adapter=restarted_correction,
    )
    assert restarted_bridge.correct(
        claim_id=CLAIM_ID,
        loop_id=ensured["loop_id"],
        cycle_id="correction",
        need_id="receipt-status",
        idempotency_key="correct.native.apply.0001",
    ) == result
    assert restarted.state(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID, loop_id=ensured["loop_id"]
    ).state_sha256 == after.state_sha256
    replay_package = restarted._cycle_observable_package(
        accepted=replayed.accepted_artifacts,
        projection_ledger=replayed.projection_ledger,
        corrections=replayed.corrections,
    )
    assert any(
        row.get("parent_artifact_id") == "record-v2"
        for row in replay_package["artifacts"]
    )


@pytest.mark.parametrize("audience", ["internal", "provider", "claimant", "authority"])
def test_native_proposed_action_is_optional_closed_and_packet_bound(audience: str) -> None:
    material = _material(
        "legacy-action-absent",
        [
            ("source-original", "Please establish the demand receipt date.\n"),
            (
                "source-answer",
                "Demand reference: ZA-47-2026\nDemand dated: 26.04.2026\n",
            ),
        ],
        answered=True,
    )
    assert _observation_packet(
        claim_id=CLAIM_ID,
        material=material,
        need_id="receipt-status",
    )["proposed_action"] is None

    action = {
        "audience": audience,
        "enabled": True,
        "requested_contents": ["Check the admitted source record."],
    }
    with_action = _set_proposed_action(material, action)
    packet = _observation_packet(
        claim_id=CLAIM_ID,
        material=with_action,
        need_id="receipt-status",
    )
    assert packet["proposed_action"] == action
    assert packet["proposal_item_sha256"] != material["provisional_proposal"][
        "needs"
    ][0]["proposal_item_sha256"]

    for invalid in (
        {"audience": "customer", "enabled": True, "requested_contents": ["Ask."]},
        {"audience": "provider", "enabled": True, "requested_contents": []},
        {
            "audience": "provider",
            "enabled": True,
            "requested_contents": ["Ask.", "Ask."],
        },
    ):
        with pytest.raises(ClaimLoopError, match="native proposed action"):
            _observation_packet(
                claim_id=CLAIM_ID,
                material=_set_proposed_action(material, invalid),
                need_id="receipt-status",
            )


def _two_action_revision_materials() -> tuple[dict, dict, dict]:
    initial = _add_neighbor(
        _material(
            "initial-actions",
            [("source-original", "Please obtain both source records.\n")],
            answered=False,
        ),
        answered=False,
    )
    for index, need in enumerate(initial["provisional_proposal"]["needs"]):
        need["proposed_action"] = {
            "audience": "provider",
            "enabled": True,
            "requested_contents": [f"Record {index + 1}"],
        }
        payload = {
            key: value for key, value in need.items() if key != "proposal_item_sha256"
        }
        need["proposal_item_sha256"] = digest_value(payload)
    proposal = initial["provisional_proposal"]
    proposal["proposal_sha256"] = digest_value(
        {key: value for key, value in proposal.items() if key != "proposal_sha256"}
    )

    revision_packet = {
        "readings": [],
        "actions": [],
        "prior_action_dispositions": [
            {
                "disposition": "retired",
                "prior_action_index": index,
                "reason": f"The later source makes separate request {index + 1} unnecessary.",
                "source_refs": ["t0"],
            }
            for index in range(2)
        ],
    }
    revision = deepcopy(initial)
    revision["cycle_id"] = "revision-actions"
    revision["proposal_revision_packet_sha256"] = digest_value(revision_packet)
    revision_proposal = revision["provisional_proposal"]
    revision_proposal["input_identity"] = "input." + digest_value(revision_packet)
    revision["input_identity"] = revision_proposal["input_identity"]
    revision_proposal["proposal_sha256"] = digest_value(
        {
            key: value
            for key, value in revision_proposal.items()
            if key != "proposal_sha256"
        }
    )
    return initial, revision, revision_packet


def test_native_revision_retires_unreached_actions_and_replays_after_restart(
    tmp_path: Path,
) -> None:
    initial, revision, packet = _two_action_revision_materials()
    materials = {"initial-actions": initial, "revision-actions": revision}
    bridge, loop, _ = _system(tmp_path, materials)
    ensured = bridge.ensure(
        claim_id=CLAIM_ID,
        cycle_id="initial-actions",
        idempotency_key="native.revision.ensure.0001",
    )
    before = loop.state(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID, loop_id=ensured["loop_id"]
    )
    facts_before = deepcopy(before.facts)
    incomplete = deepcopy(packet)
    incomplete["prior_action_dispositions"] = incomplete[
        "prior_action_dispositions"
    ][:1]
    incomplete_material = deepcopy(revision)
    incomplete_material["proposal_revision_packet_sha256"] = digest_value(incomplete)
    incomplete_bridge = NativeClaimLoopBridgeV1(
        native_material=lambda _claim_id, _cycle_id: incomplete_material,
        claim_loop=loop,
        pipeline_router=loop.cycle_pipeline,
        adapter=bridge.adapter,
        correction_adapter=bridge.correction_adapter,
    )
    with pytest.raises(
        NativeClaimLoopBridgeError,
        match="disposition every prior action",
    ):
        incomplete_bridge.record_proposal_revision(
            claim_id=CLAIM_ID,
            loop_id=ensured["loop_id"],
            prior_cycle_id="initial-actions",
            cycle_id="revision-actions",
            revision_packet=incomplete,
            idempotency_key="native.revision.incomplete.0001",
        )
    wrong_source = deepcopy(packet)
    wrong_source["prior_action_dispositions"][1]["source_refs"] = ["t99"]
    wrong_source_material = deepcopy(revision)
    wrong_source_material["proposal_revision_packet_sha256"] = digest_value(wrong_source)
    wrong_source_bridge = NativeClaimLoopBridgeV1(
        native_material=lambda _claim_id, _cycle_id: wrong_source_material,
        claim_loop=loop,
        pipeline_router=loop.cycle_pipeline,
        adapter=bridge.adapter,
        correction_adapter=bridge.correction_adapter,
    )
    with pytest.raises(NativeClaimLoopBridgeError, match="unavailable source ref"):
        wrong_source_bridge.record_proposal_revision(
            claim_id=CLAIM_ID,
            loop_id=ensured["loop_id"],
            prior_cycle_id="initial-actions",
            cycle_id="revision-actions",
            revision_packet=wrong_source,
            idempotency_key="native.revision.wrong-source.0001",
        )
    assert loop.state(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID, loop_id=ensured["loop_id"]
    ).state_sha256 == before.state_sha256
    result = bridge.record_proposal_revision(
        claim_id=CLAIM_ID,
        loop_id=ensured["loop_id"],
        prior_cycle_id="initial-actions",
        cycle_id="revision-actions",
        revision_packet=packet,
        idempotency_key="native.revision.record.0001",
    )
    after = loop.state(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID, loop_id=ensured["loop_id"]
    )
    assert after.facts == facts_before
    assert after.observations == ()
    assert after.selected_action is None
    assert after.sufficiency.status.value != "decision_ready"
    assert len(after.native_proposal_revisions) == 1
    assert after.native_proposal_revisions[0].actions == ()
    assert [value.disposition for value in after.native_proposal_revisions[0].action_dispositions] == ["retired", "retired"]
    assert derive_evidence_action_v1(after) is None

    restarted_adapter = NativeSourceSetAdapterV1()
    restarted_correction = NativeSourceCorrectionAdapterV1()
    restarted = ClaimLoopService(
        loop.storage,
        adapters={restarted_adapter.adapter_id: restarted_adapter},
        artifact_interpreter=NativeSourceSetInterpreterV1(),
        correction_adapters={restarted_correction.adapter_id: restarted_correction},
        cycle_pipeline=loop.cycle_pipeline,
        authorized_owned_sessions=(WORKSPACE_CLAIM_LOOP_SESSION_ID,),
        reconciliation_scope="authorized_only",
        clock=lambda: NOW,
    )
    restarted_bridge = NativeClaimLoopBridgeV1(
        native_material=lambda _claim_id, cycle_id: materials[cycle_id],
        claim_loop=restarted,
        pipeline_router=loop.cycle_pipeline,
        adapter=restarted_adapter,
        correction_adapter=restarted_correction,
    )
    assert restarted_bridge.record_proposal_revision(
        claim_id=CLAIM_ID,
        loop_id=ensured["loop_id"],
        prior_cycle_id="initial-actions",
        cycle_id="revision-actions",
        revision_packet=packet,
        idempotency_key="native.revision.record.0001",
    ) == result
    restarted_state = restarted.state(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID, loop_id=ensured["loop_id"]
    )
    assert restarted_state.state_sha256 == after.state_sha256
    assert len(restarted_state.native_proposal_revisions) == 1
    assert restarted_state.native_proposal_revisions[0].actions == ()
    assert derive_evidence_action_v1(restarted_state) is None

    conflicting = deepcopy(packet)
    conflicting["prior_action_dispositions"][0]["reason"] = "Different input."
    conflicting_material = deepcopy(revision)
    conflicting_material["proposal_revision_packet_sha256"] = digest_value(conflicting)
    conflict_bridge = NativeClaimLoopBridgeV1(
        native_material=lambda _claim_id, _cycle_id: conflicting_material,
        claim_loop=restarted,
        pipeline_router=loop.cycle_pipeline,
        adapter=restarted_adapter,
        correction_adapter=restarted_correction,
    )
    with pytest.raises(NativeClaimLoopBridgeError):
        conflict_bridge.record_proposal_revision(
            claim_id=CLAIM_ID,
            loop_id=ensured["loop_id"],
            prior_cycle_id="initial-actions",
            cycle_id="revision-actions",
            revision_packet=conflicting,
            idempotency_key="native.revision.record.0001",
        )


PENDING_PURPOSE = "Establish whether heating is restored after the scheduled visit."


def _pending_revision_materials(until: str | None) -> tuple[dict, dict, dict]:
    initial = _set_need_temporality(
        _material(
            "pending-initial",
            [("source-original", "Please obtain the post-visit restoration outcome.\n")],
            answered=False,
        ),
        state="missing",
        answer=None,
        until=None,
    )
    initial_need = initial["provisional_proposal"]["needs"][0]
    initial_need["description"] = PENDING_PURPOSE
    initial_need["proposal_item_sha256"] = digest_value(
        {
            key: value
            for key, value in initial_need.items()
            if key != "proposal_item_sha256"
        }
    )
    initial_proposal = initial["provisional_proposal"]
    initial_proposal["proposal_sha256"] = digest_value(
        {
            key: value
            for key, value in initial_proposal.items()
            if key != "proposal_sha256"
        }
    )
    initial = _set_proposed_action(
        initial,
        {
            "audience": "provider",
            "enabled": True,
            "requested_contents": ["Confirm the post-visit restoration outcome."],
        },
    )

    promise = (
        "Event status: the provider will report the restoration outcome by "
        f"{until}.\n"
        if until is not None
        else "Event status: the provider will report after the visit; no delivery time was given.\n"
    )
    revision = _set_need_temporality(
        _material(
            "pending-revision",
            [
                ("source-original", "Please obtain the post-visit restoration outcome.\n"),
                ("source-promise", promise),
            ],
            answered=True,
        ),
        state="pending",
        answer=None,
        until=until,
    )
    reading = {
        "question": PENDING_PURPOSE,
        "answer": None,
        "source_refs": ["t1"],
        "state": "pending",
        "uncertainty": "The future restoration outcome has not yet been supplied.",
    }
    if until is not None:
        reading["until"] = until
    packet = {
        "readings": [reading],
        "actions": [],
        "prior_action_dispositions": [
            {
                "disposition": "retired",
                "prior_action_index": 0,
                "reason": (
                    "The provider promised a later answer, so the current outgoing "
                    "request is retired while its purpose remains pending."
                ),
                "source_refs": ["t1"],
            }
        ],
    }
    revision["proposal_revision_packet_sha256"] = digest_value(packet)
    return initial, revision, packet


def test_native_initial_pending_need_preserves_null_deadline_without_action(
    tmp_path: Path,
) -> None:
    material = _set_need_temporality(
        _material(
            "pending-entry",
            [("source-promise", "A post-visit outcome report will follow.\n")],
            answered=False,
        ),
        state="pending",
        answer=None,
        until=None,
    )
    bridge, loop, _ = _system(tmp_path, {"pending-entry": material})
    ensured = bridge.ensure(
        claim_id=CLAIM_ID,
        cycle_id="pending-entry",
        idempotency_key="native.pending.entry.0001",
    )
    state = loop.state(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
        loop_id=ensured["loop_id"],
    )
    roster = state.accepted_artifacts["observable_package"]["native_need_roster"]

    assert roster[0]["state"] == "pending"
    assert roster[0]["until"] is None
    assert roster[0]["proposed_action"] is None
    assert state.observations == ()
    assert state.active_dispatch_sha256 is None
    assert state.sufficiency.status.value != "decision_ready"

    invalid_material = _set_need_temporality(
        material,
        state="received",
        answer="The restoration outcome is known.",
        until="2026-05-13T10:00:00+02:00",
    )
    invalid_root = tmp_path / "invalid-deadline"
    invalid_root.mkdir()
    invalid_bridge, _, _ = _system(
        invalid_root, {"pending-entry": invalid_material}
    )
    with pytest.raises(
        NativeClaimLoopBridgeError, match="until requires pending state"
    ):
        invalid_bridge.ensure(
            claim_id=CLAIM_ID,
            cycle_id="pending-entry",
            idempotency_key="native.pending.invalid-deadline.0001",
        )


@pytest.mark.parametrize(
    "until",
    [None, "2026-05-13T10:00:00+02:00"],
    ids=["unspecified-deadline", "explicit-deadline"],
)
def test_native_pending_revision_is_durable_source_bound_and_idempotent(
    tmp_path: Path,
    until: str | None,
) -> None:
    initial, revision, packet = _pending_revision_materials(until)
    materials = {"pending-initial": initial, "pending-revision": revision}
    bridge, loop, _ = _system(tmp_path, materials)
    ensured = bridge.ensure(
        claim_id=CLAIM_ID,
        cycle_id="pending-initial",
        idempotency_key="native.pending.ensure.0001",
    )
    before = loop.state(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
        loop_id=ensured["loop_id"],
    )

    if until is not None:
        malformed = deepcopy(packet)
        malformed["readings"][0]["until"] = "2026-05-13T10:00:00"
        malformed_material = deepcopy(revision)
        malformed_material["proposal_revision_packet_sha256"] = digest_value(
            malformed
        )
        malformed_bridge = NativeClaimLoopBridgeV1(
            native_material=lambda _claim_id, _cycle_id: malformed_material,
            claim_loop=loop,
            pipeline_router=loop.cycle_pipeline,
            adapter=bridge.adapter,
            correction_adapter=bridge.correction_adapter,
        )
        with pytest.raises(NativeClaimLoopBridgeError, match="until must be aware"):
            malformed_bridge.record_proposal_revision(
                claim_id=CLAIM_ID,
                loop_id=ensured["loop_id"],
                prior_cycle_id="pending-initial",
                cycle_id="pending-revision",
                revision_packet=malformed,
                idempotency_key="native.pending.malformed.0001",
            )
        assert loop.state(
            session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
            loop_id=ensured["loop_id"],
        ).state_sha256 == before.state_sha256

    result = bridge.record_proposal_revision(
        claim_id=CLAIM_ID,
        loop_id=ensured["loop_id"],
        prior_cycle_id="pending-initial",
        cycle_id="pending-revision",
        revision_packet=packet,
        idempotency_key="native.pending.revision.0001",
    )
    after = loop.state(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
        loop_id=ensured["loop_id"],
    )
    reading = after.native_proposal_revisions[-1].readings[0]
    serialized = after.model_dump(mode="json")["native_proposal_revisions"][-1]

    assert reading.state == "pending"
    assert reading.answer is None
    assert reading.until == until
    assert serialized["readings"][0]["until"] == until
    if until is not None:
        invalid_reading = reading.model_dump(mode="json")
        invalid_reading["state"] = "received"
        with pytest.raises(ValueError, match="until requires pending state"):
            type(reading).model_validate(invalid_reading)
    assert reading.evidence[0].source_ref.sanitized_excerpt == revision[
        "source_document"
    ]["text_views"][1]["units"][0]["text"]
    assert reading.description == PENDING_PURPOSE
    assert after.native_proposal_revisions[-1].actions == ()
    assert after.native_proposal_revisions[-1].canonical_fact_effect is None
    assert after.native_proposal_revisions[-1].readiness_effect is None
    assert after.facts == before.facts
    assert after.observations == before.observations
    assert after.active_dispatch_sha256 is None
    assert derive_evidence_action_v1(after) is None

    restarted_adapter = NativeSourceSetAdapterV1()
    restarted_correction = NativeSourceCorrectionAdapterV1()
    restarted = ClaimLoopService(
        loop.storage,
        adapters={restarted_adapter.adapter_id: restarted_adapter},
        artifact_interpreter=NativeSourceSetInterpreterV1(),
        correction_adapters={
            restarted_correction.adapter_id: restarted_correction
        },
        cycle_pipeline=loop.cycle_pipeline,
        authorized_owned_sessions=(WORKSPACE_CLAIM_LOOP_SESSION_ID,),
        reconciliation_scope="authorized_only",
        clock=lambda: NOW,
    )
    restarted_bridge = NativeClaimLoopBridgeV1(
        native_material=lambda _claim_id, cycle_id: materials[cycle_id],
        claim_loop=restarted,
        pipeline_router=loop.cycle_pipeline,
        adapter=restarted_adapter,
        correction_adapter=restarted_correction,
    )
    assert restarted_bridge.record_proposal_revision(
        claim_id=CLAIM_ID,
        loop_id=ensured["loop_id"],
        prior_cycle_id="pending-initial",
        cycle_id="pending-revision",
        revision_packet=packet,
        idempotency_key="native.pending.revision.0001",
    ) == result
    restarted_state = restarted.state(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
        loop_id=ensured["loop_id"],
    )
    assert restarted_state.state_sha256 == after.state_sha256
    assert restarted_state.native_proposal_revisions[-1].readings[0].until == until


def test_native_legacy_revision_and_state_hashes_rehydrate_without_until(
    tmp_path: Path,
) -> None:
    initial, revision, packet = _pending_revision_materials(None)
    materials = {"pending-initial": initial, "pending-revision": revision}
    bridge, loop, _ = _system(tmp_path, materials)
    ensured = bridge.ensure(
        claim_id=CLAIM_ID,
        cycle_id="pending-initial",
        idempotency_key="native.pending.legacy.ensure.0001",
    )
    bridge.record_proposal_revision(
        claim_id=CLAIM_ID,
        loop_id=ensured["loop_id"],
        prior_cycle_id="pending-initial",
        cycle_id="pending-revision",
        revision_packet=packet,
        idempotency_key="native.pending.legacy.revision.0001",
    )
    current = loop.state(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
        loop_id=ensured["loop_id"],
    )

    legacy = current.model_dump(mode="json")
    legacy_revision = legacy["native_proposal_revisions"][-1]
    assert legacy_revision["readings"][0].pop("until") is None
    legacy_revision["revision_sha256"] = digest_value(
        {
            key: value
            for key, value in legacy_revision.items()
            if key != "revision_sha256"
        }
    )
    legacy["state_sha256"] = digest_value(
        {key: value for key, value in legacy.items() if key != "state_sha256"}
    )

    rehydrated = type(current).model_validate(legacy)

    assert rehydrated.state_sha256 == legacy["state_sha256"]
    assert (
        rehydrated.native_proposal_revisions[-1].revision_sha256
        == legacy_revision["revision_sha256"]
    )
    assert rehydrated.native_proposal_revisions[-1].readings[0].until is None
