import json, sys, re
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

from concurrent.futures import ThreadPoolExecutor
from casepath_api.arena_v1 import transport
C=json.load(open("../research/casepath/reference_contracts/rent_increase.json"))
units=json.load(open(_p("/tmp/conf_cases.json")))
SYS=open(_p("/tmp/refcheck_sys.txt")).read()
def body(t):
    p=["CASE NARRATIVE:",t[:9200],"","DECISIONS:"]
    for d in C["decisions"]:
        p+=[f'\n[{d["decision_id"]}] {d["must_determine"][:260]}',
            f'  live_when: {d["live_when"]}', f'  dead_when: {d["dead_when"]}']
    return "\n".join(p)
def one(j):
    u,k=j
    r=transport.call_with_transport_retry(
        [{"role":"system","content":SYS},{"role":"user","content":body(u["text"])+f"\n\n(adjudicator {k})"}],
        model="openai/gpt-5.6-terra", max_tokens=8000, temperature=0.0, provider_only=["openai"])
    if not r["ok"]: return {"unit_id":u["unit_id"],"k":k,"error":str(r.get("error"))[:140]}
    m=re.search(r'\{.*\}',r["content"],re.S)
    try: o=json.loads(m.group(0))
    except Exception: return {"unit_id":u["unit_id"],"k":k,"error":"unparseable"}
    return {"unit_id":u["unit_id"],"claim_id":u["claim_id"],"scenario":u["scenario"],
            "arm_case":u["arm_case"],"k":k,"decisions":o.get("decisions")}
jobs=[(u,k) for u in units for k in (1,2,3)]
with ThreadPoolExecutor(max_workers=12) as ex: res=list(ex.map(one,jobs))
Path("/tmp/conf_ref_raw.json").write_text(json.dumps(res,ensure_ascii=False))
print(f"CONFIRMATORY adjudications: {sum(1 for r in res if r.get('decisions'))}/{len(res)}")
