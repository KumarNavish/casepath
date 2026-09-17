"""Deterministic, provenance-checked repairs for development-discovered refinement defects."""
from __future__ import annotations

import copy
from typing import Any, Mapping, Sequence

CONTRACT = "casepath.refinement-repairs/1.0.0"


def _rule(refinement: Mapping[str, Any], rule_id: str) -> dict[str, Any]:
    matches = [rule for rule in refinement.get("rules") or [] if rule.get("rule_id") == rule_id]
    if len(matches) != 1:
        raise ValueError(f"expected one rule {rule_id!r}, found {len(matches)}")
    return matches[0]


def _proposition(propositions: Sequence[Mapping[str, Any]], proposition_id: str) -> Mapping[str, Any]:
    matches = [p for p in propositions if p.get("proposition_id") == proposition_id]
    if len(matches) != 1:
        raise ValueError(f"expected one proposition {proposition_id!r}, found {len(matches)}")
    return matches[0]


def _rule_propositions(rule: Mapping[str, Any]) -> set[str]:
    identifiers = set(rule.get("supported_by") or []) | set(rule.get("condition_supported_by") or [])
    for fact in rule.get("facts") or []:
        identifiers.update(fact.get("from_propositions") or [])
        for capability in fact.get("capabilities") or []:
            identifiers.update(capability.get("from_propositions") or [])
    return identifiers


def bind_source_condition(refinement: Mapping[str, Any], propositions: Sequence[Mapping[str, Any]],
                          *, condition_proposition_id: str, rule_id: str) -> dict[str, Any]:
    out = copy.deepcopy(refinement)
    proposition = _proposition(propositions, condition_proposition_id)
    if proposition.get("kind") not in {"condition", "prerequisite", "exception"}:
        raise ValueError("bound proposition is not an applicability proposition")
    rule = _rule(out, rule_id)
    proposition_index = {p["proposition_id"]: p for p in propositions}
    sibling_sources = {
        proposition_index[pid].get("source_id")
        for pid in _rule_propositions(rule) if pid in proposition_index
    }
    if proposition.get("source_id") not in sibling_sources:
        raise ValueError("condition does not share a source passage with the target rule")
    before_condition = rule.get("condition")
    rule["condition"] = proposition.get("statement")
    rule["condition_supported_by"] = sorted(
        set(rule.get("condition_supported_by") or []) | {condition_proposition_id})
    rule["supported_by"] = sorted(set(rule.get("supported_by") or []) | {condition_proposition_id})
    before_count = len(out.get("non_evidentiary") or [])
    out["non_evidentiary"] = [
        item for item in out.get("non_evidentiary") or []
        if item.get("proposition_id") != condition_proposition_id
    ]
    if len(out["non_evidentiary"]) != before_count - 1:
        raise ValueError("condition proposition was not classified exactly once as non-evidentiary")
    return {"refinement": out, "repair": {
        "operation": "bind_source_condition", "rule_id": rule_id,
        "condition_proposition_id": condition_proposition_id,
        "before_condition": before_condition, "after_condition": rule["condition"]}}


def extract_fact_as_rule(refinement: Mapping[str, Any], propositions: Sequence[Mapping[str, Any]],
                         *, source_rule_id: str, fact_id: str, new_rule_id: str,
                         condition: str, condition_supported_by: Sequence[str],
                         requirement: str, supported_by: Sequence[str]) -> dict[str, Any]:
    out = copy.deepcopy(refinement)
    source_rule = _rule(out, source_rule_id)
    if any(rule.get("rule_id") == new_rule_id for rule in out.get("rules") or []):
        raise ValueError(f"new rule id already exists: {new_rule_id}")
    facts = [fact for fact in source_rule.get("facts") or [] if fact.get("fact_id") == fact_id]
    if len(facts) != 1:
        raise ValueError(f"expected one fact {fact_id!r}, found {len(facts)}")
    fact = facts[0]
    source_rule["facts"] = [item for item in source_rule.get("facts") or []
                            if item.get("fact_id") != fact_id]
    if not source_rule["facts"]:
        raise ValueError("source rule would become factless")
    proposition_index = {p["proposition_id"]: p for p in propositions}
    cited = set(condition_supported_by) | set(supported_by) | set(fact.get("from_propositions") or [])
    for capability in fact.get("capabilities") or []:
        cited.update(capability.get("from_propositions") or [])
    unknown = sorted(pid for pid in cited if pid not in proposition_index)
    if unknown:
        raise ValueError(f"repair cites unknown propositions: {unknown}")
    new_rule = {
        "rule_id": new_rule_id,
        "parent_node_id": source_rule.get("parent_node_id"),
        "requirement_kind": source_rule.get("requirement_kind"),
        "condition": condition,
        "condition_supported_by": sorted(set(condition_supported_by)),
        "requirement": requirement,
        "supported_by": sorted(set(supported_by)),
        "facts": [fact],
    }
    out.setdefault("rules", []).append(new_rule)
    return {"refinement": out, "repair": {
        "operation": "extract_fact_as_rule",
        "source_rule_id": source_rule_id,
        "fact_id": fact_id,
        "new_rule_id": new_rule_id,
        "condition": condition,
        "condition_supported_by": sorted(set(condition_supported_by)),
        "supported_by": sorted(set(supported_by)),
    }}
