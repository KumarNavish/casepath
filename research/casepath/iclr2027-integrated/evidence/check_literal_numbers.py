#!/usr/bin/env python3
"""List numeric literals in main-text sections that are not produced by number macros.
Structural numbers (equation indices, section refs, widths) are filtered; the rest are printed for review."""
import re,sys,pathlib
W=pathlib.Path(__file__).resolve().parent.parent
files=['introduction.tex','method.tex','benchmark.tex','paired_results.tex','native_study.tex','related.tex','release.tex','discussion.tex','statements.tex','appendix_studya.tex','appendix_native.tex']
skip=re.compile(r'\\(includegraphics|setlength|tabcolsep|cite[pt]?|ref|label|eqref|input|path|texttt|cmidrule)\b')
for f in files:
    for ln,line in enumerate(open(W/f,encoding='utf-8'),1):
        s=line
        if line.lstrip().startswith('%'): continue
        s=re.sub(r'\\[A-Za-z]+\{[^}]*\}','',s) if skip.search(s) else s
        s=re.sub(r'\\[a-zA-Z]+','',s)  # drop macro names
        nums=re.findall(r'(?<![A-Za-z_\\])\d+(?:[.,]\d+)*(?:\\%|%)?',s)
        nums=[n for n in nums if n not in ('1','2','3','9')]
        if nums: print(f"{f}:{ln}: {nums} :: {line.strip()[:110]}")
