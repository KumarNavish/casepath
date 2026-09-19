"""Engineering-only reservation and exact generated-draft review regressions."""
import copy
from decimal import Decimal
import json
import unittest
from unittest.mock import patch
from test_obligation_study_v1 import example
import test_obligation_study_v1 as old_tests
from casepath_api.obligation_control.study_v1 import credit_bounds_v2 as cb
from casepath_api.obligation_control.study_v1.review_delta_v1 import CONTRACT, apply_review
from casepath_api.obligation_control.study_v1.schedule import DEFAULT_CONFIG, render_plan, render_request, validate_config
from casepath_api.obligation_control.study_v1.wire import canonical, decode, Invalid
from casepath_api.obligation_control.study_v1.adapters import StudyRunner


def revised():
    cfg=copy.deepcopy(DEFAULT_CONFIG)
    cfg.update(study_id='N150-CONTROL-EXECUTION-2-COST-V2',reservation_policy=cb.POLICY,
               price_rule='max_exclusive_input_category_no_hit_assumption',review_delta_enabled=True,
               token_counter='utf8_message_text_byte_bound_plus_existing_protocol_allowance',
               estimand='planning_control_conditional_on_shared_preparation')
    return cfg


def envelope(edits):return canonical({'review_contract':CONTRACT,'edits':edits})


class CreditBoundsTests(unittest.TestCase):
    def test_rates_exclusive(self):self.assertEqual(cb.input_rate(DEFAULT_CONFIG),Decimal('.0000025'))
    def test_no_hit_assumption(self):
        cfg=copy.deepcopy(DEFAULT_CONFIG);cfg['cache_read_rate']='0'
        self.assertEqual(cb.input_rate(cfg),Decimal('.0000025'))
    def test_category_partition(self):
        u={'prompt_tokens':100,'prompt_tokens_details':{'cached_tokens':20,'cache_write_tokens':30},'completion_tokens':5}
        self.assertEqual(cb.token_categories(u),{'uncached':50,'cache_read':20,'cache_write':30,'total':100})
        self.assertEqual(cb.category_cost(u,DEFAULT_CONFIG),Decimal('.000239'))
    def test_all_writes_bound(self):
        u={'prompt_tokens':100,'prompt_tokens_details':{'cached_tokens':0,'cache_write_tokens':100},'completion_tokens':0}
        self.assertEqual(cb.category_cost(u,DEFAULT_CONFIG),100*cb.input_rate(DEFAULT_CONFIG))
    def test_overlapping_counts_rejected(self):
        with self.assertRaises(Invalid):cb.token_categories({'prompt_tokens':10,'prompt_tokens_details':{'cached_tokens':6,'cache_write_tokens':7}})
    def test_unknown_cost_categories_not_zero(self):
        with self.assertRaises(Invalid):cb.token_categories({'prompt_tokens':10})
    def test_boolean_usage_rejected(self):
        with self.assertRaises(Invalid):cb.token_categories({'prompt_tokens':True,'prompt_tokens_details':{'cached_tokens':0,'cache_write_tokens':0}})
    def test_unicode_bound(self):self.assertEqual(cb.message_bound([{'role':'user','content':'é中😀'}],4096),4109)
    def test_wire_escaping_is_not_text(self):
        m=[{'role':'user','content':'"\\\n'*100}]
        self.assertLess(cb.message_bound(m,4096),len(canonical(m))+4096)
    def test_no_multimodal_assumption(self):
        with self.assertRaises(Invalid):cb.message_bound([{'role':'user','content':[{'type':'image'}]}],4096)
    def test_unchanged_model_route_samples_and_output(self):
        cfg=revised();validate_config(cfg)
        for k in ('model','returned_model','provider_tag','returned_provider','temperature','reasoning_effort','samples_per_arm','case_batch_size','case_output_tokens','case_output_bytes','preparation_output_tokens','preparation_output_bytes','arms'):
            self.assertEqual(cfg[k],DEFAULT_CONFIG[k])
    def test_revised_cost_lower_without_ceiling_reduction(self):
        s,p,c,o=example();old=render_plan(DEFAULT_CONFIG,s,[c],engineering_fixture=True);new=render_plan(revised(),s,[c],engineering_fixture=True)
        self.assertLess(Decimal(new['summary']['reserved_usd']),Decimal(old['summary']['reserved_usd']))
        self.assertEqual([v['output_tokens'] for v in old['slots'].values()],[v['output_tokens'] for v in new['slots'].values()])
    def test_parent_and_message_exact_bounds(self):
        s,p,c,o=example();new=render_plan(revised(),s,[c],engineering_fixture=True)
        raw=b'{}';r=render_request(new,c['case_id']+':DIRECT_REVIEWED:1',{'prep:1':raw,c['case_id']+':DIRECT_REVIEWED:0':raw})
        self.assertEqual(r['input_tokens_upper'],cb.message_bound(r['payload']['messages'],4096))
    def test_never_authorizes_spend(self):
        s,p,c,o=example();new=render_plan(revised(),s,[c],engineering_fixture=True)
        self.assertFalse(new['summary']['provider_execution_enabled'])
        self.assertEqual(new['bindings']['config']['authorized_additional_spend_usd'],'0.00')
    def test_unknown_reservation_rule_rejected(self):
        cfg=revised();cfg['reservation_policy']='assume_all_cache_hits'
        with self.assertRaises(Invalid):validate_config(cfg)
    def test_retaining_entire_draft(self):
        base={'a':[1,2],'more':{'b':'full information'}}
        value,trace=apply_review(canonical(base),envelope([]),65536)
        self.assertEqual(value,base);self.assertEqual(trace['mode'],'exact_generated_draft_edits')
    def test_edit_only_changed_leaf(self):
        base={'a':[1,2],'b':{'c':3}}
        value,_=apply_review(canonical(base),envelope([{'op':'replace','path':'/b/c','value':4}]),65536)
        self.assertEqual(value,{'a':[1,2],'b':{'c':4}});self.assertEqual(base['b']['c'],3)
    def test_array_add_remove(self):
        value,_=apply_review(b'{"a":[1,2]}',envelope([{'op':'add','path':'/a/-','value':3},{'op':'remove','path':'/a/0'}]),65536)
        self.assertEqual(value,{'a':[2,3]})
    def test_pointer_escapes(self):
        value,_=apply_review(b'{"a/b":{"~":1}}',envelope([{'op':'replace','path':'/a~1b/~0','value':2}]),65536)
        self.assertEqual(value,{'a/b':{'~':2}})
    def test_complete_replacement_still_allowed(self):
        value,_=apply_review(b'{"draft":0}',b'{"complete":1}',65536)
        self.assertEqual(value,{'complete':1})
    def test_root_replacement_possible(self):
        value,_=apply_review(b'{"draft":0}',envelope([{'op':'replace','path':'','value':{'complete':1}}]),65536)
        self.assertEqual(value,{'complete':1})
    def test_invalid_pointer_rejected(self):
        with self.assertRaises(Invalid):apply_review(b'{}',envelope([{'op':'add','path':'/~x','value':1}]),65536)
    def test_negative_index_rejected(self):
        with self.assertRaises(Invalid):apply_review(b'{"a":[1]}',envelope([{'op':'remove','path':'/a/-1'}]),65536)
    def test_missing_target_rejected(self):
        with self.assertRaises(Invalid):apply_review(b'{}',envelope([{'op':'replace','path':'/missing','value':1}]),65536)
    def test_expansion_bound(self):
        with self.assertRaises(Invalid):apply_review(b'{}',envelope([{'op':'add','path':'/x','value':'x'*100}]),20)
    def test_unknown_envelope_rejected(self):
        with self.assertRaises(Invalid):apply_review(b'{}',b'{"review_contract":"bad","edits":[]}',65536)
    def test_root_removal_rejected(self):
        with self.assertRaises(Invalid):apply_review(b'{}',envelope([{'op':'remove','path':''}]),65536)
    def test_retained_incomplete_draft_not_certified(self):
        value,trace=apply_review(b'{"draft":"incomplete"}',envelope([]),65536)
        self.assertNotIn('concepts',value);self.assertTrue(trace['native_validation_still_required'])


class ReviewIntegrationTests(unittest.TestCase):
    def test_all_five_arms_keep_generated_full_output_with_real_native_parser(self):
        # Reuse established fixture harness, not any claim or target.
        h=old_tests.StudyTests();h.setUp()
        try:
            h.cfg=revised();h.plan=render_plan(h.cfg,h.s,[h.c],engineering_fixture=True)
            ex=h.executor();original=ex.transport
            class EditTransport:
                origin='engineering_fixture'
                def __call__(self,r):
                    result=original(r)
                    if not r['slot_id'].startswith('prep:') and r['slot_id'].endswith(':1'):
                        body=decode(result['raw_body']);body['choices'][0]['message']['content']=envelope([]).decode();result['raw_body']=canonical(body)
                    return result
            ex.transport=EditTransport()
            with patch('socket.socket',side_effect=AssertionError('network forbidden')):
                runner=StudyRunner(h.plan,h.s,[h.c],ex,h.native(),h.root/'out')
                rows=runner.run_all()
            self.assertEqual(len(rows),7);self.assertTrue(all(r['state']=='completed' for r in rows))
            self.assertEqual(len(original.calls),12)
            for row in rows[:5]:self.assertIn('review_trace',row)
            self.assertEqual(len(list((h.root/'out/expanded_reviews').glob('*.json'))),5)
        finally:h.tearDown()
