"""Development probe claims (dev_probe/claims.json): the interface of fresh/tenancy_fresh.py.

claim_ids(any split) lists the 16 probe claims; templates() is the fresh pack with the silence clause.
References (references.json) are for scoring only; no design sees them.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_fresh_for_probe", HERE.parent / "fresh" / "tenancy_fresh.py")
_F = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_F)
templates = _F.templates
attachment_text = _F.attachment_text
REQUEST_STATES = _F.REQUEST_STATES
_CLAIMS = json.loads((HERE / "claims.json").read_text())
_REFS = json.loads((HERE / "references.json").read_text())


def claim_ids(split: str = "test") -> list[str]:
    return sorted(_CLAIMS)


def intake(claim_id: str) -> dict:
    return _CLAIMS[claim_id]


def reference(claim_id: str) -> dict:
    return _REFS[claim_id]


def sources(claim_id: str) -> list[dict]:
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
