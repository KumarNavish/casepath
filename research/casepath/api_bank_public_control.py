"""Public diagnostic on API-Bank's released level-2 ToolSearcher samples.

This is deliberately scoped to the public sample layer, not the full API-Bank benchmark.
The target tool is the task API encoded in each sample filename; we ask whether the
ToolSearcher candidate ordering itself reveals that target without reading the user query.
"""
from pathlib import Path
import collections, hashlib, json, math, random, re, urllib.request

HERE=Path(__file__).resolve().parent
OUT=HERE/'artifacts/APIBANK_PUBLIC_CONTROL.json'
COMMIT='188835d4f9948563a6b9c8ac50cd0f3ae4021ed6'
DIR='api-bank/lv1-lv2-samples/level-2-toolsearcher'
API=f'https://api.github.com/repos/AlibabaResearch/DAMO-ConvAI/contents/{DIR}?ref={COMMIT}'
RAW=f'https://raw.githubusercontent.com/AlibabaResearch/DAMO-ConvAI/{COMMIT}/{DIR}/'
SEED=20260916; N_PERM=1000

def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'casepath-research'})
    return urllib.request.urlopen(req,timeout=60).read()

def tokens(text):
    return set(re.findall(r'[a-z0-9]{3,}', text.lower().replace('_',' ')))

def lexical_choice(query,candidates):
    q=tokens(query); scored=[]
    for i,c in enumerate(candidates):
        text=(c.get('name') or '')+' '+(c.get('description') or '')+' '+(c.get('desc_for_search') or '')
        t=tokens(text); inter=len(q&t)
        score=inter/math.sqrt(max(1,len(q))*max(1,len(t)))
        scored.append((score,inter,-i,c.get('name')))
    return max(scored)[3]

items=json.loads(get(API))
rows=[]; excluded=[]; hashes={}
for item in items:
    name=item['name']
    if not name.endswith('.jsonl'): continue
    filename_target=name.split('-level-3-')[0]
    data=get(RAW+name); hashes[name]=hashlib.sha256(data).hexdigest()
    msgs=[json.loads(x) for x in data.decode().splitlines() if x.strip()]
    user=next((m['text'] for m in msgs if m.get('role')=='User'),None)
    search_idx=next((i for i,m in enumerate(msgs) if m.get('role')=='API' and m.get('api_name')=='ToolSearcher'),None)
    search=msgs[search_idx] if search_idx is not None else None
    target=None
    if search_idx is not None:
        later=[m.get('api_name') for m in msgs[search_idx+1:] if m.get('role')=='API' and m.get('api_name') not in ('ToolSearcher','GetUserToken')]
        if later: target=later[-1]

    if not user or not search or not target:
        excluded.append({'file':name,'reason':'missing user, ToolSearcher, or downstream task API'}); continue
    output=(search.get('result') or {}).get('output') or []
    candidates=output if isinstance(output,list) else [output] if isinstance(output,dict) else []
    if len(candidates)<2:
        excluded.append({'file':name,'reason':'fewer than two returned candidates'}); continue
    names=[c.get('name') for c in candidates]
    if target not in names:
        excluded.append({'file':name,'reason':'downstream-called target absent from returned candidates','target':target,'filename_target':filename_target}); continue
    rows.append({'id':name,'query':user,'candidates':candidates,'gold':target,'filename_target':filename_target,'gold_position':names.index(target)})

position_counts=collections.Counter(r['gold_position'] for r in rows)
best_position,best_hits=position_counts.most_common(1)[0]
blind_accuracy=best_hits/len(rows)
lexical_hits=sum(lexical_choice(r['query'],r['candidates'])==r['gold'] for r in rows)
lexical_accuracy=lexical_hits/len(rows)

rng=random.Random(SEED); values=[]; queries=[r['query'] for r in rows]
for _ in range(N_PERM):
    q=list(queries); rng.shuffle(q)
    hits=sum(lexical_choice(x,r['candidates'])==r['gold'] for x,r in zip(q,rows))
    values.append(hits/len(rows))
values.sort()

result={
    'contract':'casepath.public-benchmark-control/1.0.0',
    'benchmark':'API-Bank released level-2 ToolSearcher samples',
    'paper':'Li et al., EMNLP 2023, API-Bank: A Comprehensive Benchmark for Tool-Augmented LLMs',
    'repository_commit':COMMIT,
    'sample_directory':DIR,
    'source_sha256':hashes,
    'n_multi_candidate_evaluable':len(rows),
    'excluded_count':len(excluded),
    'excluded':excluded,
    'query_blind_oracle':{'policy':f'always choose returned candidate position {best_position}',
        'accuracy':blind_accuracy,'hits':best_hits,'position_counts':dict(sorted(position_counts.items()))},
    'query_conditioned_lexical_selector':{'accuracy':lexical_accuracy,'hits':lexical_hits},
    'wrong_query_permutation':{'draws':N_PERM,'seed':SEED,'mean_accuracy':sum(values)/len(values),
        'range95':[values[int(.025*N_PERM)],values[int(.975*N_PERM)]],
        'max_accuracy':max(values),
        'p_ge_observed_plus1':(sum(v>=lexical_accuracy for v in values)+1)/(N_PERM+1)},
    'interpretation':'diagnostic warning: in every evaluable multi-candidate ToolSearcher sample, the API actually called later in the released transcript is at returned candidate position 1, so this released sample layer is solvable without the query',
    'scope_limit':'This finding applies only to the small released level-2 ToolSearcher sample directory after explicit exclusions. It is not a claim about API-Bank overall scores or the full evaluation corpus.'
}
OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps(result,indent=2))
