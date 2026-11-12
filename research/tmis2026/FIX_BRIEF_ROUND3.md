# Fixes after the third referee round (planner, 2026-11-12)

Input: `analysis/review/REFEREE_REVIEW_ROUND3.md` (major revision; 10 major,
23 minor concerns; read it in full, including Part 2's item-by-item
corrections, the ten sentence rewrites and Part 4). Every item is accepted
and is to be closed as the report says, unless a decision below says
otherwise. `REWRITE_BRIEF.md` stays binding where this brief is silent; where
they disagree, this brief wins. Nothing needs a model call.

## Decisions

**Headline (M2, M3).** The paper leads with the registered tenancy result:
H2 and H3 (0.31 against 2.14 and 1.86 strict unsafe errors per claim) and the
registered holding result (97% of reference-held documents held, against 48%
and 35%). "The design holds what the file leaves open" is claimed for
**tenancy only**. On theft the registered statement is: no premature request
on unresolved-fact pairs, and the rest of the checklist unchanged in 94% of
them; say in the same place that this measure cannot tell a hold from
reading the open fact as false (two-valued "unresolved = false" also scores
94%), that exact deferral never ran on theft, and report the F1 measure "the
open condition's documents held" for CasePath and the single prompts. Every
"every other design 27–47%" becomes the exact set of designs it is true of.

The open-or-stated split (F1) comes after the registered result, labelled
"added after review", with **one quantity everywhere**: claim-run means in
the text, Table 8 and Figure 5 (0.40 against 3.39 and 3.06 on the 56 claims;
the stated-everything values likewise), family means only in the supplement
and named as such. Describe the subset exactly: "an open fact, or a denied or
open defining event". Say in 6.2 that nine of 24 families carry the tenancy
effect (those of the two dispute types that contain the denied- and
open-event claims) and that on the 15 defect families differences are small
and mixed. Figure 5's caption says the mix within the open subset is held at
the test's.

**H4 (M1).** Seven of nine clusters favoured CasePath; it was worse on two
(by 0.125 and 1.00). Numbers through macros from the data (the writer is
already adding them). Check every other direction count in main and
supplement against `study3_review.md` R6.

**Frontier theft (M4).** Not "the rules set the limit". Say what the data
show: on the frontier model the checklist-only run made more theft errors
than the product on the cost-efficient model with the same rules (0.83
against 0.58; registered secondary S7c, +0.25, p = 0.078); the rule part is
the same in both (0.333; range 0.22 to 0.44 over two uncertain mappings,
give the range wherever the number appears); the excess is the frontier
model's readings of two broadly worded conditions (third party admitted true
in 8 of 8 ordinary texts by the frontier model, in none by the
cost-efficient one). Section 6.7's title becomes plain: "Theft on the
frontier model". 

**Reviewed rules (M5).** Section 6.1 and 7.1 say plainly: the review was done
by AI sessions that knew the test conditions; it made both single prompts
worse, mostly on documents no changed rule names; H1, H4 and H5 use the
reviewed rules; CasePath with the original rules was not run. Beside H1,
report the registered secondary S4c (0.58 against 1.47, p = 0.0117). On the
frontier model give the exact superiority p for 0.58 against 0.67 and call
the bootstrap non-inferiority share uncalibrated. State that the best
single-prompt theft result (0.67) came with the rules the review replaced.

**Readings of the rules (M6).** 6.6 says: the clean-room bundle contained
the machine-readable process catalogue, so exact agreement checks the
engine's implementation of that catalogue under the prose rules, not the
interpretation of the law; the alternative references were written by one
evaluator, after the clean room, to our instruction, and are not independent
evidence; the told/not-told asymmetry affects A2 and A4 too, so A2 and A4 are
argued from the unchanged-workflow rows; under all four readings six
registered tenancy contrasts reverse significantly. 7.1 adds: whether a
denied defining event ends the process is the one interpretive choice on
which most of the tenancy effect rests; under the other reading the
remaining lead rests on the nine open-event claims; no lawyer has ruled on
it.

**Cost (M7).** Both ratios wherever cost is summarised: the full product
costs about 20 times (tenancy) and 42 times (theft) the same-model single
prompt and 2.1 and 7.4 times the frontier prompt; checklist only about 4 and
7 times the same-model prompt (compute all ratios by macro). Table 5 gets a
ratio column. Times are lower bounds (cached calls took no time). The
frontier checklist-only run costs more per tenancy claim than the full
product on the cost-efficient model; say so.

**Lint (M8).** Out of the contributions. Contribution (2) is the artefact
and its design knowledge. The lint is "a proposed diagnostic", described in
6.7 only (Section 4.3 is deleted; one sentence in 4 may point forward), with
flag counts beside hits (theft 12 and 14 flags; tenancy 8 and 9 of 10), the
statement that the mutations were written by the analyst who designed it and
only blunt widening was tested, and the out-of-sample failure.

**Labels and multiplicity (M9).** Every number in the abstract,
introduction and conclusion is marked registered or added after review by a
phrase. Section 6 opens its post hoc part with: "Post hoc p values are
descriptive and not corrected for multiplicity." Principle 1's evidence is
"registered secondary, descriptive". "More samples did not close the gap"
becomes exact: significant on tenancy, not on theft.

**Abstract (M10 and 1.4).** Install this text, every number through its
macro (add macros where missing; cost ratios by macro), then count words
(at most 250):

> Case handlers must request evidence before a file settles the deciding
> facts. In CasePath, a model reads each such fact three times and must
> quote the file. Code admits a value only when the readings agree, executes
> the rules of a workflow, and holds every request that depends on an open
> fact. We tested a frozen commit on sealed synthetic claims under a
> pre-registered plan, against designs that give the same model the same
> rules. On tenancy it made 0.31 strict unsafe errors per claim, against
> 2.14 for a single prompt applying the rules on the same cost-efficient
> model and 1.86 on a frontier model, and it held 97% of the documents the
> reference holds, against 48% and 35%. On theft it made 0.58 errors per
> pair against 1.74 for the same-model prompt. These three hypotheses were
> confirmed; its theft lead over self-consistency (1.21) missed
> significance, so a fourth failed and a fifth was not tested. Analyses
> added after review mark the boundaries. The tenancy lead lies in claims
> with an open fact or a denied or open defining event; where every fact is
> stated there is no advantage over the frontier prompt. Most of it rests on
> reading a denied defining event as ending the process. On the frontier
> model, run once, CasePath led on tenancy and not on theft. The full
> product costs 20 to 42 times the same-model prompt and holds more than
> needed. Texts, references and rule reviews were made by AI sessions and
> the authors and checked by no jurist; one confirmation depends on a
> reordering of the hypotheses before the freeze. Code, synthetic data and
> analysis will be released.

If a number in it disagrees with a source, the source wins; tell the planner.

**Smaller decisions.** "Unsafe" is "strict unsafe" throughout, defined once
in full at first use (all five kinds). Holm in Table 6 uses the exact
non-inferiority p for H5; the bootstrap version goes to a footnote. H5's
margin (0.25) and test are stated in 6.2. Proposition 3.3(a) becomes an
observation or is folded into the definition. "Model executes rules" is
reconciled with the plan's name for it and with Section 2. Appendix B and
Section 5 say exactly where the eleven dossiers come from, as the protocol
draft says (an internal hackathon's dossiers), without calling them more
than the draft does; if the draft is unclear, leave a `%% AUTHORS:` line.
"Released" is "will be released" until Appendix D's choice is made. Table 10
and Table 8 use one unit. Apply Part 4 (cuts, figure and table notes, terms
defined before use, the quoted prose) and the ten sentence rewrites, or
better ones. The body may grow to 8,800 words if the additions need it; the
main PDF stays at 35 pages or fewer.

## Deliver

Clean build of both documents; `verify_paper.py --paper-only` passing; tests
of every script touched; the report's 10 major and 23 minor items and Part
2's numbered items listed one by one as "closed" with the place, or the
reason it is not; word and page counts.
