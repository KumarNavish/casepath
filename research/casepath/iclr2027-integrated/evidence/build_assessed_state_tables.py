"""Render the separately specified current-case analysis without rescoring it."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOC = HERE.parent
DATA = HERE / 'native150' / 'ASSESSED_STATE_REPORT.json'
METRICS = [('required_node_precision','NP'),('required_node_recall','NR'),('required_node_f1','NF'),
           ('required_edge_precision','EP'),('required_edge_recall','ER'),('required_edge_f1','EF'),
           ('critical_evidence_recall','Crit'),('evidence_obligation_completeness','Obl'),
           ('valid_chain_precision','Chain'),('unnecessary_document_rate','U'),
           ('provenance_chain_inheritance_rate','Source')]
ARMS = [('CASEPATH_CONTROL','Cp',r'\casepath'),('COMPILED_EQUIVALENT','Ce','Compiled equivalent'),
        ('LOCAL_SCOPE_ABLATION','Ls','Local scope')]

def main():
    raw = DATA.read_bytes(); digest = hashlib.sha256(raw).hexdigest()
    assert digest == json.loads((HERE/'native150/MANIFEST.json').read_text())[DATA.name]
    d = json.loads(raw)
    assert not d['new_inference'] and not d['primary_result_replaced']
    macros, audit = [], []
    def emit(name,value,pointer,integer=False,signed=False):
        text = str(int(value)) if integer else format(value,'+.3f' if signed else '.3f')
        macros.append('\\newcommand{\\'+name+'}{'+text+'}')
        audit.append(dict(macro=name,value=value,rendered=text,source='native150/'+DATA.name,
                          source_sha256=digest,json_pointer=pointer))
    for split,tag in [('public_dev','Dev'),('hidden_test','Hid'),('all150','All')]:
        for arm,at,_ in ARMS:
            base=f'/splits/{split}/arms/{arm}'; a=d['splits'][split]['arms'][arm]
            emit(f'as{tag}{at}N',a['raw_count_contributing_cells'],base+'/raw_count_contributing_cells',True)
            for metric,mt in METRICS:
                emit(f'as{tag}{at}{mt}',a['metrics'][metric]['value'],base+f'/metrics/{metric}/value')
            for key,suffix in [('evidence/valid_chain_documents','Valid'),('evidence/requested_documents','Req'),
                               ('evidence/active_evidence_obligations','Obligations'),('evidence/orphan_documents','Orphans')]:
                emit(f'as{tag}{at}{suffix}',a['raw_native_counts'][key],base+'/raw_native_counts/'+key.replace('/','~1'),True)
        for i,p in enumerate(d['splits'][split]['paired_contrasts']):
            if p['comparator']!='LOCAL_SCOPE_ABLATION': continue
            mt=next(t for k,t in METRICS if k==p['metric'])
            for key,dt in [('conventional_paired_difference','D'),('conservative_paired_benefit','C')]:
                emit(f'as{tag}{dt}{mt}',p[key]['value'],f'/splits/{split}/paired_contrasts/{i}/{key}/value',signed=True)
    (DOC/'assessed_state_numbers.tex').write_text('% Separate retrospective current-case analysis.\n'+'\n'.join(macros)+'\n')
    (HERE/'ASSESSED_STATE_NUMERICAL_AUDIT.json').write_text(json.dumps({'schema':'casepath.assessed-state-publication-audit/1','numbers':audit},indent=2)+'\n')
    lines=[r'\begin{tabular}{lrrrrrr}',r'\toprule',
           r'& \multicolumn{2}{c}{Development} & \multicolumn{2}{c}{Protected} & \multicolumn{2}{c}{Combined} \\',
           r'\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}',
           r'Endpoint & Full & Local & Full & Local & Full & Local \\',r'\midrule']
    for label,mt in [('Node precision','NP'),('Node recall','NR'),('Node $F_1$','NF'),
                     ('Edge precision','EP'),('Edge recall','ER'),('Edge $F_1$','EF'),
                     ('Critical-evidence recall','Crit'),('Obligation completeness','Obl'),
                     ('Valid-chain precision','Chain'),('Unnecessary fraction','U'),
                     ('Source-chain inheritance','Source'),('Scored cells','N')]:
        lines.append(label+' & '+' & '.join(f'\\as{tag}{at}{mt}' for tag in ('Dev','Hid','All') for at in ('Cp','Ls'))+r' \\')
    lines.append(r'\midrule')
    lines.append('Valid / all requests & '+' & '.join(f'\\as{tag}{at}Valid/\\as{tag}{at}Req' for tag in ('Dev','Hid','All') for at in ('Cp','Ls'))+r' \\')
    lines += [r'\bottomrule',r'\end{tabular}']
    (DOC/'table_assessed_state.tex').write_text('\n'.join(lines)+'\n')
    print(f'Generated {len(macros)} audited current-case values and one grouped table.')

if __name__=='__main__': main()
