# Stages the nine provider-free reference histories into a disposable database.
# Adapted from design-plans/tools/stage_reference_nine.py (branch claude/casepath-cues-prototype).
# Usage: <venv python> stage_nine.py <casepath-api dir> <data dir> <comma-separated claim ids>
# Deterministic reference adapter only: no provider, no network.
import json
import sys
import time
from pathlib import Path

api_dir, out, order = Path(sys.argv[1]).resolve(), Path(sys.argv[2]), sys.argv[3].split(',')
sys.path.insert(0, str(api_dir))
from casepath_api.autonomous_controller_v1 import AutonomousController  # noqa: E402
from casepath_api.autonomous_corpus_v1 import CanonicalCorpus  # noqa: E402
from casepath_api.autonomous_reference_v1 import DeterministicReferenceAdapter, ReferenceProfile  # noqa: E402
from casepath_api.autonomous_reference_policy_v1 import bounded_reference_policy  # noqa: E402
from casepath_api.autonomous_store_v1 import AutonomousStore  # noqa: E402

out.mkdir(parents=True, exist_ok=True)
corpus = CanonicalCorpus()
policy = bounded_reference_policy(corpus._corpus.static_policy())
store = AutonomousStore(out / 'casepath.db')
rows = []
for pid in ('synthetic-nine-v1', 'synthetic-nine-v2'):
    profile = ReferenceProfile.for_profile(pid)
    controller = AutonomousController(store, policy, reference_adapter=DeterministicReferenceAdapter(policy, profile))
    try:
        for cid in order:
            t = time.time()
            if pid == 'synthetic-nine-v1':
                packet = corpus.packet(cid)
                store.admit_original(cid, packet, expected_revision=0,
                                     expected_state_sha256=packet['initial_state_sha256'],
                                     idempotency_key='reference.original.' + cid)
            state = store.get(cid)
            known = {d['sha256'] for d in state['source_descriptors']}
            missing = [f for f, s in zip(profile.files(cid), profile.value['claims'][cid]['sources'])
                       if s['sha256'] not in known]
            store.add_sources(cid, missing, expected_revision=state['revision'],
                              expected_state_sha256=state['state_sha256'],
                              idempotency_key='reference.sources.' + profile.sha256[:16] + '.' + cid)
            final = controller.run(cid)
            o = final.get('outcome') or {}
            row = {'profile': pid, 'claim': cid, 'revision': final['revision'], 'status': final['status'],
                   'assessment_status': o.get('assessment_status'),
                   'knowledge_published': len(final.get('knowledge_published') or []),
                   'knowledge_uses': len(final.get('knowledge_uses') or []),
                   'seconds': round(time.time() - t, 2)}
            rows.append(row)
            print(json.dumps(row), flush=True)
    finally:
        controller.shutdown()
print(json.dumps({'staged': len(rows), 'final_status': {cid: store.get(cid)['status'] for cid in order}}), flush=True)
