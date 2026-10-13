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


def service_at(path, corpus, profile=None):
    policy = bounded_reference_policy(corpus._corpus.static_policy())
    store = AutonomousStore(path)
    return AutonomousController(store, policy, reference_adapter=DeterministicReferenceAdapter(policy, profile))


def admit(service, corpus, cid):
    packet = corpus.packet(cid)
    service.store.admit_original(cid, packet, expected_revision=0, expected_state_sha256=packet['initial_state_sha256'],
                                 idempotency_key='original-' + cid)
    state = service.store.get(cid)
    return service.store.add_sources(cid, service.reference_adapter.profile.files(cid), expected_revision=state['revision'],
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
            assert service.store.snapshot(cid)['replay_start'] is None
            assert_exact_prefixes(service.store, cid)
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
        supplement = next(s for s in changed if s['text'].startswith('Synthetic demonstration document'))
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


@pytest.mark.parametrize('cid, family', [
    ('clm_06400c75399e7f37', 'defect_mold_heating'),  # English mold and moisture.
    ('clm_16ac3b7054d73cc0', 'defect_mold_heating'),  # English dampness.
    ('clm_1e3f5e4acec3ef7f', 'defect_mold_heating'),  # English leak.
    ('clm_37909940906c3d22', 'defect_mold_heating'),  # German Wasserleck.
    ('clm_0c373e693a363f9e', 'rent_increase_dispute'),  # Renovation grant allocation.
    ('clm_fc970e956872f431', 'rent_increase_dispute'),  # German reference-rate calculation.
    ('clm_de7ddb30509c2358', 'rent_increase_dispute'),  # English reference-rate calculation.
    ('clm_2a9c260c26afaa34', 'lease_termination_dispute'),  # Clear original account; bounded extraction.
    ('clm_c44ddc0914ba9298', 'rent_increase_dispute'),  # Heating advance is a rent component.
    ('clm_2c55cdd816b1d0e8', 'rent_increase_dispute'),  # Heating and termination form boilerplate.
    ('clm_3f3c313482ea5657', 'rent_increase_dispute'),  # Notice dates do not establish termination.
])
def test_original_issue_language_routes_only_unassessed_template_evidence(corpus, cid, family):
    from casepath_api.autonomous_intake_gate_v1 import assess_intake
    base = corpus._corpus.static_policy()
    state = corpus.preview_state(cid)
    before = deepcopy(state)
    sources = [corpus.source_preview(cid, s['artifact_id']) for s in state['source_descriptors']]
    assert all(s['preview_only'] and not s['evidence_admitted'] for s in sources)
    assert all(type(s['complete']) is bool for s in sources)
    gate = assess_intake(state, sources, base)
    template = next(t for t in base['templates'] if t['domain'] == family)
    mandatory = [d for d in template['process_catalog']['documents'] if d['requirement_class'] == 'mandatory']
    assert gate['status'] == 'incomplete' and not gate['eligible']
    assert gate['assessment_scope'] is None and gate['provenance'] is None
    assert all(p['status'] == 'unknown' and not p['citations'] for p in gate['legal_predicates'])
    assert {d['document_type'] for d in gate['checklist']} == {d['document_type'] for d in mandatory}
    assert all(d['status'] == 'unassessed' and d['investigation_only'] and d['artifact_ids'] == []
               for d in gate['missing_documents'])
    assert {n for d in gate['checklist'] for n in d['node_ids']} <= {
        n['node_id'] for n in template['process_catalog']['nodes']}
    assert gate['active_node_ids'] == [template['process_catalog']['nodes'][0]['node_id']]
    bounded = [{**s, 'text': '', 'complete': False} for s in sources]
    bounded_gate = assess_intake(state, bounded, base)
    assert bounded_gate['checklist'] == gate['checklist'] and not bounded_gate['eligible']
    assert bounded_gate['legal_predicates'] == gate['legal_predicates']
    assert state == before == corpus.preview_state(cid)
    assert not state['acquired_sources'] and not state['receipts'] and state['revision'] == 0


@pytest.mark.parametrize('title, message, expected', [
    ('Mold in my bedroom', 'Please review the available records.', 'incomplete'),
    ('Wasserleck in der Wohnung', 'Bitte prüfen Sie meine Unterlagen.', 'incomplete'),
    ('Please update my address', 'I moved; correct my postal address.', 'unsupported'),
    ('Please sort my records', 'I need help putting the documents in order.', 'unsupported'),
    ('Mold in my apartment', 'Mold persists and I also received a landlord termination notice.', 'unsupported'),
    ('Unclear dispute', 'I may have a rent increase or a termination notice; I cannot tell.', 'unsupported'),
])
def test_subject_only_and_ambiguous_intake_never_establish_eligibility(tmp_path, corpus, title, message, expected):
    from casepath_api.autonomous_intake_gate_v1 import inspect_sources
    service = AutonomousController(AutonomousStore(tmp_path / 'routing.sqlite'),
                                   corpus._corpus.static_policy(), enforce_intake_gate=True)
    try:
        state = service.store.intake({'title': title, 'message': message, 'files': []}, 'routing-language')
        before = service.store.events(state['claim_id'])
        sources = inspect_sources(service.store, state)
        assert all(s['complete'] for s in sources)
        gate = service.intake_projection(state, sources=sources)
        assert gate['status'] == expected and not gate['eligible']
        assert gate['assessment_scope'] is None and gate['provenance'] is None
        assert all(p['status'] == 'unknown' for p in gate['legal_predicates'])
        assert bool(gate['checklist']) == (expected == 'incomplete')
        with pytest.raises(AutonomousStoreError, match='intake incomplete'):
            service.run(state['claim_id'])
        assert service.store.get(state['claim_id']) == state
        assert service.store.events(state['claim_id']) == before
        assert state['graph'] is None and state['outcome'] is None
        assert not any(r['kind'] == 'interpretation.accepted' for r in state['receipts'])
    finally:
        service.shutdown()


def test_v2_profile_is_exact_cleanup_of_immutable_legacy():
    from hashlib import sha256
    from casepath_api.autonomous_reference_v1 import clean_reference_source
    profile = ReferenceProfile()
    legacy = ReferenceProfile.for_profile('synthetic-nine-v1')
    assert profile.value['profile_id'] == 'synthetic-nine-v2'
    assert legacy.sha256 == '15c44d004cc1a34b90e8662b3185deb63652ab066c7727b080dfc0987a648de7'
    assert profile.value['supersedes'] == {'profile_id': legacy.value['profile_id'], 'profile_sha256': legacy.sha256}
    assert profile.ids == legacy.ids
    assert sum(len(profile.value['claims'][cid]['sources']) for cid in profile.ids) == 21
    for cid in profile.ids:
        for source, old in zip(profile.value['claims'][cid]['sources'], legacy.value['claims'][cid]['sources']):
            old_raw = (legacy.root / cid / old['file_name']).read_bytes()
            raw = (profile.root / cid / source['file_name']).read_bytes()
            assert source['legacy_source'] == old
            assert raw == clean_reference_source(old_raw)
            assert sha256(raw).hexdigest() == source['sha256']
            assert raw.startswith(b'Synthetic demonstration document (fictional)\n')
            assert b'SHA256' not in raw and b'Fixture author' not in raw and b'Authored for' not in raw


def test_unknown_profile_identity_hash_is_rejected(tmp_path):
    import json
    profile = ReferenceProfile()
    value = deepcopy(profile.value)
    value['authored_on'] = '2026-10-14'
    (tmp_path / 'profile.json').write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
    with pytest.raises(ValueError, match='profile bytes changed'):
        ReferenceProfile(tmp_path)


def assert_exact_prefixes(store, cid):
    """Reduce every actual prefix once and verify citations against physical bytes."""
    from hashlib import sha256
    with store.journal.connect() as connection:
        head, events, states = store._replay(store._rows(connection, cid), with_history=True)
    sources = {s['artifact_id']: store.acquire(cid, s['artifact_id']) for s in head['source_descriptors']}
    def inspect(value, allowed):
        if isinstance(value, dict):
            if {'artifact_id', 'quote', 'sha256', 'start_char', 'end_char', 'text_sha256'} <= value.keys():
                assert value['artifact_id'] in allowed
                source = sources[value['artifact_id']]
                assert source['sha256'] == value['sha256']
                assert source['text_sha256'] == value['text_sha256'] == sha256(source['text'].encode()).hexdigest()
                assert source['text'][value['start_char']:value['end_char']] == value['quote']
            for child in value.values():
                inspect(child, allowed)
        elif isinstance(value, list):
            for child in value:
                inspect(child, allowed)
    for state, event in zip(states, events):
        assert state['revision'] == event['sequence']
        assert state['state_sha256'] == event['resulting_state_sha256']
        inspect(state, {s['artifact_id'] for s in state['source_descriptors']})
    return states


@pytest.mark.parametrize('cid', ReferenceProfile().ids)
def test_completed_v1_reassesses_v2_append_only_with_real_reset_and_all_exact_prefixes(tmp_path, corpus, cid):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from casepath_api.autonomous_api_v1 import create_autonomous_router
    legacy = ReferenceProfile.for_profile('synthetic-nine-v1')
    old = service_at(tmp_path / 'migration.sqlite', corpus, legacy)
    try:
        admit(old, corpus, cid)
        previous = old.run(cid)
        assert previous['outcome']['assessment_status'] == 'complete'
        assert old.store.snapshot(cid)['replay_start'] is None
        old_rows = old.store.events(cid)
        old_prefixes = assert_exact_prefixes(old.store, cid)
        original_policy = deepcopy(old.policy)
    finally:
        old.shutdown()
    service = service_at(tmp_path / 'migration.sqlite', corpus)
    try:
        assert service.policy == original_policy
        # A read can show the valid legacy assessment, while v2 execution needs
        # the real v2 source arrival before any accepted work is appended.
        assert service.intake_projection(previous, historical=True)['eligible']
        assert not service.intake_projection(previous)['eligible']
        with pytest.raises(AutonomousStoreError, match='intake incomplete'):
            service.run(cid)
        assert service.store.events(cid) == old_rows
        state = service.store.add_sources(cid, service.reference_adapter.profile.files(cid),
            expected_revision=previous['revision'], expected_state_sha256=previous['state_sha256'],
            idempotency_key='cleaned-v2-' + cid)
        state = service.run(cid)
        assert state['outcome']['assessment_status'] == 'complete', state.get('deferral')
        assert state['evaluation']['process_status'] == 'complete'
        assert state['acquired_sources'][:len(previous['acquired_sources'])] == previous['acquired_sources']
        assert state['actions'][:len(previous['actions'])] == previous['actions']
        assert state['semantic_contexts'][previous['run_id']] == previous['semantic_contexts'][previous['run_id']]
        assert service.store.events(cid)[:len(old_rows)] == old_rows
        prefixes = assert_exact_prefixes(service.store, cid)
        assert prefixes[:len(old_prefixes)] == old_prefixes
        context = state['semantic_contexts'][state['run_id']]
        provenance = context['reference_provenance']
        active = [s['artifact_id'] for s in context['sources']]
        assert active == provenance['source_artifact_ids'] and len(active) == len(set(active))
        retired = {s['sha256'] for s in legacy.value['claims'][cid]['sources']}
        assert not retired & {s['sha256'] for s in context['sources']}
        assert len(provenance['superseded_sources']) == len(retired)
        assert set(provenance['superseded_source_artifact_ids']) == {
            s['artifact_id'] for s in state['acquired_sources'] if s['sha256'] in retired}
        descriptor = service.store.snapshot(cid)['replay_start']
        assert descriptor is not None
        assert descriptor == {'contract': 'casepath.reference-replay-start/1.0.0', 'claim_id': cid,
            'from_seq': descriptor['from_seq'], 'state_sha256': prefixes[descriptor['from_seq'] - 1]['state_sha256'],
            'event_sha256': prefixes[descriptor['from_seq'] - 1]['last_event_sha256'],
            'run_id': state['run_id'], 'profile_id': 'synthetic-nine-v2',
            'profile_sha256': service.reference_adapter.profile.sha256, 'source_artifact_ids': active}
        reset = prefixes[descriptor['from_seq'] - 1]
        assert reset['graph']['family'] == 'incoming_packet'
        assert reset['evaluation']['process_status'] != 'complete'
        assert reset['outcome'] is None
        assert reset['acquired_sources'] == previous['acquired_sources']
        assert reset['actions'] == previous['actions']
        assert {d['artifact_id'] for d in reset['graph']['document_catalog'][0]['held_files']} <= set(active)
        rows = service.store.events(cid)
        assert service.run(cid) == state and service.store.events(cid) == rows
        if cid == 'clm_0f4f13b1e3e1328c':
            from casepath_api.autonomous_reference_v1 import reference_replay_start
            assert reference_replay_start(state, rows) == descriptor
            for value in (None, [], 'foreign', {**provenance, 'unknown': True},
                          {**provenance, 'source_artifact_ids': active + active[:1]}):
                malformed = deepcopy(state)
                malformed['semantic_contexts'][state['run_id']]['reference_provenance'] = value
                assert reference_replay_start(malformed, rows) is None
            foreign = deepcopy(state)
            foreign['semantic_contexts'][state['run_id']]['claim_id'] = 'clm_foreign'
            assert reference_replay_start(foreign, rows) is None
            foreign_rows = deepcopy(rows)
            next(e for e in foreign_rows if e['idempotency_key'] == state['run_id'] + '.prepare')['claim_id'] = 'clm_foreign'
            assert reference_replay_start(state, foreign_rows) is None
            incomplete = deepcopy(state)
            incomplete['evaluation']['process_status'] = 'pending'
            assert reference_replay_start(incomplete, rows) is None
        app = FastAPI()
        app.include_router(create_autonomous_router(lambda: service, corpus_getter=lambda: corpus, read_only=True))
        prefix = '/api/claim-loops/v1/autonomous/claims/' + cid
        # Replay already validates its whole head; no second snapshot read is
        # needed to attach the current descriptor to an explicit old prefix.
        snapshot = service.store.snapshot
        with TestClient(app) as client:
            response = client.get(prefix + '/snapshot?after=' + str(state['revision'])).json()
            assert response['events'] == [] and response['replay_start'] == descriptor
            service.store.snapshot = lambda *a, **k: pytest.fail('Replay performed a second head read')
            response = client.get(prefix + '/replay?through_seq=' + str(previous['revision'])).json()
            assert response['state'] == previous and response['replay_start'] == descriptor
            assert response['projection']['intake']['provenance']['profile_id'] == 'synthetic-nine-v1'
            service.store.snapshot = snapshot
            response = client.get(prefix + '/replay?through_seq=0').json()
            assert response['state'] == corpus.preview_state(cid)
            assert response['replay_start'] == descriptor
            reset_response = client.get(prefix + '/replay?through_seq=' + str(descriptor['from_seq'])).json()
            assert reset_response['state'] == reset and reset_response['replay_start'] == descriptor
            if cid == 'clm_0f4f13b1e3e1328c':
                physical = service.store.source_root / next(iter(retired))
                raw = physical.read_bytes()
                try:
                    physical.write_bytes(raw + b'changed retired bytes')
                    for path in ('/snapshot', '/replay?through_seq=0', '/replay?through_seq=1'):
                        assert client.get(prefix + path).status_code == 409
                finally:
                    physical.write_bytes(raw)
        assert service.store.events(cid) == rows
    finally:
        service.shutdown()


@pytest.mark.parametrize('extra', ['unknown', 'partial_legacy', 'foreign_legacy'])
def test_v2_unknown_partial_and_foreign_physical_rosters_fail_closed_without_work(tmp_path, corpus, extra):
    import base64
    legacy = ReferenceProfile.for_profile('synthetic-nine-v1')
    service = service_at(tmp_path / 'closed.sqlite', corpus)
    try:
        cid = 'clm_314f2d309fea25e6'
        state = admit(service, corpus, cid)
        files = (legacy.files(cid)[:1] if extra == 'partial_legacy' else legacy.files(legacy.ids[0]) if extra == 'foreign_legacy'
                 else [{'file_name': 'adverse.txt', 'media_type': 'text/plain',
                        'content_base64': base64.b64encode(b'The defect was repaired; new adverse evidence.').decode()}])
        state = service.store.add_sources(cid, files, expected_revision=state['revision'],
            expected_state_sha256=state['state_sha256'], idempotency_key='unexpected-' + extra)
        rows = service.store.events(cid)
        assert not service.intake_projection(state)['eligible']
        assert not service.intake_projection(state, historical=True)['eligible']
        with pytest.raises(AutonomousStoreError, match='intake incomplete'):
            service.run(cid)
        assert service.store.events(cid) == rows and service.store.get(cid) == state
    finally:
        service.shutdown()


def test_unfinished_v1_frozen_context_retains_legacy_findings(tmp_path, corpus):
    from casepath_api.autonomous_controller_v1 import SupersededWorkflow
    from casepath_api.autonomous_reference_v1 import reference_findings
    legacy = ReferenceProfile.for_profile('synthetic-nine-v1')
    service = service_at(tmp_path / 'unfinished.sqlite', corpus, legacy)
    try:
        cid = 'clm_543f08f2415b2a33'
        admit(service, corpus, cid)
        apply = service._apply_verified
        service._apply_verified = lambda *a, **k: (_ for _ in ()).throw(SupersededWorkflow('Accepted context left unfinished'))
        unfinished = service.run(cid)
        context = unfinished['semantic_contexts'][unfinished['run_id']]
        expected, _ = reference_findings(service.policy, context['sources'])
        assert 'A mechanical signature is permitted at this historical date' in expected['category']['summary']
        service._apply_verified = apply
        state = service.run(cid)
        assert state['outcome']['summary'] == expected['category']['summary']
        assert state['semantic_contexts'][state['run_id']] == context
        assert state['outcome']['reference_provenance']['profile_id'] == 'synthetic-nine-v1'
        assert service.store.snapshot(cid)['replay_start'] is None
    finally:
        service.shutdown()
