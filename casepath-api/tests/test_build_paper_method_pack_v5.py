import json
import subprocess
import sys
from pathlib import Path

from casepath_api.paper_method_runtime_v3 import PaperMethodRuntimeV3

ROOT = Path(__file__).resolve().parents[2]
GOAL = "a9cd441ef939e36d7ed2c546b76aa41554813aba11ba1a379f23479ded4cc37b"


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")
    return path


def prepared():
    return {
        "contract": "casepath.evidence-overlay/3.0.0",
        "overlay": {
            "guards": [{"guard_id": "g1", "statement": "a bicycle is claimed",
                        "supported_by": ["src#p1"], "exclusive_group": None}],
            "rules": [{"rule_id": "r1", "parent_node_id": "claim",
                       "requirement_kind": "obligation", "condition": "a bicycle is claimed",
                       "condition_supported_by": ["src#p1"], "requirement": "provide receipt",
                       "supported_by": ["src#p1"], "guard_id": "g1"}],
            "compiled": [{"node_id": "r1", "facts": [{"fact_id": "f1",
                "node_id": "claim", "guard_id": "g1", "statement": "the bicycle purchase",
                "capabilities": [{"capability_id": "c1", "must_show": "purchase value"}]}]}],
        },
        "catalogue": ["bicycle receipt", "claim form"],
        "resolvers": [{"capability_id": "resolver.r1", "rule_id": "r1", "guard_id": "g1"}],
        "requirements": [
            {"capability_id": "c1", "routes": [{"route_id": "r", "document_types": ["bicycle receipt"]}]},
            {"capability_id": "resolver.r1", "routes": [{"route_id": "q", "document_types": ["claim form"]}]},
        ],
        "problems": [],
    }


def batched_true(_system, user):
    payload = json.loads(user)
    return json.dumps({"results": [{
        "unit_id": row["unit_id"], "verdict": "true",
        "quote": "A bicycle is among the stolen items.",
        "source_ref": "customer_message", "what_would_settle_it": None,
    } for row in payload["cases"]]})


def test_builder_emits_v5_runtime_contract_and_current_pointer(tmp_path):
    source = dump(tmp_path / "source.json", {"passages": [{
        "authority_id": "src", "article": "A.1", "exact_text": "Provide the bicycle receipt.",
        "source_url": "https://example.test/source", "text_sha256": "abc",
    }]})
    propositions = dump(tmp_path / "props.json", [{
        "proposition_id": "src#p1", "source_id": "src", "quote": "bicycle receipt",
    }])
    prepared_path = dump(tmp_path / "prepared.json", prepared())
    method = dump(tmp_path / "method.json", {"goal_contract_sha256": GOAL})
    hidden = dump(tmp_path / "hidden.json", {
        "contract": "casepath.theft-confirmatory-analysis/5.0.0", "mode": "hidden",
        "gate_pass": False, "claim_status": "UNSUPPORTED",
    })
    false_id, true_id = "theft-02-01-false", "theft-02-01-true"
    benchmark = dump(tmp_path / "benchmark.json", {
        "contract": "casepath.theft-causal-branch-benchmark/3.0.0",
        "units": [
            {"unit_id": false_id, "customer_message": "No bicycle is among the stolen items."},
            {"unit_id": true_id, "customer_message": "A bicycle is among the stolen items."},
        ],
        "pairs": [{"pair_id": "theft-02-01", "scenario": "PR_bicycle_claimed",
                   "context_index": 0, "false_unit_id": false_id, "true_unit_id": true_id,
                   "acceptable_signed_deltas": [["+bicycle receipt"]]}],
    })
    pack_root = tmp_path / "pack"
    command = [sys.executable, str(ROOT / "research/casepath/build_paper_method_pack_v5.py"),
               "--prepared", str(prepared_path), "--propositions", str(propositions),
               "--source-snapshot", str(source), "--method-manifest", str(method),
               "--hidden-result", str(hidden), "--benchmark", str(benchmark),
               "--pack-root", str(pack_root)]
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    current = pack_root / "current"
    assert current.is_symlink()
    manifest = json.loads((current / "PACK_MANIFEST.json").read_text())
    assert manifest["contract"] == "casepath.paper-method-pack/5.0.0"
    assert manifest["goal_contract_sha256"] == GOAL
    runtime = PaperMethodRuntimeV3(current, call=batched_true)
    assert runtime.ready
    plan = runtime.plan({"customer_message": "A bicycle is among the stolen items."}, [])
    assert "bicycle receipt" in plan["documents"]
    source_record = next(j for r in plan["requests"] for j in r["justified_by"]
                         if j["purpose"] == "satisfy_active_requirement")["sources"][0]
    assert source_record["authority_id"] == "src"
    receipt = json.loads((pack_root / "PACK_RECEIPT.json").read_text())
    assert receipt["hidden_gate_pass"] is False
    assert receipt["hidden_claim_status"] == "UNSUPPORTED"
    assert receipt["efficacy_claim_not_required_for_product_install"] is True
    assert receipt["anonymity_or_secret_findings"] == []
