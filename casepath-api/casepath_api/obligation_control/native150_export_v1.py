"""Projection into CandidateArtifact 0.1.0; no target/scorer dependency.

The producer must provide actual control concepts, transitions, branch expressions,
source locators and decision anchors. Missing semantics cause rejection, not repair.
The full planning output retains proof-route grouping and joint adequacy; the
native artifact has no fields for those internal objects and is not a lossless
serialization of the runtime state.
"""
from __future__ import annotations
import copy
from typing import Any

from .obligation_control_v1 import (Expr, Graph, Invalid, TRUE, conjunction, fields,
                                    identifier, ids, support)
from .evidence_demand_v1 import Capability

CONTRACT = "casepath.native150-binding/1.0.0"


def disjunction(values: list[Expr]) -> Expr:
    return values[0] if len(values) == 1 else Expr("any", args=tuple(values)) if values else Expr("const", False)


def expression(ref: Any, graph: Graph, expanded: dict[str, Expr]) -> Expr:
    if not isinstance(ref, dict) or len(ref) != 1:
        raise Invalid("activation reference must have exactly one field")
    if "control_id" in ref:
        if ref["control_id"] not in expanded:
            raise Invalid("unknown activation control id")
        return expanded[ref["control_id"]]
    if "expression" in ref:
        return Expr.parse(ref["expression"], set(graph.variables))
    raise Invalid("invalid activation reference")


def export(graph: Graph, caps: tuple[Capability, ...], plan: dict, evidence: dict,
           binding: dict, registry: dict, case_id: str) -> dict:
    if not isinstance(case_id, str) or not case_id or len(case_id) > 256:
        raise Invalid("invalid case id")
    fields(binding, {"contract", "control_concepts", "control_relations", "branch_predicates",
                     "documents", "decision_by_obligation", "terminal_outcome_ids"})
    if binding["contract"] != CONTRACT:
        raise Invalid("native binding contract mismatch")
    for family in ("control_concepts", "control_relations", "branch_predicates", "documents"):
        if not isinstance(binding[family], list) or len(binding[family]) > 4096:
            raise Invalid("native binding array exceeds bound")
    expanded = graph.expressions()
    source_keys = set(registry)

    def locators(refs: Any) -> list[dict]:
        return [copy.deepcopy(registry[r]["locator"]) for r in support(refs, source_keys)]

    concepts, relations, predicates, documents = {}, {}, {}, {}
    for row in binding["control_concepts"]:
        fields(row, {"concept_id", "kind", "label", "activation", "source_refs"})
        cid = identifier(row["concept_id"])
        if cid in concepts or row["kind"] not in {"process_step", "decision", "outcome"}:
            raise Invalid("invalid or duplicate control concept")
        if not isinstance(row["label"], str) or not row["label"].strip():
            raise Invalid("missing concept label")
        concepts[cid] = {"concept_id": cid, "kind": row["kind"], "label": row["label"],
            "active_when": expression(row["activation"], graph, expanded).native(),
            "provenance": locators(row["source_refs"])}
    for row in binding["control_relations"]:
        fields(row, {"relation_id", "relation_type", "source_id", "target_id", "activation"})
        rid = identifier(row["relation_id"])
        if rid in relations or row["relation_type"] not in {"precedes", "branches_to"}:
            raise Invalid("invalid or duplicate control relation")
        if row["source_id"] not in concepts or row["target_id"] not in concepts:
            raise Invalid("control relation references unknown endpoint")
        if row["relation_type"] == "branches_to" and concepts[row["source_id"]]["kind"] != "decision":
            raise Invalid("branch source must actually be a decision")
        relations[rid] = {k: row[k] for k in ("relation_id", "relation_type", "source_id", "target_id")}
        relations[rid]["active_when"] = expression(row["activation"], graph, expanded).native()
    for row in binding["branch_predicates"]:
        fields(row, {"predicate_id", "expression", "source_refs"})
        pid = identifier(row["predicate_id"])
        if pid in predicates:
            raise Invalid("duplicate branch predicate")
        predicates[pid] = {"predicate_id": pid, "expression": Expr.parse(row["expression"], set(graph.variables)).native(),
                           "provenance": locators(row["source_refs"])}
    by_doc = {}
    for row in binding["documents"]:
        fields(row, {"item_id", "document_id", "label", "source_refs"})
        did, iid = identifier(row["document_id"]), identifier(row["item_id"])
        if did in by_doc or iid in documents or iid in concepts:
            raise Invalid("duplicate/colliding native document identity")
        by_doc[did] = iid
        documents[iid] = {"item_id": iid, "document_id": did, "label": row["label"],
                          "provenance": locators(row["source_refs"])}
    required_docs = {d for c in caps for r in c.routes for d in r.document_ids}
    if set(by_doc) != required_docs:
        raise Invalid("native document bindings must match actual capability routes")
    decisions = binding["decision_by_obligation"]
    if not isinstance(decisions, dict) or set(decisions) != {o.obligation_id for o in graph.obligations}:
        raise Invalid("missing/extra obligation-to-decision bindings")
    if any(d not in concepts or concepts[d]["kind"] != "decision" for d in decisions.values()):
        raise Invalid("obligation needs a real declared decision, not relabelled steps")
    cap_index = {c.capability_id: c for c in caps}
    concept_exprs, concept_refs, doc_exprs = {}, {}, {d: [] for d in by_doc}

    def derived_concept(cid: str, kind: str, label: str, active: Expr, refs: list[str]) -> None:
        if cid in documents:
            raise Invalid("fact/capability collides with document item id")
        if cid in concepts and (concepts[cid]["kind"] != kind or concepts[cid]["label"] != label):
            raise Invalid("semantic identity collision")
        concepts.setdefault(cid, {"concept_id": cid, "kind": kind, "label": label})
        concept_exprs.setdefault(cid, []).append(active)
        concept_refs.setdefault(cid, set()).update(refs)

    chain_exprs = {}
    for o in graph.obligations:
        active = expanded[o.obligation_id]
        acquisition = conjunction(active, o.acquire_when)
        for cid in o.capability_ids:
            if cid not in cap_index:
                raise Invalid("unknown capability")
            c = cap_index[cid]
            refs = sorted(set(o.source_refs) | set(c.source_refs))
            derived_concept(c.fact_id, "fact", c.fact_statement, active, refs)
            derived_concept(cid, "evidence_capability", c.must_show, active, refs)
            chain_exprs.setdefault(("requires_fact", decisions[o.obligation_id], c.fact_id), []).append(active)
            chain_exprs.setdefault(("supported_by", c.fact_id, cid), []).append(active)
            for route in c.routes:
                for doc in route.document_ids:
                    chain_exprs.setdefault(("satisfied_by", cid, by_doc[doc]), []).append(active)
                    doc_exprs[doc].append(acquisition)
    for cid, expressions in concept_exprs.items():
        concepts[cid]["active_when"] = disjunction(expressions).native()
        concepts[cid]["provenance"] = locators(sorted(concept_refs[cid]))
    for index, (key, expressions) in enumerate(sorted(chain_exprs.items()), 1):
        rid = f"oc_chain_{index:04d}"
        if rid in relations:
            raise Invalid("generated chain id collides with actual control relation")
        kind, src, dst = key
        relations[rid] = {"relation_id": rid, "relation_type": kind, "source_id": src,
                          "target_id": dst, "active_when": disjunction(expressions).native()}
    now, conditional = set(plan["documents_now"]), set(plan["documents_conditional"])
    if (now | conditional) - set(by_doc) or now & conditional:
        raise Invalid("unbound or ambiguous emitted document")
    for doc, iid in by_doc.items():
        state = evidence["documents"].get(doc, {}).get("native_state", "unknown")
        if doc in now and state in {"provided_sufficient", "irrelevant"}:
            raise Invalid("emitted request contradicts upstream document-state assessment")
        documents[iid].update({"state": state, "request_mode": "now" if doc in now else "conditional" if doc in conditional else "none",
                               "active_when": disjunction(doc_exprs[doc]).native()})
    terminal = ids(binding["terminal_outcome_ids"])
    if any(t not in concepts or concepts[t]["kind"] != "outcome" for t in terminal):
        raise Invalid("terminal ids must already be actual outcome concepts")
    return {"artifact_version": "casepath.candidate-artifact/0.1.0", "case_id": case_id,
            "concepts": [concepts[k] for k in sorted(concepts)],
            "relations": [relations[k] for k in sorted(relations)],
            "branch_predicates": [predicates[k] for k in sorted(predicates)],
            "documents": [documents[k] for k in sorted(documents)],
            "terminal_outcome_ids": list(terminal), "abstained_concept_ids": []}
