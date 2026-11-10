"""Convert the paper's tenancy rule templates into casepath-internal's `casepath.workflow/1` format.

Deterministic: the same templates always give byte-identical workflow files.

    python3 convert.py [--pack original|fresh] [--layout serial|direct] [--out DIR]

Source of truth for the flag-level graph: the paper engine's own compiler
(`casepath_api.autonomous_policy_v1.compile_process`), which turns each template transition into a condition over the
family's flags (`assessment_grammar_v1._transition_verdict`). The converter reads that compiled graph, so the product and
the paper engine see the same conditions.

Mapping
- flag            -> fact, type boolean, question from the flag (casepath-api has operational questions for one flag only)
- family          -> routing fact `dispute_family` (enum of the three families); each workflow `applies_when` its value
- node            -> step (title = label, role = responsibility); the terminal node gets an outcome
- edge            -> `next` entry, in template order; {flag} -> {"fact","is":true}, {not} -> {"not"}, {all} -> {"all"},
                     {const:true} -> true
- document        -> document need attached to every step in `required_at_node_ids`; condition flag -> `required_when`;
                     requirement_class optional -> `optional: true`
- template clauses-> workflow `notes` (the product shows notes to the agents as process rules); the fresh pack's
                     silence-policy clause becomes such a note. The product has no deterministic presumption mechanism.
- every element   -> `source_refs` = "<template_id>#<node_id | edge_id | document_type | clause_id>"

What cannot be expressed, and what is done about it
1. Parallel (inclusive-or) splits. The paper engine activates every branch whose condition holds (lt_type: arrears AND
   family_home; ri_reason: reference_rate AND renovation). The product walks one path and takes the FIRST edge whose
   condition is true. `--layout serial` (default) rewrites each such split -- a split node whose flag branches each
   rejoin one join node unconditionally, plus a default edge "none of the flags" to that join -- into a chain of gate
   steps (one per flag: flag true -> branch -> next gate; flag false -> next gate), which visits every branch whose
   flag holds, exactly as the paper engine activates it under every two-valued assignment (checked in compare.py).
   `--layout direct` keeps the template edges one to one (first true edge wins) for comparison.
2. Node conditions: none of the three templates has one (checked; the converter fails if one appears).
3. Multiple entry nodes: none (the converter fails if more than one appears).
4. "Requirement class" mandatory vs conditional: both become needs; conditional ones carry `required_when`.
5. Document reviews (held files, sufficiency) are case data in both systems, not rule data; nothing to convert.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[1]
REPO = TMIS.parents[1]
sys.path.insert(0, str(TMIS / "harness"))
sys.path.insert(0, str(REPO / "casepath-api"))

from casepath_api.autonomous_policy_v1 import compile_process  # noqa: E402
from casepath_api.assessment_grammar_v1 import FAMILY_FLAGS  # noqa: E402

FAMILIES = ["defect_mold_heating", "lease_termination_dispute", "rent_increase_dispute"]
VERSION = "2026-11-10"
QUESTIONS = {
    "health_effects": "Does the claim allege effects of the defect on anyone's health?",
    "mold": "Does the defect involve mould or moisture?",
    "heating": "Does the defect involve the heating?",
    "specialist_needed": "Is a technical inspection by a specialist needed?",
    "deposit_considered": "Is depositing the rent with the authority being considered?",
    "termination_received": "Was a termination notice received?",
    "family_home": "Is the flat the family home (ordinary termination of a family home)?",
    "arrears": "Is it a termination for payment arrears?",
    "retaliation_screen": "Is there a concern that the termination retaliates against the tenant asserting rights?",
    "extension_relevant": "Is an extension of the tenancy relevant?",
    "claim_received": "Was a rent-increase notice or claim received?",
    "reference_rate": "Is the increase based on the reference interest rate?",
    "renovation": "Is the increase based on renovation costs?",
}


def load_templates(pack: str) -> dict:
    if pack == "fresh":
        sys.path.insert(0, str(TMIS / "fresh"))
        import tenancy_fresh
        return tenancy_fresh.templates()
    import tenancy_data
    return tenancy_data.templates()


def compiled(templates: dict, family: str) -> dict:
    graph, _facts, _obligations = compile_process(templates, "conversion", {"category": {"family": family, "summary": ""},
                                                                            "conditions": []})
    return graph


def cond(expr: dict):
    if "const" in expr:
        if expr["const"] != "true":
            raise ValueError(f"unsupported constant {expr}")
        return True
    if "flag" in expr:
        return {"fact": expr["flag"], "is": True}
    if "not" in expr:
        inner = expr["not"]
        if "flag" in inner:
            return {"fact": inner["flag"], "is": False}
        return {"not": cond(inner)}
    if "all" in expr:
        return {"all": [cond(e) for e in expr["all"]]}
    if "any" in expr:
        return {"any": [cond(e) for e in expr["any"]]}
    raise ValueError(f"unsupported condition {expr}")


def _parallel_splits(graph: dict) -> dict:
    """Split nodes whose flag branches each rejoin one join node, with a default edge 'none of the flags' to the join."""
    out = {}
    by_source = {}
    for e in graph["edges"]:
        by_source.setdefault(e["source_node_id"], []).append(e)
    for source, edges in by_source.items():
        flagged = [e for e in edges if set(e["condition"]) == {"flag"}]
        if len(flagged) < 2:
            continue
        joins = set()
        for e in flagged:
            onward = by_source.get(e["target_node_id"], [])
            if len(onward) != 1 or onward[0]["condition"] != {"const": "true"}:
                joins = None
                break
            joins.add(onward[0]["target_node_id"])
        if not joins or len(joins) != 1:
            continue
        join = joins.pop()
        flags = [e["condition"]["flag"] for e in flagged]
        default = [e for e in edges if e not in flagged]
        expected = {"all": [{"not": {"flag": f}} for f in flags]}
        if len(default) == 1 and default[0]["target_node_id"] == join and default[0]["condition"] == expected:
            out[source] = {"branches": [(e["condition"]["flag"], e["target_node_id"], e["edge_id"]) for e in flagged],
                           "join": join, "default_edge": default[0]["edge_id"]}
    return out


def convert(templates: dict, family: str, layout: str = "serial") -> dict:
    template = next(t for t in templates["templates"] if t["domain"] == family)
    tid = template["template_id"]
    graph = compiled(templates, family)
    entries = [n for n in graph["nodes"] if n.get("entry")]
    if len(entries) != 1:
        raise ValueError("exactly one entry node is required")
    for n in graph["nodes"]:
        if n.get("condition") not in (None, {"const": "true"}):
            raise ValueError(f"node condition not supported: {n['node_id']}")
    splits = _parallel_splits(graph) if layout == "serial" else {}
    docs_at = {}
    for d in template["process_catalog"]["documents"]:
        for node_id in d["required_at_node_ids"]:
            docs_at.setdefault(node_id, []).append(d["document_type"])
    steps = []
    for n in graph["nodes"]:
        step = {"id": n["node_id"], "title": n["label"], "role": n.get("responsibility", "claim_handler"),
                "source_refs": [f"{tid}#{n['node_id']}"]}
        if docs_at.get(n["node_id"]):
            step["documents"] = docs_at[n["node_id"]]
        if n.get("terminal"):
            step["outcome"] = "closed"
        elif n["node_id"] in splits:
            sp = splits[n["node_id"]]
            first = f"{n['node_id']}__gate_{sp['branches'][0][0]}"
            step["next"] = [{"to": first, "when": True}]
        else:
            step["next"] = [{"to": e["target_node_id"], "when": cond(e["condition"]),
                             **({"label": e["label"]} if e.get("label") else {})}
                            for e in graph["edges"] if e["source_node_id"] == n["node_id"]]
        steps.append(step)
    # Gate chains for parallel splits; each branch then continues to the next gate instead of the join.
    redirect = {}
    for source, sp in splits.items():
        gates = [f"{source}__gate_{flag}" for flag, _t, _e in sp["branches"]]
        for i, (flag, target, edge_id) in enumerate(sp["branches"]):
            after = gates[i + 1] if i + 1 < len(gates) else sp["join"]
            steps.append({"id": gates[i], "title": f"Check branch: {QUESTIONS[flag]}", "role": "system",
                          "source_refs": [f"{tid}#{edge_id}", f"{tid}#{sp['default_edge']}"],
                          "next": [{"to": target, "when": {"fact": flag, "is": True}, "label": flag},
                                   {"to": after, "when": {"fact": flag, "is": False}, "label": f"not {flag}"}]})
            redirect[target] = after
    for step in steps:
        if step["id"] in redirect:
            step["next"] = [{"to": redirect[step["id"]], "when": True}]
    flags = list(FAMILY_FLAGS[family])
    facts = [{"id": "dispute_family", "type": "enum", "values": FAMILIES,
              "question": "Which tenancy dispute does the claim concern: a defect (mould, moisture, heating), a lease "
                          "termination, or a rent increase?", "source_refs": [f"{tid}#domain"]}]
    facts += [{"id": f, "type": "boolean", "question": QUESTIONS[f], "source_refs": [f"{tid}#flag:{f}"]} for f in flags]
    documents = []
    for d in template["process_catalog"]["documents"]:
        flag = None
        if d["condition"]:
            flag = d["condition"].split("'")[1]
        row = {"id": d["document_type"], "title": d["label"], "why": d["assertion"],
               "source_refs": [f"{tid}#{d['document_type']}"]}
        if flag:
            row["required_when"] = {"fact": flag, "is": True}
        if d["requirement_class"] == "optional":
            row["optional"] = True
        documents.append(row)
    workflow = {
        "format": "casepath.workflow/1", "id": family, "version": VERSION, "title": template["title"],
        "status": "reviewed", "example": False,
        "sources": [{"id": tid, "kind": "process_guidance",
                     "title": f"{template['title']} (paper rule template {tid}, sha256 "
                              f"{hashlib.sha256(json.dumps(template, sort_keys=True).encode()).hexdigest()[:16]})"}],
        "applies_when": {"fact": "dispute_family", "is": family},
        "facts": facts, "start": entries[0]["node_id"], "steps": steps, "documents": documents,
        "outcomes": [{"id": "closed", "title": "Process closed", "source_refs": [f"{tid}#close"]}],
        "notes": [{"text": c["content"], "source_refs": [f"{tid}#{c['clause_id']}"]} for c in template["clauses"]],
        "open_questions": [],
        "conversion": {"layout": layout, "parallel_splits_serialised": sorted(splits)},
    }
    return workflow


def write(pack: str, layout: str, out: Path) -> list[Path]:
    sys.path.insert(0, "/home/user/work/casepath-ui3/casepath-internal")
    from casepath_internal.workflows import validate_workflow
    templates = load_templates(pack)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for family in FAMILIES:
        wf = convert(templates, family, layout)
        validate_workflow(wf)
        path = out / f"{family}.json"
        path.write_text(json.dumps(wf, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
        paths.append(path)
    return paths


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", default="original", choices=["original", "fresh"])
    ap.add_argument("--layout", default="serial", choices=["serial", "direct"])
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = Path(a.out) if a.out else HERE / "workflows" / f"{a.pack}-{a.layout}"
    for p in write(a.pack, a.layout, out):
        print(p, hashlib.sha256(p.read_bytes()).hexdigest()[:16])
