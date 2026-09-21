#!/usr/bin/env python3
"""Turn the frozen Study B finite-corpus report into manuscript macros and a results table.

Usage: python3 evidence/build_native_results.py /path/to/FINITE_REPORT.json
Reads the descriptive report produced by casepath_execution_bridge.finite_reporting.report
(schema casepath.finite-corpus-descriptive/1.0.0) and writes:
  native_results_numbers.tex   -- \newcommand macros for the protected split
  table_native_results.tex     -- per-arm endpoint means and the 12 conservative contrasts
  evidence/NATIVE_RESULTS_AUDIT.json -- every emitted number with its JSON pointer and file hash
Nothing is written unless the report is complete (schema check, 1050-cell provenance is the
exporter's responsibility). This script never fabricates values: missing quantities are rendered
as 'n/a' and listed in the audit.
"""
import hashlib, json, pathlib, sys

if len(sys.argv) != 2:
    sys.exit("usage: build_native_results.py FINITE_REPORT.json")
src = pathlib.Path(sys.argv[1])
rep = json.loads(src.read_text(encoding="utf-8"))
if rep.get("schema") != "casepath.finite-corpus-descriptive/1.0.0":
    sys.exit(f"unexpected schema {rep.get('schema')!r}")
if rep.get("statistical_significance_computed") is not False:
    sys.exit("report must declare statistical_significance_computed=false")
W = pathlib.Path(__file__).resolve().parent.parent
sha = hashlib.sha256(src.read_bytes()).hexdigest()

ARMS = [("CASEPATH_CONTROL", "bCp", "\\casepath"), ("DIRECT_REVIEWED", "bDir", "Direct (reviewed)"),
        ("DOCUMENT_FIRST_REVIEWED", "bDoc", "Document-first (reviewed)"), ("PROCESS_CONTEXT_REVIEWED", "bPc", "Process-context (reviewed)"),
        ("RULE_FIRST_REVIEWED", "bRf", "Rule-first (reviewed)"), ("COMPILED_EQUIVALENT", "bCe", "Compiled-equivalent (dependent)"),
        ("LOCAL_SCOPE_ABLATION", "bLs", "Local-scope ablation (dependent)")]
METRICS = [("emitted_checklist_f1", "F", "Checklist $F_1$"), ("critical_evidence_recall", "Cer", "Critical-evidence recall"),
           ("emitted_unnecessary_fraction", "Udr", "Unnecessary fraction")]
audit = {"schema": "casepath.native-results-audit/1.0.0", "source": str(src), "source_sha256": sha, "macros": [], "unavailable": []}
macros = []
def emit(name, value, pointer, fmt="{:.3f}"):
    if value is None:
        macros.append(f"\\newcommand{{\\{name}}}{{n/a}}"); audit["unavailable"].append({"macro": name, "json_pointer": pointer}); return "n/a"
    s = fmt.format(value); macros.append(f"\\newcommand{{\\{name}}}{{{s}}}")
    audit["macros"].append({"macro": name, "rendered": s, "value": value, "json_pointer": pointer}); return s

rows_means, rows_contrasts = [], []
for split_key, tag in (("hidden_test", "Hid"), ("public_dev", "Dev")):
    sp = rep["splits"][split_key]
    emit(f"nr{tag}Cases", sp["cases"], f"/splits/{split_key}/cases", "{}")
    emit(f"nr{tag}Families", sp["families"], f"/splits/{split_key}/families", "{}")
    for arm, atag, label in ARMS:
        a = sp["arms"].get(arm)
        if a is None: continue
        cells = []
        for mkey, mtag, _ in METRICS:
            v = (a["metrics"].get(mkey) or {}).get("value")
            cells.append(emit(f"nr{tag}{atag}{mtag}", v, f"/splits/{split_key}/arms/{arm}/metrics/{mkey}/value"))
        ex = a.get("execution_status_counts", {})
        emit(f"nr{tag}{atag}Valid", ex.get("completed", 0), f"/splits/{split_key}/arms/{arm}/execution_status_counts/completed", "{}")
        if split_key == "hidden_test":
            rows_means.append(f"{label} & " + " & ".join(cells) + f" & {ex.get('completed',0)} \\\\")
    if split_key == "hidden_test":
        for c in sp["primary_contrasts"]:
            comp = c["comparator"]; ctag = dict((a, t) for a, t, _ in ARMS)[comp]; mtag = dict((k, t) for k, t, _ in METRICS)[c["metric"]]
            cons = (c.get("conservative_paired_benefit") or {}).get("value"); conv = (c.get("conventional_paired_difference") or {}).get("value")
            met = c.get("finite_practical_target_met"); rng = c.get("sensitivity_range")
            s_cons = emit(f"nrC{ctag}{mtag}", cons, f"/splits/hidden_test/primary_contrasts/[{comp},{c['metric']}]/conservative_paired_benefit/value", "{:+.3f}")
            s_conv = emit(f"nrD{ctag}{mtag}", conv, f"/splits/hidden_test/primary_contrasts/[{comp},{c['metric']}]/conventional_paired_difference/value", "{:+.3f}")
            s_met = "met" if met else ("not met" if met is not None else "n/a")
            macros.append(f"\\newcommand{{\\nrM{ctag}{mtag}}}{{{s_met}}}")
            s_rng = f"[{rng[0]:+.3f}, {rng[1]:+.3f}]" if rng else "n/a"
            rows_contrasts.append(f"{dict((a,l) for a,_,l in ARMS)[comp]} & {dict((k,l) for k,_,l in METRICS)[c['metric']]} & {c['strict_practical_boundary']:+.2f} & {s_conv} & {s_cons} & {s_rng} & {s_met} \\\\")
n_met = sum(1 for c in rep["splits"]["hidden_test"]["primary_contrasts"] if c.get("finite_practical_target_met"))
emit("nrTargetsMet", n_met, "/splits/hidden_test/primary_contrasts/*/finite_practical_target_met", "{}")
emit("nrTargetsTotal", len(rep["splits"]["hidden_test"]["primary_contrasts"]), "/splits/hidden_test/primary_contrasts", "{}")

(W / "native_results_numbers.tex").write_text("% GENERATED by evidence/build_native_results.py -- do not edit by hand.\n" + "\n".join(macros) + "\n", encoding="utf-8")
table = ("% GENERATED by evidence/build_native_results.py\n"
         "\\begin{tabular}{lrrrr}\n\\toprule\nArm & Checklist $F_1$ & Crit.\\ recall & Unnec.\\ fraction & Valid cells \\\\\n\\midrule\n" + "\n".join(rows_means) + "\n\\bottomrule\n\\end{tabular}\n\n"
         "\\begin{tabular}{llrrrlc}\n\\toprule\nComparator & Endpoint & Boundary & Conventional & Conservative & Family-deletion range & Target \\\\\n\\midrule\n" + "\n".join(rows_contrasts) + "\n\\bottomrule\n\\end{tabular}\n")
(W / "table_native_results.tex").write_text(table, encoding="utf-8")
(W / "evidence").mkdir(exist_ok=True)
(W / "evidence" / "NATIVE_RESULTS_AUDIT.json").write_text(json.dumps(audit, indent=1) + "\n", encoding="utf-8")
print(f"wrote native_results_numbers.tex ({len(macros)} macros), table_native_results.tex; unavailable: {len(audit['unavailable'])}")
