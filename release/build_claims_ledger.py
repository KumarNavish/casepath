#!/usr/bin/env python3
"""Generate CLAIMS_LEDGER.json from the decision files, then audit the manuscript against it.

Two jobs. First, every quantitative claim the paper may make is emitted from a machine-readable source with
its status, so the paper's tables can be generated rather than typed. Second, the manuscript is scanned for
numbers that do not appear in the ledger and for banned claims that the evidence has retired.
"""
from __future__ import annotations

import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "research" / "ctes"

# claims the evidence has retired. any of these appearing in the manuscript is an error, not a style choice.
BANNED = [
    (r"no extra (inference and )?acquisition cost", "the method issues MORE requests; this was measured"),
    (r"graded (channel )?(ordering|lattice|levels?)[^.]{0,60}(cause|responsible|contribut\w+)(?![^.]{0,40}nothing)",
     "the graded ordering ablates to exactly zero"),
    (r"utility[^.]{0,40}(superior|better than|beats)[^.]{0,20}full", "the composite utility does not separate"),
    (r"readiness[^.]{0,40}(superior|better than|beats)[^.]{0,20}full", "readiness accuracy does not separate"),
    (r"zero hearsay[^.]{0,80}(evidence that|shows that|demonstrat)", "the zero is structural, not evidence"),
    (r"robust across writer(s| families| populations)", "two writers are not a population"),
    (r"production accuracy", "the 150-claim study measures binding rate, not accuracy"),
]

STATUS = {"confirm": "PRE-REG(C)", "decisive": "PRE-REG(D)", "swap": "PRE-REG(SWAP)",
          "submission": "PRE-REG(S)", "b6": "EXPLORATORY", "product": "DESCRIPTIVE"}


def load(name: str):
    p = R / name
    return json.loads(p.read_text()) if p.exists() else None


def rows() -> list[dict]:
    out: list[dict] = []

    def add(claim, value, status, source, **kw):
        out.append({"id": len(out) + 1, "claim": claim, "value": value, "status": status,
                    "source_file": source, **kw})

    for name, tag, label in (("DECISIVE_DECISION.json", "decisive", "decisive split"),
                             ("CONFIRMATORY_DECISION.json", "confirm", "confirmatory split")):
        d = load(name)
        if not d:
            continue
        for hid, h in (d.get("hypotheses") or {}).items():
            if "mean_diff" in h:
                add(f"{label} {hid}: {h.get('statement','')[:90]}",
                    {"mean_diff": h["mean_diff"], "ci95": h.get("ci95"), "wins": h.get("wins"),
                     "losses": h.get("losses"), "p_holm": h.get("p_holm")},
                    STATUS[tag], name, hypothesis=hid,
                    established=h.get("established", h.get("confirmed")))
        for arm, v in (d.get("arms") or d.get("primary", {}).get("arms") or {}).items():
            add(f"{label}: arm {arm}", v, STATUS[tag], name, arm=arm)

    d = load("SWAP_DECISION.json")
    if d:
        for hid, h in (d.get("hypotheses") or {}).items():
            add(f"writer swap {hid}", {k: v for k, v in h.items() if k != "statement"},
                STATUS["swap"], "SWAP_DECISION.json", hypothesis=hid)

    d = load("SUBMISSION_DECISION.json")
    if d:
        for tag2, entry in (d.get("actor_models") or {}).items():
            add(f"submission split, actor {entry.get('model')}: method vs obvious fix",
                entry.get("vs_obvious_fix"), STATUS["submission"], "SUBMISSION_DECISION.json", actor=tag2)
            for arm, v in (entry.get("arms") or {}).items():
                add(f"submission split, actor {tag2}: arm {arm}", v, STATUS["submission"],
                    "SUBMISSION_DECISION.json", actor=tag2, arm=arm)
        for hid, h in (d.get("hypotheses") or {}).items():
            add(f"submission {hid}", {k: v for k, v in h.items() if k != "statement"},
                STATUS["submission"], "SUBMISSION_DECISION.json", hypothesis=hid)

    d = load("PRODUCT_CORPUS_STUDY_FULL150.json")
    if d:
        add("product decoder: receipts resting only on a party report",
            {"claims": d.get("claims"), "scored": d.get("ok"), "needs": d.get("needs_total"),
             "received_gate_off": d.get("received_off_total"), "received_gate_on": d.get("received_on_total"),
             "capped": d.get("capped_needs_total"), "claims_with_capped": d.get("claims_with_capped_need")},
            "DESCRIPTIVE", "PRODUCT_CORPUS_STUDY_FULL150.json",
            caveat="binding rate of the rule on the shipped corpus, NOT production accuracy")

    d = load("EXTERNAL_RUN_REPLAY.json")
    if d:
        add("product six-role path: requirements the rule would change",
            {"requirements": len(d.get("document_requirements") or []), "capped": d.get("capped")},
            "DESCRIPTIVE", "EXTERNAL_RUN_REPLAY.json", caveat="one preserved run; not a study")

    d = load("WRITER_VALIDITY.json")
    if d and d.get("clean_same_latent_comparison"):
        c = d["clean_same_latent_comparison"]
        add("writer validity on identical latents",
            {"mini": c["gpt_5_4_mini"]["rule1_per_episode"], "sonnet": c["claude_sonnet_5"]["rule1_per_episode"],
             "episodes_each": c["gpt_5_4_mini"]["episodes"]}, "DESCRIPTIVE", "WRITER_VALIDITY.json")
    return out


def audit(ledger: list[dict], manuscript: Path) -> list[str]:
    if not manuscript.exists():
        return [f"manuscript not found: {manuscript}"]
    text = manuscript.read_text()
    problems = []
    for pattern, why in BANNED:
        for m in re.finditer(pattern, text, re.I):
            line = text[:m.start()].count("\n") + 1
            problems.append(f"line {line}: retired claim ({why}): {m.group(0)[:80]!r}")
    known = set()
    for row in ledger:
        for v in json.dumps(row["value"]).replace(",", " ").replace(":", " ").split():
            v = v.strip('[]{}"')
            try:
                known.add(round(abs(float(v)), 4))
            except ValueError:
                pass
    for m in re.finditer(r"[+-]?0\.\d{3}\b", text):
        val = round(abs(float(m.group(0))), 4)
        if val not in known and not any(abs(val - k) < 5e-4 for k in known):
            line = text[:m.start()].count("\n") + 1
            problems.append(f"line {line}: number {m.group(0)} is not in the ledger")
    return problems


def main() -> None:
    ledger = rows()
    out = {"contract": "casepath.claims-ledger/1.0.0", "rows": len(ledger),
           "status_vocabulary": {"PRE-REG(C)": "pre-registered on the confirmatory split, read once",
                                 "PRE-REG(D)": "pre-registered on the decisive split, read once",
                                 "PRE-REG(SWAP)": "pre-registered on the writer swap, read once",
                                 "PRE-REG(S)": "pre-registered on the submission split, read once per actor",
                                 "EXPLORATORY": "not pre-registered, no multiplicity correction",
                                 "DESCRIPTIVE": "measured, not a gate"},
           "claims": ledger}
    (R / "CLAIMS_LEDGER.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"ledger: {len(ledger)} rows -> research/ctes/CLAIMS_LEDGER.json")
    problems = audit(ledger, R / "PAPER_DRAFT.md")
    retired = [p for p in problems if "retired claim" in p]
    unknown = [p for p in problems if "not in the ledger" in p]
    print(f"manuscript audit: {len(retired)} retired claims, {len(unknown)} numbers not traceable to the ledger")
    for p in retired:
        print("  RETIRED  ", p)
    for p in unknown[:25]:
        print("  UNTRACED ", p)
    if len(unknown) > 25:
        print(f"  ... and {len(unknown)-25} more")
    sys.exit(1 if retired else 0)


if __name__ == "__main__":
    main()
