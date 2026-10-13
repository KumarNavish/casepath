import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from urllib.parse import quote

REPO = Path('/workspace/casepath-release-ae0-shard6')
OUT = Path('/workspace/casepath-smooth-stage-gate-3a02880a-20261013/shard6')
FIXTURE = OUT / 'pytest-tmp/test_submit_reassesses_arrival0'
PRIOR = '0d9f9e225776195f47d335b38b4ca5244d8c555c'
CANDIDATE = '3a02880abc3f824e06e5e31a888dc91edf1bcb9d'
TEST_ID = 'casepath-api/tests/test_autonomous_adversarial_v1.py::test_submit_reassesses_arrival_after_outcome_before_knowledge_publication'

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def files():
    return {p.relative_to(FIXTURE).as_posix(): {'sha256': digest(p.read_bytes()), 'size_bytes': p.stat().st_size, 'mtime_ns': p.stat().st_mtime_ns}
            for p in FIXTURE.rglob('*') if p.is_file()}

def compact_state(s):
    return {'status': s['status'], 'phase': s['phase'], 'revision': s['revision'], 'run_id': s['run_id'],
            'state_sha256': s['state_sha256'], 'updated_at': s['updated_at'], 'deferral': s.get('deferral'),
            'outcome_status': s['outcome']['status'] if s.get('outcome') else None,
            'source_ids': [x['artifact_id'] for x in s['source_descriptors']],
            'acquired_ids': [x['artifact_id'] for x in s['acquired_sources']],
            'semantic_contexts': {k: {'source_ids': [x['artifact_id'] for x in v['sources']]}
                                  for k, v in s.get('semantic_contexts', {}).items()},
            'knowledge_published': [{'knowledge_id': x.get('knowledge_id'),
                                     'qualification_status': x.get('qualification', {}).get('status'),
                                     'knowledge_sha256': x.get('knowledge_sha256')}
                                    for x in s['knowledge_published']]}

failure = next(json.loads(line) for line in (OUT / 'reports.jsonl').read_text().splitlines()
               if json.loads(line)['id'] == TEST_ID and json.loads(line)['outcome'] == 'failed')
initial_line = next(line for line in failure['failure'].splitlines()
                    if line.startswith('E       AssertionError: Automatic reassessment did not settle: '))
initial_state = ast.literal_eval(initial_line.split('Automatic reassessment did not settle: ', 1)[1])
before = files()
sys.path.insert(0, str(REPO / 'casepath-api'))
from casepath_api.autonomous_store_v1 import AutonomousStore
store = AutonomousStore.open_read_only(FIXTURE / 'claims.sqlite3')
claim_id = initial_state['claim_id']
wal = Path(str(store.path) + '-wal')
assert not wal.exists() or wal.stat().st_size == 0, 'Immutable read cannot ignore nonempty WAL'
connection = sqlite3.connect(f"file:{quote(str(store.path), safe='/')}?mode=ro&immutable=1", uri=True, isolation_level=None)
connection.row_factory = sqlite3.Row
connection.execute('PRAGMA query_only=ON')
final_state, events, _ = store._replay(store._rows(connection, claim_id))
connection.close()
after = files()
assert before == after, 'Read-only inspection changed retained fixture files'

source_paths = ['casepath-api/tests/test_autonomous_adversarial_v1.py',
                'casepath-api/tests/test_autonomous_controller_v1.py',
                'casepath-api/casepath_api/autonomous_controller_v1.py',
                'casepath-api/casepath_api/autonomous_store_v1.py']
source_hashes = []
for rel in source_paths:
    prior = subprocess.check_output(['git', 'show', f'{PRIOR}:{rel}'], cwd=REPO)
    candidate = subprocess.check_output(['git', 'show', f'{CANDIDATE}:{rel}'], cwd=REPO)
    current = (REPO / rel).read_bytes()
    source_hashes.append({'path': rel, 'prior_sha256': digest(prior), 'candidate_sha256': digest(candidate),
                          'checkout_sha256': digest(current), 'all_bytes_equal': prior == candidate == current})
diff_code = subprocess.run(['git', 'diff', '--quiet', PRIOR, CANDIDATE, '--', 'casepath-api'], cwd=REPO).returncode
assert diff_code in (0, 1)

compact_events = []
for e in events:
    row = {k: e[k] for k in ('sequence', 'kind', 'created_at', 'idempotency_key', 'event_sha256', 'resulting_state_sha256')}
    if e['kind'] == 'work.context':
        row['workflow_id'] = e['payload']['workflow_id']
        row['context_source_ids'] = [x['artifact_id'] for x in e['payload']['context']['sources']]
    if e['kind'] in {'interpretation.accepted', 'outcome.recorded'}:
        receipt = e['payload']['receipt']
        row['receipt_workflow_id'] = receipt.get('workflow_id')
        row['receipt_sha256'] = receipt.get('receipt_sha256')
        row['receipt_keys'] = list(receipt)
    if e['kind'] == 'knowledge.published':
        row['qualification_status'] = e['payload']['knowledge'].get('qualification', {}).get('status')
        row['knowledge_sha256'] = e['payload']['knowledge'].get('knowledge_sha256')
    compact_events.append(row)
published = [e for e in events if e['kind'] == 'knowledge.published']
accepted = [e for e in events if e['kind'] == 'interpretation.accepted']
record = {'candidate': CANDIDATE, 'prior': PRIOR, 'test_id': TEST_ID, 'call_duration_seconds': failure['duration'],
          'raw_failure_report_utc_epoch': failure['utc_epoch'], 'raw_failure_trace_sha256': digest(failure['failure'].encode()),
          'fixture': str(FIXTURE), 'journal': str(store.path), 'source_root': str(store.source_root),
          'inspection': 'AutonomousStore.open_read_only object; direct SQLite mode=ro&immutable=1 + PRAGMA query_only=ON; empty WAL asserted; store._replay verifies journal and source hashes',
          'initial_exception_state': compact_state(initial_state), 'post_call_retained_state': compact_state(final_state),
          'event_count': len(events), 'event_kind_counts': dict(Counter(e['kind'] for e in events)), 'events': compact_events,
          'eventual_latest_workflow_knowledge_published': len(published) == 1 and published[0]['idempotency_key'].startswith(final_state['run_id'] + '.'),
          'eventual_knowledge_qualified': len(published) == 1 and published[0]['payload']['knowledge'].get('qualification', {}).get('status') == 'qualified',
          'accepted_interpretation_receipts': len(accepted), 'fixture_hashes_before': before, 'fixture_hashes_after': after,
          'fixture_files_unchanged': before == after, 'source_hashes': source_hashes, 'entire_casepath_api_diff_empty': diff_code == 0,
          'journal_sha256_before_first_SQLite_inspection': '8901d840d213c6b26f7dd1a8fa58b957c18125c4716bbe429eaec2dfe2dcd352',
          'journal_bytes_equal_to_first_inspection_baseline': before['claims.sqlite3']['sha256'] == '8901d840d213c6b26f7dd1a8fa58b957c18125c4716bbe429eaec2dfe2dcd352',
          'SQLite_sidecar_note': 'Earlier mode=ro query_only connections created an empty WAL and touched SHM metadata; helper halted on sidecar difference. Journal and source bytes matched the first inspection baseline; no sidecars were removed. This final immutable read preserves all fixture file hashes and metadata.',
          'await_finished': {'timeout_seconds': 15, 'requirements': ['future exists and is done', 'claim absent from pending set', 'outcome truthy', 'new artifact acquired'],
                             'deadline_exact_timestamp_instrumented': False, 'future_pending_runtime_state_persisted': False},
          'observation': 'Failure snapshot has latest workflow outcome and all sources at revision 26 without knowledge; original attempt journal later has qualified knowledge at revision 27 from the latest workflow.',
          'limits': ['Exact monotonic deadline and raise timestamp are not recorded.', 'Model.calls is not persisted; accepted receipts/phases establish admitted interpretation and verification rather than the in-memory calls assertion.', 'Resource snapshot after the failure does not prove pressure at the deadline.', 'The original test failed; no retry or source changes were performed for this diagnosis.'],
          'recorded_epoch': time.time()}
with (OUT / 'failure-readonly-diagnosis.json').open('x') as handle:
    json.dump(record, handle, indent=2)
print(json.dumps({'event_count': len(events), 'initial_revision': initial_state['revision'], 'final_revision': final_state['revision'],
                  'latest_workflow': final_state['run_id'], 'knowledge_published': record['eventual_latest_workflow_knowledge_published'],
                  'knowledge_qualified': record['eventual_knowledge_qualified'], 'fixture_files_unchanged': before == after,
                  'source_bytes_equal': all(x['all_bytes_equal'] for x in source_hashes), 'entire_casepath_api_diff_empty': diff_code == 0}, indent=2))
