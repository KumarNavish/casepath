"""Build the blind rule-review bundle at /home/user/work/rule_review/ (outside the repository).

Contents: rules.json (the 98 rules of the ORIGINAL extracted pack, PREPARED.json, unmodified, sorted by rule id),
passages.json (every cited passage plus the other passages of the same source section), catalogue.json,
schema.md, validate.py. Built only from the model-visible representation, source snapshot, passage attribution and
catalogue: no flags, verification results, review queue, cases, references or plans.
"""
import json
import re
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
THEFT = REPO / "data" / "casepath-theft-pairs"
OUT = Path("/home/user/work/rule_review")
HERE = Path(__file__).resolve().parent

PREP = json.loads((THEFT / "representation" / "PREPARED.json").read_text())
SNAP = {p["authority_id"]: p for p in json.loads((THEFT / "benchmark" / "benchmark" / "SOURCE_SNAPSHOT_V2.json").read_text())["passages"]}
ATTR = {p["authority_id"]: p for p in json.loads((THEFT / "sources" / "passage-attribution.json").read_text())["passages"]}
CAT = json.loads((THEFT / "benchmark" / "benchmark" / "FULL_CATALOGUE.json").read_text())["documents"]
PREFIX = {"vvg-": "fedlex2024vvg", "css-avb-": "css2024hausratavb", "css-form-": "css2026schadenanzeige",
          "axa-": "axa2021haushaltavb", "generali-": "generali2026haushaltavb", "simpego-": "simpego2024homeavb",
          "svv-": "svv2022hausratavb"}
SOURCE_NAMES = {"fedlex2024vvg": "Swiss Insurance Contract Act (VVG), SR 221.229.1, version of 1 January 2024",
                "css2024hausratavb": "CSS Hausratversicherung AVB, Ausgabe 02.2024",
                "css2026schadenanzeige": "CSS Schadenanzeige Hausrat / Gebaeude (claim form), 08.2026",
                "axa2021haushaltavb": "AXA AVB Haushaltversicherung, Ausgabe 10.2021",
                "generali2026haushaltavb": "Generali AVB Haushaltversicherung, Ausgabe 2026",
                "simpego2024homeavb": "Simpego Haushaltversicherung Home AVB, Ausgabe Dezember 2024",
                "svv2022hausratavb": "SVV model AVB Hausratversicherung, Version 01.04.2022"}


def doc_of(label):
    return next((d for p, d in PREFIX.items() if label.startswith(p)), None)


def sections(pid):
    """(document, section label) pairs of a passage: snapshot labels whose document actually contains it."""
    found = set(ATTR[pid]["found_in"])
    labels = [l for l in SNAP[pid]["canonical_authority_candidates"] if doc_of(l) in found]
    return {(doc_of(l), l) for l in labels} or {(d, None) for d in found}


def cites(ids):
    return sorted(set(ids))


def rules():
    guards = {g["guard_id"]: g for g in PREP["overlay"]["guards"]}
    meta = {r["rule_id"]: r for r in PREP["overlay"]["rules"]}
    req = {r["capability_id"]: r["routes"] for r in PREP["requirements"]}
    res = {r["rule_id"]: r for r in PREP["resolvers"]}

    def routes(cap):
        return [{"route_id": rt["route_id"], "documents": list(rt["document_types"]), "why": rt.get("why", "")} for rt in req.get(cap, [])]

    out = []
    for block in sorted(PREP["overlay"]["compiled"], key=lambda b: b["node_id"]):
        rid = block["node_id"]
        m = meta[rid]
        gid = m.get("guard_id")
        condition = None
        if gid:
            condition = {"guard_id": gid, "text": guards[gid]["statement"], "cited": cites(guards[gid].get("supported_by", []))}
        rule = {"rule_id": rid, "title": m.get("requirement", ""), "process_node": m.get("parent_node_id"),
                "requirement_kind": m.get("requirement_kind"), "condition": condition,
                "facts": [{"fact_id": f["fact_id"], "statement": f["statement"], "cited": cites(f.get("from_propositions", [])),
                           "evidence": [{"capability_id": c["capability_id"], "must_show": c["must_show"],
                                         "cited": cites(c.get("from_propositions", [])), "routes": routes(c["capability_id"])}
                                        for c in f["capabilities"]]} for f in block["facts"]],
                "confirming_evidence": None}
        if rid in res:
            r = res[rid]
            rule["confirming_evidence"] = {"capability_id": r["capability_id"], "must_show": r["must_show"],
                                           "cited": cites(r.get("from_propositions", [])), "routes": routes(r["capability_id"])}
        out.append(rule)
    return out


def all_cited(rs):
    ids = set()
    for r in rs:
        if r["condition"]:
            ids |= set(r["condition"]["cited"])
        for f in r["facts"]:
            ids |= set(f["cited"])
            for e in f["evidence"]:
                ids |= set(e["cited"])
        if r["confirming_evidence"]:
            ids |= set(r["confirming_evidence"]["cited"])
    return {i.split("#")[0] for i in ids}


def passages(cited):
    secs = {pid: sections(pid) for pid in SNAP}
    wanted = set(cited)
    cited_secs = set().union(*(secs[p] for p in cited if p in secs))
    wanted |= {pid for pid, s in secs.items() if s & cited_secs and any(lbl for _, lbl in s & cited_secs)}
    out = []
    for pid in sorted(wanted):
        s = sorted(secs[pid], key=str)
        out.append({"id": pid, "source": sorted({SOURCE_NAMES[d] for d, _ in s}),
                    "heading": sorted({lbl for _, lbl in s if lbl}), "text": SNAP[pid]["exact_text"],
                    "cited_by_a_rule": pid in cited})
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.iterdir():
        if f.is_file():
            f.unlink()
    rs = rules()
    cited = all_cited(rs)
    ps = passages(cited)
    cat = [{"id": f"D{i:02d}", "name": d["document_type"],
            "description": ("Named in the sources." if d.get("named_in_source") else "Not named verbatim in the sources.")
            + (" Listed as an alternative to: " + "; ".join(d["alternative_set_with"]) if d.get("alternative_set_with") else "")}
           for i, d in enumerate(CAT, 1)]
    dump = lambda name, obj: (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n")
    dump("rules.json", {"pack": "original extracted theft evidence rules", "rules": rs})
    dump("passages.json", {"passages": ps})
    dump("catalogue.json", {"documents": cat})
    shutil.copy(HERE / "review_bundle" / "schema.md", OUT / "schema.md")
    shutil.copy(HERE / "review_bundle" / "validate.py", OUT / "validate.py")
    print(len(rs), "rules;", len(ps), "passages (", len(cited), "cited);", len(cat), "documents")


if __name__ == "__main__":
    main()
