"""Channel-typed evidential gate for the native live workspace (CTES product integration).

Every public text/image pointer a proposal cites belongs to an admitted source whose admission receipt
says how the bytes entered the workspace: the original claim packet (``PublicCorpus.artifact``: a party
report) or a later admission (``NativeLiveWorkspaceServiceV1.source_admission`` with kind ``export`` or
``source_update``: a returned artifact). The gate caps a need's proposed state by the channels of its
supporting evidence: ``received`` is retained only when at least one supporting pointer comes from a
returned artifact; otherwise the state is lowered to ``partial`` (a party report about the record) or
``missing`` (no supporting evidence at all). The model's answer text is retained verbatim as a
fallible reading. Enabled by ``CASEPATH_EVIDENTIAL_CHANNEL_V1=1``; disabled, the proposal is unchanged
(the preregistered ablation).
"""
from __future__ import annotations

import os
from typing import Any, Mapping, Sequence

GATE_CONTRACT = "casepath.evidential-channel-gate/1.0.0"
RETURNED_KINDS = {"export", "source_update", "unsolicited_source_update"}
CAPPED_STATES = {"received"}


def gate_enabled(override: bool | None = None) -> bool:
    if override is not None:
        return override
    return os.environ.get("CASEPATH_EVIDENTIAL_CHANNEL_V1", "") == "1"


PARTY_ROLES = {"customer_message"}
ARTIFACT_ROLES = {"attachment"}


def channel_for_admission(receipt: Mapping[str, Any] | None) -> str:
    """Channel from admission metadata only — never from content or model judgement.

    Inside the intake packet the product admits the customer's own message and the documents the
    customer actually attached through the same authority, so the artifact's declared role is what
    separates them: ``customer_message`` is a party report, ``attachment`` is a document that is
    genuinely in the workspace. A later admission (an export the workspace requested, or a source
    update) is a returned artifact. Anything unrecognised is treated conservatively as a report.
    """
    if not receipt:
        return "party_report"
    role = receipt.get("artifact_role")
    if role in ARTIFACT_ROLES:
        return "returned_artifact"
    if role in PARTY_ROLES:
        return "party_report"
    admission = receipt.get("admission") or {}
    if admission.get("kind") in RETURNED_KINDS:
        return "returned_artifact"
    if receipt.get("authority") == "PublicCorpus.artifact":
        return "party_report"
    return "party_report"


def channel_map(source_receipts: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    return {str(row["artifact_id"]): channel_for_admission(row.get("admission_receipt")) for row in source_receipts}


def apply_gate(needs: list[dict[str, Any]], registry: Mapping[str, Mapping[str, Any]], channels: Mapping[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return gated need materials plus a gate receipt. Never raises on unknown sources (treated as party reports)."""
    gated: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for need in needs:
        supports = [item for item in need.get("evidence", []) if item.get("role") == "support"]
        support_channels = sorted({channels.get(str(item.get("source_id")), "party_report") for item in supports})
        state = need["state"]
        new_state = state
        if state in CAPPED_STATES and "returned_artifact" not in support_channels:
            new_state = "partial" if supports else "missing"
        decisions.append({"need_id": need["need_id"], "proposed_state": state, "gated_state": new_state,
                          "support_channels": support_channels, "capped": new_state != state})
        gated.append({**need, "state": new_state, "channel_gate": {"proposed_state": state, "support_channels": support_channels}})
    receipt = {"contract": GATE_CONTRACT, "enabled": True, "decisions": decisions, "capped_count": sum(d["capped"] for d in decisions)}
    return gated, receipt
