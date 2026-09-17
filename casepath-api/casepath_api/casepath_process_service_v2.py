"""Product surface for the exact two-level paper method.

The service delegates inference and planning to the same method modules used by the
experiments. Its only additional work is fail-closed source resolution and product-safe
serialization of the resulting chains and next action.
"""
from __future__ import annotations

import copy
from typing import Any, Callable, Mapping, Sequence

from . import evidence_overlay_v2 as planner

CONTRACT = "casepath.process-service/2.0.0"
METHOD_MODULES = (
    "casepath.process-induction/3.0.0",
    "casepath.evidence-refinement/2.0.0",
    "casepath.evidence-document-mapper/2.0.0",
    "casepath.case-interpreter/3.0.0",
    "casepath.evidence-overlay/2.0.0",
)


def _indices(propositions: Sequence[Mapping[str, Any]],
             passages: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Mapping[str, Any]],
                                                              dict[str, Mapping[str, Any]]]:
    proposition_index = {p["proposition_id"]: p for p in propositions}
    passage_index = {p["authority_id"]: p for p in passages}
    return proposition_index, passage_index


def _source_records(proposition_ids: Sequence[str],
                    proposition_index: Mapping[str, Mapping[str, Any]],
                    passage_index: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for proposition_id in proposition_ids:
        proposition = proposition_index.get(proposition_id)
        if proposition is None:
            raise ValueError(f"unknown source proposition {proposition_id!r}")
        authority_id = proposition.get("source_id")
        passage = passage_index.get(authority_id)
        if passage is None:
            raise ValueError(f"unknown authority passage {authority_id!r}")
        quote = (proposition.get("quote") or "").strip()
        exact_text = passage.get("exact_text") or ""
        if not quote or quote not in exact_text:
            raise ValueError(f"source quote does not resolve exactly for {proposition_id!r}")
        records.append({
            "proposition_id": proposition_id,
            "authority_id": authority_id,
            "article": passage.get("article"),
            "quote": quote,
            "exact_text": exact_text,
            "source_url": passage.get("source_url"),
            "source_urls": passage.get("source_urls") or [],
            "text_sha256": passage.get("text_sha256"),
        })
    return records


def _enrich_requests(requests: Sequence[Mapping[str, Any]],
                     propositions: Sequence[Mapping[str, Any]],
                     passages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    proposition_index, passage_index = _indices(propositions, passages)
    enriched = []
    for request in requests:
        record = copy.deepcopy(dict(request))
        justifications = []
        for justification in request.get("justified_by") or []:
            item = copy.deepcopy(dict(justification))
            proposition_ids = list(item.get("authorities") or [])
            item["sources"] = _source_records(
                proposition_ids, proposition_index, passage_index)
            justifications.append(item)
        record["justified_by"] = justifications
        enriched.append(record)
    return enriched


def _validate_requests(requests: Sequence[Mapping[str, Any]]) -> None:
    for index, request in enumerate(requests):
        if not request.get("still_missing"):
            raise ValueError(f"request {index} has no missing document")
        justifications = list(request.get("justified_by") or [])
        if not justifications:
            raise ValueError(f"request {index} is an orphan")
        for justification in justifications:
            if not justification.get("process_node"):
                raise ValueError(f"request {index} lacks a process-node anchor")
            if not justification.get("fact") or not justification.get("must_show"):
                raise ValueError(f"request {index} lacks fact/evidence semantics")
            if not justification.get("guard_id") and justification.get("purpose") == "resolve_process_state":
                raise ValueError(f"request {index} lacks an applicability guard")
            sources = list(justification.get("sources") or [])
            if not sources:
                raise ValueError(f"request {index} lacks resolved primary-source support")
            for source in sources:
                if not source.get("proposition_id") or not source.get("authority_id"):
                    raise ValueError(f"request {index} has incomplete source identity")
                quote = source.get("quote") or ""
                exact_text = source.get("exact_text") or ""
                if not quote or quote not in exact_text:
                    raise ValueError(f"request {index} has an invalid source span")


def _replace_next_action_request(next_action: Mapping[str, Any] | None,
                                 requests: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    if next_action is None:
        return None
    value = copy.deepcopy(dict(next_action))
    raw_request = value.get("request") or {}
    key = tuple(raw_request.get("document_types") or [])
    replacement = next((request for request in requests
                        if tuple(request.get("document_types") or []) == key), None)
    if replacement is None:
        raise ValueError("next action references a request absent from the validated checklist")
    value["request"] = copy.deepcopy(dict(replacement))
    return value


def plan_claim(*, prepared: Mapping[str, Any], propositions: Sequence[Mapping[str, Any]],
               passages: Sequence[Mapping[str, Any]], case: Mapping[str, str],
               already_held: Sequence[str], call: Callable[[str, str], str],
               workers: int = 12) -> dict[str, Any]:
    result = planner.plan_case(
        case=case, prepared=prepared, held=already_held, call=call, workers=workers)
    requests = _enrich_requests(result["requests"], propositions, passages)
    _validate_requests(requests)
    next_action = _replace_next_action_request(result.get("next_action"), requests)
    return {
        "contract": CONTRACT,
        "paper_method_modules": METHOD_MODULES,
        "prepared_contract": prepared.get("contract"),
        "requests": requests,
        "documents": result["documents"],
        "next_action": next_action,
        "guard_verdicts": result["guard_verdicts"],
        "ungrounded_guard_events": result["ungrounded"],
        "active_requirement_chains": result["active_requirement_chains"],
        "state_resolver_chains": result["resolver_chains"],
        "evidence_gaps": result["evidence_gaps"],
        "counts": result["counts"],
    }


def _documents(plan: Mapping[str, Any]) -> set[str]:
    return set(plan.get("documents") or [])


def _request_index(plan: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for request in plan.get("requests") or []:
        for document in request.get("still_missing") or []:
            index.setdefault(document, []).extend(request.get("justified_by") or [])
    return index


def diff_plans(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    before_docs, after_docs = _documents(before), _documents(after)
    before_index, after_index = _request_index(before), _request_index(after)
    before_verdicts = before.get("guard_verdicts") or {}
    after_verdicts = after.get("guard_verdicts") or {}
    changed_guards = [{
        "guard_id": guard_id,
        "from": before_verdicts.get(guard_id, {}).get("verdict"),
        "to": after_verdicts.get(guard_id, {}).get("verdict"),
    } for guard_id in sorted(set(before_verdicts) | set(after_verdicts))
       if before_verdicts.get(guard_id, {}).get("verdict") != after_verdicts.get(guard_id, {}).get("verdict")]
    changed_ids = {item["guard_id"] for item in changed_guards}

    def explain(documents: set[str], index: Mapping[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        rows = []
        for document in sorted(documents):
            justifications = list(index.get(document) or [])
            rows.append({
                "document": document,
                "justifications": justifications,
                "attributed_to_changed_guard": any(
                    justification.get("guard_id") in changed_ids
                    for justification in justifications),
            })
        return rows

    return {
        "contract": "casepath.process-service-diff/2.0.0",
        "added": explain(after_docs - before_docs, after_index),
        "withdrawn": explain(before_docs - after_docs, before_index),
        "unchanged": sorted(before_docs & after_docs),
        "changed_guards": changed_guards,
        "next_action_before": before.get("next_action"),
        "next_action_after": after.get("next_action"),
    }
