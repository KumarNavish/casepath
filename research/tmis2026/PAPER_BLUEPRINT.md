# Paper blueprint (planner's specification, 2026-11-09)

This file fixes the narrative, structure, terminology, figures and claims of
the TMIS paper. Writers and figure makers implement it; they do not change
the thesis. Every number comes from a macro in `paper/results/numbers.tex`
(list with meanings: scratchpad `new_macros_final.txt`, plus the `rep…`
macros of the post-hoc repair analysis). Deviations from the analysis plan are
in `analysis/DEVIATIONS.md` and must be disclosed, not hidden.

## 1. Thesis

**Executing the rules does not make an agent's requests more accurate. It
decides where the agent's uncertainty and errors go.**

A model that applies the rules itself settles what it does not know inside its
answer: an unstated fact becomes a silent guess, and a faulty rule is silently
followed or silently repaired. Code that executes the rules over the model's
recorded true / false / unresolved judgments cannot guess: an unresolved fact
becomes a question, a claim it cannot admit is handed to a person, and a faulty
rule produces the same traceable error every time.

Title: **Where the Uncertainty Goes: Executing Rules over LLM Judgments to
Request Evidence**. CasePath is the name of the agent, introduced in the text.

## 2. What the evidence supports (the only claims allowed)

Formal (Section 3; proofs already corrected in `method.tex`):
- F1 Soundness: in the flow fragment, three-valued execution never requests a
  document that some completion of the unresolved judgments makes unnecessary.
  The guarantee is relative to the admitted judgments, not to the truth.
- F2 Strong Kleene evaluation holds documents that every completion requires
  (reconverging branches); exact computation over all 150 claims: it holds
  `\propKleeneExtra`% more than necessary.
- F3 Exact deferral (supervaluation, a standard notion) holds exactly the
  documents whose requirement depends on an unresolved judgment.
- F4 Error fate (exact computation, Fig. `fig_fate`): an *unresolved* judgment
  becomes a deferral under three-valued execution, a missed document if read as
  false, an unnecessary request if read as true. A *confidently wrong* judgment
  becomes an error under every semantics. A *wrong rule* is executed faithfully.

Empirical, pre-registered primary analysis (gpt-6.1-terra):
- E1 No accuracy advantage. Unsafe errors per claim 0.08 vs 0.06 (difference
  with CI; 3 informative families; not significant). Counting handed-over
  documents as missed (strict), execution is worse (0.40 vs 0.06, p = 0.002).
  Wrong changes on theft 38 vs 22 (n.s.). H1, H3, H4 not supported.
- E2 Execution defers: 25% of required documents held behind a question and 5%
  handed to a person, against 2.6% held with rules in context (H2 supported).
- E3 Run-to-run agreement on tenancy is higher with rules in context (H5
  reversed).

Empirical, pre-registered secondary analysis (gpt-6-luna):
- E4 Suggestive gains that depend on scoring. Unsafe errors 0.03 vs 0.11
  (p = 0.016 raw; 0.031 Holm within model; 0.078 across all ten tests); under
  strict scoring the direction reverses (0.30 vs 0.13, n.s.). Wrong changes
  17 vs 68, but 52 of the 68 repeat one off-case plan across conditions;
  counting each repeated error once: difference −0.15 per pair, p = 0.059.
  Unchanged requests when a fact is open 89% vs 43% (p at its floor, 6 clusters).

Mechanism (descriptive, both models):
- M1 Models are rarely confidently wrong and often unresolved: 7 of 1,170
  judgments contradicted the reference (terra), 0 (luna); 735 and 720 were
  unresolved. 638 of terra's unresolved judgments concern facts the claim never
  mentions and the reference reads as false.
- M2 The references encode a policy for silence. Reading silence as false is
  what the generator does, so a design that guesses is scored correct and a
  design that asks is scored as deferring. Two-valued execution on the same
  judgments: 26.2% / 16.0% missed (open read as false), 29.5% / 29.4% of
  requests unnecessary (open read as true).
- M3 Rule errors: with terra, 37 of 38 wrong changes and 17 of 30 misses trace
  to five of 98 extracted rules; a blind rule verifier flags all five and 59
  others. In the original study, 12 of 15 wrong changes trace to the same five
  and 3 to a sixth rule on a contested condition. The frontier model applying
  the same rules in context avoided most of their consequences; nothing records
  how.
- M4 Costs of CasePath's own machinery. The verifier (terra) rejected 35
  condition verdicts, all correct, and caught none of the 7 wrong ones. All 13
  terra handoffs and 8 of 11 luna handoffs come from the verifier rejecting the
  category item while affirming the family. Post-hoc repairs on recorded
  judgments (admit the family when the verifier affirms it; presume the routing
  fact): report with the `rep…` macros, labelled post hoc and unconfirmed.
- M5 Break-even (post hoc): with luna, execution is preferable only if an
  unsafe error costs more than ~13 held documents (~5 with the routing
  presumption); with terra, at no ratio.
- M6 Cost per case and engine runtime as measured.

Never write: "as safe as" for a non-significant difference (give the numbers);
"robust to the model" as a general claim; "four times fewer" without the
scoring caveat; "provably never premature" without "given its admitted
judgments"; anything implying the secondary analysis was primary.

## 3. Structure (target: at most 6,800 words of running text, Sections 1–7)

1. **Introduction.** Open with the watch: one sentence of a claim, one rule,
   three possible worlds. State the question (who applies the rules: the model
   or code?). Give the answer in one paragraph, organised as "not accuracy /
   where uncertainty goes / what it costs". Two-regime design in one sentence
   (clean rules with complete references; extracted, imperfect rules with
   changed facts). Relation to the earlier version in two sentences (no
   reviewer anecdote). Three contributions: (i) a formulation that separates
   three sources of error and states what each becomes under each design, with
   soundness and exact deferral (standard logic applied, said plainly);
   (ii) the CasePath agent and a pre-registered comparison reported with its
   failed hypotheses; (iii) design knowledge: when to execute, and that
   benchmarks encode a policy for silence.
2. **Background and related work.** Claims context in one paragraph; the
   approaches; Table 1 (keep, but columns limited to capabilities the paper
   tests or uses, each tick justified in the text); the gap paragraph with
   "its ingredients are established".
3. **Executing rules over judgments.** 3.1 the decision and its three sources
   of error (judgment wrong, judgment unresolved, rule wrong); 3.2 three-valued
   execution and soundness; 3.3 exact deferral; 3.4 what each error becomes
   (F4, Fig. `fig_fate`); 3.5 the CasePath agent (Algorithm 1). Keep the
   corrected mathematics; cut to essentials.
4. **Evaluation design.** Hypotheses as registered; two regimes; designs
   (Table); measures with the four outcomes (requested, held, handed over,
   missed) and unsafe errors, strict variant named; primary and secondary
   analysis; statistics with cluster counts and attainable p; pointer to the
   deviations appendix.
5. **Results**, four questions, each subsection opens with its answer:
   5.1 Does execution make requests more accurate? (E1, E4; Table of tests
   with differences and intervals; Fig. `fig_outcomes`; Fig. `fig_models`.)
   5.2 Where does the uncertainty go? (E2, M1, M2; running example on the
   actual unresolved-watch variant.)
   5.3 What happens to rule errors? (M3; Fig. `fig_trace`.)
   5.4 What does execution cost? (E3, M4, M5, M6.)
6. **Discussion.** Recap in three sentences. Four design principles in the
   form "to achieve X in context Y, do Z, because W" (separate judging from
   applying; treat silence as unresolved and make presumptions explicit rules;
   verify rules before executing them, and audit a verifier before trusting
   it; hand over what cannot be admitted). When to execute (Table). For
   evaluation research: references encode a silence policy; conclusions are
   statements about a model. Limitations (synthetic data, circular tenancy
   references, no expert review, low reasoning effort, uneven design grid, no
   ReAct-style agent, exposure, post-hoc analyses).
7. **Conclusion.** Five sentences.
Appendices: A original evaluation; B deviations from the analysis plan
(from `DEVIATIONS.md`); C data; D robustness and sensitivity; E reproducibility
and use of generative AI; F prompts (fix the overflowing listings).

## 4. Terminology (one term per concept)

- *judgment*: the model's verdict on one rule condition: true, false or
  *unresolved*. A fact the claim does not mention is *unstated*.
- *rule*, *condition*, *document*; *requirement* (evidence need with
  alternative *routes*).
- Designs: Direct; Rules in context; Self-consistency; Model executes rules;
  Two-valued execution; CasePath (production engine = strong Kleene
  evaluation; exact deferral = supervaluation).
- Outcomes of a required document: *requested*, *held* (behind a question),
  *handed over* (whole claim to a person), *missed*. *Deferred* = held or
  handed over. *Unnecessary request*. *Unsafe error* = unnecessary request or
  missed document; *strict* counts handed-over documents as missed.
- *dispute family*, *routing fact*: define in the glossary table.
- *primary analysis* (gpt-6.1-terra), *secondary analysis* (gpt-6-luna).

## 5. Figures (one insight each; standard: the MechanismFigures references)

Files in `paper/figures/`, generated by `analysis/figures.py` or TikZ.
- `fig_hero` (Fig. 1). One claim sentence about the watch stays fixed; three
  worlds are aligned as rows (separately insured: true / false / not yet
  known); the same rule stays visible; the right-hand side shows what each
  design returns. Model applies the rules: one checklist in all three rows,
  the guess invisible. Code executes the rules: request the receipt / skip /
  hold both and ask "Was the watch separately insured?". Insight: the designs
  differ only in the third row.
- `fig_reconverge` (Fig. 2). The real tenancy defect process as a graph with
  the branch on health effects and the reconverging scope step. Left: strong
  Kleene, the unresolved value floods everything downstream. Right: the two
  completions drawn as two traversals of the same graph; documents reached in
  both are requested, only the medical confirmation is held. Insight: holding
  is necessary only where the two worlds disagree.
- `fig_fate` (Fig. 3). Exact computation over all 150 claims. Three kinds of
  judgment error enter on the left (unresolved; confidently wrong) and each
  semantics sends them to an outcome (deferral, missed, unnecessary). Insight:
  three-valued execution converts uncertainty into deferral; nothing protects
  against a confident wrong verdict. Must stay quantitatively exact.
- `fig_outcomes` (Fig. 4). Where 100 required documents end up, per design and
  model: 100 unit marks per row in four colours (requested, held, handed over,
  missed), unnecessary requests as a separate small count. Primary model on
  top, secondary below, rows aligned. Insight: execution trades requests for
  questions and handoffs, not for fewer errors.
- `fig_trace` (Fig. 5). Every wrong change of the primary theft run as one
  mark: CasePath's 38 marks attached to the rule that produced them (five
  rules hold 37), with the rule verifier's flag on each rule; Rules in
  context's 22 marks beside it with no rule to attach to. Insight: executed
  errors have an address.
- `fig_models` (Fig. 6). Wrong changes per pair for the two designs across the
  three models (original single run marked as such), with the repeated-error
  sensitivity shown. Insight: the comparison depends on the model.

## 6. Style

Plain, exact, short. Lead each paragraph with its point and each results
subsection with its answer. Give denominators. Prefer a number to an adjective.
One example (the watch) carried through Sections 1, 3 and 5. No signposting
filler ("it is worth noting", "in this section we"), no stacked hedges, no
triads of adjectives, no rhetorical questions outside subsection titles, no
em-dash chains. British spelling, as in the current text.
