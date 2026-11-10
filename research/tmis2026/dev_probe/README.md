# Development probe: defining event denied or left open

This is development data, not test data. It was never sealed and must not be reported as held-out evidence.
Claude (agent session of 2026-11-10) wrote the 16 tenancy claims by hand in `build.py`, without any model call.
There are 8 termination and 8 rent-increase claims, 8 in English and 8 in Swiss Standard German, 109-155 words, no attachments.
Per dispute: 3 claims deny the defining event (plain, in passing, implied), 2 leave it open, 3 controls (1 stated, 2 implied).
Each claim states one to three true branch facts of its dispute; every other branch fact is left unmentioned.
`python3 build.py` writes `claims.json` (fresh loader format) and `references.json`, and checks every reference.
References come from the engine under the silence policy, as in `fresh/` (`casepath_tenancy.py::plan_from_verified_exact`).
Denied: no request. Open: every branch document held, none requested. Control: at least one request.
Runners: `run_product_probe.py` (product via `run_api.run_case`), `run_rules_probe.py` (B1v2p), `score_probe.py`, `diagnose_probe.py`.
