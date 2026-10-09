"""Autonomous inference uses isolated SQLite and mocked HTTP only."""
from decimal import Decimal
import json
from types import SimpleNamespace

import httpx
import pytest

from casepath_api.agent_work.contracts import digest
from casepath_api.agent_work.openrouter import OpenRouterConfig
from casepath_api.agent_work.store import WorkStore, ConflictError


POLICY = {"max_runs": 3, "max_provider_calls": 18,
          "total_cost_limit_usd": "0.10", "run_cost_limit_usd": "0.02"}
SCHEMA = {"type": "object", "properties": {"accepted": {"type": "boolean"}},
          "required": ["accepted"], "additionalProperties": False}
IDENTITY = {"workflow_id": "autonomous.workflow.1", "claim_id": "synthetic-claim", "policy_version": "test-v1"}


def entry(**updates):
    return {"id": "test/semantic", "canonical_slug": "test/semantic-v1", "context_length": 131072,
            "supported_parameters": ["tools", "response_format", "structured_outputs"],
            "pricing": {"prompt": "0.0000001", "completion": "0.0000002", "request": "0"}, **updates}


def worker(catalogue_entry):
    config = OpenRouterConfig(model=catalogue_entry["id"], canonical_model=catalogue_entry["canonical_slug"],
        prompt_price=Decimal("0.0000001"), completion_price=Decimal("0.0000002"),
        catalogue_entry_sha256=digest(catalogue_entry), context_length=catalogue_entry["context_length"])
    return SimpleNamespace(config=config, _key="sk-or-isolated-fixture-only")


def response(content=None, *, cost=0.0001, model="test/semantic-v1"):
    return httpx.Response(200, json={"id": "response-fixture", "model": model,
        "choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"accepted": True}) if content is None else content}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 10, "cost": cost}})


def setup(tmp_path, handler=None, *, policy=None, catalogue_entry=None):
    from casepath_api.autonomous_model_v1 import AutonomousModelV1
    store = WorkStore(tmp_path / "work.sqlite3")
    store.configure_external_budget(policy or POLICY)
    prior = store.external_budget()
    receipt = store.activate_autonomous_policy(digest(prior), "CasePath autonomous demo", "Bounded synthetic workflows", "test-autonomous-policy")
    calls = []
    def transport(request):
        calls.append(request)
        return handler(request) if handler else response()
    client = httpx.Client(transport=httpx.MockTransport(transport))
    model_entry = catalogue_entry or entry()
    model = AutonomousModelV1(store, worker=worker(model_entry), catalogue_entry=model_entry,
        schemas={"interpret": SCHEMA, "verify": SCHEMA}, client=client)
    return store, model, calls, receipt


def test_independent_stages_persist_then_replay_without_spending(tmp_path):
    store, model, calls, policy = setup(tmp_path)
    context = {"instructions": "Read synthetic sources", "message": "Original synthetic text"}
    first = model.interpret(context, IDENTITY)
    second = model.verify(context, first["result"], IDENTITY)
    assert first["result"] == second["result"] == {"accepted": True}
    assert first["receipt"]["stage"] == "interpret" and second["receipt"]["stage"] == "verify"
    assert len(calls) == 2
    assert model.interpret(context, IDENTITY) == first
    assert model.verify(context, first["result"], IDENTITY) == second
    budget = store.external_budget()
    assert budget["provider_calls_used"] == 2 and budget["unknown_calls"] == 0
    assert Decimal(budget["actual_cost_usd"]) == Decimal("0.0002")
    assert Decimal(budget["reserved_cost_usd"]) == 0
    assert budget["autonomous_policy"]["policy_sha256"] == policy["policy_sha256"]
    assert budget["max_runs"] == 3 and budget["effective_max_runs"] == 3
    for request in calls:
        body = json.loads(request.content)
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["strict"] is True
        assert body["max_tokens"] == 3500 and body["provider"]["allow_fallbacks"] is False
    with pytest.raises(ConflictError):
        model.interpret({**context, "message": "changed"}, IDENTITY)
    store.close()
    reopened = WorkStore(tmp_path / "work.sqlite3")
    model.store = reopened
    assert model.interpret(context, IDENTITY) == first and len(calls) == 2
    assert "sk-or-" not in json.dumps(first)
    reopened.close()


def test_unknown_outcome_blocks_new_work_and_exact_retry_never_sends(tmp_path):
    from casepath_api.autonomous_model_v1 import AutonomousModelError
    def timeout(_):
        raise httpx.ReadTimeout("Sensitive transport detail must not be recorded")
    store, model, calls, _ = setup(tmp_path, timeout)
    with pytest.raises(AutonomousModelError) as error:
        model.interpret({"text": "synthetic"}, IDENTITY)
    assert error.value.receipt["status"] == "unknown"
    with pytest.raises(AutonomousModelError):
        model.interpret({"text": "synthetic"}, IDENTITY)
    with pytest.raises(ConflictError):
        model.interpret({"text": "other"}, {**IDENTITY, "workflow_id": "autonomous.workflow.2"})
    assert len(calls) == 1
    budget = store.external_budget()
    assert budget["in_flight"] is True and budget["unknown_calls"] == 1
    assert Decimal(budget["reserved_cost_usd"]) > 0
    assert "Sensitive" not in json.dumps(error.value.receipt)
    store.close()


@pytest.mark.parametrize("content", ['{"accepted":true,"extra":"private prose"}', '{"accepted":true,"accepted":false}', 'not JSON'])
def test_invalid_results_are_accounted_but_never_retried_or_published(tmp_path, content):
    from casepath_api.autonomous_model_v1 import AutonomousModelError
    store, model, calls, _ = setup(tmp_path, lambda _: response(content))
    with pytest.raises(AutonomousModelError) as error:
        model.interpret({}, IDENTITY)
    assert error.value.receipt["status"] == "rejected"
    assert "private prose" not in json.dumps(error.value.receipt)
    with pytest.raises(AutonomousModelError):
        model.interpret({}, IDENTITY)
    assert len(calls) == 1 and store.external_budget()["in_flight"] is False
    assert Decimal(store.external_budget()["actual_cost_usd"]) == Decimal("0.0001")
    store.close()


def test_missing_cost_remains_reserved_after_successful_pair(tmp_path):
    store, model, calls, _ = setup(tmp_path, lambda _: response(cost=None))
    result = model.interpret({}, IDENTITY)
    model.verify({}, result["result"], IDENTITY)
    budget = store.external_budget()
    assert budget["unknown_calls"] == 2 and budget["in_flight"] is False
    assert Decimal(budget["actual_cost_usd"]) == 0
    assert Decimal(budget["reserved_cost_usd"]) > 0
    assert len(calls) == 2
    store.close()


def test_global_call_cap_is_not_a_new_per_workflow_allowance(tmp_path):
    from casepath_api.autonomous_model_v1 import AutonomousModelError
    store, model, calls, _ = setup(tmp_path, policy={**POLICY, "max_provider_calls": 2})
    first = model.interpret({}, IDENTITY)
    model.verify({}, first["result"], IDENTITY)
    before = store.external_budget()
    with pytest.raises(AutonomousModelError, match='configured inference allowance is unavailable; no new request was sent') as error:
        model.interpret({}, {**IDENTITY, "workflow_id": "autonomous.workflow.2"})
    assert error.value.receipt is None
    assert len(calls) == 2 and store.external_budget() == before
    assert before["max_provider_calls"] == 2
    store.close()


@pytest.mark.parametrize('policy,complete_first', [
    ({**POLICY, 'max_provider_calls': 1}, False),
    ({**POLICY, 'total_cost_limit_usd': '0.02'}, True),
    ({**POLICY, 'run_cost_limit_usd': '0.0001'}, False),
])
def test_budget_denials_are_named_without_creating_an_intent_or_sending(tmp_path, policy, complete_first):
    from casepath_api.autonomous_model_v1 import AutonomousModelError
    store, model, calls, _ = setup(tmp_path, policy=policy)
    if complete_first:
        first = model.interpret({}, IDENTITY)
        model.verify({}, first['result'], IDENTITY)
    before = store.external_budget()
    with store.connect() as db:
        prior_intents = db.execute('SELECT COUNT(*) FROM work_autonomous_calls').fetchone()[0]
        prior_workflows = db.execute('SELECT COUNT(*) FROM work_autonomous_workflows').fetchone()[0]
    with pytest.raises(AutonomousModelError, match='configured inference allowance is unavailable; no new request was sent') as error:
        model.interpret({}, {**IDENTITY, 'workflow_id': 'denied-workflow'})
    assert error.value.receipt is None and store.external_budget() == before
    assert len(calls) == (2 if complete_first else 0)
    with store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM work_autonomous_calls').fetchone()[0] == prior_intents
        assert db.execute('SELECT COUNT(*) FROM work_autonomous_workflows').fetchone()[0] == prior_workflows
    store.close()


def test_real_adapter_and_controller_contracts_interoperate_without_network(tmp_path):
    from casepath_api.autonomous_controller_v1 import AutonomousController
    from casepath_api.autonomous_policy_v1 import INTERPRET_SCHEMA, VERIFY_SCHEMA
    from casepath_api.autonomous_store_v1 import AutonomousStore
    from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root
    from test_autonomous_controller_v1 import SemanticFixture, packet
    semantic = SemanticFixture()
    def reply(request):
        body = json.loads(request.content)
        envelope = json.loads(body['messages'][1]['content'])
        stage = body['response_format']['json_schema']['name']
        if stage == 'casepath_interpret':
            output = semantic.interpret(envelope, IDENTITY)['result']
            output.setdefault('knowledge_candidates', [])
            assert envelope['instructions']['interpret'] in body['messages'][0]['content']
        else:
            output = semantic.verify(envelope['context'], envelope['proposal'], IDENTITY)['result']
            assert envelope['item_ids'] == [row['item_id'] for row in output['checks']]
            assert envelope['context']['instructions']['verify'] in body['messages'][0]['content']
        return response(json.dumps(output))
    budget, model, calls, _ = setup(tmp_path, reply)
    model.schemas = {'interpret': INTERPRET_SCHEMA, 'verify': VERIFY_SCHEMA}
    claims = AutonomousStore(tmp_path / 'claims.sqlite3')
    service = AutonomousController(claims, PublicCorpus(default_workspace_corpus_root()).static_policy(), model)
    try:
        incoming = claims.intake(packet(), 'adapter-integration')
        done = service.run(incoming['claim_id'])
        assert done['outcome'], done.get('deferral')
        assert len(calls) == 2 and len(done['knowledge_published']) == 1
        assert done['outcome']['request_draft']['status'] == 'prepared_not_sent'
        assert service.run(incoming['claim_id'])['state_sha256'] == done['state_sha256']
        assert len(calls) == 2
        assert budget.external_budget()['provider_calls_used'] == 2
    finally:
        service.shutdown()
        budget.close()


def test_disabled_real_profile_can_replay_but_cannot_reserve_new_work(tmp_path, monkeypatch):
    store, model, calls, _ = setup(tmp_path)
    result = model.interpret({}, IDENTITY)
    model._client = None
    monkeypatch.delenv('CASEPATH_AUTONOMOUS_ENABLED', raising=False)
    assert model.interpret({}, IDENTITY) == result
    before = store.external_budget()
    with pytest.raises(ConflictError, match='not explicitly enabled'):
        model.verify({}, result['result'], IDENTITY)
    assert store.external_budget() == before and len(calls) == 1
    store.close()


def test_verification_rejects_changed_original_context_or_proposal_before_send(tmp_path):
    store, model, calls, _ = setup(tmp_path)
    first = model.interpret({'text': 'original'}, IDENTITY)
    for context, proposal in (({'text': 'changed'}, first['result']), ({'text': 'original'}, {'accepted': False})):
        with pytest.raises(ConflictError):
            model.verify(context, proposal, IDENTITY)
    assert len(calls) == 1
    store.close()


def test_large_context_is_rejected_without_ledger_or_http_effect(tmp_path):
    from casepath_api.autonomous_model_v1 import AutonomousModelError
    store, model, calls, _ = setup(tmp_path)
    before = store.external_budget()
    with pytest.raises(AutonomousModelError):
        model.interpret({'text': 'x' * 64000}, IDENTITY)
    assert not calls and store.external_budget() == before
    store.close()


def test_catalogue_requires_structured_output_and_prices_extended_tiers(tmp_path):
    from casepath_api.autonomous_model_v1 import AutonomousModelV1
    store, _, _, _ = setup(tmp_path)
    missing = entry(supported_parameters=['tools'])
    with pytest.raises(ValueError, match='structured output'):
        AutonomousModelV1(store, worker=worker(missing), catalogue_entry=missing, schemas={'interpret': SCHEMA, 'verify': SCHEMA})
    tiered = entry(pricing={'prompt': '0.0000001', 'completion': '0.0000002', 'request': '0',
                           'overrides': [{'min_prompt_tokens': 32000, 'prompt': '0.0000003', 'completion': '0.0000004', 'request': '0.00001'}]})
    model = AutonomousModelV1(store, worker=worker(tiered), catalogue_entry=tiered, schemas={'interpret': SCHEMA, 'verify': SCHEMA})
    assert Decimal(model.config['prompt_price']) == Decimal('0.0000003')
    assert Decimal(model.config['completion_price']) == Decimal('0.0000004')
    assert Decimal(model.config['request_price']) == Decimal('0.00001')
    store.close()


@pytest.mark.parametrize('threshold,key,expected', [
    (32000, 'input_cache_write', '0.0000003'),
    (32000, 'input_cache_read', '0.0000003'),
    (64000, 'input_cache_write_1h', '0.0000003'),
    (64001, 'input_cache_write', '0.000000125'),
])
def test_autonomous_cache_write_reservation_covers_only_applicable_64kb_tiers(tmp_path, threshold, key, expected):
    model_entry = entry(pricing={'prompt': '0.0000001', 'completion': '0.0000005',
        'input_cache_write': '0.000000125',
        'overrides': [{'min_prompt_tokens': threshold, key: '0.0000003'}]})
    store, model, calls, _ = setup(tmp_path, catalogue_entry=model_entry)
    assert Decimal(model.config['prompt_price']) == Decimal(expected)
    assert Decimal(model.config['completion_price']) == Decimal('0.0000005')
    assert not calls and store.external_budget()['provider_calls_used'] == 0
    store.close()


def test_cache_write_bound_is_persisted_and_pair_fits_unchanged_workflow_cap(tmp_path):
    model_entry = entry(pricing={'prompt': '0.0000001', 'completion': '0.0000005',
        'input_cache_write': '0.000000125',
        'overrides': [{'min_prompt_tokens': 272000, 'prompt': '0.0000002',
                      'completion': '0.00000075', 'input_cache_write': '0.00000025'}]})
    store, model, calls, _ = setup(tmp_path, lambda _: response(cost=None), catalogue_entry=model_entry)
    assert 2 * (Decimal(model.config['prompt_price']) * 64000 +
                Decimal(model.config['completion_price']) * 3500) == Decimal('0.0195')
    context = {'text': 'x' * 60000}
    first = model.interpret(context, IDENTITY)
    second = model.verify(context, first['result'], IDENTITY)
    maxima = []
    for request, outcome in zip(calls, (first, second)):
        body = json.loads(request.content)
        assert body['provider']['max_price'] == {'prompt': 0.125, 'completion': 0.5}
        assert 'prompt_cache_options' not in body
        maximum = Decimal('0.000000125') * len(request.content) + Decimal('0.0000005') * 3500
        assert Decimal(outcome['receipt']['maximum_cost_usd']) == maximum
        maxima.append(maximum)
    before = store.external_budget()
    assert before['max_provider_calls'] == 18 and before['total_cost_limit_usd'] == '0.10'
    assert before['run_cost_limit_usd'] == '0.02' and before['provider_calls_used'] == 2
    assert before['unknown_calls'] == 2 and Decimal(before['reserved_cost_usd']) == sum(maxima)
    assert model.interpret(context, IDENTITY) == first
    assert model.verify(context, first['result'], IDENTITY) == second
    assert store.external_budget() == before and len(calls) == 2
    store.close()


def test_cache_write_bound_over_workflow_cap_reserves_and_sends_nothing(tmp_path):
    from casepath_api.autonomous_model_v1 import AutonomousModelError
    model_entry = entry(pricing={'prompt': '0.0000001', 'completion': '0.0000005',
                                'input_cache_write': '0.000001'})
    store, model, calls, _ = setup(tmp_path, catalogue_entry=model_entry)
    before = store.external_budget()
    with pytest.raises(AutonomousModelError, match='configured inference allowance is unavailable'):
        model.interpret({'text': 'x' * 60000}, IDENTITY)
    assert store.external_budget() == before and not calls
    with store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM work_autonomous_calls').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM work_autonomous_workflows').fetchone()[0] == 0
    store.close()


def test_supported_reasoning_uses_low_effort_within_output_cap_and_stays_private(tmp_path):
    model_entry = entry(supported_parameters=['tools', 'response_format', 'structured_outputs', 'reasoning'])
    def reply(_):
        payload = json.loads(response().content)
        payload['choices'][0]['message']['reasoning'] = 'Private fixture reasoning must not persist'
        return httpx.Response(200, json=payload)
    store, model, calls, _ = setup(tmp_path, reply, catalogue_entry=model_entry)
    first = model.interpret({}, IDENTITY)
    second = model.verify({}, first['result'], IDENTITY)
    for request in calls:
        body = json.loads(request.content)
        assert body['reasoning'] == {'effort': 'low', 'exclude': True}
        assert body['max_tokens'] == 3500
    assert 'Private fixture reasoning' not in json.dumps([first, second])
    assert model.config['max_calls_per_workflow'] == 2
    assert store.external_budget()['run_cost_limit_usd'] == '0.02'
    store.close()


def test_verifier_envelope_covers_new_knowledge_candidate_ids(tmp_path):
    from casepath_api.autonomous_policy_v1 import INTERPRET_SCHEMA, VERIFY_SCHEMA
    proposal = {'category': {'family': 'lease_termination_dispute', 'summary': 'Fixture', 'citations': []},
                'conditions': [], 'documents': [], 'steps': [],
                'knowledge_candidates': [{'document_type': 'spouse_notice_copy', 'required_fields': ['spouse_addressee'],
                    'summary': 'Inspect the spouse addressee.', 'citations': [{'artifact_id': 'fixture', 'quote': 'Spouse Alex'}],
                    'rule_refs': ['fixture-rule']}]}
    def reply(request):
        body = json.loads(request.content)
        if body['response_format']['json_schema']['name'] == 'casepath_interpret':
            return response(json.dumps(proposal))
        envelope = json.loads(body['messages'][1]['content'])
        assert envelope['item_ids'] == ['category', 'knowledge:spouse_notice_copy']
        return response(json.dumps({'family_supported': True, 'checks': [
            {'item_id': key, 'accepted': True, 'reason': 'Isolated contract fixture'} for key in envelope['item_ids']], 'issues': []}))
    store, model, calls, _ = setup(tmp_path, reply)
    model.schemas = {'interpret': INTERPRET_SCHEMA, 'verify': VERIFY_SCHEMA}
    result = model.interpret({}, IDENTITY)
    verified = model.verify({}, result['result'], IDENTITY)
    assert [row['item_id'] for row in verified['result']['checks']] == ['category', 'knowledge:spouse_notice_copy']
    assert len(calls) == 2
    store.close()


def test_catalogue_expires_between_stages_without_affecting_saved_replay(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from casepath_api.autonomous_model_v1 import AutonomousModelV1, AutonomousModelError
    import casepath_api.autonomous_model_v1 as adapter
    fixed_now = datetime(2026, 10, 8, 10, tzinfo=timezone.utc)
    class Clock(datetime):
        current = fixed_now
        @classmethod
        def now(cls, tz=None):
            return cls.current if tz is not None else cls.current.replace(tzinfo=None)
    monkeypatch.setattr(adapter, 'datetime', Clock)
    store, _, calls, _ = setup(tmp_path)
    catalogue = {'data': [entry()]}
    fetched_at = fixed_now - timedelta(hours=23)
    path = tmp_path / 'catalogue.json'
    packet = {'catalogue': catalogue, 'catalogue_sha256': digest(catalogue), 'fetched_at': fetched_at.isoformat()}
    path.write_text(json.dumps(packet))
    monkeypatch.setenv('CASEPATH_AGENT_WORK_CATALOGUE', str(path))
    transport_calls = []
    client = httpx.Client(transport=httpx.MockTransport(lambda request: transport_calls.append(request) or response()))
    model = AutonomousModelV1(store, worker=worker(entry()), schemas={'interpret': SCHEMA, 'verify': SCHEMA}, client=client)
    assert model._catalogue_fetched_at == fetched_at
    first = model.interpret({}, IDENTITY)
    assert first['receipt']['metadata']['catalogue_fetched_at'] == fetched_at.isoformat()
    assert first['receipt']['metadata']['catalogue_checked_at'] == fixed_now.isoformat()
    Clock.current += timedelta(hours=2)
    before = store.external_budget()
    assert model.interpret({}, IDENTITY) == first
    with pytest.raises(AutonomousModelError, match='catalogue expired'):
        model.verify({}, first['result'], IDENTITY)
    with pytest.raises(AutonomousModelError, match='catalogue expired'):
        model.interpret({}, {**IDENTITY, 'workflow_id': 'fresh-workflow'})
    assert store.external_budget() == before and len(transport_calls) == 1
    # An explicitly renewed snapshot with identical model/prices can finish the
    # same saved interpretation. No catalogue fetch or automatic retry occurs.
    packet['fetched_at'] = Clock.current.isoformat()
    path.write_text(json.dumps(packet))
    renewed = AutonomousModelV1(store, worker=worker(entry()), schemas={'interpret': SCHEMA, 'verify': SCHEMA}, client=client)
    assert renewed.config == model.config
    assert renewed.interpret({}, IDENTITY) == first
    second = renewed.verify({}, first['result'], IDENTITY)
    Clock.current += timedelta(hours=25)
    assert renewed.interpret({}, IDENTITY) == first and renewed.verify({}, first['result'], IDENTITY) == second
    assert len(transport_calls) == 2
    store.close()
