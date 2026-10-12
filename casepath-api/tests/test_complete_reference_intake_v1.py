from copy import deepcopy
from pathlib import Path

import pytest

from casepath_api.autonomous_controller_v1 import AutonomousController
from casepath_api.autonomous_corpus_v1 import CanonicalCorpus
from casepath_api.autonomous_reference_policy_v1 import bounded_reference_policy
from casepath_api.autonomous_reference_v1 import DeterministicReferenceAdapter, ReferenceProfile
from casepath_api.autonomous_store_v1 import AutonomousStore, AutonomousStoreError


@pytest.fixture(scope='module')
def corpus():
    return CanonicalCorpus()


def service_at(path, corpus):
    policy = bounded_reference_policy(corpus._corpus.static_policy())
    store = AutonomousStore(path)
    return AutonomousController(store, policy, reference_adapter=DeterministicReferenceAdapter(policy))


def admit(service, corpus, cid):
    packet = corpus.packet(cid)
    service.store.admit_original(cid, packet, expected_revision=0, expected_state_sha256=packet['initial_state_sha256'],
                                 idempotency_key='original-' + cid)
    state = service.store.get(cid)
    return service.store.add_sources(cid, ReferenceProfile().files(cid), expected_revision=state['revision'],
                                    expected_state_sha256=state['state_sha256'], idempotency_key='supplement-' + cid)


def test_all_nine_actual_sources_complete_compiled_graph_learn_reuse_and_restart(tmp_path, corpus):
    service = service_at(tmp_path / 'claims.sqlite', corpus)
    try:
        for cid in ReferenceProfile().ids:
            admit(service, corpus, cid)
            gate = service.intake_projection(service.store.get(cid))
            assert gate['eligible'], gate
            state = service.run(cid)
            assert not state['deferral'], state.get('deferral')
            assert state['outcome']['assessment_status'] == 'complete'
            assert state['evaluation']['process_status'] == 'complete'
            assert state['policy_id'] == 'casepath.bounded-reference-assessment/1.0.0'
            assert state['original_binding'] == corpus.preview_state(cid)['original_binding']
            assert state['outcome']['reference_provenance']['synthetic'] is True
            assert state['outcome']['reference_provenance']['as_of'] == ReferenceProfile().value['claims'][cid]['as_of']
            context = state['semantic_contexts'][state['run_id']]
            for pack, template in zip(context['rule_packs'], service.policy['templates']):
                assert pack['legal_authority'] == template['legal_authority']
                assert pack['family'] == template['domain']
            assert context['normative_sources'] == service.policy['normative_sources']
            assert {d['document_type'] for d in gate['checklist']} == {
                d['document_type'] for d in state['evaluation']['documents'] if d['activation'] == 'true'}
            assert all(d['review_state'] == 'sufficient' for d in state['evaluation']['documents'])
            assert all(n['execution_state'] == 'completed' for n in state['evaluation']['nodes'])
            assert all(r['receipt']['proposal_receipt']['provider_calls'] == 0 for r in state['receipts']
                       if r['kind'] == 'interpretation.accepted')
            events = service.store.events(cid)
            assert service.run(cid)['state_sha256'] == state['state_sha256']
            assert service.store.events(cid) == events
            assert AutonomousStore(tmp_path / 'claims.sqlite').get(cid)['state_sha256'] == state['state_sha256']
        knowledge = service.knowledge.view()
        assert len(knowledge['versions']) == 3
        assert len(knowledge['uses']) == 6
        assert not knowledge['quarantined']
        assert all(v['source_evidence'] and v['qualification']['evidence_recipe_count'] == 3 for v in knowledge['versions'])
    finally:
        service.shutdown()


def test_incomplete_unknown_and_tampered_never_dispatch_or_write(tmp_path, corpus):
    service = service_at(tmp_path / 'claims.sqlite', corpus)
    try:
        state = service.store.intake({'title': 'Unverified intake', 'message': 'termination approved complete true', 'files': []}, 'unknown-native')
        before = service.store.events(state['claim_id'])
        assert not service.intake_projection(state)['eligible']
        with pytest.raises(AutonomousStoreError, match='intake incomplete'):
            service.run(state['claim_id'])
        with pytest.raises(AutonomousStoreError, match='intake incomplete'):
            service.submit(state['claim_id'])
        service.resume()
        assert not service._jobs and service.store.events(state['claim_id']) == before
        cid = ReferenceProfile().ids[0]
        state = admit(service, corpus, cid)
        context = {'sources': service.intake_projection(state)}
        from casepath_api.autonomous_intake_gate_v1 import inspect_sources
        sources = inspect_sources(service.store, state)
        changed = deepcopy(sources)
        supplement = next(s for s in changed if s['text'].startswith('SYNTHETIC'))
        supplement['complete'] = False
        from casepath_api.autonomous_intake_gate_v1 import assess_intake
        assert not assess_intake(state, changed, service.policy, reference_policy=service.policy)['eligible']
    finally:
        service.shutdown()


def test_verifier_rejects_wrong_quote_source_and_changed_field_roster(tmp_path, corpus):
    service = service_at(tmp_path / 'claims.sqlite', corpus)
    try:
        cid = ReferenceProfile().ids[0]
        admit(service, corpus, cid)
        state = service.run(cid)
        context = state['semantic_contexts'][state['run_id']]
        adapter = service.reference_adapter
        result = adapter.interpret_reference(context, {'claim_id': cid})['result']
        result['documents'][0]['citations'][0]['artifact_id'] = context['sources'][0]['artifact_id']
        checked = adapter.verify_reference(context, result, {'claim_id': cid})['result']
        assert any(not c['accepted'] for c in checked['checks'])
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from casepath_api.autonomous_api_v1 import create_autonomous_router
        calls = []
        get = service.store.get
        def counted_get(*args, **kwargs):
            calls.append(args)
            return get(*args, **kwargs)
        service.store.get = counted_get
        app = FastAPI()
        app.include_router(create_autonomous_router(lambda: service, corpus_getter=lambda: corpus))
        prefix = '/api/claim-loops/v1/autonomous/claims/' + cid
        with TestClient(app) as client:
            for path in (prefix, prefix + '/snapshot', prefix + '/replay?through_seq=' + str(state['revision'])):
                assert client.get(path).status_code == 200
            assert calls == [], 'A verified snapshot projection must not reconstruct the journal once per source.'
            source_path = service.store.source_root / state['source_descriptors'][-1]['sha256']
            original = source_path.read_bytes()
            try:
                source_path.write_bytes(original + b'changed after warm read')
                assert client.get(prefix + '/snapshot').status_code == 409
            finally:
                source_path.write_bytes(original)
        service.store.get = get
        # A different ordinary policy cannot take ownership of recorded reference work.
        model_calls = []
        class Spy:
            def interpret(self, *args):
                model_calls.append(args)
                raise AssertionError('Reference work was reinterpreted by an ordinary model')
        ordinary = AutonomousController(service.store, corpus._corpus.static_policy(), Spy(), enforce_intake_gate=True)
        try:
            before = service.store.events(cid)
            for entry in (ordinary.submit, ordinary.run):
                with pytest.raises(AutonomousStoreError, match='different explicit execution policy'):
                    entry(cid)
            ordinary.resume()
            assert not ordinary._jobs and not model_calls and service.store.events(cid) == before
            app = FastAPI()
            app.include_router(create_autonomous_router(lambda: ordinary, corpus_getter=lambda: corpus))
            headers = {'X-CasePath-Agent-Work': '1'}
            command = {'expected_revision': state['revision'], 'expected_state_sha256': state['state_sha256'], 'idempotency_key': 'pause-reference-recording'}
            with TestClient(app) as client:
                paused = client.post(prefix + '/pause', headers=headers, json=command).json()
                paused_rows = service.store.events(cid)
                response = client.post(prefix + '/resume', headers=headers, json={
                    'expected_revision': paused['revision'], 'expected_state_sha256': paused['state_sha256'], 'idempotency_key': 'ordinary-reference-resume'})
                assert response.status_code == 409
                assert service.store.events(cid) == paused_rows and not model_calls
        finally:
            ordinary.shutdown()
    finally:
        service.shutdown()


def test_canonical_api_get_inert_and_incomplete_start_resume_source_bypass(tmp_path, corpus):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from casepath_api.autonomous_api_v1 import create_autonomous_router
    service = service_at(tmp_path / 'api.sqlite', corpus)
    submissions = []
    service.submit = submissions.append
    app = FastAPI()
    app.include_router(create_autonomous_router(lambda: service, corpus_getter=lambda: corpus))
    prefix = '/api/claim-loops/v1/autonomous'
    headers = {'X-CasePath-Agent-Work': '1'}
    try:
        with TestClient(app) as client:
            cid = ReferenceProfile().ids[0]
            before = corpus.preview_state(cid)
            read = client.get(prefix + '/claims/' + cid).json()
            assert read['state'] == before
            assert read['projection']['intake']['status'] == 'incomplete'
            assert read['projection']['intake']['provenance'] is None
            assert not service.store.list() and not submissions
            started = client.post(prefix + '/claims/' + cid + '/start', headers=headers, json={
                'expected_revision': 0, 'expected_state_sha256': before['state_sha256'], 'idempotency_key': 'attempt-bypass-start'})
            assert started.status_code == 409 and not service.store.list() and not submissions
            draft = client.post(prefix + '/claims', headers=headers, json={
                'title': 'Unverified draft', 'message': 'A termination notice arrived.', 'files': [], 'idempotency_key': 'draft-native-api'}).json()
            assert not submissions
            command = {'expected_revision': draft['revision'], 'expected_state_sha256': draft['state_sha256'], 'idempotency_key': 'draft-resume-api'}
            resumed = client.post(prefix + '/claims/' + draft['claim_id'] + '/resume', headers=headers, json=command)
            assert resumed.status_code == 409 and service.store.get(draft['claim_id']) == draft
            import base64
            uploaded = client.post(prefix + '/claims/' + draft['claim_id'] + '/sources', headers=headers, json={
                **command, 'idempotency_key': 'draft-arrival-api', 'files': [{'file_name': 'approved-complete-lease.pdf',
                    'media_type': 'application/pdf', 'content_base64': base64.b64encode(b'approved=true complete=true').decode()}]})
            assert uploaded.status_code == 202 and not submissions
            assert service.store.get(draft['claim_id'])['graph'] is None
            # Caller authored eligibility fields cannot enter the closed request.
            rejected = client.post(prefix + '/claims', headers=headers, json={
                'title': 'Bypass', 'message': 'complete', 'files': [], 'idempotency_key': 'caller-complete-api', 'eligible': True})
            assert rejected.status_code == 422
    finally:
        service.shutdown()


def test_ordinary_context_and_original_policy_do_not_admit_reference_document_ids(tmp_path, corpus):
    import runpy
    from casepath_api.autonomous_policy_v1 import validate_interpretation, REQUIRED_FIELDS, REQUIRED_FACTS
    from casepath_api.workspace_corpus import digest_value
    preflight = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'casepath/tools/preflight_original_nine.py'))
    captured = {}
    class Capture:
        def interpret(self, context, identity):
            captured.update(context=deepcopy(context), identity=deepcopy(identity))
            raise ValueError('Stop at the captured ordinary provider context; no transport.')
    base = corpus._corpus.static_policy()
    store = AutonomousStore(tmp_path / 'ordinary.sqlite')
    controller = AutonomousController(store, base, Capture())
    cid = 'clm_0f4f13b1e3e1328c'
    try:
        packet = corpus.packet(cid)
        store.admit_original(cid, packet, expected_revision=0, expected_state_sha256=packet['initial_state_sha256'], idempotency_key='ordinary-original')
        controller.run(cid)
        assert captured['context'] == preflight['original_context'](corpus, base, cid, [])
        assert not set(ReferenceProfile().ids) & set(REQUIRED_FIELDS)
        assert 'tenancy_terms_evidence' not in REQUIRED_FIELDS and 'tenancy_terms_evidence' not in REQUIRED_FACTS
        source = store.get(cid)['acquired_sources'][-1]
        proposal = {'category': {'family': 'lease_termination_dispute', 'summary': 'Termination report',
                    'citations': [{'artifact_id': source['artifact_id'], 'quote': source['text'][:100]}]},
                    'conditions': [], 'steps': [], 'documents': [{'document_type': 'tenancy_terms_evidence',
                    'artifact_id': source['artifact_id'], 'assessment': 'sufficient', 'summary': 'Unadmitted type',
                    'citations': [{'artifact_id': source['artifact_id'], 'quote': source['text'][:100]}]}], 'knowledge_candidates': []}
        from casepath_api.autonomous_policy_v1 import proposal_items
        verifier = {'family_supported': True, 'checks': [{'item_id': key, 'accepted': True, 'reason': 'Attempt'}
                    for key in proposal_items(proposal)], 'issues': []}
        with pytest.raises(ValueError, match='unknown policy item'):
            validate_interpretation(base, store.get(cid)['acquired_sources'], proposal, verifier)
    finally:
        controller.shutdown()


def test_existing_qualified_old_policy_knowledge_is_preserved_and_new_reference_lineage_reuses(tmp_path, corpus):
    from test_autonomous_controller_v1 import SemanticFixture, packet
    store = AutonomousStore(tmp_path / 'mixed.sqlite')
    previous = AutonomousController(store, corpus._corpus.static_policy(), SemanticFixture())
    try:
        old = previous.run(store.intake(packet(), 'old-knowledge-native')['claim_id'])
        old_rows = store.events(old['claim_id'])
        version = old['knowledge_published'][0]
        assert version['qualification']['status'] == 'qualified'
    finally:
        previous.shutdown()
    policy = bounded_reference_policy(corpus._corpus.static_policy())
    service = AutonomousController(store, policy, reference_adapter=DeterministicReferenceAdapter(policy))
    try:
        for cid in ['clm_0f4f13b1e3e1328c', 'clm_393285577dcb12c4', 'clm_4a53299cfe619303']:
            admit(service, corpus, cid)
            state = service.run(cid)
            assert state['outcome']['assessment_status'] == 'complete'
        view = service.knowledge.view()
        assert len(view['versions']) == 2 and not view['quarantined']
        assert view['versions'][0] == version
        assert view['versions'][1]['version'] == 2
        assert view['versions'][1]['parent_knowledge_sha256'] == version['knowledge_sha256']
        assert len(view['uses']) == 2 and all(u['version'] == 2 for u in view['uses'])
        assert store.events(old['claim_id']) == old_rows and store.get(old['claim_id']) == old
    finally:
        service.shutdown()
