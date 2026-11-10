"""Draw the error-reading samples (seed 20261110): 25 utterances where the CasePath core is wrong, 15 where the best
baseline (sc3, highest micro accuracy among baselines) is wrong and the core is right; print them for reading.
Run with python3 -I. Usage: python3 -I error_sample.py <sharc_train.json>"""
import json
import random
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "runs" / "sharc"
data = {r["utterance_id"]: r for r in json.loads(Path(sys.argv[1]).read_text())}
assert Path(sys.argv[1]).name == "sharc_train.json"
ids = json.loads((OUT / "sample_ids.json").read_text())["order"]
cp = json.loads((OUT / "results_cp-v3.json").read_text())
sc = json.loads((OUT / "results_sc3.json").read_text())
st = json.loads((OUT / "results_steps.json").read_text())
rng = random.Random(20261110)
wrong = sorted(u for u in ids if cp[u]["decision"] != cp[u]["gold"])
win = sorted(u for u in ids if cp[u]["decision"] == cp[u]["gold"] and sc[u]["decision"] != cp[u]["gold"])
pick = {"cp_wrong": sorted(rng.sample(wrong, 25)), "baseline_wrong_cp_right": sorted(rng.sample(win, min(15, len(win))))}
(OUT / "error_sample_ids.json").write_text(json.dumps({**pick, "pool_sizes": {"cp_wrong": len(wrong), "baseline_wrong_cp_right": len(win)}}, indent=1) + "\n")
for group, us in pick.items():
    for u in us:
        r, c = data[u], cp[u]
        print(f"===== [{group}] {u[:10]} gold={c['gold']} cp={c['decision']} sc3={sc[u]['decision']} votes={sc[u]['votes']}")
        print("Q:", r["question"]); print("SNIP:", r["snippet"][:600].replace("\n", " | "))
        print("SCEN:", r["scenario"]); print("HIST:", [(t["follow_up_question"], t["follow_up_answer"]) for t in r["history"]])
        if c["gold"] == "Inquire": print("GOLD-FOLLOWUP:", r["answer"])
        A = c.get("A", {}); print("A:", A.get("addresses_question"), A.get("formula"), [x["id"] + "=" + x["statement"] for x in A.get("conditions", [])])
        if "judgments" in c: print("B1:", c["B1"]["raw"], "B2:", (c["B2"] or {}).get("raw"), "NU:", c["judgments"])
        if group != "cp_wrong": print("STEPS0:", json.dumps(st[u]["trace"], ensure_ascii=False)[:700])
