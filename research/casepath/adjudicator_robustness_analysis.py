"""Frozen analysis for ADJUDICATOR_ROBUSTNESS_PROTOCOL.md. No network calls."""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
ART=HERE/'artifacts'
sys.path.insert(0,str(REPO/'casepath-api'))
sys.path.insert(0,str(HERE))
from casepath_api import contract_scoring_v1 as cs
from evaluation_validity_analysis import (
    HELD, audit_dynamic, cluster_bootstrap, paired_contrast,
    records_for_arm, paired_ids, summarize_rows, permutation_null,
)

CONTRACT=json.loads((HERE/'reference_contracts/rent_increase.json').read_text())
MODEL_FILES={
 'gpt-5.6-terra':'conf_arms.json',
 'claude-haiku-4.5':'mm_haiku.json',
 'gemini-2.5-flash':'mm_gemini.json',
 'deepseek-v3.2':'mm_deepseek.json',
}

def aggregate_family(rows, tag):
    by=collections.defaultdict(list); meta={}; failed=0
    for r in rows:
        if r.get('adjudicator_tag')!=tag: continue
        meta[r['unit_id']]=r['scenario']
        if r.get('ok') and r.get('decisions'):
            by[r['unit_id']].append(r)
        else:
            failed+=1
    ref={}; excluded=[]; family_states={}
    for unit_id in sorted(meta):
        votes=by.get(unit_id,[])
        if len(votes)<2:
            excluded.append(unit_id); continue
        statuses=cs.adjudicate(votes)
        family_states[unit_id]=statuses
        ref[unit_id]={**cs.reference_set(CONTRACT,statuses,held=sorted(HELD)), 'statuses':statuses}
    return ref,meta,family_states,{'failed_calls':failed,'adjudicated_units':len(ref),'excluded_units':excluded}


def original_reference():
    rows=json.loads((ART/'conf_ref_raw.json').read_text()); by=collections.defaultdict(list);meta={}
    for r in rows:
        if r.get('decisions'):
            by[r['unit_id']].append(r); meta[r['unit_id']]=r['scenario']
    states={u:cs.adjudicate(v) for u,v in by.items()}
    ref={u:{**cs.reference_set(CONTRACT,s,held=sorted(HELD)),'statuses':s} for u,s in states.items()}
    return ref,meta,states

def family_consensus(family_states, meta):
    tags=sorted(family_states)
    common=set.intersection(*(set(family_states[t]) for t in tags))
    ref={}; states={}
    for unit_id in sorted(common):
        decisions=[]
        for tag in tags:
            for did,v in family_states[tag][unit_id].items():
                decisions.append((tag,did,v['status']))
        per=collections.defaultdict(list)
        for tag,did,status in decisions: per[did].append(status)
        final={}
        for did,vals in per.items():
            c=collections.Counter(vals); top,n=c.most_common(1)[0]; tied=[x for x,m in c.items() if m==n]
            status=top if len(tied)==1 else ('live' if 'live' in tied else 'unknown')
            final[did]={'status':status,'votes':dict(c),'unanimous':len(c)==1,'n':len(vals)}
        states[unit_id]=final
        ref[unit_id]={**cs.reference_set(CONTRACT,final,held=sorted(HELD)),'statuses':final}
    excluded=sorted(set(meta)-common)
    return ref,states,{'adjudicated_units':len(ref),'excluded_units':excluded,'families':tags}


def agreement(a,b):
    units=sorted(set(a)&set(b)); same=total=0; exact_docs=0; jacc=[]
    for u in units:
        da=a[u]['statuses']; db=b[u]['statuses']
        for did in sorted(set(da)&set(db)):
            total+=1; same+=da[did]['status']==db[did]['status']
        A=set(a[u]['documents']);B=set(b[u]['documents'])
        exact_docs+=A==B; jacc.append(len(A&B)/len(A|B) if A|B else 1.0)
    return {'units':len(units),'decision_status_agreement':same/total if total else None,
            'decision_comparisons':total,'exact_document_set_rate':exact_docs/len(units) if units else None,
            'mean_document_jaccard':sum(jacc)/len(jacc) if jacc else None}

def release_agreement(a,b,meta):
    Aids={u for u in a if u.endswith('__orig') and u[:-6]+'__e07' in a}
    Bids={u for u in b if u.endswith('__orig') and u[:-6]+'__e07' in b}
    ids=sorted(Aids&Bids); exact=0;j=[]
    for o in ids:
        m=o[:-6]+'__e07'; ea=set(a[o]['documents'])-set(a[m]['documents']); eb=set(b[o]['documents'])-set(b[m]['documents'])
        exact+=ea==eb; j.append(len(ea&eb)/len(ea|eb) if ea|eb else 1.0)
    return {'pairs':len(ids),'exact_release_set_rate':exact/len(ids) if ids else None,
            'mean_release_jaccard':sum(j)/len(j) if j else None,
            'scenarios':len({meta[o] for o in ids})}


def load_arm_artifact(name):
    return {r['unit_id']:r for r in json.loads((ART/name).read_text())}


def audit_evaluator(ref,meta):
    out={'interpreters':{}}
    row_cache={}
    for model,fname in MODEL_FILES.items():
        A=load_arm_artifact(fname)
        arms=['b1_direct','b5_induced_graph']
        if model=='gpt-5.6-terra': arms.insert(1,'b3_graph_then_list')
        audit,rows=audit_dynamic(A,ref,meta,'__e07',arms)
        out['interpreters'][model]=audit; row_cache[model]=rows
    # target/oracle are interpreter-independent; take from first complete audit
    first=out['interpreters']['gpt-5.6-terra']
    for k in ('target','constant_oracle','best_input_independent_oracle','crossfit_input_independent_oracle'):
        out[k]=first[k]
    return out,row_cache

def main():
    packet=json.loads((ART/'cross_adjudicators_raw.json').read_text())
    rows=packet['rows']; tags=sorted({r['adjudicator_tag'] for r in rows})
    original_ref,meta,original_states=original_reference()
    refs={'original_gpt':original_ref}; states={'original_gpt':original_states}; execution={}
    family_states={}
    for tag in tags:
        ref,m,st,ex=aggregate_family(rows,tag)
        refs[tag]=ref;states[tag]=st;family_states[tag]=st;execution[tag]=ex
        for k,v in m.items(): meta.setdefault(k,v)
    consensus_ref,consensus_states,consensus_exec=family_consensus(family_states,meta)
    refs['external_consensus']=consensus_ref; states['external_consensus']=consensus_states
    execution['external_consensus']=consensus_exec

    audits={}; row_caches={}
    for tag,ref in refs.items():
        audits[tag],row_caches[tag]=audit_evaluator(ref,meta)

    agreements={}
    for tag in refs:
        if tag=='original_gpt': continue
        agreements[tag]={'reference':agreement(original_ref,refs[tag]),
                         'release':release_agreement(original_ref,refs[tag],meta)}
    matrix={}; evaluator_contrasts={}
    for model in MODEL_FILES:
        matrix[model]={}
        for tag in refs:
            cell=audits[tag]['interpreters'][model]['arms']['b5_induced_graph']
            matrix[model][tag]={k:cell[k] for k in ('n','excess','ci95_cluster_scenario','withdrawal_recall','exact_random_baseline','distinct_request_sets','distinct_withdrawal_sets')}
        # same frozen interpreter output, original evaluator versus independent consensus
        r0=row_caches['original_gpt'][model]['b5_induced_graph']
        rc=row_caches['external_consensus'][model]['b5_induced_graph']
        evaluator_contrasts[model]=paired_contrast(r0,rc,seed=20260961)

    # Rank/sign sensitivity across evaluator definitions.
    rankings={}
    for tag in refs:
        vals={m:matrix[m][tag]['excess'] for m in MODEL_FILES}
        rankings[tag]=sorted(vals.items(),key=lambda kv:(-kv[1],kv[0]))
    ranges={m:{'min':min(c['excess'] for c in matrix[m].values()),
               'max':max(c['excess'] for c in matrix[m].values()),
               'signs':{tag:('positive' if c['excess']>0 else 'negative' if c['excess']<0 else 'zero') for tag,c in matrix[m].items()}}
            for m in MODEL_FILES}

    result={'contract':'casepath.adjudicator-robustness/1.0.0',
            'protocol_commit_note':'Protocol and amendments were committed before response-content inspection.',
            'raw_run':{k:packet.get(k) for k in ('started_at','finished_at','system_prompt_sha256','reference_contract_sha256','models','temperature','max_tokens','repeats_per_unit','unit_count')},
            'execution':execution,'agreements_vs_original_gpt':agreements,
            'evaluator_audits':audits,'b5_interpreter_by_evaluator':matrix,
            'same_interpreter_original_minus_external_consensus':evaluator_contrasts,
            'rankings':rankings,'evaluator_ranges':ranges}
    out=ART/'ADJUDICATOR_ROBUSTNESS.json';out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'execution':execution,'agreements':agreements,'matrix':matrix,
                      'contrasts':evaluator_contrasts,'rankings':rankings,'output':str(out)},indent=2))

if __name__=='__main__': main()
