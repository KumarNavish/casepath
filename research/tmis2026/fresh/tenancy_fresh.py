"""Fresh tenancy claims (Study 2): same interface as harness/tenancy_data.py.

72 claims in 18 families from fresh/tenancy/generate.py. The rule pack is the admitted
template set plus the silence-policy clause (fresh/tenancy/rules/). References are for
scoring only; no method sees them. All fresh claims are held out: claim_ids("test") lists
them and claim_ids("dev") is empty (development uses the Study 1 development split).

Reference keys shared with Study 1: claim_id, family, scenario, implicit_flags,
document_states, request_set, family_id. Additional keys: fact_states, policy_verdicts,
open_fact {flag, true_value}, held_set, answered {document_states, request_set},
engine_routes, attachments [{artifact_id, document_type, sufficient, omitted_field}].
Document states: required_now, supplied_insufficient (both requested), held (depends on
the open fact), supplied_sufficient, not_needed.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE / "tenancy"
DATA = ROOT / "data"
REPO = HERE.parents[2]
REQUEST_STATES = {"required_now", "supplied_insufficient"}
IMPLICIT_FLAGS = {"lease_termination_dispute": {"termination_received": True},
                  "rent_increase_dispute": {"claim_received": True}}


def templates() -> dict:
    """The admitted rule packs plus the silence-policy clause (process catalogues unchanged)."""
    return json.loads((ROOT / "rules" / "static-rule-templates-v3-silence.json").read_text())


def cohort() -> dict:
    return json.loads((ROOT / "cohort.json").read_text())


def claim_ids(split: str) -> list[str]:
    if split == "dev":
        return []
    return sorted(p.stem for p in (DATA / "claims").glob("*.json"))


def intake(claim_id: str) -> dict:
    path = DATA / "claims" / f"{claim_id}.json"
    if not path.exists():
        raise KeyError(claim_id)
    return json.loads(path.read_text())


def reference(claim_id: str) -> dict:
    return json.loads((DATA / "references" / f"{claim_id}.json").read_text())


def attachment_text(att: dict) -> tuple[str, bool]:
    """Fresh attachments are plain text; the full text is available."""
    if att["media_type"] == "text/plain":
        text = base64.b64decode(att["content_base64"]).decode()
        return text, bool(text.strip())
    return "", False


def sources(claim_id: str) -> list[dict]:
    """What every method reads: the message body and attachment texts."""
    packet = intake(claim_id)
    msg = packet["customer_message"]
    rows = [{"artifact_id": msg["message_id"], "role": "customer_message", "file_name": "message.txt",
             "media_type": "text/plain", "text": msg["body"], "complete": True}]
    for att in packet.get("attachments", []):
        text, complete = attachment_text(att)
        rows.append({"artifact_id": att["artifact_id"], "role": "supporting_document", "file_name": att["file_name"],
                     "media_type": att["media_type"], "text": text, "complete": complete})
    for row in rows:
        row["sha256"] = hashlib.sha256(row["text"].encode()).hexdigest()
    return rows
