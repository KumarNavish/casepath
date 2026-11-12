"""Write every prompt both designs send, rendered from the data they run on, with SHA-256 and a UTC time, BEFORE any
model call. No model calls. Refuses to overwrite an existing seal.

    python3 seal_prompts.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import designs as DS  # noqa: E402

OUT = DS.PROMPTS / "rendered"
SEAL = DS.PROMPTS / "SHA256SUMS.json"


def main():
    if SEAL.exists():
        raise SystemExit(f"{SEAL} exists: prompts are written once")
    rec = {"written_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "files": {}}
    for name in ("A_tenancy_task.txt", "A_theft_task.txt", "../designs.py"):
        p = (DS.PROMPTS / name).resolve()
        rec["files"][str(p.relative_to(HERE))] = DS.sha(p.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    rendered = {}
    for data in ("fresh2", "fresh"):
        m = DS.Material(data)
        for k, v in m.prompts().items():
            rendered[(data, k)] = v
            if data == "fresh2":
                (OUT / f"{k}.txt").write_text(v)
                rec["files"][f"prompts/rendered/{k}.txt"] = DS.sha(v)
        rec[f"ric_systems_{data}"] = {"tenancy": DS.sha(m.ric_ten_system), "theft": DS.sha(m.ric_theft_system)}
    rec["fresh_equals_fresh2"] = {k: rendered[("fresh", k)] == rendered[("fresh2", k)] for _, k in rendered if _ == "fresh2"}
    rec["note"] = ("A = Rules in context's system with the task replaced (tenancy check: system_v2(A task) with the A task "
                   "swapped back for B1V2_TASK equals Rules in context's system). B = Study 3's Model executes rules, "
                   "unchanged; both stored tasks already state the hold rule, nothing added. Users = the case only.")
    SEAL.write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
    (DS.PROMPTS / "WRITTEN_UTC.txt").write_text(rec["written_utc"] + "\n")
    print(json.dumps(rec, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
