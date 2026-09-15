"""Channel-typed evidential state (CTES) — core calculus, provider-free.

The model contributes only local atoms (what a text unit attests, mentions, promises, denies) and a
requirement map read from the governing instructions. The epistemic *level* a unit can lend to a
requirement is a function of the unit's channel metadata, never of the model's judgement:
party reports (the customer's own message, or statements relayed in it) can raise availability
beliefs about artifacts but can never satisfy a requirement; only a returned, readable artifact
(channel ``returned_artifact``) can. Readiness, document states, and the next request are then
computed deterministically. Setting ``channel_cap=False`` removes the cap (every attestation counts at
the observed level) and is the preregistered mechanism ablation.
"""
from __future__ import annotations

import copy
import itertools
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

CONTRACT = "casepath.evidential-channel-state/1.0.0"
LEVEL = {"reported": 1, "observed": 2, "authenticated": 3}
CHANNEL_LEVEL = {
    "party_report": 1,
    "third_party_report": 1,
    "instruction": 0,
    "returned_artifact": 2,
    "authenticated_artifact": 3,
}
DOC_STATES = ("missing", "insufficient", "received", "pending", "not_required")
MENTION_STATUSES = (
    "exists", "possessed_by_customer", "held_by_third_party", "promised",
    "automatic", "nonexistent", "content_quoted", "unreadable",
)


class EvidentialChannelError(ValueError):
    pass


@dataclass(frozen=True)
class Unit:
    ref: str                      # source_id#paragraph_id
    channel: str                  # CHANNEL_LEVEL key
    document_id: str | None = None  # for returned artifacts


@dataclass
class Requirement:
    requirement_id: str
    description: str
    satisfying_document_sets: list[list[str]]
    critical: bool = True
    standard: str = "observed"
    active: bool = True           # model-read activation (trigger observed?)
    source_refs: list[str] = field(default_factory=list)


@dataclass
class Attestation:
    unit_ref: str
    requirement_id: str
    coverage: str                 # full | partial | contrary | none


@dataclass
class Mention:
    unit_ref: str
    document_id: str
    status: str                   # MENTION_STATUSES
    holder: str | None = None


def channel_for_source(source: Mapping[str, Any]) -> str:
    """Channel typing from metadata only."""
    if source.get("document_id"):
        return "returned_artifact"
    sid = str(source.get("id", ""))
    if sid.startswith("gov-"):
        return "instruction"
    return "party_report"


def units_from_actor(actor: Mapping[str, Any]) -> list[Unit]:
    units: list[Unit] = []
    for source in actor["sources"]:
        channel = channel_for_source(source)
        for paragraph in source["paragraphs"]:
            units.append(Unit(ref=f"{source['id']}#{paragraph['id']}", channel=channel,
                              document_id=source.get("document_id")))
    return units


def parse_extraction(raw: Mapping[str, Any], actor: Mapping[str, Any], parse_notes: dict | None = None) -> tuple[list[Requirement], list[Attestation], list[Mention], dict[str, str]]:
    """Validate the model's local atoms against the actor; reject unknown ids/refs (no repair)."""
    parse_notes = parse_notes if parse_notes is not None else {}
    catalog = [row["id"] for row in actor["document_catalog"]]
    units = {u.ref: u for u in units_from_actor(actor)}
    reqs: list[Requirement] = []
    seen: set[str] = set()
    dropped: list[str] = []
    for row in raw.get("requirements", []):
        rid = str(row["id"]).strip()
        if not rid or rid in seen:
            raise EvidentialChannelError("requirement ids must be unique and non-empty")
        seen.add(rid)
        # Conservative parse: ids outside the catalogue are dropped; an option that becomes empty is dropped.
        # A requirement left with no option is retained as UNSATISFIABLE — it is never satisfied, contributes no
        # request, and permanently blocks readiness. This can only lower the arm's acquired evidence; it can never
        # create a premature readiness. Applied identically with and without the channel cap.
        raw_sets = [[str(d) for d in option] for option in row.get("satisfying_document_sets", [])]
        sets = [opt for opt in ([d for d in option if d in catalog] for option in raw_sets) if opt]
        dropped.extend(d for option in raw_sets for d in option if d not in catalog)
        standard = str(row.get("standard", "observed"))
        if standard not in LEVEL:
            raise EvidentialChannelError(f"requirement {rid} has an unknown standard")
        refs = [str(r) for r in row.get("source_refs", [])]
        if any(r not in units for r in refs):
            raise EvidentialChannelError(f"requirement {rid} cites an unknown source ref")
        reqs.append(Requirement(rid, str(row.get("description", "")), sets, bool(row.get("critical", True)),
                                standard, bool(row.get("active", True)), refs))
    req_ids = {r.requirement_id for r in reqs}
    # Fail-soft atoms: an atom naming a unit, requirement, document or status that does not exist is
    # dropped and counted, never repaired and never fatal. Dropping an attestation can only remove
    # support (it can never create a receipt or a readiness); dropping a mention can only remove
    # availability knowledge, which at worst costs an extra request. Applied identically with and
    # without the channel cap, so the ablation sees exactly the same atoms.
    dropped_atoms: list[str] = []
    atts: list[Attestation] = []
    for row in raw.get("attestations", []) or []:
        try:
            ref, rid, cov = str(row["unit_ref"]), str(row["requirement_id"]), str(row["coverage"])
        except (TypeError, KeyError):
            dropped_atoms.append("attestation:malformed"); continue
        if ref not in units or rid not in req_ids or cov not in {"full", "partial", "contrary", "none"}:
            dropped_atoms.append(f"attestation:{ref}|{rid}|{cov}"); continue
        atts.append(Attestation(ref, rid, cov))
    mentions: list[Mention] = []
    for row in raw.get("mentions", []) or []:
        try:
            ref, doc, status = str(row["unit_ref"]), str(row["document_id"]), str(row["status"])
        except (TypeError, KeyError):
            dropped_atoms.append("mention:malformed"); continue
        if ref not in units or doc not in catalog or status not in MENTION_STATUSES:
            dropped_atoms.append(f"mention:{ref}|{doc}|{status}"); continue
        mentions.append(Mention(ref, doc, status, row.get("holder")))
    readability: dict[str, str] = {}
    for row in raw.get("readability", []) or []:
        try:
            doc, value = str(row["document_id"]), str(row["value"])
        except (TypeError, KeyError):
            dropped_atoms.append("readability:malformed"); continue
        if doc not in catalog or value not in {"full", "partial", "unreadable"}:
            dropped_atoms.append(f"readability:{doc}|{value}"); continue
        readability[doc] = value
    parse_notes["dropped_atoms"] = dropped_atoms
    parse_notes["dropped_document_ids"] = sorted(set(dropped))
    return reqs, atts, mentions, readability


def compute_state(
    actor: Mapping[str, Any],
    reqs: Sequence[Requirement],
    atts: Sequence[Attestation],
    mentions: Sequence[Mention],
    readability: Mapping[str, str],
    *,
    channel_cap: bool = True,
    levels_from_content: bool | None = None,
    believe_party_commitments: bool | None = None,
    satisfy_by_attestation_alone: bool | None = None,
    prior_requests: Sequence[str] = (),
    max_requests: int = 2,
    hedge_spare_slot: bool = False,
) -> dict[str, Any]:
    # ``channel_cap`` remains the compound switch it has always been, so every frozen run reproduces
    # byte for byte. It turns off three separable rules at once, which is why it cannot isolate the cap:
    #   levels_from_content          - a unit's support level comes from its text rather than its channel
    #   believe_party_commitments    - a delivery promise reported by a party is taken at face value
    #   satisfy_by_attestation_alone - an attestation can satisfy a requirement with no artifact on file
    # Each defaults to ``not channel_cap``; setting one explicitly ablates exactly that rule.
    if levels_from_content is None:
        levels_from_content = not channel_cap
    if believe_party_commitments is None:
        believe_party_commitments = not channel_cap
    if satisfy_by_attestation_alone is None:
        satisfy_by_attestation_alone = not channel_cap
    units = {u.ref: u for u in units_from_actor(actor)}
    catalog = [row["id"] for row in actor["document_catalog"]]
    returned: dict[str, list[Unit]] = {}
    for u in units.values():
        if u.channel == "returned_artifact" and u.document_id:
            returned.setdefault(u.document_id, []).append(u)

    def unit_level(u: Unit) -> int:
        if not levels_from_content:
            return CHANNEL_LEVEL[u.channel]
        return LEVEL["observed"] if u.channel != "instruction" else 0

    # attained level per requirement and per document (from full attestations)
    attained: dict[str, int] = {r.requirement_id: 0 for r in reqs}
    doc_full: dict[str, int] = {}
    doc_partial: set[str] = set()
    for a in atts:
        u = units[a.unit_ref]
        lvl = unit_level(u)
        if a.coverage == "full":
            attained[a.requirement_id] = max(attained[a.requirement_id], lvl)
            if u.document_id:
                doc_full[u.document_id] = max(doc_full.get(u.document_id, 0), lvl)
        elif a.coverage == "partial" and u.document_id:
            doc_partial.add(u.document_id)
    availability: dict[str, str] = {}
    for m in mentions:
        status = m.status
        u = units[m.unit_ref]
        # Channel rule for second-order reports: a delivery commitment (promised/automatic) counts only when
        # it comes from a returned artifact of the committing party; in a party report it is hearsay and
        # only establishes existence. Without the channel cap every report is taken at face value.
        if not believe_party_commitments and u.channel != "returned_artifact" and status in {"promised", "automatic"}:
            status = "exists"
        order = {"exists": 1, "content_quoted": 1, "possessed_by_customer": 2, "held_by_third_party": 2,
                 "promised": 3, "automatic": 4, "unreadable": 0, "nonexistent": 5}
        if order.get(status, 0) >= order.get(availability.get(m.document_id, ""), -1):
            availability[m.document_id] = status

    def doc_observed_ok(doc: str) -> bool:
        return doc in returned and readability.get(doc, "full") == "full" and doc_full.get(doc, 0) >= LEVEL["observed"]

    satisfied: dict[str, bool] = {}
    for r in reqs:
        if not r.satisfying_document_sets:
            satisfied[r.requirement_id] = False
            continue
        if satisfy_by_attestation_alone:
            satisfied[r.requirement_id] = attained[r.requirement_id] >= LEVEL[r.standard] or any(
                all(doc_observed_ok(d) for d in option) for option in r.satisfying_document_sets)
        else:
            satisfied[r.requirement_id] = any(
                all(doc_observed_ok(d) for d in option) for option in r.satisfying_document_sets
            ) and attained[r.requirement_id] >= LEVEL[r.standard]
    active_unsat = [r for r in reqs if r.critical and r.active and not satisfied[r.requirement_id]]
    need_docs: set[str] = set()
    for r in reqs:
        for option in r.satisfying_document_sets:
            need_docs.update(option)
    states: dict[str, str] = {}
    for doc in catalog:
        related = [r for r in reqs if any(doc in option for option in r.satisfying_document_sets)]
        av = availability.get(doc)
        if doc in returned and (readability.get(doc, "full") == "full") and doc_full.get(doc, 0) >= LEVEL["observed"]:
            states[doc] = "received"
        elif doc in returned and (doc in doc_partial or readability.get(doc) in {"partial", "unreadable"}):
            states[doc] = "insufficient"
        elif doc in returned:
            states[doc] = "received"   # returned artifact whose content was not needed
        elif av == "nonexistent":
            states[doc] = "not_required"
        elif not related:
            states[doc] = "not_required"
        elif all(satisfied[r.requirement_id] for r in related):
            states[doc] = "not_required"
        elif all(not r.active for r in related) or (av in {"promised", "automatic"}):
            states[doc] = "pending"
        else:
            states[doc] = "missing"
    # checklist: documents still needed by unsatisfied active/inactive-but-critical requirements
    checklist = []
    for doc in catalog:
        related = [r for r in reqs if any(doc in option for option in r.satisfying_document_sets)]
        if related and not all(satisfied[r.requirement_id] for r in related) and states[doc] != "not_required":
            checklist.append(doc)
    # request selection: greedy cheapest cover of active unsatisfied requirements
    requestable = {
        doc for doc in catalog
        if states[doc] in {"missing", "insufficient"} and availability.get(doc) not in {"promised", "automatic"}
        # do not re-request a document requested in the previous turn unless its return proved insufficient
        and not (doc in prior_requests and doc not in returned)
    }
    chosen: list[str] = []
    remaining = list(active_unsat)
    while remaining and len(chosen) < max_requests:
        best, best_gain = None, 0
        for doc in catalog:
            if doc in chosen or doc not in requestable:
                continue
            gain = 0
            for r in remaining:
                for option in r.satisfying_document_sets:
                    missing = [d for d in option if not doc_observed_ok(d) and d not in chosen]
                    if doc in missing:
                        gain += 1.0 / len(missing) + (0.5 if availability.get(doc) == "possessed_by_customer" else 0.0) - (0.75 if availability.get(doc) == "nonexistent" else 0.0)
            if gain > best_gain:
                best, best_gain = doc, gain
        if best is None:
            break
        chosen.append(best)
        remaining = [
            r for r in remaining
            if not any(all(doc_observed_ok(d) or d in chosen for d in option) for option in r.satisfying_document_sets)
        ]
    # Ordinary redundancy under uncertain fulfilment (standard machinery, not part of the claimed
    # contribution): a cover can be discharged by a single document that satisfies every open
    # requirement, and a turn is wasted if that document returns incomplete. While request slots remain
    # and requirements are still open, add the best document from an alternative route that shares no
    # document with what is already chosen, preferring one the customer is reported to hold.
    if hedge_spare_slot and chosen and len(chosen) < max_requests and active_unsat:
        alternatives: dict[str, float] = {}
        for r in active_unsat:
            for option in r.satisfying_document_sets:
                if any(d in chosen for d in option):
                    continue
                open_docs = [d for d in option if not doc_observed_ok(d) and d in requestable and d not in chosen]
                if not open_docs or len(open_docs) > max_requests - len(chosen):
                    continue
                for d in open_docs:
                    alternatives[d] = alternatives.get(d, 0.0) + 1.0 / len(open_docs) + (
                        0.5 if availability.get(d) == "possessed_by_customer" else 0.0)
        for doc, _score in sorted(alternatives.items(), key=lambda kv: (-kv[1], catalog.index(kv[0]))):
            if len(chosen) >= max_requests:
                break
            chosen.append(doc)
    ready = not active_unsat and bool(reqs)
    pending_outstanding = any(states[d] == "pending" for d in catalog if any(
        d in option for r in active_unsat for option in r.satisfying_document_sets))
    if ready:
        action = {"kind": "proceed", "document_ids": []}
    elif chosen:
        action = {"kind": "request", "document_ids": list(chosen)}
    elif not reqs:
        action = {"kind": "clarify", "document_ids": []}
    else:
        action = {"kind": "wait", "document_ids": []}
    return {
        "contract": CONTRACT,
        "channel_cap": channel_cap,
        "rules": {"levels_from_content": levels_from_content,
                  "believe_party_commitments": believe_party_commitments,
                  "satisfy_by_attestation_alone": satisfy_by_attestation_alone},
        "attained_levels": attained,
        "availability": availability,
        "satisfied": satisfied,
        "active_unsatisfied": [r.requirement_id for r in active_unsat],
        "document_states": states,
        "checklist_document_ids": checklist,
        "requested_document_ids": list(chosen),
        "next_action": action,
        "ready": ready,
        "pending_outstanding": pending_outstanding,
    }


def plan_from_state(actor: Mapping[str, Any], state: Mapping[str, Any], reqs: Sequence[Requirement],
                    atts: Sequence[Attestation], mentions: Sequence[Mention], arm_label: str) -> dict[str, Any]:
    """Project the calculus state into the common actor-output contract used by every arm."""
    catalog = [row["id"] for row in actor["document_catalog"]]
    units = units_from_actor(actor)
    gov_refs = [u.ref for u in units if u.channel == "instruction"]
    party_refs = [u.ref for u in units if u.channel == "party_report"]
    by_req_refs: dict[str, list[str]] = {r.requirement_id: list(r.source_refs) for r in reqs}
    doc_refs: dict[str, list[str]] = {d: [] for d in catalog}
    for a in atts:
        for u in units:
            if u.ref == a.unit_ref and u.document_id:
                doc_refs.setdefault(u.document_id, []).append(u.ref)
    for m in mentions:
        doc_refs.setdefault(m.document_id, []).append(m.unit_ref)
    document_states, justifications = [], []
    for doc in catalog:
        related = [r for r in reqs if any(doc in option for option in r.satisfying_document_sets)]
        refs: list[str] = []
        for r in related:
            refs += by_req_refs.get(r.requirement_id, [])
        refs += doc_refs.get(doc, [])
        refs = list(dict.fromkeys(refs)) or (gov_refs[:1] + party_refs[:1])
        document_states.append({"document_id": doc, "state": state["document_states"][doc], "source_refs": refs})
        for r in related:
            jrefs = list(dict.fromkeys(by_req_refs.get(r.requirement_id, []) + doc_refs.get(doc, [])))
            justifications.append({"document_id": doc, "source_refs": jrefs or refs, "decision_id": r.requirement_id,
                                   "reason": f"{r.description} ({'satisfied' if state['satisfied'][r.requirement_id] else 'open'}; channel-typed level {state['attained_levels'][r.requirement_id]} vs standard {r.standard})"})
    return {
        "document_states": document_states,
        "checklist_document_ids": list(state["checklist_document_ids"]),
        "requested_document_ids": list(state["requested_document_ids"]),
        "next_action": copy.deepcopy(state["next_action"]),
        "ready": bool(state["ready"]),
        "justifications": justifications,
        "method_arm": arm_label,
        "evidential_channel_state": {k: state[k] for k in ("attained_levels", "availability", "satisfied", "active_unsatisfied", "channel_cap")},
    }
