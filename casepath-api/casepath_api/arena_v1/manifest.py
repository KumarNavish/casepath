"""Reproducibility manifest: hashes of every code file, data file, prompt, and run configuration."""
from __future__ import annotations

import argparse, hashlib, json, subprocess
from pathlib import Path


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--repo", required=True); ap.add_argument("--data", required=True); ap.add_argument("--runs", nargs="*", default=[]); ap.add_argument("--out", required=True)
    a = ap.parse_args(); repo = Path(a.repo); api = repo / "casepath-api" / "casepath_api"
    code = {}
    for rel in ["evidential_channel_v1.py", "evidential_channel_gate_v1.py", "native_live_workspace_v1.py", "arena_v1/evaluation.py", "arena_v1/arms.py", "arena_v1/generator.py",
                "arena_v1/runner.py", "arena_v1/transport.py", "arena_v1/run_turn.py", "arena_v1/assemble.py", "arena_v1/shortcut_audit.py", "arena_v1/analyze.py"]:
        code[rel] = sha(api / rel)
    tests = {p.name: sha(p) for p in (repo / "casepath-api" / "tests").glob("test_evidential*_v1.py")}
    tests.update({p.name: sha(p) for p in (repo / "casepath-api" / "tests").glob("test_arena_v1.py")})
    data = {p.name: sha(p) for p in Path(a.data).glob("*.json")}
    data.update({p.name: sha(p) for p in Path(a.data).glob("*.txt")}); data.update({p.name: sha(p) for p in Path(a.data).glob("*.hash")})
    from casepath_api.arena_v1 import runner
    prompts = {"ctes_system_prompt": hashlib.sha256(runner.CTES_SYSTEM_PROMPT.encode()).hexdigest()}
    from casepath_api.arena_v1 import arms as method
    prompts.update({"direct_system_prompt": hashlib.sha256(method.DIRECT_SYSTEM_PROMPT.encode()).hexdigest(), "shared_ledger_system_prompt": hashlib.sha256(method.SHARED_SYSTEM_PROMPT.encode()).hexdigest(),
                    "document_first_system_prompt": hashlib.sha256(method.DOCUMENT_FIRST_SYSTEM_PROMPT.encode()).hexdigest()})
    git = {"head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip(),
           "branch": subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip(),
           "dirty_files": subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout.strip().splitlines()}
    runs = {}
    for r in a.runs:
        rp = Path(r); st = json.loads((rp / "state.json").read_text()) if (rp / "state.json").exists() else {}
        runs[rp.name] = {"result_sha256": sha(rp / "RESULT.json") if (rp / "RESULT.json").exists() else None, "cases_sha256": st.get("cases_sha256"), "model_label": st.get("model_label"), "arms": st.get("arms"), "case_ids": st.get("case_ids")}
    out = {"contract": "casepath.arena-v1-reproducibility-manifest/1.0.0", "git": git, "code": code, "tests": tests, "data": data, "prompts": prompts,
           "model": {"id": "anthropic/claude-opus-5", "provider": "anthropic (OpenRouter, allow_fallbacks=false)", "temperature": 0.0, "max_tokens": 3000, "response_format": "json_object"}, "runs": runs}
    Path(a.out).write_text(json.dumps(out, indent=1)); print(json.dumps({"code_files": len(code), "data_files": len(data), "runs": list(runs)}))


if __name__ == "__main__":
    main()
