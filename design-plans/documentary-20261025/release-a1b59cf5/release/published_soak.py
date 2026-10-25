#!/usr/bin/env python3
"""Published CasePath: 50 cycles x 6 sequential GETs, plus seven identity/readback GETs."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import httpx

SITE = 'https://casepath-autonomous.kumarnavish.chatgpt.site'
API = 'https://casepath-agent.fastapicloud.dev'
PREFIX = '/api/claim-loops/v1/autonomous'
ORIGINALS = [
    'clm_0c5e7c7723a3c694', 'clm_2a9c260c26afaa34', 'clm_521c20913f4e0f9b',
    'clm_7dbd7c7d1c4ddf90', 'clm_9a179a4481767d43', 'clm_c44ddc0914ba9298',
    'clm_e262801f9368bc12', 'clm_ee29ac770b1bf7b9', 'clm_f69b1747447bc221',
]

class CheckFailure(Exception):
    def __init__(self, code, **digests):
        super().__init__(code)
        self.code, self.digests = code, digests

def now():
    return datetime.now(timezone.utc).isoformat()

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode()

def json_sha(value):
    return sha(canonical(value))

def reject_constant(_):
    raise ValueError('Non-finite JSON number')

def decode(raw):
    return json.loads(raw, parse_constant=reject_constant)

def require(ok, code):
    if not ok:
        raise CheckFailure(code)

def same(expected, actual, code):
    left, right = json_sha(expected), json_sha(actual)
    if left != right:
        raise CheckFailure(code, expected_sha256=left, actual_sha256=right)

def percentile(values, fraction):
    ordered = sorted(values)
    at = (len(ordered) - 1) * fraction
    lo, hi = int(at), min(int(at) + 1, len(ordered) - 1)
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (at - lo), 3)

def route_summary(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[(r['origin'], r['template'])].append(r)
    result = {}
    for (origin, template), entries in sorted(groups.items()):
        elapsed = [e['elapsed_ms'] for e in entries]
        sources = Counter(e.get('read_source') or 'missing' for e in entries)
        result[origin + ' ' + template] = {
            'requests': len(entries), 'passed': sum(e['passed'] for e in entries),
            'latency_ms': {'min': min(elapsed), 'p50': percentile(elapsed, .5),
                           'p95': percentile(elapsed, .95), 'p99': percentile(elapsed, .99),
                           'max': max(elapsed)},
            'read_source_counts': dict(sources),
        }
    return result

def execute(args, emit):
    raw = Path(args.baseline).read_bytes()
    baseline = decode(raw)
    require(isinstance(baseline, dict), 'baseline_not_object')
    collection = baseline.get('collection')
    require(isinstance(collection, dict), 'baseline_collection_not_object')
    require(type(collection.get('limit')) is int and collection['limit'] == 500,
            'baseline_limit_not_500')
    require(type(collection.get('offset')) is int and collection['offset'] == 0,
            'baseline_offset_not_zero')
    require(type(collection.get('total')) is int and collection['total'] == 159,
            'baseline_total_not_159')
    require(isinstance(collection.get('claims'), list) and len(collection['claims']) == 159,
            'baseline_claim_count_not_159')
    require(isinstance(baseline.get('knowledge'), dict), 'baseline_knowledge_missing')
    require(isinstance(baseline.get('summary'), dict)
            and isinstance(baseline['summary'].get('limits'), dict), 'baseline_limits_missing')
    heads = {row['claim_id']: row for row in collection['claims']}
    require(len(heads) == 159, 'baseline_duplicate_claim')
    for cid in ORIGINALS:
        require(cid in heads and heads[cid].get('mode') == 'saved'
                and isinstance(heads[cid].get('revision'), int) and heads[cid]['revision'] > 0,
                'baseline_original_history_not_saved')
        for key in ('state_sha256', 'last_event_sha256'):
            require(isinstance(heads[cid].get(key), str)
                    and re.fullmatch('[0-9a-f]{64}', heads[cid][key]) is not None,
                    'baseline_original_history_hash_missing')
    emit({'kind': 'baseline', 'timestamp': now(), 'baseline_sha256': sha(raw),
          'collection_sha256': json_sha(collection),
          'knowledge_sha256': json_sha(baseline['knowledge']),
          'limits_sha256': json_sha(baseline['summary']['limits']),
          'claim_count': 159, 'saved_original_histories': ORIGINALS})

    token = subprocess.check_output(
        ['/usr/bin/security', 'find-generic-password', '-s', 'CasePath hosted proxy',
         '-a', 'kumar0002', '-w'], stderr=subprocess.DEVNULL).decode().strip()
    require(bool(token) and token.isascii() and '\r' not in token and '\n' not in token,
            'proxy_token_invalid')
    headers = {'X-CasePath-Proxy-Token': token, 'X-CasePath-Site-Origin': SITE, 'Origin': SITE}
    first_hashes = {}

    def safe_header(value):
        return value.replace(token, '[redacted]')[:8192] if value else None

    def consistent(key, value):
        digest = json_sha(value)
        before = first_hashes.setdefault(key, digest)
        if before != digest:
            raise CheckFailure('route_payload_changed', expected_sha256=before, actual_sha256=digest)

    def health(value):
        require(isinstance(value, dict), 'health_not_object')
        require(value.get('source_commit') == args.source, 'api_source_mismatch')
        require(value.get('status') == 'ok' and value.get('read_only') is True
                and value.get('writable') is False and value.get('storage') == 'remote_primary',
                'api_health_contract_failed')

    def frontend(value):
        require(isinstance(value, dict) and value.get('source_commit') == args.source,
                'site_source_mismatch')

    def claims(value, limit):
        # The verified router hashes the full ordered collection; only its echoed
        # limit differs between the complete 159-row limit=200 and limit=500 reads.
        expected = dict(collection)
        expected['limit'] = limit
        same(expected, value, 'collection_baseline_mismatch')
        if limit == 200:
            consistent('claims?limit=200', value)

    def knowledge(value):
        same(baseline['knowledge'], value, 'knowledge_baseline_mismatch')
        consistent('knowledge', value)

    def snapshot(value, cid):
        require(isinstance(value, dict) and isinstance(value.get('state'), dict),
                'snapshot_state_missing')
        require(value['state'].get('claim_id') == cid, 'snapshot_claim_identity_mismatch')
        require(value.get('mode') == 'saved' and isinstance(value.get('events'), list)
                and len(value['events']) > 0, 'snapshot_not_saved_history')
        expected = heads[cid]
        require(value.get('current_revision') == expected['revision']
                and value['state'].get('revision') == expected['revision'],
                'snapshot_revision_changed')
        require(value.get('current_state_sha256') == expected['state_sha256']
                and value['state'].get('state_sha256') == expected['state_sha256'],
                'snapshot_state_hash_changed')
        require(value.get('current_event_sha256') == expected['last_event_sha256']
                and value.get('cursor_sha256') == expected['last_event_sha256'],
                'snapshot_event_hash_changed')
        consistent(('snapshot', cid), value)

    def status(value):
        require(isinstance(value, dict) and 'limits' in value, 'status_limits_missing')
        require(value.get('read_only') is True and value.get('writable') is False,
                'status_read_only_contract_failed')
        same(baseline['summary']['limits'], value['limits'], 'ledger_baseline_mismatch')

    with httpx.Client(trust_env=False, timeout=20, follow_redirects=False) as client:
        def get(origin, path, phase, template, validator, cycle=None, cid=None):
            started = time.monotonic()
            row = {'kind': 'http', 'timestamp': now(), 'phase': phase, 'origin': origin,
                   'method': 'GET', 'template': template, 'cycle': cycle, 'claim_id': cid,
                   'status': None, 'elapsed_ms': None, 'valid_json': False,
                   'body_sha256': None, 'json_sha256': None, 'read_source': None,
                   'server_timing': None, 'passed': False}
            try:
                response = client.get((API if origin == 'api' else SITE) + path,
                                      headers=headers if origin == 'api' else None)
                row.update(status=response.status_code,
                           elapsed_ms=round((time.monotonic() - started) * 1000, 3),
                           body_sha256=sha(response.content),
                           read_source=safe_header(response.headers.get('X-CasePath-Read-Source')),
                           server_timing=safe_header(response.headers.get('Server-Timing')))
                require(response.status_code == 200, 'http_status_not_200')
                if phase == 'final_readback' and template in {'/knowledge', '/claims?limit=500'}:
                    require(row['read_source'] == 'primary', 'final_readback_not_primary')
                value = decode(response.content)
                row.update(valid_json=True, json_sha256=json_sha(value))
                validator(value)
                row['passed'] = True
            except Exception as error:
                if row['elapsed_ms'] is None:
                    row['elapsed_ms'] = round((time.monotonic() - started) * 1000, 3)
                row.update(error_type=type(error).__name__,
                           error_code=error.code if isinstance(error, CheckFailure)
                           else 'request_or_validation_error')
                if isinstance(error, CheckFailure):
                    row.update(error.digests)
                emit(row)
                raise
            emit(row)

        get('api', '/healthz', 'before', '/healthz', health)
        get('site', '/deployment.json', 'before', '/deployment.json', frontend)
        for cycle in range(1, 51):
            cid = ORIGINALS[(cycle - 1) % 9]
            for origin in ('api', 'site'):
                get(origin, PREFIX + '/claims?limit=200', 'soak', '/claims?limit=200',
                    lambda v: claims(v, 200), cycle)
                get(origin, PREFIX + '/knowledge', 'soak', '/knowledge', knowledge, cycle)
                get(origin, PREFIX + '/claims/' + cid + '/snapshot', 'soak',
                    '/claims/{claim_id}/snapshot', lambda v, c=cid: snapshot(v, c), cycle, cid)
            if cycle % 5 == 0:
                print(json.dumps({'cycle': cycle, 'successful_soak_requests': cycle * 6}), flush=True)
        get('api', '/healthz', 'after', '/healthz', health)
        get('site', '/deployment.json', 'after', '/deployment.json', frontend)
        get('api', PREFIX + '/status', 'final_readback', '/status', status)
        get('api', PREFIX + '/knowledge', 'final_readback', '/knowledge', knowledge)
        get('api', PREFIX + '/claims?limit=500', 'final_readback', '/claims?limit=500',
            lambda v: claims(v, 500))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True)
    p.add_argument('--baseline', required=True)
    p.add_argument('--out', required=True)
    args = p.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', args.source):
        p.error('source must be a lowercase 40-character SHA')
    out = Path(args.out).resolve()
    out.mkdir(mode=0o700, parents=False, exist_ok=False)
    records, failure, complete = [], None, False
    started = now()
    fd = os.open(out / 'receipts.jsonl', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as evidence:
        def emit(record):
            entry = {'sequence': len(records) + 1, **record}
            evidence.write(canonical(entry).decode() + '\n')
            evidence.flush()
            os.fsync(evidence.fileno())
            records.append(entry)
        emit({'kind': 'run_start', 'timestamp': started, 'source_commit': args.source,
              'script_sha256': sha(Path(__file__).read_bytes()), 'expected_soak_requests': 300,
              'verification_requests': 7, 'cycles': 50, 'sequential': True,
              'runner_retries': 0, 'provider_calls_initiated': 0, 'methods': ['GET']})
        try:
            execute(args, emit)
            complete = True
        except Exception as error:
            failure = {'error_type': type(error).__name__,
                       'error_code': error.code if isinstance(error, CheckFailure)
                       else 'setup_or_request_failure'}
            if isinstance(error, CheckFailure):
                failure.update(error.digests)
            emit({'kind': 'run_failure', 'timestamp': now(), **failure})
        http = [r for r in records if r['kind'] == 'http']
        soak = [r for r in http if r['phase'] == 'soak']
        passed = (complete and len(http) == 307 and len(soak) == 300
                  and all(r['passed'] and r['status'] == 200 and r['valid_json'] for r in http))
        ended = now()
        emit({'kind': 'run_end', 'timestamp': ended, 'passed': passed,
              'observed_soak_requests': len(soak)})
    summary = {
        'contract': 'casepath.published-read-soak/1', 'source_commit': args.source,
        'started_at': started, 'finished_at': ended, 'passed': passed, 'failure': failure,
        'expected_soak_requests': 300, 'observed_soak_requests': len(soak),
        'successful_soak_requests': sum(r['passed'] for r in soak),
        'soak_http_503_count': sum(r['status'] == 503 for r in soak),
        'all_http_503_count': sum(r['status'] == 503 for r in http),
        'verification_requests': len(http) - len(soak),
        'source_and_final_readbacks_passed': complete,
        'saved_original_histories': ORIGINALS,
        'last_verified_soak_count': sum(r.get('read_source') == 'last-verified' for r in soak),
        'routes': route_summary(soak), 'sequential': True, 'runner_retries': 0,
        'provider_calls_initiated': 0, 'methods': ['GET'], 'response_bodies_persisted': False,
        'receipts_sha256': sha((out / 'receipts.jsonl').read_bytes()),
        'script_sha256': sha(Path(__file__).read_bytes()),
    }
    fd = os.open(out / 'summary.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    print(json.dumps({'passed': passed, 'observed_soak_requests': len(soak),
                      'soak_http_503_count': summary['soak_http_503_count'],
                      'failure': failure, 'summary': str(out / 'summary.json')}), flush=True)
    return 0 if passed else 1

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(json.dumps({'passed': False, 'error_code': 'runner_or_evidence_write_failure',
                          'error_type': type(error).__name__}), flush=True)
        sys.exit(2)

