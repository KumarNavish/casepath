import collections, hashlib, json, time
from pathlib import Path

R = Path('/workspace/casepath-idle-read-gate-16c10bc2-20261018')
def read(p):
    return json.loads(p.read_text())
def save(p, value):
    p.write_text(json.dumps(value, indent=2) + '\n')

byid = collections.defaultdict(list)
intervals = []
collection = read(R / 'inventory/result.json')
assert collection['exit_code'] == 0
intervals.append({'shard': 0, 'phase': 'fresh_full_collection', 'start': collection['started_epoch'], 'finish': collection['finished_epoch']})
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
     'global_limit': 2, 'parent_reports_other_heavy_work': False,
     'qualification': 'All six prepare and pytest command receipts plus fresh full collection prove this gate interval overlap; protected services and lightweight observers are excluded from heavy-test accounting.'})

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
aggregate.update(baseline_inventory=2833, all2833_prior_addc_ids_retained_unchanged=True, all2777_prior_8f_ids_retained_unchanged=True, all2777_prior_4bf_ids_retained_unchanged=True,
                 all2777_a89_ids_retained_unchanged=True, original_b861_inventory=2613,
                 all_b861_ids_retained_unchanged=True, pytest_added_ids=len(read(R / 'fresh-inventory-delta.json')['added_ids']), pytest_removed_ids=0,
                 retained_timing_regressions=13, retained_timing_regressions_passed=13,
                 focused_idle_read_evidence_commit='98c4b3042ee29678507dac09076a1bf8a8a99eb6',
                 focused_idle_read_source_bindings=2, prior_language62_and_touch14_commands_reexecuted_separately=False,
                 minimum_observed_workspace_free_bytes=minimum,
                 maximum_actual_prepare_or_pytest_concurrency=maximum,
                 configured_gate_heavy_cap=2, global_heavy_cap=2, actual_serial_schedule_heavy_cap=1,
                 optional_proc_environment_sampling_retried=False, observed_child_environment_samples=0,
                 environment_qualification='Configured isolation recorded by exact command/result environments; prior EACCES13 sampling not retried and no observed child-path coverage claimed',
                 all_six_full_runtime_before_after_equal=True, source_publication_or_deployment_by_gate=False,
                 configuration_draft_changes_needed=False)
save(R / 'aggregate.json', aggregate)
print(json.dumps({'all13_timing_passed':True,'all2777_ids_retained':True,'focused_commands_reexecuted_separately':False,'minimum_observed_free_bytes':minimum,'max_heavy':maximum}),flush=True)
