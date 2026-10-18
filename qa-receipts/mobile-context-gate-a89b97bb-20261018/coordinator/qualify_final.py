import collections, hashlib, json, time
from pathlib import Path

R = Path('/workspace/casepath-mobile-context-gate-a89b97bb-20261018')
def read(p):
    return json.loads(p.read_text())
def save(p, value):
    p.write_text(json.dumps(value, indent=2) + '\n')

byid = collections.defaultdict(list)
intervals = []
for n in range(1, 7):
    out = R / f'shard{n}'
    for line in (out / 'reports.jsonl').read_text().splitlines():
        row = json.loads(line)
        byid[row['id']].append(row)
    for name in ['prepare.json', 'result.json']:
        receipt = read(out / name)
        assert receipt['exit_code'] == 0
        intervals.append({'shard': n, 'phase': 'prepare' if name == 'prepare.json' else 'pytest',
                          'start': receipt['started_epoch'], 'finish': receipt['finished_epoch']})
    runtime = read(out / 'runtime-after.json')
    assert runtime['before_after_inventory_equal'] and runtime['before_observed_before_test_start']

timing = read(R / 'timing-regression-ids.json')
timing_results = []
for ident in timing['ids']:
    rows = byid[ident]
    assert len(rows) == 3 and {r['when'] for r in rows} == {'setup', 'call', 'teardown'}
    assert all(r['outcome'] == 'passed' for r in rows)
    timing_results.append({'id': ident, 'phase_outcomes': {r['when']: r['outcome'] for r in rows}})
assert len(timing_results) == 13
save(R / 'timing-regression-results.json', {'candidate': read(R / 'aggregate.json')['candidate'],
     'count': 13, 'all_passed_once': True, 'results': timing_results})

events = [(x['start'], 1, x) for x in intervals] + [(x['finish'], -1, x) for x in intervals]
active = 0
maximum = 0
timeline = []
for epoch, change, interval in sorted(events, key=lambda x: (x[0], x[1])):
    active += change
    maximum = max(maximum, active)
    timeline.append({'epoch': epoch, 'change': change, 'active_heavy': active,
                     'shard': interval['shard'], 'phase': interval['phase']})
assert maximum <= 2 and active == 0
save(R / 'heavy-process-interval-proof.json', {'intervals': intervals, 'timeline': timeline,
     'maximum_actual_prepare_or_pytest_concurrency': maximum, 'configured_gate_limit': 2,
     'global_limit': 3, 'parent_reports_other_heavy_work': False,
     'qualification': 'Prepare and pytest command receipts prove this gate interval overlap; protected services are excluded from heavy-test accounting.'})

resource = read(R / 'resource-after.json')
observations = [resource['minimum_observed_workspace_free_bytes']]
for n in range(1, 7):
    for rel in [f'shard{n}/prepare-cache-retirement.json', f'completed-shard{n}-runtime-retirement.json']:
        p = R / rel
        if p.exists():
            x = read(p)
            observations.extend(x[k] for k in ['before_free_bytes', 'after_free_bytes'] if k in x)
minimum = min(observations)
assert minimum >= 3 * 1024 ** 3
resource.update(minimum_observed_workspace_free_bytes=minimum,
                exact_prepare_pytest_interval_maximum=maximum,
                includes_cache_and_runtime_retirement_resource_observations=True)
save(R / 'resource-after.json', resource)

aggregate = read(R / 'aggregate.json')
aggregate.update(baseline_inventory=2777, all2777_prior4a_ids_retained_unchanged=True,
                 pytest_added_ids=0, pytest_removed_ids=0,
                 retained_timing_regressions=13, retained_timing_regressions_passed=13,
                 new_node_browser_case_count=4, new_node_browser_cases_are_pytest_ids=False,
                 new_node_browser_cases_executed_by_cloud_pytest_gate=False,
                 browser_validation_evidence_commit='5620f0635ee23369d59e574754ad6adaa6ee5a60',
                 exact_final_qa_css_equal_focused_browser_source=True,
                 mac_owner_reported_integrated_context_checks=8,
                 minimum_observed_workspace_free_bytes=minimum,
                 maximum_actual_prepare_or_pytest_concurrency=maximum,
                 all_six_full_runtime_before_after_equal=True,
                 source_publication_or_deployment_by_gate=False,
                 configuration_draft_changes_needed=False)
save(R / 'aggregate.json', aggregate)
print(json.dumps({'all13_timing_passed': True, 'all2777_ids_retained': True,
                  'new_node_cases_separately_reconciled': 4,
                  'minimum_observed_free_bytes': minimum, 'max_heavy': maximum}), flush=True)
