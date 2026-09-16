"""Frozen BFCL V4 Multiple positive-control audit. See BFCL_AUDIT_PROTOCOL.md."""
from __future__ import annotations
import collections, concurrent.futures, hashlib, importlib.util, json, os, random, sys, time, types
from enum import Enum
from pathlib import Path

HERE=Path(__file__).resolve().parent
SRC=HERE/'external/bfcl'
ART=HERE/'artifacts'
DATA=SRC/'BFCL_v4_multiple.json'
GOLD=SRC/'BFCL_v4_multiple_possible_answer.json'
CHECKER=SRC/'ast_checker_bfcl.py'
MODEL='google/gemini-3.8-flash'; TEMP=0.0; MAXTOK=900; SEED=20260916; NPERM=5000
KEY_FILE=Path.home()/'.config/casepath/openrouter.key'
SYSTEM='''You are being evaluated on function calling. Select exactly one available function for the user request and fill its arguments only from information in that request. Return JSON only with this exact shape: {"calls":[{"name":"EXACT_FUNCTION_NAME","arguments":{}}]}. Use an exact function name from AVAILABLE_FUNCTIONS. Do not add prose.'''

def load_jsonl(p): return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def load_bfcl_checker():
    # Stub only modules imported by BFCL's checker that are irrelevant to Python AST evaluation.
    class Language(Enum): PYTHON='python'; JAVA='java'; JAVASCRIPT='javascript'
    enums=types.ModuleType('bfcl_eval.constants.enums'); enums.Language=Language
    cfg=types.ModuleType('bfcl_eval.constants.model_config')
    cfg.MODEL_CONFIG_MAPPING={'bfcl-local':types.SimpleNamespace(underscore_to_dot=False)}
    tm=types.ModuleType('bfcl_eval.constants.type_mappings'); tm.JAVA_TYPE_CONVERSION={}; tm.JS_TYPE_CONVERSION={}
    jc=types.ModuleType('bfcl_eval.eval_checker.ast_eval.type_convertor.java_type_converter'); jc.java_type_converter=lambda v,*a:v
    jsc=types.ModuleType('bfcl_eval.eval_checker.ast_eval.type_convertor.js_type_converter'); jsc.js_type_converter=lambda v,*a:v
    for name,mod in [('bfcl_eval.constants.enums',enums),('bfcl_eval.constants.model_config',cfg),('bfcl_eval.constants.type_mappings',tm),('bfcl_eval.eval_checker.ast_eval.type_convertor.java_type_converter',jc),('bfcl_eval.eval_checker.ast_eval.type_convertor.js_type_converter',jsc)]: sys.modules[name]=mod
    spec=importlib.util.spec_from_file_location('bfcl_ast_frozen',CHECKER); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod,Language

def question_text(item):
    return '\n'.join(m.get('content','') for turn in item['question'] for m in turn if m.get('role')=='user')
def make_user(item,removed):
    q='[REMOVED BY INPUT-DEPENDENCE AUDIT]' if removed else question_text(item)
    return 'USER_QUERY:\n'+q+'\n\nAVAILABLE_FUNCTIONS:\n'+json.dumps(item['function'],ensure_ascii=False,separators=(',',':'))
def normalize(content):
    try:
        obj=json.loads(content); calls=obj.get('calls')
        if not isinstance(calls,list) or len(calls)!=1: return None,'wrong_call_count'
        c=calls[0]; name=c.get('name'); args=c.get('arguments')
        if not isinstance(name,str) or not isinstance(args,dict): return None,'bad_call_shape'
        return [{name:args}],None
    except Exception as e: return None,'json_parse:'+type(e).__name__

def provider_call(item,condition):
    import httpx
    payload={'model':MODEL,'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':make_user(item,condition=='query_removed')}], 'temperature':TEMP,'max_tokens':MAXTOK,'response_format':{'type':'json_object'},'usage':{'include':True},'provider':{'only':['google'],'allow_fallbacks':False}}
    headers={'Authorization':'Bearer '+KEY_FILE.read_text().strip(),'Content-Type':'application/json','HTTP-Referer':'https://casepath.local/research','X-Title':'CasePath BFCL validity audit'}
    t=time.time()
    try:
        r=httpx.post('https://openrouter.ai/api/v1/chat/completions',headers=headers,json=payload,timeout=90)
        if r.status_code!=200: return {'id':item['id'],'condition':condition,'ok':False,'status':r.status_code,'error':r.text[:500],'latency_s':time.time()-t}
        body=r.json(); msg=body['choices'][0]['message']; content=msg.get('content') or ''
        norm,err=normalize(content)
        usage=body.get('usage') or {}
        return {'id':item['id'],'condition':condition,'ok':norm is not None,'content':content,'normalized':norm,'parse_error':err,'model':body.get('model'),'provider':body.get('provider'),'generation_id':body.get('id'),'usage':usage,'cost_usd':usage.get('cost'),'latency_s':time.time()-t,'payload_sha256':hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
    except Exception as e: return {'id':item['id'],'condition':condition,'ok':False,'status':None,'error':f'{type(e).__name__}: {e}'[:500],'latency_s':time.time()-t}

def score_one(checker,Language,item,gold,norm):
    if norm is None: return False
    try: return bool(checker.ast_checker(item['function'],norm,gold['ground_truth'],Language.PYTHON,'bfcl-local')['valid'])
    except Exception: return False

def main(execute=True):
    data=load_jsonl(DATA); gold=load_jsonl(GOLD); gmap={g['id']:g for g in gold}
    assert len(data)==len(gold)==200 and {x['id'] for x in data}==set(gmap)
    checker,Language=load_bfcl_checker()
    # BFCL scorer self-test on its official possible answers.
    ok=0
    for item in data:
        gt=gmap[item['id']]['ground_truth']
        ok += score_one(checker,Language,item,gmap[item['id']],gt)
    if ok!=200: raise RuntimeError(f'BFCL checker self-test failed: {ok}/200')
    raw_path=ART/'BFCL_POSITIVE_CONTROL_RAW.json'; existing=[]
    if raw_path.exists(): existing=json.loads(raw_path.read_text()).get('rows',[])
    done={(r['condition'],r['id']) for r in existing}; rows=list(existing)
    if execute:
        jobs=[(item,c) for c in ('full','query_removed') for item in data if (c,item['id']) not in done]
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            futs={ex.submit(provider_call,item,c):(item,c) for item,c in jobs}
            for k,f in enumerate(concurrent.futures.as_completed(futs),1):
                rows.append(f.result())
                raw={'contract':'casepath.bfcl-positive-control.raw/1.0.0','protocol_commit':'dbad05fde48b3b9a2b21da0f42c1392eff1bc4d5','bfcl_commit':'6ea57973c7a6097fd7c5915698c54c17c5b1b6c8','model':MODEL,'temperature':TEMP,'max_tokens':MAXTOK,'rows':rows}
                raw_path.write_text(json.dumps(raw,indent=2,sort_keys=True)+'\n')
                if k%20==0: print(f'{len(rows)}/400 persisted',flush=True)
    raw=json.loads(raw_path.read_text()); lookup={(r['condition'],r['id']):r for r in raw['rows']}
    out={'contract':'casepath.bfcl-positive-control/1.0.0','protocol_commit':raw['protocol_commit'],'bfcl_commit':raw['bfcl_commit'],'model':MODEL,'n':200,'source_hashes':{'data':sha(DATA),'gold':sha(GOLD),'checker':sha(CHECKER)},'conditions':{}}
    outputs={}
    for cond in ('full','query_removed'):
        ast=fn=parsed=0; norms=[]
        for item in data:
            r=lookup[(cond,item['id'])]; norm=r.get('normalized'); norms.append(norm)
            parsed += norm is not None
            ast += score_one(checker,Language,item,gmap[item['id']],norm)
            expected=list(gmap[item['id']]['ground_truth'][0])[0]
            got=list(norm[0])[0] if norm and len(norm)==1 else None
            fn += got==expected
        outputs[cond]=norms
        out['conditions'][cond]={'ast_correct':ast,'ast_accuracy':ast/200,'function_name_correct':fn,'function_name_accuracy':fn/200,'parse_valid':parsed,'parse_rate':parsed/200,'distinct_normalized_calls':len({json.dumps(x,sort_keys=True) for x in norms if x}),'distinct_function_names':len({list(x[0])[0] for x in norms if x})}
    rng=random.Random(SEED); vals=[]; full=outputs['full']
    for _ in range(NPERM):
        perm=list(full); rng.shuffle(perm)
        vals.append(sum(score_one(checker,Language,item,gmap[item['id']],norm) for item,norm in zip(data,perm))/200)
    vals.sort(); obs=out['conditions']['full']['ast_accuracy']; ge=sum(v>=obs-1e-15 for v in vals)
    out['wrong_pairing_permutation']={'draws':NPERM,'seed':SEED,'observed_ast_accuracy':obs,'null_mean':sum(vals)/len(vals),'null_95':[vals[int(.025*NPERM)],vals[int(.975*NPERM)]],'null_max':max(vals),'p_ge_plus1':(ge+1)/(NPERM+1)}
    out['execution']={'physical_calls':len(raw['rows']),'failed_or_unparseable':sum(not r.get('ok') for r in raw['rows']),'reported_cost_usd':sum(float(r.get('cost_usd') or 0) for r in raw['rows']),'returned_models':sorted({r.get('model') for r in raw['rows'] if r.get('model')})}
    (ART/'BFCL_POSITIVE_CONTROL.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps(out,indent=2))
if __name__=='__main__': main(execute=os.environ.get('BFCL_NO_EXECUTE')!='1')
