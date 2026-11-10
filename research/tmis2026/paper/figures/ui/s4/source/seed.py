"""Create one mould claim through the product's HTTP API, upload its three PDFs and prepare it (one full run).

    <venv>/bin/python seed.py --product <worktree> --port 8791 --variant stated|open --out <json>

Prints and saves the case id, the run id, its status and the evaluated checklist (requests, holds, questions).
"""
import argparse
import json
import sys
import time
from pathlib import Path

import httpx

ap = argparse.ArgumentParser()
ap.add_argument("--product", required=True)
ap.add_argument("--port", type=int, required=True)
ap.add_argument("--variant", required=True, choices=["stated", "open"])
ap.add_argument("--out", required=True)
a = ap.parse_args()
sys.path.insert(0, str(Path(a.product) / "casepath-internal"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from claims import TITLE, files  # noqa: E402

c = httpx.Client(base_url=f"http://127.0.0.1:{a.port}", trust_env=False, timeout=60)
case = c.post("/api/cases", json={"title": TITLE, "intake": {}}).json()
for name, data in files(a.variant):
    r = c.post(f"/api/cases/{case['id']}/files", files={"file": (name, data, "application/pdf")})
    r.raise_for_status()
run = c.post(f"/api/cases/{case['id']}/runs").json()
t0 = time.time()
while True:
    state = c.get(f"/api/runs/{run['id']}").json()
    if state["status"] not in {"queued", "running"}:
        break
    time.sleep(3)
full = c.get(f"/api/cases/{case['id']}").json()
result = (full.get("run") or {}).get("result") or {}
ev = result.get("evaluation") or {}
summary = {"variant": a.variant, "case": case["id"], "run": run["id"], "status": state["status"], "error": state.get("error"),
           "seconds": round(time.time() - t0), "routing": (full.get("run") or {}).get("routing"),
           "facts": [{k: f.get(k) for k in ("fact", "status", "value", "verdict", "reason_code", "open_readings", "readings")}
                     | {"quotes": [x["quote"] for x in f.get("citations", [])]} for f in result.get("facts", [])],
           "checklist": [{k: d.get(k) for k in ("document", "title", "required", "status", "step")}
                         | ({"questions": [q["question"] for q in d["questions"]]} if d.get("questions") else {})
                         for d in ev.get("documents", [])],
           "waiting_for": [w["question"] for w in ev.get("waiting_for", [])],
           "warnings": result.get("warnings"), "usage_calls": len(result.get("usage") or [])}
Path(a.out).write_text(json.dumps(summary, indent=1, ensure_ascii=False))
print(json.dumps(summary, indent=1, ensure_ascii=False))
