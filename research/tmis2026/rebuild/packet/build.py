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
FIG_NOTES = {
    1: ("Measured: page miniatures, the two sentences, the 27 squares per claim and their states, the question circles "
        "(attachment formal, from required\\_when). Formal: rails linking the same need; ink rail and frame on d15. "
        "Not yet measured: no element.",
        "b, one page and one fused strip: it shows a computed diff, not the two stored records; it draws one file for "
        "two and drops the questions."),
    2: ("Measured: sentences and words, quotation underlines, reading marks, ticks (recomputed by substring), the "
        "fact\u2019s value, the checklist line. Formal: agreement bracket (team.py rule, measured inputs), diamond node, "
        "outgoing edge. Schematic: horizontal positions. Not yet measured: no element.",
        "a, one lane, the open sentence alone: no partner; amber can\u2019t be read as a change without the stated lane."),
    3: ("Formal: follows from the definitions, computed by the product\u2019s own evaluator, on a real instance. "
        "Measured: all three stored readings answer open, quoting the sentence. Schematic simplification: a\\_instruction "
        "contracted. Not yet measured: no element.",
        "b, the fragment once beside a 2\u2009\u00d7\u20093 matrix: the mechanism (branch walked, rejoin) is not visible "
        "per reading; it hides the cause."),
    4: ("Measured: every mark. Formal: grouping into 5\u2009\u00d7\u200920 grids and largest-remainder rounding. "
        "Not yet measured: free-text questions of the other designs (no registered scorer).",
        "b, aligned error bars: three different x-scales make 3 settled errors look like 30 open ones, and the right "
        "share disappears from view."),
    5: ("Measured: ink levels (Study 3 sealed tenancy). Not yet measured: the dashed regions (planned ranges of the "
        "registered test).",
        "a, tercile lines: a steep \u201clength effect\u201d that is the denied-event claims."),
    6: ("Measured (left): stored replay, changed and collateral lines, 0 model calls. Formal (right): the prompt reads "
        "every file again, 56 calls. Not yet measured: the prompt\u2019s changed lines (hatched frame).",
        "b, a before\u2192after transition table: loses which file and which document changed, and the graph."),
    7: ("Measured: all marks. Not yet measured: ten runs (Study 4).",
        "b, aligned rows: auto-limited axes exaggerate small gaps; error and cost no longer read together."),
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
    # final "The reader should see that" sentence (the contract's own, last occurrence)
    hits = [m for m in re.finditer(r"(\*\*)?The reader should see that(\*\*)?", t)]
    start = hits[-1].start()
    para = t[start:].split("\n\n")[0]
    sentence = " ".join(l.strip() for l in para.splitlines()).replace("**", "")
    # final caption: last heading containing "Caption", text up to the next blank line
    caps = [m for m in re.finditer(r"^#+ .*Caption.*$", t, re.M)]
    body = t[caps[-1].end():].lstrip("\n").split("\n\n")[0]
    caption = " ".join(l.strip() for l in body.splitlines())
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
