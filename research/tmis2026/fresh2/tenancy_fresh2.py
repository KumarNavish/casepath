"""Fresh2 tenancy claims (Study 3 confirmatory data): same interface as fresh/tenancy_fresh.py.

96 claims in 24 families built by fresh2/tenancy/build.py from hand-written messages (see fresh2/README.md). The
rule pack is the admitted template set plus the silence-policy clause (identical to fresh/). References are for
scoring only; no method sees them. All claims are held out: claim_ids("test") lists them, claim_ids("dev") is empty.

Reference keys as in fresh/: claim_id, family, scenario, implicit_flags, document_states, request_set, family_id,
fact_states, policy_verdicts, open_fact {flag, true_value}, held_set, answered {document_states, request_set},
engine_routes, attachments [{artifact_id, document_type, sufficient, omitted_field}]. New: fact states may be
'stated_false' (an inactive branch fact explicitly denied, or the dispute's defining event denied), and
implicit_flags may hold False (8 families in which the termination or rent increase was announced but no written
notice was received); 'expression' records how each stated fact is worded (plain / passing / implied).

Guard: every data access refuses to run in a process that has the model client loaded unless
ANALYSIS_PLAN_STUDY3.md is committed unmodified (fresh2/guard.py).
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE / "tenancy"
DATA = ROOT / "data"
REPO = HERE.parents[2]
REQUEST_STATES = {"required_now", "supplied_insufficient"}
IMPLICIT_FLAGS = {"lease_termination_dispute": {"termination_received": True},
                  "rent_increase_dispute": {"claim_received": True}}  # the presumption; per-claim truth is in reference()

import importlib.util as _ilu  # noqa: E402
if "fresh2_guard" not in sys.modules:
    _gs = _ilu.spec_from_file_location("fresh2_guard", HERE / "guard.py")
    sys.modules["fresh2_guard"] = _ilu.module_from_spec(_gs)
    _gs.loader.exec_module(sys.modules["fresh2_guard"])
check_model_process = sys.modules["fresh2_guard"].check_model_process


def templates() -> dict:
    """The admitted rule packs plus the silence-policy clause (process catalogues unchanged)."""
    check_model_process()
    return json.loads((ROOT / "rules" / "static-rule-templates-v3-silence.json").read_text())


def cohort() -> dict:
    check_model_process()
    return json.loads((ROOT / "cohort.json").read_text())


def claim_ids(split: str) -> list[str]:
    check_model_process()
    if split == "dev":
        return []
    return sorted(p.stem for p in (DATA / "claims").glob("*.json"))


def intake(claim_id: str) -> dict:
    check_model_process()
    path = DATA / "claims" / f"{claim_id}.json"
    if not path.exists():
        raise KeyError(claim_id)
    return json.loads(path.read_text())


def reference(claim_id: str) -> dict:
    check_model_process()
    return json.loads((DATA / "references" / f"{claim_id}.json").read_text())


def attachment_text(att: dict) -> tuple[str, bool]:
    """Fresh2 attachments are plain text; the full text is available."""
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
