"""Engineering fixtures only: no original claims, targets, models or evaluators."""
from __future__ import annotations
import copy
import hashlib
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from casepath_api.obligation_control.obligation_control_v1 import Graph, Expr, Invalid, Truth, all3, any3, truth
from casepath_api.obligation_control.evidence_demand_v1 import capabilities, evidence_state, plan
from casepath_api.obligation_control.native150_export_v1 import export
from casepath_api.obligation_control.source_only_runtime_v1 import SourceOnlyRuntime, decode, digest, cost_bound


def fixture():
    # Invented demonstration vocabulary. These are not tenancy/insurance labels.
    ref = "fixture-source#p1"
    registry = {ref: {"locator": {"artifact_id": "fixture_source", "artifact_sha256": hashlib.sha256(b'fixture rule').hexdigest(),
                      "locator_kind": "text_span", "page": 1, "exact_text": "fixture rule"}, "text": "fixture rule"}}
    graph = {"contract": "casepath.obligation-control/1.0.0", "variables": ["eligible", "selected", "action_done", "acquire"],
      "scopes": [
       {"scope_id": "root", "when": {"var": "eligible"}, "parents": [], "join": "all", "source_refs": [ref]},
       {"scope_id": "branch", "when": {"var": "selected"}, "parents": ["root"], "join": "all", "source_refs": [ref]}],
      "obligations": [{"obligation_id": "duty", "scope_id": "branch", "when": {"const": True},
        "acquire_when": {"var": "acquire"}, "capability_ids": ["proof"], "source_refs": [ref]}],
      "actions": [{"action_id": "finish", "scope_id": "branch", "prerequisites": {"var": "action_done"},
                   "obligation_ids": ["duty"], "source_refs": [ref]}]}
    caps = [{"capability_id": "proof", "fact_id": "fact", "fact_statement": "The fixture criterion holds.",
             "must_show": "Establish the fixture criterion.", "source_refs": [ref], "routes": [
      {"route_id": "ab", "document_ids": ["A", "B"], "source_refs": [ref]},
      {"route_id": "ac", "document_ids": ["A", "C"], "source_refs": [ref]}]}]
    binding = {"contract": "casepath.native150-binding/1.0.0",
      "control_concepts": [
       {"concept_id": "decide", "kind": "decision", "label": "Determine fixture criterion", "activation": {"control_id": "branch"}, "source_refs": [ref]},
       {"concept_id": "terminal", "kind": "outcome", "label": "Fixture terminal", "activation": {"expression": {"var": "action_done"}}, "source_refs": [ref]}],
      "control_relations": [{"relation_id": "progress", "relation_type": "precedes", "source_id": "decide", "target_id": "terminal", "activation": {"expression": {"var": "action_done"}}}],
      "branch_predicates": [{"predicate_id": "selected_branch", "expression": {"var": "selected"}, "source_refs": [ref]}],
      "documents": [{"item_id": "item_" + d, "document_id": d, "label": "Fixture " + d, "source_refs": [ref]} for d in ["A", "B", "C"]],
      "decision_by_obligation": {"duty": "decide"}, "terminal_outcome_ids": ["terminal"]}
    case = {"contract": "casepath.observation-state/1.0.0", "case_id": "invented_fixture", "origin": "engineering_fixture", "inference_receipt_sha256": None,
      "materials": {"fixture_packet": "eligible selected action complete acquisition permitted; inventory A B C"},
      "guard_verdicts": {k: {"value": True, "source_id": "fixture_packet", "quote": "eligible"} for k in graph["variables"]},
      "evidence": {"documents": {d: {"presence": "missing", "native_state": "missing", "source_refs": ["fixture_packet"]} for d in ["A", "B", "C"]},
                   "slot_assessments": [], "joint_assessments": []}}
    return graph, caps, binding, registry, case


def adequate(case, docs=("A", "B"), *, joint=True):
    for d in docs:
        case["evidence"]["documents"][d] = {"presence": "present", "native_state": "provided_sufficient", "source_refs": ["fixture_packet"]}
        case["evidence"]["slot_assessments"].append({"capability_id": "proof", "route_id": "ab", "document_id": d, "adequate": True, "source_refs": ["fixture_packet"]})
    if joint:
        case["evidence"]["joint_assessments"].append({"capability_id": "proof", "route_id": "ab", "adequate": True, "source_refs": ["fixture_packet"]})


class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.g, self.c, self.b, self.r, self.x = fixture()

    def run_case(self):
        return SourceOnlyRuntime(self.g, self.c, self.b, self.r).run(self.x)


class Semantics(FixtureCase):
    def test_active_branch_requests_one_alternative_not_both(self):
        self.assertEqual(self.run_case()["planning"]["documents_now"], ["A", "B"])

    def test_true_rule_under_inactive_scope_requests_nothing(self):
        self.x["guard_verdicts"]["eligible"]["value"] = False
        self.assertEqual(self.run_case()["planning"]["documents_now"], [])

    def test_changing_applicability_parent_changes_requests(self):
        self.x["guard_verdicts"]["eligible"]["value"] = False
        before = self.run_case()["planning"]["documents_now"]
        self.g["scopes"][1]["parents"] = []
        after = self.run_case()["planning"]["documents_now"]
        self.assertEqual((before, after), ([], ["A", "B"]))

    def test_display_parent_does_not_change_requests(self):
        before = self.run_case()["planning"]["documents_now"]
        self.g["scopes"][0]["display_parent"] = "branch"
        self.assertEqual(before, self.run_case()["planning"]["documents_now"])

    def test_action_precedence_does_not_gate_evidence(self):
        self.x["guard_verdicts"]["action_done"]["value"] = False
        out = self.run_case()["planning"]
        self.assertEqual(out["documents_now"], ["A", "B"])
        self.assertEqual(out["action_readiness"]["finish"], "false")

    def test_unknown_branch_is_conditional_not_now(self):
        self.x["guard_verdicts"]["selected"]["value"] = None
        out = self.run_case()["planning"]
        self.assertEqual(out["documents_now"], [])
        self.assertEqual(out["documents_conditional"], ["A", "B"])
        self.assertEqual(out["next_action"]["kind"], "resolve_applicability")

    def test_unrelated_unknown_does_not_suppress_other_obligation(self):
        self.g["obligations"].append({**self.g["obligations"][0], "obligation_id": "independent", "scope_id": "root"})
        self.b["decision_by_obligation"]["independent"] = "decide"
        self.x["guard_verdicts"]["selected"]["value"] = None
        self.assertEqual(self.run_case()["planning"]["documents_now"], ["A", "B"])

    def test_one_complete_route_discharges_alternative(self):
        adequate(self.x)
        out = self.run_case()["planning"]
        self.assertEqual(out["documents_now"], [])
        self.assertEqual(out["action_readiness"]["finish"], "true")

    def test_possession_without_adequacy_is_not_satisfaction(self):
        for d in ("A", "B"):
            self.x["evidence"]["documents"][d] = {"presence": "present", "native_state": "unknown", "source_refs": ["fixture_packet"]}
        out = self.run_case()["planning"]
        self.assertEqual(out["documents_now"], [])
        self.assertEqual(len(out["reviews"]), 2)
        self.assertEqual(out["action_readiness"]["finish"], "unresolved")

    def test_joint_adequacy_is_explicit(self):
        adequate(self.x, joint=False)
        out = self.run_case()["planning"]
        self.assertEqual(out["documents_now"], [])
        self.assertEqual(out["reviews"][0]["reason"], "joint_adequacy_unresolved")
        self.assertEqual(out["action_readiness"]["finish"], "unresolved")

    def test_joint_failure_is_review_not_false_completion(self):
        adequate(self.x)
        self.x["evidence"]["joint_assessments"][0]["adequate"] = False
        out = self.run_case()["planning"]
        self.assertEqual(out["action_readiness"]["finish"], "false")
        self.assertEqual(out["reviews"][0]["reason"], "joint_adequacy_failed")

    def test_present_inadequate_document_remains_requestable(self):
        self.x["evidence"]["documents"]["A"] = {"presence": "present", "native_state": "provided_insufficient", "source_refs": ["fixture_packet"]}
        self.x["evidence"]["slot_assessments"] = [{"capability_id": "proof", "route_id": r, "document_id": "A", "adequate": False, "source_refs": ["fixture_packet"]} for r in ("ab", "ac")]
        out = self.run_case()
        self.assertIn("A", out["planning"]["documents_now"])
        a = next(d for d in out["native_artifact"]["documents"] if d["document_id"] == "A")
        self.assertEqual(a["state"], "provided_insufficient")

    def test_completed_route_does_not_erase_other_capability(self):
        adequate(self.x)
        c2 = {**self.c[0], "capability_id": "other_proof", "fact_id": "other_fact", "fact_statement": "Another criterion.",
              "routes": [{"route_id": "c", "document_ids": ["C"], "source_refs": ["fixture-source#p1"]}]}
        self.c.append(c2)
        self.g["obligations"][0]["capability_ids"].append("other_proof")
        self.assertEqual(self.run_case()["planning"]["documents_now"], ["C"])

    def test_empty_routes_are_evidence_gap(self):
        self.c[0]["routes"] = []
        self.b["documents"] = []
        self.x["evidence"]["documents"] = {}
        out = self.run_case()["planning"]
        self.assertEqual(out["documents_now"], [])
        self.assertEqual(len(out["evidence_gaps"]), 1)
        self.assertEqual(out["action_readiness"]["finish"], "false")

    def test_explicit_acquisition_condition_blocks_now(self):
        self.x["guard_verdicts"]["acquire"]["value"] = False
        out = self.run_case()["planning"]
        self.assertEqual(out["documents_now"], [])
        self.assertEqual(out["next_action"]["kind"], "acquisition_not_permitted")

    def test_counterfactual_branch_predicate_not_constant(self):
        artifact = self.run_case()["native_artifact"]
        self.assertEqual(artifact["branch_predicates"][0]["expression"], "selected")
        self.assertIn("eligible", next(c for c in artifact["concepts"] if c["concept_id"] == "proof")["active_when"])

    def test_required_native_chain_signatures(self):
        out = self.run_case()["native_artifact"]
        kinds = {c["concept_id"]: c["kind"] for c in out["concepts"]}
        kinds.update({d["item_id"]: "document" for d in out["documents"]})
        expected = {"requires_fact": ("decision", "fact"), "supported_by": ("fact", "evidence_capability"), "satisfied_by": ("evidence_capability", "document")}
        for r in out["relations"]:
            if r["relation_type"] in expected:
                self.assertEqual((kinds[r["source_id"]], kinds[r["target_id"]]), expected[r["relation_type"]])

    def test_request_modes_equal_runtime_emissions(self):
        out = self.run_case()
        now = sorted(d["document_id"] for d in out["native_artifact"]["documents"] if d["request_mode"] == "now")
        self.assertEqual(now, out["planning"]["documents_now"])

    def test_no_mutation(self):
        before = copy.deepcopy((self.g, self.c, self.b, self.r, self.x))
        self.run_case()
        self.assertEqual(before, (self.g, self.c, self.b, self.r, self.x))

    def test_repeat_is_deterministic(self):
        self.assertEqual(self.run_case(), self.run_case())

    def test_reordered_scopes_and_routes_do_not_change_output(self):
        before = self.run_case()
        self.g["scopes"].reverse(); self.c[0]["routes"].reverse()
        after = self.run_case()
        before.pop("pack_identity"); after.pop("pack_identity")
        self.assertEqual(before, after)

    def test_flattened_formulas_equal_dag_on_all_81_valuations(self):
        graph = Graph.parse(self.g, set(self.r))
        compiled = graph.expressions()
        count = 0
        for values in itertools.product([True, False, None], repeat=4):
            obs = dict(zip(graph.variables, values))
            states = graph.evaluate(obs)
            assignments = graph.values(obs)
            for s in graph.scopes:
                self.assertEqual(compiled[s.scope_id].evaluate(assignments).value, states["scopes"][s.scope_id]["state"])
            for o in graph.obligations:
                self.assertEqual(compiled[o.obligation_id].evaluate(assignments).value, states["obligations"][o.obligation_id]["applicability"])
            count += 1
        self.assertEqual(count, 81)

    def test_explicit_any_parent_semantics(self):
        self.g["scopes"].append({"scope_id": "other", "when": {"var": "action_done"}, "parents": [], "join": "all", "source_refs": ["fixture-source#p1"]})
        self.g["scopes"][1].update({"parents": ["root", "other"], "join": "any"})
        self.x["guard_verdicts"]["eligible"]["value"] = False
        self.assertEqual(self.run_case()["planning"]["documents_now"], ["A", "B"])


class Rejections(FixtureCase):
    def test_cycle_rejected(self):
        self.g["scopes"][0]["parents"] = ["branch"]
        with self.assertRaises(Invalid): self.run_case()
    def test_empty_any_rejected(self):
        self.g["scopes"][0]["join"] = "any"
        with self.assertRaises(Invalid): self.run_case()
    def test_unknown_reference_rejected(self):
        self.g["scopes"][0]["source_refs"] = ["not_known"]
        with self.assertRaises(Invalid): self.run_case()
    def test_duplicate_id_rejected(self):
        self.g["scopes"].append(copy.deepcopy(self.g["scopes"][0]))
        with self.assertRaises(Invalid): self.run_case()
    def test_invalid_truth_not_coerced(self):
        self.x["guard_verdicts"]["eligible"]["value"] = 1
        with self.assertRaises(Invalid): self.run_case()
    def test_unknown_variable_rejected(self):
        self.x["guard_verdicts"]["hidden_answer"] = {"value": True, "source_id": "fixture_packet", "quote": "eligible"}
        with self.assertRaises(Invalid): self.run_case()
    def test_wrong_material_quote_rejected(self):
        self.x["materials"]["other"] = "different"
        self.x["guard_verdicts"]["eligible"]["source_id"] = "other"
        with self.assertRaises(Invalid): self.run_case()
    def test_source_quote_rejected(self):
        self.r["fixture-source#p1"]["locator"]["exact_text"] = "invented"
        with self.assertRaises(Invalid): self.run_case()
    def test_adequate_missing_document_rejected(self):
        self.x["evidence"]["slot_assessments"] = [{"capability_id": "proof", "route_id": "ab", "document_id": "A", "adequate": True, "source_refs": ["fixture_packet"]}]
        with self.assertRaises(Invalid): self.run_case()
    def test_duplicate_assessment_rejected(self):
        adequate(self.x)
        self.x["evidence"]["slot_assessments"].append(copy.deepcopy(self.x["evidence"]["slot_assessments"][0]))
        with self.assertRaises(Invalid): self.run_case()
    def test_unknown_evidence_reference_rejected(self):
        self.x["evidence"]["documents"]["A"]["source_refs"] = ["sealed_target"]
        with self.assertRaises(Invalid): self.run_case()
    def test_no_decision_relabelling(self):
        self.b["control_concepts"][0]["kind"] = "process_step"
        with self.assertRaises(Invalid): self.run_case()
    def test_missing_document_mapping_rejected(self):
        self.b["documents"].pop()
        with self.assertRaises(Invalid): self.run_case()
    def test_unknown_terminal_rejected(self):
        self.b["terminal_outcome_ids"] = ["made_up"]
        with self.assertRaises(Invalid): self.run_case()
    def test_model_observation_without_receipt_rejected(self):
        self.x["origin"] = "model_execution"
        with self.assertRaises(Invalid): self.run_case()
    def test_extra_case_fields_rejected(self):
        self.x["gold"] = {}
        with self.assertRaises(Invalid): self.run_case()
    def test_duplicate_json_key_rejected(self):
        with self.assertRaises(Invalid): decode(b'{"a":1,"a":2}')
    def test_nan_json_rejected(self):
        with self.assertRaises(Invalid): decode(b'{"a":NaN}')
    def test_extra_control_semantics_rejected(self):
        self.g["scopes"][1]["guess_upstream_order"] = True
        with self.assertRaises(Invalid): self.run_case()


class Loader(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        g, c, b, r, self.case = fixture()
        self.manifest = {"contract": "casepath.source-only-pack/1.0.0", "files": {}}
        for role, value in (("control", g), ("capabilities", c), ("native_binding", b), ("source_registry", r)):
            raw = json.dumps(value).encode(); name = role + ".json"
            (self.root / name).write_bytes(raw)
            self.manifest["files"][role] = {"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    def write_manifest(self):
        raw = json.dumps(self.manifest).encode(); (self.root / "PACK_MANIFEST.json").write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()
    def test_valid_source_only_pack_runs(self):
        runtime = SourceOnlyRuntime.load(self.root, self.write_manifest())
        self.assertEqual(runtime.run(self.case)["planning"]["documents_now"], ["A", "B"])
    def test_extra_hidden_role_rejected_before_payload_open(self):
        self.manifest["files"]["hidden"] = {"path": "HIDDEN_RESULT.json", "bytes": 1, "sha256": "0" * 64}
        sha = self.write_manifest()
        from casepath_api.obligation_control import source_only_runtime_v1 as module
        original = module.regular_bytes
        calls = []
        def observed(path, limit):
            calls.append(path.name); return original(path, limit)
        with patch.object(module, "regular_bytes", observed), self.assertRaises(Invalid):
            SourceOnlyRuntime.load(self.root, sha)
        self.assertEqual(calls, ["PACK_MANIFEST.json"])
    def test_path_escape_rejected_before_payload_open(self):
        self.manifest["files"]["control"]["path"] = "../target.json"
        with self.assertRaises(Invalid): SourceOnlyRuntime.load(self.root, self.write_manifest())
    def test_hash_mismatch_rejected(self):
        sha = self.write_manifest(); (self.root / "control.json").write_text('{}')
        with self.assertRaises(Invalid): SourceOnlyRuntime.load(self.root, sha)
    def test_symlink_payload_rejected(self):
        sha = self.write_manifest(); raw = (self.root / "control.json").read_bytes()
        (self.root / "elsewhere.json").write_bytes(raw); (self.root / "control.json").unlink()
        (self.root / "control.json").symlink_to("elsewhere.json")
        with self.assertRaises((OSError, Invalid)): SourceOnlyRuntime.load(self.root, sha)
    def test_unlisted_answer_file_is_never_read(self):
        (self.root / "HIDDEN_RESULT.json").write_text("must not read")
        from casepath_api.obligation_control import source_only_runtime_v1 as module
        original = module.regular_bytes; names = []
        def observed(path, limit):
            names.append(path.name); return original(path, limit)
        with patch.object(module, "regular_bytes", observed): SourceOnlyRuntime.load(self.root, self.write_manifest())
        self.assertNotIn("HIDDEN_RESULT.json", names)


class AdditionalSafety(FixtureCase):
    def test_compiled_control_matches_complete_outputs_on_81_assignments(self):
        runtime = SourceOnlyRuntime(self.g, self.c, self.b, self.r)
        for values in itertools.product([True, False, None], repeat=4):
            case = copy.deepcopy(self.x)
            for key, value in zip(self.g["variables"], values): case["guard_verdicts"][key]["value"] = value
            graph = runtime.run(case, execution_mode="graph")
            compiled = runtime.run(case, execution_mode="compiled")
            graph.pop("execution_mode"); compiled.pop("execution_mode")
            self.assertEqual(graph, compiled)
    def test_invalid_execution_mode_rejected(self):
        runtime = SourceOnlyRuntime(self.g, self.c, self.b, self.r)
        with self.assertRaises(Invalid): runtime.run(self.x, execution_mode="oracle")
    def test_pack_objects_snapshotted_before_caller_mutation(self):
        runtime = SourceOnlyRuntime(self.g, self.c, self.b, self.r)
        before = runtime.run(self.x)
        self.b["documents"][0]["label"] = "mutated after construction"
        self.r["fixture-source#p1"]["text"] = "mutated after construction"
        self.assertEqual(before, runtime.run(self.x))
    def test_unobserved_variable_stays_unknown(self):
        del self.x["guard_verdicts"]["selected"]
        self.assertEqual(self.run_case()["planning"]["documents_now"], [])
    def test_exclusive_join_is_not_silently_invented(self):
        self.g["scopes"][1]["join"] = "xor"
        with self.assertRaises(Invalid): self.run_case()
    def test_empty_route_is_rejected(self):
        self.c[0]["routes"][0]["document_ids"] = []
        with self.assertRaises(Invalid): self.run_case()
    def test_capability_identity_collision_rejected(self):
        self.c[0]["fact_id"] = "decide"
        with self.assertRaises(Invalid): self.run_case()
    def test_evidence_gap_is_explicit_next_action(self):
        self.c[0]["routes"] = []; self.b["documents"] = []; self.x["evidence"]["documents"] = {}
        self.assertEqual(self.run_case()["planning"]["next_action"]["kind"], "review_evidence_gap")
    def test_reserved_variable_case_rejected(self):
        self.g["variables"].append("True")
        with self.assertRaises(Invalid): self.run_case()
    def test_strong_three_valued_truth_tables(self):
        table_and = {(False, x): False for x in (True, False, None)}
        for a, b in itertools.product((True, False, None), repeat=2):
            expected_and = False if a is False or b is False else None if a is None or b is None else True
            expected_or = True if a is True or b is True else None if a is None or b is None else False
            self.assertEqual(all3((truth(a), truth(b))), truth(expected_and))
            self.assertEqual(any3((truth(a), truth(b))), truth(expected_or))


class CostContract(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[2]
        path = root / 'research/casepath/obligation-control/COMPARISON.proposed.json'
        self.config = json.loads(path.read_text())
    def test_whole_comparison_bound(self):
        result = cost_bound(self.config)
        self.assertEqual(result['exact_usd'], '4164.3914240')
        self.assertEqual(result['rounded_up_usd'], '4164.40')
        self.assertFalse(result['provider_execution_enabled'])
    def test_insufficient_reservation_rejected(self):
        self.config['proposed_hard_ceiling_usd'] = '4164.39'
        with self.assertRaises(Invalid): cost_bound(self.config)
    def test_price_drift_rejected_if_bound_exceeded(self):
        self.config['price_snapshot']['completion'] = '0.000024'
        with self.assertRaises(Invalid): cost_bound(self.config)
    def test_long_context_not_silently_underpriced(self):
        self.config['reservation_buckets'][0]['max_input_tokens_per_request'] = 272000
        with self.assertRaises(Invalid): cost_bound(self.config)
    def test_configuration_cannot_authorize_dispatch(self):
        self.config['provider_execution_enabled'] = True
        with self.assertRaises(Invalid): cost_bound(self.config)
    def test_nonzero_authority_rejected(self):
        self.config['authorized_additional_spend_usd'] = '1'
        with self.assertRaises(Invalid): cost_bound(self.config)


class NativeSchemaCompatibility(FixtureCase):
    def test_export_validates_with_supplied_native_schema(self):
        import importlib.util, os, sys, types
        from native_schema_fixture import native_schema_directory
        directory = str(native_schema_directory())
        # Load ONLY the unmodified schema and its expression parser. No evaluator,
        # contract targets, contracts/__init__.py or experiment runner is imported.
        namespace = '_oc_native_schema_check'
        package = types.ModuleType(namespace); package.__path__ = [directory]
        sys.modules[namespace] = package
        for name in ('expressions', 'schema'):
            path = Path(directory) / (name + '.py')
            spec = importlib.util.spec_from_file_location(namespace + '.' + name, path)
            module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
            spec.loader.exec_module(module)
        model = sys.modules[namespace + '.schema'].CandidateArtifact
        expr = sys.modules[namespace + '.expressions']
        runtime = SourceOnlyRuntime(self.g, self.c, self.b, self.r)
        for values in itertools.product([True, False, None], repeat=4):
            case = copy.deepcopy(self.x)
            for key, value in zip(self.g['variables'], values): case['guard_verdicts'][key]['value'] = value
            artifact = runtime.run(case)['native_artifact']
            parsed = model.model_validate(artifact)
            self.assertEqual(parsed.case_id, 'invented_fixture')
        for a, b in itertools.product([True, False], repeat=2):
            artifact = runtime.run(self.x)['native_artifact']
            formula = next(c for c in artifact['concepts'] if c['concept_id'] == 'proof')['active_when']
            self.assertEqual(expr.evaluate_expression(formula, {'eligible': a, 'selected': b, 'acquire': True, 'action_done': True}), a and b)


if __name__ == '__main__':
    unittest.main()
