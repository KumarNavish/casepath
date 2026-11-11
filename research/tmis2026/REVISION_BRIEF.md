# Revision brief after the independent referee read and the claims audit (2026-11-11)

Binding for the revision writer. Inputs, read in full before editing:

- the referee's report: `/tmp/claude-0/-home-user-casepath/ef865128-25b1-5a5b-af7f-a334bf6c5b16/scratchpad/referee/REVIEW.md`
  (copy kept in `analysis/review/REFEREE_REVIEW.md` once committed);
- the claims audit: `/tmp/claude-0/-home-user-casepath/ef865128-25b1-5a5b-af7f-a334bf6c5b16/scratchpad/audit/CLAIMS_AUDIT.md`
  (copy in `analysis/review/CLAIMS_AUDIT.md`);
- the analyses added after review: `analysis/study3_review.md` with macros in
  `paper/results/numbers_study3_review.tex` (prefix `\sthreeR`);
- verified references: `paper/references_added.bib` and
  `analysis/REFERENCES_ADDED.md`;
- `PAPER_BLUEPRINT.md` (terms, style, binding wording of results).

Every audit finding is to be fixed as the audit's corrected text says, unless a
decision below says otherwise. Every referee concern is to be answered by a
change in the paper; the decisions below say how. Nothing may be claimed that
the results, the code at the tested commit or the records do not support.

## Decisions

**D1. What the paper is.** A design-science paper: a problem class, an
artefact, design knowledge with boundary conditions, and one confirmatory
evaluation. Say so in two sentences of the introduction and structure the
discussion around the design principles, each with its evidence and its
boundary condition. Cite the design-science sources only if they are in
`references_added.bib`. No new section; no jargon beyond "design principle"
and "boundary condition".

**D2. Contributions: three.** (1) The decision rule and its properties, with
their scope. (2) The artefact, CasePath, and the design knowledge from
building it over three studies. (3) A pre-registered confirmatory evaluation
on sealed data. The release and the expert-study protocol are named after the
list as resources, not contributions.

**D3. The expert study leaves the body.** It is a protocol at version 1.0-rc,
to be frozen before the first session; do not call it registered anywhere.
Section 7 is removed. One paragraph (at most 150 words) at the end of the
discussion says what the study will ask and points to Appendix I. Correct
Appendix I and that paragraph for the source of P: transcribed and mapped by
the product builder's automated labeller before any run on the cut copy,
checked by the study lead, who is an author and not a claims expert. Add the
referee's design issues as stated limits of the protocol in Appendix I
(interface differs from the tested commit; cases seen in development; an
expert may have handled a file before; the single test's floor). Leave a
marked `%% AUTHORS:` line for the ethics statement. The section returns when
the sessions have produced results.

**D4. Length.** Appendices B and C (Studies 1 and 2 in full), D.1–D.2 and
F.1–F.2 move to a separate supplement (`paper/supplement.tex`, built to
`supplement.pdf`, same class, own title "Supplement: Studies 1 and 2"), with
Table 13 marked "superseded by Study 2 and by the confirmatory test" in its
caption. The main paper keeps Section 5 and the root-cause table, Appendix A
(proofs), D (Study 3 only), E (data, shortened to what Study 3 needs, the rest
to the supplement), F (Study 3 only), G, H (the reading form, the four
comparator prompts, the silence clause and the two workflow excerpts; the rest
to the supplement), I. References to moved material say "Supplement, Section
…". Section 6 introduces the name "Study 3" for the confirmatory test.

**D5. Scope stated where the claim is made** (abstract, introduction,
conclusion):
- "the product at a frozen commit", not "the released product"; "we release
  the code, the research workflows, the synthetic data and the analysis";
- the tenancy references are produced by the engine CasePath implements,
  under a silence clause every design receives;
- the tenancy difference lies in the 33 claims whose defining event is
  denied or left open; on the other 63 there is no difference from the
  frontier model (and a descriptive difference from the same model, which the
  plan did not predict);
- the theft rules were reviewed for execution, with knowledge of the test
  conditions; against the single prompt with its original rules the same-model
  contrast is still large and the frontier contrast small (give both);
- "held 97%" is tenancy, against the engine's reference, and comes with more
  unneeded holds (give the number);
- the cost ratios name their regime.
Use the supported versions in the referee's list (e) and the audit's corrected
sentences.

**D6. The agents.** Fix the attribution everywhere: the brief and the process
builder run before the readings; say "the agents that cannot decide the
checklist" (brief, process builder, result checker). Report from the review
analyses: the share of case-runs in which the full product's and the
checklist-only run's checklists are identical, and one reconciled cost
statement. Say "no need added by an agent entered a scored checklist" and "no
detectable difference in errors", never "changed no checklist", "on any
measure" or "cost most of a run". Design principle 4 becomes conditional: the
brief and the reply draft may be worth their cost to a handler, which this
paper does not measure. The frontier-model row is named "CasePath, checklist
only, on the frontier model (one run)" everywhere.

**D7. The run.** Five invocations; four stopped early: two deliberately (the
operator's interrupt of the first to raise parallelism, whose log line is
wrong and corrected by a dated note; the wrapper's planned stop of the
fourth) and two by failures (the session's time limit; a container restart).
Fix Section 6, Appendix D and the macros (`make_numbers_study3.py` may be
edited for this). Settings: the commit's defaults plus the reasoning flag
turned on; say what the flag does for the independence of the readings and
how the response cache keys a call (so that the three readings of one run are
different calls). Add a dated timeline table to Section 6.1 (plan commits,
sealing of `fresh/` and `fresh2/`, the probe, the open-rule decision, the
product freeze, run start and end, analysis), from git and the run log. Model
identities: give provider route, model identifiers as sent, reasoning effort
and sampling settings from the run manifest and the harness; if a detail is
not recorded, say "not recorded".

**D8. Independence of the test data.** State exactly: the texts of `fresh2/`
were written by an AI agent session working in the repository, from a brief
that contained only the data design; the session had read access to the
repository, including the product's prompts and development results, and was
instructed to consult no design output; it implemented no product change; the
blind check ran in separate sessions of another model of the same family;
data writing and product development were directed by the same author through
separate agent sessions. State the risk in one sentence. The open-rule
decision: who reviewed (an independent AI review session of the code), what
was overruled (a numerical criterion on wrong holds set by the directing
author), when (after the probe, before the freeze and before any sealed
datum was read by a design).

**D9. Formal section.** Put the scope into the statements: the flow fragment
(and that both evaluated workflows lie in it; check against Appendix A and say
what is true), independent two-valued facts (say how enum- and value-typed
facts are handled in the product, from the code, and that related facts can
make exact deferral hold more than a feasible-completion semantics would),
and the cut-off above eight open facts (reconcile with Study 1's twelve).
Give the admission rule once, as a small table of cases (all readings give the
same value with quotations found; readings give different values; only some
give a value; all answer not stated; any answers open with words found; a
presumption exists or not), true of the code at the tested commit for facts
that decide the checklist or the routing, and say that other facts are
recorded from one reading. Say that whether a document is present is decided
by two model judgments and lies outside the propositions. Specify the noise
model and units of the error-fate computation, or cut the computation to one
sentence if it cannot be specified from the scripts. Report the measured
fact-level accuracy of admitted values from the review analyses, including how
often all readings agreed on a wrong value, next to Proposition 4.

**D10. Statistics.** Keep the registered tests as the results. Explain in two
sentences why H4's bootstrap interval excludes zero while the exact test
gives 0.0625 (few clusters; the percentile bootstrap under-covers; the exact
test is the registered one). Give sign-flip-inverted intervals for the theft
hypotheses beside or instead of the bootstrap ones (from the review
analyses). Remove bootstrap non-inferiority p-values from the body; H5 is
"not tested" once, with its raw difference and interval in the appendix,
labelled outside the procedure. Report the stories-as-clusters sensitivity in
one sentence with a pointer. Add the family-level plot to Appendix F.

**D11. New results in the body, each short and labelled "added after
review":** claim-level outcomes (one compact table: share of exactly correct
checklists per design and subset); tenancy under other mixes of claim types
(two sentences); fact-level accuracy (one small table, in Section 6 after the
hypotheses); the stress test of presumptions (one paragraph: how the
difference changes when 5, 10 and 20% of unmentioned facts are true); what the
single prompts wrote on denied-event claims (two sentences and one verbatim
example); why the reviewed rules hurt the single prompts (what the data show,
two or three sentences). Everything else from the review analyses goes to
Appendix F. Replace the worked example by the first denied-event claim in the
manifest's order, say that it was chosen by that rule after the results were
known, and show what each design did in each run; the earlier open-fact
example moves to Appendix F in one sentence.

**D12. Related work.** Add the lines of work the referee names, one sentence
each, only with verified entries: design science; case management and
declarative or artifact-centric process models; three-valued reasoning over
partial models; default reasoning and burden of proof; agreement-based
uncertainty and citation grounding for language models; value of information;
legal reasoning benchmarks; supervisory context. Table 1 loses its last two
columns. Mark reference [20] as a preprint in the text.

**D13. Limits and discussion.** Add: files of 77–320 words, so the long-file
paths were never exercised; the silence clause was written by the researchers,
not taken from the insurer; latency (from the review analyses) and what it
means next to a handler's time; exact deferral added nothing over "unresolved
= false" on theft changed-fact pairs (principle 2 is supported on tenancy and
on theft's unresolved-fact pairs only: check which, from the tables); wrong
presumptions were not tested except by the stress test; the ShARC pilot is
described exactly (what was run, on what, why) and no cross-dataset claim
rests on it. A short paragraph "For an organisation": who writes and reviews
workflows and presumptions and what the review found necessary; what a wrong
presumption costs and who answers for it; what the record of quotations and
held requests gives an auditor; how holds change a handler's work. Only what
this paper's evidence or the product's design supports.

**D14. Front matter the authors must supply** (leave marked `%% AUTHORS:`
comment lines, do not invent): conflict of interest and roles (authors'
relation to the insurer and to the product's owners); disclosure of the
conference version and what is new; ethics statement for the expert study;
the AI-assistant tool name required by the venue; licences for the three
newer data folders.

**D15. All 23 minor concerns of the referee and the remaining audit findings**
are fixed (terms glossed at first use; figure captions; Figure 2 caption;
Figures 1 and 2 request sets explained; the normalisation for quotation
matching stated from the code; "cost-matched" removed; Table 5 cleaned;
Knowledge shortened to one paragraph and Table 1's claim removed; parity
described as proof of identical code; the Study 1 tenancy figure in Section 5
corrected to the registered test with the sensitivity result labelled; "as the
plan predicted" completed; reference entries repaired).

## Word budget after revision

Body at most 9,000 words; Section 6 may grow to 2,600. Cut elsewhere to pay
for additions: Section 4 (Knowledge, interface), Section 2 (one sentence per
line of work).

## What not to do

Do not re-run or edit the registered analysis. Do not remove a failure or an
irregularity. Do not add a result that is not in the stored analyses. Do not
soften a limit into a footnote: a limit is stated where its claim is made.

## Added after the release check (D16)

Appendix G must be true of a fresh clone. `reproduce.sh` reproduces every
Study 3 table and macro and re-checks Studies 1 and 2 from stored outputs in
about ten minutes without model calls (39 steps; say what is and is not
re-checked, from `RELEASE.md`). The response caches of Study 3 are not in the
repository (about 23,000 files, 730 MB, ignored by git): do not say they are
released or that a re-run is answered from them; say that stored checklists,
ledgers and the run log are in the repository and that the cache is offered
as a separate archive (leave a marked `%% AUTHORS:` line for its location). A
re-run with model calls needs the reader's own model endpoint; say so. The
product source at the tested commit names the insurer's subsidiary as the
default organisation and ships a Knowledge seed derived from its letters:
Appendix G says that the public release is a scrubbed commit whose parity
hash is reported beside the tested one, or the tested commit with the
insurer's approval; leave a marked `%% AUTHORS:` line for the choice. The
analyses added after review (`analysis/study3_review.py`) are to be covered
by `reproduce.sh`; tell the planner which step to add rather than editing the
script.
