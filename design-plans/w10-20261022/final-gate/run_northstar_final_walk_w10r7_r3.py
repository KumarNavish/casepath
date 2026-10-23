from pathlib import Path
import subprocess, os, datetime, json, hashlib, urllib.request, math

root = Path.cwd()
sha = (root / '.runtime/northstar-frozen-sha').read_text().strip()
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == sha
dest = root / '.runtime/northstar-final-walk-w10r7-r3'
dest.mkdir(exist_ok=False)
deployment = json.load(urllib.request.urlopen('http://127.0.0.1:4192/deployment.json'))
assert deployment['source_commit'] == sha
assets = {}
for asset in ['autonomous-workspace-v1.js', 'autonomous-workspace-v1.css', 'autonomous-presentation-v1.js', 'autonomous-language-v1.js', 'fonts/Mulish.ttf']:
    source = (root / 'casepath/assets' / asset).read_bytes()
    served = urllib.request.urlopen('http://127.0.0.1:4192/assets/' + asset).read()
    assert served == source, asset
    assets[asset] = hashlib.sha256(source).hexdigest()
report = {'review_commit': sha, 'deployment': deployment, 'served_assets': assets, 'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'status': 'running', 'wrapper_pid': os.getpid(), 'scripts': {}, 'serialized': True, 'origin_adapter': {'file': '.runtime/w10-walk-origin-adapter.mjs', 'sha256': 'dc2fd5fc3cccc51fae60d06c6abac060943af6b5bd6c0f8e9af2f31c3c2874f2', 'scope': 'Replace the single hardcoded acceptance base with its existing validated proofOrigin; no assertion changes.'}}
receipt = dest / 'walk.json'
receipt.write_text(json.dumps(report, indent=2) + '\n')
env = {'HOME': str(Path.home()), 'PATH': '/Users/kumar0002/.local/bin:/usr/local/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'CASEPATH_PROOF_OUTPUT': str(dest), 'CASEPATH_PROOF_ORIGIN': 'http://127.0.0.1:4192', 'NODE_PATH': '/Users/kumar0002/Documents/Die Mobiliar/casepath-canonical/casepath-qa/node_modules', 'PLAYWRIGHT_EXECUTABLE_PATH': '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'}
try:
    for name in ['process', 'memory', 'acceptance', 'reduced', 'motion', 'live-layout', 'presentation']:
        script = root / ('design-plans/w9-20261021/verify_presentation.mjs' if name == 'presentation' else f'design-plans/w8-20261021-mac-r1/verify-{name}.mjs')
        log = dest / (name + '.log')
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        report['scripts'][name] = {'status': 'running', 'started_at': started, 'command': ['/usr/local/bin/node', *(['--import', str(root / '.runtime/w10-walk-origin-adapter.mjs')] if name == 'acceptance' else []), str(script)]}
        with log.open('w') as output:
            proc = subprocess.Popen(report['scripts'][name]['command'], env=env, stdout=output, stderr=subprocess.STDOUT)
            report['scripts'][name]['pid'] = proc.pid
            receipt.write_text(json.dumps(report, indent=2) + '\n')
            code = proc.wait()
        report['scripts'][name].update(status='completed', exit_code=code, finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), log_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
        receipt.write_text(json.dumps(report, indent=2) + '\n')
        print(name, json.dumps(report['scripts'][name]), flush=True)
        assert code == 0, name
        result = json.loads((dest / (name + '-receipt.json')).read_text())
        assert result['passed'] and not result.get('overrides') and not result['errors'] and not result['writes'], name
        assert result['deployment']['source_commit'] == sha
        assert len(result['cleanup']) == 3 and all(x.get('closed') is True or x.get('status') == 'closed' for x in result['cleanup']), name
        if name in ['process', 'memory', 'acceptance', 'live-layout']:
            assert len(result['cases']) == 9
        if name == 'memory':
            assert all(item.get('closed') is True for item in result['cleanup'])
        if name == 'presentation':
            assert all(item['status'] == 'closed' for item in result['cleanup'])
            assert result['allFrames']['count'] == math.ceil(result['manifest']['duration'] * 60 / 1000) and result['live']['animations'] == 0
    process = json.loads((dest / 'process-receipt.json').read_text())
    memory = json.loads((dest / 'memory-receipt.json').read_text())
    live = json.loads((dest / 'live-layout-receipt.json').read_text())
    report['overlap_checks'] = len(process['overlapChecks']) + len(memory['overlapChecks']) + sum(len(case['frames']) for case in live['cases'])
    report['overlaps'] = sum(row['count'] for row in process['overlapChecks']) + sum(row['count'] for row in memory['overlapChecks']) + sum(case['overlapCount'] for case in live['cases'])
    assert report['overlaps'] == 0
    report.update(status='passed', cases=9, errors=0, writes=0)
except Exception as error:
    report.update(status='failed', failure=repr(error))
finally:
    report['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    report['receipt_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dest.glob('*-receipt.json'))}
    receipt.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report), flush=True)
raise SystemExit(0 if report['status'] == 'passed' else 1)
