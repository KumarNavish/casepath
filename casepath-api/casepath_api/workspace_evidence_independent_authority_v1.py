from __future__ import annotations

import re
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any

from .claim_loop import ClaimLoopError, playbook_template_from_accepted_v1
from .claim_loop_contracts import (
    AcquisitionReceiptV1,
    CanonicalFactInterpretationV1,
    ClaimLoopState,
    ClaimObservation,
    ClaimSourceRef,
    EvidenceAction,
)
from .foundation.common import digest_text, digest_value, is_sha256


_ADAPTER_ID = "loopback-source-byte-acquisition-v1"
_AUTHORITY_ID = "casepath.independent-evidence-authority/1.0.0"
_INTERPRETER_ID = "casepath.fixed-source-span-interpreter/1.0.0"
_GRAMMAR_ID = "casepath.workspace-source-span-grammar/1.0.0"
_SCHEMA_ID = "casepath.workspace-source-span-interpretation/1.0.0"
_SCHEMA_SHA256 = digest_value(
    {
        "schema_id": _SCHEMA_ID,
        "input": "exact-receipted-source-span",
        "output": "canonical-fact-interpretation/1.2.0",
        "unknown_default": True,
    }
)
_POSITIVE_TERMS = (
    "cough",
    "coughing",
    "hustet",
    "husten",
    "rash",
    "ausschlag",
    "pharmacy",
    "apotheke",
    "breathing",
    "atem",
)
_NEGATIVE_TERMS = (
    "no health effects",
    "no immediate health risk",
    "keine gesundheitlichen folgen",
    "kein unmittelbares gesundheitsrisiko",
)
_UNCERTAINTY_TERMS = (
    "unresolved",
    "unclear",
    "unknown",
    "missing",
    "cannot safely",
    "ungeklärt",
    "unklar",
    "offen",
    "fehlt",
    "nicht sicher",
)
_INSTRUCTION_PATTERNS = (
    r"\bignore\s+(?:all\s+)?(?:previous|prior)\s+instructions?\b",
    r"\b(?:set|choose|select|override|change|mark|grant)\s+(?:the\s+)?(?:finding|readiness|parser|policy|authority|branch|normalized value)\b",
    r"[\"'](?:finding|readiness|parser|policy|authority|process_branch|normalized_value)[\"']\s*[:=]",
    r"\b(?:approve|deny|pay|close)\s+(?:this\s+|the\s+)?claim\b",
)
_NEGATED_POSITIVE_PATTERNS = (
    r"\bno\s+(?:cough|coughing|rash|breathing problem)\b",
    r"\bwithout\s+(?:a\s+)?(?:cough|rash|breathing problem)\b",
    r"\bkein(?:e|en)?\s+(?:husten|ausschlag|atemproblem)\b",
)
_LEASE_TERMINATION_INTAKE_TERMS = (
    "termination",
    "termination notice",
    "notice of termination",
    "kündigung",
    "kündigungsschreiben",
    "mietvertragskündigung",
)
_RENT_INCREASE_INTAKE_TERMS = (
    "rent increase",
    "rent increases",
    "rent rises",
    "net rent",
    "gross rent",
    "mietzinserhöhung",
    "mietzins",
    "nettomiete",
    "bruttomiete",
)


def _module_sha256() -> str:
    return sha256(Path(__file__).read_bytes()).hexdigest()


def _term_present(text: str, term: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text) is not None


def _instruction_bearing(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) is not None for pattern in _INSTRUCTION_PATTERNS)


def _substantive(text: str) -> bool:
    return len(re.findall(r"\w+", text, flags=re.UNICODE)) >= 5


def _single_edge_intake_is_decisive(process_node_id: str, text: str) -> bool:
    folded = text.casefold()
    terms = (
        _LEASE_TERMINATION_INTAKE_TERMS
        if process_node_id.endswith("lt_intake")
        else (
            _RENT_INCREASE_INTAKE_TERMS
            if process_node_id.endswith("ri_intake")
            else ()
        )
    )
    return bool(terms) and any(_term_present(folded, term) for term in terms)


def _admission(state: ClaimLoopState) -> dict[str, Any]:
    package = state.accepted_artifacts.get("observable_package")
    value = package.get("workspace_evidence_admission") if isinstance(package, Mapping) else None
    if not isinstance(value, Mapping):
        raise ClaimLoopError("independent authority source policy is absent")
    material = dict(value)
    policy_sha256 = material.pop("policy_sha256", None)
    expected_policy_keys = {
        "contract",
        "policy_id",
        "source_registry_file_sha256",
        "source_entries",
        "actor_grants",
        "positive_assertion_requires_decision_bearing_grant",
        "operator_note_is_evidence",
        "policy_sha256",
    }
    if (
        set(value) != expected_policy_keys
        or value.get("contract")
        != "casepath.workspace-evidence-admission-policy/1.0.0"
        or value.get("policy_id")
        != "casepath.workspace-handler-source-admission/1.0.0"
        or policy_sha256 != digest_value(material)
        or not is_sha256(value.get("source_registry_file_sha256"))
        or value.get("positive_assertion_requires_decision_bearing_grant") is not True
        or value.get("operator_note_is_evidence") is not False
        or not isinstance(value.get("source_entries"), list)
        or not isinstance(value.get("actor_grants"), Mapping)
    ):
        raise ClaimLoopError("independent authority source policy is invalid")
    expected_entry_keys = {
        "contract",
        "source_kind",
        "support_scope",
        "artifact_id",
        "artifact_sha256",
        "parent_artifact_id",
        "parent_artifact_sha256",
        "representation_identity",
        "source_version",
        "locator_kind",
        "page",
        "text_start",
        "text_end",
        "byte_start",
        "byte_end",
        "exact_text",
        "span_sha256",
        "source_entry_sha256",
    }
    for entry in value["source_entries"]:
        if not isinstance(entry, Mapping) or set(entry) != expected_entry_keys:
            raise ClaimLoopError("independent authority source entry schema drifted")
        entry_material = {
            key: item for key, item in entry.items() if key != "source_entry_sha256"
        }
        exact_text = entry.get("exact_text")
        if (
            entry.get("source_entry_sha256") != digest_value(entry_material)
            or entry.get("contract")
            != "casepath.workspace-admissible-source-span/1.0.0"
            or entry.get("source_kind") != "observable_message_span"
            or entry.get("support_scope") != "case_specific"
            or entry.get("locator_kind") != "text_span"
            or entry.get("page") != 1
            or not isinstance(exact_text, str)
            or digest_text(exact_text) != entry.get("span_sha256")
            or entry.get("text_end") - entry.get("text_start") != len(exact_text)
            or entry.get("byte_end") - entry.get("byte_start")
            != len(exact_text.encode("utf-8"))
        ):
            raise ClaimLoopError("independent authority source entry is invalid")
    return dict(value)


def _finding(
    *,
    action: EvidenceAction,
    text: str,
    unresolved: str | None,
    resolved: list[str],
    grant: Mapping[str, Any],
) -> str | None:
    if unresolved is None:
        raise ClaimLoopError("source span has no closed decision catalog")
    folded = text.casefold()
    if grant.get("decision_bearing") is not True:
        raise ClaimLoopError("source span lacks a decision-bearing actor grant")
    if _instruction_bearing(text):
        raise ClaimLoopError("instruction-bearing source content is not evidence")
    if not _substantive(text):
        raise ClaimLoopError("source span is not substantively interpretable")
    if len(resolved) == 1 and _single_edge_intake_is_decisive(
        action.process_node_id, text
    ):
        return resolved[0]
    if any(_term_present(folded, term) for term in _UNCERTAINTY_TERMS):
        return unresolved
    if action.process_node_id.endswith("dh_intake") and sorted(resolved) == [
        "dh_e01",
        "dh_e02",
    ]:
        positive = any(_term_present(folded, term) for term in _POSITIVE_TERMS)
        negative = any(_term_present(folded, term) for term in _NEGATIVE_TERMS)
        negated_positive = any(
            re.search(pattern, folded, flags=re.IGNORECASE) is not None
            for pattern in _NEGATED_POSITIVE_PATTERNS
        )
        if negated_positive or positive == negative:
            raise ClaimLoopError(
                "health source span is ambiguous, negated, or contradictory"
            )
        if positive:
            return "dh_e01"
        if negative:
            return "dh_e02"
    if not action.process_node_id.endswith("_intake"):
        raise ClaimLoopError("source span is outside the intake decision grammar")
    raise ClaimLoopError("source span does not contain a decisive grammar token")


class IndependentWorkspaceEvidenceAuthorityV1:
    """A separately implemented verifier for the exact persisted proposal."""

    authority_id = _AUTHORITY_ID

    def __init__(self, adapter: Any, *, interpreter_source_sha256: str) -> None:
        if not is_sha256(interpreter_source_sha256):
            raise ValueError("interpreter source identity is invalid")
        self.adapter = adapter
        self.interpreter_source_sha256 = interpreter_source_sha256
        self._implementation_source_sha256 = _module_sha256()
        self._writer_capability = adapter.bind_independent_authority(
            authority_id=self.authority_id,
            authority_source_sha256=self._implementation_source_sha256,
        )

    @property
    def implementation_source_sha256(self) -> str:
        current = _module_sha256()
        if current != self._implementation_source_sha256:
            raise ClaimLoopError("independent authority source changed")
        return current

    @staticmethod
    def _catalog(
        *, state: ClaimLoopState, action: EvidenceAction
    ) -> tuple[dict[str, Any], str | None, list[str], dict[str, Any]]:
        policy = _admission(state)
        grant = policy["actor_grants"].get(action.evidence_item_id)
        fact = next((item for item in state.facts if item.get("fact_id") == action.fact_id), None)
        if (
            fact is None
            or not isinstance(grant, Mapping)
            or set(grant)
            != {
                "contract",
                "actor_type",
                "required_process_owner",
                "authority_scope",
                "decision_bearing",
            }
            or grant.get("contract") != "casepath.workspace-actor-grant/1.0.0"
            or grant.get("actor_type") != "claim_handler"
            or grant.get("required_process_owner")
            not in {"claim_handler", "external_specialist"}
            or grant.get("authority_scope")
            not in {"handler_attested_case_source", "specialist_only"}
            or not isinstance(grant.get("decision_bearing"), bool)
            or (
                grant.get("required_process_owner") == "claim_handler"
            )
            != (
                grant.get("authority_scope")
                == "handler_attested_case_source"
            )
            or (
                grant.get("required_process_owner") == "claim_handler"
            )
            != grant.get("decision_bearing")
        ):
            raise ClaimLoopError("independent authority actor grant is invalid")
        template = playbook_template_from_accepted_v1(state.accepted_artifacts)
        decision_key = fact.get("decision_key")
        options = template.decision_options.get(decision_key, {}) if decision_key else {}
        unresolved = template.fail_closed_normalized_values.get(decision_key) if decision_key else None
        if decision_key is not None and (not isinstance(options, Mapping) or unresolved not in options):
            raise ClaimLoopError("independent authority catalog is invalid")
        catalog = {
            "template_sha256": template.template_sha256,
            "decision_key": decision_key,
            "normalized_values": list(options),
            "unresolved_normalized_value": unresolved,
        }
        return catalog, unresolved, [item for item in options if item != unresolved], dict(grant)

    def _interpretation(
        self,
        *,
        state: ClaimLoopState,
        action: EvidenceAction,
        acquisition: AcquisitionReceiptV1,
        receipt: Any,
        entry: Mapping[str, Any],
        text: str,
        finding: str | None,
        unresolved: str | None,
        catalog: Mapping[str, Any],
    ) -> CanonicalFactInterpretationV1:
        prior_fact = next(item for item in state.facts if item.get("fact_id") == action.fact_id)
        resolved = finding is not None and finding != unresolved
        source_ref = ClaimSourceRef.model_validate(
            {
                "source_id": entry["artifact_id"],
                "source_sha256": entry["artifact_sha256"],
                "source_version": entry["source_version"],
                "locator_kind": "text_quote",
                "page": 1,
                "sanitized_excerpt": text,
                "text_start": entry["text_start"],
                "text_end": entry["text_end"],
                "field": None,
                "value": None,
                "span_sha256": entry["span_sha256"],
                "adapter_id": _ADAPTER_ID,
            }
        )
        observation_material = {
            "contract": "casepath.claim-observation/1.0.0",
            "observation_id": "observation."
            + digest_value(
                {
                    "acquisition_receipt_sha256": acquisition.receipt_sha256,
                    "source_entry_sha256": entry["source_entry_sha256"],
                    "action_sha256": action.action_sha256,
                }
            ),
            "fact_id": action.fact_id,
            "evidence_item_id": action.evidence_item_id,
            "value": text,
            "fact_state": "known" if resolved else "unknown",
            "normalized_value": finding if resolved and catalog["decision_key"] is not None else None,
            "explanation": (
                "A fixed-version server interpreter derived this bounded policy transition from an exact acquired source span."
                if resolved
                else "The fixed-version server interpreter abstained because this acquired source span does not resolve the current policy step."
            ),
            "evidence_status": "provided_sufficient" if resolved else "provided_insufficient",
            "source_refs": [source_ref.model_dump(mode="json")],
            "observed_at": acquisition.acquired_at,
        }
        observation = ClaimObservation.model_validate(
            {**observation_material, "observation_sha256": digest_value(observation_material)}
        )
        interpretation_material = {
            "contract": "casepath.canonical-fact-interpretation/1.2.0",
            "action_id": action.action_id,
            "action_sha256": action.action_sha256,
            "fact_id": action.fact_id,
            "evidence_item_id": action.evidence_item_id,
            "acquisition_receipt_sha256": acquisition.receipt_sha256,
            "raw_artifact_sha256": acquisition.receipt_sha256,
            "prior_fact_sha256": digest_value(prior_fact),
            "assertion_catalog_sha256": digest_value(dict(catalog)),
            "selected_assertion_id": (
                f"server-source-span.{action.evidence_item_id}.{finding}/1" if resolved else None
            ),
            "observation": observation.model_dump(mode="json"),
            "implementation": _INTERPRETER_ID,
            "implementation_source_sha256": self.interpreter_source_sha256,
            "model_calls": 0,
            "provider_calls": 0,
            "provider_credentials_read": False,
            "cost_usd": 0.0,
        }
        return CanonicalFactInterpretationV1.model_validate(
            {**interpretation_material, "receipt_sha256": digest_value(interpretation_material)}
        )

    def validate(
        self,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
        acquisition: AcquisitionReceiptV1,
        interpretation: CanonicalFactInterpretationV1,
    ) -> dict[str, Any]:
        try:
            proposal = self.adapter.proposal_for_acquisition(acquisition.receipt_sha256)
            receipt, raw = self.adapter.binding_for_acquisition(acquisition=acquisition)
            text = raw.decode("utf-8", errors="strict")
            policy = _admission(state)
            matches = [
                dict(item)
                for item in policy["source_entries"]
                if item.get("source_entry_sha256") == receipt.source_entry_sha256
            ]
            if len(matches) != 1:
                raise ClaimLoopError("independent authority source span is ambiguous")
            entry = matches[0]
            registration = self.adapter.staged(
                session_id=state.session_id,
                loop_id=state.loop_id,
                parent_revision=receipt.expected_revision,
                action_sha256=action.action_sha256,
            )
            intent = self.adapter.intent(receipt.acquisition_intent_id)
            if (
                entry.get("exact_text") != text
                or entry.get("artifact_id") != receipt.source_artifact_id
                or entry.get("artifact_sha256") != receipt.source_artifact_sha256
                or entry.get("text_start") != receipt.text_start
                or entry.get("text_end") != receipt.text_end
                or entry.get("byte_start") != receipt.byte_start
                or entry.get("byte_end") != receipt.byte_end
                or digest_text(text) != receipt.content_sha256
                or intent.receipt_sha256 != receipt.intent_receipt_sha256
                or registration is None
                or registration.receipt_sha256
                != proposal.get("registration_receipt_sha256")
                or registration.source_acquisition_receipt_sha256
                != receipt.receipt_sha256
            ):
                raise ClaimLoopError("independent authority receipt chain differs")
            catalog, unresolved, resolved, grant = self._catalog(state=state, action=action)
            finding = _finding(
                action=action,
                text=text,
                unresolved=unresolved,
                resolved=resolved,
                grant=grant,
            )
            expected = self._interpretation(
                state=state,
                action=action,
                acquisition=acquisition,
                receipt=receipt,
                entry=entry,
                text=text,
                finding=finding,
                unresolved=unresolved,
                catalog=catalog,
            )
            proposal_material = {
                "contract": "casepath.workspace-server-interpretation-proposal/1.0.0",
                "authoritative": False,
                "claim_id": state.claim_id,
                "loop_id": state.loop_id,
                "record_version": state.record_version,
                "parent_revision": receipt.expected_revision,
                "action_id": action.action_id,
                "action_sha256": action.action_sha256,
                "acquisition_intent_id": receipt.acquisition_intent_id,
                "acquisition_receipt_id": receipt.acquisition_receipt_id,
                "acquisition_receipt_sha256": acquisition.receipt_sha256,
                "registration_receipt_sha256": registration.receipt_sha256,
                "content_sha256": receipt.content_sha256,
                "content_length": receipt.content_length,
                "source_entry_sha256": entry["source_entry_sha256"],
                "source_artifact_sha256": entry["artifact_sha256"],
                "text_start": entry["text_start"],
                "text_end": entry["text_end"],
                "byte_start": entry["byte_start"],
                "byte_end": entry["byte_end"],
                "span_sha256": entry["span_sha256"],
                "interpreter_id": _INTERPRETER_ID,
                "interpreter_source_sha256": self.interpreter_source_sha256,
                "grammar_id": _GRAMMAR_ID,
                "grammar_sha256": digest_value(
                    {
                        "positive": list(_POSITIVE_TERMS),
                        "negative": list(_NEGATIVE_TERMS),
                        "uncertainty": list(_UNCERTAINTY_TERMS),
                        "lease_termination_intake": list(
                            _LEASE_TERMINATION_INTAKE_TERMS
                        ),
                        "rent_increase_intake": list(
                            _RENT_INCREASE_INTAKE_TERMS
                        ),
                    }
                ),
                "schema_id": _SCHEMA_ID,
                "schema_sha256": _SCHEMA_SHA256,
                "catalog_sha256": digest_value(catalog),
                "policy_sha256": policy["policy_sha256"],
                "actor_grant_sha256": digest_value(grant),
                "intent_receipt_sha256": receipt.intent_receipt_sha256,
                "source_acquisition_receipt_sha256": receipt.receipt_sha256,
                "freshness_nonce": receipt.freshness_nonce,
                "proposed_normalized_value": finding if finding != unresolved else None,
                "proposed_fact_state": expected.observation.fact_state,
                "proposed_evidence_status": expected.observation.evidence_status,
                "interpretation_receipt_sha256": expected.receipt_sha256,
            }
            expected_proposal = {
                **proposal_material,
                "proposal_sha256": digest_value(proposal_material),
            }
            if (
                proposal != expected_proposal
                or interpretation.model_dump(mode="json")
                != expected.model_dump(mode="json")
            ):
                raise ClaimLoopError("independent authority rejected the exact proposal")
            return self.adapter.record_admission(
                capability=self._writer_capability,
                proposal=proposal,
                interpretation_sha256=interpretation.receipt_sha256,
                authority_id=self.authority_id,
                authority_source_sha256=self.implementation_source_sha256,
            )
        except (KeyError, TypeError, UnicodeError, ValueError, ClaimLoopError) as exc:
            self.record_rejection(
                action=action, state=state, acquisition=acquisition, reason=str(exc)
            )
            raise ClaimLoopError(str(exc)) from exc

    def record_rejection(
        self,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
        acquisition: AcquisitionReceiptV1,
        reason: str,
    ) -> dict[str, Any]:
        return self.adapter.record_authority_rejection(
            capability=self._writer_capability,
            authority_id=self.authority_id,
            authority_source_sha256=self.implementation_source_sha256,
            action=action,
            state=state,
            acquisition=acquisition,
            reason=reason,
        )


__all__ = ["IndependentWorkspaceEvidenceAuthorityV1"]
