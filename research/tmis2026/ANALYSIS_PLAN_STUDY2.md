# Analysis plan, Study 2 (frozen before any design runs on the fresh data)

Date: 2026-11-10. This file and the scoring code named below are committed
before the first model call on `fresh/`. The runner refuses to start on fresh
data unless this file is committed unmodified. Development used only the
Study 1 data (tenancy development families; theft stories 0–2). Background and
the development history are in `STUDY2_DESIGN.md`, `WORKLOG.md` and
`runs/v2/`.

## 1. Question

Does CasePath v2, the agent after the root-cause fixes that Study 1 motivated,
request evidence better than a model that applies the same rules itself, when
both run on cases no model has been run on?

## 2. Data (sealed; hashes in `fresh/MANIFEST.json`)

- Theft: four new stories (4–7), nine changed-fact pairs and six
  unresolved-fact pairs each; references from the frozen source contract.
- Tenancy: 72 new claims in 18 families, flag combinations unused in Study 1,
  18 claims with one fact raised and left open, 38 attachments (18 sufficient).
  References are computed by the engine from the true scenario under the
  stated silence policy.

Known limits, fixed here so they are not discovered later: tenancy references
come from the same engine and silence policy that v2 implements, so this
regime tests rule application given the policy, and every design receives the
policy clause; messages that a blind reader misread were rewritten or
replaced, so claims are explicit; the theft stories reuse the nine conditions
and the 98 extracted rules of Study 1, so they test new settings, not new
rules, and the rule-repair pass was developed with knowledge of which rules
are faulty.

## 3. Designs

All designs receive the same case text, catalogue and case-reading
instructions, low reasoning effort and schema-constrained output.

- **CasePath v2** (`CPv2p`): one interpretation call records a judgment with
  quotation for every rule condition; code admits a true or false verdict only
  if its quotation is located in the case after the fixed normalisation; the
  rule pack is the verified pack (flagged rules stay in force and are listed
  for review); the tenancy pack's presumption clause applies (the dispute's
  defining event is presumed unless the claim denies it; a branch fact is
  presumed absent only when nothing was quoted for it); code executes the
  rules with exact deferral. No verifier call (development showed the
  evidence-bearing verifier changes no plan).
- **Rules in context, same pack** (`B1v2p` tenancy, `Rv2p` theft): the model
  applies the rules itself, given the same pack and the same presumption
  clause.
- **Rules in context, original pack** (`R`, theft): the Study 1 baseline.
- **CasePath v1** (`CPv1`, gpt-6-luna only): the Study 1 configuration, for
  the ablation.

Models: gpt-6-luna and gpt-6.1-terra, three runs per case (k = 3). CPv1 runs
with gpt-6-luna only.

## 4. Measures

Tenancy, per claim-run, against the fresh reference:
- A document the reference marks *required now*: requested (correct), held,
  handed over (whole claim), or missed.
- A document the reference marks *held* (it depends on the fact left open):
  held (correct); requested = premature request; skipped = silent skip.
- A document the reference marks not needed, or supplied and sufficient:
  requested = unnecessary request.
- **Strict unsafe errors per claim** (primary) = unnecessary requests +
  missed + handed-over required documents + premature requests + silent skips.
- Requested share of required-now documents; held required-now documents per
  claim; holds of documents that are neither required now nor held in the
  reference; correct holds as a share of reference-held documents.

Theft, per changed-fact pair-run, with the frozen `best_realization` scorer:
wrong changes, missed changes, and **wrong + missed changes per pair**
(primary); F1. Per unresolved-fact pair-run: premature request of the open
condition's documents; any other change (reported, not primary).

A failed output is an empty plan. Cost per case from the ledger.

Scoring conventions, fixed with the scoring code before any run: a supplied
but insufficient document counts as required now; a document a plan both
requests and holds counts as requested; when a claim is handed over, its
required-now documents count as handed over (unsafe) and its reference-held
documents as deferred (not unsafe); a request for a document outside the
reference is an unnecessary request; shares are pooled ratios over documents;
CasePath v1 is scored on its production (strong Kleene) plan; a bootstrap
non-inferiority p of 0 means that none of the 10,000 resamples reached the
margin and is reported as p < 0.0001.

## 5. Primary contrasts (Holm over these four)

Clusters: the nine changed facts for theft (pairs from the four stories and
three runs averaged within a fact); the 18 families for tenancy (claims and
runs averaged within a family).

- **A. Theft, same model.** CasePath v2 vs Rules in context with the same
  pack, gpt-6-luna: wrong + missed per pair. Two-sided exact sign-flip test.
- **B. Tenancy, same model.** CasePath v2 vs Rules in context with the same
  pack, gpt-6-luna: strict unsafe errors per claim. Two-sided exact sign-flip
  test.
- **C. Theft, against the frontier baseline.** CasePath v2 with gpt-6-luna vs
  Rules in context with the original pack on gpt-6.1-terra: wrong + missed per
  pair. Non-inferiority with margin 0.25 per pair: p = share of paired
  cluster-bootstrap resamples (10,000) in which the difference (v2 − baseline)
  is at least the margin.
- **D. Tenancy, against the frontier baseline.** CasePath v2 with gpt-6-luna
  vs Rules in context with the same pack on gpt-6.1-terra: strict unsafe
  errors per claim. Non-inferiority with margin 0.10 per claim, same test.

Every contrast is reported with the two values, the paired difference, its
95% cluster-bootstrap interval, the number of clusters and of non-zero
clusters, and the smallest attainable p. For C and D the two-sided
superiority test is also reported. The margins were chosen before the fresh
data were opened, as about half of the corresponding development differences
between the designs.

## 6. Secondary analyses (reported in full, not in the Holm family)

- The same-model contrasts with gpt-6.1-terra (A and B with terra on both
  sides), and CasePath v2 with terra against both theft baselines.
- A with the original pack as comparator (gpt-6-luna).
- Requested share on tenancy: v2 vs Rules in context, both models, with a
  five-point non-inferiority margin.
- Unresolved-fact pairs: premature requests and other changes.
- Open-fact tenancy claims: correct holds, premature requests, silent skips.
- Cost per case; the cross-model cost ratio for C and D.
- Ablation with gpt-6-luna: CPv1 vs CasePath v2, and, computed on the
  recorded judgments without model calls, v2 without the presumption clause,
  v2 with strong Kleene evaluation, v2 with the original pack, and v2 with
  the "two readings agree" admission (a verdict counts only if two of the
  three runs' readings agree, cyclic pairing). The original pack has eight
  conditions that the verified pack lacks; their judgments are obtained with
  one additional gpt-6-luna call per theft text, used for this ablation only.
- Sensitivities as in Study 1: repeated off-case errors counted once per
  story and run; all run pairings.
- Run-to-run agreement.

## 7. Evolution experiment (secondary)

gpt-6-luna. Both arms start from the verified pack. Handler corrections are
the reference answers for the pairs of story 4, given in order. CasePath v2
traces each wrong or missed request to a rule and applies a source-verified
typed repair or, if none passes, suspends the rule (regression-checked against
the earlier corrected pairs). The comparator is Rules in context with the same
corrections appended to its prompt as a memory. Both are then evaluated on
stories 5–7 (27 changed-fact pairs, three runs). Reported: wrong + missed per
pair on stories 5–7 before and after, for both arms, the paired difference of
the after values with its interval (clusters: changed facts), and what was
repaired or suspended.

## 8. Reporting

All results are reported whatever their direction, together with Study 1.
Anything not specified here is labelled post hoc. Scoring and tests are
implemented in `analysis/study2.py`, written and checked on oracle and
perturbed plans before any design output on fresh data exists.
