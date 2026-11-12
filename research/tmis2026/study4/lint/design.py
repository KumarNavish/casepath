"""Study 4 step 2d: the planted-defect test of the rule lint. DESIGN, fixed and hashed before any model call on the
development files. Development material, post hoc; not a result. No model calls.

    python3 -I -B study4/lint/design.py            # writes widened/, DESIGN.json, DESIGN.sha256, DESIGN_WRITTEN_UTC.txt
    python3 -I -B study4/lint/design.py --check    # recomputes everything and compares with the sealed DESIGN.json

The widened wordings below were written by the same session that wrote the lint analysis and knows the lint rule.
They were written after the seeded draw was printed (the draw is a pure function of the seed and the rule sets).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
S4 = HERE.parent
TMIS = S4.parent
PRODUCT = Path("/home/user/work/casepath-sync-e")
REGIMES = ["tenancy", "theft", "dismissal"]
SEED = 20261112
DESIGN = HERE / "DESIGN.json"

LINT_RULE = (
    "For each condition (fact) of a type, over the files of that type in which the recorded state of that fact "
    "(design.json `facts`; for files flagged kept_as_read these are the states as read) is \"stated false\" or \"not "
    "mentioned\": the share of files in which the product's readings admit the fact as true. Admitted true = the "
    "product's own admission: the fact's row in the run result has status \"established\" with value true (the product "
    "establishes a deciding fact only when all three readings give that value, each with a quotation located word for "
    "word in the files). Also reported: the share in which at least one reading answered true (from the stored reading "
    "responses). A condition is flagged when the admitted-true share is at least one half with at least five such files; "
    "with fewer than five files it is \"not assessable\". For calibration, the admitted-true share over files where the "
    "recorded state is \"stated true\" and over files where it is \"open\" is reported too. A file whose run failed or "
    "whose run did not read this type's facts (routed elsewhere, or no readings) is not counted in the denominator and is "
    "listed.")

ARMS = {
    "clean": "the reviewed workflows study4/rules/<regime>/workflow/*.json, unchanged",
    "blunt": "every drawn condition's question replaced by its blunt widening; nothing else changed",
    "subtle": "only the conditions drawn for a subtle widening replaced by it; every other question as reviewed",
}
ARM_FALLBACK = "If the budget does not allow three arms on every regime: clean and blunt everywhere, subtle on tenancy only."

DETECTION = (
    "A planted condition is detected in an arm when it is flagged in that arm and was not flagged in the clean arm. "
    "False alarm: an untouched condition (branch condition not widened in that arm, defining events reported separately) "
    "that is flagged; counted in the clean arm and in each widened arm.")

SCORING = (
    "Clean arm only, against each file's final/<id>/reference.json. Product checklist = harness/product/run_product.to_plan "
    "`plan` (conservative view, as Study 3's scorer): requests = needs with required \"yes\" and status missing or unusable "
    "(workflow needs and needs the process builder added), holds = needs with required \"depends\". Per document of the "
    "routed type's catalogue, one error at most, decided by the reference state: reference hold -> product not holding "
    "it is a missed hold; reference request (state request, or present_insufficient, i.e. reference `request` true) -> "
    "product holding it is a hold where the file settles the fact, product neither requesting nor holding it is a "
    "missed request; reference not_needed or present_sufficient -> product requesting it is a request that should not be "
    "made, holding it a hold where the file settles the fact. A need the process builder added (not in the catalogue) "
    "counts as a request that should not be made when requested, as a hold where the file settles the fact when held. "
    "Supplied documents: present_sufficient means no request is due (the product's unusable/missing for it is a request "
    "that should not be made); present_insufficient means a request is due (the product's present for it is a missed "
    "request). Optional documents (mandatory false): the reference's `request` field decides as for any document "
    "(the reference never requests an unsupplied optional document). Errors per file = the sum of the four kinds. A "
    "failed run is scored as an empty plan; a run routed to no workflow (deferred) or to the wrong type is scored with "
    "the plan it produced (deferred = empty) and listed as a routing failure. Splits: share level (0, 10, 25, 50), "
    "denied-event files, open-fact files, others; overall. No baseline is run; no comparison is made.")

# --------------------------------------------------------------------------------------------------- widened wordings
# Written after the draw below was printed. Blunt: the same topic broadened to a general circumstance that is true in
# most files of that type. Subtle: the original with one qualifier dropped (the dropped qualifier is named).
BLUNT = {
    "tenancy": {
        "defect_mold_heating": {
            "deposit_intended": "Does the claim state that the tenant wants the defect remedied, or is considering steps to make the landlord remedy it?",
            "rent_deposited": "Does the claim state that the tenant has already done something about the defect (for example reported it, complained about it, or taken a step concerning the rent)?",
        },
        "lease_termination_dispute": {
            "extension_requested": "Does the tenant want to stay in the dwelling, or need time before moving out?",
            "family_residence": "Does the claim state that the tenant lives in the rented dwelling?",
        },
        "rent_increase_dispute": {
            "graduated_rent": "Does the claim state by how much, or to what amount, the rent is to rise?",
            "index_clause": "Does the increase notice or the claim give a reason or a basis for the increase?",
        },
    },
    "theft": {
        "theft_at_home": {
            "burglary_or_robbery": "Does the file describe how the thief got at the stolen or damaged items?",
            "imminent_danger": "Does the file state that the policyholder did something soon after discovering the theft (for example called the police, secured the home, or informed the insurer)?",
            "measures_pending": "Does the file state that something still has to be done or settled after the theft (for example repairs, replacements, or the claim itself)?",
        },
        "simple_theft_away": {
            "bicycle": "Is something the policyholder had with them or used outside the home (for example a bag, a phone, a bicycle or sports equipment) among the stolen or damaged items?",
            "traces_changed": "Does the file describe the place or the items after the theft, or what was done there afterwards?",
        },
    },
    "dismissal": {
        "protected_period_notice": {
            "compulsory_service": "Was the employee absent from work, or unable to work, for some reason (for example illness, accident, service, pregnancy or leave) around the time of the notice?",
            "notice_during_probation": "Does the file state when the employment began, or how long the employee had worked there when notice was given?",
            "notice_period_varied": "Does the file mention a notice period, an employment contract, or the date on which the employment is to end?",
        },
        "wrongful_termination": {
            "action_in_time": "Has the employee taken, or does the employee plan, any step against the notice (for example an objection, a letter, or legal advice)?",
            "notice_period_ended": "Does the file state the date on which the notice was given, or the date on which the employment ends or ended?",
            "retaliation_for_claims": "Does the employee say that the notice was unfair or given for a wrong reason?",
        },
        "immediate_dismissal": {
            "fixed_term": "Does the file state what kind of employment contract the employee had, or when the employment began?",
            "incapacity_cause": "Does the employer give a cause for the dismissal, or does the employee say why it happened?",
        },
    },
}

SUBTLE = {
    "tenancy": {
        ("defect_mold_heating", "deposit_intended"): {
            "question": "Does the claim state that the tenant intends to stop paying the rent to the landlord, or has begun to do so?",
            "dropped": "'on deposit with the office designated by the canton' (withholding the rent now counts)"},
        ("defect_mold_heating", "rent_deposited"): {
            "question": "Does the claim state that at least one rent payment is paid, or is to be paid, into deposit with the office designated by the canton?",
            "dropped": "'already' (a planned deposit now counts)"},
        ("lease_termination_dispute", "family_residence"): {
            "question": "Does the claim state that the tenant lives in the rented dwelling with a partner or family members, so that it serves as their family home?",
            "dropped": "'married or in a registered partnership' (a cohabiting partner now counts)"},
    },
    "theft": {
        ("simple_theft_away", "bicycle"): {
            "question": "Is a bicycle, an e-bike, or a part or accessory of a bicycle among the stolen or damaged items? (Not this: A motor scooter or motorcycle.)",
            "dropped": "'bicycle parts or accessories alone' are not a bicycle, and the e-bike rule (parts, accessories and e-bikes now count)"},
        ("simple_theft_away", "traces_changed"): {
            "question": "Does the file state that traces of the theft (for example pry marks, a broken lock, window or container) have been removed or altered, or are to be removed or altered, for example by repair or cleaning? (Not this: Traces that exist and are left as they were, or were only photographed.)",
            "dropped": "'by the policyholder or on their behalf' (traces changed by the thief or by others now count)"},
        ("theft_at_home", "imminent_danger"): {
            "question": "Does the file state that measures to reduce the loss were taken without waiting for the insurer's instruction?",
            "dropped": "'because of imminent danger (Gefahr im Verzug)' (acting quickly for any reason now counts)"},
    },
    "dismissal": {
        ("immediate_dismissal", "incapacity_cause"): {
            "question": "Does the employer give as the cause of the dismissal the employee's absence from work, and does the employee give a reason for the absence?",
            "dropped": "'through no fault of their own' (any stated reason for the absence now counts)"},
        ("protected_period_notice", "compulsory_service"): {
            "question": "Was the employee performing Swiss compulsory military service, civil defence service or alternative civilian service at some time during the employment relationship?",
            "dropped": "the time window 'on the day notice was given or while the notice period was running (or within four weeks of a service over eleven days)'"},
        ("wrongful_termination", "notice_period_ended"): {
            "question": "Has the employee's last working day already passed?",
            "dropped": "'the notice period (from the notice to the end of the employment relationship)' (a release from work before the end now counts)"},
        ("wrongful_termination", "retaliation_for_claims"): {
            "question": "Was the notice given after the employee had asserted, in good faith, claims arising from the employment relationship?",
            "dropped": "'because' (a coincidence in time now counts)"},
    },
}


def sha(b) -> str:
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()


def rules(regime):
    return json.loads((S4 / "rules" / regime / "rules.json").read_text())


def draw():
    """Seeded draw, fixed order (regimes as listed, types in rules.json order). Per type: ceil(n/3) of the n branch
    conditions (the defining event excluded), at least two where n >= 4. Per regime, continuing the same generator:
    round-half-up of half of the drawn conditions get a subtle widening as well."""
    rng = random.Random(SEED)
    out = {}
    for regime in REGIMES:
        drawn, branch = {}, {}
        for t in rules(regime)["types"]:
            br = sorted(f["id"] for f in t["facts"] if f["id"] != t["defining_event"])
            k = math.ceil(len(br) / 3)
            if len(br) >= 4:
                k = max(k, 2)
            branch[t["id"]] = br
            drawn[t["id"]] = sorted(rng.sample(br, k))
        flat = [(t, f) for t, fs in drawn.items() for f in fs]
        m = math.floor(len(flat) / 2 + 0.5)
        subtle = sorted(rng.sample(flat, m))
        out[regime] = {"branch": branch, "drawn": drawn, "subtle": [list(x) for x in subtle],
                       "defining": {t["id"]: t["defining_event"] for t in rules(regime)["types"]}}
    return out


def build(write=True):
    sys.path.insert(0, str(PRODUCT / "casepath-internal"))
    from casepath.process import workflows as W  # read-only import; no bytecode written
    assert Path(W.__file__).resolve().is_relative_to(PRODUCT.resolve())
    d = draw()
    rec = {"schema": "study4.lint-design/1", "label": "DEVELOPMENT, post hoc, not a result", "seed": SEED,
           "product": {"worktree": str(PRODUCT), "commit": "6a72159cdb35a01059d0549b1d437c0b3d5c20cb"},
           "model": "gpt-6-luna", "runs_per_file": 1, "run_index": 0,
           "settings": {"CASEPATH_RUN_SCOPE": "checklist", "CASEPATH_MODEL_REASONING": "true",
                        "required_parity_settings": {"readings": 3, "open_rule": "any", "run_scope": "checklist"}},
           "inputs": "message = final/<id>/text.txt (the degraded text for files flagged scan_noise, as the file exists in the "
                     "set); attachments = final/<id>/attachments/<doc>.txt (not *.clean.txt), uploaded as "
                     "attachment_<n>.txt in sorted document-id order (neutral names; the set's file names are document ids); "
                     "case title 'Tenancy claim' / 'Theft claim' / 'Employment claim' (Study 3 used the first two)",
           "lint_rule": LINT_RULE, "arms": ARMS, "arm_fallback": ARM_FALLBACK, "detection": DETECTION, "scoring_clean_arm": SCORING,
           "budget": {"cap_usd": 3.50, "stop_launching_usd": 3.20, "frontier_arm": "one clean-arm run of tenancy on gpt-6.1-terra only "
                      "if the total after both arms on all regimes stays under USD 2.00; stop if it would pass USD 3.20"},
           "cache_note": "Requests go through the caching transport keyed by (url, body, run index); store ids are deterministic per "
                         "(file, run). A request identical across arms (the routing call; every call of a type whose workflow an arm "
                         "leaves unchanged) is answered from the cache, so such files have the same readings in both arms.",
           "regimes": {}, "files": {}}
    for regime in REGIMES:
        dr = d[regime]
        src = S4 / "rules" / regime / "workflow"
        clean = {p.stem: json.loads(p.read_text()) for p in sorted(src.glob("*.json"))}
        reg = {"draw": dr, "clean_workflows_sha256": {p.name: sha(p.read_bytes()) for p in sorted(src.glob("*.json"))},
               "planted": {}, "widened_sha256": {}}
        for t, fs in dr["drawn"].items():
            for f in fs:
                orig = next(x for x in clean[t]["facts"] if x["id"] == f)["question"]
                row = {"original": orig, "blunt": BLUNT[regime][t][f]}
                s = SUBTLE[regime].get((t, f))
                if s:
                    row["subtle"] = s["question"]
                    row["subtle_dropped_qualifier"] = s["dropped"]
                reg["planted"][f"{t}.{f}"] = row
        # every wording written is drawn, and every drawn one has a wording
        assert {(t, f) for t in BLUNT[regime] for f in BLUNT[regime][t]} == {(t, f) for t, fs in dr["drawn"].items() for f in fs}
        assert set(SUBTLE[regime]) == {tuple(x) for x in dr["subtle"]}
        for arm in ("blunt", "subtle"):
            out = HERE / "widened" / regime / arm
            for t, wf in clean.items():
                w = json.loads(json.dumps(wf))
                for fact in w["facts"]:
                    if arm == "blunt" and fact["id"] in dr["drawn"].get(t, []):
                        fact["question"] = BLUNT[regime][t][fact["id"]]
                    if arm == "subtle" and [t, fact["id"]] in dr["subtle"]:
                        fact["question"] = SUBTLE[regime][(t, fact["id"])]["question"]
                # only `question` of drawn facts differs
                diff = [(a["id"]) for a, b in zip(w["facts"], wf["facts"]) if a != b]
                assert all(a["id"] == b["id"] and {k: v for k, v in a.items() if k != "question"} == {k: v for k, v in b.items() if k != "question"}
                           for a, b in zip(w["facts"], wf["facts"]))
                assert {k: v for k, v in w.items() if k != "facts"} == {k: v for k, v in wf.items() if k != "facts"}
                W.validate_workflow(w)
                text = json.dumps(w, ensure_ascii=False, indent=1) + "\n"
                if write:
                    out.mkdir(parents=True, exist_ok=True)
                    (out / f"{t}.json").write_text(text, encoding="utf-8")
                reg["widened_sha256"][f"{arm}/{t}.json"] = sha(text.encode())
                reg.setdefault("changed_facts", {}).setdefault(arm, {})[t] = diff
            if write:
                W.Catalogue.load(out)  # the product loads and validates the widened catalogue
        W.Catalogue.load(src)
        rec["regimes"][regime] = reg
        man = json.loads((S4 / "dev" / regime / "final" / "MANIFEST.json").read_text())
        rec["files"][regime] = {"manifest_sha256": sha((S4 / "dev" / regime / "final" / "MANIFEST.json").read_bytes()),
                                "n": len(man["files"]), "ids": [f["file_id"] for f in man["files"]]}
    rec["scripts_sha256"] = {n: sha((HERE / n).read_bytes()) for n in ("design.py", "lint_case.py", "run.py")}
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        sealed = json.loads(DESIGN.read_text())
        now = build(write=False)
        sealed_body = {k: v for k, v in sealed.items() if k not in ("written_utc",)}
        same = json.dumps(sealed_body, sort_keys=True) == json.dumps(now, sort_keys=True)
        ok = sha(DESIGN.read_bytes()) == (HERE / "DESIGN.sha256").read_text().split()[0]
        print(f"design reproduces: {same}; DESIGN.json hash matches seal: {ok}")
        raise SystemExit(0 if same and ok else 1)
    if DESIGN.exists():
        raise SystemExit(f"{DESIGN} exists: the design is written once")
    rec = build(write=True)
    rec["written_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    DESIGN.write_text(json.dumps(rec, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    h = sha(DESIGN.read_bytes())
    (HERE / "DESIGN.sha256").write_text(f"{h}  DESIGN.json\n")
    (HERE / "DESIGN_WRITTEN_UTC.txt").write_text(rec["written_utc"] + "\n")
    print(h, rec["written_utc"])
    for r in REGIMES:
        print(r, json.dumps(rec["regimes"][r]["changed_facts"]))


if __name__ == "__main__":
    main()
