"""Model-generality: does b1's anti-correlation and b5's signal survive a change of reasoner?"""
import sys, json, collections, random
sys.path.insert(0,'.')
from pathlib import Path
from casepath_api import contract_scoring_v1 as cs
C=json.load(open("../research/casepath/reference_contracts/rent_increase.json"))
HELD={"lease_contract"}
by=collections.defaultdict(list); meta={}
for r in json.load(open("/tmp/conf_ref_raw.json")):
    if r.get("decisions"): by[r["unit_id"]].append(r); meta[r["unit_id"]]=r["scenario"]
ref={u:cs.reference_set(C,cs.adjudicate(v),held=list(HELD)) for u,v in by.items()}
SRC=[("gpt-5.6-terra","/tmp/conf_arms.json"),("claude-haiku-4.5","/tmp/mm_haiku.json"),
     ("gemini-2.5-flash","/tmp/mm_gemini.json"),("deepseek-v3.2","/tmp/mm_deepseek.json")]
print("="*104)
print("MODEL GENERALITY — same held-out pairs, same frozen graph, same contract; only the reasoner changes")
print("="*104)
print(f"{'model':18} {'arm':22} {'n':>3} {'recall':>7} {'random':>7} {'excess':>8} {'95% CI':>20}")
allres={}
for name,path in SRC:
    p=Path(path)
    if not p.exists():
        part=Path(path.replace(".json",".partial.json"))
        if not part.exists(): print(f"{name:18} (no data yet)"); continue
        p=part
    A={r["unit_id"]:r for r in json.load(open(p))}
    pairs=[(u,u[:-6]+"__e07") for u in sorted(A) if u.endswith("__orig") and u[:-6]+"__e07" in A
           and u in ref and u[:-6]+"__e07" in ref]
    if len(pairs)<8: print(f"{name:18} only {len(pairs)} pairs so far — skipped"); continue
    arms=[a for a in ("b1_direct","b5_induced_graph") if all(a in A[o]["arms"] for o,_ in pairs)]
    _r=random.Random(20260916)
    for arm in arms:
        rs=[]
        for o,m in pairs:
            Ew=set(ref[o]["documents"])-set(ref[m]["documents"])
            b=set(A[o]["arms"][arm].get("documents") or [])-HELD
            af=set(A[m]["arms"][arm].get("documents") or [])-HELD
            w=b-af; pool=sorted(b); rok=0.0
            if pool and w:
                for _ in range(300):
                    s_=set(_r.sample(pool,min(len(w),len(pool)))); rok+=len(s_&Ew)/300
            rs.append({"sc":meta[o],"E":len(Ew),"ok":len(w&Ew),"rok":rok,"req":len(b)})
        sc=collections.defaultdict(list)
        for i,x in enumerate(rs): sc[x["sc"]].append(i)
        names=list(sc); rb=random.Random(7)
        def lift(idx): return (sum(rs[i]["ok"] for i in idx)-sum(rs[i]["rok"] for i in idx))/max(1e-9,sum(rs[i]["E"] for i in idx))
        obs=lift(range(len(rs))); d=[]
        for _ in range(5000):
            idx=[i for _ in names for i in sc[names[rb.randrange(len(names))]]]
            d.append(lift(idx))
        d.sort()
        E=sum(x["E"] for x in rs); ok=sum(x["ok"] for x in rs); rk=sum(x["rok"] for x in rs)
        tag="ANTI-CORR" if d[4875]<0 else ("signal" if d[125]>0 else "none")
        allres[(name,arm)]={"excess":obs,"ci":[d[125],d[4875]],"recall":ok/E,"random":rk/E,"n":len(pairs),
                            "req":sum(x['req'] for x in rs)/len(rs)}
        print(f"{name:18} {arm:22} {len(pairs):3} {ok/E:7.3f} {rk/E:7.3f} {obs:+8.3f}  [{d[125]:+.3f},{d[4875]:+.3f}] {tag}")
Path("/tmp/mm_result.json").write_text(json.dumps({f"{k[0]}|{k[1]}":v for k,v in allres.items()},indent=1))
print("\nreplication check")
b1=[(m,v) for (m,a),v in allres.items() if a=="b1_direct"]
b5=[(m,v) for (m,a),v in allres.items() if a=="b5_induced_graph"]
print(f"  b1 anti-correlated (CI entirely below 0): {sum(1 for _,v in b1 if v['ci'][1]<0)}/{len(b1)} models")
print(f"  b5 real signal     (CI entirely above 0): {sum(1 for _,v in b5 if v['ci'][0]>0)}/{len(b5)} models")
print(f"  b5 excess > b1 excess in every model    : {all(dict(b5)[m]['excess']>dict(b1)[m]['excess'] for m,_ in b1 if m in dict(b5))}")
