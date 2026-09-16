from pathlib import Path
import json
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent; R=HERE.parent; A=R/'artifacts'
S=json.loads((A/'RELEASE_SET_VALIDITY.json').read_text()); B=json.loads((A/'BFCL_POSITIVE_CONTROL.json').read_text()); J=json.loads((A/'ADJUDICATOR_ROBUSTNESS.json').read_text())

def best(d,key): return max(v[key] for v in d['arms'].values())
# Core symmetric release-set table.
rows=[]
for key,label in [('rent','Rent increase'),('termination','Termination')]:
 x=S[key]; rows.append((label,x['pairs'],x['gold']['distinct_sets'],x['crossfit_no_input_micro_opt']['micro_f1'],best(x,'micro_f1'),x['crossfit_no_input_exact_opt']['exact_match'],best(x,'exact_match')))
tex=['\\begin{tabular}{lrrrrrr}','\\toprule','Scope & Pairs & Gold sets & No-input $\\mu$F1 & Best agent $\\mu$F1 & No-input exact & Best agent exact \\\\','\\midrule']
for r in rows: tex.append(f'{r[0]} & {r[1]} & {r[2]} & {r[3]:.3f} & {r[4]:.3f} & {r[5]:.3f} & {r[6]:.3f} \\\\')
tex+=['\\bottomrule','\\end{tabular}']; (HERE/'table_core.tex').write_text('\n'.join(tex)+'\n')
# BFCL table.
f=B['conditions']['full']; q=B['conditions']['query_removed']; p=B['wrong_pairing_permutation']
tex=['\\begin{tabular}{lrrr}','\\toprule','BFCL condition & AST accuracy & Function-name accuracy & Parse rate \\\\','\\midrule',f'Full query & {f["ast_accuracy"]:.3f} & {f["function_name_accuracy"]:.3f} & {f["parse_rate"]:.3f} \\\\',f'Query removed & {q["ast_accuracy"]:.3f} & {q["function_name_accuracy"]:.3f} & {q["parse_rate"]:.3f} \\\\','\\bottomrule','\\end{tabular}']
(HERE/'table_bfcl.tex').write_text('\n'.join(tex)+'\n')
# Evaluator table retained for appendix.
order=[('original_gpt','GPT-5.6 Terra'),('opus5','Claude Opus 5'),('gemini31pro','Gemini 3.1 Pro'),('deepseekv4pro','DeepSeek V4 Pro'),('external_consensus','3-family consensus')]
tex=['\\begin{tabular}{lrrr}','\\toprule','Evaluator & Complete pairs & Exact release agreement & GPT-B5 excess \\\\','\\midrule']
for key,label in order:
 audit=J['evaluator_audits'][key]; score=J['b5_interpreter_by_evaluator']['gpt-5.6-terra'][key]['excess']
 agree='--' if key=='original_gpt' else f'{100*J["agreements_vs_original_gpt"][key]["release"]["exact_release_set_rate"]:.1f}\\%'
 tex.append(f'{label} & {audit['crossfit_input_independent_oracle']['n']} & {agree} & {score:+.3f} \\\\')
tex+=['\\bottomrule','\\end{tabular}']; (HERE/'table_evaluator.tex').write_text('\n'.join(tex)+'\n')
# Figure: symmetric CasePath release-set micro-F1.
labels=['Rent increase','Termination']; no=[S['rent']['crossfit_no_input_micro_opt']['micro_f1'],S['termination']['crossfit_no_input_micro_opt']['micro_f1']]; ag=[best(S['rent'],'micro_f1'),best(S['termination'],'micro_f1')]
fig,ax=plt.subplots(figsize=(5.15,2.75)); x=[0,1]; w=.34
ax.bar([i-w/2 for i in x],no,w,label='Cross-fitted no-input'); ax.bar([i+w/2 for i in x],ag,w,label='Best measured agent'); ax.set_ylim(0,1.02); ax.set_ylabel('Release-set micro-F1'); ax.set_xticks(x,labels); ax.spines[['top','right']].set_visible(False); ax.legend(frameon=False,fontsize=8)
for i,v in enumerate(no): ax.text(i-w/2,v+.025,f'{v:.3f}',ha='center',fontsize=8)
for i,v in enumerate(ag): ax.text(i+w/2,v+.025,f'{v:.3f}',ha='center',fontsize=8)
fig.tight_layout(); fig.savefig(HERE/'fig_casepath_release_f1.pdf',bbox_inches='tight'); plt.close(fig)
# Figure: BFCL positive control.
vals=[f['ast_accuracy'],q['ast_accuracy'],p['null_mean']]; labs=['Full query','Query removed','Wrong-pairing\nnull mean']
fig,ax=plt.subplots(figsize=(4.7,2.65)); ax.bar(range(3),vals); ax.set_ylim(0,1.02); ax.set_ylabel('BFCL AST accuracy'); ax.set_xticks(range(3),labs); ax.spines[['top','right']].set_visible(False)
for i,v in enumerate(vals): ax.text(i,v+.025,f'{v:.3f}',ha='center',fontsize=8)
fig.tight_layout(); fig.savefig(HERE/'fig_bfcl_control.pdf',bbox_inches='tight'); plt.close(fig)
# Machine-readable submission summary.
summary={'casepath':S,'bfcl':B,'adjudicator_robustness':{'opus':J['agreements_vs_original_gpt']['opus5'],'external_consensus':J['agreements_vs_original_gpt']['external_consensus']}}
(HERE/'submission_summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')

# Audit-plane figure and compact table: positive gaps are required for an input-conditioned claim.
def best_arm(scope):
    items=S[scope]['arms'].items(); return max(items,key=lambda kv:kv[1]['micro_f1'])
points=[]
for scope,label in [('rent','CasePath rent'),('termination','CasePath termination')]:
    an,av=best_arm(scope); no=S[scope]['crossfit_no_input_micro_opt']['micro_f1']; pair=av['within_scenario_pairing_null']['null_mean']; obs=av['micro_f1']; points.append((label,obs-no,obs-pair,obs,no,pair,an))
points.append(('BFCL Multiple',B['conditions']['full']['ast_accuracy']-B['conditions']['query_removed']['ast_accuracy'],B['conditions']['full']['ast_accuracy']-B['wrong_pairing_permutation']['null_mean'],B['conditions']['full']['ast_accuracy'],B['conditions']['query_removed']['ast_accuracy'],B['wrong_pairing_permutation']['null_mean'],'Gemini 3.8 Flash'))
tex=['\\begin{tabular}{lrrrr}','\\toprule','Evaluation & System/full & No-input & Wrong-pair mean & (Input gap, Pair gap) \\\\','\\midrule']
for label,ig,pg,obs,no,pair,arm in points: tex.append(f'{label} & {obs:.3f} & {no:.3f} & {pair:.3f} & ({ig:+.3f}, {pg:+.3f}) \\\\')
tex+=['\\bottomrule','\\end{tabular}']; (HERE/'table_audit_plane.tex').write_text('\n'.join(tex)+'\n')
fig,ax=plt.subplots(figsize=(4.7,3.0));
for label,ig,pg,*_ in points:
    ax.scatter([ig],[pg],s=45); ax.annotate(label,(ig,pg),xytext=(5,5),textcoords='offset points',fontsize=8)
ax.axhline(0,linewidth=.8); ax.axvline(0,linewidth=.8); ax.set_xlabel('Input gap: system − no-input'); ax.set_ylabel('Pairing gap: system − wrong-pair mean'); ax.spines[['top','right']].set_visible(False); fig.tight_layout(); fig.savefig(HERE/'fig_audit_plane.pdf',bbox_inches='tight'); plt.close(fig)
