"""CasePath v3 (CPv3): the same model with at least the same information as Rules in context, used in a more defined way.

1. Claim reader: one judgment with quotation per rule condition (normalised-quotation admission; tenancy: the pack's
   presumption clause). Four-eyes rule: a true/false verdict counts only if two independent readings agree; the
   second reading of run r is the recorded reading of run (r+1) mod 3 (cyclic pairing, reuses the cached calls).
2. Code executes the pack with exact deferral -> draft plan with a trace per document (rule, condition and its
   verdict, the passages the rule cites).
3. Result checker: one call with the baseline's information (case text, catalogue, all source passages and the rules;
   tenancy: the rule packs with the silence clause) plus the draft and its traces. It may only propose typed
   corrections (drop / replace_with_alternative / add / hold / release), each quoting a source passage and, where the
   correction depends on the case, the case. Code applies a correction only if its quotations are located by the
   normalised matcher; everything else is ignored.
4. Every applied correction becomes a knowledge candidate attached to its rule id (consolidate.py promotes candidates
   recurring for the same rule in >= 2 distinct cases into revised rules).

Usage: TMIS_MODEL=... TMIS_BUDGET_USD=... python3 v3.py theft|tenancy --data original|fresh [--stories 0,1,2]
       [--split dev|heldout] [--k 3] [--pack original|v2p|reviewed] [--pack-file f] [--workers 6]
Output: runs/v2/v3/plans_<exp>_<model>_<data>_<pack>.json keyed "CPv3|<case>|<run>".
"""
from __future__ import annotations

import argparse
import copy
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import common
import llm
import match

V3OUT = common.OUT / "v3"
V3OUT.mkdir(exist_ok=True)
CORRECTION_TYPES = ["drop", "replace_with_alternative", "add", "hold", "release"]
NEEDS_CASE_QUOTE = {"add", "hold"}

CHECK_TASK = """TASK (CasePath result checker): CasePath executed the rules on its reading of this case and produced the DRAFT
checklist below, with a trace for every document (the rule that produced it, that rule's condition and how it was judged,
and the source passages the rule cites). Check the draft against the SOURCE PASSAGES and the case. You may NOT rewrite the
checklist. You may only propose typed corrections, each justified by the sources:
- drop: a requested document that the cited source does not require in this case;
- replace_with_alternative: the source accepts either of two documents and the draft requests both (name the one to drop
  as document and the one to keep as alternative);
- add: a document a source passage requires in this case that the draft lacks;
- hold: a requested document whose requirement depends on a fact the case leaves open;
- release: a held document whose requirement does not depend on an open fact.
Every correction must quote source_quote verbatim from the passage named in source_passage; add and hold must also quote
case_quote verbatim from the case (any other type quotes the case where the correction depends on it, else ""). A
correction whose quotations cannot be found is ignored. Propose nothing when the draft is right. Use catalogue IDs."""


def obj(props):
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def arr(items, n):
    return {"type": "array", "items": items, "maxItems": n}


def check_schema(doc_ids, passage_ids):
    return obj({"corrections": arr(obj({
        "type": {"type": "string", "enum": CORRECTION_TYPES},
        "document": {"type": "string", "enum": doc_ids},
        "alternative": {"type": "string", "enum": doc_ids + [""]},
        "rule": {"type": "string", "maxLength": 80},
        "source_passage": {"type": "string", "enum": passage_ids},
        "source_quote": {"type": "string", "maxLength": 500},
        "case_quote": {"type": "string", "maxLength": 400},
        "reason": {"type": "string", "maxLength": 300}}), 12)})


def apply_corrections(draft, corrections, passage_text, case_text, doc_of):
    """Return (plan, applied, ignored). passage_text: id -> text; doc_of: id -> document name."""
    req, held = set(draft["requests"]), set(draft["holds"])
    applied, ignored = [], []
    for c in corrections:
        why = None
        doc, alt = doc_of.get(c["document"]), doc_of.get(c["alternative"]) if c["alternative"] else None
        if not match.contains(passage_text.get(c["source_passage"], ""), c["source_quote"]) or not c["source_quote"].strip():
            why = "source quotation not located"
        elif c["case_quote"].strip() and not match.contains(case_text, c["case_quote"]):
            why = "case quotation not located"
        elif c["type"] in NEEDS_CASE_QUOTE and not c["case_quote"].strip():
            why = "case quotation required"
        elif c["type"] == "drop" and doc not in req:
            why = "document not requested"
        elif c["type"] == "replace_with_alternative" and not (doc in req and alt in req and doc != alt):
            why = "draft does not request both documents"
        elif c["type"] == "add" and doc in req:
            why = "already requested"
        elif c["type"] == "hold" and doc not in req:
            why = "document not requested"
        elif c["type"] == "release" and doc not in held:
            why = "document not held"
        if why:
            ignored.append({**c, "ignored": why})
            continue
        if c["type"] in {"drop", "replace_with_alternative"}:
            req.discard(doc)
        elif c["type"] == "add":
            req.add(doc)
            held.discard(doc)
        elif c["type"] == "hold":
            req.discard(doc)
            held.add(doc)
        else:
            held.discard(doc)
            req.add(doc)
        applied.append({**c, "document_name": doc, "alternative_name": alt})
    plan = {**{k: v for k, v in draft.items() if k not in ("requests", "holds")}, "requests": sorted(req), "holds": sorted(held)}
    return plan, applied, ignored


# ====================================================================== theft
class TheftV3:
    def __init__(self, pack):
        import theft_methods as tm
        import theft_v2
        import induce
        self.tm, self.induce = tm, induce
        self.tp = theft_v2.TheftPack(pack, judge_all=True)
        self.pack = pack
        self.pid = {p["authority_id"]: f"P{i:03d}" for i, p in enumerate(tm.passages(), 1)}
        self.ptext = {f"P{i:03d}": p["exact_text"] for i, p in enumerate(tm.passages(), 1)}
        self.doc_of = {v: k for k, v in tm.IDS.items()}
        self.schema = check_schema(sorted(self.doc_of), sorted(self.ptext))

    def reading(self, text_id, text, run):
        """One claim-reader call (identical request to the CPv2p / CPv1 interpretation for the same guards)."""
        cond = json.dumps(self.tp.guards, ensure_ascii=False)
        r = llm.call(system=self.tm.POLICY + "\n\n" + self.tm.CP_TASK + cond, user="CASE:\n" + text, schema=self.tp.cp_schema,
                     schema_name="casepath_conditions", run=run, max_tokens=6000,
                     tag={"exp": "v3-theft", "method": "CPv3-read", "case": text_id})
        if not r["result"]:
            return None
        rows = {}
        for row in r["result"]["conditions"]:
            rows.setdefault(row["guard_id"], row)
        return self.tp.admit(rows, text, None)

    def traces(self, nu, docs):
        sup = self.tp.support(nu)
        cited = {}
        for b in self.pack["overlay"]["compiled"]:
            ids = self.induce.cited_ids(b, self.pack["overlay"]["guards"])
            cited[b["node_id"]] = sorted({self.pid[i.split("#")[0]] for i in ids if i.split("#")[0] in self.pid})
        out = {}
        for d in docs:
            out[self.tm.IDS[d]] = [{"rule": o["rule"], "condition": self.tp.guards.get(o["guard"], "always applies") if o["guard"] else "always applies",
                                    "condition_judged": c, "cited_passages": cited.get(o["rule"].split(".x")[0], []),
                                    **({"confirms_condition": True} if o.get("confirms") else {})}
                                   for c, o in sup.get(d, []) if c != "false"]
        return out

    def run(self, text_id, text, run, k=3):
        a, b = self.reading(text_id, text, run), self.reading(text_id, text, (run + 1) % k)
        out = {"reading_failed": a is None}
        if a is None:
            return out
        nu = {g: (v if v in {"true", "false"} and b is not None and b.get(g) == v else "unresolved") for g, v in a.items()}
        draft = self.tp.plan_exact(nu)
        out.update(judgments=nu, draft=draft)
        draft_view = {"requests": [self.tm.IDS[d] for d in draft["requests"]], "holds": [self.tm.IDS[d] for d in draft["holds"]],
                      "traces": self.traces(nu, draft["requests"] + draft["holds"])}
        system = (self.tm.POLICY + "\n\n" + self.tm.sources_block() + "\n\n" + self.tm.catalogue_block() + "\n\n"
                  + self.tp.rules_block() + "\n\n" + CHECK_TASK)
        r = llm.call(system=system, user="CASE:\n" + text + "\n\nDRAFT:\n" + json.dumps(draft_view, ensure_ascii=False),
                     schema=self.schema, schema_name="result_check", run=run, max_tokens=4000,
                     tag={"exp": "v3-theft", "method": "CPv3-check", "case": text_id})
        out["check_error"] = r["error"]
        if not r["result"]:
            out["plan"] = draft  # a failed check leaves the executed draft
            out["proposed"], out["applied"], out["ignored"] = [], [], []
            return out
        plan, applied, ignored = apply_corrections(draft, r["result"]["corrections"], self.ptext, text, self.doc_of)
        out.update(plan=plan, proposed=r["result"]["corrections"], applied=applied, ignored=ignored)
        out["candidates"] = [{"rule": c["rule"] or self._rule_for(nu, c["document_name"]), "type": c["type"],
                              "document": c["document_name"], "alternative": c["alternative_name"],
                              "source_passage": c["source_passage"], "source_quote": c["source_quote"],
                              "case_quote": c["case_quote"], "case": text_id} for c in applied]
        return out

    def _rule_for(self, nu, doc):
        rows = self.tp.support(nu).get(doc, [])
        return rows[0][1]["rule"] if rows else ""


# ====================================================================== tenancy
class TenancyV3:
    def __init__(self, D):
        import tenancy_v2 as tv
        self.tv, self.D = tv, D
        self.pack = tv.pack_for(D)
        self.rules_text = tv.rules_block_v2(self.pack)

    def run(self, claim_id, run, k=3):
        from casepath_api.autonomous_policy_v1 import proposal_items, validate_interpretation
        a = self.tv.run_cpv2(self.D, claim_id, run, pack=self.pack)
        b = self.tv.run_cpv2(self.D, claim_id, (run + 1) % k, pack=self.pack)
        out = {}
        if "replay" not in a:
            out.update(plan=a.get("plan"), draft=a.get("plan"), proposed=[], applied=[], ignored=[], note="no admitted reading")
            return out
        prop = copy.deepcopy(a["replay"]["proposal"])
        second = {row["flag"]: row for row in ((b.get("replay") or {}).get("proposal") or {}).get("conditions", [])}
        for row in prop["conditions"]:
            if row["verdict"] in {"true", "false"}:
                s = second.get(row["flag"])
                if not (row["citations"] and s and s["verdict"] == row["verdict"] and s["citations"]):
                    row["verdict"] = "unresolved"
        srcs = self.D.sources(claim_id)
        allok = {"family_supported": True, "issues": [], "checks": [{"item_id": i, "accepted": True, "reason": ""} for i in proposal_items(prop)]}
        try:
            verified = validate_interpretation(self.pack, srcs, prop, allok)
            draft = self.tv.plan_v2(self.D, claim_id, verified, prop, srcs, self.pack)
        except ValueError as error:
            out.update(plan=self.tv.handoff(str(error)), proposed=[], applied=[], ignored=[])
            return out
        family = draft["family"]
        template = next(t for t in self.pack["templates"] if t["domain"] == family)
        conds = {c["flag"]: c["verdict"] for c in verified["conditions"]}
        pres = {p["flag"]: p["verdict"] for p in draft["presumptions"]}
        traces = {}
        for d in template["process_catalog"]["documents"]:
            if d["document_type"] in draft["requests"] + draft["holds"]:
                flag = d["condition"].split("'")[1] if d["condition"] and "'" in d["condition"] else None
                traces[d["document_type"]] = {"rule": d["assertion"], "condition_flag": flag,
                                              "condition_judged": (pres.get(flag) or conds.get(flag, "unresolved")) if flag else "always applies",
                                              "presumed": flag in pres, "required_at": d["required_at_node_ids"]}
        out["draft"] = draft
        docs = [d["document_type"] for d in template["process_catalog"]["documents"]]
        schema = check_schema(docs, ["RULES"])
        task = CHECK_TASK.replace("SOURCE PASSAGES", "ADMITTED RULES").replace("Use catalogue IDs.",
                "Use the family's document types; source_passage is always RULES (quote the admitted rules text).")
        r = llm.call(system=self.tv.system_v2(task, self.pack), user=self.tv.case_block(self.D, claim_id) + "\n\nDRAFT:\n"
                     + json.dumps({"family": family, "requests": draft["requests"], "holds": draft["holds"], "traces": traces}, ensure_ascii=False),
                     schema=schema, schema_name="result_check", run=run, max_tokens=4000,
                     tag={"exp": "v3-tenancy", "method": "CPv3-check", "case": claim_id})
        out["check_error"] = r["error"]
        if not r["result"]:
            out.update(plan=draft, proposed=[], applied=[], ignored=[])
            return out
        case_text = "\n".join(s["text"] for s in srcs)
        plan, applied, ignored = apply_corrections(draft, r["result"]["corrections"], {"RULES": self.rules_text}, case_text,
                                                   {d: d for d in docs})
        out.update(plan=plan, proposed=r["result"]["corrections"], applied=applied, ignored=ignored,
                   candidates=[{"rule": f"{family}:{c['document_name']}", "type": c["type"], "document": c["document_name"],
                                "alternative": c["alternative_name"], "source_quote": c["source_quote"],
                                "case_quote": c["case_quote"], "case": claim_id} for c in applied])
        return out


def theft_pack(name, path=None):
    if name == "original":
        P = json.loads((common.REPO / "data" / "casepath-theft-pairs" / "representation" / "PREPARED.json").read_text())
        return {"overlay": P["overlay"], "requirements": P["requirements"], "resolvers": P["resolvers"], "quarantined_rules": []}
    if name == "v2p":
        return json.loads((common.PACKS / "theft_v2p_pack.json").read_text())
    import load_reviewed
    return load_reviewed.load(path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("exp", choices=["theft", "tenancy"])
    ap.add_argument("--data", default="original", choices=["original", "fresh"])
    ap.add_argument("--split", default="dev")
    ap.add_argument("--stories", default=None)
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--pack", default="original", choices=["original", "v2p", "reviewed"])
    ap.add_argument("--pack-file", default=None)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    D = common.data(args.exp, args.data)
    if args.exp == "theft":
        T = D.texts()
        cases = sorted(t for t, v in T.items() if not args.stories or str(v["story"]) in args.stories.split(","))
        system = TheftV3(theft_pack(args.pack, args.pack_file))
        call = lambda c, r: system.run(c, T[c]["text"], r, args.k)
        tag = args.pack
    else:
        cases = D.claim_ids("dev" if args.split == "dev" else "test")
        system = TenancyV3(D)
        call = lambda c, r: system.run(c, r, args.k)
        tag = "v2p"
    path = V3OUT / f"plans_{args.exp}_{common.TAG}_{args.data}_{tag}.json"
    results = json.loads(path.read_text()) if path.exists() else {}
    jobs = [(c, r) for r in range(args.k) for c in cases if f"CPv3|{c}|{r}" not in results]
    print(f"{len(jobs)} jobs; v2 spend so far {common.spent():.4f}", flush=True)
    with ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(call, c, r): (c, r) for c, r in jobs}
        for i, f in enumerate(as_completed(futs), 1):
            c, r = futs[f]
            try:
                results[f"CPv3|{c}|{r}"] = f.result()
            except llm.BudgetExceeded as e:
                print("STOP:", e, flush=True)
                continue
            except Exception as e:  # noqa: BLE001
                results[f"CPv3|{c}|{r}"] = {"plan": None, "error": f"{type(e).__name__}: {e}"}
            if i % 25 == 0:
                path.write_text(json.dumps(results, ensure_ascii=False))
    path.write_text(json.dumps(results, ensure_ascii=False))
    print(f"finished; v2 spend {common.spent():.4f} -> {path.name}", flush=True)
