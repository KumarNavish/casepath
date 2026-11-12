# Referee report, round 3: "CasePath: Agents That Read, Rules That Decide"

Submission to ACM TMIS. Reviewed from main.pdf (31 pp.) and supplement.pdf. Part 1 was written from the submission alone, before any repository source was opened. Parts 2 to 4 were written after checking the sources named in the review brief, read-only.

---

## Part 1. From the paper alone

### 1.1 Summary in five sentences

1. The paper proposes a division of labour for deciding which documents to request on an insurance claim. A language model reads each deciding fact three times with a verbatim quotation. Code admits a value only when the readings agree and the quotation is found, then executes a source-cited workflow under "exact deferral" (supervaluation over the completions of the open facts). Exact deferral holds every document whose need an open fact could change.
2. Section 3 gives four short propositions. Soundness under strong Kleene evaluation, its over-holding at reconverging branches, the exactness of deferral, and how reading errors propagate are all proved for "flow workflows" over independent two-valued facts. The authors themselves describe the semantics as known and the application as new.
3. The empirical core is Study 3, one pre-registered test of a frozen commit on sealed synthetic data: 72 changed-fact and 48 unresolved-fact theft pairs from 8 stories and 9 changed facts, and 96 tenancy claims in 24 families. The comparators are a single prompt carrying the same rules, self-consistency, a semantics-stating prompt and ReAct, on a cost-efficient model (3 runs) and a frontier model. CasePath ran only once on the frontier model, and only in the checklist-only setting.
4. Three of five registered hypotheses were confirmed: H1 and H2 against the same-model prompt, and H3 against the frontier prompt on tenancy. H3 was tested only because the hypotheses were reordered 38 minutes before the freeze. H4 failed against self-consistency on theft (p = 0.0625), and H5 was therefore not tested. Most of the tenancy advantage comes from 33 claims that deny or leave open the defining event, which the test set over-represents by design.
5. A large set of post hoc checks follows: an error decomposition, a budget-matched comparison, a clean-room re-derivation of the references, sensitivity to four alternative readings of the rule text, and a reference-free "rule lint". They show that the design (a) gives no advantage over the frontier prompt on claims that state every fact, (b) does not beat the frontier prompt with the original rules on theft, (c) loses its tenancy lead when the product's workflow is scored under one rejected reading of the rule text, and (d) costs between about 2 and 42 times a single prompt, depending on which prompt is the reference.

### 1.2 Recommendation: major revision

The idea is sound and useful to IS and BPM readers. The engineering is careful, and the disclosure of deviations is unusually honest. The paper is not yet accurate enough to publish. Three reasons carry the recommendation:

1. **A factual and statistical error sits in the text of the central failed test.** Section 6.2 says that for H4 "CasePath had the lower mean in all nine clusters" yet the exact sign-flip test gave p = 0.0625. That is impossible. When all nine non-zero differences share a sign, the observed sum has the largest absolute value of all 2^9 sign patterns, so the exact two-sided p is 2/512 = 0.0039, the very minimum the paragraph quotes. The Supplement's Table S22 shows the truth: CasePath was worse on 2 of the 9 changed facts, one of them by 1.00 error per pair. The paragraph's explanation ("the differences are unequal in size, so sums as far from zero are not rare") is wrong as statistics. This is the hypothesis readers will look at most closely.
2. **The headline numbers lead with a post hoc subset, and they use a per-claim label for family means that differ substantially from the per-claim means.** The first numbers in the abstract and introduction (0.34 against 2.32 and 2.13 "unsafe errors per claim" on 56 "open" claims) come from a split added after review. The abstract does not say so. Table 8 calls them family means, while Figure 5 draws claim-run means for the same subsets. The two disagree badly: from Table S16, the per-claim mean of Rules in context on those 56 claims is about 3.39, not 2.32, and CasePath's is about 0.40, not 0.34. A reader cannot reconcile Table 8 with Figure 5 or with the overall means. The direction understates the baselines' errors, but a headline must be the quantity it claims to be.
3. **Several claims are worded more strongly than the paper's own evidence allows.**
   - "Every other design" held 27–47% of theft unresolved pairs, but Core, checklist only and two-valued "unresolved = false" held 85–95%.
   - The theft "holding" measure cannot tell holding from reading open as false (two-valued = 94%).
   - "The rules alone account for 0.333" is presented as a point fact, but the Supplement gives a range of 0.22 to 0.44 over two uncertain mappings.
   - "Costs several times a single prompt" is true only against the frontier prompt (2.1× and 7.4×). Against the same-model prompt the full product costs about 20× (tenancy) and 42× (theft).
   - The lint "found" the faulty conditions, but it flags 8–9 of 10 tenancy conditions and 3 of 5 untouched ones.
   - "The lead holds under alternative readings" rests on references that one evaluator wrote after the clean-room step and that the Supplement calls "not independent evidence"; two of the five rows are upper bounds.

None of these needs new model runs. All can be fixed by recomputation from stored outputs or by rewording. That is why the recommendation is major revision rather than reject.

### 1.3 What a first-time reader will not understand, by section

- **Abstract.**
  - "Open or denied deciding fact": the subset is actually "an open fact, or a denied or open *defining event*". Denied ordinary facts are not in it.
  - "Unsafe errors" is not defined.
  - "Run once" does not say that the frontier product was the checklist-only setting.
  - "Two blind AI evaluators reproduced the tenancy references exactly" does not say what that shows.
  - "Reverses under one when it does not" is cryptic without knowing what "the workflow follows them" means.
  - "The rules alone account for 0.333" uses a decomposition the abstract never introduces.
- **Section 1.**
  - "Strict unsafe" (Section 6) and "unsafe" (Section 1) are used for the same quantity.
  - The definition in Section 1 ("a request the rules do not allow or a needed document left out") omits premature requests, the dominant baseline error on open-event claims (Table S37).
  - "Reviewed rules" against "original rules" is used before Section 5 explains it.
  - "Self-consistency" is defined, but "prior-work design" is not.
  - The reader cannot tell why the frontier comparator has two rule bases.
- **Section 3.**
  - Proposition 3.3(a) restates Equation (3), so a reader will ask what is being proved.
  - "Flow workflow" is defined negatively ("no relation that blocks, suppresses or waits").
  - The 84.5 coincidence is explained only in Appendix A.
  - "Plain walk" first appears in 3.4 without a definition.
  - "Exact deferral never ran on theft" sits oddly with the claim that its output equals the plain walk there; a reader will wonder whether Principle 2 has any theft evidence (it has none).
- **Section 4.** "Second judgment", "document finder", "source checker" and "result checker" are introduced in one paragraph. "Parity command" and "Knowledge store" are named but not explained. The checklist-only setting skips the document finder for single-file claims, "whose needs then count as missing". The consequence for theft scoring is never stated: theft scores only requests, and every theft text is single-file.
- **Section 5.**
  - Table 3 mixes Study 1 and Study 2 evidence, frontier and cost-efficient models, and new and recomputed numbers.
  - "Label-free repair" is undefined.
  - "Four-eyes rule" first appears in Section 6.7.
  - The reader is never told that the theft *conditions* (the 9 changed facts) are the same in Studies 1–3. Section 7.1 says "theft reuses Study 1's conditions" only in passing.
- **Section 6.1.**
  - "Changed-fact pair" and "unresolved-fact pair" are defined, but how "errors per pair" handles the unresolved-fact pairs is not (they are scored separately as "unchanged").
  - "Silent skips", "handed-over" and "premature requests" are not defined.
  - "Family" is not defined (a family appears to be four variants of one dispute).
  - "No comparator text changed after 19:10" is unclear: a prompt? a rule text?
- **Section 6.2.**
  - The reader is not told what H5's non-inferiority margin is (0.25, stated only in the Supplement).
  - "Descriptive family means" with p values attached is confusing.
  - The H4 paragraph is wrong (see 1.2).
  - Table 6's footnote b mixes a bootstrap "p" that the Supplement says is "not a calibrated p" into a Holm correction.
- **Section 6.3.**
  - "Every such difference was significant except…" cites no table. The tenancy contrasts against Self-consistency, Model executes rules and ReAct are secondary contrasts S2a–S2c (Table S19), uncorrected for multiplicity.
  - The decomposition's "their sum does not depend on the order" is trivially true. The parts do depend on the order, and the reader is not told by how much.
- **Section 6.4.**
  - Table 8 and Figure 5 disagree (family means against claim-run means).
  - "For any share above 0% to 1.7%" is not parseable on first reading.
  - Figure 5 keeps the mix *within* the open subset fixed at the test's 24:9:23 proportions, and this is not said.
- **Section 6.5.**
  - "Matched budget" is defined relative to checklist only, not to the product the paper names CasePath.
  - The hollow diamond in Figure 6 "is not the same quantity as m = 1", and nothing explains why.
- **Section 6.6.**
  - "Rejected reading": rejected by whom, and on what basis?
  - The four alternative references were written by one evaluator after the clean room (Supplement S13.4). This is crucial and absent from the main text.
  - "Upper bounds" for A3 and "all four" is explained in one sentence.
- **Section 6.7.**
  - The "traces" condition is never explained.
  - "In sample" means flags computed on the test texts themselves.
  - Table 10's "Unchanged" is a fraction (0.750), while Table 8 gives a percentage (75).
  - "Held: documents held in every ordinary text" is not a rate.
- **Section 7.**
  - Principle 1 calls the subset values "Registered". Section 6.2 calls the same family of values "descriptive", and the numbers differ (0.47/5.69 in 6.2 against 0.61/0.26 and 5.68/4.63 in 7), because one set is family means and the other claim means.
  - Principle 2's post hoc figures (0.25 against 0.23, 0.65 against 1.31) are on a 277-claim-run subset with a different scorer basis (Table S28), and the text does not say so.

### 1.4 Does the abstract's headline match Section 6? Sentence by sentence

| # | Abstract sentence (abridged) | Supported by Section 6? |
|---|---|---|
| 1 | "Case handlers must request evidence before a file settles the deciding facts." | Framing; fine. |
| 2 | "In CasePath, a model reads each such fact several times and must quote the file." | Yes (Section 4). "Several" is three by default, and one reading in the k = 1 replay. |
| 3 | "Code admits a value only when the readings agree, executes the organisation's rules, and holds every request that depends on an open fact." | Partly. Table 2 also admits a presumed value when some readings give it and others none. "Every request that depends on an open fact" is true only under exact deferral (≤ 8 open facts), and on theft only via the plain-walk equivalence. "Organisation's rules": the theft rules were extracted by a model and reviewed by AI sessions, and the tenancy rules were written by the authors. No organisation's rules were tested. |
| 4 | "We tested a frozen commit on sealed synthetic claims under a pre-registered plan, against designs that give the same model the same rules." | Yes, with caveats the abstract omits: the texts were AI-written by a session that could read the product's prompts, and the theft rules were reviewed by sessions that knew the test conditions. |
| 5 | "On tenancy claims with an open or denied deciding fact it made 0.34 unsafe errors per claim; a single prompt applying the rules made 2.32 … and 2.13 …" | **Not as worded.** The split is post hoc and unlabelled here. The numbers are family means; the per-claim means are about 0.40 / 3.39 / 3.06 (from Table S16). The subset is mislabelled ("denied deciding fact" should be "denied defining event"). |
| 6 | "Where every fact was stated it had no advantage over the frontier prompt (0.22 against 0.19)." | Yes (post hoc, p = 0.90). Honest. It should add that the same-model comparison on these claims is 0.22 against 0.40. |
| 7 | "On the cost-efficient model its mean error was below that of every single-prompt and prior-work design on tenancy and on theft;" | Yes for point estimates. |
| 8 | "three of five registered hypotheses were confirmed, and its theft lead over self-consistency missed significance." | Yes. It omits that one confirmation (H3) depends on a reordering made 38 minutes before the freeze, which the introduction does disclose. That belongs in the abstract. |
| 9 | "More samples of the same prompt did not close the gap." | **Overstated for theft.** At matched budget the theft difference was −0.53, p = 0.13, not significant. Tenancy is supported (p = 0.0006). Post hoc and unlabelled. |
| 10 | "On the frontier model, run once, it led on tenancy and had no advantage on theft, where the rules alone account for 0.333 of its 0.833 errors per pair." | Partly. "It" was checklist-only, not the product. "No advantage" understates: its theft mean (0.83) was *above* the frontier prompt with the original rules (0.67) and above the cost-efficient CasePath (0.58; S7c, p = 0.078). The 0.333 depends on two uncertain mappings (range 0.22–0.44, Supplement S11.4). Post hoc. |
| 11 | "Two blind AI evaluators reproduced the tenancy references exactly." | True, but it shows only that two AI sessions read the rule text the way the engine does. It does not show that the rule text was read correctly, and no person checked them. One session saw the file names of other work. |
| 12 | "The lead holds under alternative readings of the rules when the workflow follows them, and reverses under one when it does not." | Partly. Only A1, A2 and A4 count as evidence (A3 and "all four" are upper bounds). The alternative references were written by one evaluator to an instruction after the clean room and are "not independent evidence" (S13.4). Under "all four", H2 and H3 reverse significantly with the unchanged workflow; "reverses under one" omits that. |
| 13 | "The design holds more than needed and costs several times a single prompt." | **Understated.** Against the same-model single prompt the full product costs about 20× (tenancy) and 42× (theft). "Several times" holds only against the frontier prompt (2.1× and 7.4×). |
| 14 | "Code, synthetic data and analysis are released." | Section D says release of the tested commit needs the insurer's approval or a scrubbed commit with a different hash. "Are released" is too strong while that is pending. |

**Verdict on the headline.** The introduction's "main finding is that the design holds what the file leaves open" is supported on tenancy, by registered evidence (97% held against 48% and 35%). On theft the registered "unchanged" share does not distinguish holding from reading open as false. The abstract leads with a post hoc number mislabelled as per-claim. The registered H2/H3 contrasts (0.31 against 2.14 and 1.86) are the evidence that should carry the headline.

---

## Part 2. Claims checked against the sources

**Method.** Each item gives the sentence as printed, the source location (path relative to `research/tmis2026/`, with line numbers), what the source says, and a corrected sentence. Items are grouped by topic, not by page.

**Sources read (read-only):**
- `ANALYSIS_PLAN_STUDY3.md`
- `analysis/study3_results_fresh2_confirm.md` (registered output)
- `analysis/study3_review.md`
- `analysis/study3_feedback.md`
- `analysis/decomposition.md`
- `analysis/lint_followup.md`
- `cleanroom/README.md`
- `expert_study/PREREGISTRATION_DRAFT.md`

**Labels used below:**
- *R*: registered (primary, or a registered secondary analysis of plan §7).
- *P*: post hoc, made after the results.

**Items that match their source exactly.** Every primary number of Table 6 matches the registered output (`analysis/study3_results_fresh2_confirm.md` l. 70–80). So do:
- every overall tenancy and theft mean in Table 7;
- the subset per-claim values in Section 7 (l. 127–195);
- the cost per case and the ratios to the frontier prompt (l. 248, 263);
- the budget numbers of Section 6.5 (`study3_feedback.md` l. 215–263);
- the S/O crossovers (l. 141–175);
- Table 9 (l. 282–289, 560–609);
- Table 10 (`lint_followup.md` l. 35–39, 72–81);
- the mutation counts (`lint_followup.md` l. 119);
- the 9-of-1344 count (`study3_review.md` l. 125).

The problems are in wording, labelling and omissions, plus one factual error.

### 2.1 A factual error

**(1) Section 6.2, H4 paragraph.**
- *Printed:* "its smallest attainable p is 0.0039, and it returned 0.0625, although CasePath had the lower mean in all nine clusters. The differences are unequal in size, so sums as far from zero are not rare."
- *Source:* the registered table gives "9 / 9" as clusters / *non-zero* clusters (`study3_results_fresh2_confirm.md` l. 77). `study3_feedback.md` l. 205: "CasePath had fewer errors in 7 clusters and more in 2 … largest difference against CasePath 1.000". `study3_review.md` l. 213 lists the nine differences: two are positive, +0.125 (expert procedure) and +1.000 (third party).
- *Why it matters:* with all nine differences of one sign, the exact test would have returned 2/512 = 0.0039. The sentence is both false and impossible.
- *Corrected:* "Its smallest attainable p is 0.0039. It returned 0.0625: CasePath had fewer errors on 7 of the 9 changed facts and more on 2, one of them by 1.00 error per pair (third party caused the loss; Supplement, Table S22), and 32 of the 512 sign patterns give a sum at least as far from zero."

### 2.2 Subset numbers, per-claim labels and registration status

**(2) Abstract, sentence 5, and Introduction, paragraph 4.**
- *Printed:* "On tenancy claims with an open or denied deciding fact it made 0.34 unsafe errors per claim; a single prompt applying the rules made 2.32 on a cost-efficient model and 2.13 on a frontier model."
- *Source:* `study3_feedback.md` l. 3 marks F1 as post hoc. At l. 15–22 the 0.337, 2.323 and 2.128 are *family means*. The claim-run (per-claim) means are 0.399, 3.387 and 3.060. The subset is "an open fact or a denied or open defining event" (l. 7, 11). Denied ordinary facts are not in it.
- *Corrected:* "On the 56 tenancy claims that leave a fact open or deny or leave open the dispute's defining event (an analysis added after review), CasePath made 0.40 strict unsafe errors per claim, against 3.39 and 3.06 for a single prompt with the same rules on the cost-efficient and the frontier model."
- *Alternative:* keep the family means and call them that, not "per claim".

**(3) Section 6.4.**
- *Printed:* "On the 56 claims … CasePath made 0.34 strict unsafe errors per claim; Rules in context made 2.32 … and 2.13 …, and Self-consistency 2.24 (each p ≤ 0.0001)."
- *Source:* as in (2). The p values are family-cluster sign-flip tests (F1 l. 47, 53, 71), descriptive and uncorrected. Self-consistency's p is 0.0001 exactly, so "≤ 0.0001" is fine.
- *Corrected:* "… made 0.34 strict unsafe errors per claim as a family mean (0.40 per claim-run); Rules in context 2.32 (3.39) …"
- *Also needed:* say that the large differences sit in the 9 families that contain denied- or open-event claims (`study3_review.md` l. 223–231).

**(4) Table 8 against Figure 5.**
- *Source:* Table 8's S and O columns are family means. Figure 5's endpoints are claim-run means (`study3_feedback.md` l. 133–139). For Rules in context, O is 2.32 in Table 8 and 3.39 in Figure 5.
- *Correction:* use one quantity in both, or print both columns in Table 8.

**(5) Section 6.2.**
- *Printed:* "These subset rows are descriptive family means (Supplement, Table S16)."
- *Source:* the family means are in the registered output (`study3_results_fresh2_confirm.md` l. 72–76). Table S16 holds the *claim* means (0.61, 0.26 and so on), which do not reproduce 0.47, 5.69 or 5.31.
- *Corrected:* "… descriptive family means, reported beside each tenancy hypothesis as the plan requires; Supplement, Table S16 gives the per-claim values."

**(6) Section 7, Principle 1.**
- *Printed:* "Registered: on the 24 denied-event and 9 open-event tenancy claims, CasePath made 0.61 and 0.26 …"
- *Source:* these are registered *secondary* per-claim values (plan §7 l. 166; results l. 127–167). Section 6.2 calls the parallel numbers "descriptive". The labels are inconsistent, not wrong.
- *Corrected:* "Registered secondary analysis, descriptive: …"

### 2.3 "All", "every" and "each" statements

**(7) Introduction and Section 6.4.**
- *Printed:* "CasePath left 94% of theft pairs with an unresolved fact otherwise unchanged, against 27–47% for every other design given the reviewed rules."
- *Source:* `study3_results_fresh2_confirm.md` l. 228–240 gives these unchanged shares with the reviewed rules:
  - CasePath, checklist only: 95.1%
  - Two-valued, unresolved = false: 94.4%
  - Core: 84.7%
  - CasePath, checklist only, frontier: 75.0%
- *Corrected:* "… against 27–47% for every single-prompt and prior-work design given the reviewed rules (91% for the frontier prompt with the original rules)."
- *Also add:* "On theft this measure does not separate holding from treating an open fact as false: two-valued execution with unresolved taken as false scores the same 94%" (`study3_review.md` l. 417: "unresolved = false gives exactly CasePath's requests in 384 of 384 text-runs").

**(8) Section 6.3.**
- *Printed:* "… every such difference was significant except the theft difference from Self-consistency."
- *Source:* the statement is true. It mixes registered primary tests (H1, H2, H4.2, H4.3) with registered secondary contrasts (S2a–S2c, S4c; results l. 96–106), and none of them is corrected for multiplicity.
- *Corrected:* "… every such difference had p < 0.05 except the theft difference from Self-consistency (registered primary tests H1, H2 and H4, and the plan's secondary contrasts S2a–S2c and S4c, uncorrected)."

**(9) Section 6.6.**
- *Printed:* "the lead holds under every reading we can read as evidence."
- *Source:* `study3_feedback.md` l. 269 says the told/not-told asymmetry applies wherever "a reading changes what the registered rule text told every design (A2, A3, A4)". The paper treats only A3 and "all four" as upper bounds. For A2 and A4 the *unchanged-workflow* contrasts, where nobody was told the reading, hold: −1.43 / −1.01 and −1.83 / −1.55 (l. 570–599). The conclusion therefore survives, but the evidence for A2 and A4 should come from those rows.
- *Corrected:* "Under A2 and A4 the lead holds with the product's workflow unchanged, so no design was told the reading. Under A1 it holds once the workflow encodes the reading, a comparison that favours the baselines. A3 and the four readings together favour the product and are upper bounds."

**(10) Section 6.6.**
- *Printed:* "With all four readings together, H2's contrast reverses significantly (+0.94, p = 0.0234)."
- *Source:* `study3_feedback.md` l. 600–609. With all four readings, H3 also reverses (+0.75, p = 0.0472), and so do S2a, S2d, S3a and S3b. Six of the ten tenancy contrasts reverse with p < 0.05.
- *Corrected:* "With all four readings together, six of the ten registered tenancy contrasts reverse with p < 0.05, among them H2 (+0.94, p = 0.0234) and H3 (+0.75, p = 0.0472)."

**(11) Section 3.5 and Principle 3.**
- *Printed:* "9 of 1344 tenancy fact values used by CasePath were admitted with a wrong value."
- *Source:* `study3_review.md` l. 108–125. The 1344 includes 417 unmentioned facts, 394 of them presumed. On the fact that matters most, a *denied defining event*, the full product admitted a wrong value in 6 of 72 claim-runs and left 12 conflicting (l. 117–119, 134). That fact drives 0.611 errors per denied-event claim (`decomposition.md` l. 34).
- *Corrected:* "Over 1344 fact × claim-runs, 9 values were admitted wrong, in each case with all readings agreeing. Six of them concerned a denied defining event (6 of its 72 claim-runs, with 12 more left conflicting), and these caused most of CasePath's tenancy errors."

### 2.4 p values and the tests that produced them

**(12) Table 6, Holm column, H5 (0.0005).**
- *Source:* `study3_feedback.md` l. 183–203. The 0.0005 comes from a bootstrap "share" that the Supplement itself calls "not a calibrated p" (Supplement, S11.1). With the exact one-sided non-inferiority sign-flip test, Holm gives H1 0.0234, H2 0.0008, H3 0.0032 and H5 0.0234 (l. 194–202).
- *Correction:* report the exact-test version in Table 6 and move the bootstrap version to the footnote.

**(13) Section 6.2.**
- *Printed:* "An interval from inverting this test … runs from −1.25 to 0.08."
- *Source:* matches (`study3_review.md` l. 207). Fine.

**(14) Section 6.2.**
- *Printed:* "With the eight stories as clusters instead, p = 0.0156."
- *Source:* matches (l. 207). Also say that under the same unit H5's superiority p is 0.0547 (l. 210), so the unit matters.

**(15) Section 6.4.**
- *Printed:* "CasePath made 0.22 and the frontier prompt 0.19 (p = 0.8984)."
- *Source:* matches (`study3_feedback.md` l. 68).
- *Add:* the same-model contrast on these 40 claims, CasePath 0.22 against Rules in context 0.40, has p = 0.28 (l. 44). The paper should not leave the impression that CasePath beat the same-model prompt on fully stated files.

**(16) Section 6.4.**
- *Printed:* "Counting these as errors, CasePath made 0.73 deviations per claim, against 2.33 (p = 0.001) and 2.09 (p = 0.0023)."
- *Source:* registered secondary S3a and S3b (results l. 102–103). Label them "registered secondary".

### 2.5 The four cells of model × data set

**(17) Section 6.3, Table 7, Figure 4.** The values match: tenancy 0.31 / 0.30; theft 0.58 / 0.83; Rules in context 2.14 / 1.86 / 1.74 / 0.95; original rules 1.47 / 0.67. Two things are omitted:
- The frontier cell is *CasePath, checklist only*, one run. It is compared with the full product only in Table 7. The abstract and conclusion say "it".
- Registered secondary S7c (results l. 113): on theft the frontier checklist-only run made *more* errors than the cost-efficient full product (0.83 against 0.58, difference +0.25, interval 0.05 to 0.46, p = 0.078, descriptive). This is the most direct evidence that the frontier theft cell is a frontier-*reading* problem, not a rules problem. `decomposition.md` l. 90–91 shows that the two cells share the same rule part, 0.333, and differ in reading and hold (0.088 + 0.157 against 0.250 + 0.250).

**(18) Abstract, Introduction and Conclusion.**
- *Printed (abstract):* "On the frontier model, run once, it led on tenancy and had no advantage on theft, where the rules alone account for 0.333 of its 0.833 errors per pair."
- *Printed (conclusion):* "…where the rules set the limit."
- *Source:* the decomposition is post hoc (`decomposition.md` l. 1–3). The theft mapping is "partly uncertain" (l. 86); the Supplement, S11.4, gives a floor between 0.22 and 0.44 over the two uncertain mappings. The cost-efficient product with the same rules made 0.58 (S7c above).
- *Corrected (abstract):* "On the frontier model, where only the checklist-only setting ran once, it led on tenancy but not on theft (0.83 errors per pair against 0.95 and, with the original rules, 0.67). A post hoc decomposition attributes 0.33 errors per pair (0.22–0.44 under alternative fact mappings) to the rules, and most of the rest to the frontier model reading two over-broad conditions literally."
- *Corrected (conclusion):* "where the frontier model's literal reading of two over-broad rule conditions, and the rules themselves, set the limit".

### 2.6 Registered or added after review, and whether each is labelled

**(19) Abstract.** Five of its empirical sentences rest on post hoc analyses. None is labelled:
- the S/O split (sentences 5 and 6);
- the budget-matched comparison (sentence 9);
- the decomposition (sentence 10);
- the clean room (sentence 11);
- the reading sensitivity (sentence 12).

Sentence 7 rests on registered primary and secondary tests, and sentence 8 on the registered procedure.

*Correction:* add "In analyses added after review, …" before sentence 5, or rebuild the abstract around H1–H5 (see the rewrite in Part 3).

**(20) Introduction, paragraph 5.**
- *Printed:* "With every fact read correctly, the reviewed theft rules still cause 0.333 errors per pair; most of the rest comes from two over-broad rule conditions read literally (Section 6.7)."
- *Source:* post hoc (`decomposition.md` l. 1–3), with no label in the sentence. "Most of the rest" (0.305 of 0.500) is the *in-sample* lint result (`lint_followup.md` l. 36: 0.833 → 0.528).
- *Corrected:* "In a post hoc decomposition, the reviewed theft rules cause 0.33 errors per pair even with every fact read correctly (0.22–0.44 under alternative mappings). The frontier model's literal readings of two over-broad conditions account for about 0.3 of the remaining 0.5."

**(21) Introduction, paragraph 5.**
- *Printed:* "A lint that flags such conditions without reference answers found them …"
- *Source:* in sample: the flags were computed on the same test texts (`lint_followup.md` l. 7: "these results are in-sample"). Out of sample, the development flags miss the traces condition (l. 62: g003 and g061 are "only in-sample"). The lint flags 12–14 theft conditions and 8–9 of 10 tenancy conditions (l. 9, 31, 85–106).
- *Corrected:* "A post hoc lint that needs no reference answers flagged both conditions when run on the test texts themselves, but it also flags most other conditions, and flags computed from development runs alone missed one of the two."

**(22) Contribution (2).**
- *Printed:* "CasePath, the artefact, with design knowledge from two design cycles, including a rule lint that needs no reference answers."
- *Source:* Section 4.3 of the paper states that the lint was "written after the test and not part of the tested commit". The second cycle has produced no result (the protocol is at 1.0-rc).
- *Corrected:* "CasePath, the artefact, with design knowledge from the first design cycle, and a post hoc rule lint offered as a diagnostic whose false-alarm rate is unknown."

### 2.7 Alternative readings of the rules: evidence and upper bounds

**(23) Section 6.6, and the abstract's "Two blind AI evaluators reproduced the tenancy references exactly."**
- *Source:* `cleanroom/README.md` l. 26–31. The evaluators received "the process catalogue (nodes, transitions with conditions, documents with condition, requirement class and steps)" and the designed fact state of every fact (l. 40–44). Exact agreement therefore shows that the engine implements the machine-readable catalogue as two AI sessions read it. It does not independently confirm the prose interpretation.
- *Corrected:* "Two AI sessions that never saw the engine, given the rule text, its process catalogue and the designed fact states, wrote evaluators whose references matched the registered one on all 1,024 document decisions. This confirms that the engine implements the catalogue; it does not settle how the prose should be read."

**(24) Section 6.6.**
- *Printed:* "the product's unchanged workflow scored against references written under four readings that the evaluators had rejected."
- *Source:* `cleanroom/README.md` l. 50–54. The alternative references were written by evaluator B *after* the clean room, "to an instruction", and "are not independent evidence". The Supplement says so (S13.4); the main text does not.
- *Corrected:* "… against references that evaluator B wrote afterwards, to our instruction, under four readings both evaluators had rejected. These references are not independent evidence; they measure how far the result depends on the reading."

**(25) Section 6.6.** Which rows are evidence. The paper says "Those two rows (A3 and all four) are upper bounds; only A1, A2 and A4 are read as evidence." The source (`study3_feedback.md` l. 269) names A2, A3 and A4 as told/not-told comparisons. See item (9) for the corrected sentence.

**(26) Section 6.6, Under A1.** The paper says the lead "consists of the open-event claims". The source agrees: −4.37 on open events against −0.40 on denied events (`study3_feedback.md` l. 376). Add the count: under A1 the remaining same-model lead rests on 9 claims in 9 families.

### 2.8 Lint claims, in sample and out of sample

**(27) Section 6.7.**
- *Printed:* "The lint flagged these conditions without reference answers."
- *Source:* in sample (see item 21).
- *Corrected:* "Run on the test texts themselves, the lint flagged both conditions among 14 it flagged for the frontier model."

**(28) Section 6.7, mutation test.** The source adds that the mutations were "written by the same analyst who knows the lint" and that the test "cannot show detection of subtler, realistic over-breadth" (`lint_followup.md` l. 156). Add both to the paper.

**(29) Section 6.7.**
- *Printed:* "Treating a flagged condition as open helped in sample and not out of sample."
- *Source:* matches (0.528 against 0.778; p 0.1406–0.6719; `lint_followup.md` l. 72–81). Fine. The Table 10 numbers also match.

### 2.9 Cost and time

**(30) Abstract, Introduction and Section 7.1.**
- *Printed:* "costs several times a single prompt."
- *Source:* `study3_results_fresh2_confirm.md` l. 37–46 and 52–64. Full product USD 0.01339 (tenancy) and 0.02999 (theft). Same-model Rules in context 0.00068 and 0.00072. That is **19.7×** and **41.7×**. Against the frontier prompt the ratios are 2.12× and 7.35× (l. 248, 263). The frontier checklist-only run cost 3.40× and 9.46× the frontier prompt (l. 257, 275).
- *Corrected:* "The full product cost about 20 (tenancy) and 42 (theft) times the same-model single prompt, and 2.1 and 7.4 times the frontier single prompt. The checklist-only setting cost 4 and 7 times the same-model prompt."

**(31) Section 6.5.**
- *Printed:* "a full case-run took a median of 204 and 287 s, checklist only 33 and 87 s."
- *Source:* `study3_review.md` l. 400: "Calls answered from the response cache … take no model time, so these times are lower bounds for an uncached run." Checklist only shared cached responses with the full product in the same run.
- *Corrected:* "… a full case-run took a median of at least 204 and 287 s (lower bounds, because cached calls took no time; checklist only, which shared the full product's cache, at least 33 and 87 s)…"

**(32) Section 6.5.**
- *Printed:* "At a matched budget, the lead was significant on tenancy and not on theft."
- *Source:* matches (`study3_feedback.md` l. 236, 261). The abstract's "More samples of the same prompt did not close the gap" therefore holds for tenancy only.
- *Corrected (abstract):* "More samples of the same prompt left a large gap on tenancy; on theft the gap at matched cost was not significant (p = 0.13)."

### 2.10 Decomposition

**(33) Section 6.3.**
- *Printed:* "The parts add up exactly, and their sum does not depend on the order."
- *Source:* `decomposition.md` l. 5 and 17–27: the "interaction remainder" is 0.000 in every row, so the *parts themselves* do not depend on the order in these data. The printed sentence states a triviality and misses the useful fact.
- *Also:* one part is negative (reading, expert procedure, −0.375, l. 116), so "the error that disappears at a stage" is not always an error that disappears.
- *Corrected:* "The parts add up exactly, and in these data each part is the same whatever the order of the stages (the interaction remainder is zero). A part can be negative where correcting one stage uncovers an error that another had masked."

### 2.11 Theft rule review

**(34) Introduction, paragraph 5, and Section 5.**
- *Printed:* "The theft rules had been reviewed by AI editor sessions that knew the test conditions; with the original rules, the single prompt made 1.47 … and 0.67 …"
- *Source:* `study3_review.md` l. 338 and 367 (R9). With the reviewed rules both single prompts were worse: 1.74 against 1.47, and 0.95 against 0.67. Only 11.2% and 27.5% of the change fell on documents named by a changed rule. The frontier prompt's unresolved-pair holding fell from 87–100% to 37–50% per changed fact (l. 369–379).
- *Add:* "With the reviewed rules both single prompts made more errors than with the original rules, mostly on documents no changed rule names. The comparisons in H1, H4 and H5 therefore use a rule base that is less favourable to the single prompts, for reasons we cannot isolate."

### 2.12 The planned study on real files

**(35) Section 5, Appendix B and Section 7.1.** The wording is correct:
- "protocol … version 1.0-rc … will be frozen on 20 November 2026" (`PREREGISTRATION_DRAFT.md` l. 39, 477–478);
- "this article reports no result";
- "four sealed files", "five experts" and "sign test … 1/32" (l. 72, 81, 372);
- the 80% prediction rule (l. 344).

No result is implied, and the study is not called registered. Two points remain:
- Contribution (3) and the Introduction call it "the protocol of a planned study". That is fine. The *file* is titled "Pre-registration". The paper should keep calling it a protocol until it is frozen and deposited.
- `PREREGISTRATION_DRAFT.md` l. 82 describes the cases as "Eleven closed dossiers of an internal hackathon". The paper says "the insurer's real files" and "eleven closed tenancy-defect (mould) files of the insurer". Say how these files reached the hackathon, and whether they are unaltered real claim files.

### 2.13 Smaller factual points

**(36) Appendix C.**
- *Printed:* "50 comparator outputs failed and were scored as empty checklists."
- *Source:* the Supplement, S10.1, says 7 of the 50 were Self-consistency *samples* scored as empty votes, not empty checklists. The registered output lists 43 failed design outputs (`study3_results_fresh2_confirm.md` l. 19–27).
- *Corrected:* "50 comparator outputs failed: 43 design outputs, scored as empty checklists as planned (40 from ReAct), and 7 Self-consistency samples, counted as empty votes."

**(37) Section 6.1, the limits paragraph.** The plan's own fixed limits include "theft reuses the nine conditions and the rule base of the earlier studies, so it tests new documents, not new rules" (`ANALYSIS_PLAN_STUDY3.md` l. 68–71). The paper mentions this only in passing in Section 7.1 ("theft reuses Study 1's conditions"). Add it to "Three limits apply to every result", making four.

**(38) Section 6.2.**
- *Printed:* "On the 63 ordinary claims, CasePath made 0.20 against 0.44 … (p = 0.0417, which the plan did not predict)."
- *Source:* the plan predicted *no difference* (`ANALYSIS_PLAN_STUDY3.md` l. 153–155), and the registered row is labelled "descriptive, outside the procedure" (results l. 72).
- *Corrected:* "… (p = 0.0417, descriptive; the plan had predicted no difference here)".

---

## Part 3. Concerns

Every item below can be resolved with stored data or rewording. None needs a new model run.

### 3.1 Major concerns

**M1. The H4 paragraph is false and its statistics are wrong.**
- *Problem:* see 2.1, item (1). If CasePath had been better in all nine clusters, the test would have given p = 0.0039. It was worse on two clusters, by +0.125 and +1.00. The explanation offered ("sums as far from zero are not rare") gives the wrong reason for the p value.
- *Resolve:* replace the paragraph with the 7-of-9 statement and cite Table S22.
- *Also:* check every other sentence whose cluster-direction counts were taken from the "clusters / non-zero" column of the registered output. Fig. S6's "3 favour Rules in context" and similar statements should be counted from `study3_review.md` R6 (l. 223–246), not from "non-zero".

**M2. The headline leads with a post hoc subset, mislabelled.**
- *Problem:* the first numbers a reader sees (0.34 against 2.32 and 2.13) come from an S/O split added after review, are family means printed as "per claim", disagree with Figure 5, and describe the subset wrongly ("open or denied deciding fact").
- *Problem:* the advantage is concentrated in 9 of 24 families: those of two dispute types (termination, rent increase) that contain the denied- and open-event claims the test set was built to include. On the 15 defect families the differences are small and mixed (`study3_review.md` l. 223–246).
- *Resolve:* lead the abstract and introduction with the registered H2 and H3 (0.31 against 2.14 and 1.86), with the subset rows of Section 6.2 as the plan's prediction. Then give the S/O split as post hoc, with claim-run means (0.40 against 3.39 and 3.06) or clearly named family means.
- *Resolve:* state in Section 6.2 that 9 families carry the effect.
- *Resolve:* make Table 8 and Figure 5 use the same quantity.

**M3. The theft "holding" evidence does not show holding.**
- *Problem:* the registered theft holding measure scores 94% for CasePath and also 94% for "unresolved = false". Exact deferral never ran on theft, and the plain walk on this one-step workflow equals unresolved = false for requests (`study3_review.md` l. 417).
- *Problem:* the claim that every other design held 27–47% is false (Core 85%, checklist only 95%, frontier checklist only 75%, two-valued false 94%).
- *Resolve:* restrict "the design holds what the file leaves open" to tenancy. On theft, say that CasePath avoided premature requests on unresolved-fact pairs (0.0%) and changed nothing else in 94% of them, but that the measure cannot tell a hold from a closed-world reading.
- *Resolve:* report the F1 measure "open condition's documents held" (`study3_feedback.md` l. 79–91): CasePath 83%, Rules in context 85%, Self-consistency 90%. On that measure the single prompts hold the open condition's documents *as often or more often*; their failure is changing other documents.
- *Effect:* this changes the story of the theft result, from "CasePath holds" to "CasePath changes nothing else".

**M4. The frontier theft cell is attributed to the rules; the data point to the frontier model's readings.**
- *Problem:* the abstract says the rules "account for 0.333 of its 0.833", and the conclusion says "the rules set the limit". The cost-efficient product, with the same rules, made 0.58, and the frontier checklist-only run was worse than it (S7c: +0.25, p = 0.078).
- *Problem:* the rule part (0.333) is the same in both cells (`decomposition.md` l. 90–91). The extra 0.25 is reading and hold, mostly the third-party condition, which the frontier model admitted true in 8 of 8 base texts and the cost-efficient model in none (Supplement, S11.4).
- *Problem:* the 0.333 floor depends on two uncertain mappings (range 0.22–0.44).
- *Resolve:* reword the abstract, introduction and conclusion as in 2.5, items (17)–(18). Report S7c in Section 6.3. Give the floor as a range wherever it appears.

**M5. The reviewed rules confound the theft comparisons.**
- *Problem:* the review was done by AI sessions that knew the test conditions. It made both single prompts worse (1.47 → 1.74, 0.67 → 0.95), mostly on documents no changed rule names (R9). H1, H4 and H5 all use the reviewed rules. CasePath's error with the original rules on these data is unknown, because readings depend on the rule base.
- *Resolve:* say this plainly in Section 6.1 and Section 7.1.
- *Resolve:* report beside H1 the registered secondary S4c (CasePath 0.58 against original-rules Rules in context 1.47, p = 0.0117), so the same-model theft result does not depend on the comparator's rule base.
- *Resolve:* on the frontier model, report S4b honestly. Its non-inferiority value is an uncalibrated bootstrap share; the exact superiority p for 0.58 against 0.67 is 0.64 (`study3_feedback.md` l. 119).
- *Resolve:* state that the best theft result for any single prompt (0.67) came with the rules the review replaced.

**M6. The sensitivity to the reading of the rules is presented more strongly than its sources allow.**
- *Problem:* the alternative references were written by one evaluator, after the clean room, to an instruction. The source says they "are not independent evidence" (`cleanroom/README.md` l. 50–54). The main text omits this.
- *Problem:* the clean-room bundle contained the machine-readable process catalogue (README l. 26–31). Exact agreement therefore tests the engine's implementation, not the interpretation of the prose.
- *Problem:* the told/not-told asymmetry affects A2 and A4 as well as A3 (`study3_feedback.md` l. 269).
- *Problem:* the core tenancy effect rests on the authors' choice that a denied defining event stops the process. Under A1 the remaining lead rests on 9 open-event claims.
- *Resolve:* reword the abstract and Section 6.6 as in 2.7.
- *Resolve:* say in Section 7.1 that whether a denied defining event stops the process is the single interpretive choice on which most of the tenancy effect depends, and that no lawyer has ruled on it.
- *Resolve:* for A2 and A4, cite the unchanged-workflow rows.

**M7. The cost of the design is understated.**
- *Problem:* "several times a single prompt" holds only against the frontier prompt. Against the same-model prompt, which is what "same-model claim" invites, the full product costs about 20× and 42×.
- *Problem:* the frontier checklist-only design costs more per case than the cost-efficient full product on tenancy (0.0214 against 0.0134).
- *Problem:* the times are lower bounds.
- *Resolve:* reword as in 2.9, items (30)–(31). Put a cost-ratio column (same-model and frontier) in Table 5.

**M8. The lint is presented as a finding and a contribution; it is an in-sample, post hoc diagnostic.**
- *Problem:* the lint was written after the test and is not in the tested commit. It found the two theft conditions only on the test texts. It flags most conditions in both data sets (theft 12 and 14; tenancy 8 of 10 and 9 of 10). Its mutation test was designed by an analyst who knew the lint and planted blunt over-breadth. Its remedy failed out of sample.
- *Resolve:* remove it from contribution (2), or recast it there as "a proposed diagnostic". Reword the introduction and abstract as in 2.6, items (21)–(22). In Section 6.7, give the flag counts beside the hits, so the reader can see its specificity on these data.

**M9. Labelling and multiplicity.**
- *Problem:* the paper is careful in Sections 6.3–6.7, but the abstract, introduction (paragraph 5) and conclusion mix registered and post hoc results without labels (2.6, item 19).
- *Problem:* over a hundred post hoc p values are reported without correction (Sections 6.3–6.7, Tables 9 and 10, F1, F5). The phrase "each p ≤ 0.0001" invites confirmatory reading.
- *Resolve:* tag every number in the abstract, introduction and conclusion as registered or post hoc; a superscript or a phrase is enough. Add one sentence to Section 6: "Post hoc p values are descriptive and not corrected for multiplicity." Give Principle 1 the label "registered secondary, descriptive".

**M10. The abstract omits limits a reader needs to weigh the result.** The study's limits are disclosed honestly in Sections 6.1 and 7.1. The abstract, which is what most readers see, mentions only "synthetic". It omits:
- the texts were written by an AI session that could read the product's prompts and development results;
- the tenancy references come from the engine the product implements;
- the theft test reuses Study 1's nine conditions and rule base, so it tests new texts, not new rules;
- the theft rules were reviewed by AI sessions that knew the test conditions;
- H3 depends on a reordering 38 minutes before the freeze;
- no person, and no lawyer, checked any AI-written material, rule or reference.

*Resolve:* one added abstract sentence. Suggested: "The texts were written by an AI session with access to the product's prompts, the tenancy references come from the engine CasePath implements, the theft rules were reviewed by AI sessions that knew the test conditions, and no person checked these materials; one confirmed hypothesis depends on a reordering made before the freeze."

### 3.2 Minor concerns

1. Section 6.3, decomposition: replace "their sum does not depend on the order" with the zero-interaction statement, and note that parts can be negative (2.10, item 33).
2. Table 6: compute Holm with the exact non-inferiority p for H5 (S13.2 already has it) and footnote the bootstrap version.
3. H5's margin (0.25) and its test appear only in the Supplement. State both in Section 6.2.
4. Section 6.1: "unsafe error" is defined differently in Section 1 (two kinds) and Section 6.1 (five kinds). Use the full definition at first use and say "strict unsafe" throughout.
5. Abstract: "open or denied deciding fact" should read "an open fact or a denied or open defining event".
6. Section 6.2's pointer "(Supplement, Table S16)" goes to claim means, while the text quotes family means.
7. Section 6.6: say that six registered tenancy contrasts reverse significantly under "all four", not only H2.
8. Section 3.5 and Principle 3: break down the 9-of-1344 count by role (2.3, item 11).
9. Section 6.5: times are lower bounds, because cached calls take no time.
10. Appendix C: 50 failed outputs comprise 43 design outputs and 7 Self-consistency samples, which are scored differently.
11. Appendix B and Section 5: clarify the provenance of the eleven "hackathon" dossiers.
12. Appendix D: "Code, synthetic data and analysis are released" (abstract) conflicts with "the public release is either a scrubbed commit … or the tested commit with the insurer's approval". Say "will be released" until it is.
13. Proposition 3.3(a) restates Equation (3). Call it an observation, or fold it into the definition.
14. Section 6.7, mutation test: state that the mutations were written by the analyst who designed the lint, and that only blunt widening was tested.
15. Section 6.4: report the same-model S-subset contrast (0.22 against 0.40, p = 0.28) beside the frontier one.
16. Section 6.4, Figure 5: state that the composition *within* the O subset (24 denied, 32 open-fact claims) is held at the test's mix. Real files with open branch facts but no denied events would sit much nearer the S line.
17. Table 5 lists "Model executes rules" without saying it is the plan's "Chain-of-Logic style" design (plan §4). Section 2 says Chain of Logic is not run. Reconcile.
18. Section 6.3: "CasePath, checklist only … at 22% and 16% of the full product's cost". Also give the two settings' run-to-run identity (81% against 93% in the same run, R7b), so readers see how much the shared cache narrows the comparison.
19. Section 4.4 and Section 6.1: say once and early that the frontier product is the checklist-only setting, and that on theft checklist only skips the document finder.
20. Section 6.1: "no comparator text changed after 19:10 on 10 November". Name the texts meant, and reconcile with Appendix C's "Model executes rules and ReAct were written during the product's development".
21. Principle 2: say that the strong Kleene comparison (0.25 against 0.23; 0.65 against 1.31) is on 277 of 286 claim-runs, scored by the research engine, and that strong Kleene had *fewer* strict errors in 3 claim-runs and more in none (R11b).
22. Table 10: the "Unchanged" column is a fraction (0.750), Table 8 a percentage (75). Use one unit.
23. Section 6.2, ordinary claims: say that the plan predicted no difference, rather than "which the plan did not predict" (2.13, item 38).

### 3.3 Does the paper oversell or undersell?

**Oversold:**
- the H4 sentence (M1);
- the theft holding result (M3);
- the attribution of the frontier theft cell to the rules (M4);
- the clean room and the reading sensitivity (M6);
- the lint (M8);
- "more samples did not close the gap" on theft (2.9, item 32).

**Undersold:**
- cost, relative to the same-model prompt, is understated (M7). That is overselling the design by understating its price.
- The subset effect sizes in the abstract are *understated* by the family-mean choice (0.34 against 2.32, where per claim it is 0.40 against 3.39).
- The decomposition is described more weakly than its source supports (the parts are order-invariant).
- The registered tenancy result (H2/H3, p = 0.0002 and 0.0008, robust to a 10% random perturbation of the reference, F5 l. 520–529) is stronger than the abstract makes it look, because the abstract leads with a post hoc split.

**Disclosed limitations, checked one by one:**

| Limitation | Disclosed? |
|---|---|
| Synthetic data | Yes. |
| References from the implemented engine | Yes (6.1, 7.1). |
| AI-written texts with access to the product's prompts | Yes (6.1, App. D). |
| AI-checked materials, no person | Yes (6.6, 7.1, App. D). |
| Hypotheses reordered before the freeze | Yes (Intro, 6.2, 7.1). |
| One frontier run | Yes. |
| Post hoc analyses | Yes in Section 6; not in the abstract. |

**Missing or under-weighted:**
- the theft test reuses the earlier studies' conditions and rule base (plan l. 68–71), mentioned only in passing;
- the alternative references are not independent (README l. 50–54);
- the clean room was given the machine-readable catalogue;
- the times are lower bounds;
- the reviewed rules lowered the comparators' scores for unexplained reasons;
- the tenancy effect sits in 9 families of two dispute types;
- the mutation test was designed by the lint's author;
- the provenance of the "hackathon" dossiers.

### 3.4 The ten weakest sentences, with rewrites

1. **Section 6.2:** "…although CasePath had the lower mean in all nine clusters. The differences are unequal in size, so sums as far from zero are not rare."
   **Rewrite:** "CasePath had fewer errors on 7 of the 9 changed facts and more on 2, one by 1.00 error per pair; 32 of the 512 sign patterns give a sum as far from zero."

2. **Abstract:** "On tenancy claims with an open or denied deciding fact it made 0.34 unsafe errors per claim; a single prompt applying the rules made 2.32 on a cost-efficient model and 2.13 on a frontier model."
   **Rewrite:** "On tenancy, CasePath made 0.31 strict unsafe errors per claim, against 2.14 and 1.86 for a single prompt with the same rules on the cost-efficient and frontier models (registered, p = 0.0002 and 0.0008). Most of the difference lay in claims that deny or leave open the dispute's defining event."

3. **Introduction and Section 6.4:** "CasePath left 94% of theft pairs with an unresolved fact otherwise unchanged, against 27–47% for every other design given the reviewed rules."
   **Rewrite:** "CasePath changed nothing else in 94% of theft pairs with an unresolved fact, against 27–47% for every single-prompt and prior-work design given the reviewed rules. Reading open facts as false scores the same."

4. **Abstract:** "More samples of the same prompt did not close the gap."
   **Rewrite:** "At matched cost, majority voting over more samples left the tenancy gap (p = 0.0006); on theft the gap was not significant (p = 0.13)."

5. **Abstract:** "The design holds more than needed and costs several times a single prompt."
   **Rewrite:** "The design held 0.33 unneeded documents per claim, against 0.17 for the same-model prompt, and cost about 20 to 40 times that prompt and 2 to 7 times the frontier prompt."

6. **Abstract:** "The lead holds under alternative readings of the rules when the workflow follows them, and reverses under one when it does not."
   **Rewrite:** "Scored against references for four readings of the rule text that we had rejected, the unchanged workflow lost its tenancy lead under one of them (not significantly) and under all four combined (significantly). Rewritten to follow each reading, it kept the lead. These references were written to our instruction and are not independent."

7. **Introduction:** "A lint that flags such conditions without reference answers found them, but a remedy built on its flags did not survive out of sample."
   **Rewrite:** "A post hoc lint flagged both conditions on the test texts, among most others; from development runs alone it missed one, and treating flagged conditions as open did not help out of sample."

8. **Conclusion:** "…and had no advantage on theft (0.83 errors per pair against 0.95 and, with the original rules, 0.67), where the rules set the limit."
   **Rewrite:** "…and had no advantage on theft (0.83 against 0.95 and, with the original rules, 0.67), where it read two over-broad rule conditions literally and the rules themselves cause about a third of an error per pair."

9. **Section 6.3:** "The parts add up exactly, and their sum does not depend on the order."
   **Rewrite:** "The parts add up exactly, and in these data none of them changes with the order of the stages."

10. **Abstract and Section 6.6:** "Two blind AI evaluators reproduced the tenancy references exactly."
    **Rewrite:** "Two AI sessions that never saw the engine, given the rule text, its process catalogue and the designed facts, reproduced every tenancy reference decision. This confirms the implementation, not the reading of the rules."

**Reserve: Introduction.** "The main finding is that the design holds what the file leaves open."
**Rewrite:** "The main registered finding is on tenancy: CasePath made far fewer strict unsafe errors than single prompts with the same rules, chiefly on claims that deny or leave open the defining event, by holding or stopping where the prompts requested."

---

## Part 4. Clarity and length

### 4.1 What to cut or merge

The main text is 31 pages, with a supplement of about 60. The empirical story fits in about 22 pages.

- **Section 5 and Table 3** (Studies 1 and 2, the redesign history). Keep one paragraph: what failed, what changed, and that no change was evaluated on confirmatory data. Move Table 3 to the Supplement. Design-science readers want the lineage, but Table 3 mixes models, studies, and new and recomputed numbers, and it slows the reader before Study 3.
- **Section 4.4** (tested configuration). Merge it into Section 6.1. Its one consequential fact, that checklist only skips the document finder on every theft text, belongs where the designs are defined.
- **Section 6.3, "All four cells", and Figure 4.** Figure 4 repeats the top of Table 7 value for value. Keep one. A good choice is to keep Figure 4, move Table 7's decomposition block into a small Table 7 of its own, and drop the duplicated top block.
- **Section 6.7.** Cut by half. Give the decomposition result in one paragraph. Put the lint, including Table 10, in a short "post hoc diagnostic" subsection, or move it to Section 7 as future work, with Table 10 in the Supplement.
- **Section 7, Principles.** Each principle repeats numbers already given in Section 6. Cite the section instead and keep only the boundary conditions. That saves about half a page.
- **Section 7.1 against Appendix C.** The irregularities are listed three times: Section 7.1, Appendix C and Supplement S10. Keep a one-line pointer in 7.1.
- **Figure 7** repeats the numbers of Section 3.5. Drop it, or drop the numbers from the text.
- **Section 2.** It is good, but "Legal benchmarks and supervision" and "Reliance on advice" could each shrink to one sentence. The latter matters only for the protocol.

### 4.2 Figures and tables

Rendered at 80 dpi and inspected: pages 14–18 and 20.

**Table 6 (page 14).**
- Ten columns, with two kinds of "status" side by side. The registered and added blocks are separated only by a header rule. Shade the added block, or move it to the Supplement and keep one sentence.
- The H4 row spans three sub-rows with no visual grouping.
- Footnote b uses an uncalibrated p.

**Table 7 (page 15).** Readable. Problems:
- the decomposition rows use three decimals while the top uses two;
- "Measured (sum)" differs from the top block in the third decimal (case-run against cluster means), and a reader will think it is an error.

Give one sentence in the caption, or use the same means.

**Figure 4 (page 16).**
- Clear. The blue vertical reference line at CasePath's value helps.
- The frontier column shows only two or three marks, so the panel is mostly empty space. The open circles carry no interval, and nothing marks them visually as "not comparable".
- It duplicates Table 7.
- The theft x-axis label "wrong + missed changes per pair" sits under both panels, but the y-axis design labels are only on the left. Acceptable.

**Table 8 (page 17).**
- It mixes registered and post hoc columns and three units (%, per claim, family means).
- The S and O columns do not match Figure 5 on the same page (family means against claim-run means; 2.32 against about 3.4 for Rules in context). A reader who compares them will lose trust.
- Fix the units, and split the registered and post hoc parts into two tables.

**Figure 5 (page 17).**
- Two of the three single-prompt lines (Rules in context, Self-consistency) overlap almost exactly, with stacked labels.
- The grey band for the frontier prompt covers the whole upper half, which looks alarming but is uninformative.
- The vertical "this test (58%)" line is useful.
- The figure implies linear extrapolation from a designed mix. Add a sentence about the fixed within-O composition.

**Figure 6 (page 18).**
- Point labels "m = 1", "m = 5", "k = 1" and so on float away from their points. In the tenancy panel, "m = 1" sits under the Rules in context diamond and reads as belonging to it.
- The hollow diamond ("not the same quantity as m = 1") needs explaining or removing.
- The theft and tenancy panels share an x scale, which is good.
- The cost axis starts at 0.0005, so the cost ratio to the same-model prompt (the point of M7) is not visible. Add the full product as a point.

**Table 9 (page 20).** Hard to read:
- ten numeric columns;
- negative numbers with p values in parentheses;
- "matched" against "unchanged" explained only in the caption;
- the two upper-bound rows (A3, all four) not marked in the table body.

Split it into (a) agreement and errors per design, and (b) the contrasts. Mark the upper-bound rows with a dagger. Add a column "evidence or bound".

**Table 10 (page 20).**
- The columns "Held" (a count of documents held in every ordinary text) and "Open" (facts per text) are not rates and are hard to interpret.
- "Unchanged" is a fraction here and a percentage in Table 8.
- The cost-efficient rows have no p value, with no reason given.

**Table 5.** Add a column "cost relative to same-model prompt".

### 4.3 Terms used before they are defined

| Term | First used | Defined |
|---|---|---|
| "unsafe error" | abstract | partly in Section 1; fully in Section 6.1 |
| "strict unsafe" | Section 6.1, first appearance in Table 7 | Section 6.1 |
| "defining event" | Section 1 ("denied or open defining event") | Section 6.1 |
| "reviewed rules" / "original rules" | Section 1 | Section 5 |
| "prior-work design" | abstract | never stated |
| "family" (24 families) | Section 1 | never stated (a family is four variants of one dispute) |
| "plain walk" | Section 3.4 | briefly in Section 3.4 |
| "Core" | Table 5 | Table 5 only |
| "case-run", "pair-run" | Section 6.1 | Section 6.1 (fine) |
| "four-eyes rule" | Section 6.7 | described in Section 5 but not named there |
| "parity command", "Knowledge store" | Section 4.1 | Supplement only |
| "silence clause" | Section 3.2 | Section 3.2 (fine) |
| "flow workflow" | Section 3.1 | Section 3.1, negatively |
| "checklist only" | Section 4.4 | Section 4.4 (fine), but used in the abstract implicitly ("run once") without being named |

### 4.4 Prose

The prose is mostly plain and precise. It is unusually free of hype for this genre. Its fault is the opposite: a compressed, aphoristic, telegraphic register, in which short declaratives carry claims their evidence qualifies. Many of these read as slogans written to be quotable.

**Slogan-like declaratives that carry more than the evidence allows:**
- "Agents That Read, Rules That Decide" (title)
- "Code executes faulty rules faithfully, so the rules need their own check." (4.3)
- "A design cannot look good by holding." (6.1)
- "Holding has a cost." (6.4)
- "The frontier theft cell shows where the design stops helping." (Section 1)
- "Deciding a flag needs a jurist." (6.7)
- "The design has costs." / "The statistics have limits of their own." (7.1)
- "Files are often silent on a fact, and silence is not doubt." (3.2)

**Formulaic signposting:**
- "Each paragraph names a line of work and what this article does differently" (2)
- "We answered in three steps. First, a clean room. … Second, … Third, …" (6.6)
- "We state the design knowledge as three principles. Each comes with its evidence, marked registered or added after review, and with the boundary condition under which it holds." (7)

**Repetition.**
- "added after review, not registered" appears more than fifteen times. Use one convention, such as a superscript † or a shaded block.
- "no advantage" is used for both "not significantly different" and "worse in mean".

**Hedged-yet-categorical pairs:**
- "The lead holds under alternative readings of the rules when the workflow follows them, and reverses under one when it does not." The construction is symmetric and memorable, and it hides that the reversal is not significant and that the references are not independent.
- "More samples of the same prompt did not buy what the design buys." (6.5) This is cute, and false on theft at matched cost.

**Overlong sentences in the abstract.** Sentence 10 ("On the frontier model, run once, it led on tenancy and had no advantage on theft, where the rules alone account for 0.333 of its 0.833 errors per pair") puts three claims and one post hoc decomposition into one clause chain.

### 4.5 Bottom line for the editor

The idea, the formal core and the honesty about deviations are of TMIS quality. The registered tenancy result is strong and survives a perturbed reference and three of four alternative readings. The theft result is weaker than written, and the abstract and introduction lead with post hoc numbers. One paragraph on the failed hypothesis is factually wrong. All of this can be fixed with stored data and rewording: **major revision.**
