#!/usr/bin/env python3
"""Read-only canonical release DTO derivation; stdout only, no journal or head."""
import hashlib
import json
from pathlib import Path
import sys


def generate(root):
    root = Path(root).resolve()
    sys.path.insert(0, str(root / 'casepath-api'))
    from casepath_api.autonomous_reference_policy_v1 import bounded_reference_policy, SCOPES
    from casepath_api.workspace_corpus import canonical_json_bytes, digest_value

    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    profile_root = root / 'casepath-api/casepath_api/reference_profiles/synthetic-nine-v2'
    profile_raw = (profile_root / 'profile.json').read_bytes()
    profile = json.loads(profile_raw)
    base_path = root / 'casepath-api/casepath_api/corpora/synthetic-150/policy/static-rule-templates-v3.json'
    base = json.loads(base_path.read_bytes())
    policy = bounded_reference_policy(base)
    catalogs = []
    for template in policy['templates']:
        catalog = template['process_catalog']
        catalogs.append({
            'family': template['domain'],
            'rule_pack_sha256': digest_value(template),
            'nodes': [{
                'node_id': node['node_id'], 'label': node['label'],
                'document_types': [doc['document_type'] for doc in catalog['documents']
                                   if node['node_id'] in doc['required_at_node_ids']],
            } for node in catalog['nodes']],
            'transitions': [{
                'edge_id': edge['edge_id'], 'source_node_id': edge['source_node_id'],
                'target_node_id': edge['target_node_id'],
            } for edge in catalog['transitions']],
            'documents': [{
                'document_type': doc['document_type'], 'label': doc['label'],
                'required_at_node_ids': doc['required_at_node_ids'],
            } for doc in catalog['documents']],
        })
    claims = []
    for claim_id, entry in profile['claims'].items():
        matches = []
        for source in entry['sources']:
            raw = (profile_root / claim_id / source['file_name']).read_bytes()
            if sha(raw) != source['sha256'] or len(raw) != source['size_bytes']:
                raise ValueError('release source bytes differ: ' + claim_id)
            text = raw.decode('utf-8')
            for family, scope in SCOPES.items():
                start = text.find(scope['request'])
                if start >= 0:
                    matches.append({
                        'family': family, 'file_name': source['file_name'],
                        'source_sha256': source['sha256'], 'text_sha256': sha(text.encode('utf-8')),
                        'offset_unit': 'unicode_code_point', 'start_char': start,
                        'end_char': start + len(scope['request']), 'quote': scope['request'],
                    })
        if len(matches) != 1:
            raise ValueError('release request must have one exact source match: ' + claim_id)
        claims.append({
            'claim_id': claim_id, 'family': matches[0]['family'],
            # The legacy profile key names the corpus claim binding, not the
            # derived autonomous original-binding wrapper. Match the native
            # ReferenceProfile.match contract explicitly.
            'claim_binding_sha256': entry['original_binding_sha256'],
            'corpus_manifest_sha256': entry['corpus_manifest_sha256'],
            # These are release-profile supplement hashes. They do not assert
            # the selected run's full/current source roster or active sources.
            'source_sha256s': sorted(source['sha256'] for source in entry['sources']),
            'request_source_pin': matches[0],
        })
    value = {
        'contract': 'casepath.release-procedure-outline/1',
        'profile_id': profile['profile_id'], 'profile_raw_sha256': sha(profile_raw),
        'base_policy_sha256': digest_value(base), 'bounded_policy_sha256': digest_value(policy),
        'source_files_sha256': {name: sha((root / name).read_bytes()) for name in [
            'casepath-api/casepath_api/autonomous_reference_policy_v1.py',
            'casepath-api/casepath_api/corpora/synthetic-150/policy/static-rule-templates-v3.json',
            'casepath-api/casepath_api/reference_profiles/synthetic-nine-v1/normative_sources.json',
        ]},
        'catalogs': catalogs, 'claims': claims,
    }
    value['artifact_material_sha256'] = digest_value(value)
    return value


if __name__ == '__main__':
    result = generate(sys.argv[1] if len(sys.argv) > 1 else '/workspace/casepath-cold-start-20261015')
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':')))
