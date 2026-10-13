from collections import Counter
import json
from pathlib import Path
import time

OUT = Path('/workspace/casepath-smooth-stage-gate-3a02880a-20261013/attempt2-shard6')
TARGET = 'casepath-api/tests/test_autonomous_adversarial_v1.py::test_submit_reassesses_arrival_after_outcome_before_knowledge_publication'
raw = (OUT / 'reports.jsonl').read_text()
lines = raw.splitlines()
if raw and not raw.endswith('\n'):
    lines = lines[:-1]
reports = [json.loads(line) for line in lines]
latch = json.loads((OUT / 'ATTEMPT_STARTED.json').read_text())
result = json.loads((OUT / 'result.json').read_text()) if (OUT / 'result.json').exists() else None
print(json.dumps({'elapsed_seconds': round(time.time() - latch['started_epoch'], 1),
                  'terminal': result is not None,
                  'terminal_exit_code': result['exit_code'] if result else None,
                  'terminal_duration_seconds': result['duration_seconds'] if result else None,
                  'phase_counts': {f'{w}/{o}': n for (w, o), n in Counter((r['when'], r['outcome']) for r in reports).items()},
                  'last_id': reports[-1]['id'] if reports else None,
                  'previously_failed_test_phases': [{k: r[k] for k in ('when', 'outcome', 'duration', 'utc_epoch')} for r in reports if r['id'] == TARGET],
                  'failures': [{'id': r['id'], 'when': r['when']} for r in reports if r['outcome'] == 'failed']}, indent=2))
