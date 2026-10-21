"""Writes <outdir>/summary.json for gate_check.sh (stdlib only).

Inputs in <outdir>: .gate-state.tsv (phase results), .gate-notes.txt, test.log, browser.json.
The verdict is "pass" only when every gate condition holds; anything unknown counts as a failure.
"""
import json
import re
import sys
from pathlib import Path

out = Path(sys.argv[1])
state = {}
for line in (out / '.gate-state.tsv').read_text(errors='replace').splitlines() if (out / '.gate-state.tsv').exists() else []:
    if '\t' in line:
        k, v = line.split('\t', 1)
        state[k] = v
notes = [n for n in ((out / '.gate-notes.txt').read_text(errors='replace').splitlines() if (out / '.gate-notes.txt').exists() else []) if n.strip()]
IDS = 9


def as_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ test
log = (out / 'test.log').read_text(errors='replace') if (out / 'test.log').exists() else ''
test = {'exit': as_int(state.get('test_rc')), 'passed': None, 'failed': None, 'errors': None, 'skipped': None,
        'duration_s': as_int(state.get('test_s'))}
summary_line = None
for line in reversed(log.splitlines()):
    s = line.strip().strip('=').strip()
    if re.search(r'\b\d+ (passed|failed|errors?|skipped|deselected|xfailed|xpassed)\b', s) and re.search(r'\bin [\d.]+s\b', s):
        summary_line = s
        break
if summary_line:
    def count(word):
        m = re.search(r'(\d+) ' + word + r'\b', summary_line)
        return int(m.group(1)) if m else 0
    test.update(passed=count('passed'), failed=count('failed'), errors=count('errors?'), skipped=count('skipped'))
    notes.append(f'pytest summary: {summary_line}')
elif test['exit'] is not None:
    notes.append('test.log has no pytest summary line; counts unknown')
failed_names = []
for line in log.splitlines():
    m = re.match(r'^_+ (test\S*|\S+::\S+|ERROR at .+?) _+$', line.rstrip())   # per-test failure/error headers
    if m and m.group(1) not in failed_names:
        failed_names.append(m.group(1))
if failed_names:
    notes.append('failing tests: ' + '; '.join(failed_names[:25]) + (f' (+{len(failed_names) - 25} more)' if len(failed_names) > 25 else ''))
# Environment-only failures. This container denies reading other processes' /proc/<pid>/maps,
# even to root, so the product's registry memory-map audit fails closed, as designed. A failure is
# excluded only when its whole section sits in ENV_FILE and shows that exact denial; every failure
# must be classified, otherwise nothing is excluded.
ENV_FILE = 'casepath-api/tests/test_local_data_root.py'
lines = log.splitlines()
heads = [i for i, l in enumerate(lines) if re.match(r'^_+ (test\S*|\S+::\S+|ERROR at .+?) _+$', l.rstrip())]
env_excluded, other_failed = [], []
for k, i in enumerate(heads):
    j = heads[k + 1] if k + 1 < len(heads) else len(lines)
    for t in range(i + 1, j):
        if re.match(r'^={5,}', lines[t]):
            j = t
            break
    body = '\n'.join(lines[i:j])
    name = re.match(r'^_+ (.+?) _+$', lines[i].rstrip()).group(1)
    blocked = ('PermissionError' in body and '/proc/1/maps' in body) or 'registry memory-map audit is unavailable' in body
    (env_excluded if ENV_FILE in body and blocked and not name.startswith('ERROR at') else other_failed).append(name)
test['env_excluded'] = len(env_excluded)
test['effective_exit'] = test['exit']
test['effective_failed'] = test['failed']
if env_excluded:
    test['env_excluded_tests'] = env_excluded
    test['env_reason'] = ("this container denies reading /proc/<pid>/maps even to root, so the product's registry "
                          'memory-map audit fails closed as designed; only failures in ' + ENV_FILE +
                          ' whose output shows that exact denial are excluded')
    if test['failed'] is not None and len(heads) == (test['failed'] or 0) + (test['errors'] or 0):
        test['effective_failed'] = len([n for n in other_failed if not n.startswith('ERROR at')])
        if not other_failed and not test['errors'] and test['exit'] == 1:
            test['effective_exit'] = 0
    else:
        notes.append(f'failure sections ({len(heads)}) do not match the failure count; no exclusion applied')
    notes.append(f'{len(env_excluded)} environment-only failure(s) excluded (exact /proc maps denial in {ENV_FILE}); '
                 f'other failures: {len(other_failed)}')
skips = sorted({l.strip() for l in log.splitlines() if l.startswith('SKIPPED [')})
if skips:
    notes.append(f'{len(skips)} skip reason line(s): ' + ' | '.join(s[:160] for s in skips[:6]))

# ------------------------------------------------------------------ browser
b = None
if (out / 'browser.json').exists():
    try:
        b = json.loads((out / 'browser.json').read_text())
    except ValueError as e:
        notes.append(f'browser.json unreadable: {e}')


def fmt(ev, key):
    return f"{ev.get('at', '?')}: {str(ev.get(key, ''))[:300]}"


browser = {'cases_total': IDS, 'cases_passed': 0, 'console_errors': [], 'page_errors': [], 'write_requests': [],
           'overlaps': 0, 'failures': []}
if b:
    browser['cases_total'] = b.get('cases_total', IDS)
    browser['cases_passed'] = sum(1 for c in b.get('cases', []) if c.get('passed'))
    browser['console_errors'] = [fmt(e, 'text') for e in b.get('console_errors', [])]
    browser['page_errors'] = [fmt(e, 'message') for e in b.get('page_errors', [])]
    browser['write_requests'] = [f"{w.get('method')} {w.get('url')} ({w.get('at', '?')})" for w in b.get('write_requests', [])]
    browser['overlaps'] = int(b.get('overlaps') or 0)
    browser['failures'] = [{'case': f.get('case', 'global'), 'step': f.get('step', '?'), 'reason': f.get('reason', '')}
                           for f in b.get('failures', [])]
    if not b.get('completed'):
        browser['failures'].append({'case': 'global', 'step': 'browser', 'reason': 'browser walk-through did not complete (see browser.log)'})
    for e in b.get('external_requests', []):
        browser['failures'].append({'case': e.get('at', 'global').split(':')[0], 'step': 'external-request',
                                    'reason': f"blocked request to a non-local origin: {e.get('method')} {e.get('url')}"})
    for o in b.get('observations', [])[:12]:
        notes.append('observation: ' + o)
    if b.get('discovery'):
        d = b['discovery']
        notes.append('ui discovered: ' + ', '.join(f'{k}={v}' for k, v in d.get('summary', {}).items()))
    if b.get('demonstration'):
        dm = b['demonstration']
        notes.append(f"demonstration: {dm.get('result')} ({dm.get('detail', '')})")
    notes.append(f"browser duration {b.get('duration_s')}s at {b.get('base')}")
else:
    reason = 'browser walk-through not run'
    for n in notes:
        if any(w in n for w in ('seeding failed', 'could not start', 'refusing to browse', 'not run', 'prepare failed', 'skipped')):
            reason = n
            break
    browser['failures'].append({'case': 'global', 'step': 'browser', 'reason': reason})

# ------------------------------------------------------------------ verdict
why = []
if test['effective_exit'] != 0:
    why.append(f"test exit {test['exit']}")
if test['passed'] is None:
    why.append('test counts unknown')
elif test['effective_failed'] or test['errors'] or not test['passed']:
    why.append(f"tests: {test['effective_failed']} failed beyond environment-only exclusions, {test['errors']} errors, {test['passed']} passed")
if browser['cases_passed'] != browser['cases_total'] or browser['cases_total'] != IDS:
    why.append(f"{browser['cases_passed']}/{browser['cases_total']} cases passed")
for key in ('console_errors', 'page_errors', 'write_requests'):
    if browser[key]:
        why.append(f'{len(browser[key])} {key}')
if browser['overlaps'] and (b or {}).get('overlaps_gating', True):
    why.append(f"{browser['overlaps']} overlaps")
elif browser['overlaps']:
    notes.append(f"{browser['overlaps']} visible box overlap(s) reported, not gating in the minimum gate (see browser.json overlap_details)")
if browser['failures']:
    why.append(f"{len(browser['failures'])} browser failures")
if state.get('aborted'):
    why.append(f"aborted at {state['aborted']}")
verdict = 'fail' if why else 'pass'
if why:
    notes.insert(0, 'verdict fail: ' + '; '.join(why))
for k in ('fetch_s', 'prepare_s', 'seed_s', 'browser_s', 'total_s'):
    if k in state:
        notes.append(f'{k}={state[k]}')
if 'port' in state:
    notes.append(f"served on 127.0.0.1:{state['port']} from the worktree capsule; worktree {state.get('worktree', '?')}")

summary = {'sha': state.get('sha', ''), 'test': test, 'browser': browser, 'verdict': verdict, 'notes': notes}
(out / 'summary.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False) + '\n')
print(json.dumps({'verdict': verdict, 'why': why}))
