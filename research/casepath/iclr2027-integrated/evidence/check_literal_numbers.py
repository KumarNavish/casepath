#!/usr/bin/env python3
"""Reject unexplained numeric literals in manuscript prose.

Equations, version identifiers, bibliography keys, figure dimensions and the
fixed 95% confidence level are not measurements. Result values use audited macros.
The submitted abstract is deliberately preserved verbatim and separately checked.
"""
import re
from pathlib import Path

root = Path(__file__).resolve().parent.parent
files = ['introduction.tex','method.tex','benchmark.tex','paired_results.tex',
         'native_study.tex','related.tex','release.tex','discussion.tex',
         'statements.tex','appendix_studya.tex','appendix_native.tex']
errors = []
for name in files:
    for line_no, line in enumerate((root/name).read_text().splitlines(), 1):
        if line.lstrip().startswith('%') or re.search(r'\\(?:includegraphics|setlength)\b', line):
            continue
        text = re.sub(r'\\(?:cite[pt]?|ref|label|eqref|input|path|texttt|url)\{[^}]*\}', '', line)
        text = re.sub(r'\\[a-zA-Z]+', '', text)
        nums = re.findall(r'(?<![A-Za-z_\\])\d+(?:[.,]\d+)*(?:\\%|%)?', text)
        nums = [n for n in nums if n not in {'1','2','3','9'}]
        if nums == ['95\\%'] and 'interval' in line + (root/name).read_text():
            continue
        if nums == ['0'] and 'temperature $0$' in line:
            continue
        if nums == ['1,1'] and 'b_m' in line:
            continue
        if nums:
            errors.append(f'{name}:{line_no}: {nums}')
print('\n'.join(errors) if errors else 'No unexplained numeric literals; measured quantities use audited macros.')
raise SystemExit(bool(errors))
