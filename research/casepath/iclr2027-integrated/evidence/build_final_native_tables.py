"""Build publication tables from the completed primary and post-hoc evidence.

Every displayed number has a source hash and JSON pointer in the audit. The
request-only diagnostic never replaces the registered all-penalty result.
"""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
DOC = HERE.parent
DATA = HERE / 'native150'
ARMS = [('CASEPATH_CONTROL', 'Cp', r'\casepath'), ('DIRECT_REVIEWED', 'Dir', 'Direct'),
        ('DOCUMENT_FIRST_REVIEWED', 'Doc', 'Document-first'),
        ('PROCESS_CONTEXT_REVIEWED', 'Pc', 'Process-context'), ('RULE_FIRST_REVIEWED', 'Rf', 'Rule-first'),
        ('COMPILED_EQUIVALENT', 'Ce', 'Compiled equivalent'), ('LOCAL_SCOPE_ABLATION', 'Ls', 'Local-scope ablation')]
METRICS = [('emitted_checklist_precision', 'P'), ('emitted_checklist_recall', 'R'),
           ('emitted_checklist_f1', 'F'), ('emitted_checklist_exact', 'Exact'),
           ('emitted_unnecessary_fraction', 'U')]


def main():
    manifest = json.loads((DATA / 'MANIFEST.json').read_text())
    for name, checksum in manifest.items():
        if hashlib.sha256((DATA / name).read_bytes()).hexdigest() != checksum:
            raise ValueError('changed numerical evidence: ' + name)
    report = json.loads((DATA / 'REQUEST_ONLY_REPORT.json').read_text())
    scope = json.loads((DATA / 'EVIDENCE_SCOPE.json').read_text())
    assert report['schema'] == 'casepath.posthoc-request-only/1'
    assert report['primary_result_replaced'] is False and report['thresholds_applied'] is False
    macros, audit = [], []
    def emit(name, value, pointer, source='REQUEST_ONLY_REPORT.json', integer=False, signed=False):
        if value is None:
            raise ValueError('unavailable requested publication quantity: ' + pointer)
        rendered = str(int(value)) if integer else format(value, '+.3f' if signed else '.3f')
        macros.append('\\newcommand{\\' + name + '}{' + rendered + '}')
        audit.append({'macro': name, 'value': value, 'rendered': rendered, 'source': source,
                      'source_sha256': manifest[source], 'json_pointer': pointer})
    for split, tag in [('public_dev', 'Dev'), ('hidden_test', 'Hid'), ('all150', 'All')]:
        for arm, short, label in ARMS:
            a = report['splits'][split]['arms'][arm]
            base = f'/splits/{split}/arms/{arm}'
            emit(f'rq{tag}{short}N', a['request_count_eligible_cases'], base + '/request_count_eligible_cases', integer=True)
            for metric, abbreviation in METRICS:
                emit(f'rq{tag}{short}{abbreviation}', a['metrics'][metric]['value'], base + f'/metrics/{metric}/value')
            for key, suffix in [('correct', 'Correct'), ('requested', 'Requested'), ('missed', 'Missed'),
                                ('unnecessary', 'Extra'), ('required', 'Required'), ('conditional_requested', 'Conditional')]:
                emit(f'rq{tag}{short}{suffix}', a['raw_request_counts_where_available'][key], base + '/raw_request_counts_where_available/' + key, integer=True)
        for position, contrast in enumerate(report['splits'][split]['paired_contrasts']):
            atag = next(tag for a, tag, _ in ARMS if a == contrast['comparator'])
            metric = next(tag for m, tag in METRICS if m == contrast['metric'])
            for key, prefix in [('conventional_paired_difference', 'D'), ('conservative_paired_benefit', 'C')]:
                emit(f'rq{tag}{prefix}{atag}{metric}', contrast[key]['value'],
                     f'/splits/{split}/paired_contrasts/{position}/{key}/value', signed=True)
    for key, name in [('primary_native_evaluation_failures', 'nrArtifactFailures'),
                      ('primary_penalty_cells', 'nrPrimaryPenalties'),
                      ('request_only_observed_cells', 'nrRequestObserved'),
                      ('request_only_penalty_cells', 'nrRequestPenalties'),
                      ('registered_practical_targets_met', 'nrPrimaryMet'),
                      ('registered_practical_targets_total', 'nrPrimaryTotal'), ('native_symbols', 'nrNativeSymbols')]:
        emit(name, scope[key], '/' + key, 'EVIDENCE_SCOPE.json', integer=True)
    for key, name in [('all_history_outlay_usd', 'nrTotalCost'), ('attributed_final_study_usd', 'nrStudyCost')]:
        value = float(scope['cost'][key])
        rendered = f'{value:.2f}'
        macros.append('\\newcommand{\\' + name + '}{' + rendered + '}')
        audit.append({'macro': name, 'value': scope['cost'][key], 'rendered': rendered,
                      'source': 'EVIDENCE_SCOPE.json', 'source_sha256': manifest['EVIDENCE_SCOPE.json'],
                      'json_pointer': '/cost/' + key})
    (DOC / 'native_final_numbers.tex').write_text('% Generated from authenticated native150 evidence.\n' + '\n'.join(macros) + '\n')

    lines = [r'\begin{tabular}{lrrrrrr}', r'\toprule',
             r'& \multicolumn{2}{c}{Generated lists} & \multicolumn{2}{c}{Checklist $F_1\uparrow$} & \multicolumn{2}{c}{Unnecessary$\downarrow$} \\',
             r'\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}',
             r'Pipeline & Dev. & Prot. & Dev. & Prot. & Dev. & Prot. \\', r'\midrule']
    for position, (_, short, label) in enumerate(ARMS):
        if position == 5:
            lines += [r'\midrule', r'\multicolumn{7}{l}{\textit{Dependent controls: same recorded CasePath assessments}} \\']
        values = [f'\\rq{split}{short}{metric}' for metric in ('N', 'F', 'U') for split in ('Dev', 'Hid')]
        lines.append(label + ' & ' + ' & '.join(values) + r' \\')
    lines += [r'\bottomrule', r'\end{tabular}']
    (DOC / 'table_native_final.tex').write_text('\n'.join(lines) + '\n')

    tables = []
    for split, tag, title in [('public_dev', 'Dev', 'Development: 60 claims'),
                             ('hidden_test', 'Hid', 'Protected families: 90 claims'), ('all150', 'All', 'Combined: 150 claims')]:
        tables += [r'\begin{tabular}{lrrrrrr}', r'\toprule',
                   '\\multicolumn{7}{l}{\\textbf{' + title + r'}} \\',
                   r'Pipeline & Lists & Correct/req. & Missed & Cond. & Prec. & Recall \\', r'\midrule']
        for _, short, label in ARMS:
            values = [f'\\rq{tag}{short}N', f'\\rq{tag}{short}Correct/\\rq{tag}{short}Requested',
                      f'\\rq{tag}{short}Missed', f'\\rq{tag}{short}Conditional', f'\\rq{tag}{short}P', f'\\rq{tag}{short}R']
            tables.append(label + ' & ' + ' & '.join(values) + r' \\')
        tables += [r'\bottomrule', r'\end{tabular}', r'\par\medskip']
    (DOC / 'table_native_request_counts.tex').write_text('\n'.join(tables) + '\n')
    contrasts = [r'\begin{tabular}{llrr}', r'\toprule', r'Comparator & Endpoint & Conventional & Conservative \\', r'\midrule']
    for _, short, label in ARMS[1:5]:
        for metric, text in [('F', '$F_1$'), ('U', 'Unnecessary fraction')]:
            contrasts.append(label + ' & ' + text + f' & \\rqHidD{short}{metric} & \\rqHidC{short}{metric}' + r' \\')
    contrasts += [r'\bottomrule', r'\end{tabular}']
    (DOC / 'table_native_request_contrasts.tex').write_text('\n'.join(contrasts) + '\n')
    (HERE / 'NATIVE_FINAL_NUMERICAL_AUDIT.json').write_text(json.dumps({'schema': 'casepath.native-publication-audit/1', 'numbers': audit}, indent=2) + '\n')
    print(f'Generated {len(macros)} audited macros and three grouped tables.')


if __name__ == '__main__':
    main()
