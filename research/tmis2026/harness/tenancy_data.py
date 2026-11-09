"""Tenancy claims (Study B data) for the TMIS experiments.

Loads intake packets, the three admitted process templates and the scoring
references. References are used for scoring only; no method sees them.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
BENCH = REPO / "data" / "casepath-tenancy-claims" / "benchmark"
HELDOUT_REFS = REPO / "data" / "casepath-tenancy-claims" / "heldout-references"
REQUEST_STATES = {"missing", "provided_insufficient"}
IMPLICIT_FLAGS = {"lease_termination_dispute": {"termination_received": True},
                  "rent_increase_dispute": {"claim_received": True}}


def templates() -> dict:
    """The admitted rule packs; byte-identical to the product's static policy."""
    return json.loads((BENCH / "rules" / "static-rule-templates-v3.json").read_text())


def cohort() -> dict:
    return json.loads((BENCH / "cohort.json").read_text())


def claim_ids(split: str) -> list[str]:
    folder = "dev" if split == "dev" else "test"
    return sorted(p.stem for p in (BENCH / "data" / folder / "claims").glob("*.json"))


def intake(claim_id: str) -> dict:
    for folder in ("dev", "test"):
        path = BENCH / "data" / folder / "claims" / f"{claim_id}.json"
        if path.exists():
            return json.loads(path.read_text())
    raise KeyError(claim_id)


def reference(claim_id: str) -> dict:
    """Scoring reference: family, scenario flags and the document request set."""
    path = BENCH / "data" / "dev" / "gold" / f"{claim_id}.json"
    if not path.exists():
        path = HELDOUT_REFS / f"{claim_id}.json"
    gold = json.loads(path.read_text())
    contract = gold["acceptance_contract"]
    alias = {c["concept_id"]: c["aliases"][0] for c in contract["concepts"]
             if c["kind"] == "document" and c.get("aliases")}
    states = {}
    for row in contract["evidence_contracts"]:
        for doc_id, state in row["expected_document_states"].items():
            states[alias[doc_id]] = state
    return {
        "claim_id": claim_id,
        "family": _family(contract, alias),
        "scenario": dict(contract["scenario"]),
        # Routing flags the benchmark generator leaves implicit (always true in
        # its scenarios) but the latest product asks the model to judge.
        "implicit_flags": IMPLICIT_FLAGS.get(_family(contract, alias), {}),
        "document_states": states,
        "request_set": sorted(d for d, s in states.items() if s in REQUEST_STATES),
        "family_id": contract.get("metadata", {}).get("family"),
    }


def _family(contract: dict, alias: dict) -> str:
    docs = set(alias.values())
    for tpl in templates()["templates"]:
        kinds = {d["document_type"] for d in tpl["process_catalog"]["documents"]}
        if docs <= kinds:
            return tpl["domain"]
    raise ValueError("reference documents do not match one template")


def sources(claim_id: str) -> list[dict]:
    """What every method reads: the message body and attachment texts."""
    packet = intake(claim_id)
    msg = packet["customer_message"]
    rows = [{"artifact_id": msg["message_id"], "role": "customer_message",
             "file_name": "message.txt", "media_type": "text/plain",
             "text": msg["body"], "complete": True}]
    for att in packet.get("attachments", []):
        text, complete = attachment_text(att)
        rows.append({"artifact_id": att["artifact_id"], "role": "supporting_document",
                     "file_name": att["file_name"], "media_type": att["media_type"],
                     "text": text, "complete": complete})
    for row in rows:
        row["sha256"] = hashlib.sha256(row["text"].encode()).hexdigest()
    return rows


def attachment_text(att: dict) -> tuple[str, bool]:
    """Same projection as the original study: pypdf 5.9.0 plain text; images opaque."""
    data = base64.b64decode(att["content_base64"])
    if att["media_type"] == "application/pdf":
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(data), strict=True)
        pages = [page.extract_text(extraction_mode="plain") or "" for page in reader.pages]
        text = "\n\n".join(pages).strip()
        return text, bool(text) and all(p.strip() for p in pages)
    return "", False
