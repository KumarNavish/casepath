from pathlib import Path
import json
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
R=HERE.parent
A=R/'artifacts'
V=json.loads((A/'EVALUATION_VALIDITY.json').read_text())
J=json.loads((A/'ADJUDICATOR_ROBUSTNESS.json').read_text())
HERE.mkdir(parents=True,exist_ok=True)

def pct(x): return f'{100*x:.1f}\\%'
def ci(v): return f'[{v[0]:+.3f}, {v[1]:+.3f}]'
# Table 1: static and dynamic falsification across the two scopes.
rows=[]
for scope,label,dyn in [('rent_increase','Rent increase','rent_dynamic'),('termination','Termination','termination_dynamic')]:
    st=V['static'][scope]
    d=V[dyn]
    cf=d['crossfit_input_independent_oracle']
    agents=d['models']['gpt-5.6-terra']['arms'] if scope=='rent_increase' else d['arms']
    best=max((v['excess'],k,v) for k,v in agents.items())
    rows.append((label,V['document_layer_capacity'][scope],st['distinct_gold_sets'],st['modal_oracle_mean_f1'],cf,best))
tex=['\\begin{tabular}{lrrrrr}','\\toprule','Scope & Capacity & Gold sets & Static oracle F1 & Const. excess & Best agent excess \\\\','\\midrule']
for label,cap,ng,f1v,cf,best in rows:
    tex.append(f'{label} & {cap} & {ng} & {f1v:.3f} & {cf["excess"]:+.3f} & {best[0]:+.3f} \\\\')
tex += ['\\bottomrule','\\end{tabular}']
(HERE/'table_core.tex').write_text('\n'.join(tex)+'\n')
# Table 2: evaluator robustness.  Exact release agreement is vs original GPT.
order=[('original_gpt','GPT-5.6 Terra'),('opus5','Claude Opus 5'),('gemini31pro','Gemini 3.1 Pro'),('deepseekv4pro','DeepSeek V4 Pro'),('external_consensus','3-family consensus')]
tex=['\\begin{tabular}{lrrrr}','\\toprule','Reference evaluator & Pairs & Release agreement & Const. excess & Best agent excess \\\\','\\midrule']
for key,label in order:
    audit=J['evaluator_audits'][key]
    cf=audit['crossfit_input_independent_oracle']
    vals=[v['arms']['b5_induced_graph']['excess'] for v in audit['interpreters'].values()]
    if key=='original_gpt': agree='--'
    else: agree=pct(J['agreements_vs_original_gpt'][key]['release']['exact_release_set_rate'])
    tex.append(f'{label} & {cf["n"]} & {agree} & {cf["excess"]:+.3f} & {max(vals):+.3f} \\\\')
tex += ['\\bottomrule','\\end{tabular}']
(HERE/'table_evaluator.tex').write_text('\n'.join(tex)+'\n')
# Figure 1: cross-fitted case-ignoring policy vs strongest measured agent.
labels=['Rent increase','Termination']
const=[V['rent_dynamic']['crossfit_input_independent_oracle']['excess'],V['termination_dynamic']['crossfit_input_independent_oracle']['excess']]
best=[max(v['excess'] for v in V['rent_dynamic']['models']['gpt-5.6-terra']['arms'].values()),max(v['excess'] for v in V['termination_dynamic']['arms'].values())]
x=range(len(labels)); w=.34
fig,ax=plt.subplots(figsize=(5.2,2.9))
ax.bar([i-w/2 for i in x],const,w,label='Cross-fitted constant')
ax.bar([i+w/2 for i in x],best,w,label='Best measured agent')
ax.axhline(0,linewidth=.8)
ax.set_xticks(list(x),labels); ax.set_ylabel('Excess withdrawal recall')
ax.legend(frameon=False,fontsize=8); ax.spines[['top','right']].set_visible(False)
for i,v in enumerate(const): ax.text(i-w/2,v+.015,f'{v:+.3f}',ha='center',fontsize=8)
for i,v in enumerate(best): ax.text(i+w/2,v+.015,f'{v:+.3f}',ha='center',fontsize=8)
fig.tight_layout(); fig.savefig(HERE/'fig_constant_vs_agent.pdf',bbox_inches='tight'); plt.close(fig)
# Figure 2: rent-increase pairing-permutation test for the b5 interpreter conditions.
models=[('gpt-5.6-terra','GPT'),('claude-haiku-4.5','Haiku'),('gemini-2.5-flash','Gemini'),('deepseek-v3.2','DeepSeek')]
obs=[]; lo=[]; hi=[]; ps=[]
for key,_ in models:
    r=V['rent_dynamic']['models'][key]['arms']['b5_induced_graph']
    p=r['within_scenario_permutation']; obs.append(r['excess']); lo.append(p['null_range95'][0]); hi.append(p['null_range95'][1]); ps.append(p['p_ge_observed_plus1'])
fig,ax=plt.subplots(figsize=(5.2,3.0))
y=list(range(len(models)))
ax.hlines(y,lo,hi,linewidth=5,label='95% wrong-pairing null')
ax.scatter(obs,y,zorder=3,label='Observed')
ax.axvline(0,linewidth=.8)
ax.set_yticks(y,[m[1] for m in models]); ax.set_xlabel('Excess withdrawal recall')
ax.invert_yaxis(); ax.spines[['top','right']].set_visible(False); ax.legend(frameon=False,fontsize=8,loc='lower right')
for i,p in enumerate(ps): ax.text(max(hi)+.008,i,f'p={p:.2f}',va='center',fontsize=8)
fig.tight_layout(); fig.savefig(HERE/'fig_pairing_null.pdf',bbox_inches='tight'); plt.close(fig)
