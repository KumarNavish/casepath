import sys, json, collections, random

import os as _os
_A = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "artifacts")
if not _os.path.isdir(_A):
    _A = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "casepath", "artifacts")
def _p(name):
    """Committed artifact if present, else the /tmp path the run originally wrote."""
    c = _os.path.join(_A, _os.path.basename(name))
    return c if _os.path.exists(c) else name

sys.path.insert(0,'.')
from pathlib import Path


from casepath_api import contract_scoring_v1 as cs
C=json.load(open("../research/casepath/reference_contracts/rent_increase.json"))
HELD=["lease_contract"]
by=collections.defaultdict(list); meta={}
for p in ("/tmp/e1_ref_raw.json","/tmp/e07_ref_raw.json"):
    for r in json.load(open(p)):
        if r.get("decisions"):
            by[r["unit_id"]].append(r); meta[r["unit_id"]]=r["scenario"]
ref={u:{**cs.reference_set(C,cs.adjudicate(v),held=HELD),
        "unanimity":sum(1 for x in cs.adjudicate(v).values() if x["unanimous"])/len(cs.adjudicate(v))}
     for u,v in by.items()}
def load(*ps):
    A={}
    for p in ps:
        if Path(p).exists():
            try:
                for r in json.load(open(p)): A[r["unit_id"]]=r
            except Exception: pass
    return A
MX=load("/tmp/matrix.json","/tmp/matrix.partial.json")
V1=load("/tmp/e1_arms.json","/tmp/e1_arms.partial.json","/tmp/e07_arms.json","/tmp/e07_arms.partial.json")
V2=load("/tmp/v2_arms.json","/tmp/v2_arms.partial.json")
graph1=json.load(open(_p("/tmp/graph_s2.json"))); graph2=json.load(open(_p("/tmp/graph_s2_v2.json")))
props={p["proposition_id"]:p for p in json.load(open(_p("/tmp/props_bundle.json")))}
out={}

print("="*100); print("TABLE 1 — static floor check, clean development originals"); print("="*100)
src = MX if len(MX)>=8 else V1
orig=[u for u in src if u.endswith("__orig") and u in ref]
ARMS=sorted({a for u in orig for a in src[u]["arms"]})
print(f"{'arm':26} {'F1':>6} {'prec':>6} {'rec':>6} {'#req':>6} {'unjust':>7} {'chain':>6} {'grnd':>6}  n")
t1={}
for a in ARMS:
    rs=[]
    for u in orig:
        if a not in src[u]["arms"]: continue
        s=cs.score(src[u]["arms"][a].get("documents") or [], ref[u], held=HELD)
        j=cs.score_justification(src[u]["arms"][a].get("chains") or [], ref[u], C, graph1, props)
        rs.append({**s,**{"j_"+k:v for k,v in j.items()}})
    if not rs: continue
    m=lambda k: sum(r[k] for r in rs)/len(rs); t1[a]={k:m(k) for k in rs[0] if isinstance(rs[0][k],(int,float))}
    print(f"{a:26} {m('f1'):6.3f} {m('precision'):6.3f} {m('recall'):6.3f} {m('burden'):6.2f} "
          f"{m('unjustified_burden'):7.2f} {m('j_chain_rate'):6.3f} {m('j_grounded_rate'):6.3f}  {len(rs)}")
modal=collections.Counter(tuple(sorted(ref[u]["documents"])) for u in orig).most_common(1)[0][0]
ms=[cs.score(list(modal), ref[u], held=HELD) for u in orig]
f=lambda k: sum(x[k] for x in ms)/len(ms)
print(f"{'[modal-list oracle]':26} {f('f1'):6.3f} {f('precision'):6.3f} {f('recall'):6.3f} {f('burden'):6.2f} {f('unjustified_burden'):7.2f}")
print(f"\ndistinct reference checklists: {len(set(tuple(sorted(ref[u]['documents'])) for u in orig))} over {len(orig)} cases "
      f"| adjudicator unanimity {sum(ref[u]['unanimity'] for u in orig)/len(orig):.0%}")
out["table1"]=t1

def causal(A,arm,tag):
    pairs=[(u,u[:-6]+"__e07") for u in A if u.endswith("__orig") and (u[:-6]+"__e07") in A
           and u in ref and (u[:-6]+"__e07") in ref]
    if not pairs: return None
    rows=[]
    for o,m in pairs:
        E=set(ref[o]["documents"])-set(ref[m]["documents"]); K=set(ref[m]["documents"])
        b=set(A[o]["arms"][arm].get("documents") or [])-set(HELD)
        af=set(A[m]["arms"][arm].get("documents") or [])-set(HELD)
        w=b-af
        rows.append({"scenario":meta[o],"E":len(E),"ok":len(w&E),"false":len(w&K),
                     "keep":len((b&K)&af),"keepable":len(b&K),"req":len(b)})
    return rows
def show(rows,label):
    if not rows: print(f"{label:34} — no pairs"); return
    E=sum(r["E"] for r in rows); ok=sum(r["ok"] for r in rows); fa=sum(r["false"] for r in rows)
    kp=sum(r["keepable"] for r in rows); st=sum(r["keep"] for r in rows)
    print(f"{label:34} {len(rows):3} {E:5} {ok:4} {fa:6} {ok/E if E else 0:7.3f} "
          f"{ok/(ok+fa) if ok+fa else 0:7.3f} {st/kp if kp else 0:7.3f} {sum(r['req'] for r in rows)/len(rows):6.1f}")
print("\n"+"="*100); print("TABLE 2 — branch intervention e07 (the tenant did not challenge in time)"); print("="*100)
print(f"{'arm':34} {'n':>3} {'expW':>5} {'okW':>4} {'falsW':>6} {'recall':>7} {'prec':>7} {'retain':>7} {'#req':>6}")
res={}
for arm in ("b1_direct","b3_graph_then_list","b5_induced_graph"):
    r=causal(V1,arm,"v1"); res[("v1",arm)]=r; show(r,f"graph v1  {arm}")
print()
for arm in ("b3_graph_then_list","b5_induced_graph"):
    r=causal(V2,arm,"v2"); res[("v2",arm)]=r; show(r,f"graph v2  {arm}")
def boot(a,b):
    n=min(len(a),len(b)); a,b=a[:n],b[:n]
    sc=collections.defaultdict(list)
    for i,x in enumerate(a): sc[x["scenario"]].append(i)
    names=list(sc); rnd=random.Random(20260916)
    def rate(rows,idx):
        E=sum(rows[i]["E"] for i in idx); return sum(rows[i]["ok"] for i in idx)/E if E else 0.0
    obs=rate(a,range(n))-rate(b,range(n)); d=[]
    for _ in range(5000):
        idx=[i for _ in names for i in sc[names[rnd.randrange(len(names))]]]
        d.append(rate(a,idx)-rate(b,idx))
    d.sort(); return obs,d[125],d[4875],len(names),n
print()
for lbl,x,y in (("v1-B5 vs v1-B1",("v1","b5_induced_graph"),("v1","b1_direct")),
                ("v1-B3 vs v1-B1",("v1","b3_graph_then_list"),("v1","b1_direct")),
                ("v2-B5 vs v1-B5",("v2","b5_induced_graph"),("v1","b5_induced_graph")),
                ("v2-B5 vs v1-B1",("v2","b5_induced_graph"),("v1","b1_direct"))):
    if res.get(x) and res.get(y):
        o,lo,hi,ns,n=boot(res[x],res[y])
        print(f"{lbl:18} {o:+.3f}  95% CI [{lo:+.3f},{hi:+.3f}]  ({ns} scenarios, n={n})  "
              f"{'EXCLUDES ZERO' if lo>0 or hi<0 else 'includes zero'}")
out["table2"]={f"{k[0]}|{k[1]}":v for k,v in res.items() if v}
Path("/tmp/final_tables.json").write_text(json.dumps(out,ensure_ascii=False,indent=1))
print("\nwritten /tmp/final_tables.json")
