from pathlib import Path
import subprocess, os, datetime, json, hashlib, urllib.request

root = Path.cwd()
sha = (root / '.runtime/w9-final-frozen-sha').read_text().strip()
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == sha
dest = root / '.runtime/w9-final-head-proof'
dest.mkdir(exist_ok=False)
deployment = json.load(urllib.request.urlopen('http://127.0.0.1:4180/deployment.json'))
assert deployment['source_commit'] == sha
assets = {}
for asset in ['autonomous-workspace-v1.js', 'autonomous-workspace-v1.css', 'autonomous-presentation-v1.js', 'autonomous-language-v1.js', 'fonts/Mulish.ttf']:
    source = (root / 'casepath/assets' / asset).read_bytes()
    served = urllib.request.urlopen('http://127.0.0.1:4180/assets/' + asset).read()
    assert served == source, asset
    assets[asset] = hashlib.sha256(source).hexdigest()
report = {'review_commit': sha, 'deployment': deployment, 'served_assets': assets, 'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'status': 'running', 'wrapper_pid': os.getpid(), 'scripts': {}, 'serialized': True}
receipt = dest / 'walk.json'
receipt.write_text(json.dumps(report, indent=2) + '\n')
env = {'HOME': str(Path.home()), 'PATH': '/Users/kumar0002/.local/bin:/usr/local/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'CASEPATH_PROOF_OUTPUT': str(dest)}
try:
    for name in ['process', 'memory', 'acceptance', 'reduced', 'motion', 'live-layout', 'presentation']:
        script = root / ('design-plans/w9-20261021/verify_presentation.mjs' if name == 'presentation' else f'design-plans/w8-20261021-mac-r1/verify-{name}.mjs')
        log = dest / (name + '.log')
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        report['scripts'][name] = {'status': 'running', 'started_at': started, 'command': ['/usr/local/bin/node', str(script)]}
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
        if name in ['process', 'memory', 'acceptance', 'live-layout']:
            assert len(result['cases']) == 9
        if name == 'memory':
            assert all(item.get('closed') is True for item in result['cleanup'])
        if name == 'presentation':
            assert all(item['status'] == 'closed' for item in result['cleanup'])
            assert result['allFrames']['count'] == result['manifest']['duration'] * 60 / 1000 and result['live']['animations'] == 0
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
