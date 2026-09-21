"""Validate/model-materialize source-only preparation without evaluator access."""
from __future__ import annotations
import copy
from pathlib import Path
from ..source_only_runtime_v1 import SourceOnlyRuntime, FILES
from ..obligation_control_v1 import fields, Invalid
from .wire import canonical, decode, digest, save, sha


def runtime_registry(sources: dict) -> dict:
    result = {}
    for ref, row in sources['registry'].items():
        if row['source_kind'] not in {'case_invariant_rule','swiss_authority_passage'}:
            raise Invalid('non-normative entry in preparation registry')
        locator = row['locator']
        # Offsets refer to the complete normalized public artifact, not the quote.
        text = sources.get('artifact_texts', {}).get(locator['artifact_id'], row['text'])
        result[ref] = {'locator':copy.deepcopy(locator), 'text':text}
    return result


def materialize(sources: dict, output: dict, directory: Path, *, response_receipt_sha256: str, origin: str) -> dict:
    if origin not in {'engineering_fixture','model_execution'}:
        raise Invalid('unknown preparation origin')
    fields(output, {'control','capabilities','native_binding','variable_descriptions','source_accounting'})
    if set(output['variable_descriptions']) != set(output['control']['variables']) or any(not isinstance(v,str) or not v.strip() for v in output['variable_descriptions'].values()):
        raise Invalid('every primitive requires a case-testable meaning')
    account = output['source_accounting']
    if set(account) != set(sources['registry']):
        raise Invalid('source accounting omitted or introduced a source')
    for item in account.values():
        fields(item, {'status','reason'})
        if item['status'] not in {'used','non_evidentiary'} or not isinstance(item['reason'],str) or not item['reason'].strip():
            raise Invalid('unjustified source classification')
    registry = runtime_registry(sources)
    runtime = SourceOnlyRuntime(output['control'], output['capabilities'], output['native_binding'], registry)
    # Engineering schema validation at wholly unknown state; not claim scoring.
    runtime.run({'contract':'casepath.observation-state/1.0.0','case_id':'pack_shape_check',
       'materials':{},'guard_verdicts':{},'evidence':{'documents':{},'slot_assessments':[],'joint_assessments':[]},
       'origin':'engineering_fixture','inference_receipt_sha256':None})
    values = {'control':output['control'], 'capabilities':output['capabilities'],
              'native_binding':output['native_binding'], 'source_registry':registry}
    files = {}
    for role, name in FILES.items():
        raw = canonical(values[role]) + b'\n'
        from .wire import immutable
        immutable(Path(directory) / name, raw)
        files[role] = {'path':name,'bytes':len(raw),'sha256':sha(raw)}
    manifest = {'contract':'casepath.source-only-pack/1.0.0','files':files}
    manifest_sha = save(Path(directory) / 'PACK_MANIFEST.json', manifest)
    save(Path(directory) / 'PREPARATION_TRACE.json', {'origin':origin,'source_identity':sources['identity'],
         'output':output,'response_receipt_sha256':response_receipt_sha256,
         'runtime_pack_identity':runtime.pack_identity,'manifest_sha256':manifest_sha,
         'source_entailment_certified':False,'case_inputs_used':False})
    return {'runtime':runtime, 'prepared':copy.deepcopy(output), 'manifest_sha256':manifest_sha,
            'source_identity':sources['identity'], 'origin':origin}
