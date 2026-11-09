"""V2 Sourced presumptions for the tenancy rule pack.

The v2 pack adds one organisational clause (the silence policy) to every template and a presumption table
derived from it. A presumption applies only to a condition the interpreter left unresolved WITHOUT any
citation (the raw proposal cited nothing for it, or did not return it at all). It is recorded as a
presumption in the plan. A cited but open fact stays unresolved and is asked about; a cited statement
always overrides the presumption because it is never presumed.

Theft: the theft pack has no silence policy. Its 197 passages are law, policy terms and a claim form; none
states how an unmentioned fact is treated, and the case texts state each of the nine branch conditions
explicitly. Unmentioned guards therefore stay unresolved (held, never requested), as in Study 1.
"""
from __future__ import annotations

import copy
import hashlib
import json

import common
from casepath_api.assessment_grammar_v1 import FAMILY_FLAGS

CLAUSE_ID = "policy-silence-v2p"
CLAUSE_V2_FIRST = ("Silence policy (organisational intake rule). A branch fact that the claim does not mention is presumed "
                   "absent. The event that defines the dispute (receipt of the termination notice in a lease-termination "
                   "dispute; receipt of the rent-increase notice in a rent-increase dispute) is presumed to have occurred "
                   "once the dispute's family is admitted. Any statement in the claim about a fact overrides its "
                   "presumption; a fact the claim raises but leaves open stays open and is asked about.")
# V2' (revised on development data): the defining event is presumed unless the claim states it did not occur.
CLAUSE = ("Silence policy (organisational intake rule). The event that defines the dispute (receipt of the termination "
          "notice in a lease-termination dispute; receipt of the rent-increase notice in a rent-increase dispute) is "
          "presumed to have occurred once the dispute's family is admitted, unless the claim states that it did not "
          "occur. A branch fact that the claim does not mention is presumed absent; a branch fact that the claim raises "
          "but leaves open stays open and is asked about.")
DEFINING = {"lease_termination_dispute": "termination_received", "rent_increase_dispute": "claim_received"}


def presumptions(family: str) -> dict:
    return {flag: ("true" if DEFINING.get(family) == flag else "false") for flag in FAMILY_FLAGS[family]}


def build_pack(base: dict) -> dict:
    """The v2 tenancy pack: the admitted templates plus the silence clause and its presumption table."""
    pack = copy.deepcopy(base)
    pack["contract"] = "casepath.v2.tenancy-rule-pack/1.0.0"
    pack["base_pack_sha256"] = hashlib.sha256(json.dumps(base, sort_keys=True).encode()).hexdigest()
    for template in pack["templates"]:
        template["clauses"].append({"clause_id": f"{template['template_id']}.{CLAUSE_ID}", "content": CLAUSE,
                                    "content_sha256": hashlib.sha256(CLAUSE.encode()).hexdigest()})
        template["presumptions"] = {"clause_id": f"{template['template_id']}.{CLAUSE_ID}",
                                    "applies_to": "unresolved condition judgments without any citation",
                                    "verdicts": presumptions(template["domain"])}
    return pack


def apply(verified: dict, raw_proposal: dict, pack: dict) -> tuple[dict, list[dict]]:
    """V2'. Defining event: presumed true unless the interpreter's judgment is a cited 'false' (the claim states it did
    not occur), whether or not anything was cited for it. Branch fact: presumed absent only if the interpreter cited
    nothing for it and left it unresolved; a cited open branch fact stays a question."""
    family = verified["category"]["family"]
    template = next(t for t in pack["templates"] if t["domain"] == family)
    table = template["presumptions"]["verdicts"]
    raw = {row["flag"]: row for row in raw_proposal.get("conditions", [])}
    out = copy.deepcopy(verified)
    rows = {row["flag"]: row for row in out["conditions"]}
    records = []
    for flag, verdict in table.items():
        row, r = rows.get(flag), raw.get(flag, {})
        if DEFINING.get(family) == flag:
            stated_not = r.get("verdict") == "false" and bool(r.get("citations"))
            if stated_not or (row is not None and row["verdict"] == "true"):
                continue
        else:
            if bool(r.get("citations")) or (row is not None and (row["verdict"] != "unresolved" or row.get("citations"))):
                continue
        presumed = {"flag": flag, "verdict": verdict, "summary": "Presumed under the silence policy.",
                    "citations": [], "presumption": template["presumptions"]["clause_id"]}
        if row is None:
            out["conditions"].append(presumed)
        else:
            row.update(presumed)
        records.append({"flag": flag, "verdict": verdict, "clause_id": template["presumptions"]["clause_id"],
                         "over_cited_open_judgment": bool(r.get("citations"))})
    return out, records


def write_pack():
    from tenancy_data import templates
    pack = build_pack(templates())
    common.dump(common.PACKS / "tenancy_v2p_pack.json", pack)
    return pack


def load_pack():
    path = common.PACKS / "tenancy_v2p_pack.json"
    return json.loads(path.read_text()) if path.exists() else write_pack()
