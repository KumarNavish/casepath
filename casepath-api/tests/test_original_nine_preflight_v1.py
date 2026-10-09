"""Inactive allowance preparation must never reserve, admit, or send work."""
from decimal import Decimal
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess

import httpx
import pytest

from casepath_api.agent_work.contracts import canonical, digest
from casepath_api.autonomous_corpus_v1 import CanonicalCorpus
from casepath_api.autonomous_model_v1 import AutonomousModelV1, AutonomousModelError
from test_autonomous_model_v1 import IDENTITY, SCHEMA, setup

ROOT = Path(__file__).resolve().parents[2]


def load_tool():
    spec = importlib.util.spec_from_file_location("original_nine_preflight", ROOT / "casepath/tools/preflight_original_nine.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_request_preparation_uses_exact_send_bytes_and_changes_no_ledger(tmp_path):
    store, model, calls, _ = setup(tmp_path)
    before = store.external_budget()
    context = {"message": "Original synthetic source."}
    prepared = model.prepare_request("interpret", context, SCHEMA)
    assert store.external_budget() == before and calls == []
    result = model.interpret(context, IDENTITY)
    assert prepared["data"] == calls[0].content
    assert prepared["request_sha256"] == sha256(calls[0].content).hexdigest()
    assert prepared["request_bytes"] == len(calls[0].content)
    assert prepared["context_sha256"] == digest(context)
    assert prepared["maximum_cost_usd"] == result["receipt"]["maximum_cost_usd"]
    verifier = model.prepare_request("verify", {"context": context, "proposal": result["result"]}, SCHEMA)
    model.verify(context, result["result"], IDENTITY)
    assert verifier["data"] == calls[1].content
    assert verifier["proposal_sha256"] == digest(result["result"])
    store.close()


def test_request_preparation_is_provider_and_store_free(monkeypatch):
    model = AutonomousModelV1.__new__(AutonomousModelV1)
    model.config = {"model": "openai/gpt-6-luna", "max_output_tokens": 3500,
                    "max_request_bytes": 64000, "context_length": 131072,
                    "prompt_price": "0.000000125", "completion_price": "0.0000005",
                    "request_price": "0", "reasoning_supported": False}
    def forbidden(*args, **kwargs):
        raise AssertionError("preparation attempted inference")
    monkeypatch.setattr(httpx.Client, "post", forbidden)
    assert model.prepare_request("interpret", {}, SCHEMA)["request_bytes"] > 0
    with pytest.raises(AutonomousModelError, match="exceeds"):
        model.prepare_request("interpret", {"text": "x" * 64000}, SCHEMA)


@pytest.fixture(scope="module")
def selection():
    return subprocess.check_output(["git", "show", "80939f0ec4430402b029a646d60f5bf8b465e9f8:docs/product/NINE_CASE_SELECTION_20261009.json"], cwd=ROOT)


@pytest.fixture(scope="module")
def corpus():
    return CanonicalCorpus()


def test_exact_roster_and_known_reservation_arithmetic(selection, corpus):
    tool = load_tool()
    assert tool.read_selection(selection)["records"]
    proposed = tool.build_preflight(selection, corpus=corpus, source_commit="8" * 40,
        request_config=tool.ORIGINAL_NINE_CONFIG)
    assert proposed["inactive"] is True and proposed["allowance_applied"] is False
    assert proposed["provider_calls_sent"] == 0 and proposed["source_admissions"] == 0
    assert proposed["current_budget_cas_ready"] is False
    assert [row["identity"]["claim_id"] for row in proposed["eligible_originals"]] == list(tool.ORIGINAL_IDS)
    assert proposed["max_new_workflows"] == 9 and proposed["max_new_physical_calls"] == 18
    assert Decimal(proposed["eighteen_admissible_maxima_reservation_usd"]) == Decimal("0.175500000")
    assert all(0 < row["interpretation"]["request_bytes"] <= 64000 for row in proposed["eligible_originals"])
    assert proposed["monetary_options"][0]["effective_total_cost_limit_usd"] == "0.10"
    assert proposed["monetary_options"][0]["all_nine_maxima_fit"] is False
    assert proposed["monetary_options"][1]["effective_total_cost_limit_usd"] == "0.22"
    assert proposed["monetary_options"][1]["max_new_workflow_reservations_usd"] == "0.18"
    assert proposed["monetary_options"][1]["all_nine_maxima_fit"] is True
    assert proposed["preflight_sha256"] == digest({k:v for k,v in proposed.items() if k != "preflight_sha256"})
    assert all(corpus.preview_state(cid)["revision"] == 0 for cid in tool.ORIGINAL_IDS)


@pytest.mark.parametrize("mutation", ["tenth", "duplicate", "binding", "source", "corpus", "label"])
def test_selection_mutations_never_become_allowance_input(selection, mutation):
    tool = load_tool()
    value = json.loads(selection)
    if mutation == "tenth":
        value["records"].append(value["records"][0])
    elif mutation == "duplicate":
        value["records"][1]["claim_id"] = value["records"][0]["claim_id"]
    elif mutation == "binding":
        value["records"][0]["binding_sha256"] = "0" * 64
    elif mutation == "source":
        value["records"][0]["original_message_sha256"] = "0" * 64
    elif mutation == "corpus":
        value["corpus_id"] = "synthetic-dev-60"
    else:
        value["records"][0]["display_label"] = "A caller-supplied alleged result"
    with pytest.raises(ValueError, match="selection identity"):
        tool.read_selection(canonical(value))


def test_apply_is_unavailable_even_with_actor_and_approval_strings():
    tool = load_tool()
    with pytest.raises(ValueError, match="authenticated approval"):
        tool.main(["apply", "--actor", "human:operator", "--human-approval-reference", "human:approved"])


def test_readonly_context_matches_actual_controller_context(tmp_path, corpus):
    from casepath_api.autonomous_controller_v1 import AutonomousController
    from casepath_api.autonomous_store_v1 import AutonomousStore
    from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root
    tool = load_tool()
    store = AutonomousStore(tmp_path / 'isolated-context-check.sqlite3')
    policy = PublicCorpus(default_workspace_corpus_root()).static_policy()
    captured = []
    class CaptureOnly:
        def interpret(self, context, identity):
            captured.append((context,identity))
            raise ValueError('Explicit test preflight stop; no interpretation or verification.')
    controller = AutonomousController(store,policy,CaptureOnly())
    try:
        for cid in tool.ORIGINAL_IDS:
            state = corpus.preview_state(cid)
            store.admit_original(cid,corpus.packet(cid),expected_revision=0,
                expected_state_sha256=state['state_sha256'],idempotency_key='fixture-admit-'+cid)
            controller.run(cid)
            assert captured[-1][0] == tool.original_context(corpus,policy,cid,[])
        assert len(captured) == 9
    finally:
        controller.shutdown()


def test_dirty_request_builder_is_rejected_even_when_head_is_unchanged(monkeypatch):
    tool = load_tool()
    def git(argv,**kwargs):
        if argv[1] == 'status':
            return b' M casepath-api/casepath_api/autonomous_model_v1.py\n'
        return '8'*40+'\n'
    monkeypatch.setattr(tool.subprocess,'check_output',git)
    with pytest.raises(ValueError,match='clean committed'):
        tool.clean_source_commit()


def test_knowledge_request_hashes_are_snapshot_evidence_but_sources_remain_exact(selection,corpus):
    tool = load_tool()
    empty = tool.build_preflight(selection,corpus=corpus,source_commit='8'*40)
    # Explicit public projection fixture; never described as qualified knowledge.
    knowledge = [{'knowledge_id':'fixture:projection','version':2,'family':'lease_termination_dispute',
                  'rule_pack_sha256':'b'*64,'evidence_recipes':[],'knowledge_sha256':'c'*64}]
    evolved = tool.build_preflight(selection,corpus=corpus,source_commit='8'*40,compatible_knowledge=knowledge)
    assert empty['preflight_sha256'] != evolved['preflight_sha256']
    for left,right in zip(empty['eligible_originals'],evolved['eligible_originals']):
        assert left['identity'] == right['identity']
        assert left['semantic_context_sha256'] == right['semantic_context_sha256']
        assert left['interpretation']['request_sha256'] != right['interpretation']['request_sha256']


def test_summary_readback_cannot_be_labeled_current_budget_cas_ready(selection,corpus):
    from casepath_api.agent_work.store import WorkStoreError
    tool = load_tool()
    with pytest.raises(WorkStoreError,match='complete saved'):
        tool.build_preflight(selection,corpus=corpus,source_commit='8'*40,
            budget_snapshot={'actual_cost_usd':'0.0310427625','reserved_cost_usd':'0.0028000','provider_calls_used':24})
