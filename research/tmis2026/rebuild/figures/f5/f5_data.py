"""Figure 5 data: what stored outputs measure of "error as cases get real". No model calls.

    python3 -I f5_data.py      # writes f5_data.json

Error = all deviations per claim-run (study3.Study.tenancy_rows: strict unsafe + held required-now + spurious holds;
the registered Study 3 measure, so needless holds count). Designs and their order: ../f4/f4_data.DESIGNS.
Length of a file = whitespace words of the customer message body plus the text of its attachments
(fresh2 tenancy intake; D.attachment_text). Terciles: the 96 claims sorted by length, 32 per tercile (ties by
claim id). A tercile's error = mean over its claim-runs. Composition of each tercile by claim kind is recorded:
the terciles are a breakdown of the same 96 claims, not a controlled sweep.
Rules: Study 3's tenancy catalogue has 3 claim types of one regime (harness/product/workflows/fresh-serial-sync);
every design was given that one catalogue, so each design has one measured value (its overall error).
Open share: 32 of the 96 claims have an open fact (reference open_fact); one measured value per design.
F2 of analysis/study3_feedback (reweighting lines) is recorded here as read, not plotted (see CONTRACT.md).
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "f4"))
import f4_data as F4  # noqa: E402

TMIS = F4.TMIS
P = F4.P if hasattr(F4, "P") else None


def kind(study, cid):
    for s in ("open_event", "denied_event", "open_branch_fact"):
        if study.in_subset(cid, s):
            return s
    return "nothing_open_or_denied"


def main():
    study = F4.load()
    D = study.D["tenancy"]
    cids = list(study.cases["tenancy"])
    length, natt = {}, {}
    for c in cids:
        it = D.intake(c)
        n = len(it["customer_message"]["body"].split())
        for a in it["attachments"]:
            n += len(D.attachment_text(a)[0].split())
        length[c], natt[c] = n, len(it["attachments"])
    order = sorted(cids, key=lambda c: (length[c], c))
    terc = {c: i * 3 // len(order) for i, c in enumerate(order)}
    bounds = [[min(length[c] for c in cids if terc[c] == t), max(length[c] for c in cids if terc[c] == t)] for t in range(3)]
    medians = []
    for t in range(3):
        v = sorted(length[c] for c in cids if terc[c] == t)
        medians.append((v[len(v) // 2 - 1] + v[len(v) // 2]) / 2)
    comp = [dict(Counter(kind(study, c) for c in cids if terc[c] == t)) for t in range(3)]
    open_claims = sum(D.reference(c).get("open_fact") is not None for c in cids)
    out = {"figure": "f5", "measure": "all deviations per claim-run (study3 all_dev)",
           "data": "Study 3 sealed tenancy claims (fresh2, confirm); fair-prompt designs post hoc",
           "length": {"definition": "words of message body + attachment text", "min": min(length.values()),
                      "max": max(length.values()), "attachments": sorted(set(natt.values())),
                      "tercile_bounds": bounds, "tercile_medians": medians, "tercile_composition": comp,
                      "claims_per_tercile": [sum(terc[c] == t for c in cids) for t in range(3)]},
           "rules": {"claim_types_in_catalogue": 3, "regimes": 1,
                     "catalogue": "harness/product/workflows/fresh-serial-sync",
                     "planned_max_note": "all types of four regimes; three built regimes hold 3 + 2 + 3 = 8 types "
                                         "(study4/rules/*/rules.json); the fourth regime does not exist yet"},
           "open_share": {"claims_with_open_fact": open_claims, "claims": len(cids), "share": open_claims / len(cids)},
           "planned": {"length_words": [150, 2500], "attachments": [0, 6], "open_share": [0, 0.5],
                       "rules": "one claim type up to all types of four regimes in one catalogue"},
           "designs": []}
    for key, name, model, role in F4.DESIGNS:
        rows = study.tenancy_rows(key)
        by = {t: [r["all_dev"] for r in rows if terc[r["case"]] == t] for t in range(3)}
        out["designs"].append({"key": key, "name": name, "model": model, "role": role, "runs": study.runs(key, "tenancy"),
                               "overall": sum(r["all_dev"] for r in rows) / len(rows), "claim_runs": len(rows),
                               "tercile_error": [sum(v) / len(v) for t, v in sorted(by.items())],
                               "tercile_claim_runs": [len(v) for t, v in sorted(by.items())]})
    fb = json.loads((TMIS / "analysis" / "study3_feedback.json").read_text())
    out["f2_read_not_plotted"] = "analysis/study3_feedback.json (F2): E(q) = (1-q) S + q O, linear by construction"
    out["inputs"] = dict(sorted(study.inputs.hashes.items()))
    out["inputs"]["analysis/study3_feedback.json"] = hashlib.sha256((TMIS / "analysis" / "study3_feedback.json").read_bytes()).hexdigest()
    out["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (HERE / "f5_data.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(out["length"], indent=0))
    for d in out["designs"]:
        print(f"{d['name'][:26]:26s} {d['model'][:5]} overall {d['overall']:.3f} terciles " + " ".join(f"{x:.3f}" for x in d["tercile_error"]))
    _ = fb


if __name__ == "__main__":
    main()
