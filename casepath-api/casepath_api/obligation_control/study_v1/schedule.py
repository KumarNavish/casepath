"""Reviewable complete request DAG and conservative pre-send cost envelopes.

A future model output cannot have an actual payload hash before it exists.
The logical slot is fixed now; its physical request ID additionally binds the
exact parent outputs. Deferred blocks are explicit, never fabricated answers.
"""
from __future__ import annotations
from decimal import Decimal, ROUND_CEILING
import copy
from pathlib import Path
from .wire import canonical, digest, save, sha, Invalid
from .prompts import COMMON, CONTROL_FORMAT, PREPARATION, ARMS
from . import credit_bounds_v2 as cb
from .review_delta_v1 import INSTRUCTION as REVIEW_DELTA_INSTRUCTION

DEFAULT_CONFIG = {
 'contract':'casepath.native150-credit-study/1.0.0',
 'study_id':'N150-CONTROL-EXECUTION-2',
 'provider_execution_enabled':False, 'authorized_additional_spend_usd':'0.00',
 'observed_credit_upper_bound_usd':'236.81', 'auto_top_up':False, 'purchases_allowed':False,
 'claims_novelty':False, 'uses_fresh_confirmation':False,
 'model':'openai/gpt-5.6-terra', 'returned_model':'openai/gpt-5.6-terra-20260709',
 'provider_tag':'openai', 'returned_provider':'OpenAI', 'allow_fallbacks':False,
 'temperature':None, 'temperature_claim':'not sent; effective setting unverified',
 'reasoning_effort':'medium', 'effective_parameter_binding':'pending_canonical_route_receipt',
 'price_receipt_sha256':'7539ceec75f6151b0568b96d401ee297c2ff4058c68f986ebcb8cfca98bd8383',
 'input_rate':'0.000002', 'cache_read_rate':'0.0000002', 'cache_write_rate':'0.0000025',
 'output_rate':'0.000012', 'request_rate':'0', 'long_context_threshold':272000,
 'price_rule':'add input+cache_read+cache_write for every input token; no discounts',
 'token_counter':'utf8_byte_upper_bound_plus_4096_protocol_tokens',
 'tokenizer_assumption':'text-only byte-token vocabulary; requires canonical pre-send tokenizer/usage bound attestation',
 'protocol_overhead_tokens':4096, 'max_input_tokens':200000,
 'case_output_tokens':12000, 'case_output_bytes':65536,
 'preparation_output_tokens':32768, 'preparation_output_bytes':131072,
 'case_batch_size':1, 'samples_per_arm':1, 'attempts_per_request':1,
 'arms':list(ARMS),
 'deterministic_arms':['COMPILED_EQUIVALENT','LOCAL_SCOPE_ABLATION'],
 'preserved_kernel':{'decision':'excluded_unavailable_source_not_reproduced',
   'path_lead':'f1_kernel/k0_kernel.py','reported_hash_prefix':'098ff3d0...337b',
   'receipt':'c5131a872c8a3203e7d5e7c9dd1b56b83d5ff46193734c80735b4ae89acb0979',
   'substitute_called_preserved':False},
 'inference_mode':'new joint-within-one-case assessment plus independent review; not V5 per-guard isolation',
 'native_release_manifest_raw_sha256':'638630886a1d291dfe9009839eb0519130e56700bb4d454277ce2e45c6044f4c',
 'native_release_manifest_declared_id':'ff5aec73ae3c7de03b1caa23e476701653539c0c0ec45f0b2427348b25c6af47',
 'frozen_legacy_prompt_sha256':'2e09439bb984bb0e8029eb0250a44e785e51009a9d5c884633fc09da82ce91b5',
 'legacy_prompt_reproduction_claimed':False,
 'old_v5':'historical predecessor preserved separately, not silently relabelled as this new joint-state adapter',
 'native_evaluator':'unchanged original evaluator; this package exports submissions but cannot score',
 'pdf_projector_version':'6.10.0',
 'case_projection':'new source-preserving request view; not legacy byte-identical model input',
 'weighting':'equal_domain_equal_family_equal_case; dev and protected separate',
 'protected_input_history':'all150 intake inputs previously inspected; not untouched-input generalization',
 'dynamic_output_rule':'No truncation/repair/resampling on bound failure; keep terminal failure and charge.',
}


def money(value: str) -> Decimal:
    x = Decimal(str(value))
    if not x.is_finite() or x < 0:
        raise Invalid('negative/nonfinite monetary value')
    return x


def validate_config(config: dict) -> None:
    if config.get('contract') != DEFAULT_CONFIG['contract'] or config.get('provider_execution_enabled') is not False or money(config.get('authorized_additional_spend_usd','0')) != 0:
        raise Invalid('construction configuration is not spending authority')
    if config.get('arms') != list(ARMS) or config.get('deterministic_arms') != DEFAULT_CONFIG['deterministic_arms']:
        raise Invalid('do not drop comparison arms')
    if config.get('case_batch_size') != 1 or config.get('attempts_per_request') != 1 or config.get('samples_per_arm') != 1:
        raise Invalid('changed experimental execution design')
    for key in ['case_output_tokens','case_output_bytes','preparation_output_tokens','preparation_output_bytes','max_input_tokens','protocol_overhead_tokens']:
        if type(config.get(key)) is not int or config[key] <= 0:
            raise Invalid('invalid bound: ' + key)
    if config['max_input_tokens'] >= config['long_context_threshold']:
        raise Invalid('long-context pricing not allowed by this plan')
    for key in ['input_rate','cache_read_rate','cache_write_rate','output_rate','request_rate']:
        money(config[key])
        if config[key] != DEFAULT_CONFIG[key]:
            raise Invalid('price change requires a newly reviewed protocol, not a cheap edited quote')
    policy = config.get('reservation_policy')
    if policy not in (None, cb.POLICY):
        raise Invalid('unknown reservation policy')
    if policy == cb.POLICY and config.get('price_rule') != 'max_exclusive_input_category_no_hit_assumption':
        raise Invalid('reservation must use the bound exclusive-category rule')
    if config.get('review_delta_enabled') not in (None, False, True):
        raise Invalid('invalid review mode')
    if config.get('allow_fallbacks') is not False or config.get('purchases_allowed') is not False or config.get('auto_top_up') is not False:
        raise Invalid('fallbacks and purchases are forbidden')


def compact_sources(sources: dict) -> dict:
    """Reversible source-reference projection: no semantic selection or pruning."""
    return {'rules':sources['rules'], 'registry':{k:{'text':v['text'], 'kind':v['source_kind'],
          'support_scope':v.get('support_scope')} for k,v in sources['registry'].items()},
          'source_identity':sources['identity']}


def _slot(config: dict, scope: str, stage: int, system: str, visible: dict, dependencies: list[str], slots: dict) -> dict:
    fixed_messages = [{'role':'system','content':system}, {'role':'user','content':canonical(visible).decode()}]
    blocks = [{'slot_id':dep, 'role':'user', 'label': 'SOURCE_PREPARATION' if dep.startswith('prep:') else 'PRIOR_ANALYSIS',
               'max_utf8_bytes':slots[dep]['max_response_bytes']} for dep in dependencies]
    prep = scope == 'prep'
    # Byte upper bound includes JSON envelope overhead as well as message text.
    revised = config.get('reservation_policy') == cb.POLICY
    static_upper = (cb.message_bound(fixed_messages, config['protocol_overhead_tokens']) if revised
                    else len(canonical(fixed_messages)) + config['protocol_overhead_tokens'])
    # A dependent block is a separate text message, not JSON-escaped text nested
    # inside another JSON string. Keep its full declared UTF-8 byte envelope.
    deferred_upper = sum(b['max_utf8_bytes'] + (len((b['label']+'\n').encode())+len(b['role']) if revised else 128) for b in blocks)
    upper = static_upper + deferred_upper
    input_reservation = min(upper, config['max_input_tokens'])
    output_tokens = config['preparation_output_tokens'] if prep else config['case_output_tokens']
    rate = cb.input_rate(config) if revised else sum(money(config[k]) for k in ['input_rate','cache_read_rate','cache_write_rate'])
    price = input_reservation*rate + output_tokens*money(config['output_rate']) + money(config['request_rate'])
    slot_id = f'{scope}:{stage}'
    record = {'slot_id':slot_id, 'fixed_messages':fixed_messages, 'dependencies':blocks,
        'static_input_tokens_bound':static_upper, 'deferred_input_tokens_bound':deferred_upper,
        'input_category_reservation_rate':str(rate),
        'upper_input_tokens_before_per_call_stop':upper, 'reserved_input_tokens':input_reservation,
        'possible_pre_send_input_rejection':upper > config['max_input_tokens'],
        'output_tokens':output_tokens, 'max_response_bytes':config['preparation_output_bytes'] if prep else config['case_output_bytes'],
        'reserved_usd':str(price), 'state':'rendered_exact' if not dependencies else 'bounded_dependent_template',
        'no_actual_provider_call':True}
    return {**record,'template_sha256':digest(record)}


def render_plan(config: dict, sources: dict, cases: list[dict], output: Path | None = None, *, engineering_fixture: bool = False) -> dict:
    validate_config(config)
    if not engineering_fixture:
        if len(cases) != 150 or len({c['case_id'] for c in cases}) != 150:
            raise Invalid('all 150 cases required, not a favorable subset')
        if {s:sum(c['split']==s for c in cases) for s in ['public_dev','hidden_test']} != {'public_dev':60,'hidden_test':90}:
            raise Invalid('split changed')
    identities = [(c['case_id'], c['visible_sha256'], c['split'], c['family_id'], c['domain']) for c in sorted(cases,key=lambda c:c['case_id'])]
    seed = {'config':config,'source_identity':sources['identity'],'cohort':identities,
            'code_identity':implementation_identity(), 'origin':'engineering_fixture' if engineering_fixture else 'original_observable_release'}
    plan_id = digest(seed)
    slots = {}
    source_view = compact_sources(sources)
    for stage in range(2):
        rec = _slot(config, 'prep',stage, COMMON+'\n'+PREPARATION[stage]+'\n'+CONTROL_FORMAT,
                    {'sources':source_view}, [] if stage==0 else ['prep:0'], slots)
        slots[rec['slot_id']] = rec
    cells = []; case_schedule = {}; positions = {}
    for case in sorted(cases,key=lambda c:(c['split'] != 'public_dev',c['case_id'])):
        index=positions.get(case['split'],0); positions[case['split']]=index+1
        shift=index % len(config['arms'])
        order=config['arms'][shift:]+config['arms'][:shift]
        case_schedule[case['case_id']]=order
        for arm in order:
            for stage in range(2):
                scope = case['case_id'] + ':' + arm
                instructions = ARMS[arm][stage]
                if stage == 1 and config.get('review_delta_enabled'):
                    instructions += '\n' + REVIEW_DELTA_INSTRUCTION
                grammar = ARMS[arm][2] if stage==1 or arm in {'CASEPATH_CONTROL','DIRECT_REVIEWED'} else 'Return a detailed JSON draft sufficient for the stated task.'
                # The visible packet never includes scheduling family/domain/split or real case ID.
                visible = {'sources':source_view, 'case':case['visible'], 'case_id':'live_case'}
                deps = ['prep:1'] + ([] if stage==0 else [scope+':0'])
                rec = _slot(config,scope,stage,COMMON+'\n'+instructions+'\n'+grammar,visible,deps,slots)
                slots[rec['slot_id']] = rec
            cells.append({'case_id':case['case_id'], 'arm':arm, 'split':case['split'],
                'family_id':case['family_id'],'domain':case['domain'],'requests':[scope+':0',scope+':1'],
                'source_identity':sources['identity'],'visible_sha256':case['visible_sha256'],'status':'unsubmitted'})
        for arm in config['deterministic_arms']:
            cells.append({'case_id':case['case_id'],'arm':arm,'split':case['split'],'family_id':case['family_id'],'domain':case['domain'],
                'requests':[], 'depends_on':case['case_id']+':CASEPATH_CONTROL:1','status':'unsubmitted',
                'comparison_scope':'conditional_on_same_fresh_case_assessment'})
    total = sum(money(s['reserved_usd']) for s in slots.values())
    capacity = money(config['observed_credit_upper_bound_usd'])
    summary = {'provider_requests':len(slots),'learned_case_cells':len(cases)*len(config['arms']),
        'total_case_arm_cells':len(cells),'cases':len(cases),'reserved_usd':str(total),
        'rounded_reservation_usd':str(total.quantize(Decimal('.01'),rounding=ROUND_CEILING)),
        'observed_credit_upper_bound_usd':str(capacity),'exceeds_even_unallocated_credit_balance':total>capacity,
        'feasibility':'RESERVATION_EXCEEDS_BALANCE_UPPER_BOUND' if total>capacity else 'CAPACITY_ONLY_NEEDS_LIVE_ALLOCATION',
        'affordability_is_not_admission':True, 'provider_execution_enabled':False,
        'actual_inference_calls':0,'exact_initial_requests':sum(not s['dependencies'] for s in slots.values()),
        'bounded_future_request_templates':sum(bool(s['dependencies']) for s in slots.values()),
        'upper_bound_not_expected_bill_or_minimum_cost':True,
        'possible_input_rejection_slots':sum(s['possible_pre_send_input_rejection'] for s in slots.values()),
        'ordering':'five-arm position-balanced cyclic schedule separately within each split; not the legacy six-arm Williams design',
        'reservation_by_phase_usd':{'source_preparation':str(sum(money(s['reserved_usd']) for k,s in slots.items() if k.startswith('prep:'))), **{split:str(sum(money(slots[r]['reserved_usd']) for c in cells if c['split']==split for r in c.get('requests',[]))) for split in ['public_dev','hidden_test']}},
        'missing_preserved_kernel':'excluded_unavailable_source_not_reproduced',
        'reservation_policy':config.get('reservation_policy','legacy_additive'),
        'estimand':'planning_and_control_conditional_on_shared_source_preparation; not end_to_end_source_to_process_superiority',
        'financial_envelope_is_not_input_feasibility':True,
        'fixed_text_input_bound_total':sum(s['static_input_tokens_bound'] for s in slots.values()),
        'dependent_text_input_bound_total':sum(s['deferred_input_tokens_bound'] for s in slots.values()),
        'output_token_ceiling_total':sum(s['output_tokens'] for s in slots.values()),
        'output_only_reservation_usd':str(sum(s['output_tokens']*money(config['output_rate']) for s in slots.values())),
        'protected_scoring':False}
    plan = {'contract':'casepath.rendered-study-dag/1.0.0','plan_id':plan_id,'bindings':seed,
            'slots':slots,'matrix':cells,'case_schedule':case_schedule,'summary':summary}
    if output is not None:
        output=Path(output)
        save(output/'PLAN.json',plan)
        save(output/'RENDER_REPORT.json',summary)
        from .wire import immutable
        immutable(output/'MATRIX.jsonl', b''.join(canonical(c)+b'\n' for c in cells))
        # One file per request makes every prompt/template independently reviewable.
        for slot in slots.values():
            save(output/'requests'/(digest(slot['slot_id'])+'.json'),slot)
    return plan


def implementation_identity() -> str:
    root = Path(__file__).parents[1]
    return digest({str(p.relative_to(root)):sha(p.read_bytes()) for p in sorted(root.rglob('*.py'))})


def render_request(plan: dict, slot_id: str, parent_raw: dict[str,bytes]) -> dict:
    slot=plan['slots'][slot_id]; config=plan['bindings']['config']
    messages=copy.deepcopy(slot['fixed_messages']); parent_hashes={}
    for block in slot['dependencies']:
        if block['slot_id'] not in parent_raw:
            raise Invalid('dependent result not available; no invented output')
        raw=parent_raw[block['slot_id']]
        if len(raw)>block['max_utf8_bytes']:
            raise Invalid('parent output exceeds bound; no truncation')
        messages.append({'role':block['role'],'content':block['label']+'\n'+raw.decode('utf-8')})
        parent_hashes[block['slot_id']]=sha(raw)
    bound=(cb.message_bound(messages,config['protocol_overhead_tokens']) if config.get('reservation_policy')==cb.POLICY
           else len(canonical(messages))+config['protocol_overhead_tokens'])
    if bound>slot['reserved_input_tokens']:
        raise Invalid('actual request input bound exceeds its reservation; stop before send')
    payload={'model':config['model'],'messages':messages,'max_tokens':slot['output_tokens'],
        'response_format':{'type':'json_object'},'provider':{'only':[config['provider_tag']],'allow_fallbacks':False,'require_parameters':True},
        'reasoning':{'effort':config['reasoning_effort']},'usage':{'include':True}}
    record={'plan_id':plan['plan_id'],'slot_id':slot_id,'template_sha256':slot['template_sha256'],
       'parent_sha256':parent_hashes,'payload':payload,'payload_sha256':digest(payload),
       'input_tokens_upper':bound,'reserved_usd':slot['reserved_usd'],'max_response_bytes':slot['max_response_bytes']}
    return {**record,'request_id':'req-'+digest(record)}
