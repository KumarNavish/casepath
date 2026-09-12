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
from casepath_api.native_inference_v1 import TransportRequest, TransportResponse
from casepath_api.native_live_workspace_v1 import (
    LIVE_RESEARCH_MODE,
    LIVE_RESEARCH_MODE_HEADER,
)


CLAIM_ID = "clm_bd74de2a73d9e05a"
ROOT = f"/api/claim-loops/v1/workspace/claims/{CLAIM_ID}/native-inquiry/live"
T0 = "2025-08-27T09:00:00+02:00"
T1 = "2025-08-28T09:00:00+02:00"
T2 = "2025-08-29T09:00:00+02:00"


def _need() -> dict[str, Any]:
    return {
        "need_id": "grant_record",
        "description": "Match the grant decision to this building.",
        "answer": None,
        "warrant_refs": ["t0"],
        "evidence": [],
        "state": "missing",
        "until": None,
    }


def _output(*channels: str) -> dict[str, Any]:
    return {
        "needs": [_need()],
        "requests": [
            {
                "channel_id": channel,
                "need_ids": ["grant_record"],
                "purpose": f"Export the declared {channel} case file.",
            }
            for channel in channels
        ],
    }


def _response(output: dict[str, Any]) -> TransportResponse:
    final = json.dumps(output, sort_keys=True, separators=(",", ":"))
    events = [
        {"type": "thread.started", "thread_id": "test-thread"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": final}},
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 1,
                "cached_input_tokens": 0,
                "output_tokens": 1,
                "reasoning_output_tokens": 0,
            },
        },
    ]
    return TransportResponse(
        returncode=0,
        stdout="".join(json.dumps(event) + "\n" for event in events),
        stderr="",
        final_output=final,
    )


@dataclass
class _SequenceTransport:
    outputs: list[dict[str, Any]]
    requests: list[TransportRequest]

    def __call__(self, request: TransportRequest) -> TransportResponse:
        self.requests.append(request)
        return _response(self.outputs[len(self.requests) - 1])


def _headers(key: str) -> dict[str, str]:
    return {
        LIVE_RESEARCH_MODE_HEADER: LIVE_RESEARCH_MODE,
        "X-CasePath-Idempotency-Key": key,
    }


def _source(source_id: str, text: str) -> dict[str, str]:
    raw = text.encode("utf-8")
    return {
        "source_id": source_id,
        "file_name": source_id + ".txt",
        "media_type": "text/plain; charset=utf-8",
        "raw_base64": base64.b64encode(raw).decode("ascii"),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def test_mounted_export_loop_charges_actions_and_admits_exact_source_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    read_output = _output("c3")
    refined_output = _output("c1", "c2")
    transport = _SequenceTransport(
        [read_output, refined_output, _output(), _output()], []
    )
    monkeypatch.setenv("CASEPATH_NATIVE_LIVE_ENABLED", "1")
    monkeypatch.setenv("CASEPATH_NATIVE_LIVE_ROOT", str(tmp_path / "runtime"))
    monkeypatch.delenv("CASEPATH_NATIVE_LIVE_ENABLE_CODEX_TRANSPORT", raising=False)
    app_module.native_live_workspace_service.cache_clear()
    service = app_module.native_live_workspace_service()
    service.transport = transport
    times = iter((T0, T0, T1, T2))
    service.clock = lambda: next(times)
    config = {
        "system_prompt": "Use only supplied public sources and channel catalog.",
        "refinement_prompt": "Review the exact fresh proposal independently.",
        "available_channels": [
            {"channel_id": "c1", "description": "First public export."},
            {"channel_id": "c2", "description": "Second public export."},
            {"channel_id": "c3", "description": "Third public export."},
        ],
        "remaining_export_attempts": 2,
    }
    primary_text = "Controlled primary export bytes.\nSecond line retained.\n"
    correction_text = "Controlled correction bytes.\n"
    primary = _source("record_primary", primary_text)
    correction = _source("record_correction", correction_text)
    try:
        with TestClient(app_module.app) as client:
            configured = client.put(
                ROOT + "/export-config",
                headers=_headers("export.config.0001"),
                json=config,
            )
            assert configured.status_code == 200, configured.text

            read = client.post(ROOT, headers=_headers("export.read.0001"))
            assert read.status_code == 200, read.text
            assert read.json()["actor_output"] == read_output

            bad_refine = client.post(
                ROOT,
                headers=_headers("export.refine.bad.0001"),
                json={"fresh_proposal": refined_output},
            )
            assert bad_refine.status_code == 409
            refined = client.post(
                ROOT,
                headers=_headers("export.refine.0001"),
                json={"fresh_proposal": read_output},
            )
            assert refined.status_code == 200, refined.text
            assert refined.json()["actor_output"] == refined_output
            refined_input = json.loads(transport.requests[1].stdin)
            assert refined_input["prior_self"] == []
            assert refined_input["fresh_proposal"] == read_output

            for index, channel in enumerate(("c1", "c2")):
                request = refined_output["requests"][index]
                admission = {
                    "kind": "export",
                    "origin_cycle_id": refined.json()["cycle_id"],
                    "request_index": index,
                    "request": request,
                    "status": "exported",
                    "observed_at": T1,
                    "source": primary,
                }
                admitted = client.post(
                    ROOT + "/source-admissions",
                    headers=_headers(f"export.admit.{index}.0001"),
                    json=admission,
                )
                assert admitted.status_code == 200, admitted.text
                assert admitted.json()["export_state"]["remaining_export_attempts"] == 1 - index
                if index == 1:
                    assert admitted.json()["source_receipt"][
                        "duplicate_of_prior_source"
                    ] is True

            update = client.post(ROOT, headers=_headers("export.update.0001"))
            assert update.status_code == 200, update.text
            update_input = json.loads(transport.requests[2].stdin)
            rendered_primary = "".join(
                unit["text"]
                for view in update_input["text_views"]
                if view["source_id"] == primary["source_id"]
                for unit in view["units"]
            )
            assert rendered_primary == primary_text
            assert update_input["remaining_export_attempts"] == 0
            assert len(update_input["actual_exports"]) == 2

            source_update = {
                "kind": "source_update",
                "origin_cycle_id": update.json()["cycle_id"],
                "replaces_source_id": primary["source_id"],
                "provenance_ref": "controlled-tape/update-after-observation",
                "observed_at": T2,
                "source": correction,
            }
            corrected = client.post(
                ROOT + "/source-admissions",
                headers=_headers("export.correction.0001"),
                json=source_update,
            )
            assert corrected.status_code == 200, corrected.text
            assert corrected.json()["source_receipt"]["cost"] == 0

            app_module.native_live_workspace_service.cache_clear()
            restarted = app_module.native_live_workspace_service()
            restarted.transport = transport
            restarted.clock = lambda: T2
            final = client.post(ROOT, headers=_headers("export.final.0001"))
            assert final.status_code == 200, final.text
            final_input = json.loads(transport.requests[3].stdin)
            rendered_correction = "".join(
                unit["text"]
                for view in final_input["text_views"]
                if view["source_id"] == correction["source_id"]
                for unit in view["units"]
            )
            assert rendered_correction == correction_text
            assert final.json()["export_state"]["remaining_export_attempts"] == 0
            assert len(final.json()["export_state"]["actions"]) == 2
            assert final.json()["export_state"]["current_output"] == _output()

            state = client.get(
                ROOT, headers={LIVE_RESEARCH_MODE_HEADER: LIVE_RESEARCH_MODE}
            )
            assert state.status_code == 200
            assert state.json()["export_state"]["current_output"] == _output()
            assert len(transport.requests) == 4
    finally:
        app_module.native_live_workspace_service.cache_clear()
