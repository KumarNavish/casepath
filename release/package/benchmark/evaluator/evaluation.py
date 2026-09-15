# Arena v1 evaluator: derived from the frozen E76 evaluation.py (2026-09-12) with activation rules,
# unavailable artifacts, and mechanism metrics added. Provenance: see arena_v1/PROVENANCE.md.
"""Deterministic environment and scorer for EVALUATION_DRAFT.json.

Stdlib only. This module performs no model, provider, network, or product calls.
The pinned JSON is the sole case/reference definition.
"""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
from collections import defaultdict
from pathlib import Path


EXPECTED_DRAFT_SHA256 = "f12b925825ff9e6b3a1c1a94a5f9f83c7d20fd854414dda30232f0077a441435"
VALID_STATES = {"missing", "insufficient", "received", "pending", "not_required"}
VALID_ACTIONS = {"request", "wait", "proceed", "clarify"}
SCORE_KEYS = (
    "critical_evidence_recall",
    "unnecessary_document_rate",
    "checklist_accuracy",
    "checklist_precision",
    "checklist_recall",
    "state_accuracy",
    "next_action_accuracy",
    "next_action_jaccard",
    "replanning_accuracy",
    "readiness_accuracy",
    "exact_provenance",
    "acquired_critical_evidence",
)
COUNT_KEYS = (
    "premature_readiness",
    "missed_readiness",
    "hearsay_receipts",
    "total_document_requests",
    "unique_document_requests",
    "unnecessary_unique_requests",
    "repeat_requests",
    "clarification_actions",
    "burden_primary",
)


def load_cases(path):
    """Load and validate an arena case file ({"cases": [...]}) or a single case object."""
    source = Path(path)
    spec = json.loads(source.read_bytes())
    cases = spec.get("cases") if isinstance(spec, dict) and "cases" in spec else [spec]
    if not isinstance(cases, list) or not cases:
        raise ValueError("expected a non-empty case list")
    for case in cases:
        _validate_case(case)
    return copy.deepcopy(cases)


def _validate_case(case):
    catalog = case["actor_initial"]["document_catalog"]
    doc_ids = [item["document_id"] for item in catalog]
    if len(doc_ids) != len(set(doc_ids)):
        raise ValueError(f"duplicate catalog ID in {case.get('case_id')}")
    sources = case["actor_initial"]["sources"] + case["source_store"]
    source_ids = [source["id"] for source in sources]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError(f"duplicate source ID in {case.get('case_id')}")
    paragraphs = {}
    for source in sources:
        for paragraph in source["paragraphs"]:
            ref = f"{source['id']}#{paragraph['id']}"
            if ref in paragraphs:
                raise ValueError(f"duplicate paragraph ref {ref}")
            paragraphs[ref] = paragraph["text"]
    for requirement in case["reference_requirements"]:
        for support in requirement["exact_support"]:
            if paragraphs.get(support["source_ref"]) != support["exact_sentence"]:
                raise ValueError(f"non-exact support in {case['case_id']}")
        for option in requirement["satisfying_document_sets"]:
            if not option or not set(option) <= set(doc_ids):
                raise ValueError(f"bad satisfying set in {case['case_id']}")
    if not set(case["accepted_justification_refs"]) == set(doc_ids):
        raise ValueError(f"missing justification map in {case['case_id']}")
    intake = case.get("intake_source_documents", {})
    initial_ids = {s["id"]: s for s in case["actor_initial"]["sources"]}
    for source_id, document_id in intake.items():
        if source_id not in initial_ids or initial_ids[source_id].get("provided_document_id") != document_id:
            raise ValueError(f"intake attachment {source_id} is not an initial source bound to {document_id}")


def initial_state(case):
    """Return a fresh action-conditioned state at decision turn zero."""
    return {
        "case_id": case["case_id"],
        "turn": 0,
        "visible_source_ids": [s["id"] for s in case["actor_initial"]["sources"]],
        "source_documents": dict(case.get("intake_source_documents", {})),
        "deliveries": [],
        "request_history": [],
        "scheduled": [],
        "followups": {},
        "repeat_burden_count": 0,
    }


def actor_input(case, state, own_prior=None):
    """Materialize actor-visible data without evaluator status or relevance labels."""
    _check_state(case, state)
    source_map = _source_map(case)
    visible = []
    for source_id in state["visible_source_ids"]:
        source = copy.deepcopy(source_map[source_id])
        document_id = state["source_documents"].get(source_id)
        if document_id is not None:
            source["provided_document_id"] = document_id
        visible.append(source)
    payload = {
        "aware_at": case["aware_at"],
        "turn": state["turn"],
        "sources": visible,
        "document_catalog": copy.deepcopy(case["actor_initial"]["document_catalog"]),
        "static_category_checklist": copy.deepcopy(
            case["actor_initial"]["static_category_checklist"]
        ),
    }
    if own_prior is not None:
        payload["own_prior"] = copy.deepcopy(own_prior)
    return payload


def advance(case, state, requested_ids):
    """Advance one turn using only requests and previously committed follow-ups."""
    _check_state(case, state)
    if state["turn"] >= 2:
        raise ValueError("turn 2 is terminal")
    catalog_ids = _catalog_ids(case)
    if not isinstance(requested_ids, (list, tuple)):
        raise ValueError("requested_ids must be a list or tuple")
    requested = list(requested_ids)
    if len(requested) > 2 or len(requested) != len(set(requested)):
        raise ValueError("at most two distinct requests are allowed")
    if not set(requested) <= set(catalog_ids):
        raise ValueError("request contains an unknown document ID")

    updated = copy.deepcopy(state)
    old_turn = state["turn"]
    new_turn = old_turn + 1
    receipt = {
        "case_id": case["case_id"],
        "from_turn": old_turn,
        "to_turn": new_turn,
        "requested_document_ids": requested,
        "request_events": [],
        "delivered_sources": [],
    }
    prior_ids = [event["document_id"] for event in updated["request_history"]]
    rows = {row["document_id"]: row for row in case["action_response_table"]}

    for document_id in requested:
        repeated = document_id in prior_ids
        event = {"turn": old_turn, "document_id": document_id}
        if repeated and document_id in updated["followups"]:
            followup = updated["followups"].pop(document_id)
            if followup.get("deliver_at_turn") == new_turn:
                _deliver(updated, receipt, document_id, followup["source_ids"], "follow_up")
                event["outcome"] = "follow_up_delivered"
            else:
                event["outcome"] = "follow_up_not_due"
        elif repeated:
            event["outcome"] = "repeat_no_new_commitment"
            updated["repeat_burden_count"] += 1
        else:
            event["outcome"] = _commit_first_request(
                rows[document_id], document_id, old_turn, new_turn, updated, receipt
            )
        updated["request_history"].append(event)
        receipt["request_events"].append(copy.deepcopy(event))

    due = [item for item in updated["scheduled"] if item["deliver_at_turn"] == new_turn]
    updated["scheduled"] = [
        item for item in updated["scheduled"] if item["deliver_at_turn"] != new_turn
    ]
    for item in due:
        _deliver(updated, receipt, item["document_id"], item["source_ids"], "automatic")
    updated["turn"] = new_turn
    receipt["automatic_followups_remaining"] = copy.deepcopy(updated["scheduled"])
    return updated, receipt


def _commit_first_request(row, document_id, old_turn, new_turn, state, receipt):
    keyed = row.get(f"if_first_requested_at_turn_{old_turn}")
    if keyed is not None:
        delivered = False
        committed = False
        for response in keyed:
            target = response["deliver_at_turn"]
            item = {
                "document_id": document_id,
                "deliver_at_turn": target,
                "source_ids": list(response["source_ids"]),
            }
            if target == new_turn:
                _deliver(state, receipt, document_id, item["source_ids"], "request")
                delivered = True
            elif response.get("automatic_after_partial"):
                state["scheduled"].append(item)
                committed = True
            elif response.get("requires_follow_up_request_at_turn_1"):
                state["followups"][document_id] = item
                committed = True
        if delivered and committed:
            return "partial_delivered_followup_committed"
        if delivered:
            return "delivered"
        return "committed" if committed else "no_response"
    source_ids = row.get("response_source_ids")
    earliest = row.get("earliest_turn_available")
    if source_ids and earliest is not None:
        target = max(new_turn, earliest)
        if target == new_turn:
            _deliver(state, receipt, document_id, source_ids, "request")
        elif target <= 2:
            state["scheduled"].append(
                {"document_id": document_id, "deliver_at_turn": target, "source_ids": source_ids}
            )
        return "delivered" if target == new_turn else "committed"
    return "no_response"


def _deliver(state, receipt, document_id, source_ids, delivery_kind):
    for source_id in source_ids:
        if source_id in state["visible_source_ids"]:
            continue
        state["visible_source_ids"].append(source_id)
        state["source_documents"][source_id] = document_id
        delivery = {
            "turn": receipt["to_turn"],
            "source_id": source_id,
            "provided_document_id": document_id,
            "delivery_kind": delivery_kind,
        }
        state["deliveries"].append(delivery)
        receipt["delivered_sources"].append(copy.deepcopy(delivery))


def reference(case, state):
    """Compute the independent reference only from actor-visible source IDs."""
    _check_state(case, state)
    catalog_ids = _catalog_ids(case)
    effects = _source_effects(case)
    visible = set(state["visible_source_ids"])
    observed = defaultdict(list)
    for source_id in visible:
        if source_id in effects:
            document_id, scope = effects[source_id]
            observed[document_id].append((source_id, scope))

    final_docs = {
        doc for doc, values in observed.items() if any(scope.startswith("final") for _, scope in values)
    }
    requirements = case["reference_requirements"]
    active_flag = {req["requirement_id"]: _requirement_active(req, visible) for req in requirements}
    satisfied_by_docs = {
        req["requirement_id"]: any(set(option) <= final_docs for option in req["satisfying_document_sets"])
        for req in requirements
    }
    # A requirement switched off by an observed return is treated as satisfied (its documents
    # become not_required); a requirement whose trigger has not fired is "conditional" below.
    satisfied = {
        key: value or (not active_flag[key] and _requirement_switched_off(req_by_id[key], visible))
        for key, value in satisfied_by_docs.items()
        for req_by_id in [{req["requirement_id"]: req for req in requirements}]
    }
    unavailable_docs = {
        doc for doc, values in observed.items() if any(scope == "unavailable" for _, scope in values)
    }
    doc_requirements = defaultdict(list)
    for req in requirements:
        for option in req["satisfying_document_sets"]:
            for document_id in option:
                doc_requirements[document_id].append(req)
    conditional_docs = {
        doc
        for req in requirements
        if (not req["critical"]) or (not active_flag[req["requirement_id"]] and not satisfied[req["requirement_id"]])
        for option in req["satisfying_document_sets"]
        for doc in option
    }

    state_by_doc = {}
    for document_id in catalog_ids:
        scopes = [scope for _, scope in observed.get(document_id, [])]
        related = doc_requirements.get(document_id, [])
        redundant = bool(related) and all(satisfied[req["requirement_id"]] for req in related)
        if any(scope == "unavailable" for scope in scopes):
            state_by_doc[document_id] = "not_required"
        elif any(scope.startswith("final") or scope == "irrelevant" for scope in scopes):
            state_by_doc[document_id] = "received"
        elif redundant:
            state_by_doc[document_id] = "not_required"
        elif any(scope.startswith("partial") for scope in scopes):
            state_by_doc[document_id] = "insufficient"
        elif document_id in conditional_docs:
            state_by_doc[document_id] = "pending"
        elif not related:
            state_by_doc[document_id] = "not_required"
        else:
            state_by_doc[document_id] = "missing"

    active = [
        req
        for req in requirements
        if req["critical"] and active_flag[req["requirement_id"]] and not satisfied[req["requirement_id"]]
    ]
    checklists = _accepted_checklists(requirements, satisfied, final_docs, catalog_ids)
    relevant = _ordered_union(checklists, catalog_ids)
    canonical_critical = _ordered_union(
        [[doc for doc in req["satisfying_document_sets"][0] if doc not in final_docs] for req in active],
        catalog_ids,
    )
    ready = not active
    valid_actions = _valid_actions(case, state, checklists, conditional_docs | unavailable_docs, ready)
    ref_states = []
    warrants = []
    justification_map = case["accepted_justification_refs"]
    visible_refs = _visible_refs(case, visible)
    for document_id in catalog_ids:
        accepted = justification_map[document_id]
        observed_refs = [ref for ref in accepted["observed_return"] if ref in visible_refs]
        refs = list(dict.fromkeys(observed_refs + accepted["need_origin"] + accepted["handling_instruction"]))
        ref_states.append(
            {"document_id": document_id, "state": state_by_doc[document_id], "source_refs": refs}
        )
        returns = observed_refs or [None]
        for need in accepted["need_origin"] or [None]:
            for instruction in accepted["handling_instruction"] or [None]:
                for returned in returns:
                    warrants.append((document_id, need, instruction, returned))
    return {
        "document_states": ref_states,
        "checklist_document_ids": list(checklists[0]),
        "accepted_checklist_sets": [list(items) for items in checklists],
        "relevant_document_ids": relevant,
        "canonical_critical_document_ids": canonical_critical,
        "active_critical_requirement_ids": [req["requirement_id"] for req in active],
        "satisfied_requirement_ids": [key for key, value in satisfied.items() if value],
        "valid_next_actions": valid_actions,
        "ready": ready,
        "accepted_justification_refs": copy.deepcopy(justification_map),
        "justification_warrants": warrants,
    }


def _accepted_checklists(requirements, satisfied, final_docs, catalog_ids):
    alternatives = []
    for req in requirements:
        if satisfied[req["requirement_id"]]:
            continue
        options = []
        for option in req["satisfying_document_sets"]:
            options.append(tuple(doc for doc in option if doc not in final_docs))
        alternatives.append(options)
    if not alternatives:
        return [tuple()]
    candidates = []
    for combination in itertools.product(*alternatives):
        union = set(itertools.chain.from_iterable(combination))
        candidates.append(tuple(doc for doc in catalog_ids if doc in union))
    return list(dict.fromkeys(candidates))


def _valid_actions(case, state, checklists, conditional_docs, ready):
    if ready:
        return [{"kind": "proceed", "document_ids": []}]
    auto_docs = {item["document_id"] for item in state["scheduled"]}
    actions = []
    routes = []
    for checklist in checklists:
        route = tuple(doc for doc in checklist if doc not in conditional_docs and doc not in auto_docs)
        routes.append(route)
        if not route:
            actions.append(("wait", tuple()))
            continue
        for size in range(1, min(2, len(route)) + 1):
            for choice in itertools.combinations(route, size):
                if state["turn"] < 2:
                    later_capacity = 2 * max(0, 1 - state["turn"])
                    if len(route) - size > later_capacity:
                        continue
                actions.append(("request", choice))
    if not actions:
        actions.append(("clarify", tuple()))
    unique = list(dict.fromkeys(actions))
    return [{"kind": kind, "document_ids": list(ids)} for kind, ids in unique]


def score(case, state, plan, previous_plan=None, previous_state=None):
    """Score one valid decision snapshot, retaining explicit output failures."""
    ref = reference(case, state)
    errors = _plan_errors(case, plan)
    if errors:
        return _failure_metrics(errors)
    catalog_ids = _catalog_ids(case)
    expected_states = {row["document_id"]: row["state"] for row in ref["document_states"]}
    actor_states = {row["document_id"]: row["state"] for row in plan["document_states"]}
    state_accuracy = sum(actor_states[doc] == expected_states[doc] for doc in catalog_ids) / len(catalog_ids)

    checklist = set(plan["checklist_document_ids"])
    best_precision, best_recall, best_f1 = 0.0, 0.0, 0.0
    for accepted in ref["accepted_checklist_sets"]:
        truth = set(accepted)
        if not checklist and not truth:
            precision = recall = f1 = 1.0
        else:
            overlap = len(checklist & truth)
            precision = overlap / len(checklist) if checklist else 0.0
            recall = overlap / len(truth) if truth else 0.0
            f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        if f1 > best_f1 or (f1 == best_f1 and (precision, recall) > (best_precision, best_recall)):
            best_precision, best_recall, best_f1 = precision, recall, f1

    received = {doc for doc, value in expected_states.items() if value == "received"}
    active_ids = set(ref["active_critical_requirement_ids"])
    active_requirements = [
        req for req in case["reference_requirements"] if req["requirement_id"] in active_ids
    ]
    if active_requirements:
        represented = sum(
            any(set(option) <= checklist | received for option in req["satisfying_document_sets"])
            for req in active_requirements
        )
        critical_recall = represented / len(active_requirements)
    else:
        critical_recall = None

    action = (plan["next_action"]["kind"], frozenset(plan["next_action"]["document_ids"]))
    valid = [(item["kind"], frozenset(item["document_ids"])) for item in ref["valid_next_actions"]]
    next_exact = float(action in valid)
    similarities = []
    for kind, docs in valid:
        if action[0] != kind:
            similarities.append(0.0)
        elif not action[1] and not docs:
            similarities.append(1.0)
        else:
            similarities.append(len(action[1] & docs) / len(action[1] | docs))
    next_jaccard = max(similarities, default=0.0)

    requested = set(plan["requested_document_ids"])
    valid_request_sets = [docs for kind, docs in valid if kind == "request"]
    if requested:
        best_route = max(valid_request_sets, key=lambda docs: len(requested & docs), default=frozenset())
        unnecessary_docs = requested - best_route
        unnecessary = len(unnecessary_docs)
        unnecessary_rate = unnecessary / len(requested)
    else:
        unnecessary_docs = set()
        unnecessary = 0
        unnecessary_rate = None
    prior_requested = {event["document_id"] for event in state["request_history"]}
    scheduled = {item["document_id"] for item in state["scheduled"]}
    followups = set(state["followups"])
    repeat_docs = {
        doc
        for doc in requested
        if doc in prior_requested and (doc in received or doc in scheduled or doc not in followups)
    }
    repeats = len(repeat_docs)

    provenance = _provenance_score(case, state, plan, ref)
    readiness = float(plan["ready"] == ref["ready"])
    total_critical = [req for req in case["reference_requirements"] if req["critical"]]
    satisfied_ids = set(ref["satisfied_requirement_ids"])
    acquired = sum(req["requirement_id"] in satisfied_ids for req in total_critical) / len(total_critical)
    replanning = _replanning(case, state, plan, previous_plan, previous_state, ref)
    clarification = int(plan["next_action"]["kind"] == "clarify")
    returned_docs = set(state["source_documents"].values())
    hearsay_receipts = sum(
        1 for doc, value in actor_states.items()
        if value in {"received", "insufficient"} and doc not in returned_docs
    )
    premature_readiness = int(bool(plan["ready"]) and not ref["ready"])
    missed_readiness = int(ref["ready"] and not plan["ready"])
    return {
        "status": "ok",
        "failure_type": None,
        "errors": [],
        "premature_readiness": premature_readiness,
        "missed_readiness": missed_readiness,
        "hearsay_receipts": hearsay_receipts,
        "critical_evidence_recall": critical_recall,
        "unnecessary_document_rate": unnecessary_rate,
        "checklist_accuracy": best_f1,
        "checklist_precision": best_precision,
        "checklist_recall": best_recall,
        "state_accuracy": state_accuracy,
        "next_action_accuracy": next_exact,
        "next_action_jaccard": next_jaccard,
        "replanning_accuracy": replanning,
        "readiness_accuracy": readiness,
        "exact_provenance": provenance,
        "acquired_critical_evidence": acquired,
        "total_document_requests": len(plan["requested_document_ids"]),
        "unique_document_requests": len(requested),
        "unnecessary_unique_requests": unnecessary,
        "repeat_requests": repeats,
        "clarification_actions": clarification,
        "burden_primary": len(unnecessary_docs | repeat_docs),
    }


def _provenance_score(case, state, plan, ref):
    asserted_need = set(plan["checklist_document_ids"]) | set(plan["requested_document_ids"])
    actor_states = {item["document_id"]: item["state"] for item in plan["document_states"]}
    asserted_return = {
        document_id
        for document_id, value in actor_states.items()
        if value in {"received", "insufficient"}
    }
    obligations = asserted_need | asserted_return
    if not obligations:
        return None
    visible_refs = _visible_refs(case, set(state["visible_source_ids"]))
    by_doc = defaultdict(list)
    for item in plan["justifications"]:
        by_doc[item["document_id"]].append(item)
    correct = 0
    reference_relevant = set(ref["relevant_document_ids"])
    for document_id in obligations:
        accepted = ref["accepted_justification_refs"][document_id]
        need = set(accepted["need_origin"])
        instruction = set(accepted["handling_instruction"])
        returned = set(accepted["observed_return"]) & visible_refs
        need_asserted = document_id in asserted_need
        return_asserted = document_id in asserted_return
        if need_asserted and document_id not in reference_relevant:
            continue
        if return_asserted and not returned:
            continue
        for item in by_doc.get(document_id, []):
            refs = set(item["source_refs"])
            if not refs <= visible_refs:
                continue
            if need_asserted and need and not refs & need:
                continue
            if need_asserted and instruction and not refs & instruction:
                continue
            if return_asserted and not refs & returned:
                continue
            if item["decision_id"].strip() and item["reason"].strip():
                correct += 1
                break
    return correct / len(obligations)


def _replanning(case, state, plan, previous_plan, previous_state, current_ref):
    if previous_plan is None and previous_state is None:
        return None
    if previous_plan is None or previous_state is None or _plan_errors(case, previous_plan):
        return 0.0
    previous_ref = reference(case, previous_state)
    actor_old = {x["document_id"]: x["state"] for x in previous_plan["document_states"]}
    actor_new = {x["document_id"]: x["state"] for x in plan["document_states"]}
    ref_old = {x["document_id"]: x["state"] for x in previous_ref["document_states"]}
    ref_new = {x["document_id"]: x["state"] for x in current_ref["document_states"]}
    actor_state_delta = {(d, actor_old[d], actor_new[d]) for d in actor_old if actor_old[d] != actor_new[d]}
    ref_state_delta = {(d, ref_old[d], ref_new[d]) for d in ref_old if ref_old[d] != ref_new[d]}
    state_delta = float(actor_state_delta == ref_state_delta)

    old_check = set(previous_plan["checklist_document_ids"])
    new_check = set(plan["checklist_document_ids"])
    actor_check_delta = (new_check - old_check, old_check - new_check)
    globally_new = set().union(*map(set, current_ref["accepted_checklist_sets"])) - set().union(
        *map(set, previous_ref["accepted_checklist_sets"])
    )
    valid_check_deltas = {
        (frozenset(set(new) - set(old)), frozenset(set(old) - set(new)))
        for old in previous_ref["accepted_checklist_sets"]
        for new in current_ref["accepted_checklist_sets"]
        if set(new) - set(old) <= globally_new
    }
    check_delta = float((frozenset(actor_check_delta[0]), frozenset(actor_check_delta[1])) in valid_check_deltas)
    old_kinds = {item["kind"] for item in previous_ref["valid_next_actions"]}
    new_kinds = {item["kind"] for item in current_ref["valid_next_actions"]}
    action_delta = float(
        previous_plan["next_action"]["kind"] in old_kinds and plan["next_action"]["kind"] in new_kinds
    )
    readiness_delta = float(
        (previous_plan["ready"], plan["ready"]) == (previous_ref["ready"], current_ref["ready"])
    )
    return (state_delta + check_delta + action_delta + readiness_delta) / 4


def _plan_errors(case, plan):
    if not isinstance(plan, dict):
        return ["no_output" if plan is None else "output_not_object"]
    errors = []
    docs = set(_catalog_ids(case))
    rows = plan.get("document_states")
    if not isinstance(rows, list):
        errors.append("document_states_missing")
    else:
        ids = [row.get("document_id") for row in rows if isinstance(row, dict)]
        if len(rows) != len(docs) or set(ids) != docs or len(ids) != len(set(ids)):
            errors.append("document_states_must_cover_catalog_once")
        for row in rows:
            if not isinstance(row, dict) or row.get("state") not in VALID_STATES:
                errors.append("invalid_document_state")
                break
            if not isinstance(row.get("source_refs"), list) or not all(
                isinstance(ref, str) for ref in row["source_refs"]
            ):
                errors.append("invalid_document_state_refs")
                break
    for field in ("checklist_document_ids", "requested_document_ids"):
        value = plan.get(field)
        if not isinstance(value, list) or len(value) != len(set(value)) or not set(value or []) <= docs:
            errors.append(f"invalid_{field}")
    requested = plan.get("requested_document_ids")
    if isinstance(requested, list) and len(requested) > 2:
        errors.append("request_limit_exceeded")
    action = plan.get("next_action")
    if not isinstance(action, dict) or action.get("kind") not in VALID_ACTIONS:
        errors.append("invalid_next_action")
    else:
        action_docs = action.get("document_ids")
        if not isinstance(action_docs, list) or len(action_docs) != len(set(action_docs)) or not set(action_docs or []) <= docs:
            errors.append("invalid_next_action_documents")
        elif action["kind"] == "request" and action_docs != requested:
            errors.append("request_action_mismatch")
        elif action["kind"] != "request" and (action_docs or requested):
            errors.append("nonrequest_action_has_documents")
    if not isinstance(plan.get("ready"), bool):
        errors.append("ready_not_boolean")
    justifications = plan.get("justifications")
    if not isinstance(justifications, list):
        errors.append("justifications_missing")
    else:
        for item in justifications:
            if (
                not isinstance(item, dict)
                or item.get("document_id") not in docs
                or not isinstance(item.get("source_refs"), list)
                or not all(isinstance(ref, str) for ref in item.get("source_refs", []))
                or not isinstance(item.get("decision_id"), str)
                or not isinstance(item.get("reason"), str)
            ):
                errors.append("invalid_justification")
                break
    return list(dict.fromkeys(errors))


def _failure_metrics(errors):
    result = {
        "status": "failure",
        "failure_type": "actor_output_failure",
        "errors": errors,
        "critical_evidence_recall": 0.0,
        "unnecessary_document_rate": 1.0,
        "checklist_accuracy": 0.0,
        "checklist_precision": 0.0,
        "checklist_recall": 0.0,
        "state_accuracy": 0.0,
        "next_action_accuracy": 0.0,
        "next_action_jaccard": 0.0,
        "replanning_accuracy": 0.0,
        "readiness_accuracy": 0.0,
        "exact_provenance": 0.0,
        "acquired_critical_evidence": 0.0,
    }
    result.update({key: 0 for key in COUNT_KEYS})
    result["burden_primary"] = 1
    return result


def aggregate(records):
    """Aggregate score records by arm while retaining failures and denominators."""
    grouped = defaultdict(list)
    for record in records:
        arm = record.get("arm", record.get("arm_id"))
        if not isinstance(arm, str) or not arm:
            raise ValueError("every record needs arm or arm_id")
        metrics = record.get("metrics", record)
        grouped[arm].append(metrics)
    output = {}
    for arm, rows in grouped.items():
        means = {}
        denominators = {}
        for key in SCORE_KEYS:
            values = [row.get(key) for row in rows if isinstance(row.get(key), (int, float))]
            means[key] = sum(values) / len(values) if values else None
            denominators[key] = len(values)
        sums = {
            key: sum(row.get(key, 0) for row in rows if isinstance(row.get(key, 0), (int, float)))
            for key in COUNT_KEYS
        }
        failures = sum(row.get("status") != "ok" for row in rows)
        output[arm] = {
            "records": len(rows),
            "successful_records": len(rows) - failures,
            "failed_records": failures,
            "mean_metrics": means,
            "metric_denominators": denominators,
            "sum_counts": sums,
        }
    return output


def _requirement_active(req, visible):
    rule = req.get("activation")
    if not rule:
        return True
    on = rule.get("active_if_any_observed")
    off = rule.get("inactive_if_any_observed")
    if off and set(off) & set(visible):
        return False
    if on:
        return bool(set(on) & set(visible))
    return True


def _requirement_switched_off(req, visible):
    rule = req.get("activation") or {}
    off = rule.get("inactive_if_any_observed")
    return bool(off and set(off) & set(visible))


def _check_state(case, state):
    if not isinstance(state, dict) or state.get("case_id") != case.get("case_id"):
        raise ValueError("state does not belong to case")
    if state.get("turn") not in {0, 1, 2}:
        raise ValueError("invalid state turn")


def _catalog_ids(case):
    return [item["document_id"] for item in case["actor_initial"]["document_catalog"]]


def _source_map(case):
    sources = case["actor_initial"]["sources"] + case["source_store"]
    return {source["id"]: source for source in sources}


def _source_effects(case):
    effects = {}
    for row in case["action_response_table"]:
        document_id = row["document_id"]
        for source_id in row.get("response_source_ids", []):
            effects[source_id] = (document_id, row.get("scope", "final"))
        for key in ("if_first_requested_at_turn_0", "if_first_requested_at_turn_1"):
            for response in row.get(key, []):
                for source_id in response["source_ids"]:
                    effect = (document_id, response.get("scope", "final"))
                    if source_id in effects and effects[source_id] != effect:
                        raise ValueError(f"conflicting source effect for {source_id}")
                    effects[source_id] = effect
    return effects


def _visible_refs(case, source_ids):
    refs = set()
    sources = _source_map(case)
    for source_id in source_ids:
        for paragraph in sources[source_id]["paragraphs"]:
            refs.add(f"{source_id}#{paragraph['id']}")
    return refs


def _ordered_union(groups, catalog_ids):
    wanted = set(itertools.chain.from_iterable(groups)) if groups else set()
    return [doc for doc in catalog_ids if doc in wanted]
