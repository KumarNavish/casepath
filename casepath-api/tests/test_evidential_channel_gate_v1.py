from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from casepath_api import app as app_module
from casepath_api import evidential_channel_gate_v1 as gate
from casepath_api.native_inference_v1 import PreparedInference, TransportRequest, TransportResponse
from casepath_api.native_live_workspace_v1 import (
    LIVE_RESEARCH_MODE,
    LIVE_RESEARCH_MODE_HEADER,
    decode_provisional_proposal,
)

CLAIM_ID = "clm_bd74de2a73d9e05a"
ROOT = f"/api/claim-loops/v1/workspace/claims/{CLAIM_ID}/native-inquiry/live"
T0 = "2025-08-27T09:00:00+02:00"
T1 = "2025-08-28T09:00:00+02:00"
T2 = "2025-08-29T09:00:00+02:00"


def _prepared(returned_text: str | None) -> PreparedInference:
    views = [{"source_id": "com_claim", "view_id": "v1", "first_observed_at": T0,
              "units": [{"ref": "t0", "text": "I found the signed notice at home; it shows 3 March."}]}]
    receipts: list[dict[str, Any]] = [{"artifact_id": "com_claim", "media_type": "text/plain", "raw_sha256": "0" * 64, "size_bytes": 1,
                                       "admission_receipt": {"authority": "PublicCorpus.artifact", "claim_id": CLAIM_ID, "artifact_id": "com_claim"}}]
    if returned_text is not None:
        views.append({"source_id": "ret_notice", "view_id": "v1", "first_observed_at": T1, "units": [{"ref": "t1", "text": returned_text}]})
        receipts.append({"artifact_id": "ret_notice", "media_type": "text/plain", "raw_sha256": "1" * 64, "size_bytes": 1,
                         "admission_receipt": {"authority": "NativeLiveWorkspaceServiceV1.source_admission", "admission": {"kind": "export"}}})
    document = {"text_views": views, "image_views": []}
    return PreparedInference(messages=({"role": "system", "content": "x"}, {"role": "user", "content": [{"type": "text", "text": json.dumps(document)}]}),
                             input_identity="input.test", source_prefix_sha256="2" * 64, source_receipts=tuple(receipts), image_receipts=(), observed_at=T1)


def _output(state: str, refs: list[str]) -> dict[str, Any]:
    return {"needs": [{"need_id": "notice_date", "description": "Signed notice date", "answer": "3 March", "warrant_refs": ["t0"],
                       "evidence": [{"ref": r, "role": "support"} for r in refs], "state": state, "until": None}]}


def test_gate_caps_hearsay_receipt_but_keeps_returned_artifact() -> None:
    hearsay = decode_provisional_proposal(actor_output=_output("received", ["t0"]), prepared=_prepared(None), channel_gate=True)
    assert hearsay["needs"][0]["state"] == "partial"
    assert hearsay["needs"][0]["channel_gate"]["support_channels"] == ["party_report"]
    assert hearsay["evidential_channel_gate"]["capped_count"] == 1
    returned = decode_provisional_proposal(actor_output=_output("received", ["t1"]), prepared=_prepared("Signed notice dated 3 March 2025."), channel_gate=True)
    assert returned["needs"][0]["state"] == "received"
    assert returned["evidential_channel_gate"]["capped_count"] == 0
    no_support = decode_provisional_proposal(actor_output=_output("received", []), prepared=_prepared(None), channel_gate=True)
    assert no_support["needs"][0]["state"] == "missing"


def test_gate_disabled_is_the_unchanged_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CASEPATH_EVIDENTIAL_CHANNEL_V1", raising=False)
    off = decode_provisional_proposal(actor_output=_output("received", ["t0"]), prepared=_prepared(None))
    assert off["needs"][0]["state"] == "received" and off["evidential_channel_gate"] is None
    monkeypatch.setenv("CASEPATH_EVIDENTIAL_CHANNEL_V1", "1")
    on = decode_provisional_proposal(actor_output=_output("received", ["t0"]), prepared=_prepared(None))
    assert on["needs"][0]["state"] == "partial"
    assert on["proposal_sha256"] != off["proposal_sha256"]


def test_channel_map_uses_admission_metadata_only() -> None:
    assert gate.channel_for_admission({"authority": "PublicCorpus.artifact"}) == "party_report"
    assert gate.channel_for_admission({"authority": "x", "admission": {"kind": "source_update"}}) == "returned_artifact"
    assert gate.channel_for_admission(None) == "party_report"


# ---- end-to-end through the mounted native live workspace (zero-provider sequence transport) ----
def _response(output: dict[str, Any]) -> TransportResponse:
    final = json.dumps(output, sort_keys=True, separators=(",", ":"))
    events = [{"type": "thread.started", "thread_id": "test-thread"}, {"type": "item.completed", "item": {"type": "agent_message", "text": final}},
              {"type": "turn.completed", "usage": {"input_tokens": 1, "cached_input_tokens": 0, "output_tokens": 1, "reasoning_output_tokens": 0}}]
    return TransportResponse(returncode=0, stdout="".join(json.dumps(e) + "\n" for e in events), stderr="", final_output=final)


@dataclass
class _SequenceTransport:
    outputs: list[dict[str, Any]]
    requests: list[TransportRequest]

    def __call__(self, request: TransportRequest) -> TransportResponse:
        self.requests.append(request)
        return _response(self.outputs[len(self.requests) - 1])


def _headers(key: str) -> dict[str, str]:
    return {LIVE_RESEARCH_MODE_HEADER: LIVE_RESEARCH_MODE, "X-CasePath-Idempotency-Key": key}


def _source(source_id: str, text: str) -> dict[str, str]:
    raw = text.encode("utf-8")
    return {"source_id": source_id, "file_name": source_id + ".txt", "media_type": "text/plain; charset=utf-8",
            "raw_base64": base64.b64encode(raw).decode("ascii"), "sha256": hashlib.sha256(raw).hexdigest()}


def _live_output(state: str, evidence_refs: list[str], *channels: str) -> dict[str, Any]:
    return {"needs": [{"need_id": "grant_record", "description": "Match the grant decision to this building.", "answer": "Building East" if state == "received" else None,
                       "warrant_refs": ["t0"], "evidence": [{"ref": r, "role": "support"} for r in evidence_refs], "state": state, "until": None}],
            "requests": [{"channel_id": c, "need_ids": ["grant_record"], "purpose": f"Export the declared {c} case file."} for c in channels]}


def test_live_workflow_invokes_gate_before_and_after_a_return(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hearsay_output = _live_output("received", ["t0"], "c1")      # model claims receipt from the claim text alone
    transport = _SequenceTransport([hearsay_output, hearsay_output, None], [])  # third output filled after we know the return alias
    monkeypatch.setenv("CASEPATH_NATIVE_LIVE_ENABLED", "1")
    monkeypatch.setenv("CASEPATH_NATIVE_LIVE_ROOT", str(tmp_path / "runtime"))
    monkeypatch.setenv("CASEPATH_EVIDENTIAL_CHANNEL_V1", "1")
    monkeypatch.delenv("CASEPATH_NATIVE_LIVE_ENABLE_CODEX_TRANSPORT", raising=False)
    app_module.native_live_workspace_service.cache_clear()
    service = app_module.native_live_workspace_service()
    service.transport = transport
    times = iter((T0, T0, T1, T2, T2))
    service.clock = lambda: next(times)
    config = {"system_prompt": "Use only supplied public sources and channel catalog.", "refinement_prompt": "Review the exact fresh proposal independently.",
              "available_channels": [{"channel_id": "c1", "description": "Grant register export."}], "remaining_export_attempts": 1}
    returned = _source("grant_export", "Grant decision G-52 is registered to Building East, Rosenweg 12.\n")
    try:
        with TestClient(app_module.app) as client:
            assert client.put(ROOT + "/export-config", headers=_headers("gate.config.0001"), json=config).status_code == 200
            read = client.post(ROOT, headers=_headers("gate.read.0001"))
            assert read.status_code == 200, read.text
            proposal = read.json()["provisional_proposal"]
            assert proposal["needs"][0]["state"] == "partial"                      # gate capped the hearsay receipt
            assert proposal["evidential_channel_gate"]["capped_count"] == 1
            refined = client.post(ROOT, headers=_headers("gate.refine.0001"), json={"fresh_proposal": hearsay_output})
            assert refined.status_code == 200, refined.text
            admission = {"kind": "export", "origin_cycle_id": refined.json()["cycle_id"], "request_index": 0, "request": hearsay_output["requests"][0],
                         "status": "exported", "observed_at": T1, "source": returned}
            admitted = client.post(ROOT + "/source-admissions", headers=_headers("gate.admit.0001"), json=admission)
            assert admitted.status_code == 200, admitted.text
            # the returned export renders as later text aliases; cite the first alias after the claim's own units
            prior_input = json.loads(transport.requests[1].stdin)
            claim_units = sum(len(v["units"]) for v in prior_input["text_views"])
            transport.outputs[2] = _live_output("received", [f"t{claim_units}"])
            update = client.post(ROOT, headers=_headers("gate.update.0001"))
            assert update.status_code == 200, update.text
            after = update.json()["provisional_proposal"]
            assert after["needs"][0]["state"] == "received"                        # returned artifact retains receipt
            assert after["needs"][0]["channel_gate"]["support_channels"] == ["returned_artifact"]
            assert after["evidential_channel_gate"]["capped_count"] == 0
            state = client.get(ROOT, headers=_headers("gate.state.0001"))
            assert state.status_code == 200
    finally:
        app_module.native_live_workspace_service.cache_clear()


def test_intake_attachment_is_an_artifact_and_the_message_is_a_report() -> None:
    """The live corpus admits both through PublicCorpus.artifact; the declared role separates them."""
    message = {"authority": "PublicCorpus.artifact", "artifact_role": "customer_message", "file_name": "claim.eml"}
    attachment = {"authority": "PublicCorpus.artifact", "artifact_role": "attachment", "file_name": "Kuendigung.pdf"}
    later = {"authority": "NativeLiveWorkspaceServiceV1.source_admission", "admission": {"kind": "export"}}
    assert gate.channel_for_admission(message) == "party_report"
    assert gate.channel_for_admission(attachment) == "returned_artifact"
    assert gate.channel_for_admission(later) == "returned_artifact"
    assert gate.channel_for_admission({"authority": "PublicCorpus.artifact"}) == "party_report"
