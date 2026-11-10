# Pre-registration: expert review of an agentic case-preparation system (draft)

| | |
|---|---|
| Document | Pre-registration of the CasePath expert study |
| Version | 0.1 (draft, not frozen) |
| Status | Open choices are listed in section 14. Frozen as version 1.0 by the procedure in section 13. |
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
- **Cases.** Three closed cases from an internal hackathon, chosen because the insurer's explicit process reference exists for them. They are **sealed**: no fix, rule or Knowledge item is derived from them, and they are scored only at the freeze. Eight further hackathon cases were used in development; they are the **development dossiers**.
- **Practice case.** One synthetic case, used for ten minutes before the study cases.
- **Inference** is conditional on these three cases, this insurer and these five experts. No population claim is made.

## 4. Materials produced before the first session

### 4.1 Frozen runs

1. The product commit, workflow catalogue and Knowledge store are fixed. Their parity manifest is recorded.
2. Each of the three cases is run once. The stored run is the **frozen run**. Its record holds: the run, the hash of its result (SHA-256 of canonical JSON), the item list (section 5) and its hash, and the parity manifest.
3. Each case is run four more times under the same manifest. These **variation runs** are never shown to an expert. They give run-to-run variation (section 9.6).
4. During the study period the Knowledge store is read-only, no run is started on a study case, and no model call is made in a session.
5. Each expert works on their own copy of each case. Every copy points to the frozen run. A session starts only if the copy's item-list hash equals the frozen run's.

### 4.2 Comparator

On each case, one run of the same model with a single prompt, given the same case files (the same text extraction),
the same workflow catalogue and the same active Knowledge in context, asked for: the process step, the facts the step
depends on, the documents to request and the next action. The prompt is fixed in advance and attached to the frozen
version of this document. Three runs per case if the token budget allows; the first is primary.

### 4.3 Gold

Two adjudicators of the insurer, not among the five experts, label before the first session and without access to
any session record:

- every chain item (section 5) of the frozen run and of the comparator's primary run: **correct**, **incorrect** or **cannot be decided from the file**, against the process reference and the file;
- every **reference item** (step, required document, next action in the process reference) that a run lacks: an **omission**.

Both systems' items are shown in one neutral format, without citations or system labels, in random order. Each
adjudicator labels alone. Agreement is recorded (section 9.5). Disagreements are settled by discussion against the
process reference; any still open become "cannot be decided".

After all sessions, the same adjudicators label every expert correction's new value and every expert addition
(correct / incorrect / cannot be decided), blind to who made it.

## 5. Units

- **Item**: one statement of the frozen run, with a stable id. Kinds: process step, fact, deadline, document need (whether required, and its status: present, missing, unusable), next action, letter clause, open point, summary field, party, timeline entry.
- **Chain items** (the primary universe): process step, facts that gate a step or a document, deadlines, document needs, next action. All other kinds are recorded and analysed as exploratory.
- **Decision units** for the unaided comparison: the current process step (one unit); each document of the case's workflow, requested or not (one unit each, over the union of the reference's, CasePath's and the expert's documents); the next action (one unit, judged by the adjudicators).
- Denominators are always the items of the frozen run. Items that appear only through propagation of a correction are not in any denominator; they are counted and reported.

## 6. Design and allocation

### 6.1 Session (about two hours)

| Part | Time | What happens |
|---|---|---|
| Opening | 5 min | Consent, purpose, "use is measured to improve CasePath, not you" |
| Practice | 10 min | Synthetic case in the full tool |
| Trust, baseline | 1 min | Trust scale (section 8) |
| Case 1 (unaided first) | ≤ 15 + ≤ 15 min | Unaided: original files only, structured answer form. Reveal: the answer is frozen; CasePath's result is shown; the expert reviews and may revise. Workload scale. |
| Case 2, case 3 (aided) | ≤ 25 min each | Review of CasePath's result. Workload scale after each. |
| Trust, after | 1 min | Trust scale |
| Recall | 20 min | Stimulated recall (section 8) |

### 6.2 Unaided answer

The unaided view shows the original files only: page images or native text, no text read by the model, no quotes, no
highlights, no run output. The answer form has three fields: the process step (chosen from the workflow's steps, or
"not in the list" with text), the documents to request (chosen from the workflow's document catalogue, plus free
text), and the next action (chosen from the action kinds, plus free text). At the reveal the answer is frozen and
stored with its time. Every later change is a separate event.

### 6.3 Time caps

When a cap is reached the screen says so; the current state is kept. A capped unaided answer is frozen as it stands;
an empty field counts as "not answered", which is neither right nor wrong. A capped aided case is closed as it stands.
Capped cases stay in the primary analysis and are flagged; a sensitivity analysis drops them.

### 6.4 Allocation

Case labels A, B, C are assigned to the three sealed cases by lot. The case that is unaided for one expert only
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

- **Workload**: raw NASA-TLX without the physical-demand item (five items), after each case.
- **Trust**: the Facets of System Trustworthiness scale (five items, German version), after the practice case and after case 3.
- **Recall**: twenty minutes. The expert sees, in event order, each of their own corrections, dismissals and additions, and up to three kept items selected by a fixed rule (all kept items that gold labels incorrect, ranked by on-screen time, longest first, then kept correct items with the longest on-screen time to fill three, shown mixed and unlabelled). The expert explains each in their own words. Whether a kept item was wrong is not said during the conversation; it is said at the end only if the expert asks. The researcher codes a reason from the explanation without seeing the tapped reason.

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
*d* is 2 seconds for the primary sensitivity analysis and is varied over 1, 2, 4 and 8 seconds.

### 9.2 Q1: accuracy

| | Definition |
|---|---|
| Primary | Item accuracy of CasePath = correct chain items / (correct + incorrect chain items) of the frozen run, per case and pooled |
| Secondary | The same for the comparator; reference coverage = reference items present / reference items, for both; accuracy by item kind; share "cannot be decided"; the same on the eight development dossiers, reported beside the sealed cases |
| Counts against the claim that CasePath adds value over a single prompt | The comparator's accuracy or coverage is equal or higher on two of three cases |

### 9.3 Q2: reliance

| | Definition |
|---|---|
| Hypothesis H2 | Experts change wrong items more often than right ones |
| Primary | For each chain item with gold correct or incorrect: the share of the five experts who changed it. Statistic: mean share over incorrect items minus mean share over correct items |
| Secondary | Over-reliance = kept incorrect / incorrect items; under-reliance = changed correct / correct items; both per expert, per case and pooled, under two definitions of kept (kept = fates 4–6; verified = fate 4 only); the share of corrections whose new value is correct; agreement among the five experts per item (Fleiss' kappa on changed / kept) |
| Sensitivity | Seen / unseen at each threshold *d*; without capped cases; without items of cases an expert knew before |
| Counts against H2 | The primary statistic is zero or negative, or fewer than four of five experts show a positive difference |

### 9.4 Q3: effort and the reveal (descriptive)

| | Definition |
|---|---|
| Primary | On the unaided case: accuracy over decision units of (a) the unaided answer, (b) the same expert's answer after the reveal, (c) CasePath alone, each against gold |
| Secondary | Active time per case (idle excluded) for unaided and aided work; corrections per case; letter change ratio; the share of post-reveal changes that move to CasePath's answer, split by whether CasePath was right; relative AI reliance (units where the unaided answer was wrong and CasePath right: share whose final answer is CasePath's) and relative self-reliance (units where the unaided answer was right and CasePath wrong: share whose final answer stays right), both as counts with denominators |
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

**Gate (nested).** A proposal is replayed on the stored runs of the training cases and the eight development dossiers.
It passes if no training-case accuracy and neither development reference score (share of reference documents
requested; share of requests in the reference) falls. Knowledge is never applied to its own origin case, so the gate
in effect tests the other training case and the development dossiers. The gate never sees the held-out case's gold.

**Activation in replay.** Every proposal that passes is activated; no person chooses.

| | Definition |
|---|---|
| Folds | Three: each sealed case held out once; Knowledge from the other two |
| Primary | Held-out item accuracy and the two reference scores, before and after the activated Knowledge, per fold |
| New items | An item that appears only after replay and is not in the reference counts as an unnecessary request; a sensitivity analysis uses the adjudicators' blind label |
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
Adjudicator agreement: Cohen's kappa on correct / incorrect / cannot be decided. Calibration: case accuracy for
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
| Expert knew a case before | Kept; sensitivity analysis without those expert-case pairs |
| Expert took part in the reference or the gold | Kept; reported; sensitivity analysis without that expert |
| Withdrawal | All records of the expert are removed; the analyses run on the rest; the number is reported |
| Item-list hash mismatch at session start | The session does not start until the copy is restored |

## 12. Privacy

The record measures CasePath. Two exports exist. The **pseudonymous export** holds no case content, only
identifiers, statuses, counts, relative times and randomised expert labels; a guard rejects free text. The
**content export** (item texts, notes, recall transcripts) never leaves the insurer. No result is reported per named
person. Per-expert values are shown unlabelled.

## 13. Versioning and freeze

1. Changes to this draft are made by new versions (0.2, 0.3 …), each committed.
2. **Freeze**, before the first session, as version 1.0, which records:
   - the commit hash of this document's repository at freeze;
   - the product commit and the parity manifest's source-tree hash;
   - the SHA-256 of each frozen run's result and item list, and of the variation runs;
   - the SHA-256 of the allocation table after the lot (with the lot seed), of the comparator prompt and of the adjudicators' gold file;
   - the permutation seed for T1 and the bootstrap seed.
3. The frozen version is deposited with a timestamp (an internal registry and, if the paper's venue requires, a public registry with the content-free parts).
4. Any change after the freeze is a dated **deviation**, listed in the paper with its reason.

## 14. Open choices (to settle before the freeze)

1. Whether the three cases share a process family with each other and with the development dossiers. If not, Q4's cross-case claim is dropped before the freeze.
2. The number of variation runs (four proposed) and of comparator runs (one or three), given the internal token budget.
3. The time caps (15 + 15 and 25 minutes proposed).
4. The dwell threshold for the primary sensitivity analysis (2 seconds proposed).
5. The position of the unaided case: always first (proposed) or rotated (positions 1, 2, 3, 3, 2 for E1–E5, which balances position but exposes three experts to CasePath on a study case before their unaided answer).
6. Whether the expert learns at the end which kept items were wrong (proposed: only if asked).
7. Whether the eight development dossiers have gold of the same kind; if not, Q1 on them uses the reference scores only.
8. Exact item wordings of the two scales, copied from their sources.
