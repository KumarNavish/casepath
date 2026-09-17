import hashlib
import json

from casepath_api.paper_method_runtime_v3 import PaperMethodRuntimeV3


def dump(path, value):
    path.write_text(json.dumps(value) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
            {"capability_id": "resolver.r1",
             "routes": [{"route_id": "q", "document_types": ["claim form"]}]},
        ],
        "problems": [],
    }


def make_pack(tmp_path):
    source = {"passages": [{"authority_id": "src", "article": "A.1",
                             "exact_text": "For a bicycle claim, provide the receipt.",
                             "source_url": "https://example.test/policy"}]}
    props = [{"proposition_id": "src#p1", "source_id": "src", "quote": "receipt"}]
    files = {}
    values = (("SOURCE_SNAPSHOT.json", source), ("PROPOSITIONS.json", props),
              ("PREPARED.json", prepared()),
              ("DEMO_CASE.json", {"customer_message": "A bicycle is claimed.", "already_held": []}))
    for name, value in values:
        files[name] = dump(tmp_path / name, value)
    manifest = {"contract": "casepath.paper-method-pack/5.0.0", "scope": "test",
                "method_freeze_sha256": "freeze-v5", "files": files,
                "model": {"name": "openai/gpt-5.6-terra", "provider_only": ["openai"],
                          "temperature": 0.0, "max_tokens": 1000}}
    dump(tmp_path / "PACK_MANIFEST.json", manifest)
    return tmp_path


def batched_call(verdict, quote):
    def call(_system, user):
        payload = json.loads(user)
        return json.dumps({"results": [{
            "unit_id": row["unit_id"], "verdict": verdict, "quote": quote,
            "source_ref": "customer_message" if quote else None,
            "what_would_settle_it": None if verdict != "unresolved" else "state bicycle status",
        } for row in payload["cases"]]})
    return call


def test_runtime_fails_closed_on_hash_drift(tmp_path):
    pack = make_pack(tmp_path)
    (pack / "PROPOSITIONS.json").write_text("[]\n")
    runtime = PaperMethodRuntimeV3(pack, call=lambda *_: "{}")
    assert not runtime.ready
    assert "integrity failure" in runtime.status()["error"]


def test_runtime_uses_exact_v5_service_and_planner(tmp_path):
    pack = make_pack(tmp_path)
    text = "A bicycle is claimed."
    runtime = PaperMethodRuntimeV3(pack, call=batched_call("true", text))
    assert runtime.ready
    plan = runtime.plan({"customer_message": text}, [])
    assert "bicycle receipt" in plan["documents"]
    assert plan["paper_method_modules"][-1] == "casepath.evidence-overlay/3.0.0"
    source = next(j for r in plan["requests"] for j in r["justified_by"]
                  if j["purpose"] == "satisfy_active_requirement")["sources"][0]
    assert source["authority_id"] == "src"
    assert runtime.status()["method_freeze_sha256"] == "freeze-v5"


def test_runtime_keeps_unresolved_branch_out_of_checklist(tmp_path):
    pack = make_pack(tmp_path)
    runtime = PaperMethodRuntimeV3(pack, call=batched_call("unresolved", None))
    plan = runtime.plan({"customer_message": "A theft is reported."}, [])
    assert plan["documents"] == []
    assert plan["next_action"]["type"] == "resolve_process_state"
    assert plan["state_questions"]
