# Stages the nine provider-free reference runs into a copied database. Run from casepath-api/: python stage_reference_nine.py <data-dir> <comma-separated claim ids>
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'casepath-api'))
from casepath_api.autonomous_controller_v1 import AutonomousController
from casepath_api.autonomous_corpus_v1 import CanonicalCorpus
from casepath_api.autonomous_reference_v1 import DeterministicReferenceAdapter, ReferenceProfile, reference_replay_start
from casepath_api.autonomous_reference_policy_v1 import bounded_reference_policy
from casepath_api.autonomous_store_v1 import AutonomousStore
out = Path(sys.argv[1]); path = out/'casepath.db'
corpus = CanonicalCorpus()
policy = bounded_reference_policy(corpus._corpus.static_policy())
store = AutonomousStore(path)
order = sys.argv[2].split(',')
for pid in ('synthetic-nine-v1','synthetic-nine-v2'):
    profile = ReferenceProfile.for_profile(pid)
    controller = AutonomousController(store, policy, reference_adapter=DeterministicReferenceAdapter(policy, profile))
    try:
        for cid in order:
            t=time.time()
            if pid == 'synthetic-nine-v1':
                packet = corpus.packet(cid)
                store.admit_original(cid, packet, expected_revision=0, expected_state_sha256=packet['initial_state_sha256'], idempotency_key='reference.original.'+cid)
            state = store.get(cid)
            known = {d['sha256'] for d in state['source_descriptors']}
            missing = [f for f, s in zip(profile.files(cid), profile.value['claims'][cid]['sources']) if s['sha256'] not in known]
            store.add_sources(cid, missing, expected_revision=state['revision'], expected_state_sha256=state['state_sha256'], idempotency_key='reference.sources.'+profile.sha256[:16]+'.'+cid)
            final = controller.run(cid)
            o = final.get('outcome') or {}
            print(pid, cid, final['revision'], final['status'], o.get('assessment_status'), len(final.get('knowledge_published') or []), len(final.get('knowledge_uses') or []), round(time.time()-t,2), flush=True)
    finally:
        controller.shutdown()
for cid in order:
    head = store.get(cid)
    events = store.events(cid) if hasattr(store,'events') else None
    print('replay_start', cid, 'n/a' if events is None else bool(reference_replay_start(head, events)))
