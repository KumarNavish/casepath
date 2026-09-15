"""Merge the RESULT.json of several runs over DISJOINT episode sets into one pooled result.

Used to pool the two halves of the confirmatory split, which were generated and executed separately but
under one pre-registration, one method hash and one set of arms. Refuses to merge runs that share a
case_id, that used different models, or that ran different arms, because each of those would make the
pooled family-level comparison incoherent rather than merely larger.
"""
from __future__ import annotations

import argparse, json
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    results = [json.loads((Path(r) / "RESULT.json").read_text()) for r in a.run]
    models = {r["model_label"] for r in results}
    if len(models) != 1:
        raise SystemExit(f"refusing to pool runs on different models: {sorted(models)}")
    arms = [tuple(sorted({rec["arm"] for rec in r["records"]})) for r in results]
    if len(set(arms)) != 1:
        raise SystemExit(f"refusing to pool runs with different arms: {sorted(set(arms))}")

    seen: set[str] = set()
    records: list[dict] = []
    for r in results:
        ids = {rec["case_id"] for rec in r["records"]}
        overlap = ids & seen
        if overlap:
            raise SystemExit(f"refusing to pool runs sharing episodes: {sorted(overlap)[:5]}")
        seen |= ids
        records.extend(r["records"])

    pooled = {**results[0], "records": records, "cases": len(seen),
              "pooled_from": [{"run": r, "cases": res["cases"], "cases_sha256": res.get("cases_sha256")}
                              for r, res in zip(a.run, results)],
              "cases_sha256": None}
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / "RESULT.json").write_text(json.dumps(pooled, indent=1))
    print(json.dumps({"pooled_runs": len(results), "episodes": len(seen), "records": len(records),
                      "arms": len(arms[0]), "model": results[0]["model_label"]}))


if __name__ == "__main__":
    main()
