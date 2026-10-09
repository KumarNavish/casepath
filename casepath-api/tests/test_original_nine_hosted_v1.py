"""Remote-primary semantics use MockHrana only; zero real network calls."""
from datetime import datetime, timezone
import json

import httpx
import pytest

from hosted_hrana_fixture import MockHrana
from casepath_api.agent_work.contracts import digest
from casepath_api.agent_work.store import WorkStore, ConflictError, ReconciliationRequired
from casepath_api.autonomous_model_v1 import AutonomousModelV1
from casepath_api.hosted_sql_v1 import HostedStorageError
from casepath_api.hosted_lease_v1 import HostedWorkflowLease, HostedOwnershipLost, _CURRENT_OWNER
from test_original_nine_budget_v1 import exhausted, proposal, apply, begin, complete
from test_original_nine_preflight_v1 import selection, corpus, load_tool
from test_autonomous_model_v1 import response
from casepath_api.autonomous_policy_v1 import INTERPRET_SCHEMA, VERIFY_SCHEMA


def model_for(store):
    calls = []
    model = AutonomousModelV1.__new__(AutonomousModelV1)
    tool = load_tool()
    model.store, model.config = store, tool.ORIGINAL_NINE_CONFIG.copy()
    model.schemas = {'interpret':INTERPRET_SCHEMA,'verify':VERIFY_SCHEMA}
    model._catalogue_fetched_at = datetime.now(timezone.utc)
    model._key = 'fixture-only-never-a-real-provider-credential'
    model._client = httpx.Client(transport=httpx.MockTransport(lambda request: calls.append(request) or response(model=model.config['model'])))
    return model,calls


def test_lost_grant_commit_readback_replays_exact_approval_without_send(exhausted, proposal, tmp_path):
    server = MockHrana(exhausted.path)
    remote = WorkStore(tmp_path/'unused-remote',connection_factory=server.connection,validated_source_commit='8'*40)
    try:
        server.fail_next('timeout',sql_prefix='COMMIT')
        with pytest.raises(HostedStorageError):
            apply(remote,proposal)
        first = remote.external_budget()
        assert first['original_nine_workflows_used'] == first['original_nine_provider_calls_used'] == 0
        assert apply(remote,proposal) == first['original_nine_grant']
        assert remote.external_budget() == first
        assert not remote.path.exists()
    finally:
        remote.close(); server.close()


def test_lost_reservation_acknowledgement_sends_zero_and_new_key_cannot_resend(exhausted, proposal, tmp_path, corpus):
    apply(exhausted,proposal)
    server = MockHrana(exhausted.path)
    remote = WorkStore(tmp_path/'unused-remote',connection_factory=server.connection,validated_source_commit='8'*40)
    model,calls = model_for(remote)
    tool = load_tool()
    from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root
    context = tool.original_context(corpus,PublicCorpus(default_workspace_corpus_root()).static_policy(),tool.ORIGINAL_IDS[0],[])
    identity = {k:v for k,v in proposal['eligible_originals'][0]['identity'].items()
                if k not in {'claim_binding_sha256','original_binding_sha256','corpus_manifest_sha256'}}
    try:
        server.fail_next('timeout',sql_prefix='COMMIT')
        with pytest.raises(HostedStorageError):
            model.interpret(context,identity)
        assert calls == []
        assert remote.external_budget()['original_nine_provider_calls_used'] == 1
        with pytest.raises(ReconciliationRequired):
            model.interpret(context,identity)
        assert calls == []
        from casepath_api.agent_work.store import ConflictError
        with pytest.raises(ConflictError):
            model.interpret(context,{**identity,'workflow_id':'new-key-bypass'})
        assert calls == []
    finally:
        model._client.close(); remote.close(); server.close()


def test_hosted_generation_fence_prevents_grant_and_reservation_writes(exhausted, proposal, tmp_path):
    server = MockHrana(exhausted.path)
    lease = HostedWorkflowLease(server.connection)
    lease.initialize()
    remote = WorkStore(tmp_path/'unused-remote',connection_factory=lease.connect,validated_source_commit='8'*40)
    token = lease.acquire()
    assert token is not None
    mark = _CURRENT_OWNER.set(token)
    try:
        with server.connection() as db:
            db.execute('UPDATE hosted_workflow_lease SET generation=generation+1')
        with pytest.raises(HostedOwnershipLost):
            apply(remote,proposal)
    finally:
        _CURRENT_OWNER.reset(mark)
        lease.release(token)
    assert 'original_nine_grant' not in remote.external_budget()
    apply(remote,proposal)
    with server.connection() as db:
        db.execute('UPDATE hosted_workflow_lease SET expires_at=0')
    token = lease.acquire()
    assert token is not None
    mark = _CURRENT_OWNER.set(token)
    before = remote.external_budget()
    try:
        with server.connection() as db:
            db.execute('UPDATE hosted_workflow_lease SET expires_at=0')
        with pytest.raises(HostedOwnershipLost):
            begin(remote,proposal,0)
    finally:
        _CURRENT_OWNER.reset(mark)
        lease.release(token)
    assert remote.external_budget() == before
    remote.close(); server.close()


def test_exact_nine_adapter_sends_eighteen_mock_requests_and_replays_without_more(exhausted,proposal,tmp_path,corpus):
    apply(exhausted,proposal)
    server = MockHrana(exhausted.path)
    remote = WorkStore(tmp_path/'unused-remote',connection_factory=server.connection,validated_source_commit='8'*40)
    model,calls = model_for(remote)
    tool = load_tool()
    from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root
    policy = PublicCorpus(default_workspace_corpus_root()).static_policy()
    # Schema-only fixture outputs carry no source assertions, token usage or
    # billing measurements and never reach a claim controller/publication.
    interpretation = {'category':{'family':'unsupported','summary':'Explicit schema fixture','citations':[]},
                      'conditions':[],'documents':[],'steps':[],'knowledge_candidates':[]}
    verification = {'family_supported':False,'checks':[],'issues':['Explicit schema fixture']}
    def fixture(request):
        calls.append(request)
        stage = json.loads(request.content)['response_format']['json_schema']['name']
        output = interpretation if stage == 'casepath_interpret' else verification
        return httpx.Response(200,json={'id':'fixture-only','model':model.config['model'],
            'choices':[{'finish_reason':'stop','message':{'content':json.dumps(output)}}]})
    model._client.close()
    model._client = httpx.Client(transport=httpx.MockTransport(fixture))
    try:
        for index,cid in enumerate(tool.ORIGINAL_IDS):
            context = tool.original_context(corpus,policy,cid,[])
            identity = tool.ORIGINAL_NINE_CANDIDATES[index]['identity']
            first = model.interpret(context,identity)
            final = model.verify(context,first['result'],identity)
            assert model.interpret(context,identity) == first
            assert model.verify(context,first['result'],identity) == final
        assert len(calls) == 18
        budget = remote.external_budget()
        assert budget['original_nine_workflows_used'] == 9 and budget['original_nine_provider_calls_used'] == 18
        assert budget['autonomous_can_start'] is False
        assert all(len(request.content) <= 64000 for request in calls)
        assert all('usage' not in json.loads(request.content) for request in calls)
        remote.close()
        model.store = WorkStore(tmp_path/'unused-restarted',connection_factory=server.connection,validated_source_commit='8'*40)
        assert model.store.external_budget() == budget
        assert model.verify(context,first['result'],identity) == final and len(calls) == 18
        model.store.close()
    finally:
        model._client.close(); remote.close(); server.close()


def test_remote_midpoint_restart_blocks_another_workflow_and_changed_source(exhausted, proposal, tmp_path):
    server = MockHrana(exhausted.path)
    remote = WorkStore(tmp_path/'unused-midpoint',connection_factory=server.connection,validated_source_commit='8'*40)
    try:
        apply(remote,proposal)
        recorded = complete(remote,proposal,0)
        before = remote.external_budget()
        assert before['autonomous_reason'] == 'workflow_in_progress'
        assert before['original_nine_workflow_pending'] is True
        assert before['autonomous_can_start'] is before['in_flight'] is False
        with pytest.raises(ConflictError,match='workflow_in_progress'):
            begin(remote,proposal,1)
        remote.close()
        remote = WorkStore(tmp_path/'unused-midpoint-restarted',connection_factory=server.connection,validated_source_commit='8'*40)
        assert remote.external_budget() == before
        assert begin(remote,proposal,0)['receipt'] == recorded['receipt']
        with pytest.raises(ConflictError,match='workflow_in_progress'):
            begin(remote,proposal,1)
        for source in (None,'unknown','9'*40):
            changed = WorkStore(tmp_path/'unused-changed-source',connection_factory=server.connection,validated_source_commit=source)
            try:
                assert begin(changed,proposal,0)['receipt'] == recorded['receipt']
                with pytest.raises(ConflictError,match='source commit'):
                    begin(changed,proposal,0,'verify')
                assert changed.external_budget() == before
            finally:
                changed.close()
        complete(remote,proposal,0,'verify')
        assert remote.external_budget()['original_nine_workflow_pending'] is False
        assert begin(remote,proposal,1)['intent']['source_commit'] == '8'*40
    finally:
        remote.close(); server.close()


def test_hosted_composition_binds_validated_source_without_model_or_provider(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from casepath_api import hosted_app_v1
    from casepath_api.hosted_sql_v1 import TursoDatabase
    observed = []
    def construct(*args,**kwargs):
        observed.append(kwargs['validated_source_commit'])
        return WorkStore(*args,**kwargs)
    monkeypatch.setattr(hosted_app_v1,'WorkStore',construct)
    server = MockHrana(tmp_path/'isolated-hosted-source.db')
    database = TursoDatabase('libsql://fixture.turso.io','fixture-token-'*4,client_factory=server.client)
    env = {'CASEPATH_SITE_ORIGIN':'https://casepath.example','CASEPATH_PROXY_TOKEN':'t'*48,
        'CASEPATH_SOURCE_COMMIT':'8'*40,'CASEPATH_HOSTED_WRITABLE':'0','CASEPATH_AUTONOMOUS_ENABLED':'0'}
    try:
        with TestClient(hosted_app_v1.create_hosted_app(database=database,environment=env,runtime_directory=tmp_path/'runtime')) as client:
            assert client.get('/healthz').json()['source_commit'] == '8'*40
            assert observed == ['8'*40]
    finally:
        server.close()


def test_whole_apply_cli_gates_mocked_remote_and_replays_one_receipt(exhausted, proposal, tmp_path, monkeypatch, capsys):
    from casepath_api import hosted_sql_v1
    tool = load_tool()
    monkeypatch.setattr(tool,'clean_source_commit',lambda:'8'*40)
    packet_path = tmp_path/'fixture-preflight.json'
    packet_path.write_text(json.dumps(proposal))
    args = ['apply','--apply','--preflight',str(packet_path),
        '--actor','fixture:authenticated-database-operator','--reason','Explicit temporary-fixture application',
        '--idempotency-key','fixture-cli-exact-nine','--human-approval-reference','fixture:direct-human-approval',
        '--acknowledged-preflight-sha256',proposal['preflight_sha256'],
        '--expected-budget-sha256',proposal['prior_budget_sha256'],'--monetary-option','new_018_total_022']
    # Explicit fixture transport values; the real factory is replaced before
    # any apply command. No environment credential is read by this test.
    monkeypatch.setenv('CASEPATH_TURSO_URL','libsql://fixture.turso.io')
    monkeypatch.setenv('TURSO_AUTH_TOKEN','fixture-token-'*4)
    server = MockHrana(exhausted.path)
    lease = HostedWorkflowLease(server.connection)
    lease.initialize()
    constructed = []
    class FixtureDatabase:
        def __init__(self,url,token):
            assert url == 'libsql://fixture.turso.io' and token == 'fixture-token-'*4
            constructed.append(True)
        def connect(self):
            return server.connection()
    monkeypatch.setattr(hosted_sql_v1,'TursoDatabase',FixtureDatabase)
    before = exhausted.external_budget()
    try:
        missing = args.copy()
        index = missing.index('--human-approval-reference')
        del missing[index:index+2]
        with pytest.raises(ValueError,match='authenticated approval'):
            tool.main(missing)
        assert constructed == [] and exhausted.external_budget() == before
        monkeypatch.setattr(tool,'clean_source_commit',lambda:'9'*40)
        with pytest.raises(ValueError,match='source commit changed'):
            tool.main(args)
        assert constructed == [] and exhausted.external_budget() == before
        monkeypatch.setattr(tool,'clean_source_commit',lambda:'8'*40)
        owner = lease.acquire()
        assert owner is not None
        try:
            with pytest.raises(ValueError,match='lease is busy'):
                tool.main(args)
            assert exhausted.external_budget() == before
        finally:
            lease.release(owner)
        assert tool.main(args) == 0
        receipt = json.loads(capsys.readouterr().out)
        after = exhausted.external_budget()
        assert receipt == after['original_nine_grant']
        assert after['original_nine_provider_calls_used'] == after['original_nine_workflows_used'] == 0
        assert tool.main(args) == 0
        assert json.loads(capsys.readouterr().out) == receipt
        assert exhausted.external_budget() == after
        assert len(constructed) == 3
        with server.connection() as db:
            assert db.execute('SELECT COUNT(*) FROM work_original_nine_grant').fetchone()[0] == 1
    finally:
        server.close()
