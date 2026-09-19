"""Offline engineering tests. Invented model outputs are not scientific evidence."""
from __future__ import annotations
import copy
from datetime import datetime,timezone,timedelta
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from test_obligation_control_increment import fixture
from native_schema_fixture import EXPECTED, native_schema_directory
from casepath_api.obligation_control.source_only_runtime_v1 import SourceOnlyRuntime
from casepath_api.obligation_control.obligation_control_v1 import Invalid
from casepath_api.obligation_control.study_v1.wire import canonical,decode,digest,sha,save,immutable,safe_member,load
from casepath_api.obligation_control.study_v1.schedule import DEFAULT_CONFIG,render_plan,render_request,validate_config
from casepath_api.obligation_control.study_v1.preparation import materialize
from casepath_api.obligation_control.study_v1.adapters import NativeBoundary,StudyRunner,expand_candidate
from casepath_api.obligation_control.study_v1.inputs import registry_view,source_packet
from casepath_api.obligation_control.study_v1.journal import Journal
from casepath_api.obligation_control.study_v1.transport import BoundExecutor


def example():
    graph,caps,binding,registry,obs=fixture()
    sources=source_packet({'case_activation_values_included':False,'model_visibility':'all_three_templates_identical_for_every_case','templates':[]},
        {r:{**v,'source_kind':'case_invariant_rule','support_scope':'normative'} for r,v in registry.items()})
    prepared={'control':graph,'capabilities':caps,'native_binding':binding,
              'variable_descriptions':{v:'Fixture meaning '+v for v in graph['variables']},
              'source_accounting':{r:{'status':'used','reason':'Invented fixture source'} for r in registry}}
    visible={'materials':obs['materials'],'customer_message':{'body':'Invented fixture only'},'attachments':[],'case_registry':{}}
    case={'case_id':'fixture_1','split':'public_dev','family_id':'fixture_family','domain':'fixture_domain',
          'visible':visible,'visible_sha256':digest(visible),'registry':sources['registry']}
    return sources,prepared,case,obs


def allocation(plan):
    return {'plan_id':plan['plan_id'],'canonical_admission_receipt_sha256':'1'*64,
       'credit_authority_receipt_sha256':'2'*64,'parameter_binding_sha256':'3'*64,
       'token_bound_attestation_sha256':'4'*64,'balance_observed_usd':'236.81',
       'outside_liabilities_usd':'10','allocated_usd':'200','observed_at':datetime.now(timezone.utc).isoformat(),
       'origin':'engineering_fixture'}


class ScriptedTransport:
    origin='engineering_fixture'
    def __init__(self,prepared,obs,candidate):self.prepared,self.obs,self.candidate=prepared,obs,candidate;self.calls=[]
    def __call__(self,request):
        self.calls.append(request)
        slot=request['slot_id']
        if slot.startswith('prep:'):value=self.prepared
        elif ':CASEPATH_CONTROL:' in slot:value={'guard_verdicts':self.obs['guard_verdicts'],'evidence':self.obs['evidence']}
        else:value=self.candidate
        body={'model':DEFAULT_CONFIG['returned_model'],'provider':DEFAULT_CONFIG['returned_provider'],
             'choices':[{'finish_reason':'stop','message':{'content':canonical(value).decode()}}],
             'usage':{'cost':'0.001','prompt_tokens':1,'completion_tokens':1}}
        return {'http_status':200,'raw_body':canonical(body)}


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.s,self.p,self.c,self.x=example()
        self.cfg=copy.deepcopy(DEFAULT_CONFIG)
        self.plan=render_plan(self.cfg,self.s,[self.c],engineering_fixture=True)
    def tearDown(self):self.tmp.cleanup()
    def native(self):
        return NativeBoundary(native_schema_directory().parent, EXPECTED)
    def executor(self,transport=None):
        rt=SourceOnlyRuntime(self.p['control'],self.p['capabilities'],self.p['native_binding'],
                {k:{'text':v['text'],'locator':v['locator']} for k,v in self.s['registry'].items()})
        candidate=rt.run(self.x)['native_artifact'];candidate['case_id']='live_case'
        for family in ['concepts','documents','branch_predicates']:
            for item in candidate[family]:item['provenance']=[{'source_ref':'fixture-source#p1'}]
        trans=transport or ScriptedTransport(self.p,self.x,candidate)
        j=Journal(self.root/'journal.sqlite3');j.reserve(self.plan,allocation(self.plan))
        def auth(plan,req):return {'authorized':True,'origin':'engineering_fixture','plan_id':plan['plan_id'],
                'request_id':req['request_id'],'payload_sha256':req['payload_sha256']}
        return BoundExecutor(self.plan,j,self.root,auth,trans)

    def test_complete_slot_count(self):
        self.assertEqual(len(self.plan['slots']),12)
        self.assertEqual(len(self.plan['matrix']),7)
    def test_stable_plan_identity(self):
        self.assertEqual(self.plan['plan_id'],render_plan(self.cfg,self.s,[self.c],engineering_fixture=True)['plan_id'])
    def test_requests_depend_on_preparation(self):
        for key,row in self.plan['slots'].items():
            if not key.startswith('prep:'):self.assertEqual(row['dependencies'][0]['slot_id'],'prep:1')
    def test_no_fabricated_parent(self):
        with self.assertRaises(Invalid):render_request(self.plan,'fixture_1:DIRECT_REVIEWED:0',{})
    def test_physical_identity_binds_actual_parent(self):
        key='fixture_1:DIRECT_REVIEWED:0'
        a=render_request(self.plan,key,{'prep:1':b'{}'})
        b=render_request(self.plan,key,{'prep:1':b'{"changed":true}'})
        self.assertNotEqual(a['request_id'],b['request_id'])
        self.assertEqual(a['slot_id'],b['slot_id'])
    def test_unicode_count_is_byte_bound_not_chars_div_four(self):
        p=copy.deepcopy(self.plan);p['slots']['prep:0']['fixed_messages'][1]['content']='é中😀'
        r=render_request(p,'prep:0',{})
        self.assertGreater(r['input_tokens_upper'],len('é中😀')+4096)
    def test_no_temperature_or_tools_in_payload(self):
        r=render_request(self.plan,'prep:0',{})
        self.assertNotIn('temperature',r['payload']);self.assertNotIn('tools',r['payload'])
        self.assertFalse(r['payload']['provider']['allow_fallbacks'])
    def test_response_overflow_not_truncated(self):
        with self.assertRaises(Invalid):render_request(self.plan,'fixture_1:DIRECT_REVIEWED:0',{'prep:1':b'x'*(self.cfg['preparation_output_bytes']+1)})
    def test_armless_plan_rejected(self):
        c=copy.deepcopy(self.cfg);c['arms'].pop()
        with self.assertRaises(Invalid):validate_config(c)
    def test_topup_or_fallback_forbidden(self):
        for key in ['purchases_allowed','allow_fallbacks','auto_top_up']:
            c=copy.deepcopy(self.cfg);c[key]=True
            with self.assertRaises(Invalid):validate_config(c)
    def test_configuration_cannot_authorize(self):
        c=copy.deepcopy(self.cfg);c['provider_execution_enabled']=True
        with self.assertRaises(Invalid):validate_config(c)
    def test_complete150_not_favorable_subset(self):
        with self.assertRaises(Invalid):render_plan(self.cfg,self.s,[self.c])
    def test_complete150_engineering_render_is_not_measurement(self):
        cases=[]
        for i in range(150):
            c=copy.deepcopy(self.c);c['case_id']=f'invented_{i:03}';c['split']='public_dev' if i<60 else 'hidden_test';c['visible_sha256']=digest(c['visible']);cases.append(c)
        p=render_plan(self.cfg,self.s,cases,engineering_fixture=True)
        self.assertEqual(len(p['slots']),1502);self.assertEqual(len(p['matrix']),1050)
        self.assertEqual(p['summary']['actual_inference_calls'],0)
        self.assertTrue(p['summary']['exceeds_even_unallocated_credit_balance'])
    def test_source_preparation_contains_no_cases(self):
        s=self.plan['slots']['prep:0'];text=canonical(s).decode()
        self.assertNotIn(self.c['case_id'],text);self.assertNotIn('fixture_family',text)
    def test_models_never_receive_family_split_or_scheduler_case_id(self):
        for slot in self.plan['slots'].values():
            text=canonical(slot['fixed_messages']).decode()
            self.assertNotIn('fixture_family',text);self.assertNotIn('fixture_1',text)
    def test_source_only_pack_roundtrip(self):
        out=materialize(self.s,self.p,self.root/'pack',response_receipt_sha256='0'*64,origin='engineering_fixture')
        loaded=SourceOnlyRuntime.load(self.root/'pack',out['manifest_sha256'])
        self.assertEqual(out['runtime'].pack_identity,loaded.pack_identity)
    def test_source_accounting_omission_fails(self):
        p=copy.deepcopy(self.p);p['source_accounting']={}
        with self.assertRaises(Invalid):materialize(self.s,p,self.root/'pack',response_receipt_sha256='0'*64,origin='engineering_fixture')
    def test_primitive_semantics_missing_fails(self):
        p=copy.deepcopy(self.p);p['variable_descriptions'].pop('eligible')
        with self.assertRaises(Invalid):materialize(self.s,p,self.root/'pack',response_receipt_sha256='0'*64,origin='engineering_fixture')
    def test_no_target_path(self):
        with self.assertRaises(Invalid):safe_member(self.root,'data/dev/gold/a.json',('data/dev/',))
    def test_symlink_ancestor_rejected(self):
        (self.root/'data').symlink_to('/tmp',target_is_directory=True)
        with self.assertRaises(Invalid):safe_member(self.root,'data/claims/x.json',('data/',))
    def test_unknown_registry_role_rejected(self):
        with self.assertRaises(Invalid):registry_view({'entries':[{'source_kind':'gold_answer'}]})
    def test_case_source_not_preparation(self):
        s=copy.deepcopy(self.s);next(iter(s['registry'].values()))['source_kind']='observable_message_span'
        with self.assertRaises(Invalid):source_packet(s['rules'],s['registry'])
    def test_immutable_output_cannot_be_replaced(self):
        save(self.root/'x.json',{'a':1});save(self.root/'x.json',{'a':1})
        with self.assertRaises(Invalid):save(self.root/'x.json',{'a':2})
    def test_duplicate_json_fields_fail(self):
        with self.assertRaises(Invalid):decode(b'{"a":1,"a":2}')
    def test_reservation_needs_liabilities(self):
        a=allocation(self.plan);a['outside_liabilities_usd']=None
        with self.assertRaises(Exception):Journal(self.root/'j').reserve(self.plan,a)
    def test_reservation_requires_whole_study(self):
        a=allocation(self.plan);a['allocated_usd']='0.01'
        with self.assertRaises(Invalid):Journal(self.root/'j').reserve(self.plan,a)
    def test_observed_balance_not_an_allocation(self):
        a=allocation(self.plan);a.pop('allocated_usd')
        with self.assertRaises(Invalid):Journal(self.root/'j').reserve(self.plan,a)
    def test_outside_liabilities_respected(self):
        a=allocation(self.plan);a['outside_liabilities_usd']='230'
        with self.assertRaises(Invalid):Journal(self.root/'j').reserve(self.plan,a)
    def test_stale_credit_observation_rejected(self):
        a=allocation(self.plan);a['observed_at']=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
        with self.assertRaises(Invalid):Journal(self.root/'j').reserve(self.plan,a)
    def test_missing_admission_hash_rejected(self):
        a=allocation(self.plan);a['canonical_admission_receipt_sha256']=None
        with self.assertRaises(Invalid):Journal(self.root/'j').reserve(self.plan,a)
    def test_repeat_request_never_resends(self):
        ex=self.executor();ex.call('prep:0',{})
        with self.assertRaises(Invalid):ex.call('prep:0',{})
        self.assertEqual(len(ex.transport.calls),1)
    def test_denied_canonical_authorization_sends_nothing(self):
        ex=self.executor();ex.authorize=lambda p,r:{'authorized':False,'origin':'engineering_fixture'}
        with self.assertRaises(Invalid):ex.call('prep:0',{})
        self.assertEqual(ex.transport.calls,[])
    def test_lost_ack_is_uncertain_not_retry(self):
        ex=self.executor()
        class Lost:
            origin='engineering_fixture'
            def __call__(self,r):raise TimeoutError('invented transport timeout')
        ex.transport=Lost()
        with self.assertRaises(TimeoutError):ex.call('prep:0',{})
        facts=ex.journal.facts(self.plan['plan_id']);self.assertEqual(facts['requests'][0]['state'],'uncertain')
        with self.assertRaises(Invalid):ex.call('prep:1',{'prep:0':b'{}'})
    def test_unknown_cost_remains_unknown(self):
        ex=self.executor();old=ex.transport
        class Unknown:
            origin='engineering_fixture'
            def __call__(self,r):
                x=old(r);b=decode(x['raw_body']);b['usage']['cost']=None;x['raw_body']=canonical(b);return x
        ex.transport=Unknown()
        with self.assertRaises(Invalid):ex.call('prep:0',{})
        f=ex.journal.facts(self.plan['plan_id']);self.assertEqual(f['unknown_cost_count'],1);self.assertFalse(f['complete_cost_known'])
        self.assertEqual(f['requests'][0]['state'],'cost_unknown')
    def test_wrong_provider_recorded_as_failure(self):
        ex=self.executor();old=ex.transport
        class Wrong:
            origin='engineering_fixture'
            def __call__(self,r):
                x=old(r);b=decode(x['raw_body']);b['provider']='NotOpenAI';x['raw_body']=canonical(b);return x
        ex.transport=Wrong()
        with self.assertRaises(Invalid):ex.call('prep:0',{})
        self.assertEqual(ex.journal.facts(self.plan['plan_id'])['requests'][0]['state'],'failed')
        self.assertEqual(len(list(self.root.glob('calls/*/PROVIDER.raw'))),1)
    def test_journal_events_are_append_only(self):
        ex=self.executor();ex.call('prep:0',{})
        with ex.journal.connect() as db:
            with self.assertRaises(sqlite3.IntegrityError):db.execute('DELETE FROM events')
    def test_reconcile_unknown_same_request(self):
        ex=self.executor();req=render_request(self.plan,'prep:0',{})
        ex.journal.begin(self.plan,req,ex.authorize(self.plan,req))
        ex.journal.observe(req['request_id'],state='uncertain',actual_usd=None,evidence={'test':True})
        ex.journal.observe(req['request_id'],state='failed',actual_usd='0.001',evidence={'native_observation':'fixture'})
        facts=ex.journal.facts(self.plan['plan_id']);self.assertEqual(facts['requests'][0]['state'],'failed')
        self.assertEqual(len(facts['events']),4)
    def test_terminal_observation_not_overwritten(self):
        ex=self.executor();ex.call('prep:0',{});rid=ex.transport.calls[0]['request_id']
        with self.assertRaises(Invalid):ex.journal.observe(rid,state='completed',actual_usd='0',evidence={})
    def test_native_schema_and_parser_not_scorer(self):
        n=self.native();self.assertTrue(n.identity)
        self.assertFalse(any(k.startswith('_casepath_native_') and 'scorer' in k for k in __import__('sys').modules))
    def test_full_product_and_comparator_fixture_path(self):
        with patch('socket.socket',side_effect=AssertionError('network forbidden')):
            ex=self.executor();runner=StudyRunner(self.plan,self.s,[self.c],ex,self.native(),self.root/'out')
            result=runner.run_all()
        self.assertEqual(len(result),7)
        self.assertTrue(all(r['state']=='completed' for r in result))
        self.assertEqual(len(ex.transport.calls),12)
        full=next(r for r in result if r['arm']=='CASEPATH_CONTROL')['result']
        comp=next(r for r in result if r['arm']=='COMPILED_EQUIVALENT')['result']
        self.assertEqual(full['planning'],comp['planning'])
        self.assertIn('capabilities',full['planning'])
        self.assertTrue((self.root/'out/EVALUATOR_BOUNDARY.json').is_file())
        self.assertFalse(load(self.root/'out/EVALUATOR_BOUNDARY.json')['native_projection_is_lossless'])
    def test_incomplete_matrix_cannot_export(self):
        ex=self.executor();runner=StudyRunner(self.plan,self.s,[self.c],ex,self.native(),self.root/'out')
        with self.assertRaises(Invalid):runner.export_submissions([])
    def test_fabricated_source_ref_rejected(self):
        with self.assertRaises(Invalid):expand_candidate({'case_id':'live_case','concepts':[{'provenance':[{'source_ref':'secret_gold'}]}]},self.c,self.native())
    def test_source_pack_never_loads_hidden_files(self):
        out=materialize(self.s,self.p,self.root/'pack',response_receipt_sha256='0'*64,origin='engineering_fixture')
        (self.root/'pack/HIDDEN_RESULT.json').write_text('DO NOT OPEN')
        original=__import__('casepath_api.obligation_control.source_only_runtime_v1',fromlist=['regular_bytes']).regular_bytes
        opened=[]
        def track(path,limit):opened.append(Path(path).name);return original(path,limit)
        with patch('casepath_api.obligation_control.source_only_runtime_v1.regular_bytes',side_effect=track):
            SourceOnlyRuntime.load(self.root/'pack',out['manifest_sha256'])
        self.assertNotIn('HIDDEN_RESULT.json',opened)

    def test_product_invokes_same_inference_core_and_replays_same_request_only(self):
        from casepath_api.obligation_control.study_v1.product import ProductPlanService
        ex=self.executor();runner=StudyRunner(self.plan,self.s,[self.c],ex,self.native(),self.root/'out');runner.prepare()
        service=ProductPlanService(runner)
        first=service.plan(self.c['case_id'],expected_visible_sha256=self.c['visible_sha256'],expected_plan_id=self.plan['plan_id'])
        count=len(ex.transport.calls)
        second=service.plan(self.c['case_id'],expected_visible_sha256=self.c['visible_sha256'],expected_plan_id=self.plan['plan_id'])
        self.assertEqual(first['record'],second['record']);self.assertEqual(len(ex.transport.calls),count)
        self.assertTrue(second['same_request_replay']);self.assertFalse(first['six_role_workflow_claimed'])
        with self.assertRaises(Invalid):service.plan(self.c['case_id'],expected_visible_sha256='0'*64,expected_plan_id=self.plan['plan_id'])
    def test_product_http_rejects_client_supplied_graph(self):
        from casepath_api.obligation_control.study_v1.product import ProductPlanService,create_router
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        ex=self.executor();runner=StudyRunner(self.plan,self.s,[self.c],ex,self.native(),self.root/'out');runner.prepare()
        service=ProductPlanService(runner);app=FastAPI();app.include_router(create_router(lambda:service));client=TestClient(app)
        body={'case_id':self.c['case_id'],'expected_visible_sha256':self.c['visible_sha256'],'expected_plan_id':self.plan['plan_id']}
        before=len(ex.transport.calls)
        self.assertEqual(client.post('/api/obligation-control/plan',json={**body,'graph':{}}).status_code,422)
        self.assertEqual(len(ex.transport.calls),before)
        reply=client.post('/api/obligation-control/plan',json=body)
        self.assertEqual(reply.status_code,200);self.assertIn('planning',reply.json()['record']['result'])
    def test_no_implicit_preparation_from_product(self):
        from casepath_api.obligation_control.study_v1.product import ProductPlanService
        ex=self.executor();runner=StudyRunner(self.plan,self.s,[self.c],ex,self.native(),self.root/'out')
        with self.assertRaises(Invalid):ProductPlanService(runner).plan(self.c['case_id'],expected_visible_sha256=self.c['visible_sha256'],expected_plan_id=self.plan['plan_id'])
        self.assertEqual(ex.transport.calls,[])

    def test_unpriced_quote_edit_cannot_make_study_affordable(self):
        c=copy.deepcopy(self.cfg);c['output_rate']='0'
        with self.assertRaises(Invalid):validate_config(c)
    def test_allocation_above_existing_credit_ceiling_rejected(self):
        a=allocation(self.plan);a['balance_observed_usd']='500'
        with self.assertRaises(Invalid):Journal(self.root/'j').reserve(self.plan,a)
    def test_multiple_studies_cannot_double_reserve_small_balance(self):
        j=Journal(self.root/'j');a=allocation(self.plan)
        amount=Decimal(self.plan['summary']['reserved_usd'])
        a.update(balance_observed_usd=str(amount*Decimal('1.5')),outside_liabilities_usd='0',allocated_usd=str(amount))
        j.reserve(self.plan,a)
        cfg=copy.deepcopy(self.cfg);cfg['study_id']='another-explicit-fixture'
        p=render_plan(cfg,self.s,[self.c],engineering_fixture=True);b={**a,'plan_id':p['plan_id']}
        with self.assertRaises(Invalid):j.reserve(p,b)
    def test_fixture_submissions_cannot_look_like_model_submissions(self):
        ex=self.executor();runner=StudyRunner(self.plan,self.s,[self.c],ex,self.native(),self.root/'out');runner.run_all()
        self.assertTrue((self.root/'out/engineering_fixture_submissions').is_dir())
        self.assertFalse((self.root/'out/submissions').exists())

    def test_explicit_completed_request_recovery_sends_nothing(self):
        ex=self.executor();first=ex.call('prep:0',{})
        second=ex.recover('prep:0',{})
        self.assertEqual(first,second);self.assertEqual(len(ex.transport.calls),1)
    def test_completed_runner_resume_does_not_regenerate(self):
        ex=self.executor();runner=StudyRunner(self.plan,self.s,[self.c],ex,self.native(),self.root/'out')
        first=runner.run_all();count=len(ex.transport.calls)
        resumed=StudyRunner(self.plan,self.s,[self.c],ex,self.native(),self.root/'out').run_all()
        self.assertEqual(first,resumed);self.assertEqual(len(ex.transport.calls),count)
    def test_corrupt_recovered_output_is_rejected(self):
        ex=self.executor();ex.call('prep:0',{});rid=ex.transport.calls[0]['request_id']
        (self.root/'calls'/rid/'MODEL_OUTPUT.raw').write_bytes(b'{}')
        with self.assertRaises(Invalid):ex.recover('prep:0',{})
    def test_unknown_request_cannot_be_recovered_as_success(self):
        ex=self.executor();req=render_request(self.plan,'prep:0',{})
        ex.journal.begin(self.plan,req,ex.authorize(self.plan,req))
        with self.assertRaises(Invalid):ex.recover('prep:0',{})
    def test_compilation_is_not_protected_scoring(self):
        ex=self.executor();runner=StudyRunner(self.plan,self.s,[self.c],ex,self.native(),self.root/'out');out=runner.run_all()
        self.assertTrue(all(r.get('result',{}).get('native_scoring_performed',False) is False for r in out))
        self.assertFalse(load(self.root/'out/EVALUATOR_BOUNDARY.json')['targets_read'])

if __name__=='__main__':unittest.main()
