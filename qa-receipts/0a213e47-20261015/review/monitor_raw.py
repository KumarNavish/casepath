"""Read currently complete report lines; does not execute tests or modify gate state."""
from pathlib import Path
import json
import time

root = Path('/workspace/casepath-transport-gate-0a213e47-20261015')
snapshot = {'epoch': time.time(), 'shards': []}
for number in range(1, 7):
    path = root / ('shard' + str(number))
    reports = path / 'reports.jsonl'
    rows = []
    if reports.exists():
        for line in reports.read_text().splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                # A concurrently appended partial last line is not terminal evidence.
                pass
    result = path / 'result.json'
    item = {'shard': number, 'phase_rows_so_far': len(rows),
            'failed_reports': [row for row in rows if row['outcome'] == 'failed'],
            'terminal': result.exists()}
    if result.exists():
        item['runner_exit'] = json.loads(result.read_text())['exit_code']
    snapshot['shards'].append(item)
with (root / 'review/live-monitor-snapshots.jsonl').open('a') as handle:
    handle.write(json.dumps(snapshot) + '\n')
print(json.dumps(snapshot))
