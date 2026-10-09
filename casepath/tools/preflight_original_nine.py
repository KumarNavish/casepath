#!/usr/bin/env python3
"""Prepare exact-nine requests offline; apply only through explicit operator CLI.

Preparation cannot open a work database, admit sources, or construct HTTP clients.
The candidate/selection pins restrict eligibility and supply no human approval.
"""
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'casepath-api'))

from casepath_api.agent_work.contracts import canonical, digest
from casepath_api.agent_work.store import (
    WorkStore, ORIGINAL_NINE_CANDIDATES, ORIGINAL_NINE_CONFIG,
    ORIGINAL_NINE_SELECTION_SHA256, ORIGINAL_NINE_CORPUS_SHA256,
)
from casepath_api.autonomous_corpus_v1 import CanonicalCorpus
from casepath_api.autonomous_model_v1 import AutonomousModelV1
from casepath_api.autonomous_policy_v1 import (
    POLICY_ID, REQUIRED_FACTS, REQUIRED_FIELDS, KNOWLEDGE_RECIPE_COMPILER,
    SUPPLIED_DOCUMENT_REVIEW_POLICY, OPERATIONAL_CONDITION_QUESTIONS,
    INTERPRET_INSTRUCTIONS, VERIFY_INSTRUCTIONS, INTERPRET_SCHEMA, VERIFY_SCHEMA,
)
from casepath_api.assessment_grammar_v1 import FAMILY_FLAGS
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root

ORIGINAL_IDS = tuple(row['claim_id'] for row in ORIGINAL_NINE_CANDIDATES)
OPTIONS = ('existing_010', 'new_018_total_022')


def clean_source_commit():
    dirty = subprocess.check_output(['git','status','--porcelain','--untracked-files=normal'],cwd=ROOT)
    if dirty:
        raise ValueError('a clean committed integrated checkout is required for an operator preflight or application')
    return subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()


def read_selection(raw):
    if not isinstance(raw, bytes) or sha256(raw).hexdigest() != ORIGINAL_NINE_SELECTION_SHA256:
        raise ValueError('selection identity differs from the adopted nine-original packet')
    value = json.loads(raw)
    if [r['claim_id'] for r in value['records']] != list(ORIGINAL_IDS):
        raise ValueError('selection identity roster differs')
    return value


def pinned_originals(corpus, policy):
    rows = []
    for candidate in ORIGINAL_NINE_CANDIDATES:
        cid = candidate['claim_id']
        state = corpus.preview_state(cid)
        binding = state['original_binding']
        identity = {'workflow_id': 'autonomy.' + digest({'claim':cid,
                    'sources':digest(state['source_descriptors']), 'policy':POLICY_ID,
                    'rules':digest(policy)})[:24], 'claim_id':cid, 'policy_id':POLICY_ID,
                    'source_roster_sha256':digest(state['source_descriptors']), 'rule_set_sha256':digest(policy)}
        if (identity != candidate['identity'] or binding['original_binding_sha256'] != candidate['original_binding_sha256']
                or binding['claim_binding_sha256'] != candidate['binding_sha256']):
            raise ValueError('canonical original binding, source roster or rules changed')
        identity.update(original_binding_sha256=binding['original_binding_sha256'],
                        claim_binding_sha256=binding['claim_binding_sha256'],
                        corpus_manifest_sha256=binding['corpus_manifest_sha256'])
        rows.append({'identity':identity, 'original_binding':binding})
    return rows


def original_context(corpus, policy, claim_id, compatible_knowledge):
    """Mirror the controller's context; a regression compares its actual output."""
    state = corpus.preview_state(claim_id)
    sources = [corpus.source_preview(claim_id, d['artifact_id']) for d in state['source_descriptors']]
    return {'claim_id':claim_id, 'title':state['title'], 'policy_id':POLICY_ID,
        'knowledge_recipe_compiler':KNOWLEDGE_RECIPE_COMPILER,
        'document_review_policy':SUPPLIED_DOCUMENT_REVIEW_POLICY,
        'operational_condition_questions':deepcopy(OPERATIONAL_CONDITION_QUESTIONS),
        'rule_packs':[{'family':t['domain'], 'template_id':t['template_id'], 'title':t['title'],
            'content':t['content'], 'template_sha256':digest(t),
            'process_catalog':{kind:[{k:v for k,v in row.items() if k != 'assertion'} for row in rows]
                               for kind,rows in t['process_catalog'].items()}} for t in policy['templates']],
        'condition_catalog':FAMILY_FLAGS, 'required_facts_by_document':REQUIRED_FACTS,
        'required_fields_by_document':REQUIRED_FIELDS,
        'sources':[{k:s[k] for k in ('artifact_id','file_name','media_type','role','sha256','text','complete','coverage')}
                   for s in sources], 'instructions':{'interpret':INTERPRET_INSTRUCTIONS,'verify':VERIFY_INSTRUCTIONS},
        'compatible_knowledge':deepcopy(compatible_knowledge)}


def build_preflight(selection_raw, *, corpus=None, source_commit, budget_snapshot=None,
                    request_config=None, compatible_knowledge=None):
    read_selection(selection_raw)
    config = deepcopy(ORIGINAL_NINE_CONFIG if request_config is None else request_config)
    if config != ORIGINAL_NINE_CONFIG or canonical(config) != canonical(ORIGINAL_NINE_CONFIG):
        raise ValueError('frozen provider configuration or prices changed')
    if (not isinstance(source_commit,str) or len(source_commit) != 40
            or any(c not in '0123456789abcdef' for c in source_commit)):
        raise ValueError('an exact source commit is required')
    public = PublicCorpus(default_workspace_corpus_root())
    if sha256((public.root / 'manifest.json').read_bytes()).hexdigest() != ORIGINAL_NINE_CORPUS_SHA256:
        raise ValueError('canonical corpus file identity differs')
    corpus = corpus or CanonicalCorpus(public)
    policy = public.static_policy()
    knowledge = [] if compatible_knowledge is None else compatible_knowledge
    if not isinstance(knowledge,list):
        raise ValueError('a saved compatible-knowledge projection is required')
    model = AutonomousModelV1.__new__(AutonomousModelV1)
    model.config = config
    rows = pinned_originals(corpus, policy)
    interpret_total = Decimal(0)
    maximum_call = Decimal(config['prompt_price']) * 64000 + Decimal(config['completion_price']) * 3500 + Decimal(config['request_price'])
    for row in rows:
        context = original_context(corpus, policy, row['identity']['claim_id'], knowledge)
        request = model.prepare_request('interpret', context, INTERPRET_SCHEMA)
        row['semantic_context_sha256'] = digest({k:v for k,v in context.items() if k != 'compatible_knowledge'})
        row['interpretation'] = {k:request[k] for k in ('request_sha256','request_bytes','context_sha256','schema_sha256','maximum_cost_usd')}
        row['verification'] = {'request_bytes_ceiling':64000,'output_tokens_ceiling':3500,
            'schema_sha256':digest(VERIFY_SCHEMA), 'maximum_cost_usd':str(maximum_call),
            'actual_input_known':False, 'fit_guaranteed':False}
        row['two_stage_reservation_bound_usd'] = str(Decimal(request['maximum_cost_usd']) + maximum_call)
        interpret_total += Decimal(request['maximum_cost_usd'])
    # A supplied snapshot is hashed verbatim; only transactional application can
    # establish whether it still equals the current remote-primary budget.
    if budget_snapshot is not None:
        WorkStore.validate_original_nine_budget_snapshot(budget_snapshot)
    documented = {'observed_at':'2026-10-09T15:18:04Z', 'actual_cost_usd':'0.0310427625',
        'reserved_cost_usd':'0.0028000', 'source':'supplied preparation document; no live query', 'provider_calls_used':24}
    costs = budget_snapshot or documented
    committed = Decimal(costs['actual_cost_usd']) + Decimal(costs['reserved_cost_usd'])
    options = [{'id':name, 'effective_total_cost_limit_usd':'0.10' if name == OPTIONS[0] else '0.22',
        'max_new_workflow_reservations_usd':'0.18', 'workflow_cost_limit_usd':'0.02',
        'all_nine_maxima_fit':committed + Decimal('0.18') <= Decimal('0.10' if name == OPTIONS[0] else '0.22'),
        'completion_conditional':True, 'approved':False} for name in OPTIONS]
    packet = {'contract':'casepath.original-nine-preflight/1.0.0','inactive':True,'allowance_applied':False,
        'execution_authorized':False,'provider_calls_sent':0,'source_admissions':0,
        'source_commit':source_commit, 'selection_file_sha256':ORIGINAL_NINE_SELECTION_SHA256,
        'corpus_manifest_file_sha256':ORIGINAL_NINE_CORPUS_SHA256,'frozen_model_config':config,
        'compatible_knowledge_sha256':digest(knowledge), 'compatible_knowledge':deepcopy(knowledge),
        'knowledge_evidence':'operator-supplied saved compatibility projection' if knowledge else 'empty knowledge preflight',
        'eligible_originals':rows,'max_new_workflows':9,'max_new_physical_calls':18,
        'max_output_tokens':3500,'max_request_bytes':64000,
        'eighteen_admissible_maxima_reservation_usd':str(maximum_call * 18),
        'interpretation_reservation_total_usd':str(interpret_total),
        'two_stage_reservation_total_bound_usd':str(interpret_total + maximum_call * 9),
        'monetary_options':options,'documented_budget':documented,
        'prior_budget':deepcopy(budget_snapshot),'prior_budget_sha256':digest(budget_snapshot) if budget_snapshot is not None else None,
        'current_budget_cas_ready':budget_snapshot is not None,
        'current_snapshot_match_proven':False, 'automatic_retry':False,
        'verifier_limit':'Every eventual compiled request must independently pass the same byte, context and output bounds.'}
    return {**packet,'preflight_sha256':digest(packet)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    prepare = sub.add_parser('preflight')
    prepare.add_argument('--selection',type=Path,required=True)
    prepare.add_argument('--budget-readback',type=Path)
    prepare.add_argument('--knowledge-context',type=Path)
    prepare.add_argument('--output',type=Path,required=True)
    apply = sub.add_parser('apply',help='operator-only; requires separate direct human approval')
    for name in ('preflight','actor','reason','idempotency-key','human-approval-reference',
                 'acknowledged-preflight-sha256','expected-budget-sha256','monetary-option'):
        apply.add_argument('--'+name)
    apply.add_argument('--apply',action='store_true')
    args = parser.parse_args(argv)
    if args.command == 'preflight':
        source_commit = clean_source_commit()
        packet = build_preflight(args.selection.read_bytes(),source_commit=source_commit,
            budget_snapshot=json.loads(args.budget_readback.read_bytes()) if args.budget_readback else None,
            compatible_knowledge=json.loads(args.knowledge_context.read_bytes()) if args.knowledge_context else None)
        with args.output.open('xb') as stream:
            stream.write(canonical(packet) + b'\n')
        print(json.dumps({'preflight_sha256':packet['preflight_sha256'],'inactive':True,
            'provider_calls_sent':0,'current_budget_cas_ready':packet['current_budget_cas_ready']}))
        return 0
    if not args.apply or any(getattr(args,name) is None for name in ('preflight','actor','reason','idempotency_key',
            'human_approval_reference','acknowledged_preflight_sha256','expected_budget_sha256','monetary_option')):
        raise ValueError('explicit authenticated approval application and all exact proposal inputs are required')
    packet = json.loads(Path(args.preflight).read_bytes())
    WorkStore.validate_original_nine_preflight(packet)
    WorkStore._validate_grant_command(args.expected_budget_sha256,args.actor,args.reason,args.idempotency_key)
    WorkStore._validate_grant_command(args.acknowledged_preflight_sha256,args.human_approval_reference,args.reason,args.idempotency_key)
    current = clean_source_commit()
    if current != packet['source_commit']:
        raise ValueError('source commit changed; prepare the integrated source before approval')
    pinned_originals(CanonicalCorpus(),PublicCorpus(default_workspace_corpus_root()).static_policy())
    public = PublicCorpus(default_workspace_corpus_root())
    corpus = CanonicalCorpus(public)
    for row in packet['eligible_originals']:
        context = original_context(corpus,public.static_policy(),row['identity']['claim_id'],[])
        if digest({k:v for k,v in context.items() if k != 'compatible_knowledge'}) != row['semantic_context_sha256']:
            raise ValueError('source extraction, schemas or workflow instructions changed after preflight')
    if (args.acknowledged_preflight_sha256 != packet['preflight_sha256']
            or args.expected_budget_sha256 != packet['prior_budget_sha256'] or args.monetary_option not in OPTIONS):
        raise ValueError('acknowledged preflight, budget CAS or monetary option differs')
    # Credential reads and remote construction occur only past every explicit
    # application gate. Transport authenticates the operator to the primary.
    from casepath_api.hosted_sql_v1 import TursoDatabase
    from casepath_api.hosted_lease_v1 import HostedWorkflowLease, _CURRENT_OWNER
    database = TursoDatabase(os.environ['CASEPATH_TURSO_URL'],os.environ['TURSO_AUTH_TOKEN'])
    lease = HostedWorkflowLease(database.connect)
    with TemporaryDirectory(prefix='casepath-original-nine-') as directory:
        work = WorkStore(Path(directory).resolve() / 'remote-handle',connection_factory=lease.connect,
                         validated_source_commit=current)
        try:
            token = lease.acquire()
            if token is None:
                raise ValueError('the hosted writer lease is busy; no allowance was applied')
            context_token = None
            try:
                context_token = _CURRENT_OWNER.set(token)
                receipt = work.apply_original_nine_grant(preflight=packet,expected_budget_sha256=args.expected_budget_sha256,
                    actor=args.actor,reason=args.reason,idempotency_key=args.idempotency_key,
                    human_approval_reference=args.human_approval_reference,monetary_option=args.monetary_option,
                    acknowledged_preflight_sha256=args.acknowledged_preflight_sha256)
                print(json.dumps(receipt,ensure_ascii=False,sort_keys=True))
            finally:
                try:
                    if context_token is not None:
                        _CURRENT_OWNER.reset(context_token)
                finally:
                    lease.release(token)
        finally:
            work.close()
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        # Do not echo database errors, URLs, credential values or raw input.
        print('Original-nine operation failed; inspect the same immutable command before retry ('
              + type(error).__name__ + ').',file=sys.stderr)
        raise SystemExit(1)
