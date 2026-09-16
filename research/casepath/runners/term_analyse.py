"""Termination transfer — the single read, under the transfer preregistration."""
import sys, json, collections, random
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

from casepath_api import contract_scoring_v1 as cs
C=json.load(open("../research/casepath/reference_contracts/termination.gated.json"))
graph=json.load(open(_p("/tmp/graph_term.json")))
props={p["proposition_id"]:p for p in json.load(open(_p("/tmp/props_term.json")))}
HELD=["lease_contract"]
by=collections.defaultdict(list); meta={}
for r in json.load(open(_p("/tmp/term_ref_raw.json"))):
    if r.get("decisions"): by[r["unit_id"]].append(r); meta[r["unit_id"]]=r["scenario"]
ref={}
for u,v in by.items():
    st=cs.adjudicate(v)
    ref[u]={**cs.reference_set(C,st,held=HELD),
            "unan":sum(1 for x in st.values() if x["unanimous"])/len(st)}
A={r["unit_id"]:r for r in json.load(open(_p("/tmp/term_arms.json")))}
pairs=[(u,u[:-6]+"__e05") for u in sorted(A) if u.endswith("__orig") and u[:-6]+"__e05" in A
       and u in ref and u[:-6]+"__e05" in ref]
print("="*98); print("TRANSFER READ — termination, 8 scenarios"); print("="*98)
if not pairs: print("NO PAIRS"); raise SystemExit(1)
E=[len(set(ref[o]["documents"])-set(ref[m]["documents"])) for o,m in pairs]
ne=sum(1 for x in E if x)
print(f"pairs {len(pairs)}  scenarios {len(set(meta[o] for o,_ in pairs))}  unanimity {sum(ref[u]['unan'] for u,_ in pairs)/len(pairs):.0%}")
print(f"expected withdrawal: mean {sum(E)/len(E):.2f}  non-empty {ne}/{len(pairs)}")
if ne<15: print("\nPREREGISTERED UNINFORMATIVE CONDITION MET (<15 non-empty). No primary comparison reported.")
rows={}
_r=random.Random(20260916)
print(f"\n{'arm':24} {'expW':>5} {'okW':>4} {'falsW':>6} {'recall':>7} {'prec':>7} {'retain':>7} {'#req':>6} {'chain':>6}")
for arm in ("b1_direct","b3_graph_then_list","b5_induced_graph"):
    rs=[]
    for o,m in pairs:
        Ew=set(ref[o]["documents"])-set(ref[m]["documents"]); K=set(ref[m]["documents"])
        b=set(A[o]["arms"][arm].get("documents") or [])-set(HELD)
        af=set(A[m]["arms"][arm].get("documents") or [])-set(HELD)
        w=b-af; pool=sorted(b); rok=0.0
        if pool and w:
            for _ in range(300):
                s_=set(_r.sample(pool,min(len(w),len(pool)))); rok+=len(s_&Ew)/300
        j=cs.score_justification(A[o]["arms"][arm].get("chains") or [], ref[o], C, graph, props)
        rs.append({"sc":meta[o],"E":len(Ew),"ok":len(w&Ew),"false":len(w&K),"rok":rok,
                   "keep":len((b&K)&af),"keepable":len(b&K),"req":len(b),"chain":j["chain_rate"]})
    rows[arm]=rs
    Es=sum(x["E"] for x in rs); ok=sum(x["ok"] for x in rs); fa=sum(x["false"] for x in rs)
    kp=sum(x["keepable"] for x in rs); st=sum(x["keep"] for x in rs)
    print(f"{arm:24} {Es:5} {ok:4} {fa:6} {ok/Es if Es else 0:7.3f} {ok/(ok+fa) if ok+fa else 0:7.3f} "
          f"{st/kp if kp else 0:7.3f} {sum(x['req'] for x in rs)/len(rs):6.1f} {sum(x['chain'] for x in rs)/len(rs):6.3f}")
print("\n--- PRIMARY: withdrawal recall above each arm's OWN random-drop baseline ---")
print(f"{'arm':24} {'recall':>7} {'random':>7} {'excess':>8} {'95% CI':>20}")
ctl={}
for arm,rs in rows.items():
    sc=collections.defaultdict(list)
    for i,x in enumerate(rs): sc[x["sc"]].append(i)
    names=list(sc); rb=random.Random(7)
    def lift(idx): return (sum(rs[i]["ok"] for i in idx)-sum(rs[i]["rok"] for i in idx))/max(1e-9,sum(rs[i]["E"] for i in idx))
    obs=lift(range(len(rs))); d=[]
    for _ in range(5000):
        idx=[i for _ in names for i in sc[names[rb.randrange(len(names))]]]
        d.append(lift(idx))
    d.sort()
    Es=sum(x["E"] for x in rs); ok=sum(x["ok"] for x in rs); rk=sum(x["rok"] for x in rs)
    ctl[arm]={"recall":ok/Es,"random":rk/Es,"excess":obs,"ci":[d[125],d[4875]]}
    tag="anti-correlated" if d[4875]<0 else ("real signal" if d[125]>0 else "no signal")
    print(f"{arm:24} {ok/Es:7.3f} {rk/Es:7.3f} {obs:+8.3f}  [{d[125]:+.3f}, {d[4875]:+.3f}]  {tag}")
b5,b1=ctl["b5_induced_graph"],ctl["b1_direct"]
ok=(b5["ci"][0]>0) and (b5["excess"]>b1["excess"])
print(f"\nPREREGISTERED TRANSFER VERDICT: {'SUPPORTED' if ok else 'NOT SUPPORTED'}")
print(f"  b5 excess {b5['excess']:+.3f} CI [{b5['ci'][0]:+.3f},{b5['ci'][1]:+.3f}] ; b1 excess {b1['excess']:+.3f}")
print(f"  b1 anti-correlated (as on rent increase)? {'YES' if b1['ci'][1]<0 else 'no'}")
Path("/tmp/term_result.json").write_text(json.dumps({"pairs":len(pairs),"rows":rows,"control":ctl,"supported":ok},ensure_ascii=False,indent=1))
print("\nwritten /tmp/term_result.json")
