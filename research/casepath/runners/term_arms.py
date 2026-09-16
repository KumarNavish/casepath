import sys, json, time
sys.path.insert(0,'.')
from pathlib import Path

import os as _os
_A = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "artifacts")
if not _os.path.isdir(_A):
    _A = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "casepath", "artifacts")
def _p(name):
    """Committed artifact if present, else the /tmp path the run originally wrote."""
    c = _os.path.join(_A, _os.path.basename(name))
    return c if _os.path.exists(c) else name

from casepath_api import process_experiment_v1 as px
from casepath_api.arena_v1 import transport
def call(system,user):
    r=transport.call_with_transport_retry([{"role":"system","content":system},{"role":"user","content":user}],
        model="openai/gpt-5.6-terra", max_tokens=8000, temperature=0.0, provider_only=["openai"])
    if not r["ok"]: raise RuntimeError(str(r.get("error"))[:200])
    return r["content"]
bundle=json.load(open("casepath_api/corpora/authority/swiss-authority-bundle-v1.json"))
props={p["proposition_id"]:p for p in json.load(open(_p("/tmp/props_term.json")))}
graph=json.load(open(_p("/tmp/graph_term.json")))
units=json.load(open(_p("/tmp/term_units.json")))
CAT=json.load(open(_p("/tmp/term_catalogue.json")))
SCOPE=("a tenant who has received a termination of a residential or commercial lease and is considering "
       "challenging it as void, abusive or improperly served, or requesting an extension")
ARMS=("b1_direct","b3_graph_then_list","b5_induced_graph")
done={}
if Path("/tmp/term_arms.partial.json").exists():
    for r in json.load(open(_p("/tmp/term_arms.partial.json"))): done[r["unit_id"]]=r
cache,out={},list(done.values())
for i,u in enumerate(units,1):
    if u["unit_id"] in done: continue
    t0=time.time()
    try:
        res=px.run_case(sources=bundle["passages"],propositions=props,case={"customer_message":u["text"]},
            catalogue=CAT,held=["lease_contract"],scope=SCOPE,induced_graph=graph,reference_graph=graph,
            call=call,arms=ARMS,cached=cache)
    except Exception as e:
        print(f"[{i:2d}/{len(units)}] {u['unit_id'][:28]} FAILED {type(e).__name__} {str(e)[:80]}",flush=True); continue
    cache=res.pop("_cached",cache)
    res.update({k:u[k] for k in ("unit_id","claim_id","scenario","arm_case")})
    out.append(res); Path("/tmp/term_arms.partial.json").write_text(json.dumps(out,ensure_ascii=False))
    print(f"[{i:2d}/{len(units)}] {u['unit_id'][:28]:30} {u['arm_case'][:14]:16} {time.time()-t0:4.0f}s " +
          " ".join(f"{a.split('_')[0]}={len(res['arms'][a].get('documents') or [])}" for a in ARMS),flush=True)
Path("/tmp/term_arms.json").write_text(json.dumps(out,ensure_ascii=False))
print(f"written /tmp/term_arms.json ({len(out)} units)")
