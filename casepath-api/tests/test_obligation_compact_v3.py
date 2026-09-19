"""Offline construction fixtures only. No benchmark target or provider access."""
from __future__ import annotations
import copy
import json
from native_schema_fixture import native_schema_directory
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime,timezone
from decimal import Decimal
from casepath_api.obligation_control.study_v1.wire import canonical,decode,digest,sha,Invalid
from casepath_api.obligation_control.study_v1.inputs import source_packet
from casepath_api.obligation_control.study_v1.adapters import NativeBoundary
from casepath_api.obligation_control.study_v1.journal import Journal
from casepath_api.obligation_control.study_v1.product import ProductPlanService
from casepath_api.obligation_control.study_v1.compact_v3.preparation import compile_public
from casepath_api.obligation_control.study_v1.compact_v3.codec import Book,FAMILIES
from casepath_api.obligation_control.study_v1.compact_v3.view import make_view,simplified,expand_source_text
from casepath_api.obligation_control.study_v1.compact_v3.schedule import configuration,render_plan,render_request,normalized_response
from casepath_api.obligation_control.study_v1.compact_v3.runner import CompactRunner,CompactExecutor


def fixture():
    templates=[];registry={}
    for i,domain in enumerate(['alpha','beta','gamma']):
        nodes=[{'node_id':domain+'_start','label':'Check '+domain,'responsibility':'handler','terminal':False,'assertion':domain+' process starts with checking.'},
               {'node_id':domain+'_end','label':'Conclude '+domain,'responsibility':'handler','terminal':True,'assertion':domain+' process concludes.'}]
        edges=[{'edge_id':domain+'_edge','source_node_id':nodes[0]['node_id'],'target_node_id':nodes[1]['node_id'],
                'condition':'route selected','optional_path':False,'assertion':domain+' concludes after route selection.'}]
        docs=[{'document_type':'doc_'+domain,'label':domain+' evidence','requirement_class':'conditional','condition':"scenario flag 'needed' is active",'required_at_node_ids':[nodes[0]['node_id']],'assertion':domain+' evidence is requested if needed.'}]
        templates.append({'domain':domain,'template_id':'template_'+domain,'title':domain,'content':'Policy '+domain,'clauses':[],
                          'process_catalog':{'nodes':nodes,'transitions':edges,'documents':docs}})
        for j,row in enumerate(nodes+edges+docs):
            text=row['assertion'];ref='r'+str(i)+'_'+str(j)
            registry[ref]={'source_kind':'case_invariant_rule','support_scope':'normative','text':text,
               'locator':{'artifact_id':'source_'+domain,'artifact_sha256':'a'*64,'locator_kind':'json_pointer','json_pointer':'/entry/'+str(j),
                          'canonical_value_sha256':digest(text)}}
    sources=source_packet({'case_activation_values_included':False,'model_visibility':'all_three_templates_identical_for_every_case','templates':templates},registry)
    visible={'materials':{'m':'The route is selected. Evidence is present.'},'customer_message':{'body':'The route is selected. Evidence is present.','subject':'Engineering fixture'},
            'message_source':{'artifact_id':'m'},'case_registry':{},'attachments':[],'submission':{'language':'en','claim_id':'fixture'}}
    case={'case_id':'fixture','split':'public_dev','family_id':'fixture_family','domain':'alpha','visible':visible,'visible_sha256':digest(visible),'registry':registry}
    return sources,case


def native():
    root=native_schema_directory().parent
    return NativeBoundary(root,{x:sha((root/'contracts'/x).read_bytes()) for x in ['schema.py','expressions.py']})


def allocation(plan):
    return {'plan_id':plan['plan_id'],'canonical_admission_receipt_sha256':'1'*64,'credit_authority_receipt_sha256':'2'*64,
     'parameter_binding_sha256':'3'*64,'token_bound_attestation_sha256':'4'*64,'balance_observed_usd':'236.81','outside_liabilities_usd':'10',
     'allocated_usd':'200','observed_at':datetime.now(timezone.utc).isoformat(),'origin':'engineering_fixture'}


class CompactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources,cls.case=fixture();cls.native=native();cls.prep=compile_public(cls.sources)
    def setUp(self):
        self.book=Book(self.prep,self.case,self.native);self.cfg=configuration()
    def full(self):
        return self.native.validate({'artifact_version':'casepath.candidate-artifact/0.1.0','case_id':self.case['case_id'],
            **{family:self.book.tables[tag] for tag,family in FAMILIES.items()},'terminal_outcome_ids':self.prep['prepared']['native_binding']['terminal_outcome_ids'],'abstained_concept_ids':[]})
    def state(self,truth=None):
        return {'guard_verdicts':{v:{'value':truth,'source_id':'m' if truth is not None else None,'quote':'The route is selected.' if truth is not None else None} for v in self.book.variables},
           'evidence':{'documents':{d:{'presence':'missing','native_state':'missing','source_refs':['m']} for d in self.book.documents},'slot_assessments':[],'joint_assessments':[]}}
    def plan(self):return render_plan(self.cfg,self.sources,[self.case],self.native,engineering_fixture=True)
    def test_shared_source_text_is_recoverable_exactly(self):
        view=make_view(self.sources,self.book)
        for i,ref in enumerate(self.book.source_refs):
            self.assertEqual(expand_source_text(view,i),self.case['registry'][ref]['text'])
    def test_source_formulas_are_available_in_prompt(self):
        view=make_view(self.sources,self.book)
        self.assertEqual(set(view['legend']['assertion_expansion']),{'node','edge','document','condition_suffix','overrides'})
    def test_public_compilation_zero_calls(self):self.assertEqual(self.prep['manifest']['model_calls'],0)
    def test_compilation_never_reads_case(self):self.assertFalse(self.prep['manifest']['case_inputs_used'])
    def test_three_templates_required(self):
        s=copy.deepcopy(self.sources);s['rules']['templates'].pop()
        with self.assertRaises(Invalid):compile_public(s)
    def test_case_source_rejected_in_preparation(self):
        s=copy.deepcopy(self.sources);next(iter(s['registry'].values()))['source_kind']='observable_message_span'
        with self.assertRaises(Invalid):compile_public(s)
    def test_temporal_edges_do_not_become_acquisition_guards(self):
        self.assertTrue(all(o['acquire_when']=={'const':True} for o in self.prep['prepared']['control']['obligations']))
    def test_native_all_objects_roundtrip(self):
        a=self.full();self.assertEqual(self.book.decode_native(self.book.encode_native(a)),a)
    def test_no_auto_inclusion(self):
        a=self.book.decode_native({'kind':'native','c':[],'r':[],'b':[],'d':[],'t':[],'a':[]})
        self.assertEqual(a['concepts'],[]);self.assertEqual(a['documents'],[])
    def test_document_mode_explicit(self):
        w=self.book.encode_native(self.full());w['d'][0]=0
        with self.assertRaises(Invalid):self.book.decode_native(w)
    def test_document_state_change_roundtrip(self):
        a=self.full();a['documents'][0]['state']='provided_insufficient';a['documents'][0]['request_mode']='now'
        self.assertEqual(self.book.decode_native(self.book.encode_native(a)),a)
    def test_confidence_roundtrip(self):
        a=self.full();a['concepts'][0]['confidence']=0.123
        self.assertEqual(self.book.decode_native(self.book.encode_native(a)),a)
    def test_empty_provenance_preserved(self):
        a=self.full();a['concepts'][0]['provenance']=[]
        self.assertEqual(self.book.decode_native(self.book.encode_native(a)),a)
    def test_nonstandard_literal_native_object_preserved(self):
        a=self.full();a['concepts'].append({'concept_id':'custom','kind':'fact','label':'A different legitimate hypothesis','active_when':'other_flag','confidence':0.2,'provenance':[]})
        self.assertEqual(self.book.decode_native(self.book.encode_native(a)),self.native.validate(a))
    def test_wrong_edge_not_silently_corrected(self):
        a=self.full();a['relations'][0]['active_when']='false'
        self.assertEqual(self.book.decode_native(self.book.encode_native(a))['relations'][0]['active_when'],'false')
    def test_unbound_literal_locator_preserved_for_original_scorer(self):
        a=self.full();a['concepts'][0]['provenance']=[{'artifact_id':'invented-for-engineering-test','artifact_sha256':'b'*64,'locator_kind':'whole_artifact'}]
        expected=self.native.validate(a)
        self.assertEqual(self.book.decode_native(self.book.encode_native(expected)),expected)
    def test_reference_index_boolean_not_integer(self):
        w=self.book.encode_native(self.full());w['c'][0]=True
        with self.assertRaises(Invalid):self.book.decode_native(w)
    def test_bad_index_rejected(self):
        w=self.book.encode_native(self.full());w['c'][0]=99999
        with self.assertRaises(Invalid):self.book.decode_native(w)
    def test_native_expression_parser_unchanged(self):
        w=self.book.encode_native(self.full());w['c'][0]=[0,{'set':{'active_when':'foo('},'remove':[]}]
        with self.assertRaises(ValueError):self.book.decode_native(w)
    def test_literal_field_expressions_select_exact_original(self):
        w=self.book.encode_native(self.full());w['c'][0]=[0,{'set':{'active_when':{'e':0}},'remove':[]}]
        self.assertEqual(self.book.decode_native(w)['concepts'][0]['active_when'],self.book.expression_originals[0])
    def test_alias_formula_keeps_custom_boolean_choices(self):
        w=self.book.encode_native(self.full());w['c'][0]=[0,{'set':{'active_when':{'formula':'v0 and not v1'}},'remove':[]}]
        self.assertEqual(self.book.decode_native(w)['concepts'][0]['active_when'],self.book.variables[0]+' and not '+self.book.variables[1])
    def test_wrong_alias_formula_index_rejected(self):
        w=self.book.encode_native(self.full());w['c'][0]=[0,{'set':{'active_when':{'formula':'v9999'}},'remove':[]}]
        with self.assertRaises(Invalid):self.book.decode_native(w)
    def test_terminal_alias(self):
        w=self.book.encode_native(self.full());tid=w['t'][0];idx=self.book.by_id['c'][tid];w['t']=[{'c':idx}]
        self.assertEqual(self.book.decode_native(w)['terminal_outcome_ids'],[tid])
    def test_state_roundtrip_all_truths(self):
        for value in (True,False,None):
            x=self.state(value);self.assertEqual(self.book.decode_state(self.book.encode_state(x)),x)
    def test_incomplete_state_rejected(self):
        w=self.book.encode_state(self.state());w['g'].pop()
        with self.assertRaises(Invalid):self.book.decode_state(w)
    def test_quote_end_bound(self):
        w=self.book.encode_state(self.state(True));w['g'][0][1][2]=9999
        with self.assertRaises(Invalid):self.book.decode_state(w)
    def test_decided_without_quote_rejected(self):
        w=self.book.encode_state(self.state());w['g'][0]=[True,None]
        with self.assertRaises(Invalid):self.book.decode_state(w)
    def test_duplicate_quote_exact_unicode_offsets(self):
        c=copy.deepcopy(self.case);c['visible']['materials']['m']='ä中😀 repeated ä中😀'
        b=Book(self.prep,c,self.native);w=b.encode_state(self.state());w['g'][0]=[True,[0,0,3]]
        self.assertEqual(next(iter(b.decode_state(w)['guard_verdicts'].values()))['quote'],'ä中😀')
    def test_envelopes_do_not_truncate(self):
        raw=canonical({'answer':{'kind':'state'},'notes':'x'*2000})
        with self.assertRaises(Invalid):normalized_response(raw,self.cfg,stage=0)
    def test_whitespace_dedup_preserves_json(self):
        obj={'answer':{'kind':'state'},'notes':'exact'}
        raw=json.dumps(obj,indent=6).encode();self.assertEqual(decode(normalized_response(raw,self.cfg,stage=0)),obj)
    def test_wire_json_duplicate_key_rejected(self):
        with self.assertRaises(Invalid):normalized_response(b'{"answer":{},"answer":{},"notes":""}',self.cfg,stage=0)
    def test_all_arms_share_source_packet(self):
        p=self.plan();payloads={r['fixed_messages'][1]['content'] for k,r in p['slots'].items() if not k.startswith('prep:')}
        self.assertEqual(len(payloads),1)
    def test_same_complete_output_caps_all_arms(self):
        self.assertEqual({r['output_tokens'] for k,r in self.plan()['slots'].items() if not k.startswith('prep:')},{4096})
    def test_preserves_model_route_sample_count(self):
        from casepath_api.obligation_control.study_v1.schedule import DEFAULT_CONFIG
        for k in ['model','returned_model','provider_tag','returned_provider','reasoning_effort','temperature','samples_per_arm']:
            self.assertEqual(self.cfg[k],DEFAULT_CONFIG[k])
    def test_no_preparation_requests(self):
        p=self.plan();self.assertEqual([k for k in p['slots'] if k.startswith('prep:')],['prep:route:0','prep:route:1'])
    def test_no_fabricated_parent(self):
        with self.assertRaises(Invalid):render_request(self.plan(),'fixture:DIRECT_REVIEWED:1',{})
    def test_parent_id_hash_uses_original_raw(self):
        p=self.plan();a=canonical({'answer':self.book.encode_native(self.full()),'notes':''})
        b=json.dumps(decode(a),indent=2).encode()
        x=render_request(p,'fixture:DIRECT_REVIEWED:1',{'fixture:DIRECT_REVIEWED:0':a});y=render_request(p,'fixture:DIRECT_REVIEWED:1',{'fixture:DIRECT_REVIEWED:0':b})
        self.assertNotEqual(x['request_id'],y['request_id']);self.assertEqual(x['payload'],y['payload'])
    def test_context_bound_includes_worst_future_draft(self):
        p=self.plan();s=p['slots']['fixture:DIRECT_REVIEWED:1']
        self.assertGreaterEqual(s['deferred_input_tokens_bound'],6144)
    def test_context_capacity_not_used_as_token_count(self):
        self.assertLess(max(s['reserved_input_tokens'] for s in self.plan()['slots'].values()),self.cfg['max_input_tokens'])
    def test_cache_categories_not_added(self):
        p=self.plan();s=p['slots']['fixture:DIRECT_REVIEWED:0'];expected=Decimal(s['reserved_input_tokens'])*Decimal('.0000025')+Decimal(4096)*Decimal('.000012')
        self.assertEqual(Decimal(s['reserved_usd']),expected)
    def test_config_no_purchase_or_send(self):
        for k in ['auto_top_up','purchases_allowed','provider_execution_enabled']:self.assertFalse(self.cfg[k])
    def test_cannot_drop_arm(self):
        c=copy.deepcopy(self.cfg);c['arms'].pop()
        with self.assertRaises(Invalid):render_plan(c,self.sources,[self.case],self.native,engineering_fixture=True)
    def test_cannot_drop_families(self):
        with self.assertRaises(Invalid):render_plan(self.cfg,self.sources,[self.case],self.native)
    def test_display_expression_identities_only(self):
        self.assertEqual(simplified('((foo and true) and foo)',{'foo':'v0'}),'v0')
        self.assertEqual(simplified('(foo or false)',{'foo':'v0'}),'v0')
    def test_source_views_preserve_material_text(self):
        v=make_view(self.sources,self.book);self.assertEqual(v['materials'][0][1],self.case['visible']['materials']['m'])
        self.assertTrue(v['assertion_overrides'])
    def test_source_symbols_not_claim_family(self):
        text=canonical(make_view(self.sources,self.book)).decode();self.assertNotIn('fixture_family',text)
    def test_minimal_quote_form_all_document_slots(self):
        wire=self.book.encode_state(self.state(True));self.assertLess(len(canonical(wire)),4096)
    def test_full_native_representation_size(self):
        self.assertLess(len(canonical(self.book.encode_native(self.full()))),4096)

    def test_guarded_runner_and_shared_product_no_network(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.plan();j=Journal(Path(d)/'journal.db');j.reserve(p,allocation(p));book=self.book
            class FixtureTransport:
                origin='engineering_fixture'
                def __init__(self):self.requests=[]
                def __call__(self,request):
                    self.requests.append(request)
                    if request['slot_id'].startswith('prep:'):ans={'route_check':True}
                    elif ':CASEPATH_CONTROL:' in request['slot_id']:ans=book.encode_state(CompactTests.state(self_outer))
                    else:ans=book.encode_native(self_outer.full())
                    body={'model':p['bindings']['config']['returned_model'],'provider':p['bindings']['config']['returned_provider'],
                         'choices':[{'finish_reason':'stop','message':{'content':canonical({'answer':ans,'notes':''}).decode()}}],
                         'usage':{'cost':'.001','prompt_tokens':1,'completion_tokens':1}}
                    return {'http_status':200,'raw_body':canonical(body)}
            self_outer=self;transport=FixtureTransport()
            def auth(p,r):return {'authorized':True,'origin':'engineering_fixture','plan_id':p['plan_id'],'request_id':r['request_id'],'payload_sha256':r['payload_sha256']}
            ex=CompactExecutor(p,j,Path(d),auth,transport);runner=CompactRunner(p,self.sources,[self.case],ex,self.native,Path(d)/'out')
            with patch('socket.socket',side_effect=AssertionError('no network')):
                runner.route_checks();rows=runner.run_all()
                self.assertEqual(len(rows),7);self.assertTrue(all(r['state']=='completed' for r in rows),rows)
                self.assertEqual(len(transport.requests),12)
                replay=ProductPlanService(runner).plan('fixture',expected_visible_sha256=self.case['visible_sha256'],expected_plan_id=p['plan_id'])
                self.assertTrue(replay['same_request_replay']);self.assertEqual(len(transport.requests),12)
            self.assertIn('planning',rows[0]['result']);self.assertFalse(rows[0]['scoring_performed'])
