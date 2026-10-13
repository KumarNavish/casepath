import base64, gzip, json, sys, tempfile, time
from pathlib import Path
from unittest.mock import patch
sys.path[:0] = [str(Path.cwd()/'casepath-api'), str(Path.cwd()/'casepath-api/tests'), str(Path.cwd()/'casepath-qa')]
from fastapi import FastAPI
from fastapi.testclient import TestClient
from casepath_api.autonomous_api_v1 import create_autonomous_router
from casepath_api.autonomous_corpus_v1 import CanonicalCorpus
from casepath_api.autonomous_reference_v1 import ReferenceProfile
from test_complete_reference_intake_v1 import service_at, admit, assert_exact_prefixes
from importlib.util import spec_from_file_location, module_from_spec
spec = spec_from_file_location('existing_clock', Path.cwd()/'casepath-qa/build-prior-assessment-fixture-v1.py')
clock = module_from_spec(spec); spec.loader.exec_module(clock)
started = time.perf_counter()
with tempfile.TemporaryDirectory(prefix='casepath-native-v1-v2-qa-') as temporary, patch('casepath_api.autonomous_store_v1.datetime', clock.FixtureClock):
    corpus = CanonicalCorpus(); path = Path(temporary)/'claims.sqlite'
    legacy = ReferenceProfile.for_profile('synthetic-nine-v1')
    ids = ReferenceProfile().ids
    old = service_at(path, corpus, legacy)
    before = {}; unprocessed = {}
    initial_app = FastAPI(); initial_app.include_router(create_autonomous_router(lambda: old, corpus_getter=lambda: corpus, read_only=True))
    try:
        with TestClient(initial_app) as initial_client:
            for cid in ids:
                response = initial_client.get('/api/claim-loops/v1/autonomous/claims/' + cid + '/snapshot')
                response.raise_for_status(); unprocessed[cid] = response.json()
                assert unprocessed[cid]['state']['revision'] == 0 and unprocessed[cid]['current_revision'] == 0
        for cid in ids:
            admit(old, corpus, cid)
            before[cid] = old.run(cid)
            assert before[cid]['outcome']['assessment_status'] == 'complete'
            print('legacy completed ' + cid, file=sys.stderr, flush=True)
    finally:
        old.shutdown()
    service = service_at(path, corpus); app = FastAPI()
    app.include_router(create_autonomous_router(lambda: service, corpus_getter=lambda: corpus, read_only=True))
    output = {'snapshots': {}, 'prefixes': {}, 'unprocessed': unprocessed, 'sources': {}, 'raw_sources': {},
              'knowledge': None, 'profile_sha256': ReferenceProfile().sha256, 'earlier_context': None,
              'before_v1_snapshots': {}}
    try:
        with TestClient(app) as client:
            base = '/api/claim-loops/v1/autonomous'
            def get(path):
                response = client.get(base+path); response.raise_for_status(); return response.json()
            for cid in ids:
                output['before_v1_snapshots'][cid] = get('/claims/'+cid+'/snapshot')
                previous = before[cid]
                service.store.add_sources(cid, ReferenceProfile().files(cid), expected_revision=previous['revision'],
                    expected_state_sha256=previous['state_sha256'], idempotency_key='qa-v2-after-v1-' + cid)
                state = service.run(cid)
                assert state['outcome']['assessment_status'] == 'complete', state.get('deferral')
                assert_exact_prefixes(service.store, cid)
                output['snapshots'][cid] = get('/claims/'+cid+'/snapshot')
                replay_start = output['snapshots'][cid]['replay_start']
                assert replay_start is not None
                output['prefixes'][cid] = {}
                for seq in range(state['revision']+1):
                    prefix = get('/claims/'+cid+'/replay?through_seq='+str(seq))
                    assert prefix['replay_start'] == replay_start
                    output['prefixes'][cid][str(seq)] = prefix
                assert output['prefixes'][cid]['0']['state'] == output['unprocessed'][cid]['state']
                assert output['prefixes'][cid][str(previous['revision'])]['state'] == previous
                assert output['prefixes'][cid][str(replay_start['from_seq'])]['state']['state_sha256'] == replay_start['state_sha256']
                for descriptor in state['source_descriptors']:
                    identity = cid+'/'+descriptor['artifact_id']; output['sources'][identity] = get('/sources/'+identity+'/text')
                    response = client.get(base+'/sources/'+identity); response.raise_for_status()
                    output['raw_sources'][identity] = base64.b64encode(response.content).decode()
                assert service.run(cid) == state
                print('v2 exported ' + cid + ' prefixes=' + str(state['revision']+1), file=sys.stderr, flush=True)
            output['knowledge'] = get('/knowledge')
        raw = json.dumps(output, sort_keys=True).encode()
        target = Path(sys.argv[1]); target.write_bytes(raw)
        with gzip.GzipFile(filename=str(target)+'.gz', mode='wb', mtime=0) as compressed:
            compressed.write(raw)
        print(json.dumps({'fixture': str(target), 'size_bytes': len(raw), 'gzip_bytes': Path(str(target)+'.gz').stat().st_size,
                          'claims': len(ids), 'prefixes': sum(len(p) for p in output['prefixes'].values()),
                          'sources': len(output['sources']), 'profile_sha256': output['profile_sha256'],
                          'elapsed_seconds': time.perf_counter()-started}), file=sys.stderr, flush=True)
    finally:
        service.shutdown()
