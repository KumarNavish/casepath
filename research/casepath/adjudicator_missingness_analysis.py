"""Post-run descriptive missingness audit for cross-family adjudication."""
import collections,json
from pathlib import Path
HERE=Path(__file__).resolve().parent; ART=HERE/'artifacts'
raw=json.loads((ART/'cross_adjudicators_raw.json').read_text())
rob=json.loads((ART/'ADJUDICATOR_ROBUSTNESS.json').read_text())
units={u['unit_id']:u for u in json.loads((ART/'conf_cases.json').read_text())}
rows=raw['rows']; tags=['opus5','gemini31pro','deepseekv4pro']
by=collections.defaultdict(lambda:collections.defaultdict(list))
for r in rows:
 if r.get('ok') and r.get('decisions'): by[r['adjudicator_tag']][r['unit_id']].append(r)

def unit_valid(tag,u): return len(by[tag].get(u,[]))>=2
def length_stats(ids):
 vals=[len(units[u]['text']) for u in ids]
 return {'n':len(vals),'mean_chars':sum(vals)/len(vals) if vals else None,'median_chars':sorted(vals)[len(vals)//2] if vals else None,'max_chars':max(vals) if vals else None}
out={'contract':'casepath.adjudicator-missingness/1.0.0','families':{}}
for tag in tags:
 inc=[u for u in units if unit_valid(tag,u)]; exc=[u for u in units if not unit_valid(tag,u)]
 out['families'][tag]={'included':length_stats(inc),'excluded':length_stats(exc),'excluded_by_scenario':dict(collections.Counter(units[u]['scenario'] for u in exc)),'included_by_scenario':dict(collections.Counter(units[u]['scenario'] for u in inc))}
common=[u for u in units if all(unit_valid(t,u) for t in tags)]; exc=[u for u in units if u not in common]
out['three_family_complete_case']={'included':length_stats(common),'excluded':length_stats(exc),'excluded_by_scenario':dict(collections.Counter(units[u]['scenario'] for u in exc))}
# Pair retention by scenario for consensus complete-case subset.
pairs=[]
for u in sorted(units):
 if not u.endswith('__orig'): continue
 m=u[:-6]+'__e07'
 if m in units:
  pairs.append((u,m))
out['pair_retention']={}
for scenario in sorted({units[o]['scenario'] for o,_ in pairs}):
 ps=[p for p in pairs if units[p[0]]['scenario']==scenario]
 kept=sum(p[0] in common and p[1] in common for p in ps)
 out['pair_retention'][scenario]={'total':len(ps),'kept':kept,'rate':kept/len(ps) if ps else None}
(ART/'ADJUDICATOR_MISSINGNESS.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
print(json.dumps(out,indent=2))
