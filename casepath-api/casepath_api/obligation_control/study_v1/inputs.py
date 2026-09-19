"""Observable release input projection, with no target or scorer dependency.

All three shared templates and all source-registry entries remain available to
all arms. Source references are shortened by a reversible dictionary, not
selected by relevance. The cohort's domain/family/split are scheduling metadata
and are never included in model messages. No module reads public-dev gold either.
"""
from __future__ import annotations
import base64
import copy
import importlib.metadata
import io
import json
from pathlib import Path
from typing import Any
from .wire import canonical, digest, load, regular_bytes, safe_member, sha, Invalid
from .release_binding import FrozenRelease

ALLOWED_KINDS = {'case_invariant_rule', 'swiss_authority_passage', 'observable_message_span', 'observable_attachment_inventory'}


def registry_view(raw: dict) -> dict:
    entries = raw.get('entries')
    if not isinstance(entries, list) or not entries:
        raise Invalid('model-visible source registry absent')
    # Stable locator-derived names: no family/target routing and no encounter index.
    out = {}
    for entry in entries:
        if entry.get('source_kind') not in ALLOWED_KINDS:
            raise Invalid('unknown registry role requires explicit review')
        locator = entry['locator']
        ref = 's_' + digest(locator)[:24]
        value = {'locator': copy.deepcopy(locator), 'text': str(entry['display_value']),
                 'source_kind': entry['source_kind'], 'support_scope': entry.get('support_scope')}
        if ref in out and out[ref] != value:
            raise Invalid('ambiguous locator identity')
        out[ref] = value
    return dict(sorted(out.items()))


def source_packet(shared_rules: dict, invariant_registry: dict, artifact_texts: dict | None = None) -> dict:
    if shared_rules.get('case_activation_values_included') is not False or shared_rules.get('model_visibility') != 'all_three_templates_identical_for_every_case':
        raise Invalid('shared rules do not declare source-only all-template visibility')
    if any(v.get('source_kind') not in {'case_invariant_rule', 'swiss_authority_passage'} for v in invariant_registry.values()):
        raise Invalid('case-derived registry entry in preparation source')
    value = {'contract': 'casepath.study-source-input/1.0.0', 'rules': shared_rules,
             'registry': invariant_registry, 'artifact_texts': artifact_texts or {}, 'case_inputs_used': False}
    return {**value, 'identity': digest(value)}


def _attachment(raw: dict, expected_pdf_version: str) -> tuple[dict, dict]:
    # This is request input construction, not a corpus integrity sweep.
    required = {'artifact_id', 'content_base64', 'file_name', 'media_type', 'sha256', 'size_bytes'}
    if set(raw) != required:
        raise Invalid('unexpected observable attachment fields')
    data = base64.b64decode(raw['content_base64'], validate=True)
    if len(data) != raw['size_bytes'] or sha(data) != raw['sha256']:
        raise Invalid('observable attachment changed while projecting request')
    value = {k: raw[k] for k in sorted(required - {'content_base64'})}
    media = raw['media_type'].split(';')[0]
    coverage = {'source_id': raw['artifact_id'], 'bytes_read': len(data), 'visual_interpretation': False}
    if media == 'application/pdf':
        import pypdf
        actual = importlib.metadata.version('pypdf')
        if actual != expected_pdf_version:
            raise Invalid(f'PDF projector pin mismatch: required {expected_pdf_version}, installed {actual}')
        reader = pypdf.PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise Invalid('encrypted PDF')
        pages = [page.extract_text(extraction_mode='plain') or '' for page in reader.pages]
        text = '\n\n'.join(f'[page {i}]\n{t}' for i, t in enumerate(pages, 1))
        coverage.update({'extractor': 'pypdf-' + actual, 'pages': len(pages), 'empty_text_pages': [i for i,t in enumerate(pages,1) if not t.strip()], 'representation': 'text_only_not_visual_complete'})
    elif media.startswith('text/') or media in {'message/rfc822', 'application/json'}:
        text = data.decode('utf-8', errors='strict')
        coverage['representation'] = 'utf8_full_text'
    elif media.startswith('image/'):
        text = ''
        coverage['representation'] = 'opaque_binary_no_vision_native_text_track'
    else:
        raise Invalid('unsupported source format: ' + media)
    if len(text.encode('utf-8')) > 800000:
        raise Invalid('source projection exceeds declared bound; no truncation')
    return {**value, 'text': text, 'coverage': coverage}, coverage


def read_release(root: Path, *, expected_pdf_version: str, allow_development_inputs: bool = True) -> tuple[dict, list[dict], dict]:
    root = Path(root)
    release = FrozenRelease(root)
    cohort = release.load('cohort.json')
    shared = release.load('rules/static-rule-templates-v3.json')
    rows = cohort['cases']
    if len(rows) != 150 or len({r['case_id'] for r in rows}) != 150:
        raise Invalid('matrix requires the complete 150-case cohort')
    split = {s: [r for r in rows if r['split'] == s] for s in ('public_dev', 'hidden_test')}
    if [len(split[s]) for s in split] != [60,90] or [len({r['family_id'] for r in split[s]}) for s in split] != [11,17]:
        raise Invalid('complete original split required')
    if {r['family_id'] for r in split['public_dev']} & {r['family_id'] for r in split['hidden_test']}:
        raise Invalid('family overlap')
    all_cases, invariant, coverage = [], None, []
    opened = ['cohort.json', 'rules/static-rule-templates-v3.json']
    for row in sorted(rows, key=lambda r:r['case_id']):
        zone = 'dev' if row['split'] == 'public_dev' else 'test'
        rp = row['source_registry_path']; cp = row['observable_claim_path']
        safe_member(root, rp, (f'data/{zone}/source-registry/',))
        safe_member(root, cp, (f'data/{zone}/claims/',))
        source_registry = release.load(rp)
        claim = release.load(cp)
        opened += [rp, cp]
        if set(claim) != {'contract','customer_message','submission','attachments'}:
            raise Invalid('unexpected observable claim fields')
        registry = registry_view(source_registry)
        static = {k:v for k,v in registry.items() if v['source_kind'] in {'case_invariant_rule','swiss_authority_passage'}}
        if invariant is None:
            invariant = static
        elif invariant != static:
            raise Invalid('shared source registry varies across cases; not silently selecting a domain')
        message = copy.deepcopy(claim['customer_message'])
        original_message = message.pop('raw_file')
        # Preserve exact customer body; original message metadata remains retained.
        if not isinstance(message.get('body'), str):
            raise Invalid('message body absent')
        message_meta = {k:v for k,v in original_message.items() if k != 'content_base64'}
        attachments = []
        materials = {message_meta['artifact_id']: message['body']}
        for att in claim['attachments']:
            projected, cov = _attachment(att, expected_pdf_version)
            attachments.append(projected); coverage.append({'case_id':row['case_id'], **cov})
            materials[att['artifact_id']] = projected['text']
        # An inventory is observable; it is not a claim of substantive adequacy.
        materials['observable_inventory'] = canonical([{'artifact_id':a['artifact_id'],'file_name':a['file_name'],'media_type':a['media_type']} for a in attachments]).decode()
        visible = {'customer_message':message, 'message_source':message_meta,
                   'submission':claim['submission'], 'attachments':attachments,
                   'case_registry':{k:v for k,v in registry.items() if k not in static},
                   'materials':materials}
        all_cases.append({'case_id':row['case_id'], 'split':row['split'], 'family_id':row['family_id'], 'domain':row['domain'],
                          'visible':visible, 'registry':registry, 'visible_sha256':digest(visible),
                          'observable_claim_sha256':release.verified[cp]})
    authority_text = release.read('rules/swiss-authority-passages-v3.txt', 1000000).decode('utf-8')
    opened.append('rules/swiss-authority-passages-v3.txt')
    authority_ids = {v['locator']['artifact_id'] for v in (invariant or {}).values() if v['source_kind'] == 'swiss_authority_passage'}
    sources = source_packet(shared, invariant or {}, {a: authority_text for a in authority_ids})
    sources.pop('identity')
    sources['release_binding'] = release.receipt()
    sources['identity'] = digest(sources)
    report = {'contract':'casepath.study-input-projection/1.0.0', 'projection':'declared_new_request_view_not_byte_identical_to_legacy_model_projection',
              'pdf_extractor':'pypdf-' + expected_pdf_version, 'jpeg':'opaque_native_text_track',
              'cases':len(all_cases), 'splits':{s:len(v) for s,v in split.items()},
              'source_identity':sources['identity'], 'release_binding':release.receipt(),
              'attachment_coverage':coverage,
              'opened_paths':opened, 'target_paths_opened':[], 'scoring_performed':False,
              'access_history':'all 150 intake inputs previously inspected; protected labels not opened here'}
    return sources, all_cases, report
