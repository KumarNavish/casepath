# Claims audit: research/tmis2026 paper (repository HEAD 09047150, product commit 6a72159c)

Read-only audit. No repository file was edited. No model calls and no network were used. Scripts and outputs are in this folder:
`expand.py` (expands the macros of the three numbers files), `check_macros.py` (independent lookup of Study 3 macros in the results JSON),
`regen_*.py` / `regen_*.tex` (copies of the three macro generators writing here), `repro_confirm.json/.md` (re-run of the Study 3 analysis),
`prompts.py` (quoted prompts against their sources), `bibcheck.py`, `code/` (product files extracted with `git show 6a72159c:...`).

## Counts

| Section | Claims checked | Confirmed | Wrong | Imprecise | Unsupported |
|---|---|---|---|---|---|
| 0 Abstract | 16 | 11 | 0 | 3 | 2 |
| 1 Introduction (incl. Fig. 1 caption) | 24 | 16 | 1 | 6 | 1 |
| 6 Confirmatory test (text, Tables 3–5 cell by cell, Fig. 4–5 captions) | 220 | 208 | 3 | 7 | 2 |
| 8 Discussion | 30 | 24 | 1 | 3 | 2 |
| 9 Conclusion | 6 | 4 | 1 | 1 | 0 |
| Macros: 120 random of numbers_study3.tex + all 289 used in Sections 0, 1, 6, 8, 9 | 409 (360 distinct) | 409 | 0 | 0 | 0 |
| Macros: undefined / defined twice (all three files and macros.tex) | all | – | 0 | 0 | 0 |
| 6 against plan, manifest and Appendix D | 40 | 33 | 3 (counted above) | 4 | 0 |
| 3–4 Decision rule and product, against code at 6a72159c | 45 | 36 | 0 | 7 | 2 |
| 5 and Appendices B–C (spot checks) + rule review | 25 | 21 | 0 | 3 | 1 |
| 7 and Appendix I against the pre-registration draft | 30 | 28 | 1 | 1 | 0 |
| Appendices E, G, H (counts, reproduction, five prompts) | 45 | 43 | 0 | 1 | 1 |
| References (45 cited keys) | 45 | 40 | 0 | 5 (field/format) | 0 |

Macro checks: all three generators (`make_numbers.py`, `make_numbers_sharc.py`, `make_numbers_study3.py`), run as copies writing to this folder, reproduce the committed `numbers*.tex` byte for byte (2,371 + 18 + 1,766 macros). The independent lookup of 120 random Study 3 macros and of every Study 3 macro used in Sections 0, 1, 6, 8 and 9 (289) found no mismatch. Macros not in the results JSON were checked by hand against MANIFEST, RUNLOG, the posthoc JSON, `fresh2/MANIFEST.json` or the stored plans. No macro is undefined; none is defined twice; the LaTeX log has no undefined-reference warning; the PDF text matches the sources.

Reproduction: `python3 analysis/study3.py --data fresh2 --label confirm --out <scratch>/repro_confirm` (run with `PYTHONDONTWRITEBYTECODE=1`) reproduces `study3_results_fresh2_confirm.json` and `.md` byte for byte. The plan and spec are unchanged since the freeze commit fd35e438 (22:29:32Z, 43 s before the first invocation).

## Findings, most serious first

### F1. The cost and the "no change" of the full product are attributed to "agents after the readings", but the brief and the process builder run before the readings (wrong)
- Locations: s1_introduction.tex:18 "The agents after the readings added cost and changed no checklist: the checklist-only setting showed no difference in errors, at 22% (tenancy) and 16% (theft) of the full product's cost."; s6_test.tex:141 "so their comparison shows what the later agents add, here nothing"; s8_discussion.tex:11 "The agents after the readings changed no scored checklist …; they buy only the brief, the reply draft and the checks a handler reads."; s9_conclusion.tex:4 "The agents after the readings cost most of a run and changed no checklist."
- Source: `casepath/agents/team.py` at 6a72159c, lines 112–119 (PLAN: claim_reader brief, then process_builder, then the readings, document finder, source checker, result checker) and 1097–1112 (run loop); stored agent sequence in `runs/study3/confirm/plans_tenancy_casepath.json` (router, claim_reader x8, process_builder x4, then the readings). The checklist-only setting skips the brief, the process builder (unless active Knowledge applies), the source checker's fact check and the result checker (team.py:1123–1142). Per-agent cost (`study3_results_fresh2_confirm.json` designs/casepath/regimes/*/cost/by_group_per_case_run): process builder + result checker = USD 0.00554 of 0.01339 (41%) on tenancy, 0.01120 of 0.02999 (37%) on theft. The agents "that can decide the checklist" cost 51% and 62% in the full run.
- Discrepancy: the difference between full and checklist-only (78% and 84% of the cost) includes two agents that run before the readings (the brief and the process builder). The process builder's additions, the only "changes" counted (0 of 288 and 0 of 384 entered), are made before the readings. "Cost most of a run" holds only for the difference between settings. Assigned to the later agents by the ledger, it does not hold (41% and 37%).
- Corrected: "The steps that the checklist-only setting skips (the brief, the process builder, the source checker's check of facts and the result checker) changed no scored checklist in a way the tests detected and account for 78% (tenancy) and 84% (theft) of the full product's cost." In S9: "The steps that do not decide the checklist account for most of a run's cost and …".

### F2. "Changed no checklist" claims more than was measured (imprecise, overclaim)
- Locations: s1:18, s8:11, s8:21 ("the checklist-only setting showed no difference from the full product"), s9:4, s6:141 ("showed no difference from the full product on any measure").
- Source: JSON secondary/product_checklist_changes (needs added by an agent that entered the scored checklist: 0/288, 0/384). Contrasts S5a–S5c: non-zero clusters 7 of 24, 10 of 24, 6 of 9; p = 0.50, 1.00, 0.59. Run-to-run Jaccard is 0.944/0.956 (tenancy), 0.974/0.973 (theft). Full scope also lets the source checker reject documents and triggers a retry (team.py:659–720, 1144–1158). Only three measures were tested.
- Discrepancy: the checklists differ between the two settings in many clusters. What was shown is (a) that no agent-added need entered a checklist and (b) that three error measures do not differ significantly with 9–24 clusters. "On any measure" covers untested measures. For example, premature requests are 0.024 against 0.000 and correct-hold share is 97% against 100%.
- Corrected: "No need added by an agent entered a scored checklist (0 of 288 and 0 of 384 case-runs), and the full product's errors did not differ significantly from the checklist-only setting's (strict unsafe 0.31 vs 0.34, p = 0.5; wrong + missed 0.58 vs 0.55, p = 0.59)."

### F3. The expert study is called "registered", but the pre-registration is an unfrozen draft (wrong)
- Locations: s7_experts.tex:7 "We have registered a study in which five claims experts …"; s1:22 "A registered study will have …"; s1:29 "A registered study …"; s0 "and register a study"; s2 Table 1 "registered (§7)".
- Source: `expert_study/PREREGISTRATION_DRAFT.md` lines 3, 17–18 ("Version 1.0-rc … Frozen as version 1.0 by the procedure in section 13"), 335–336 (freeze on day 10 = 2026-11-20) and 350 (deposit in a registry after the freeze). App I itself says "version 1.0-rc. It becomes version 1.0 at the freeze".
- Corrected: "We have drafted a pre-registration (version 1.0-rc) of a study …; it will be frozen and deposited on 20 November 2026, before the first session."

### F4. "All settings are the commit's defaults" is false: model reasoning was switched on (wrong)
- Location: s6_test.tex:13 "All settings are the commit's defaults: 3 readings that must agree, and no presumption for a fact any reading finds raised and left open."
- Source: `casepath/config.py` lines 121–123 at 6a72159c: for a non-Azure provider `reasoning` defaults to False unless `CASEPATH_MODEL_REASONING` is set. `runs/study3/confirm/MANIFEST.json` fixed.product.settings_env_by_run sets `CASEPATH_MODEL_REASONING=true` (provider databricks, chat API) for every product run. The plan (§2) lists "Defaults of the frozen commit … " and reasoning separately, and s4_casepath.tex:85 itself says "the tested runs also pass the model's reasoning effort". Several model-client settings are also set explicitly (max output tokens, timeout).
- Corrected: "Settings are the commit's defaults (three readings that must agree; the open rule any; full run scope), except that the model's reasoning effort is passed (`CASEPATH_MODEL_REASONING=true`), as the plan specifies."

### F5. The count of early stops "1 on purpose … 3 not" misreports the first invocation (wrong)
- Locations: s6_test.tex:158 "Of 5 invocations of the run, 4 stopped early: 1 on purpose, to end before a time limit, and 3 not."; app_d_deviations.tex:45 "4 of them stopped early, 1 on purpose and 3 not".
- Source: RUNLOG.jsonl correction note 2026-11-10T23:00:18Z: "… when the operator interrupted it at 22:59:37 to resume with more parallel workers (the run was slow, not faulty)". Note 2026-11-11T04:38:40Z: the fourth stop "is the only early stop that was planned". App D:47 itself says "the operator interrupted it, unplanned, to resume with more parallel workers".
- Discrepancy: two stops were deliberate (the operator's interrupt and the planned wrapper stop). Two were not (the background time-limit kill and the container restart). The macro `\sthreeRunUnplannedStops` (3) counts unplanned stops, and the text calls them "not on purpose".
- Corrected: "4 stopped early: 1 as planned, by the wrapper before a time limit; 1 interrupted deliberately by the operator to add workers; and 2 by failures of the environment (a time-limit kill and a container restart)."

### F6. "Released product" and "We release the product" are not true at this commit (unsupported)
- Locations: s0 "We tested the released product …"; "We release the product, workflows, data and analysis"; s1:28 contribution 2 "released with its workflows, data …".
- Source: `git merge-base --is-ancestor 6a72159c HEAD` returns false. 6a72159c is only on branch `claude/casepath-internal-paper-sync-20261110d`. app_g_repro.tex:8 (AUTHORS comment: the commit "is on the product branch, not on the paper branch; the release must contain it"). app_g:18 (no licence for fresh/, dev_probe/, fresh2/). app_g:43 (undecided whether the insurer-naming source and seed Knowledge are released). App D:60 (the merge of the tested commit was not confirmed by the owners). references.bib casepath2026repo names the paper branch.
- Corrected: "We tested the product at a frozen commit (6a72159c) … We will release the product commit, workflows, data and analysis."

### F7. The Study 1 frontier tenancy result quoted is a post-hoc sensitivity analysis, and it shows CasePath significantly worse, not "no better" (imprecise, status)
- Location: s5_history.tex:7 "With the frontier model it was no better than Rules in context: it made 38 wrong theft changes against 22 (p = 0.211) and, counting documents handed to a person as missed, 0.404 unsafe errors per tenancy claim against 0.063 (p = 0.002)." Also s1:20 "Two earlier pre-registered studies found execution no better than Rules in context".
- Source: `analysis/primary_tests.json` gpt-6.1-terra|secondary[0] key H1_strict, test "H1 sensitivity (post hoc): handed-over documents counted as missed", a 0.4037, b 0.0630, p 0.00195, favours b. The registered H1 is gpt-6.1-terra[0]: 0.0815 vs 0.0630, p = 0.25. With gpt-6-luna (the registered sensitivity model), the Study 1 configuration was better on tenancy (0.026 vs 0.115, p = 0.016) and on theft (0.210 vs 0.840, p = 0.0039).
- Corrected: "With the frontier model (the primary analysis) it was no better than Rules in context: 38 against 22 wrong theft changes (p = 0.211) and 0.081 against 0.063 unsafe errors per tenancy claim (p = 0.25); counting handed-over documents as missed (post hoc), it was worse (0.404 against 0.063, p = 0.002)."

### F8. "As the plan predicted, the tenancy difference lies in the 33 claims" omits that the plan's other prediction failed (imprecise)
- Locations: s1:18 "As the plan predicted, the tenancy difference lies in the 33 claims whose defining event is denied or left open."; s6:102 "… and so they were."
- Source: ANALYSIS_PLAN_STUDY3.md §6: "On the 63 ordinary claims we expect no difference between CasePath and either baseline." JSON hypotheses[1].beside (H2 on ordinary): 0.203 vs 0.438, diff −0.234, p = 0.0417 (descriptive). Section 6 does report this ("which the plan did not predict"); the introduction does not.
- Corrected (s1): "As the plan predicted, most of the tenancy difference lies in the 33 claims …; against the same model the ordinary claims also differed (0.20 against 0.44, descriptive), which the plan did not predict."

### F9. "The checklist-only setting is the cost-matched comparison" repeats a plan premise that Appendix D shows false (wrong; body contradicts App D)
- Location: s6_test.tex:18 "No design was matched to the cost of the full product; the checklist-only setting is the cost-matched comparison."
- Source: plan §4: "Self-consistency with five samples costs at least as much as CasePath, checklist only, on both regimes. … the checklist-only row is the cost-matched comparison." app_d:69: this holds on tenancy (0.0034 vs 0.0030) but not on theft (0.0035 vs 0.0049). Checklist-only costs 0.47 and 1.20 times the frontier single prompt.
- Discrepancy: the sentence does not say what checklist-only is matched to. The only match the plan states (to Self-consistency) fails on theft.
- Corrected: "No design was matched to the cost of the full product. The plan intended Self-consistency to cost at least as much as the checklist-only setting; this held on tenancy but not on theft (Appendix D)."

### F10. "A value counts only when the readings agree" holds only for deciding and routing facts (imprecise)
- Locations: s0 "a value counts only when the readings agree"; s1:16 "code admits a value only when the readings agree"; s3_rule.tex:21 "A value is admitted when every reading gives it …".
- Source: team.py:731–740 (`read_again`/`gating_facts`: only facts in transitions, `required_when` and the routing condition are combined across readings); 954–1057 (`confirm_facts` combines only those); 866–889 (the first reading records every fact); 1201–1208 (`finalize`: reply-draft statements rest on established and accepted facts, which may come from one reading for non-deciding facts).
- Corrected: "a value that decides the checklist or the routing counts only when every reading gives it …"

### F11. "Inside CasePath the two models showed no difference" compares different settings (imprecise)
- Locations: s8:5 "inside CasePath the two models showed no difference in tenancy errors (0.31 against 0.30, one run of the frontier model, descriptive)"; s1:18 "The frontier model inside CasePath was not better than the frontier single prompt on theft"; s6:152 "On the frontier model the product cost USD 0.021 per claim …".
- Source: S7d compares `casepath` (full scope, gpt-6-luna, 3 runs) with `casepath_frontier_checklist` (checklist scope, gpt-6.1-terra, 1 run); p = 0.957.
- Corrected: "CasePath on the cost-efficient model (full) and CasePath on the frontier model (checklist only, one run) made 0.31 and 0.30 strict unsafe errors per claim (descriptive)."

### F12. Presumption rule stated too strongly (imprecise)
- Locations: s3_rule.tex:25 "It does not apply when any reading answers open with words found in the file, or when a reading finds another value; a reading that finds the presumed value supports it."; s4_casepath.tex:85 "with any, the default, one reading that answers open with words found in the file keeps a presumption from applying."
- Source: workflows.py:738–745 `open_without_raise`: the presumption applies if `not raised_open(row) or value in readings`. A reading that gives the presumed value therefore overrides another reading's open answer. The docstring at 748–757 ("every reading quoted a passage") also disagrees with OPEN_RULE "any".
- Corrected: "… one reading that answers open with words found in the file keeps a presumption from applying, unless another reading gives the presumed value."

### F13. Routing described imprecisely; rerouting not described (imprecise)
- Locations: s4:9 "The router reads the routing facts from the beginning and end of each file. … when none or several remain, the claim goes to a person, or to a fallback workflow where the catalogue has one."; Table 2, row Router.
- Source: core.py:198–212, 236 (a file is read whole when it fits in 12,000 characters, otherwise its first and last pages, about 6,000 characters each; only the first 12 files). workflows.py:272–306: when exactly one workflow's condition is open and no fallback exists, it is selected and its routing facts are presumed. Several selected → ambiguous (a person). A fallback is used only when no workflow can apply. core.py:356–414: after the readings, a contradicted routing fact reroutes once; a second contradiction goes to a person. Intake routing values count without a quotation (core.py:264).
- Corrected: "The router reads each of the first twelve files, whole if short, otherwise its beginning and end. Code selects the workflow whose condition the values satisfy, or the only workflow whose condition they leave open (its routing facts then count as presumed). Several candidates go to a person; a fallback workflow is used when none can apply. If the readings later contradict the routing, code reroutes once, and a second contradiction goes to a person."

### F14. Section 6 description departs from the plan in several smaller points (imprecise)
- s6:11 "stories 6–7 once for validation": plan §3 says "used once, for validation, before the last review fixes, and re-run from cached readings after them". Add "and re-run from cached readings after the last fixes".
- s6:18 "All designs received the same files, document catalogue and rules": the two original-rules designs receive the Study 1 rules (Table 3 itself). Say "the same rules, except the two original-rules designs".
- s6:49 "The tests are exact two-sided sign-flip tests over clusters": H5 is a paired cluster-bootstrap non-inferiority test (plan §6; JSON hypotheses[4] test noninferiority). Say "H1–H4 use exact two-sided sign-flip tests …; H5 a cluster-bootstrap non-inferiority test".
- s6:96 "CasePath had fewer errors on 7 changed facts and more on 2": correct values, but these come from the post-hoc file (`study3_posthoc.md` §2) and are not labelled post hoc in the body.
- s6:105 "against 27–47% for every single-prompt design": the 47% is ReAct, a tool-using agent, not a single prompt. Say "every other baseline".

### F15. Causal and interpretive statements without a stored analysis (unsupported)
- s6:138 and s8:11 "most of them on denied-event claims, where the readings did not all agree on the denial": no analysis file supports the cause. The stored plans show that all 84 spurious holds on the 72 denied-event case-runs occur in 12 case-runs and wait on `claim_received`. Whether the cause is disagreeing readings, a single reading, or an open answer was not analysed. Say "where the defining event stayed unresolved".
- s6:152 "The gain from executing rules is largest for the cost-efficient model.": it rests on one descriptive, one-run checklist-only design (S7a p = 0.672, S7b). Mark it as descriptive.
- s4:85 "the tested runs also pass the model's reasoning effort …, so the readings are sampled independently": no code or result shows that reasoning makes readings independent, and readings use effort "low" (team.py:144). Delete the clause after "so".
- s4:23 "… so more deciding facts stay unresolved" (claims over 40,000 characters): consequence asserted, not measured.

### F16. "Two independent AI editor sessions" is not documented in rule_review/ (unsupported)
- Locations: s5:32, s8:14, app_g:12, app_g:52.
- Source: `rule_review/final/RECONCILIATION.md` names "Editor A" and "Editor B" and the adoption rule ("both editors made it, or one made it and the other approved it", confirmed). Nothing in `rule_review/` says that the editors were AI sessions; only WORKLOG.md:127 says "two blind editors". Counts confirmed: 98 rules reviewed, 9 changed (016, 023, 030, 042, 049, 068, 071, 074, 020 with split 020.a), 99 in the final file, 14 queued for a jurist, none rejected.
- Fix: record the editors' identity (model, session) in rule_review/, or soften to "two independent editors".

### F17. ShARC pilot includes development items (imprecise)
- Location: s5:35 "On 320 training utterances with the cost-efficient model, its accuracy was 0.725 against 0.719 …".
- Source: `runs/sharc/summary.json` has `micro_excl_dev60` for every design and a cost component `cp_dev_revisions` (290 calls): 60 of the 320 items were used to develop the core. Excluding them: core 0.742 vs self-consistency 0.735. Self-consistency here uses 3 samples ("sc3"); in Study 3 it uses 5.
- Corrected: "On 320 training utterances, 60 of which were used in development, … (0.742 against 0.735 without them)."

### F18. "638 of 735 unresolved values concerned facts the claim never mentions" relabels "truth false" (imprecise)
- Location: s5:18 (Table 2).
- Source: `analysis/judgment_accuracy_gpt-6.1-terra.json`: "interp | unresolved | truth_false" = 638, "truth_true" = 97, "routing" = 44. The count is of facts whose true value is false. Unmentioned true routing facts (44) fall in the other group, and false facts are not all unmentioned.
- Corrected: "638 of 735 unresolved values concerned facts that were false in the scenario, which the claims leave unmentioned."

### F19. Knowledge "cannot change a condition" has an exception shipped in the build (imprecise)
- Location: s4:70 "An item learned from a case only adds a need, a question, a step or a note: it cannot remove a need or change a condition of the workflow".
- Source: casegraph.py:71–82. An active document_need with `replaces` moves an existing workflow need to intake and replaces its `required_when`. Two shipped seed items use this (`process/knowledge_seed/osm-mold.pilot.json` lines 12 and 45, active at build per knowledge.py:116–144). Items learned from cases (knowledge.py:95–110, core.py:318–347) cannot do this, so the sentence is literally true but leaves out shipped Knowledge.
- Corrected: add "(Knowledge shipped with a build can also move a workflow's need to intake and set its condition.)"

### F20. Exact-deferral limit and cost (imprecise)
- Location: s3:86 "The cost is 2^u evaluations for u open facts; … above eight, CasePath stops at the first open branch."
- Source: workflows.py:432, 506–517: the walk also stops when the product of the answer domains exceeds 256. Enum and text facts have more than two answers, and facts that a condition asks to be known get an extra "unset" answer. Say "at most 256 completions; above eight open facts, or 256 combinations, …".

### F21. Wording of non-significant results as "no difference" (imprecise)
- s1:18 "showed no difference in errors"; s6:102 "the ordinary claims show no difference (p = 0.409)"; s8:8 "CasePath did not differ from the frontier model"; s6:141 "on any measure". These are non-significant, two-sided tests with 9 to 24 clusters (S5a–c, H3-ordinary). Say "did not differ significantly". The ordinary-claims non-inferiority (S1a, p = 0.0225) is the only equivalence-type result.

### F22. Abstract: comparators and regimes not named for two figure pairs (imprecise)
- s0 "It held 97% … against 48% and 35%, at 2.1 and 7.4 times the frontier single prompt's cost." Say "against 48% for Rules in context and 35% on the frontier model, at 2.1 (tenancy) and 7.4 (theft) times …".

### F23. Appendix E: "8 more hold everything" (imprecise; inherited from README)
- app_e:95 "The references of 24 claims (defining event denied) mark every document not needed, and 8 more hold everything behind the open defining event."
- Source: fresh2/README.md:100 "33 claims have an empty request set (the 32 with the defining event false, and one with the notice left open)". The plan and analysis count 9 open-event claims (empty request set, at least one held). README:124 repeats "8 more". Say "and 9 more (8 in families where the event is false, 1 where it is true) hold everything …".

### F24. Section 7: "change it in place with one of six reasons" (imprecise)
- s7:16. PREREGISTRATION_DRAFT.md:207: the reason is one of six "in one tap, 'ohne Angabe' by default". App I states this correctly. Say "optionally with one of six reasons".

### F25. Bibliography (field and format issues within the file)
- All 45 cited keys resolve; no duplicate keys.
- li2026sopbench: doi `10.18653/2026.emnlp-main.936` lacks the `v1/` segment that every other ACL DOI in the file has (e.g. `10.18653/v1/2024.findings-emnlp.638`).
- saeidi2018sharc: no pages, publisher, DOI or verification note, unlike the neighbouring EMNLP 2018 entries (kaushik2018reading has all of them).
- erwin2025ldpc ("the closest system"): misc with only `howpublished`/`url`, and no verification note.
- yao2022react: key says 2022, year field 2023 (ICLR 2023).
- BibTeX warnings for cited entries: missing publisher/address/pages in geifman2017selective, saeidi2018sharc, wang2023selfconsistency, yao2025taubench, yao2022react, reiter1978closed, schemmer2023appropriate. Address is missing in several others.

### Confirmed but worth noting (no correction needed)
- Hypothesis table (s6:64–73): every cell equals the JSON after half-away-from-zero rounding, e.g. H3 B 1.8646 → 1.86 and H4.1 Lo −1.125 → −1.13.
- Ratios: 0.00296/0.01339 = 22%, 0.00490/0.02999 = 16%, 4.52x, 6.12x; 2.12x, 7.35x (frontier); shared calls 1087/8101 = 13% and 1162/11542 = 10%.
- Failed outputs: 50 = 23 + 17 (ReAct) + 2 (MER) + 1 (Core) + 7 (SC samples); none from the product designs.
- Running example (s6:108): claim f2cl_03fdd7ee632bb267, German e-mail, quoted sentence present, technical_inspection held, 7 requests.

## What I could not check, and why
- The screen crops of Fig. 1 (hero) and the plotted points of Figs. 3–5 (fig_main, fig_cost, fig_reconverge, fig_pipeline): images were not inspected; only captions against data.
- The second reproduction line (`make_numbers_study3.py && fig_s6.py`) as written: it writes into the repository. I ran a copy of each macro generator with its output redirected (identical result) and did not run `fig_s6.py`. `verify_paper.py` (Studies 1–2) was not run, because it requires unpacking the Study 1 response cache into the repository.
- A Study 3 re-run with model calls (`harness/study3/run_all.py`): needs network and model access, which the task excludes.
- Ledger spend (USD 34.33 / 22.41 / 11.92 / 6.99 / 27.34): checked only by regenerating the macros from the ledgers with the repository's own script, not by an independent sum.
- s3:86 "the Study 1 claims had at most five [open facts]", and the s3:98 propagation numbers (`\propClaims` etc.): their source (`scicore/out_local`) was not traced.
- Appendices A (proofs), F (robustness) and Section 2 beyond the cite keys: outside the requested scope. Appendix B and C were spot-checked only (25 numbers).
- UI statements in s7 ("no control for closing a case and none for a note"): `web/ui/assets/casepath.js` was not inspected.
- Whether parity was computed per case-run or per design: MANIFEST records it per design and regime (6 records, all hash 030480203f7d10b3). `run_api.py` mentions an in-process check, which was not traced.
- Bibliography details against external records: excluded by the no-network rule.
