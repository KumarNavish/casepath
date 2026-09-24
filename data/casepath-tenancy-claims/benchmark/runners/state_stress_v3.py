"""Build and score the paired CasePath document-state stress track."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from contracts.expressions import evaluate_expression, referenced_names
from contracts.schema import (
    AcceptanceContract,
    ConceptKind,
    DocumentState,
    RequestMode,
)
from contracts.state_stress_v3 import (
    StateStressDocumentDecisionV3,
    StateStressExpectedV3,
    StateStressManifestRowV3,
    StateStressManifestV3,
    StateStressObservableUpdateV3,
    StateStressPredictionV3,
    StateStressPublicCaseV3,
    StateStressScoreV3,
    StressVariantV3,
)
from manifests.digests import canonical_json_bytes, digest_json


class StateStressError(RuntimeError):
    pass


@dataclass(frozen=True)
class StateStressFile:
    relative_path: str
    sha256: str
    size_bytes: int
    role: str


_VARIANTS: tuple[StressVariantV3, ...] = (
    "add_sufficient_artifact",
    "deactivate_requirement",
    "defer_conditional_requirement",
    "resolve_all_active_requirements",
)


def _write_json(path: Path, value: Any) -> tuple[str, int]:
    raw = canonical_json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _active(expression: str, scenario: dict[str, Any]) -> bool:
    return evaluate_expression(expression, scenario)


def _load_contract(public_root: Path, hidden_root: Path, case: Any) -> AcceptanceContract:
    if case.split == "public_dev":
        raw = json.loads((public_root / case.public_gold_path).read_text(encoding="utf-8"))
    else:
        raw = json.loads(
            (hidden_root / f"contracts/{case.case_id}.json").read_text(encoding="utf-8")
        )
    return AcceptanceContract.model_validate(raw["acceptance_contract"])


def _active_graph(
    contract: AcceptanceContract,
    scenario: dict[str, Any],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    concepts = tuple(
        sorted(
            concept.concept_id
            for concept in contract.concepts
            if _active(concept.active_when, scenario)
        )
    )
    relations = tuple(
        sorted(
            relation.relation_id
            for relation in contract.relations
            if _active(relation.active_when, scenario)
        )
    )
    terminals = tuple(
        sorted(
            concept.concept_id
            for concept in contract.concepts
            if concept.kind is ConceptKind.OUTCOME and _active(concept.active_when, scenario)
        )
    )
    if not terminals:
        raise StateStressError("state-stress base contract has no active terminal")
    return concepts, relations, terminals


def _document_labels(contract: AcceptanceContract) -> dict[str, str]:
    return {
        concept.concept_id: concept.label
        for concept in contract.concepts
        if concept.kind is ConceptKind.DOCUMENT
    }


def _active_obligations(contract: AcceptanceContract, scenario: dict[str, Any]) -> list[Any]:
    return [
        evidence
        for evidence in contract.evidence_contracts
        if _active(evidence.active_when, scenario)
    ]


def _base_states(
    contract: AcceptanceContract,
    scenario: dict[str, Any],
) -> tuple[dict[str, DocumentState], list[Any]]:
    active = _active_obligations(contract, scenario)
    states: dict[str, DocumentState] = {}
    for evidence in active:
        for document_id, state in evidence.expected_document_states.items():
            previous = states.get(document_id)
            if previous is not None and previous is not state:
                raise StateStressError("one active document has conflicting generator states")
            states[document_id] = state
    for document_id in _document_labels(contract):
        states.setdefault(document_id, DocumentState.IRRELEVANT)
    return states, active


def _branch_target(
    contract: AcceptanceContract,
    scenario: dict[str, Any],
) -> tuple[Any, str, tuple[str, ...]] | None:
    active = _active_obligations(contract, scenario)
    document_usage: dict[str, int] = defaultdict(int)
    for evidence in active:
        for document_id in evidence.expected_document_states:
            document_usage[document_id] += 1
    for evidence in active:
        variables = sorted(referenced_names(evidence.active_when))
        for variable in variables:
            if scenario.get(variable) is not True:
                continue
            changed = dict(scenario)
            changed[variable] = False
            if _active(evidence.active_when, changed):
                continue
            unique = tuple(
                sorted(
                    document_id
                    for document_id in evidence.expected_document_states
                    if document_usage[document_id] == 1
                )
            )
            if unique:
                return evidence, variable, unique
    return None


def _eligible_base(contract: AcceptanceContract) -> bool:
    states, active = _base_states(contract, dict(contract.scenario))
    requestable = {
        document_id
        for document_id, state in states.items()
        if state in {DocumentState.MISSING, DocumentState.PROVIDED_INSUFFICIENT}
    }
    return bool(active and requestable and _branch_target(contract, dict(contract.scenario)))


def _update(
    stress_case_id: str,
    kind: str,
    target_ids: Iterable[str],
    statement: str,
) -> StateStressObservableUpdateV3:
    payload = {
        "update_id": f"update.{stress_case_id.split('.', 1)[1]}",
        "update_kind": kind,
        "target_ids": tuple(sorted(target_ids)),
        "statement": statement,
    }
    payload["update_sha256"] = digest_json(payload)
    return StateStressObservableUpdateV3.model_validate(payload)


def _request_mode(state: DocumentState) -> RequestMode:
    if state in {DocumentState.MISSING, DocumentState.PROVIDED_INSUFFICIENT}:
        return RequestMode.NOW
    if state is DocumentState.CONDITIONAL:
        return RequestMode.CONDITIONAL
    return RequestMode.NONE


def _compile_variant(
    *,
    contract: AcceptanceContract,
    case: Any,
    variant: StressVariantV3,
) -> tuple[StateStressPublicCaseV3, StateStressExpectedV3]:
    seed = digest_json({"base_case_id": case.case_id, "variant": variant})
    stress_case_id = f"stress.{seed[:24]}"
    scenario = dict(contract.scenario)
    base_states, active = _base_states(contract, scenario)
    branch = _branch_target(contract, scenario)
    if branch is None:
        raise StateStressError("selected state-stress base has no deactivatable requirement")
    target_obligation, branch_variable, branch_documents = branch
    labels = _document_labels(contract)
    target_document = next(
        document_id
        for document_id in branch_documents
        if base_states[document_id] in {DocumentState.MISSING, DocumentState.PROVIDED_INSUFFICIENT}
    )
    expected_states = dict(base_states)
    variant_scenario = dict(scenario)
    support_by_document: dict[str, tuple[str, ...]] = defaultdict(tuple)
    if variant == "add_sufficient_artifact":
        update = _update(
            stress_case_id,
            "sufficient_artifact",
            (target_document,),
            f"A complete, legible, and sufficient {labels[target_document]} is now attached.",
        )
        expected_states[target_document] = DocumentState.PROVIDED_SUFFICIENT
        support_by_document[target_document] = (update.update_id,)
    elif variant == "deactivate_requirement":
        update = _update(
            stress_case_id,
            "branch_fact_false",
            (branch_variable, *branch_documents),
            f"The observable claim now establishes that {branch_variable} is false.",
        )
        variant_scenario[branch_variable] = False
        remaining = _active_obligations(contract, variant_scenario)
        remaining_documents = {
            document_id
            for evidence in remaining
            for document_id in evidence.expected_document_states
        }
        for document_id in branch_documents:
            if document_id not in remaining_documents:
                expected_states[document_id] = DocumentState.IRRELEVANT
                support_by_document[document_id] = (update.update_id,)
    elif variant == "defer_conditional_requirement":
        update = _update(
            stress_case_id,
            "branch_fact_unresolved",
            (branch_variable, *branch_documents),
            (
                f"Whether {branch_variable} applies is explicitly unresolved; related evidence "
                "must be deferred until that branch is established."
            ),
        )
        for document_id in branch_documents:
            expected_states[document_id] = DocumentState.CONDITIONAL
            support_by_document[document_id] = (update.update_id,)
    else:
        active_documents = tuple(
            sorted(
                document_id
                for evidence in active
                for document_id in evidence.expected_document_states
            )
        )
        update = _update(
            stress_case_id,
            "all_active_facts_resolved",
            active_documents,
            (
                "Complete and sufficient source artifacts now establish every currently active "
                "fact; no document request remains necessary."
            ),
        )
        for document_id in active_documents:
            expected_states[document_id] = DocumentState.PROVIDED_SUFFICIENT
            support_by_document[document_id] = (update.update_id,)

    base_concepts, base_relations, _ = _active_graph(contract, scenario)
    concepts, relations, terminals = _active_graph(contract, variant_scenario)
    decisions = tuple(
        StateStressDocumentDecisionV3(
            document_id=document_id,
            state=state,
            request_mode=_request_mode(state),
            support_update_ids=support_by_document[document_id],
        )
        for document_id, state in sorted(expected_states.items())
    )
    public_payload: dict[str, Any] = {
        "contract": "casepath.state-stress-public-case/3.0.0",
        "stress_case_id": stress_case_id,
        "base_case_id": case.case_id,
        "domain": case.domain,
        "family_id": case.family_id,
        "split": case.split,
        "variant": variant,
        "base_observable_claim_path": case.observable_claim_path,
        "base_source_registry_path": case.source_registry_path,
        "observable_updates": (update.model_dump(mode="json"),),
    }
    public_payload["public_input_sha256"] = digest_json(public_payload)
    expected_payload: dict[str, Any] = {
        "contract": "casepath.state-stress-expected/3.0.0",
        "stress_case_id": stress_case_id,
        "base_case_id": case.case_id,
        "variant": variant,
        "document_decisions": tuple(item.model_dump(mode="json") for item in decisions),
        "active_concept_ids": concepts,
        "active_relation_ids": relations,
        "terminal_outcome_ids": terminals,
        "unaffected_concept_ids": tuple(sorted(set(base_concepts).intersection(concepts))),
        "unaffected_relation_ids": tuple(sorted(set(base_relations).intersection(relations))),
    }
    expected_payload["expected_sha256"] = digest_json(expected_payload)
    return (
        StateStressPublicCaseV3.model_validate(public_payload),
        StateStressExpectedV3.model_validate(expected_payload),
    )


def build_state_stress_track_v3(
    *,
    public_root: Path,
    hidden_root: Path,
    cases: Iterable[Any],
) -> tuple[StateStressManifestV3, tuple[StateStressFile, ...]]:
    """Freeze 12 paired bases and 48 objective state-transition variants."""

    grouped: dict[tuple[str, str], dict[str, list[Any]]] = defaultdict(lambda: defaultdict(list))
    contracts: dict[str, AcceptanceContract] = {}
    for case in cases:
        grouped[(case.split, case.domain)][case.family_id].append(case)
        contracts[case.case_id] = _load_contract(public_root, hidden_root, case)
    selected: list[Any] = []
    for split in ("public_dev", "hidden_test"):
        for domain in sorted({case.domain for case in cases}):
            eligible_families: list[Any] = []
            for family_id in sorted(grouped[(split, domain)]):
                members = sorted(grouped[(split, domain)][family_id], key=lambda item: item.case_id)
                member = next(
                    (item for item in members if _eligible_base(contracts[item.case_id])),
                    None,
                )
                if member is not None:
                    eligible_families.append(member)
            if len(eligible_families) < 2:
                raise StateStressError(
                    f"not enough eligible state-stress families for {split}/{domain}"
                )
            selected.extend(eligible_families[:2])
    if len(selected) != 12:
        raise StateStressError("state-stress base roster is not exactly twelve")

    files: list[StateStressFile] = []
    rows: list[StateStressManifestRowV3] = []
    for case in selected:
        for variant in _VARIANTS:
            public_case, expected = _compile_variant(
                contract=contracts[case.case_id],
                case=case,
                variant=variant,
            )
            reference_prediction = StateStressPredictionV3(
                contract="casepath.state-stress-prediction/3.0.0",
                stress_case_id=expected.stress_case_id,
                document_decisions=expected.document_decisions,
                active_concept_ids=expected.active_concept_ids,
                active_relation_ids=expected.active_relation_ids,
                terminal_outcome_ids=expected.terminal_outcome_ids,
            )
            reference_score = score_state_stress_v3(expected, reference_prediction)
            score_values = reference_score.model_dump(
                mode="json", exclude={"contract", "stress_case_id", "score_sha256"}
            )
            if any(
                value != (0.0 if key == "unnecessary_request_rate" else 1.0)
                for key, value in score_values.items()
            ):
                raise StateStressError("state-stress reference prediction does not score exactly")
            zone = "dev" if case.split == "public_dev" else "test"
            public_path = f"state-stress/data/{zone}/{public_case.stress_case_id}.json"
            public_sha, public_size = _write_json(
                public_root / public_path,
                public_case.model_dump(mode="json"),
            )
            files.append(StateStressFile(public_path, public_sha, public_size, "stress_input"))
            if case.split == "public_dev":
                gold_path = f"state-stress/gold/{public_case.stress_case_id}.json"
                gold_sha, gold_size = _write_json(
                    public_root / gold_path,
                    expected.model_dump(mode="json"),
                )
                files.append(StateStressFile(gold_path, gold_sha, gold_size, "stress_dev_gold"))
                hidden_commitment = None
            else:
                gold_path = None
                hidden_path = hidden_root / f"state-stress/{public_case.stress_case_id}.json"
                hidden_commitment, _ = _write_json(
                    hidden_path,
                    expected.model_dump(mode="json"),
                )
            row_payload: dict[str, Any] = {
                "stress_case_id": public_case.stress_case_id,
                "base_case_id": case.case_id,
                "domain": case.domain,
                "family_id": case.family_id,
                "split": case.split,
                "variant": variant,
                "public_case_path": public_path,
                "public_case_sha256": public_sha,
                "public_gold_path": gold_path,
                "hidden_expected_commitment_sha256": hidden_commitment,
            }
            row_payload["row_sha256"] = digest_json(row_payload)
            rows.append(StateStressManifestRowV3.model_validate(row_payload))
    manifest_payload: dict[str, Any] = {
        "contract": "casepath.state-stress-manifest/3.0.0",
        "benchmark_id": "casepath-state-stress-v3",
        "construction": (
            "deterministic_paired_generator_state_transitions_no_model_or_expert_calls"
        ),
        "base_case_count": 12,
        "variant_count": 48,
        "public_dev_variant_count": 24,
        "hidden_test_variant_count": 24,
        "variants": tuple(row.model_dump(mode="json") for row in rows),
        "endpoint_ids": (
            "state_transition_accuracy",
            "request_mode_accuracy",
            "immediate_request_set_exact",
            "conditional_request_set_exact",
            "empty_request_stopping_accuracy",
            "active_graph_accuracy",
            "unaffected_graph_invariance",
            "observable_update_support_accuracy",
            "unnecessary_request_rate",
        ),
        "runtime_model_calls": 0,
        "experts_required": False,
    }
    manifest_payload["manifest_sha256"] = digest_json(manifest_payload)
    manifest = StateStressManifestV3.model_validate(manifest_payload)
    manifest_path = "state-stress/manifest.json"
    manifest_sha, manifest_size = _write_json(
        public_root / manifest_path,
        manifest.model_dump(mode="json"),
    )
    files.append(StateStressFile(manifest_path, manifest_sha, manifest_size, "stress_manifest"))
    return manifest, tuple(files)


def _set_accuracy(expected: set[Any], observed: set[Any]) -> float:
    if not expected and not observed:
        return 1.0
    return len(expected.intersection(observed)) / len(expected.union(observed))


def score_state_stress_v3(
    expected: StateStressExpectedV3,
    prediction: StateStressPredictionV3,
) -> StateStressScoreV3:
    if prediction.stress_case_id != expected.stress_case_id:
        raise StateStressError("state-stress prediction belongs to another case")
    expected_docs = {item.document_id: item for item in expected.document_decisions}
    predicted_docs = {item.document_id: item for item in prediction.document_decisions}
    denominator = len(expected_docs)
    state_hits = sum(
        predicted_docs.get(document_id) is not None
        and predicted_docs[document_id].state is decision.state
        for document_id, decision in expected_docs.items()
    )
    request_hits = sum(
        predicted_docs.get(document_id) is not None
        and predicted_docs[document_id].request_mode is decision.request_mode
        for document_id, decision in expected_docs.items()
    )
    expected_now = {
        document_id
        for document_id, item in expected_docs.items()
        if item.request_mode is RequestMode.NOW
    }
    predicted_now = {
        document_id
        for document_id, item in predicted_docs.items()
        if item.request_mode is RequestMode.NOW
    }
    expected_conditional = {
        document_id
        for document_id, item in expected_docs.items()
        if item.request_mode is RequestMode.CONDITIONAL
    }
    predicted_conditional = {
        document_id
        for document_id, item in predicted_docs.items()
        if item.request_mode is RequestMode.CONDITIONAL
    }
    expected_support = {
        (document_id, update_id)
        for document_id, item in expected_docs.items()
        for update_id in item.support_update_ids
    }
    predicted_support = {
        (document_id, update_id)
        for document_id, item in predicted_docs.items()
        for update_id in item.support_update_ids
    }
    requested = predicted_now | predicted_conditional
    necessary = expected_now | expected_conditional
    unnecessary = requested - necessary
    expected_graph = set(expected.active_concept_ids) | set(expected.active_relation_ids)
    predicted_graph = set(prediction.active_concept_ids) | set(prediction.active_relation_ids)
    unaffected = set(expected.unaffected_concept_ids) | set(expected.unaffected_relation_ids)
    payload: dict[str, Any] = {
        "contract": "casepath.state-stress-score/3.0.0",
        "stress_case_id": expected.stress_case_id,
        "state_transition_accuracy": state_hits / denominator,
        "request_mode_accuracy": request_hits / denominator,
        "immediate_request_set_exact": float(predicted_now == expected_now),
        "conditional_request_set_exact": float(predicted_conditional == expected_conditional),
        "empty_request_stopping_accuracy": (float(not requested) if not necessary else 1.0),
        "active_graph_accuracy": _set_accuracy(expected_graph, predicted_graph),
        "unaffected_graph_invariance": (
            len(unaffected.intersection(predicted_graph)) / len(unaffected) if unaffected else 1.0
        ),
        "observable_update_support_accuracy": _set_accuracy(
            expected_support,
            predicted_support,
        ),
        "unnecessary_request_rate": len(unnecessary) / len(requested) if requested else 0.0,
    }
    payload["score_sha256"] = digest_json(payload)
    return StateStressScoreV3.model_validate(payload)


def _strict_json(raw: str, *, label: str) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise StateStressError(f"{label} contains duplicate key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise StateStressError(f"{label} contains non-finite constant {value}")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=reject_constant)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise StateStressError(f"{label} is not strict JSON") from exc


def load_state_stress_submission_v3(
    path: Path,
    *,
    expected_case_ids: set[str],
) -> dict[str, StateStressPredictionV3]:
    if path.stat().st_size > 32 * 1024 * 1024:
        raise StateStressError("state-stress submission exceeds 32 MiB")
    predictions: dict[str, StateStressPredictionV3] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if len(line.encode("utf-8")) > 512 * 1024:
                raise StateStressError(f"state-stress submission line {line_number} is too large")
            if not line.strip():
                continue
            raw = _strict_json(line, label=f"state-stress submission line {line_number}")
            if not isinstance(raw, dict) or set(raw) != {"stress_case_id", "prediction"}:
                raise StateStressError("state-stress submission row envelope differs")
            case_id = raw["stress_case_id"]
            if not isinstance(case_id, str) or case_id in predictions:
                raise StateStressError("state-stress submission case ID is invalid or repeated")
            prediction = StateStressPredictionV3.model_validate(raw["prediction"])
            if prediction.stress_case_id != case_id:
                raise StateStressError("state-stress prediction ID differs from its row")
            predictions[case_id] = prediction
    if set(predictions) != expected_case_ids:
        missing = sorted(expected_case_ids - set(predictions))
        extra = sorted(set(predictions) - expected_case_ids)
        raise StateStressError(
            f"state-stress submission roster differs: missing={missing[:3]}, extra={extra[:3]}"
        )
    return predictions


def build_state_stress_missing_floor_v3(root: Path) -> tuple[StateStressPredictionV3, ...]:
    manifest = StateStressManifestV3.model_validate_json(
        (root / "state-stress/manifest.json").read_bytes()
    )
    predictions: list[StateStressPredictionV3] = []
    for row in manifest.variants:
        if row.split != "public_dev":
            continue
        public_case = StateStressPublicCaseV3.model_validate_json(
            (root / row.public_case_path).read_bytes()
        )
        registry = _strict_json(
            (root / public_case.base_source_registry_path).read_text(encoding="utf-8"),
            label=f"source registry {public_case.base_case_id}",
        )
        document_ids = sorted(
            {
                item["proposition_id"]
                for item in registry.get("entries", [])
                if isinstance(item, dict)
                and item.get("proposition_kind") == "document"
                and isinstance(item.get("proposition_id"), str)
            }
        )
        predictions.append(
            StateStressPredictionV3(
                contract="casepath.state-stress-prediction/3.0.0",
                stress_case_id=row.stress_case_id,
                document_decisions=tuple(
                    StateStressDocumentDecisionV3(
                        document_id=document_id,
                        state=DocumentState.MISSING,
                        request_mode=RequestMode.NOW,
                    )
                    for document_id in document_ids
                ),
                active_concept_ids=(),
                active_relation_ids=(),
                terminal_outcome_ids=(),
            )
        )
    if len(predictions) != 24:
        raise StateStressError("state-stress dev floor did not cover 24 variants")
    return tuple(predictions)


def score_state_stress_dev_v3(root: Path, submission_path: Path) -> dict[str, Any]:
    manifest = StateStressManifestV3.model_validate_json(
        (root / "state-stress/manifest.json").read_bytes()
    )
    dev_rows = tuple(item for item in manifest.variants if item.split == "public_dev")
    predictions = load_state_stress_submission_v3(
        submission_path,
        expected_case_ids={item.stress_case_id for item in dev_rows},
    )
    scores: list[tuple[Any, StateStressScoreV3]] = []
    for row in dev_rows:
        assert row.public_gold_path is not None
        expected = StateStressExpectedV3.model_validate_json(
            (root / row.public_gold_path).read_bytes()
        )
        scores.append((row, score_state_stress_v3(expected, predictions[row.stress_case_id])))
    endpoint_ids = manifest.endpoint_ids

    def summary(rows: list[StateStressScoreV3]) -> dict[str, float]:
        return {
            endpoint: statistics.fmean(float(getattr(score, endpoint)) for score in rows)
            for endpoint in endpoint_ids
        }

    overall = summary([score for _, score in scores])
    by_variant = {
        variant: summary([score for row, score in scores if row.variant == variant])
        for variant in _VARIANTS
    }
    by_domain = {
        domain: summary([score for row, score in scores if row.domain == domain])
        for domain in sorted({row.domain for row, _ in scores})
    }
    result: dict[str, Any] = {
        "contract": "casepath.state-stress-dev-score/3.0.0",
        "state_stress_manifest_sha256": manifest.manifest_sha256,
        "case_count": len(scores),
        "overall": overall,
        "by_variant": by_variant,
        "by_domain": by_domain,
        "row_score_set_sha256": digest_json(
            [
                score.score_sha256
                for _, score in sorted(scores, key=lambda item: item[0].stress_case_id)
            ]
        ),
    }
    if any(
        not math.isfinite(value)
        for section in (overall, *by_variant.values(), *by_domain.values())
        for value in section.values()
    ):
        raise StateStressError("state-stress aggregate contains a non-finite value")
    result["score_sha256"] = digest_json(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    subcommands = parser.add_subparsers(dest="command", required=True)
    floor = subcommands.add_parser("baseline-dev")
    floor.add_argument("--output", type=Path, required=True)
    score = subcommands.add_parser("score-dev")
    score.add_argument("--submission", type=Path, required=True)
    score.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "baseline-dev":
            predictions = build_state_stress_missing_floor_v3(args.root)
            raw = b"".join(
                canonical_json_bytes(
                    {
                        "stress_case_id": prediction.stress_case_id,
                        "prediction": prediction.model_dump(mode="json"),
                    }
                )
                + b"\n"
                for prediction in predictions
            )
            args.output.write_bytes(raw)
        else:
            result = score_state_stress_dev_v3(args.root, args.submission)
            args.output.write_bytes(canonical_json_bytes(result) + b"\n")
        return 0
    except (OSError, ValueError, StateStressError) as exc:
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
