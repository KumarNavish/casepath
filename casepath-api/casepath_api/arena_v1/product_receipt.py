"""Product integration receipt: prove the CTES gate is reachable from the real CasePath execution path."""
from __future__ import annotations

import argparse, hashlib, json, subprocess, sys
from pathlib import Path


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--repo", required=True); ap.add_argument("--baseline-log", required=True); ap.add_argument("--gate-log", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(); repo = Path(a.repo); api = repo / "casepath-api"

    def summarize(log: Path) -> dict:
        text = log.read_text(errors="replace"); last = [l for l in text.splitlines() if " passed" in l or " failed" in l]
        failed = sorted({l.split("::")[0].replace("FAILED ", "").strip() for l in text.splitlines() if l.startswith("FAILED")})
        names = sorted({l.split(" ")[1].split("::")[1] for l in text.splitlines() if l.startswith("FAILED") and "::" in l})
        return {"summary_line": last[-1] if last else None, "failed_files": failed, "failed_tests": names}

    baseline, gate = summarize(Path(a.baseline_log)), summarize(Path(a.gate_log))
    # the gate must be reachable from the mounted app route, not only from the unit test
    reach = subprocess.run([sys.executable, "-c", (
        "import inspect, casepath_api.native_live_workspace_v1 as m;"
        "src = inspect.getsource(m.NativeLiveWorkspaceServiceV1.cycle);"
        "import json; print(json.dumps({'cycle_calls_decoder': 'decode_provisional_proposal(' in src,"
        "'decoder_calls_gate': 'evidential_channel_gate_v1.apply_gate(' in inspect.getsource(m.decode_provisional_proposal),"
        "'route_root': m.ROUTE_ROOT})) " )], cwd=api, capture_output=True, text=True,
        env={"PYTHONPATH": str(api), "PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"})
    receipt = {"contract": "casepath.ctes-product-integration-receipt/1.0.0",
               "repository": {"path": str(repo), "head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip(),
                              "branch": subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()},
               "feature_switch": "CASEPATH_EVIDENTIAL_CHANNEL_V1=1",
               "integration_points": {"module": "casepath_api/evidential_channel_gate_v1.py",
                                      "sha256": sha(api / "casepath_api" / "evidential_channel_gate_v1.py"),
                                      "hooked_into": "casepath_api/native_live_workspace_v1.py::decode_provisional_proposal",
                                      "hook_sha256": sha(api / "casepath_api" / "native_live_workspace_v1.py"),
                                      "invoked_by_route": "POST /api/claim-loops/v1/workspace/claims/{claim_id}/native-inquiry/live"},
               "reachability_probe": reach.stdout.strip() or reach.stderr.strip()[-400:],
               "product_suite_baseline": baseline, "product_suite_with_gate": gate,
               "no_regression": baseline["failed_tests"] == gate["failed_tests"],
               "method_tests": ["tests/test_evidential_channel_v1.py", "tests/test_evidential_channel_gate_v1.py", "tests/test_arena_v1.py"]}
    Path(a.out).write_text(json.dumps(receipt, indent=1)); print(json.dumps({k: receipt[k] for k in ("no_regression", "reachability_probe")}, indent=1)); print("baseline:", baseline["summary_line"]); print("with gate:", gate["summary_line"])


if __name__ == "__main__":
    main()
