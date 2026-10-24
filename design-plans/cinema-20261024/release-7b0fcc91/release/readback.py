"""GET-only hosted readback: health, frontend identity, status/budget, knowledge and claim heads.

The proxy token goes from Keychain into request headers only; it is never printed or saved.
Usage: readback.py <output.json> [--require-primary]
"""
if not __debug__:
    raise RuntimeError('Release helpers require Python assertions enabled.')
from pathlib import Path
import hashlib, json, subprocess, sys, time
import httpx

SITE = 'https://casepath-autonomous.kumarnavish.chatgpt.site'
API = 'https://casepath-agent.fastapicloud.dev'
assert len(sys.argv) in (2, 3) and (len(sys.argv) == 2 or sys.argv[2] == '--require-primary')
require_primary = len(sys.argv) == 3
out = Path(sys.argv[1])
assert not out.exists(), 'refusing to overwrite an earlier readback'
token = subprocess.check_output(['/usr/bin/security', 'find-generic-password', '-s', 'CasePath hosted proxy',
                                 '-a', 'kumar0002', '-w'], text=True, stderr=subprocess.DEVNULL).strip()
headers = {'X-CasePath-Proxy-Token': token, 'X-CasePath-Site-Origin': SITE, 'Origin': SITE}
del token
started = time.time()
read_sources = {}
with httpx.Client(trust_env=False, timeout=60) as c:
    def get(url, h=None, primary=False):
        r = c.get(url, headers=h)
        r.raise_for_status()
        observed = r.headers.get('X-CasePath-Read-Source')
        read_sources[url] = observed if observed in ('primary', 'last-verified') else None
        if primary and observed != 'primary':
            raise RuntimeError('Final readback requires a primary database read: ' + url)
        return r.json()
    result = {'observed_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'health': get(API + '/healthz'), 'frontend': get(SITE + '/deployment.json')}
    base = API + '/api/claim-loops/v1/autonomous'
    result['status'] = get(base + '/status', headers)
    result['knowledge'] = get(base + '/knowledge', headers, primary=require_primary)
    result['collection'] = get(base + '/claims?limit=500', headers, primary=require_primary)
del headers
result['primary_reads_required'] = require_primary
result['read_sources'] = read_sources
claims = result['collection'].get('claims', [])
result['summary'] = {
    'claims': len(claims),
    'collection_sha256': hashlib.sha256(json.dumps(result['collection'], sort_keys=True).encode()).hexdigest(),
    'knowledge_sha256': hashlib.sha256(json.dumps(result['knowledge'], sort_keys=True).encode()).hexdigest(),
    'limits': result['status'].get('limits'),
    'seconds': round(time.time() - started, 2),
}
out.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
print(json.dumps({k: v for k, v in result['summary'].items() if k != 'limits'}))
print(json.dumps({k: result['summary']['limits'].get(k) for k in ['provider_calls_used','original_nine_workflows_used','original_nine_provider_calls_used','actual_cost_usd']}))

