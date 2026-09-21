"""Frozen public preparation + 150 singleton cases, five paired two-call arms.

A UTF-8 text-byte bound is a bound, NOT an observed native token count. The
unchanged external token/framing attestation remains mandatory before sending.
No paid entry point is provided. The schedule includes the complete matrix.
"""
from __future__ import annotations
import copy
from decimal import Decimal,ROUND_CEILING
from pathlib import Path
from ..wire import canonical,decode,digest,sha,save,immutable,Invalid
from ..schedule import DEFAULT_CONFIG,implementation_identity
from .codec import Book
from .view import make_view
from .preparation import compile_public

CONTRACT='casepath.compact-native-study/3.0.0'
INSTRUCTION='''Use only the shared public templates, sources and this ONE case. Unknown is not false; an allegation is not independent evidence. Assess all three domains without a supplied routing answer. Source preparation is deterministic public-template compilation, NOT model induction. All arms receive exactly this representation. No web/tools, hidden answers or cross-case data.
Return JSON {"answer":ANSWER,"notes":"bounded explanation"}. Notes <=1536 UTF-8 bytes. First-turn normalized JSON <=6144 bytes. No dropped fields or truncated arrays. Review may correct any field; return a complete answer.
Native ANSWER={"kind":"native","c":[],"r":[],"b":[],"d":[],"t":[],"a":[]}. c/r/b entries select prototype row N, or [N,{"set":{field:value},"remove":[field]}], or {"literal":complete_native_row}. d entries MUST be [N,state_index,request_mode_index,optional_patch], or a literal full row. t and a are native concept IDs or {"c":N}. No object is included unless selected. Provenance arrays use source-selector integers; {"literal":locator} escapes a full locator. Expression fields accept {"e":N}, {"formula":"v0 and not v1"}, or a literal native expression; endpoint fields accept {"c":N}/{"d":N} or native IDs. Table display simplifications do not change selected original expressions. confidence and other original fields can be set explicitly. Decoder only expands; it does not correct decisions.
State ANSWER={"kind":"state","g":[],"d":[],"s":[],"j":[]}. g has one row per variable in order [true|false|null,null|[material_index,start_char,end_char]]. Every true/false needs an exact quote span from THAT material. d has one row per document_order [presence_index,state_index,[material_indices]]. s rows [capability_index,route_index,document_index,true|false|null,[material_indices]] assess capability-specific adequacy; j omits document_index for joint adequacy. Every present/missing assertion needs a material reference; the inventory can establish absence. A held file is not sufficient by its name. Unknown/opaque contents stay unknown. Missing s/j means unknown, not false or sufficient. Include every variable/document. Preserve the full planning trace separately from its native projection.'''
# Common decoder schema, clarified before the protected phase.
CAPABILITY_INDEX_LEGEND='All indices are zero-based. capabilities[c]=[fact_label_index,must_show_label_index,routes]; labels are not c or r. In s=[c,r,d,adequate,material_indices], c indexes capabilities, r indexes capabilities[c][2], and d is a document-codebook index in capabilities[c][2][r], not its within-route position. Material indices keep their existing meaning.'
INSTRUCTION += "\n" + CAPABILITY_INDEX_LEGEND

ARM_INSTRUCTIONS={
 'CASEPATH_CONTROL':('Produce the strongest complete STATE assessment; deterministic control will derive requests.','Review every state, quote and adequacy against the unchanged inputs. Return corrected complete STATE.'),
 'DIRECT_REVIEWED':('Produce the strongest complete NATIVE artifact directly, with no reasoning order imposed.','Review process, predicates, evidence coverage, requests and grounding; return corrected complete NATIVE.'),
 'DOCUMENT_FIRST_REVIEWED':('Start with document needs and states, then construct the full NATIVE artifact. Explain the document-first draft in notes.','Review the document-first draft against all sources; correct branches and unjustified/missing demands; return complete NATIVE.'),
 'PROCESS_CONTEXT_REVIEWED':('Resolve process scope and obligations first; YOU select evidence and requests using that context. Return full NATIVE.','Review process-conditioned requests and all native fields; return complete NATIVE. Do not use the deterministic control output.'),
 'RULE_FIRST_REVIEWED':('First derive and execute condition/action rules from the same information, then return full NATIVE. Notes give the rule draft.','Review inferred rules, routing, evidence states and sources; return complete NATIVE. This is not the missing preserved kernel.'),
}

def configuration():
    c=copy.deepcopy(DEFAULT_CONFIG)
    c.update({'contract':CONTRACT,'study_id':'N150-SHARED-COMPILED-COMPACT-3','reservation_policy':'compact_v3_byte_bound',
       'case_output_tokens':4096,'case_output_bytes':24576,'draft_normalized_bytes':6144,'notes_max_bytes':1536,
       'final_normalized_bytes':16384,'preparation_model_calls':0,'route_validation_requests':2,
       'price_rule':'max_exclusive_input_category_no_hit_assumption','max_input_tokens':100000,
       'preparation':'deterministic_actual_public_templates_not_model_induction',
       'estimand':'case_assessment_and_planning_conditional_on_shared_compiled_public_representation',
       'native_codec':'lossless_expansion_of_selected_native_objects; full_planning_to_native_is_lossy',
       'token_counter':'UTF8_text_bytes_plus_4096_framing_upper_bound_not_native_token_observation',
       'tokenizer_binding':'external_attestation_required; generic_gpt5_prefix_is_not_exact_endpoint_verification',
       'preserve_existing_journal_and_release_binding':True,'pdf_projector_version':'6.10.0',
       'completion_justification':'4096 common tokens; complete all-template native object uses selector references; adequacy/quote spans avoid repeated text; no baseline-specific cap',
       'review_change':'first stage emits a complete draft with ordering-specific notes; second independently reviews full same-information draft; not frozen V3 factorial reproduction'})
    return c


def validate(c):
    fixed=configuration()
    for key in fixed:
        if key in {'pdf_projector_version','study_id'}:continue
        if c.get(key)!=fixed[key]:raise Invalid('changed compact scientific/configuration binding: '+key)
    if c['provider_execution_enabled'] is not False or c['authorized_additional_spend_usd']!='0.00':raise Invalid('construction is not spend authority')


def normalized_response(raw,c,*,stage):
    value=decode(raw)
    if not isinstance(value,dict) or set(value)!= {'answer','notes'} or not isinstance(value['answer'],dict) or not isinstance(value['notes'],str):raise Invalid('complete answer plus review notes required')
    if len(value['notes'].encode())>c['notes_max_bytes']:raise Invalid('notes exceed bound; never truncated')
    result=canonical(value)
    bound=c['draft_normalized_bytes'] if stage==0 else c['final_normalized_bytes']
    if len(result)>bound:raise Invalid('complete normalized response exceeds prospective bound')
    return result


def text_bound(messages,c):
    return c['protocol_overhead_tokens']+sum(len(m['content'].encode())+len(m['role']) for m in messages)


def render_plan(c,sources,cases,native,output=None,*,engineering_fixture=False):
    validate(c)
    if not engineering_fixture:
        if len(cases)!=150 or len({x['case_id'] for x in cases})!=150:raise Invalid('all 150 cases required')
        if {s:sum(x['split']==s for x in cases) for s in ['public_dev','hidden_test']}!={'public_dev':60,'hidden_test':90}:raise Invalid('split changed')
        groups={s:{x['family_id'] for x in cases if x['split']==s} for s in ['public_dev','hidden_test']}
        if len(groups['public_dev'])!=11 or len(groups['hidden_test'])!=17 or groups['public_dev']&groups['hidden_test']:raise Invalid('family geometry changed')
    prep=compile_public(sources)
    rate=max(Decimal(c[k]) for k in ('input_rate','cache_read_rate','cache_write_rate'))
    seed={'config':c,'source_identity':sources['identity'],'preparation_manifest':prep['manifest'],
         'cohort':[(x['case_id'],x['visible_sha256'],x['split'],x['family_id'],x['domain']) for x in sorted(cases,key=lambda x:x['case_id'])],
         'native_schema_identity':native.identity,'code_identity':implementation_identity(),
         'origin':'engineering_fixture' if engineering_fixture else 'original_observable_release'}
    slots={};matrix=[];schedule={};books={};witnesses=[];position={}
    def slot(key,messages,deps,phase,output_tokens=None):
        fixed=text_bound(messages,c);future=c['draft_normalized_bytes']+len('PRIOR_DRAFT\n')+4 if deps else 0
        upper=fixed+future
        if upper>c['max_input_tokens'] or upper>=c['long_context_threshold']:raise Invalid('complete request cannot fit declared input contract')
        tokens=output_tokens or c['case_output_tokens'];cost=upper*rate+tokens*Decimal(c['output_rate'])+Decimal(c['request_rate'])
        row={'slot_id':key,'fixed_messages':messages,'dependencies':deps,'phase':phase,
             'static_input_tokens_bound':fixed,'deferred_input_tokens_bound':future,'reserved_input_tokens':upper,
             'output_tokens':tokens,'max_response_bytes':c['case_output_bytes'],'reserved_usd':str(cost),
             'state':'rendered_exact' if not deps else 'bounded_exact-parent-template','no_actual_provider_call':True}
        row['template_sha256']=digest(row);slots[key]=row
    for i in range(c['route_validation_requests']):
        slot('prep:route:'+str(i),[{'role':'system','content':'Return JSON only. Route/parameter verification; no benchmark case.'},
            {'role':'user','content':'Return {"answer":{"route_check":true},"notes":""}.'}],[],'route_validation',c['case_output_tokens'])
    for case in sorted(cases,key=lambda x:(x['split']!='public_dev',x['case_id'])):
        book=Book(prep,case,native);books[case['case_id']]=book
        view=make_view(sources,book);view_text=canonical(view).decode()
        index=position.get(case['split'],0);position[case['split']]=index+1;shift=index%5
        order=c['arms'][shift:]+c['arms'][:shift];schedule[case['case_id']]=order
        for arm in order:
            key=case['case_id']+':'+arm
            for stage in range(2):
                messages=[{'role':'system','content':INSTRUCTION+'\n'+ARM_INSTRUCTIONS[arm][stage]},
                          {'role':'user','content':view_text}]
                slot(key+':'+str(stage),messages,[] if stage==0 else [key+':0'],case['split'])
            matrix.append({'case_id':case['case_id'],'arm':arm,'split':case['split'],'family_id':case['family_id'],'domain':case['domain'],
                'requests':[key+':0',key+':1'],'codebook_identity':book.identity,'visible_sha256':case['visible_sha256'],'status':'unsubmitted'})
        for arm in c['deterministic_arms']:
            matrix.append({'case_id':case['case_id'],'arm':arm,'split':case['split'],'family_id':case['family_id'],'domain':case['domain'],
                'requests':[],'depends_on':case['case_id']+':CASEPATH_CONTROL:1','status':'unsubmitted'})
        # Full public union is an engineering representation witness, never a prediction.
        prototype={'artifact_version':'casepath.candidate-artifact/0.1.0','case_id':'live_case',
            **{family:book.tables[tag] for tag,family in {'c':'concepts','r':'relations','b':'branch_predicates','d':'documents'}.items()},
            'terminal_outcome_ids':prep['prepared']['native_binding']['terminal_outcome_ids'],'abstained_concept_ids':[]}
        wire=book.encode_native(prototype);expanded=book.decode_native(wire)
        if expanded!=native.validate({**prototype,'case_id':case['case_id']}):raise Invalid('native codebook roundtrip failure')
        witnesses.append({'case_id':case['case_id'],'kind':'all_public_template_native_object_not_prediction','compact_json_bytes':len(canonical(wire)),
            'expanded_native_bytes':len(canonical(expanded)),'roundtrip_exact':True,'concepts':len(expanded['concepts']),'relations':len(expanded['relations'])})
    total=sum(Decimal(r['reserved_usd']) for r in slots.values())
    phase={p:str(sum(Decimal(r['reserved_usd']) for r in slots.values() if r['phase']==p)) for p in ['route_validation','public_dev','hidden_test']}
    summary={'provider_requests':len(slots),'cases':len(cases),'learned_case_cells':5*len(cases),'total_case_arm_cells':len(matrix),
       'reserved_usd':str(total),'rounded_reservation_usd':str(total.quantize(Decimal('.01'),rounding=ROUND_CEILING)),
       'observed_credit_upper_bound_usd':c['observed_credit_upper_bound_usd'],'phase_reservations_usd':phase,
       'fits_observed_upper_bound':total<=Decimal(c['observed_credit_upper_bound_usd']),
       'unallocated_headroom_usd':str(Decimal(c['observed_credit_upper_bound_usd'])-total),
       'provider_execution_enabled':False,'authorized_allocation_usd':'0.00','actual_inference_calls':0,
       'preparation_model_calls':0,'preparation_provider_cost_usd':'0.00','preparation_cpu_and_wall_cost':'measure separately in render receipt',
       'max_input_upper':max(x['reserved_input_tokens'] for x in slots.values()),'completion_tokens_per_case_request':c['case_output_tokens'],
       'framing_allowance_per_request':c['protocol_overhead_tokens'],'count_kind':c['token_counter'],
       'no_cache_hit_assumed':True,'exact_native_tokenizer_verified':False,
       'financial_fit_is_not_credit_allocation_or_admission':True,'protected_scoring_performed':False,
       'estimand':c['estimand'],'possible_deferred_input_rejection':False,
       'native_output_roundtrip_witnesses':len(witnesses),'max_full_union_output_bytes':max(w['compact_json_bytes'] for w in witnesses)}
    plan={'contract':CONTRACT,'bindings':seed,'slots':slots,'matrix':matrix,'case_schedule':schedule,'summary':summary,'witnesses':witnesses}
    plan['plan_id']=digest(plan)
    if output is not None:
        output=Path(output);save(output/'PLAN.json',plan);save(output/'RESERVATION.json',summary)
        save(output/'PREPARATION.json',{'manifest':prep['manifest'],'prepared':prep['prepared']})
        immutable(output/'MATRIX.jsonl',b''.join(canonical(x)+b'\n' for x in matrix))
        immutable(output/'REQUEST_RESERVATIONS.jsonl',b''.join(canonical({k:v for k,v in x.items() if k!='fixed_messages'})+b'\n' for x in slots.values()))
        save(output/'NATIVE_ROUNDTRIP_WITNESSES.json',witnesses)
    return plan


def render_request(plan,slot_id,parents):
    c=plan['bindings']['config'];validate(c);slot=plan['slots'][slot_id]
    messages=copy.deepcopy(slot['fixed_messages']);parent_hashes={}
    for dep in slot['dependencies']:
        if dep not in parents:raise Invalid('missing real prior answer')
        raw=parents[dep];normalized=normalized_response(raw,c,stage=0)
        messages.append({'role':'user','content':'PRIOR_DRAFT\n'+normalized.decode()});parent_hashes[dep]=sha(raw)
    upper=text_bound(messages,c)
    if upper>slot['reserved_input_tokens']:raise Invalid('pre-send input exceeds exact slot reservation')
    payload={'model':c['model'],'messages':messages,'max_tokens':slot['output_tokens'],
      'response_format':{'type':'json_object'},'provider':{'only':[c['provider_tag']],'allow_fallbacks':False,'require_parameters':True},
      'reasoning':{'effort':c['reasoning_effort']},'usage':{'include':True}}
    row={'plan_id':plan['plan_id'],'slot_id':slot_id,'template_sha256':slot['template_sha256'],'parent_sha256':parent_hashes,
         'payload':payload,'payload_sha256':digest(payload),'input_tokens_upper':upper,'reserved_usd':slot['reserved_usd'],
         'max_response_bytes':slot['max_response_bytes']}
    row['request_id']='req-'+digest(row);return row
