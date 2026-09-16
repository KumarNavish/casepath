"""Symmetric release-set validity analysis; no network/model calls."""
from __future__ import annotations
import collections,json,math,random
from pathlib import Path
HERE=Path(__file__).resolve().parent; ART=HERE/'artifacts'

def load(n): return json.loads((ART/n).read_text())

def reference(raw_name):
 import sys
 sys.path.insert(0,str(HERE.parents[1]/'casepath-api'))
 from casepath_api import contract_scoring_v1 as cs
 C=json.loads((HERE/'reference_contracts'/('termination.gated.json' if raw_name.startswith('term_') else 'rent_increase.json')).read_text())
 by=collections.defaultdict(list); meta={}
 for r in load(raw_name):
  if r.get('decisions'): by[r['unit_id']].append(r); meta[r['unit_id']]=r['scenario']
 return {u:cs.reference_set(C,cs.adjudicate(v),held=['lease_contract']) for u,v in by.items()},meta

def pairs(A,ref,suffix):
 return [(u,u[:-6]+suffix) for u in sorted(A) if u.endswith('__orig') and u[:-6]+suffix in A and u in ref and u[:-6]+suffix in ref]

def gold_sets(ref,ps): return [set(ref[o]['documents'])-set(ref[m]['documents']) for o,m in ps]
def metrics(pred,gold):
 tp=sum(len(p&g) for p,g in zip(pred,gold)); P=sum(map(len,pred)); G=sum(map(len,gold))
 micro=2*tp/(P+G) if P+G else 1.0
 macro=sum((1.0 if not p and not g else (2*len(p&g)/(len(p)+len(g)) if len(p)+len(g) else 1.0)) for p,g in zip(pred,gold))/len(gold)
 exact=sum(p==g for p,g in zip(pred,gold))/len(gold)
 return {'micro_f1':micro,'macro_f1':macro,'exact_match':exact,'tp':tp,'predicted_items':P,'gold_items':G}

def best_constant_micro(train_gold):
 freq=collections.Counter(d for g in train_gold for d in g); n=len(train_gold); G=sum(map(len,train_gold)); ranked=sorted(freq,key=lambda d:(-freq[d],d))
 best=(0.0,set())
 hits=0
 for k,d in enumerate(ranked,1):
  hits+=freq[d]; f=2*hits/(n*k+G) if n*k+G else 1.0
  if f>best[0]+1e-15: best=(f,set(ranked[:k]))
 return best[1]
def modal_constant(train_gold):
 c=collections.Counter(tuple(sorted(g)) for g in train_gold); return set(c.most_common(1)[0][0])
def crossfit_constants(ps,gold,meta):
 sc=sorted({meta[o] for o,_ in ps}); micro_policy={}; exact_policy={}; pred_micro=[];pred_exact=[]
 for held in sc:
  train=[g for (p,g) in zip(ps,gold) if meta[p[0]]!=held]
  micro_policy[held]=best_constant_micro(train); exact_policy[held]=modal_constant(train)
 for p in ps:
  pred_micro.append(set(micro_policy[meta[p[0]]])); pred_exact.append(set(exact_policy[meta[p[0]]]))
 return pred_micro,pred_exact,micro_policy,exact_policy


def pairing_null(pred,gold,ps,meta,draws=5000,seed=20260916):
 by=collections.defaultdict(list)
 for i,(o,m) in enumerate(ps): by[meta[o]].append(i)
 rng=random.Random(seed); vals=[]
 for _ in range(draws):
  assigned=list(gold)
  for idx in by.values():
   g=[gold[i] for i in idx]; rng.shuffle(g)
   for i,x in zip(idx,g): assigned[i]=x
  vals.append(metrics(pred,assigned)['micro_f1'])
 vals.sort(); obs=metrics(pred,gold)['micro_f1']; ge=sum(v>=obs-1e-15 for v in vals)
 return {'observed_micro_f1':obs,'null_mean':sum(vals)/draws,'null_95':[vals[int(.025*draws)],vals[int(.975*draws)]],'null_min':vals[0],'null_max':vals[-1],'p_ge_plus1':(ge+1)/(draws+1),'draws':draws,'seed':seed}

def arm_predictions(A,ps,arm):
 out=[]
 for o,m in ps:
  B=set(A[o]['arms'][arm].get('documents') or [])-{'lease_contract'}; after=set(A[m]['arms'][arm].get('documents') or [])-{'lease_contract'}
  out.append(B-after)
 return out

def audit(scope):
 if scope=='rent': ref,meta=reference('conf_ref_raw.json'); A={r['unit_id']:r for r in load('conf_arms.json')}; suffix='__e07'; arms=['b1_direct','b3_graph_then_list','b5_induced_graph']
 else: ref,meta=reference('term_ref_raw.json'); A={r['unit_id']:r for r in load('term_arms.json')}; suffix='__e05'; arms=['b1_direct','b3_graph_then_list','b5_induced_graph']
 ps=pairs(A,ref,suffix); gold=gold_sets(ref,ps); pm,pe,mp,ep=crossfit_constants(ps,gold,meta)
 out={'pairs':len(ps),'scenarios':sorted({meta[o] for o,_ in ps}),'gold':{'distinct_sets':len({tuple(sorted(g)) for g in gold}),'total_items':sum(map(len,gold))},'crossfit_no_input_micro_opt':{**metrics(pm,gold),'policy_count':len({tuple(sorted(x)) for x in mp.values()}),'policies':{k:sorted(v) for k,v in mp.items()}},'crossfit_no_input_exact_opt':{**metrics(pe,gold),'policy_count':len({tuple(sorted(x)) for x in ep.values()}),'policies':{k:sorted(v) for k,v in ep.items()}},'arms':{}}
 for a in arms:
  pred=arm_predictions(A,ps,a); out['arms'][a]={**metrics(pred,gold),'within_scenario_pairing_null':pairing_null(pred,gold,ps,meta)}
 return out

def main():
 out={'contract':'casepath.release-set-validity/1.0.0','metric_definition':'All policies predict exactly the release set E. micro-F1 pools TP/predicted/gold items; exact match is per pair. No request-set-volume baseline is used.','rent':audit('rent'),'termination':audit('term')}
 # sensitivity: rent without corrupted S8 scenario, evaluated with cross-fitting among remaining scenarios
 ref,meta=reference('conf_ref_raw.json'); A={r['unit_id']:r for r in load('conf_arms.json')}; ps=[p for p in pairs(A,ref,'__e07') if meta[p[0]]!='S8_nebenkosten_reclass']; gold=gold_sets(ref,ps); pm,pe,mp,ep=crossfit_constants(ps,gold,meta)
 out['rent_without_S8']={'pairs':len(ps),'crossfit_no_input_micro_opt':metrics(pm,gold),'crossfit_no_input_exact_opt':metrics(pe,gold),'arms':{}}
 for a in ['b1_direct','b3_graph_then_list','b5_induced_graph']:
  pred=arm_predictions(A,ps,a); out['rent_without_S8']['arms'][a]={**metrics(pred,gold),'within_scenario_pairing_null':pairing_null(pred,gold,ps,meta)}
 (ART/'RELEASE_SET_VALIDITY.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
 print(json.dumps(out,indent=2))
if __name__=='__main__': main()
