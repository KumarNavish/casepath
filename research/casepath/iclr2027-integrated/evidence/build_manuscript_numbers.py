#!/usr/bin/env python3
"""Generate number macros, result tables and the numerical audit from preserved evidence.

Every number that appears in the manuscript through a macro is traced here to an
evidence file, a JSON pointer (or an explicit derivation) and the file's SHA-256.
Run:  python3 evidence/build_manuscript_numbers.py
"""
import hashlib, json, pathlib, sys

E = pathlib.Path(__file__).resolve().parent
W = E.parent

def load(name):
    return json.load(open(E / name, encoding="utf-8"))

def sha(name):
    return hashlib.sha256(open(E / name, "rb").read()).hexdigest()

R = load("PAIRED_V5_REPRODUCED_RESULT.json")
PF = load("SHORTCUT_PREFLIGHT_V3.json")
RC = load("PAIRED_V5_RECEIPT_ACCOUNTING.json")
PA = load("PAIRED_V5_REPRODUCED_PARITY.json")
HA = load("HISTORICAL_AUDIT.json")
SF = load("PUBLICATION_STATIC_FACTS.json")
EX = load("studyB_execution_status_695.json")

SHAS = {n: sha(n) for n in ["PAIRED_V5_REPRODUCED_RESULT.json", "SHORTCUT_PREFLIGHT_V3.json",
        "PAIRED_V5_RECEIPT_ACCOUNTING.json", "PAIRED_V5_REPRODUCED_PARITY.json",
        "HISTORICAL_AUDIT.json", "PUBLICATION_STATIC_FACTS.json", "studyB_execution_status_695.json"]}

macros = []
def m(name, value, rendered, file, pointer, note=""):
    macros.append({"macro": name, "rendered": rendered, "value": value, "evidence_file": file,
                   "json_pointer": pointer, "derivation": note})

f3 = lambda v: f"{v:.3f}"
f2 = lambda v: f"{v:.2f}"
f1 = lambda v: f"{v:.1f}"
pct = lambda v: f"{100*v:.1f}"
RF = "PAIRED_V5_REPRODUCED_RESULT.json"

ARMS = {"cp": "b5_process_compiled", "dir": "b1_direct", "gc": "b3_representation_then_list", "ef": "b6_evidence_first"}
LABEL = {"cp": "\\casepath", "dir": "Direct", "gc": "Graph as context", "ef": "Evidence-first"}
gold = R["scores"]["b5_process_compiled"]["gold_atoms"]
pairs = R["scores"]["b5_process_compiled"]["pairs"]
m("nGoldAtoms", gold, str(gold), RF, "/scores/b5_process_compiled/gold_atoms")
m("nPairsHid", pairs, str(pairs), RF, "/scores/b5_process_compiled/pairs")

for tag, arm in ARMS.items():
    s = R["scores"][arm]; p = f"/scores/{arm}/"
    m(tag + "Prec", s["precision"], f3(s["precision"]), RF, p + "precision")
    m(tag + "Rec", s["recall"], f3(s["recall"]), RF, p + "recall")
    m(tag + "F", s["micro_f1"], f3(s["micro_f1"]), RF, p + "micro_f1")
    m(tag + "Exact", s["exact_rate"], f3(s["exact_rate"]), RF, p + "exact_rate")
    en = round(s["exact_rate"] * pairs)
    m(tag + "ExactN", en, str(en), RF, p + "exact_rate", f"round(exact_rate*{pairs})")
    m(tag + "Pred", s["predicted_atoms"], str(s["predicted_atoms"]), RF, p + "predicted_atoms")
    m(tag + "TP", s["tp"], str(s["tp"]), RF, p + "tp")
    m(tag + "Spur", s["spurious_atoms"], str(s["spurious_atoms"]), RF, p + "spurious_atoms")
    m(tag + "Miss", s["missed_atoms"], str(s["missed_atoms"]), RF, p + "missed_atoms")
    m(tag + "Ratio", s["predicted_atoms"] / gold, f2(s["predicted_atoms"] / gold), RF, p + "predicted_atoms", f"predicted_atoms/{gold}")
    m(tag + "Macro", s["family_macro_pair_f1"], f3(s["family_macro_pair_f1"]), RF, p + "family_macro_pair_f1")
    ci = R["cluster_bootstrap"]["arms"][arm]
    m(tag + "CIlo", ci["low"], f3(ci["low"]), RF, f"/cluster_bootstrap/arms/{arm}/low")
    m(tag + "CIhi", ci["high"], f3(ci["high"]), RF, f"/cluster_bootstrap/arms/{arm}/high")

cps = R["scores"]["b5_process_compiled"]["spurious_atoms"]
for tag in ("dir", "gc", "ef"):
    arm = ARMS[tag]
    d = R["cluster_bootstrap"]["b5_minus"][arm]
    m("d" + tag.capitalize() + "Lo", d["low"], f"{d['low']:+.3f}", RF, f"/cluster_bootstrap/b5_minus/{arm}/low")
    m("d" + tag.capitalize() + "Hi", d["high"], f"{d['high']:+.3f}", RF, f"/cluster_bootstrap/b5_minus/{arm}/high")
    mg = R["b5_minus_comparator_micro_f1"][arm]
    m("m" + tag.capitalize(), mg, f"{mg:+.3f}", RF, f"/b5_minus_comparator_micro_f1/{arm}")
    fs = R["family_swap_tests"][arm]
    m("pHolm" + tag.capitalize(), fs["holm_adjusted_p"], f3(fs["holm_adjusted_p"]), RF, f"/family_swap_tests/{arm}/holm_adjusted_p")
    m("pRaw" + tag.capitalize(), fs["one_sided_p"], f3(fs["one_sided_p"]), RF, f"/family_swap_tests/{arm}/one_sided_p")
    sp = R["scores"][arm]["spurious_atoms"]
    m("red" + tag.capitalize(), (sp - cps) / sp, pct((sp - cps) / sp), RF, f"/scores/{arm}/spurious_atoms", f"({sp}-{cps})/{sp}")

wp = R["wrong_pairing"]
m("wpObs", wp["observed_micro_f1"], f3(wp["observed_micro_f1"]), RF, "/wrong_pairing/observed_micro_f1")
m("wpMax", wp["null_max"], f3(wp["null_max"]), RF, "/wrong_pairing/null_max")
m("wpNinetySevenFive", wp["null_95"][1], f3(wp["null_95"][1]), RF, "/wrong_pairing/null_95/1")
m("wpMean", wp["null_mean"], f3(wp["null_mean"]), RF, "/wrong_pairing/null_mean")
m("wpP", wp["p_ge_plus1"], f"{wp['p_ge_plus1']:.3e}".replace("e-04", "\\times10^{-4}"), RF, "/wrong_pairing/p_ge_plus1")
m("wpDraws", wp["random_draws"], f"{wp['random_draws']:,}", RF, "/wrong_pairing/random_draws")
m("wpShifts", len(wp["cyclic_shifts"]), str(len(wp["cyclic_shifts"])), RF, "/wrong_pairing/cyclic_shifts", "len")
m("wpEvaluated", len(wp["cyclic_shifts"]) + wp["random_draws"], f"{len(wp['cyclic_shifts']) + wp['random_draws']:,}", RF, "/wrong_pairing", "cyclic_shifts+random_draws")

cm = R["chain_metrics"]
m("chainAttributed", cm["attributed_predicted_atoms"], str(cm["attributed_predicted_atoms"]), RF, "/chain_metrics/attributed_predicted_atoms")
m("chainPredicted", cm["predicted_atoms"], str(cm["predicted_atoms"]), RF, "/chain_metrics/predicted_atoms")
m("chainCovered", cm["covered_gold_atoms"], str(cm["covered_gold_atoms"]), RF, "/chain_metrics/covered_gold_atoms")
m("chainCoverage", cm["gold_chain_coverage"], pct(cm["gold_chain_coverage"]), RF, "/chain_metrics/gold_chain_coverage")
m("bootDraws", R["cluster_bootstrap"]["draws"], f"{R['cluster_bootstrap']['draws']:,}", RF, "/cluster_bootstrap/draws")
m("bootSeed", R["cluster_bootstrap"]["seed"], str(R["cluster_bootstrap"]["seed"]), RF, "/cluster_bootstrap/seed")
m("swapAssignments", R["family_swap_tests"]["b1_direct"]["assignments"], str(R["family_swap_tests"]["b1_direct"]["assignments"]), RF, "/family_swap_tests/b1_direct/assignments")
m("ratioAll", R["predicted_to_gold_atom_ratio"], f2(R["predicted_to_gold_atom_ratio"]), RF, "/predicted_to_gold_atom_ratio")

PFF = "SHORTCUT_PREFLIGHT_V3.json"
m("pfNoInputMax", PF["max_held_out_no_input_micro_f1"], f1(PF["max_held_out_no_input_micro_f1"]), PFF, "/max_held_out_no_input_micro_f1")
m("pfSignatures", PF["distinct_acceptable_target_signatures"], str(PF["distinct_acceptable_target_signatures"]), PFF, "/distinct_acceptable_target_signatures")
m("pfEntropy", PF["target_signature_entropy_bits"], f2(PF["target_signature_entropy_bits"]), PFF, "/target_signature_entropy_bits")
m("nPairsAll", PF["pairs"], str(PF["pairs"]), PFF, "/pairs")
m("nUnitsAll", PF["units"], str(PF["units"]), PFF, "/units")
m("nConcepts", PF["scenarios"], str(PF["scenarios"]), PFF, "/scenarios")
m("pfUniverse", len(PF["signed_document_universe"]), str(len(PF["signed_document_universe"])), PFF, "/signed_document_universe", "len")

HF = "HISTORICAL_AUDIT.json"
si = HA["source_inventory"]; sp = HA["split"]
m("nPassages", si["passages"], str(si["passages"]), HF, "/source_inventory/passages")
m("nPropositions", si["propositions"], str(si["propositions"]), HF, "/source_inventory/propositions")
m("nRules", si["overlay_rules"], str(si["overlay_rules"]), HF, "/source_inventory/overlay_rules")
m("nGuards", si["overlay_guards"], str(si["overlay_guards"]), HF, "/source_inventory/overlay_guards")
m("nNonEvidentiary", si["non_evidentiary_classifications"], str(si["non_evidentiary_classifications"]), HF, "/source_inventory/non_evidentiary_classifications")
m("nCatalogue", si["catalogue_documents"], str(si["catalogue_documents"]), HF, "/source_inventory/catalogue_documents")
m("nPairsDev", sp["development_pairs"], str(sp["development_pairs"]), HF, "/split/development_pairs")
m("nUnitsDev", sp["development_units"], str(sp["development_units"]), HF, "/split/development_units")
m("nUnitsHid", sp["heldout_units"], str(sp["heldout_units"]), HF, "/split/heldout_units")

CF = "PAIRED_V5_RECEIPT_ACCOUNTING.json"
for tag, arm in ARMS.items():
    c = RC[arm]
    m(tag + "Calls", c["receipts"], str(c["receipts"]), CF, f"/{arm}/receipts")
    m(tag + "Cost", float(c["cost_usd"]), f"{float(c['cost_usd']):.2f}", CF, f"/{arm}/cost_usd")
    m(tag + "PromptTok", c["prompt_tokens"], f"{c['prompt_tokens']/1e6:.2f}M", CF, f"/{arm}/prompt_tokens", "tokens/1e6")
    m(tag + "ComplTok", c["completion_tokens"], f"{c['completion_tokens']/1e3:.1f}k", CF, f"/{arm}/completion_tokens", "tokens/1e3")
    m(tag + "MaxTok", c["max_tokens"], "/".join(f"{int(k):,}" for k in sorted(c["max_tokens"], key=int)), CF, f"/{arm}/max_tokens")
    m(tag + "Model", c["models"][0], c["models"][0].replace("_", "\\_"), CF, f"/{arm}/models/0")

PAF = "PAIRED_V5_REPRODUCED_PARITY.json"
m("parityUnits", PA["benchmark_units"], str(PA["benchmark_units"]), PAF, "/benchmark_units")
m("parityPairs", PA["benchmark_pairs"], str(PA["benchmark_pairs"]), PAF, "/benchmark_pairs")
parity_all = all(PA[k] for k in ("all_unit_documents_match", "all_unit_guard_states_match", "all_unit_next_actions_match", "all_pair_deltas_match"))
m("parityAllMatch", parity_all, "all" if parity_all else "not all", PAF, "/all_*_match", "conjunction of four flags")

SFF = "PUBLICATION_STATIC_FACTS.json"
sp = SF["splits"]
m("nbClaims", sp["combined"]["claims"], str(sp["combined"]["claims"]), SFF, "/splits/combined/claims")
m("nbFamilies", sp["combined"]["families"], str(sp["combined"]["families"]), SFF, "/splits/combined/families")
m("nbCells", sp["combined"]["scheduled_cells"], f"{sp['combined']['scheduled_cells']:,}", SFF, "/splits/combined/scheduled_cells")
m("nbLearnedCells", sp["combined"]["learned_cells"], str(sp["combined"]["learned_cells"]), SFF, "/splits/combined/learned_cells")
m("nbDependentCells", sp["combined"]["dependent_cells"], str(sp["combined"]["dependent_cells"]), SFF, "/splits/combined/dependent_cells")
m("nbDevClaims", sp["public_dev"]["claims"], str(sp["public_dev"]["claims"]), SFF, "/splits/public_dev/claims")
m("nbDevFamilies", sp["public_dev"]["families"], str(sp["public_dev"]["families"]), SFF, "/splits/public_dev/families")
m("nbDevCells", sp["public_dev"]["scheduled_cells"], str(sp["public_dev"]["scheduled_cells"]), SFF, "/splits/public_dev/scheduled_cells")
m("nbHidClaims", sp["hidden_test"]["claims"], str(sp["hidden_test"]["claims"]), SFF, "/splits/hidden_test/claims")
m("nbHidFamilies", sp["hidden_test"]["families"], str(sp["hidden_test"]["families"]), SFF, "/splits/hidden_test/families")
m("nbHidCells", sp["hidden_test"]["scheduled_cells"], str(sp["hidden_test"]["scheduled_cells"]), SFF, "/splits/hidden_test/scheduled_cells")
cfg = SF["configuration"]
m("nbTokens", cfg["case_output_tokens"], f"{cfg['case_output_tokens']:,}", SFF, "/configuration/case_output_tokens")
m("nbCallsPerCell", SF["learned_calls_per_cell"], str(SF["learned_calls_per_cell"]), SFF, "/learned_calls_per_cell")
m("nbModel", cfg["model"], cfg["model"].replace("_", "\\_"), SFF, "/configuration/model")
m("nbReasoning", cfg["reasoning_effort"], cfg["reasoning_effort"], SFF, "/configuration/reasoning_effort")
m("nbLearnedArms", len(SF["learned_arms"]), str(len(SF["learned_arms"])), SFF, "/learned_arms", "len")
m("nbDependentArms", len(SF["dependent_arms"]), str(len(SF["dependent_arms"])), SFF, "/dependent_arms", "len")

EXF = "studyB_execution_status_695.json"
m("nbRecorded", EX["snapshot_cells"], str(EX["snapshot_cells"]), EXF, "/snapshot_cells")
by = EX["by_split_arm"]
dev_total = sum(sum(v.values()) for k, v in by.items() if k.startswith("public_dev|"))
hid_total = sum(sum(v.values()) for k, v in by.items() if k.startswith("hidden_test|"))
m("nbDevRecorded", dev_total, str(dev_total), EXF, "/by_split_arm/public_dev|*", "sum of states")
m("nbHidRecorded", hid_total, str(hid_total), EXF, "/by_split_arm/hidden_test|*", "sum of states")
ARMB = {"CASEPATH_CONTROL": ("bCp", "\\casepath"), "DIRECT_REVIEWED": ("bDir", "Direct (reviewed)"),
        "DOCUMENT_FIRST_REVIEWED": ("bDoc", "Document-first (reviewed)"), "PROCESS_CONTEXT_REVIEWED": ("bPc", "Process-context (reviewed)"),
        "RULE_FIRST_REVIEWED": ("bRf", "Rule-first (reviewed)"), "COMPILED_EQUIVALENT": ("bCe", "Compiled-equivalent (dependent)"),
        "LOCAL_SCOPE_ABLATION": ("bLs", "Local-scope ablation (dependent)")}
tax = EX["failure_taxonomy_by_split_arm"]
for arm, (tag, label) in ARMB.items():
    d = by[f"public_dev|{arm}"]
    m(tag + "DevOk", d.get("completed", 0), str(d.get("completed", 0)), EXF, f"/by_split_arm/public_dev|{arm}/completed")
    m(tag + "DevFail", d.get("failed", 0), str(d.get("failed", 0)), EXF, f"/by_split_arm/public_dev|{arm}/failed")
    m(tag + "DevBlocked", d.get("blocked_dependency", 0), str(d.get("blocked_dependency", 0)), EXF, f"/by_split_arm/public_dev|{arm}/blocked_dependency")
    t = tax.get(f"public_dev|{arm}", {})
    m(tag + "DevEndpoint", t.get("unknown_relation_endpoint", 0), str(t.get("unknown_relation_endpoint", 0)), EXF, f"/failure_taxonomy_by_split_arm/public_dev|{arm}/unknown_relation_endpoint")
    m(tag + "DevTrunc", t.get("truncated_or_nonterminal", 0), str(t.get("truncated_or_nonterminal", 0)), EXF, f"/failure_taxonomy_by_split_arm/public_dev|{arm}/truncated_or_nonterminal")
    m(tag + "DevCodebook", t.get("invalid_codebook_index", 0), str(t.get("invalid_codebook_index", 0)), EXF, f"/failure_taxonomy_by_split_arm/public_dev|{arm}/invalid_codebook_index")
    m(tag + "DevPresence", t.get("contradictory_presence_state", 0), str(t.get("contradictory_presence_state", 0)), EXF, f"/failure_taxonomy_by_split_arm/public_dev|{arm}/contradictory_presence_state")


# ---- per-concept CasePath values used in prose ----
fam = R["scores"]["b5_process_compiled"]["family_pair_f1"]
m("cpFamScheduled", fam["PR_scheduled_valuable_1000"], f3(fam["PR_scheduled_valuable_1000"]), RF, "/scores/b5_process_compiled/family_pair_f1/PR_scheduled_valuable_1000")
m("cpFamSim", fam["PR_sim_card_stolen"], f3(fam["PR_sim_card_stolen"]), RF, "/scores/b5_process_compiled/family_pair_f1/PR_sim_card_stolen")
m("cpFamRepair", fam["PR_repair_over_500"], f3(fam["PR_repair_over_500"]), RF, "/scores/b5_process_compiled/family_pair_f1/PR_repair_over_500")
# ---- gate thresholds are encoded in the frozen gate names ----
m("gateMargin", 0.10, "0.10", RF, "/positive_claim_gates/margin_at_least_0_10_against_all", "threshold encoded in gate key")
m("gatePrec", 0.70, "0.70", RF, "/positive_claim_gates/delta_precision_at_least_0_70", "threshold encoded in gate key")
# ---- Study B practical boundaries from the frozen analysis contract ----
AC = load("ANALYSIS_CONTRACT.json"); ACF = "ANALYSIS_CONTRACT.json"; SHAS[ACF] = sha(ACF)
pc = {c["id"]: c for c in AC["endpoint_hierarchy"]["primary_practical_contrasts"]}
m("bndF", pc["F1__DIRECT_REVIEWED"]["practical_boundary"], f"{pc['F1__DIRECT_REVIEWED']['practical_boundary']:+.2f}", ACF, "/endpoint_hierarchy/primary_practical_contrasts/[F1__DIRECT_REVIEWED]/practical_boundary")
m("bndCer", pc["CER__DIRECT_REVIEWED"]["practical_boundary"], f"{pc['CER__DIRECT_REVIEWED']['practical_boundary']:+.2f}", ACF, "/endpoint_hierarchy/primary_practical_contrasts/[CER__DIRECT_REVIEWED]/practical_boundary")
m("bndUdr", pc["UDR__DIRECT_REVIEWED"]["practical_boundary"], f"{pc['UDR__DIRECT_REVIEWED']['practical_boundary']:+.2f}", ACF, "/endpoint_hierarchy/primary_practical_contrasts/[UDR__DIRECT_REVIEWED]/practical_boundary")
m("nbPrimaryContrasts", AC["endpoint_hierarchy"]["number_of_primary_practical_contrasts"], str(AC["endpoint_hierarchy"]["number_of_primary_practical_contrasts"]), ACF, "/endpoint_hierarchy/number_of_primary_practical_contrasts")
# ---- stage-specific completion limits from receipts ----
ef = RC["b6_evidence_first"]["max_tokens"]; cpm = RC["b5_process_compiled"]["max_tokens"]; dm = RC["b1_direct"]["max_tokens"]
m("efMaxTokExtract", max(int(k) for k in ef), f"{max(int(k) for k in ef):,}", CF, "/b6_evidence_first/max_tokens", "larger of the two stage limits")
m("efMaxTokPlan", min(int(k) for k in ef), f"{min(int(k) for k in ef):,}", CF, "/b6_evidence_first/max_tokens", "smaller of the two stage limits")
m("cpMaxTokGuard", int(list(cpm)[0]), f"{int(list(cpm)[0]):,}", CF, "/b5_process_compiled/max_tokens")
m("dirMaxTokCall", int(list(dm)[0]), f"{int(list(dm)[0]):,}", CF, "/b1_direct/max_tokens")
# ---- benchmark pair example quoted in the text ----
BP = load("BENCHMARK_V3_pair_theft-01-04.json"); BPF = "BENCHMARK_V3_pair_theft-01-04.json"; SHAS[BPF] = sha(BPF)
m("pairExampleFalse", BP["pair"]["changed_statement_false"], BP["pair"]["changed_statement_false"].rstrip("."), BPF, "/pair/changed_statement_false", "trailing period stripped")
m("pairExampleTrue", BP["pair"]["changed_statement_true"], BP["pair"]["changed_statement_true"].rstrip("."), BPF, "/pair/changed_statement_true", "trailing period stripped")

# ---------- write numbers.tex ----------
lines = ["% GENERATED by evidence/build_manuscript_numbers.py -- do not edit by hand."]
for x in macros:
    lines.append(f"\\newcommand{{\\{x['macro']}}}{{{x['rendered']}}}")
(W / "numbers.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

# ---------- tables ----------
def wr(name, text):
    (W / name).write_text("% GENERATED by evidence/build_manuscript_numbers.py\n" + text, encoding="utf-8")

rows = []
for tag in ("dir", "gc", "ef", "cp"):
    s = R["scores"][ARMS[tag]]
    b = (lambda v: f"\\textbf{{{v}}}") if tag == "cp" else (lambda v: v)
    rows.append(f"{LABEL[tag]} & {b(f3(s['precision']))} & {f3(s['recall'])} & {b(f3(s['micro_f1']))} & {b(f3(s['exact_rate']))} & {s['predicted_atoms']}/{gold} & {b(str(s['spurious_atoms']))} & {s['missed_atoms']} \\\\")
wr("table_main_results.tex", "\\begin{tabular}{lrrrrrrr}\n\\toprule\nMethod & Prec. & Recall & $F_1$ & Exact & Pred./Gold & Spurious & Missed \\\\\n\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n")

GATES = [("margin_at_least_0_10_against_all", "$F_1$ margin $\\geq 0.10$ against every comparator"),
         ("holm_p_at_most_0_05_against_all", "Holm-adjusted family-swap $p\\leq 0.05$ against every comparator"),
         ("delta_precision_at_least_0_70", "Signed-change precision $\\geq 0.70$"),
         ("predicted_gold_ratio_in_range", "Predicted/gold change ratio in $[0.75,1.50]$"),
         ("predicted_chain_attribution_at_least_0_90", "Predicted changes attributed to a changed guard $\\geq 0.90$"),
         ("gold_chain_coverage_at_least_0_80", "Reference changes reachable through a source chain $\\geq 0.80$"),
         ("correct_pairing_above_null_97_5", "Correct pairing above the wrong-pairing 97.5th percentile"),
         ("no_orphan_insertion_path", "No requested document without a source chain")]
g = R["positive_claim_gates"]
grows = [f"{lab} & {'pass' if g[k] else 'fail'} \\\\" for k, lab in GATES]
wr("table_claim_gates.tex", "\\begin{tabular}{p{0.80\\linewidth}c}\n\\toprule\nPreregistered held-out gate & Result \\\\\n\\midrule\n" + "\n".join(grows) + "\n\\bottomrule\n\\end{tabular}\n")

FAM = [("PR_bicycle_claimed", "Bicycle among stolen items"), ("PR_declined", "Insurer declination"),
       ("PR_expert_procedure_requested", "Formal expert procedure"), ("PR_goods_recovered", "Recovery of stolen goods"),
       ("PR_nachfrist_set", "Written demand with period (Nachfrist)"), ("PR_repair_over_500", "Repair above consent threshold"),
       ("PR_scheduled_valuable_1000", "Scheduled valuable"), ("PR_sim_card_stolen", "SIM-card theft"),
       ("PR_third_party_causer", "Identifiable third-party causer")]
frows = []
for fid, lab in FAM:
    vals = [R["scores"][ARMS[t]]["family_pair_f1"][fid] for t in ("dir", "gc", "ef", "cp")]
    frows.append(f"{lab} & " + " & ".join(f3(v) for v in vals) + " \\\\")
wr("table_family_results.tex", "\\begin{tabular}{lcccc}\n\\toprule\nBranch concept & Direct & Graph ctx. & Evid.-first & \\casepath \\\\\n\\midrule\n" + "\n".join(frows) + "\n\\bottomrule\n\\end{tabular}\n")

crow = []
for tag in ("dir", "gc", "ef", "cp"):
    c = RC[ARMS[tag]]
    crow.append(f"{LABEL[tag]} & {c['receipts']} & {c['prompt_tokens']:,} & {c['completion_tokens']:,} & {'/'.join(f'{int(k):,}' for k in sorted(c['max_tokens'], key=int))} & {float(c['cost_usd']):.2f} \\\\")
wr("table_costs.tex", "\\begin{tabular}{lrrrrr}\n\\toprule\nArm & Calls & Prompt tokens & Completion tokens & Max completion & Cost (USD) \\\\\n\\midrule\n" + "\n".join(crow) + "\n\\bottomrule\n\\end{tabular}\n")

nrows = []
for arm, (tag, label) in ARMB.items():
    d = by[f"public_dev|{arm}"]; t = tax.get(f"public_dev|{arm}", {})
    other = d.get("failed", 0) - t.get("unknown_relation_endpoint", 0) - t.get("truncated_or_nonterminal", 0) - t.get("invalid_codebook_index", 0) - t.get("contradictory_presence_state", 0)
    nrows.append(f"{label} & {d.get('completed',0)} & {d.get('failed',0)} & {d.get('blocked_dependency',0)} & {t.get('unknown_relation_endpoint',0)} & {t.get('truncated_or_nonterminal',0)} & {t.get('invalid_codebook_index',0)} & {t.get('contradictory_presence_state',0)} & {other} \\\\")
wr("table_native_execution.tex", "\\begin{tabular}{lrrrrrrrr}\n\\toprule\n & \\multicolumn{3}{c}{Cells of 60} & \\multicolumn{5}{c}{Failure class} \\\\\n\\cmidrule(lr){2-4}\\cmidrule(lr){5-9}\nArm & Valid & Failed & Blocked & Endpoint & Trunc. & Codebook & Presence & Other \\\\\n\\midrule\n" + "\n".join(nrows) + "\n\\bottomrule\n\\end{tabular}\n")

# ---------- audit ----------
audit = {"schema": "casepath.manuscript-numerical-audit/2.0.0",
         "generated_by": "evidence/build_manuscript_numbers.py",
         "evidence_sha256": SHAS,
         "macro_count": len(macros),
         "tables": ["table_main_results.tex", "table_claim_gates.tex", "table_family_results.tex", "table_costs.tex", "table_native_execution.tex"],
         "macros": macros}
(E / "NUMERICAL_AUDIT.json").write_text(json.dumps(audit, indent=1, default=str) + "\n", encoding="utf-8")
print(f"wrote numbers.tex ({len(macros)} macros), 5 tables, evidence/NUMERICAL_AUDIT.json")
