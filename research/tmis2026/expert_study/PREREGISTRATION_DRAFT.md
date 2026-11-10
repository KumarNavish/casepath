# Pre-registration: expert review of an agentic case-preparation system

Becomes 1.0 at the freeze (section 13), when the decision points and hashes are recorded; nothing else may change.

| | |
|---|---|
| Document | Pre-registration of the CasePath expert study |
| Version | 1.0-rc |
| Status | All design choices are settled (section 14). Frozen as version 1.0 by the procedure in section 13. |
| Use | Cited from the TMIS paper on CasePath, in which the study is planned to appear, or from a separate later paper. The text is the same for both. |

This document is self-contained. It defines the system, the cases, the procedure, the records, every measure and every
analysis. It does not depend on any other file.

## 1. The system and what is studied

CasePath reads the file of a legal-expenses insurance case, places the case in a process (a workflow of steps, facts,
document needs and conditions), lists the documents to request and proposes the next action. Each statement it makes
about a case is an **item**: a fact, a deadline, a document need with its status, a process step, a next action, a
letter clause. A handler reviews the items and corrects them. A reviewable **Knowledge** base grows from corrections:
a correction can become a **proposal** (a candidate Knowledge item), and an activated item changes the process of later
cases in the same process family.

Every run carries a **parity manifest**: the hash of the source tree of the code, the git commit, the hash of each
workflow file and of each Knowledge item, and the model provider and name.

**Link to the outside experiments.** The same product is evaluated outside the insurer on synthetic claims. The two
deployments run the same code commit and the same workflow format and rules, shown by equal source-tree hashes in the
parity manifest. They differ in two declared ways only: the model (the insurer's gateway model inside; the model
`gpt-6-luna` outside) and proprietary data (the insurer's process catalogue, Knowledge and cases inside).

## 2. Research questions

| | Question | Estimation target |
|---|---|---|
| Q1 | How often is what CasePath asserts right, and compared with what? | Item accuracy and reference coverage of CasePath, and of a single-prompt comparator on the same inputs |
| Q2 | Do experts change what is wrong and keep what is right? | Over- and under-reliance; the difference in change rates between wrong and right items |
| Q3 | How much work is left for the expert, and how does the reveal of CasePath's result move an expert's own answer? | Time and corrections per case (descriptive); accuracy of the unaided answer, the answer after the reveal, and CasePath alone |
| Q4 | Does CasePath improve from corrections on a case it has not seen, without harm? | Held-out-case accuracy before and after Knowledge learned from the other two cases, with a nested safety gate |
| Q5 | Why do experts change things? | Distribution of reasons; agreement between the tapped reason and a blind coding of the expert's explanation |

## 3. Participants and cases

- **Experts.** Five claims experts of the insurer's legal-protection unit. No more will be recruited. Each agrees individually, may withdraw at any time and may have their records removed. The insurer's consent is in place.
- **Cases.** Eleven closed dossiers of an internal hackathon, all tenancy-defect (mould) cases, for which the insurer's explicit process reference exists. **Study cases**: D2, D4, D7. **Reserve**: D5, held back in the same way as the study cases. **Development dossiers**: D1, D3, D6, D8, D9, D10, D11 (seven). The three study cases share a process family with each other and with the development dossiers.
- **Inclusion criterion.** The three study cases route to the common workflow. This is checked from routing alone, before the freeze, and recorded.
- **Reserve rule.** D5 replaces a study case only before the first session, and only for a reason listed here in advance: the inclusion criterion fails, the cut copy cannot be made, or a leak cannot be removed. Never after the first session. If D5 is not used, it is reported as unused and is not analysed.
- **Development dossiers.** They carry **development labels**, made by a single labeller who also builds the product. Their results are reported separately under that name, never pooled with the study cases, and no test (section 10) uses them.
- **Practice case.** One synthetic case, used for ten minutes before the study cases.
- **Inference** is conditional on these three cases, this insurer and these five experts. No population claim is made.

### 3.1 Decision point

The dossiers are whole closed files. On the full file, document status is confounded (documents count as present
because they arrived later) and "next action" is undefined. Each study case is therefore cut at one **decision point**.

1. **Rule.** The decision point is the state of the file immediately before the insurer's first outgoing request for documents or information in that case (to the client or to the other party). If a case has no such request, it is the state before the case's first outgoing action of any kind. The point is fixed by this rule, not by choice. Its date and the rule's application (which outgoing action, and why it is the first) are recorded per case before any run on the cut copy.
2. **Cut copy.** A case copy holding only the documents (or page ranges) dated up to the decision point. The frozen run, the four variation runs, the single-prompt comparator, the unaided view, the experts' work, gold and the replay for Q4 all use the cut copy. Nobody in a session sees anything dated after the decision point.
3. **Second decision point (optional, secondary).** A second, later point per case may be added for the system only, with no expert time, labelled by the adjudicator (section 4.3) only if time allows. If it is done, it is done for all three cases, its rule is the state before the insurer's second outgoing action, and it is reported as exploratory.

### 3.2 Development exposure

The three study cases and the reserve are among the eleven dossiers the product was developed on until the seal. This
is a limit of the study. It is reduced as follows:

1. **Seed Knowledge** is rebuilt without D2, D4, D7 and D5; its content hash is in the freeze record.
2. **New cut copies.** No run on a cut copy exists before the frozen run, and none may be made before the freeze except the frozen and variation runs themselves.
3. **Development-exposure record**, made before the freeze from the product's commit history: the commits before the seal whose change was derived from D2, D4, D7 or D5, listed by hash with one line each.
4. **Consequences for claims.** Q1 on the study cases is accuracy on cases seen in development and is labelled so; accuracy on unseen cases comes from the outside experiments on sealed synthetic claims. Q2 and Q5 do not need the cases to be unseen, only the item labels to be right. In Q3 the same holds for the expert's own answers (unaided, and after the reveal); the value for CasePath alone is accuracy on a case seen in development and is labelled so wherever it is shown. Q4's held-out case is held out from the corrections, not from development, and this is said wherever Q4 is reported.

### 3.3 The process reference is the workflow's source

The process CasePath executes for these cases was built from the same process reference that gold uses. Therefore:

1. The structure of the process (its steps, the conditions, and the documents each step demands) is the reference by construction. It is not scored as accuracy.
2. Gold for the path is the reference applied by the adjudicator to the file at the decision point: which step the case is at, which conditions hold, which documents that demands, and what the next action is.
3. Q1 measures placement on a given process and reading of the file (facts, document status, step, needs, next action), reported by item kind. It is not evidence that the process itself is right, and not evidence about process discovery.

## 4. Materials produced before the first session

### 4.1 Frozen runs

1. The product commit, workflow catalogue and Knowledge store are fixed. The Knowledge store is the seed Knowledge rebuilt without the three study cases (section 3.2). Their parity manifest and the seed Knowledge content hash are recorded.
2. Each of the three cut copies (section 3.1) is run once. The stored run is the **frozen run**. Its record holds: the run, the hash of its result (SHA-256 of canonical JSON), the item list (section 5) and its hash, and the parity manifest.
3. Each cut copy is run four more times under the same manifest. These **variation runs** are never shown to an expert. They give run-to-run variation (section 9.7). No other run is made on a cut copy before the freeze.
4. During the study period the Knowledge store is read-only, no run is started on a study case, and no model call is made in a session.
5. Each expert works on their own copy of each cut copy, with a `source_case` field naming the study case. Every copy points to the frozen run. A session starts only if the copy's item-list hash equals the frozen run's and its cut hash equals the recorded one.

### 4.2 Comparator

On each cut copy, one run of the same model with a single prompt, given the same case files (the same text
extraction), the same workflow catalogue and the same active Knowledge in context, asked for: the process step, the
facts the step depends on, the documents to request and the next action. The prompt is fixed in advance and attached to
the frozen version of this document. One run per case is primary. Two more runs per case are made only if the internal
token budget allows (about 6M non-cached tokens in total for the study); if made, they are secondary.

### 4.3 Gold

**Who labels.** One human adjudicator: the process owner (who drew the process reference), who is not one of the five
experts. Second rater: the product builder's automated labeller. It labels every item independently and before it can
see the adjudicator's labels. Both label sets are hashed and time-stamped; the automated set's hash is recorded before
the adjudicator starts. The adjudicator's label stands in every case; the automated labels are never used to resolve
or change a label. Agreement between the two is reported (section 9.7).

**Labelled for the decision point.** The adjudicator labels on the frozen runs, after the freeze and before the first
session (section 13), never sees a session record, and does not know which list came from CasePath and which from the
single-prompt comparator. Each item is judged against the file as it stood at the decision point and the process
reference (section 3.3):

- every chain item (section 5) of the frozen run and of the comparator's primary run: **correct**, **incorrect** or **cannot be decided from the file**;
- every **reference item** (step, required document, next action in the process reference) that a run lacks: an **omission**.

The reference for "documents to request" and "next action" is what the insurer did next, recorded by the adjudicator
from the later file, together with any alternative the adjudicator judges equally correct. The insurer's own action is a reference,
not automatically the only right answer. Alternatives are listed before the first session and never after.

Both systems' items are shown in one neutral format, without citations or system labels, in random order. Where the
adjudicator cannot decide, the label is "cannot be decided".

After all sessions, the adjudicator labels every expert correction's new value and every expert addition (correct /
incorrect / cannot be decided), blind to who made it; the automated labeller labels them first, by the same procedure
(hash recorded before the adjudicator starts).

### 4.4 Cut verification

For each cut copy: the list of included documents or page ranges with their dates, checked by the adjudicator against
the full file for leaks (later-dated pages inside merged PDFs, later notes, stamps, summaries written after the point,
file names that reveal later events); and the SHA-256 of the cut copy. Both are recorded before the frozen run. A leak
found after a session does not change the record: the affected items are flagged, kept in the primary analyses and
removed in a sensitivity analysis.

## 5. Units

- **Item**: one statement of the frozen run on the cut copy, with a stable id; it is a statement about the case at the decision point. Kinds: process step, fact, deadline, document need (whether required, and its status: present, missing, unusable), next action, letter clause, open point, summary field, party, timeline entry.
- **Chain items** (the primary universe): process step, facts that gate a step or a document, deadlines, document needs, next action. All other kinds are recorded and analysed as exploratory.
- **Decision units** for the unaided comparison: the current process step (one unit); each document of the case's workflow, requested or not (one unit each, over the union of the reference's, CasePath's and the expert's documents); the next action (one unit, judged by the adjudicator against the insurer's next action and the alternatives listed before the first session).
- **Not scored**: the structure of the process (steps, conditions, the documents each step demands), which is the process reference by construction (section 3.3). What is scored is where the case is placed on it and what is read from the file.
- Denominators are always the items of the frozen run. Items that appear only through propagation of a correction are not in any denominator; they are counted and reported.

## 6. Design and allocation

### 6.1 Session (about two hours)

| Part | Time | What happens |
|---|---|---|
| Opening | 5 min | Consent, purpose, "use is measured to improve CasePath, not you" |
| Practice | 10 min | Synthetic case in the full tool |
| Trust, baseline | 1 min | TiA Propensity to Trust and Trust in Automation (section 8) |
| Case 1 (unaided first) | ≤ 15 + ≤ 15 min | Unaided: original files only, structured answer form. Reveal: the answer is frozen; CasePath's result is shown; the expert reviews and may revise. Workload scale. |
| Case 2, case 3 (aided) | ≤ 25 min each | Review of CasePath's result. Workload scale after each. |
| Trust, after | 1 min | TiA Trust in Automation (section 8) |
| Recall | 20 min | Stimulated recall (section 8) |

### 6.2 Unaided answer

The unaided view shows the original files of the cut copy only: page images or native text, no text read by the model, no quotes, no
highlights, no run output. The answer form has three fields: the process step (chosen from the workflow's steps, or
"not in the list" with text), the documents to request (chosen from the workflow's document catalogue, plus free
text), and the next action (chosen from the action kinds, plus free text). At the reveal the answer is frozen and
stored with its time. Every later change is a separate event.

### 6.3 Time caps

The caps are 15 minutes for the unaided answer, 15 minutes after the reveal, and 25 minutes for an aided case.
Reaching a cap is an event. When a cap is reached the screen says so; the current state is kept. A capped unaided answer is frozen as it stands;
an empty field counts as "not answered", which is neither right nor wrong. A capped aided case is closed as it stands.
Capped cases stay in the primary analysis and are flagged; a sensitivity analysis drops them.

### 6.4 Allocation

Case labels A, B, C are assigned to the three study cases by lot. The case that is unaided for one expert only
(C) is chosen by the same lot. Expert labels E1–E5 are assigned to the five experts by lot. The lot is drawn by a
person outside the research team, with a recorded seed, before the first session.

| Expert | Position 1 (unaided first) | Position 2 (aided) | Position 3 (aided) |
|---|---|---|---|
| E1 | A | B | C |
| E2 | A | C | B |
| E3 | B | A | C |
| E4 | B | C | A |
| E5 | C | A | B |

Each case is unaided for two, two and one experts (A, B, C) and aided for three, three and four. Within the aided
positions each case appears in position 2 and position 3 at least once. The unaided case is always first, so that the
unaided answer is given before any study-case exposure to CasePath; condition is therefore confounded with position,
and the effort comparison is descriptive.

### 6.5 Other rules

- Experts are asked not to discuss the cases until all five sessions are done.
- For each expert and case it is recorded whether the expert knew the case before, and whether the expert took part in making the process reference or the gold.
- Session order (first to fifth) is recorded.

## 7. Records

Every action of the expert is an event in an append-only log with a relative time (seconds since session start).
Event kinds: case opened, item on screen (interval), source opened, item confirmed, item corrected (before, after,
reason), item dismissed (reason), item added (what, reason), correction undone, point settled, unaided answer saved,
unaided answer frozen, reveal, idle start and end, letter copied (change ratio), case closed ("erledigt" or
"erledigt, mit Vorbehalt"), scale answered, technical failure. A correction's consequences for other items
(**propagation**) are recomputed without a model from the log and stored, each with the id of the correction that
caused it.

**Reasons** offered in one tap, with "ohne Angabe" as default: (1) Steht anders in den Akten; (2) Steht nicht in den
Akten; (3) Hier nicht relevant; (4) Gilt generell so; (5) Weiss ich von ausserhalb der Akten; (6) Formulierung.

## 8. Scales and recall

- **Workload**: raw NASA-TLX, German version of Unema et al. (1988) as reproduced in Seifert (2002, Anhang 5), without the physical-demand item (five items, 0–100 in steps of 5, unweighted mean), after each case.
- **Trust**: the Trust in Automation questionnaire (Körber 2019), two whole subscales in the author's German version: Trust in Automation (items 9, 14) after the practice case and after case 3; Propensity to Trust (items 5, 12, 18; item 5 reversed) once, after the practice case. Five-point agreement scale with "Keine Angabe"; subscale means, no total.
- Wordings, response formats, sources and deviations: the scales guide, section 1, attached to the frozen version.
- **Recall**: twenty minutes. The expert sees, in event order, each of their own corrections, dismissals and additions, and up to three kept items selected by a fixed rule (all kept items that gold labels incorrect, ranked by on-screen time, longest first, then kept correct items with the longest on-screen time to fill three, shown mixed and unlabelled). The expert explains each in their own words. Whether a kept item was wrong is not said during the session. After the last of the five sessions, all five experts are shown together which kept items the reference judged incorrect, without naming who kept what. The researcher codes a reason from the explanation without seeing the tapped reason.

## 9. Measures and analyses

### 9.1 Final fate (derived)

For each expert and item of the frozen run, the final fate is derived from that expert's events by this rule, applied
in order:

1. **corrected**: a correction of the item that is not undone, whose final value differs from the frozen value;
2. **dismissed**: a dismissal ("nicht nötig") that is not undone;
3. **removed by propagation**: the item vanished through a correction of another item (not counted as a judgment of this item);
4. **verified-kept**: the item's source was opened or the item was confirmed;
5. **seen-kept**: on screen for at least the dwell threshold *d* in total;
6. **unseen-kept**: otherwise.

A correction followed by its undo leaves the item kept, with the flag "reconsidered". *Changed* = corrected or
dismissed. *Kept* = fates 4–6. Items with fate 3 are excluded from reliance measures and counted. The dwell threshold
*d* is 2 seconds (primary); 1 and 4 seconds are sensitivity analyses.

### 9.2 Q1: accuracy

| | Definition |
|---|---|
| What it measures | Placement on a given process and reading of the file, by item kind; not evidence that the process itself is right, and not evidence about process discovery (section 3.3) |
| Primary | Item accuracy of CasePath = correct chain items / (correct + incorrect chain items) of the frozen run, per case and pooled. Labelled "accuracy on cases seen in development" (section 3.2) |
| Secondary | The same for the comparator; reference coverage = reference items present / reference items, for both; accuracy by item kind; share "cannot be decided" |
| Reported separately, not pooled, not tested | The same measures on the seven development dossiers, under the name "development labels" |
| Counts against the claim that CasePath adds value over a single prompt | The comparator's accuracy or coverage is equal or higher on two of three cases |

### 9.3 Q2: reliance

| | Definition |
|---|---|
| Hypothesis H2 | Experts change wrong items more often than right ones |
| Primary | For each chain item with gold correct or incorrect: the share of the five experts who changed it. Statistic: mean share over incorrect items minus mean share over correct items |
| Secondary | Over-reliance = kept incorrect / incorrect items; under-reliance = changed correct / correct items; both per expert, per case and pooled, under two definitions of kept (kept = fates 4–6; verified = fate 4 only); the share of corrections whose new value is correct; agreement among the five experts per item (Fleiss' kappa on changed / kept) |
| Sensitivity | Seen / unseen at *d* = 1 and 4 seconds; without capped cases; without items of cases an expert knew before; without items flagged by a leak (section 4.4) |
| Counts against H2 | The primary statistic is zero or negative, or fewer than four of five experts show a positive difference |

### 9.4 Q3: effort and the reveal (descriptive)

| | Definition |
|---|---|
| Primary | On the unaided case: accuracy over decision units of (a) the unaided answer, (b) the same expert's answer after the reveal, (c) CasePath alone, each against gold |
| Secondary | Active time per case (idle excluded) for unaided and aided work; corrections per case; letter change ratio; the share of post-reveal changes that move to CasePath's answer, split by whether CasePath was right; relative AI reliance and relative self-reliance as defined by Schemmer et al. (2023, equations 1 and 2): RAIR = units where the unaided answer was wrong, CasePath right and the post-reveal answer right / units where the unaided answer was wrong and CasePath right; RSR = units where the unaided answer was right, CasePath wrong and the post-reveal answer right / units where the unaided answer was right and CasePath wrong. "Right" means correct against gold, including the alternatives listed before the sessions; units where both were right or both wrong enter neither. Both as counts with denominators |
| Anchoring estimate | Agreement with CasePath of the unaided answers versus the post-reveal answers |
| Not claimed | That the change after the reveal is caused by the advice alone: the expert also looks at the case a second time |
| Counts against the claim that review with CasePath reaches the accuracy of CasePath and the expert together | (b) is below both (a) and (c) on most expert-case pairs |

### 9.5 Q4: learning (model-free replay)

**Proposal rule (mechanical).** From the events of the training cases, a Knowledge proposal is created for every
expert addition of a document need, a step or a question that (a) carries reason 4 ("Gilt generell so"), or (b) was
made by at least three of the five experts on the same case, matched by the same catalogue id. Its scope is the case's
process family and the node the addition named. Free-text additions without a catalogue id become proposals only under
(a). Corrections of facts, dismissals and changed conditions do not become proposals (the product cannot turn them
into Knowledge).

**Gate (nested).** A proposal is replayed on the stored runs of the training cases and the seven development dossiers. The gate is a mechanical filter, not a test of a claim; the development dossiers enter it with their development labels.
It passes if no training-case accuracy and neither development reference score (share of reference documents
requested; share of requests in the reference) falls. Knowledge is never applied to its own origin case, so the gate
in effect tests the other training case and the development dossiers. The gate never sees the held-out case's gold.

**Activation in replay.** Every proposal that passes is activated; no person chooses.

| | Definition |
|---|---|
| Folds | Three: each study case held out once; Knowledge from the other two. The held-out case is held out from the corrections, not from development (section 3.2). Replay runs on the cut copies |
| Primary | Held-out item accuracy and the two reference scores, before and after the activated Knowledge, per fold |
| New items | An item that appears only after replay and is not in the reference counts as an unnecessary request; a sensitivity analysis uses the adjudicator's blind label |
| Secondary | Number of proposals made, passed and stopped; robustness to who supplied the corrections (leave one expert's events out of the training set); transfer of Knowledge from all three cases to the development dossiers and to the synthetic claims, as regression checks |
| Scope | Replay changes the process and the checklist only. Knowledge that acts through what the agents read is not measured. |
| Counts against the claim | Held-out accuracy or a reference score falls in any fold; or no proposal passes the gate; or no proposal applies to any held-out case |

### 9.6 Q5: reasons

| | Definition |
|---|---|
| Primary | Agreement between the tapped reason and the blind-coded reason (Cohen's kappa over corrections with a tapped reason) |
| Secondary | Distribution of reasons; share "ohne Angabe"; accuracy (against gold) of corrections with reason 5, reported separately |
| Counts against non-overlap | Kappa below 0.6, or one pair of reasons accounting for most disagreements |

### 9.7 Other measures

Run-to-run variation: for each item key, the share of the five runs (frozen and variation) with the same value.
Rater agreement between the adjudicator and the automated labeller: raw agreement and Cohen's kappa on correct /
incorrect / cannot be decided, overall and by item kind. It shows how reproducible the labels are, not that they are
right. Expert consensus: for each chain item, the share of the five experts who kept it, reported beside gold as a
second view; it is read with the anchoring caveat (the experts saw CasePath's answer). Calibration: case accuracy for
"erledigt" versus "erledigt, mit Vorbehalt" (15 observations, descriptive). Trust and workload: values per case and
per expert, unlabelled.

## 10. Statistics

- **Estimation first.** Every measure is given per case, per expert (unlabelled) and pooled.
- **Intervals.** (a) Bootstrap over items within case, cases fixed, 10,000 resamples, percentile intervals. (b) Over experts: all five values and the leave-one-expert-out range; a bootstrap over experts (126 distinct resamples) is given only as a crude secondary interval. (c) Leave-one-case-out range.
- **Tests**, only these two, both for H2:
  - T1 (primary). Item-level permutation test of the Q2 primary statistic: correctness labels permuted within strata of case × item kind; 10,000 permutations with a recorded seed; one-sided. The smallest attainable p is reported (1/10,001, or the exact minimum when the strata allow fewer distinct permutations).
  - T2 (secondary). Per-expert sign test: the number of experts whose change rate on incorrect items exceeds that on correct items. Five of five gives one-sided p = 1/32.
- **Q4** has three folds; the direction in each fold is reported (three of three has the smallest attainable one-sided p = 1/8). No other test is run.
- **Exploratory.** Every analysis not listed in sections 9 and 10 is labelled exploratory.

## 11. Exclusions and handling

| Situation | Handling |
|---|---|
| Incomplete session | Completed cases are kept; missing cases are reported |
| Technical failure | Recorded as an event; the affected case is kept up to the failure and flagged; sensitivity analysis without it |
| Time-capped case | Kept and flagged; sensitivity analysis without it |
| Item adjudicated "cannot be decided" | Excluded from accuracy and reliance; counted and reported |
| Leak found in a cut copy after a session | Affected items flagged and kept; sensitivity analysis without them |
| Expert knew a case before | Kept; sensitivity analysis without those expert-case pairs |
| Expert took part in the reference or the gold | Kept; reported; sensitivity analysis without that expert |
| Reserve D5 used | Only before the first session and for a reason listed in section 3; the replaced case and the reason are reported |
| Withdrawal | All records of the expert are removed; the analyses run on the rest; the number is reported |
| Item-list hash mismatch at session start | The session does not start until the copy is restored |

## 12. Privacy

The record measures CasePath. Two exports exist. The **pseudonymous export** holds no case content, only
identifiers, statuses, counts, relative times and randomised expert labels; a guard rejects free text. The
**content export** (item texts, notes, recall transcripts) never leaves the insurer. No result is reported per named
person. Per-expert values are shown unlabelled.

## 13. Versioning and freeze

1. This is version 1.0-rc. It becomes 1.0 at the freeze, when the decision points and hashes are recorded; nothing else may change.
2. **Timetable.** Day 0 is 2026-11-10, the date of the owner's decisions. Freeze on day 10. Adjudication on days 11–13, on the frozen runs. The first session takes place after adjudication is complete and hashed, and within two weeks of that. Rule: **no session before the gold hash exists.**
3. **Freeze**, on day 10, as version 1.0. The freeze commit contains exactly:
   - the commit hash of this document's repository at freeze;
   - the product commit and the parity manifest's source-tree hash;
   - per case: the decision-point date and the rule's application (section 3.1), the cut verification list and the SHA-256 of the cut copy (section 4.4), and the routing check of the inclusion criterion;
   - the content hash of the seed Knowledge rebuilt without D2, D4, D7 and D5 (section 3.2);
   - the development-exposure record (section 3.2);
   - the SHA-256 of each frozen run's result and item list, and of the variation runs;
   - the allocation table after the lot, with the lot seed, and its SHA-256;
   - the SHA-256 of the comparator prompt;
   - the permutation seed for T1 and the bootstrap seed.
4. **After the freeze, before the first session**, two records are added as dated entries (not deviations): the SHA-256 and time of the automated label set, recorded before the adjudicator starts; and the SHA-256 and time of the adjudicator's gold file, with the alternatives listed for next actions and documents to request.
5. The frozen version is deposited with a timestamp (an internal registry and, if the paper's venue requires, a public registry with the content-free parts).
6. Any other change after the freeze is a dated **deviation**, listed in the paper with its reason.

## 14. Choices settled on 2026-11-10

1. Process family: all eleven dossiers are tenancy-defect (mould) cases; the three study cases share a process family with each other and with the development dossiers. Inclusion criterion added (section 3).
2. Four variation runs per case; one comparator run per case primary, three only if the token budget allows (section 4.2).
3. Time caps 15 + 15 minutes unaided and after the reveal, 25 minutes aided; reaching a cap is an event (section 6.3).
4. Dwell threshold 2 seconds primary; 1 and 4 seconds sensitivity (section 9.1).
5. The unaided case is always the expert's first study case (section 6.4).
6. Experts learn which kept items were wrong only after the last session, all five together (section 8).
7. Development dossiers (seven): development labels by a single labeller who builds the product; reported separately, never pooled, no test (section 3).
8. Scales: German NASA-TLX (Unema et al. 1988, via Seifert 2002) and two TiA subscales (Körber 2019), wordings copied from the sources (section 8).

Added on the same date: the decision point and cut copies (sections 3.1, 4.4), development exposure (section 3.2).

Owner's decisions, also 2026-11-10: study cases D2, D4, D7, reserve D5 and its rule, seven development dossiers
(section 3); Q4 stands; the process reference is the workflow's source (section 3.3); one human adjudicator with an
automated second rater (section 4.3); the timetable (section 13); four variation runs per case and the decision-point
runs approved.

## 15. Limits

- **Development exposure.** The study cases were among the dossiers the product was developed on (section 3.2).
- **Process reference.** The process CasePath executes was built from the process reference that gold uses. Its structure is not scored. Q1 measures placement on a given process and reading of the file; it is not evidence that the process itself is right, and not evidence about process discovery.
- **One human adjudicator.** The process owner wrote the process reference, so gold for the path reflects one expert's reading of their own process.
- **Automated second rater.** It is run by the builder of the product and is not independent evidence of correctness. Its agreement with the adjudicator shows how reproducible the labels are, not that they are right.
- **Second view.** The experts' consensus on the same items is reported beside gold; it carries the anchoring caveat, because the experts saw CasePath's answer.
- **Learning.** Only added documents, steps and questions become Knowledge, and replay changes the process and the checklist only (section 9.5).
- **Scope.** Three cases, one insurer, five experts; inference is conditional on them.
