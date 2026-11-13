#!/usr/bin/env python3
"""Assemble the gate-1 packet: CLAIM_SHEET.md, seven figures, COSTED_PLAN.md -> packet.tex.

Sentences and captions are taken from each CONTRACT.md by exact extraction (no rewording).
Status and rejected-construction lines are condensed by hand from CONTRACT.md (FIG_NOTES below).
"""
import re
from pathlib import Path

LANDSCAPE = False
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

TITLES = ["One changed sentence", "The journey of one sentence", 'Why \u201copen\u201d needs its own value',
          "The fate of 100 open facts", "As cases get real", "A rule changes", "The price"]

# Hand-condensed from each CONTRACT.md (element status / status lines; the rejected construction).
# Number fixes where the contract sentence and the latest caption disagree and the data JSON confirms the caption.
# f7: core cost / cost-efficient prompt that may hold = 0.0029608 / 0.00067164 = 4.41 (f7_data.json).
SENTENCE_FIXES = {}  # f7 fix retired: the planner rewrote the sentence

FIG_NOTES = {
    1: ("Measured: the two sentences and their page marks, the 27 marks per claim and their states, the question dots "
        "(attachment formal, from required\\_when), the amber underline on the words quoted as open. Formal: the frame "
        "on d15. Not yet measured: no element.",
        "b, one page and one fused strip: it shows a computed diff, not the two stored records; it draws one file for "
        "two and drops the questions."),
    2: ("Measured: sentences and words, quotation underlines, reading marks, ticks (recomputed by substring), the "
        "fact’s value, the checklist line. Formal: agreement bracket (team.py rule, measured inputs), diamond node, "
        "outgoing edge. Schematic: horizontal positions. Not yet measured: no element.",
        "a, one lane, the open sentence alone: no partner; amber can’t be read as a change without the stated lane."),
    3: ("Formal: follows from the definitions, computed by the product’s own evaluator, on a real instance. "
        "Measured: all three stored readings answer open, quoting the sentence. Schematic simplification: a\\_instruction "
        "contracted. Not yet measured: no element.",
        "b, the fragment once beside a 2 × 3 matrix: the mechanism (branch walked, rejoin) is not visible "
        "per reading; it hides the cause."),
    4: ("Measured: every mark. Formal: grouping into 5 × 20 blocks and largest-remainder rounding. "
        "The frontier CasePath and prompt rows rest on one run. Not yet measured: no element.",
        "b, continuous bars: loses the line as unit, erases slivers."),
    5: ("two measured points per panel (Study 3); the arrows are the registered prediction, not data. This figure has no "
        "content until Study 4 runs.",
        "b, dots alone: the hypothesis then lives only in the caption and the panels look like a finished result at one point."),
    6: ("Measured: stored replay, the changed lines, 0 model calls. Formal: the prompt reads every file again, 56 calls. "
        "Not yet measured: the prompt’s changed lines (dashed frame).",
        "b, a before→after transition table: loses which file and which document changed, and the graph."),
    7: ("Measured: all marks (cost from ledgers; errors and repeats from three stored runs). Not yet measured: ten runs "
        "(Study 4).",
        "b, three stored checklists of the median file as strips: identical for both designs, true for the median, but it "
        "hides the 26 and 40 claims that change."),
}


def esc(s):
    rep = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
           "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(rep.get(c, c) for c in s)


def inline(s):
    """Markdown inline -> LaTeX: `code`, **bold**, *italic*, quotes."""
    out, i = [], 0
    for m in re.finditer(r"`([^`]+)`", s):
        out.append(("t", s[i:m.start()]))
        out.append(("c", m.group(1)))
        i = m.end()
    out.append(("t", s[i:]))
    res = []
    for kind, txt in out:
        if kind == "c":
            res.append(r"\code{" + esc(txt).replace("/", r"/\allowbreak{}").replace(r"\_", r"\_\allowbreak{}") + "}")
            continue
        t = esc(txt)
        t = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", t)
        t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\\emph{\1}", t)
        t = re.sub(r'"(\S)', "\u201c\\1", t)
        t = t.replace('"', "\u201d")
        res.append(t)
    return "".join(res)


def md_to_tex(md, table_spec):
    lines = md.splitlines()
    out, i, para = [], 0, []
    list_env = None

    def flush():
        nonlocal para
        if para:
            out.append(inline(" ".join(para)) + "\n")
            para = []

    def close_list():
        nonlocal list_env
        if list_env:
            out.append(r"\end{%s}" % list_env)
            list_env = None

    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            flush(); i += 1; continue
        if ln.startswith("# "):
            flush(); close_list()
            out.append(r"\doctitle{%s}" % inline(ln[2:])); i += 1; continue
        if ln.startswith("## "):
            flush(); close_list()
            out.append(r"\sect{%s}" % inline(ln[3:])); i += 1; continue
        if ln.startswith("|"):
            flush(); close_list()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"-+", c) for c in cells):
                    rows.append(cells)
                i += 1
            spec = table_spec(rows[0])
            out.append(r"\begin{tabularx}{\linewidth}{%s}\toprule" % spec)
            out.append(" & ".join(r"\textbf{%s}" % inline(c) for c in rows[0]) + r"\\\midrule")
            for r in rows[1:]:
                out.append(" & ".join(inline(c) for c in r) + r"\\")
            out.append(r"\bottomrule\end{tabularx}" + "\n")
            continue
        m = re.match(r"^(\d+)\. (.*)", ln) or re.match(r"^(-) (.*)", ln)
        if m:
            flush()
            env = "itemize" if m.group(1) == "-" else "enumerate"
            if list_env != env:
                close_list(); out.append(r"\begin{%s}" % env); list_env = env
            item = [m.group(2)]
            i += 1
            while i < len(lines) and lines[i].startswith("  ") and lines[i].strip():
                item.append(lines[i].strip()); i += 1
            out.append(r"\item " + inline(" ".join(item)))
            continue
        close_list()
        para.append(ln.strip()); i += 1
    flush(); close_list()
    return "\n".join(out)


def contract_parts(n):
    t = (ROOT / f"figures/f{n}/CONTRACT.md").read_text()
    # final "The reader should see that" sentence (first occurrence; any "Earlier wording" note below it is skipped)
    hits = [m for m in re.finditer(r"(\*\*)?The reader should see that(\*\*)?", t)]
    para = t[hits[0].start():].split("\n\n")[0]
    sentence = " ".join(l.strip() for l in para.splitlines()).replace("**", "")
    # latest caption: a "Caption" heading or a "- Caption (...):" bullet, whichever comes last
    cands = []
    for m in re.finditer(r"^#+ .*Caption.*$", t, re.M):
        body = t[m.end():].lstrip("\n").split("\n\n")[0]
        cands.append((m.start(), body))
    for m in re.finditer(r"^- Caption \([^)]*\): ", t, re.M):
        rest = t[m.end():]
        stop = re.search(r"\n(- |\n)", rest)
        cands.append((m.start(), rest[:stop.start()] if stop else rest))
    caption = " ".join(l.strip() for l in max(cands)[1].splitlines())
    for old, new in SENTENCE_FIXES.get(n, []):
        assert sentence.count(old) == 1, (n, old)
        sentence = sentence.replace(old, new)
    return sentence, caption


def claim_spec(head):
    # # | Claim | Figure | Exists today | Must be produced
    return (r">{\raggedright\arraybackslash}p{0.8em}"
            r">{\hsize=0.95\hsize\raggedright\arraybackslash}X"
            r">{\raggedright\arraybackslash}p{4.2em}"
            r">{\hsize=1.25\hsize\raggedright\arraybackslash}X"
            r">{\hsize=0.8\hsize\raggedright\arraybackslash}X")


def plan_spec(head):
    if head[0] == "#":  # fixes table
        return (r">{\raggedright\arraybackslash}p{0.8em}"
                r">{\hsize=1.3\hsize\raggedright\arraybackslash}X"
                r">{\hsize=0.8\hsize\raggedright\arraybackslash}X"
                r">{\hsize=0.9\hsize\raggedright\arraybackslash}X")
    return (r">{\raggedright\arraybackslash}p{0.42\linewidth}"
            r">{\raggedright\arraybackslash}X>{\raggedright\arraybackslash}X>{\raggedright\arraybackslash}X")


PRE = r"""\documentclass[10pt]{article}
\usepackage[a4paper,margin=18mm,top=20mm,bottom=18mm,headsep=5mm,footskip=8mm]{geometry}
\usepackage{fontspec}
\setmainfont{Carlito}
\setmonofont{DejaVu Sans Mono}[Scale=0.85]
\usepackage{xcolor}
\definecolor{ink}{HTML}{1F2A44}
\usepackage{graphicx,tabularx,booktabs,array,enumitem,fancyhdr,lastpage}
\usepackage{pdflscape}
\newenvironment{claimpage}{}{}
\color{ink}
\pagestyle{fancy}\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\fancyhead[L]{\footnotesize\color{ink}CasePath paper rebuild: gate 1 (13 November 2026)}
\fancyfoot[C]{\footnotesize\color{ink}\thepage\ of \pageref*{LastPage}}
\setlength{\parindent}{0pt}\setlength{\parskip}{3pt}
\newcommand{\code}[1]{\texttt{#1}}
\newcommand{\doctitle}[1]{{\large\bfseries #1\par}\vspace{2pt}}
\usepackage{needspace}
\newcommand{\sect}[1]{\needspace{5\baselineskip}\vspace{3pt}{\bfseries #1\par}\vspace{1pt}}
\setlist{nosep,leftmargin=1.4em}
\setlength{\aboverulesep}{1pt}\setlength{\belowrulesep}{1pt}
\usepackage[hidelinks]{hyperref}
\begin{document}
"""


def main():
    claim = md_to_tex((ROOT / "CLAIM_SHEET.md").read_text(), claim_spec)
    plan = md_to_tex((ROOT / "COSTED_PLAN.md").read_text(), plan_spec)
    parts = [PRE]
    # Page 1: claim sheet (landscape page, compact type)
    parts.append(r"\newgeometry{margin=14mm,top=17mm,bottom=15mm,headsep=4mm,footskip=7mm}\begin{CLAIMENV}\fontsize{9}{10.8}\selectfont\setlength{\tabcolsep}{3.5pt}\renewcommand{\arraystretch}{1.0}\renewcommand{\sect}[1]{\vspace{3pt}{\bfseries #1\par}\vspace{1pt}}"
                 r"\setlength{\parskip}{2pt}")
    parts.append(claim)
    parts.append(r"\end{CLAIMENV}\clearpage\restoregeometry")
    # Figures
    for n in range(1, 8):
        sentence, caption = contract_parts(n)
        status, rejected = FIG_NOTES[n]
        parts.append(r"""{\large\bfseries Figure %d. %s\par}\vspace{6pt}
{\small %s\par}\vspace{8pt}
\begin{center}\includegraphics[width=5.5in]{../figures/f%d/f%d.pdf}\end{center}
\vspace{2pt}\begin{center}\begin{minipage}{5.5in}
%s\par\vspace{8pt}
{\footnotesize \textbf{Status:} %s\par\vspace{3pt}
\textbf{Rejected construction:} %s\par}
\end{minipage}\end{center}
\clearpage""" % (n, inline(TITLES[n - 1]), inline(sentence), n, n, inline(caption), status, inline(rejected).replace(r"\textbackslash{}", "\\")))
    parts.append(r"{\fontsize{8.8}{10.6}\selectfont\setlength{\tabcolsep}{3.5pt}")
    parts.append(plan)
    parts.append(r"}")
    parts.append(r"\end{document}")
    (HERE / "packet.tex").write_text("\n".join(parts).replace("CLAIMENV", "landscape" if LANDSCAPE else "claimpage"))


if __name__ == "__main__":
    main()
