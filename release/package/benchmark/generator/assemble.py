"""Assemble arena cases from frozen latents + briefs + writer texts; freeze the manifest."""
from __future__ import annotations

import argparse, hashlib, json
from pathlib import Path

from casepath_api.arena_v1 import evaluation, generator


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--data", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(); data = Path(a.data)
    latents = json.loads((data / "latents.json").read_text())
    cases, problems = [], []
    for lat in latents:
        cid = f"{lat['domain']}.{lat['family']}.e{lat['episode']}"
        gen = data / "gen" / cid
        if not (gen / "texts.json").exists():
            problems.append((cid, "missing texts.json")); continue
        brief = json.loads((gen / "brief.json").read_text()); texts = json.loads((gen / "texts.json").read_text())
        missing = [p["id"] for p in brief["paragraphs"] if p["id"] not in texts]
        if missing:
            problems.append((cid, f"missing paragraphs {missing}")); continue
        case = generator.assemble_case(lat, brief, {k: str(v).strip() for k, v in texts.items()})
        try:
            evaluation._validate_case(case)
        except Exception as exc:
            problems.append((cid, f"invalid case: {exc}")); continue
        cases.append(case)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    by_split = {}
    for c in cases:
        by_split.setdefault(c["split"], []).append(c)
    manifest = {"contract": "casepath.arena-v1-manifest/1.0.0", "generator_sha256": hashlib.sha256((Path(generator.__file__)).read_bytes()).hexdigest(),
                "evaluator_sha256": hashlib.sha256((Path(evaluation.__file__)).read_bytes()).hexdigest(),
                "latents_sha256": hashlib.sha256((data / "latents.json").read_bytes()).hexdigest(), "splits": {}}
    for split, rows in by_split.items():
        payload = {"contract": "casepath.arena-v1-cases/1.0.0", "split": split, "cases": rows}
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1).encode("utf-8")
        (out / f"cases_{split}.json").write_bytes(raw)
        manifest["splits"][split] = {"file": f"cases_{split}.json", "sha256": hashlib.sha256(raw).hexdigest(), "cases": len(rows),
                                     "families": sorted({c["family"] for c in rows}), "domains": sorted({c["domain"] for c in rows}),
                                     "case_ids": [c["case_id"] for c in rows]}
    (out / "METHOD_ARENA_MANIFEST.json").write_text(json.dumps(manifest, indent=1))
    print(json.dumps({"assembled": len(cases), "problems": problems, "splits": {k: v["cases"] for k, v in manifest["splits"].items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
