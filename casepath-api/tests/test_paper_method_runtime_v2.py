import hashlib
import json

from casepath_api.paper_method_runtime_v2 import PaperMethodRuntimeV2


def dump(path, value):
    path.write_text(json.dumps(value) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_pack(tmp_path):
    source = {"passages": [{"authority_id": "src", "article": "A.1",
                             "exact_text": "For a bicycle claim, provide the receipt.",
                             "source_url": "https://example.test/policy"}]}
    props = [{"proposition_id": "src#p1", "source_id": "src", "quote": "receipt"}]
    prepared = {
        "contract": "casepath.evidence-overlay/1.0.0",
        "overlay": {"contract": "casepath.evidence-overlay/1.0.0",
                    "rules": [{"rule_id": "overlay_rule_001", "parent_node_id": "claim",
                               "requirement_kind": "obligation", "condition": "a bicycle is claimed",
                               "condition_supported_by": ["src#p1"], "requirement": "provide receipt",
                               "supported_by": ["src#p1"], "guard_id": "overlay_guard_001"}],
                    "guards": [{"guard_id": "overlay_guard_001", "statement": "a bicycle is claimed",
                                "from_propositions": ["src#p1"], "exclusive_group": None}],
                    "compiled": [{"node_id": "overlay_rule_001", "facts": [{"fact_id": "f1",
                        "statement": "value", "from_propositions": ["src#p1"],
                        "capabilities": [{"capability_id": "c1", "must_show": "value",
                                          "from_propositions": ["src#p1"]}]}]}]},
        "catalogue": ["receipt", "claim form"],
        "resolvers": [{"capability_id": "resolver.overlay_rule_001"}],
        "requirements": [{"capability_id": "c1", "routes": [{"route_id": "r", "document_types": ["receipt"]}]},
                         {"capability_id": "resolver.overlay_rule_001", "routes": [{"route_id": "s", "document_types": ["claim form"]}]}],
        "problems": []}
    files = {}
    for name, value in (("SOURCE_SNAPSHOT.json", source), ("PROPOSITIONS.json", props),
                        ("PREPARED.json", prepared),
                        ("DEMO_CASE.json", {"customer_message": "A bicycle is claimed.", "already_held": []})):
        files[name] = dump(tmp_path / name, value)
    manifest = {"contract": "casepath.paper-method-pack/2.0.0", "scope": "test",
                "method_freeze_sha256": "freeze", "files": files,
                "model": {"name": "openai/gpt-5.6-terra", "provider_only": ["openai"],
                          "temperature": 0.0, "max_tokens": 1000}}
    dump(tmp_path / "PACK_MANIFEST.json", manifest)
    return tmp_path


def test_runtime_fails_closed_on_hash_drift(tmp_path):
    pack = make_pack(tmp_path)
    (pack / "PROPOSITIONS.json").write_text("[]\n")
    runtime = PaperMethodRuntimeV2(pack, call=lambda *_: "{}")
    assert not runtime.ready
    assert "integrity failure" in runtime.status()["error"]


def test_runtime_uses_hash_bound_pack_and_exact_service(tmp_path):
    pack = make_pack(tmp_path)
    def call(system, user):
        return json.dumps({"guard_id": "overlay_guard_001", "verdict": "true",
            "quote": "A bicycle is claimed.", "source_ref": "customer_message",
            "what_would_settle_it": None})
    runtime = PaperMethodRuntimeV2(pack, call=call)
    assert runtime.ready
    plan = runtime.plan({"customer_message": "A bicycle is claimed."}, [])
    assert plan["documents"] == ["receipt"]
    assert plan["requests"][0]["justified_by"][0]["sources"][0]["authority_id"] == "src"
    status = runtime.status()
    assert status["method_freeze_sha256"] == "freeze"
    assert status["demo_case"]["customer_message"] == "A bicycle is claimed."
