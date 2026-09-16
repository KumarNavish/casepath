"""The single confirmatory read. Fixed before the data existed; run once."""
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
graph=json.load(open(_p("/tmp/graph_s2.json")))
props={p["proposition_id"]:p for p in json.load(open(_p("/tmp/props_bundle.json")))}
HELD=["lease_contract"]
by=collections.defaultdict(list); meta={}
for r in json.load(open(_p("/tmp/conf_ref_raw.json"))):
    if r.get("decisions"): by[r["unit_id"]].append(r); meta[r["unit_id"]]=r["scenario"]
ref={}
for u,v in by.items():
    st=cs.adjudicate(v)
    ref[u]={**cs.reference_set(C,st,held=HELD),
            "unanimity":sum(1 for x in st.values() if x["unanimous"])/len(st)}
A={r["unit_id"]:r for r in json.load(open(_p("/tmp/conf_arms.json")))}
pairs=[(u,u[:-6]+"__e07") for u in sorted(A) if u.endswith("__orig")
       and (u[:-6]+"__e07") in A and u in ref and (u[:-6]+"__e07") in ref]
E_nonempty=sum(1 for o,m in pairs if set(ref[o]["documents"])-set(ref[m]["documents"]))
print("="*96); print("CONFIRMATORY READ — rent increase, 6 held-out scenarios"); print("="*96)
print(f"pairs: {len(pairs)}   scenarios: {len(set(meta[o] for o,_ in pairs))}")
if not pairs:
    print("NO PAIRS — a unit is missing its ground truth or its arm run. Nothing is reported.")
    raise SystemExit(1)
print(f"pairs with a non-empty expected withdrawal: {E_nonempty}")
print(f"adjudicator unanimity: {sum(ref[u]['unanimity'] for u,_ in pairs)/len(pairs):.0%}")
if E_nonempty < 15:
    print("\nPREREGISTERED UNINFORMATIVE CONDITION MET (<15 pairs with a non-empty expected withdrawal).")
    print("No primary comparison is reported. The intervention does not bite on these scenarios.")
rows={}
for arm in ("b1_direct","b3_graph_then_list","b5_induced_graph"):
    rs=[]
    for o,m in pairs:
        Ew=set(ref[o]["documents"])-set(ref[m]["documents"]); K=set(ref[m]["documents"])
        b=set(A[o]["arms"][arm].get("documents") or [])-set(HELD)
        af=set(A[m]["arms"][arm].get("documents") or [])-set(HELD)
        w=b-af
        j=cs.score_justification(A[o]["arms"][arm].get("chains") or [], ref[o], C, graph, props)
        rs.append({"scenario":meta[o],"E":len(Ew),"ok":len(w&Ew),"false":len(w&K),
                   "keep":len((b&K)&af),"keepable":len(b&K),"req":len(b),
                   "grnd":j["grounded_rate"],"chain":j["chain_rate"]})
    rows[arm]=rs
print(f"\n{'arm':24} {'expW':>5} {'okW':>4} {'falsW':>6} {'recall':>7} {'prec':>7} {'retain':>7} {'#req':>6} {'chain':>6} {'grnd':>6}")
for arm,rs in rows.items():
    E=sum(r["E"] for r in rs); ok=sum(r["ok"] for r in rs); fa=sum(r["false"] for r in rs)
    kp=sum(r["keepable"] for r in rs); st=sum(r["keep"] for r in rs)
    print(f"{arm:24} {E:5} {ok:4} {fa:6} {ok/E if E else 0:7.3f} {ok/(ok+fa) if ok+fa else 0:7.3f} "
          f"{st/kp if kp else 0:7.3f} {sum(r['req'] for r in rs)/len(rs):6.1f} "
          f"{sum(r['chain'] for r in rs)/len(rs):6.3f} {sum(r['grnd'] for r in rs)/len(rs):6.3f}")
def boot(a,b):
    sc=collections.defaultdict(list)
    for i,x in enumerate(rows[a]): sc[x["scenario"]].append(i)
    names=list(sc); rnd=random.Random(20260916)
    def rate(arm,idx):
        E=sum(rows[arm][i]["E"] for i in idx); return sum(rows[arm][i]["ok"] for i in idx)/E if E else 0.0
    allidx=list(range(len(rows[a])))
    obs=rate(a,allidx)-rate(b,allidx); d=[]
    for _ in range(5000):
        idx=[i for _ in names for i in sc[names[rnd.randrange(len(names))]]]
        d.append(rate(a,idx)-rate(b,idx))
    d.sort(); return obs,d[125],d[4875],len(names)
def ret(arm):
    kp=sum(r["keepable"] for r in rows[arm]); return sum(r["keep"] for r in rows[arm])/kp if kp else 0
print("\n--- PRIMARY (amendment A3): b3_graph_then_list vs b1_direct ---")
o,lo,hi,ns=boot("b3_graph_then_list","b1_direct")
print(f"withdrawal recall difference: {o:+.3f}   95% CI [{lo:+.3f}, {hi:+.3f}]   ({ns} scenarios, {len(pairs)} pairs)")
rd=ret("b3_graph_then_list")-ret("b1_direct")
print(f"retention difference: {rd:+.3f}  (support requires not worse than -0.050)")
ok = (lo>0) and (rd>=-0.05)
print(f"\nPREREGISTERED VERDICT: {'SUPPORTED' if ok else 'NOT SUPPORTED'}")
if not ok:
    print("  reason:", "interval includes or lies below zero" if lo<=0 else "retention penalty exceeds 0.050")
print("\n--- SECONDARY (formerly primary): b5_induced_graph vs b1_direct ---")
o5,lo5,hi5,_=boot("b5_induced_graph","b1_direct")
print(f"withdrawal recall difference: {o5:+.3f}   95% CI [{lo5:+.3f}, {hi5:+.3f}]  "
      f"{'excludes zero' if lo5>0 or hi5<0 else 'includes zero'}")
# --- volume control -------------------------------------------------------------------------------
# b5 requests about twice as many documents as the others, and an arm that asks for more has more to
# drop. A raw withdrawal recall is therefore not comparable across arms. Compare each arm against
# ITSELF dropping the same number of its own requested documents at random.
print("\n--- volume control: withdrawal recall above each arm's own random-drop baseline ---")
print(f"{'arm':24} {'recall':>7} {'random':>7} {'excess':>8} {'95% CI':>20}")
ctl={}
for arm in rows:
    rs=[]
    for o,m in pairs:
        Ew=set(ref[o]["documents"])-set(ref[m]["documents"])
        b=set(A[o]["arms"][arm].get("documents") or [])-set(HELD)
        af=set(A[m]["arms"][arm].get("documents") or [])-set(HELD)
        w=b-af
        rok=(len(w)*len(b&Ew)/len(b)) if b else 0.0
        rs.append({"sc":meta[o],"E":len(Ew),"ok":len(w&Ew),"rok":rok})
    sc=collections.defaultdict(list)
    for i,x in enumerate(rs): sc[x["sc"]].append(i)
    names=list(sc); rb=random.Random(7)
    def _lift(idx):
        return (sum(rs[i]["ok"] for i in idx)-sum(rs[i]["rok"] for i in idx))/max(1e-9,sum(rs[i]["E"] for i in idx))
    obs=_lift(range(len(rs))); d=[]
    for _ in range(5000):
        idx=[i for _ in names for i in sc[names[rb.randrange(len(names))]]]
        d.append(_lift(idx))
    d.sort()
    E=sum(x["E"] for x in rs); ok=sum(x["ok"] for x in rs); rk=sum(x["rok"] for x in rs)
    ctl[arm]={"recall":ok/E,"random":rk/E,"excess":obs,"ci":[d[125],d[4875]]}
    tag="below own baseline" if d[4875]<0 else ("above own baseline" if d[125]>0 else "overlaps own baseline")
    print(f"{arm:24} {ok/E:7.3f} {rk/E:7.3f} {obs:+8.3f}  [{d[125]:+.3f}, {d[4875]:+.3f}]  {tag}")
print("  This control corrects withdrawal volume only. Case-specific information is tested separately by permutation in evaluation_validity_analysis.py.")

Path(_A, "confirmatory_result.json").write_text(json.dumps(
  {"pairs":len(pairs),"rows":rows,"volume_control":ctl,"primary":{"delta":o,"ci":[lo,hi],"retention_delta":rd,"supported":ok},
   "secondary_b5":{"delta":o5,"ci":[lo5,hi5]}},ensure_ascii=False,indent=1))
print("\nwritten committed-artifact location: confirmatory_result.json")
