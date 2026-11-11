# Paper blueprint, version 3.1 (planner's specification, 2026-11-11)

Binding for writers and figure makers. It replaces version 2 (in git history
at `13dd238d`). The paper is now about the CasePath product: the system that
is released and deployed is the system that is tested. Studies 1 and 2 become
the account of how the design was found. Claims marked [S3] depend on the
confirmatory test and are written only after it has run; until then writers
leave a clearly marked gap, never a guessed number.

## 1. Thesis

**An organisation's rules should be executed by code, over facts that agents
read from the file several times and can quote. Built this way, a
cost-efficient model makes fewer errors than the same model applying the
rules itself, and on claims where a rule stops or holds the checklist it makes
fewer errors than a frontier model applying the same rules. It holds exactly
the requests that depend on a fact the file leaves open.**

One sentence for a practitioner: the model reads, the organisation's rules
decide, and what the file does not settle becomes a question.

Working title: **CasePath: Agents That Read, Rules That Decide**. Subtitle if
the venue needs one: *Requesting Evidence for Insurance Claims with
Executable Workflows*.

### Results of the confirmatory test (Study 3; binding wording)

Source: `analysis/study3_results_fresh2_confirm.md` (first and only run of the
pre-registered analysis). Five hypotheses in a fixed order; the first three
were confirmed, the fourth was not, so the fifth was not tested.

- **H1 confirmed.** Theft, same model, same rules: 0.58 against 1.74 wrong +
  missed changes per pair (difference −1.15, interval −1.65 to −0.64,
  p = 0.008).
- **H2 confirmed.** Tenancy, same model: 0.31 against 2.14 strict unsafe
  errors per claim (p = 0.0002).
- **H3 confirmed.** Tenancy, frontier model: 0.31 against 1.87 (p = 0.0008).
- **Where the tenancy difference lies, as predicted in the plan:** on the 33
  claims whose defining event is denied or left open, 0.47 against 5.69 and
  5.31. On the 63 ordinary claims, 0.21 against 0.43 (same model) and 0.29
  (frontier model); against the frontier model that is no difference, and
  non-inferiority at the 0.10 margin holds as a secondary result.
- **H4 not confirmed.** Theft against every prior-work strategy: fewer errors
  than Model executes rules (p = 0.004) and ReAct (p = 0.012), but against
  Self-consistency the test over nine facts gave p = 0.0625 (0.58 against
  1.21; interval −1.13 to −0.08). The hypothesis required all three.
- **H5 not tested** (outside the procedure, reported as such): against the
  frontier model with the same rules on theft, 0.58 against 0.95; with the
  original rules, 0.58 against 0.67.
- **Open facts.** Theft: 94% of unresolved-fact pairs left otherwise
  unchanged, against 27–47% for every single-prompt design on either model
  with the reviewed rules. Tenancy: 97% of reference-held documents held,
  against 48% (same model) and 35% (frontier model). Two-valued execution of
  the product's own readings fails on open facts by construction.
- **All deviations per claim** (unsafe errors plus wrong holds): 0.73 against
  2.33 and 2.09. CasePath holds more than the single prompts (0.33 against
  0.17–0.18 unneeded holds per claim), most of it on denied-event claims
  where the readings did not all agree on the denial.
- **Which agents matter.** Checklist only against the full product: no
  difference on any measure (0.34 against 0.31; 0.55 against 0.58), at
  about a fifth of the cost. The full product costs USD 0.013 per tenancy
  claim and USD 0.030 per theft text; checklist only USD 0.003 and USD 0.005;
  the frontier single prompt USD 0.006 and USD 0.004.
- **Model for model (one run, no hypothesis).** On the frontier model the
  product equals itself on tenancy (0.30) and is not better than the frontier
  single prompt on theft (0.83 against 0.95, no difference). The gain from
  executing rules is largest for the cost-efficient model.
- **Irregularities to report:** three of five invocations of the run ended
  abnormally (one operator interrupt whose log line is wrong and corrected by
  a dated note; one time limit; one container restart), each resumed from
  the cache with settings unchanged; 50 failed outputs, none from the
  product, 40 from ReAct, counted as empty plans as planned; a post-hoc
  sensitivity analysis leaves ReAct's failed outputs out.

Never claim: that CasePath beats every prior-work strategy on theft; that it
beats the frontier model on theft; that the later agents improve the
checklist; that the result holds for a frontier model inside CasePath.

## 2. What the paper may claim

Formal (unchanged, proofs in the appendix): F1 soundness relative to admitted
facts; F2 strong Kleene evaluation over-holds; F3 exact deferral holds exactly
the documents that depend on an open fact; F4 what happens to a reading error
(two kinds, exact computation).

The product (descriptive, verified against the frozen commit): the agents and
what each may change; the workflow format; admission by exact quotation; two
readings must agree; presumptions with a source clause; Knowledge; the parity
command that proves inside and outside builds are the same source.

Confirmatory test [S3]: exactly the hypotheses of `ANALYSIS_PLAN_STUDY3.md`,
each stated with its comparator, test and outcome. Secondary results are
called secondary. A hypothesis that fails is reported in the same table and
the same voice.

Development history (Studies 1 and 2, pre-registered at the time, now
context): execution alone did not beat a frontier model; errors traced to a
few faulty extracted rules and to silence treated as doubt; label-free rule
repair failed; expert review of the rules, a second reading and exact
deferral are what changed the result. One page in the body, full reports in
the appendix.

Expert study (five experts, three real cases, pre-registered in
`expert_study/PREREGISTRATION_DRAFT.md`): only claims Q1–Q5 as worded there.
Written after the sessions; until then the section states the design.

Cost, stated plainly: the full product uses about 25 calls per case; [S3:
which agents changed a checklist]; the checklist-only setting and what it
costs relative to the frontier baseline.

Never write: "as safe as" for a non-significant difference; "outperforms"
without comparator and test; any development number as if it were a test;
"state of the art" unless H2 [S3] is confirmed, and then only for the stated
task and data.

## 3. Structure (at most 9,000 words of running text, Sections 1–9)

1. **Introduction** (700 words). The mould claim and its one open fact. Why
   a single prompt cannot keep "not stated" apart from "false". The idea in
   three sentences. What the test showed [S3]. Contributions: (i) the decision
   rule with its guarantees; (ii) the product, released with data and an API;
   (iii) a pre-registered test against prior-work strategies and a frontier
   model [S3]; (iv) a study with five claims experts on real cases.
2. **Background and related work** (800). Rule-based and neuro-symbolic
   reasoning over text (Chain-of-Logic, LDPC, ShARC line); agents and tool use
   (ReAct, self-consistency); abstention and three-valued logic; process
   mining and document checklists in claims handling; human reliance on AI
   advice. One comparison table: prior system × (rules executed by code,
   explicit unresolved value, quotation required, deferral exact, learns from
   corrections, tested with experts).
3. **The decision rule** (1,300). Facts, readings, admission, agreement,
   evaluation, exact deferral. Two results stated, proofs in the appendix.
   Fig. `fig_reconverge`. Running example carried through.
4. **CasePath** (1,300). One figure of the pipeline; one table: agent → what
   it reads → what it may change → what it may never change. Workflow format
   in ten lines. Knowledge and how a correction becomes a rule. The interface
   (Fig. `fig_hero`, real screens). Parity.
5. **How the design was found** (700). Table: root cause in Study 1 → change
   → evidence. The failed first redesign in one sentence. The ShARC pilot in
   two sentences (no advantage on small rule sets).
6. **Confirmatory test** (2,000) [S3]. Data and freeze; designs; hypotheses;
   Fig. `fig_main`; hypothesis table; open facts; cost and which agents
   mattered; robustness.
7. **Expert study** (1,200). Design now; results when the sessions are done.
   Fig. `fig_gestures` (real screens: leave, change with reason, note).
8. **Discussion** (800). When the advantage appears (many rules in force) and
   when it does not; what it costs (calls, holds); what an organisation must
   supply (reviewed rules); limits, each with its consequence.
9. **Conclusion** (150).

Appendices: A proofs; B Study 1 in full; C Study 2 in full; D deviations and
irregularities, all studies; E data, including `fresh2/` and the probe
claims; F robustness; G reproducibility, release and use of generative AI;
H prompts and workflows; I expert-study protocol.

## 4. Running example

The mould claim on the interface screens, as in version 2 §4. It appears in
Sections 1, 3 (the health-effects fact), 4 (the screens) and 6 (one open-fact
claim from `fresh2/`, described exactly, chosen by a rule stated in the
caption: the first open-fact defect claim in the manifest's order).

## 5. Figures (six in the body; one insight each; theme in `analysis/figtheme.py`)

| Figure | The reader should see | Source |
|---|---|---|
| `fig_hero` | one sentence left open turns a request into a question | real interface screens at the frozen commit |
| `fig_pipeline` | which agents read, which code decides, where a value can be rejected | drawn; names exactly as in the product |
| `fig_reconverge` | strong Kleene holds a document every completion requires; exact deferral does not | existing |
| `fig_main` [S3] | CasePath against every baseline on both regimes, with intervals, cost on a second panel | `analysis/study3.py` output |
| `fig_agents` [S3] | cost per agent against how often it changed a checklist | `analysis/study3.py` output |
| `fig_gestures` | the three gestures of the expert study | real interface screens |

Rules: dot plots with intervals, never bars for means; one axis per panel;
designs in one fixed order and one fixed colour each across all figures;
CasePath is the only saturated colour; direct labels, no legend box where
four or fewer series; no figure wider than the text block; screens are
unedited captures, cropped only, with the commit in the caption. Figures that
leave the body (`fig_outcomes`, `fig_trace`, `fig_study2`, `fig_fate`,
`fig_models`, `fig_knowledge`) move to the appendices unchanged.

## 6. Terminology and style

One term per concept, used everywhere, in the product, the paper and the
study files:

| Term | Meaning | Do not write |
|---|---|---|
| fact | a rule condition with a value true, false or unresolved | flag, atom, variable |
| reading | one model pass that gives every fact a value and a quotation | interpretation, judgment call |
| admitted | both readings agree and the quotation is found in the file | verified, accepted |
| workflow | an organisation's rules in the product's format | pack, template, rule base (except for the theft source) |
| checklist | the documents to request, to hold, and already present | plan |
| request / hold / hand over | the three things the product does with a needed document | defer (except "exact deferral") |
| presumption | what a workflow says an unstated fact is taken to be | default, silence policy (except when defining it) |
| Rules in context | one prompt that applies the rules | baseline B1, R |
| frontier model / cost-efficient model | gpt-6.1-terra / gpt-6-luna, named once in Section 6 | big, small, strong, weak |
| CasePath | the product at the frozen commit | v2, v3, CP4 (the core is "the two-reading core") |

Style: plain English; sentences under 25 words where possible; every
paragraph opens with its point; numbers with denominators; active voice with
"we"; British spelling; no rhetorical questions, no stacked hedges, no
adjectives of praise. Say a thing once. A paragraph that a figure or table
already says is deleted. Failures in the same voice as successes.
