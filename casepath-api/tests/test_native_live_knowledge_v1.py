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
ORIGINAL_SOURCE_ID = "com_41f8115f9cf98700"
ROOT = f"/api/claim-loops/v1/workspace/claims/{CLAIM_ID}/native-inquiry/live"
T0 = "2025-08-27T09:00:00+02:00"
T1 = "2025-08-28T09:00:00+02:00"


def _source(source_id: str, text: str) -> dict[str, str]:
    raw = text.encode("utf-8")
    return {
        "source_id": source_id,
        "file_name": source_id + ".txt",
        "media_type": "text/plain; charset=utf-8",
        "raw_base64": base64.b64encode(raw).decode("ascii"),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _output(*, evidence_ref: str, answer: str) -> dict[str, Any]:
    return {
        "needs": [
            {
                "need_id": "grant_policy",
                "description": "Determine the applicable public grant policy.",
                "answer": answer,
                "warrant_refs": ["t9"],
                "evidence": [{"ref": evidence_ref, "role": "support"}],
                "state": "received",
                "until": None,
            }
        ],
        "requests": [],
    }


def _response(output: dict[str, Any]) -> TransportResponse:
    final = json.dumps(output, sort_keys=True, separators=(",", ":"))
    events = [
        {"type": "thread.started", "thread_id": "knowledge-test"},
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


def _config(knowledge: dict[str, Any]) -> dict[str, Any]:
    return {
        "system_prompt": "Read the supplied claim and public knowledge sources.",
        "refinement_prompt": "Review the exact fresh proposal.",
        "available_channels": [
            {"channel_id": "c1", "description": "Declared public export."}
        ],
        "remaining_export_attempts": 2,
        "knowledge_sources": [knowledge],
    }


def _aliases(document: dict[str, Any]) -> dict[str, tuple[str, str, str]]:
    return {
        unit["ref"]: (view["source_id"], view["view_id"], unit["text"])
        for view in document["text_views"]
        for unit in view["units"]
    }


def test_mounted_public_knowledge_bytes_and_revision_preserve_prior_aliases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy_text = "Public grant policy limit: CHF 500.\nReview annually.\n"
    revision_text = "Revised public grant policy limit: CHF 600.\nReview annually.\n"
    policy = _source("knowledge_policy_2025", policy_text)
    revision = _source("knowledge_policy_2025_r2", revision_text)
    first_output = _output(evidence_ref="t22", answer="The public policy states CHF 500.")
    second_output = _output(evidence_ref="t24", answer="The revision states CHF 600.")
    transport = _SequenceTransport([first_output, second_output], [])

    monkeypatch.setenv("CASEPATH_NATIVE_LIVE_ENABLED", "1")
    monkeypatch.setenv("CASEPATH_NATIVE_LIVE_ROOT", str(tmp_path / "runtime"))
    monkeypatch.delenv("CASEPATH_NATIVE_LIVE_ENABLE_CODEX_TRANSPORT", raising=False)
    app_module.native_live_workspace_service.cache_clear()
    service = app_module.native_live_workspace_service()
    service.transport = transport
    service.clock = lambda: T0
    try:
        with TestClient(app_module.app) as client:
            invalid = _config(
                {"knowledge_kind": "private_answer", "source": policy}
            )
            malformed = client.put(
                ROOT + "/export-config",
                headers=_headers("knowledge.invalid.0001"),
                json=invalid,
            )
            assert malformed.status_code == 400
            assert transport.requests == []

            conflicting = _config(
                {
                    "knowledge_kind": "policy",
                    "source": {**policy, "source_id": ORIGINAL_SOURCE_ID},
                }
            )
            conflict = client.put(
                ROOT + "/export-config",
                headers=_headers("knowledge.conflict.0001"),
                json=conflicting,
            )
            assert conflict.status_code == 409
            assert transport.requests == []

            config = _config({"knowledge_kind": "policy", "source": policy})
            configured = client.put(
                ROOT + "/export-config",
                headers=_headers("knowledge.config.0001"),
                json=config,
            )
            assert configured.status_code == 200, configured.text

            app_module.native_live_workspace_service.cache_clear()
            restarted = app_module.native_live_workspace_service()
            restarted.transport = transport
            restarted.clock = lambda: T0
            replayed_config = client.put(
                ROOT + "/export-config",
                headers=_headers("knowledge.config.0001"),
                json=config,
            )
            assert replayed_config.status_code == 200
            assert replayed_config.json()["replayed"] is True

            first = client.post(ROOT, headers=_headers("knowledge.read.0001"))
            assert first.status_code == 200, first.text
            first_document = json.loads(transport.requests[0].stdin)
            first_aliases = _aliases(first_document)
            policy_aliases = {
                ref: row for ref, row in first_aliases.items() if row[0] == policy["source_id"]
            }
            assert "".join(row[2] for row in policy_aliases.values()) == policy_text
            assert list(policy_aliases) == ["t22", "t23"]
            assert first_document["knowledge_sources"] == [
                {
                    "role": "public_domain_knowledge",
                    "knowledge_kind": "policy",
                    "source_id": policy["source_id"],
                    "sha256": policy["sha256"],
                    "first_observed_at": T0,
                    "source_order_zero_based": 1,
                    "supersedes_source_id": None,
                }
            ]
            developer_config = next(
                item
                for item in transport.requests[0].argv
                if item.startswith("developer_instructions=")
            )
            assert policy_text not in developer_config

            source_update = {
                "kind": "source_update",
                "origin_cycle_id": first.json()["cycle_id"],
                "replaces_source_id": policy["source_id"],
                "provenance_ref": "public-policy-registry/revision-2",
                "observed_at": T1,
                "source": revision,
            }
            updated = client.post(
                ROOT + "/source-admissions",
                headers=_headers("knowledge.revision.0001"),
                json=source_update,
            )
            assert updated.status_code == 200, updated.text
            receipt = updated.json()["source_receipt"]
            assert receipt["cost"] == 0
            assert receipt["knowledge_kind"] == "policy"
            assert receipt["superseded_knowledge_source_id"] == policy["source_id"]

            app_module.native_live_workspace_service.cache_clear()
            restarted = app_module.native_live_workspace_service()
            restarted.transport = transport
            restarted.clock = lambda: T1
            replayed_update = client.post(
                ROOT + "/source-admissions",
                headers=_headers("knowledge.revision.0001"),
                json=source_update,
            )
            assert replayed_update.status_code == 200
            assert replayed_update.json()["replayed"] is True

            second = client.post(ROOT, headers=_headers("knowledge.read.0002"))
            assert second.status_code == 200, second.text
            second_document = json.loads(transport.requests[1].stdin)
            second_aliases = _aliases(second_document)
            assert {
                ref: second_aliases[ref] for ref in first_aliases
            } == first_aliases
            revision_aliases = {
                ref: row
                for ref, row in second_aliases.items()
                if row[0] == revision["source_id"]
            }
            assert "".join(row[2] for row in revision_aliases.values()) == revision_text
            assert list(revision_aliases) == ["t24", "t25"]
            assert second_document["prior_self"] == first_output["needs"]
            assert second_document["actual_exports"] == []
            assert second_document["remaining_export_attempts"] == 2
            assert second_document["knowledge_sources"][1] == {
                "role": "public_domain_knowledge_revision",
                "knowledge_kind": "policy",
                "source_id": revision["source_id"],
                "sha256": revision["sha256"],
                "first_observed_at": T1,
                "source_order_zero_based": 2,
                "supersedes_source_id": policy["source_id"],
            }
            assert [row["artifact_id"] for row in second.json()["source_receipts"]] == [
                ORIGINAL_SOURCE_ID,
                policy["source_id"],
                revision["source_id"],
            ]
            assert second.json()["canonical_facts"] == {}
            assert second.json()["certified_readiness"] is None
            assert second.json()["customer_send"] is False
            assert len(transport.requests) == 2
    finally:
        app_module.native_live_workspace_service.cache_clear()
