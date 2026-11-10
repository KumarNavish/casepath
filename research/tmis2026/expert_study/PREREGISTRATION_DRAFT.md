# Pre-registration: expert review of an agentic case-preparation system

Becomes 1.0 at the freeze (section 13), when the decision points and hashes are recorded; nothing else may change.

**Change note (2026-11-10).** Rewritten to the interface-only design: no expert time beyond the sessions, and all
expert input through the CasePath interface. Removed: adjudicators and gold labels; accuracy claims (replaced by
agreement with what the insurer did); the hypothesis that experts change wrong items more than right ones over all item
kinds (replaced by reliance on document requests against practice); trust and workload scales; the stimulated-recall
conversation and blind coding of reasons; rater agreement between an adjudicator and the automated labeller; blind
labelling of the comparator; the unaided-versus-aided effort comparison. Verified German wordings of the NASA-TLX and
of two Trust in Automation subscales remain in the repository history (commit `c05cec8a`,
`SCALES_AND_RECALL_GUIDE.md`) if a later study wants them.

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
workflow file and of each Knowledge item (content fields only), and the model provider and name.

**Link to the outside experiments.** The same product is evaluated outside the insurer on synthetic claims. The two
deployments run the same code commit and the same workflow format and rules, shown by equal source-tree hashes in the
parity manifest. They differ in two declared ways only: the model (the insurer's gateway model inside; the model
`gpt-6-luna` outside) and proprietary data (the insurer's process catalogue, Knowledge and cases inside).

**The only instrument is the experts' ordinary work in CasePath.** There is no adjudicator, no questionnaire, no
interview and no question outside the interface.

## 2. Research questions

| | Question | Estimation target |
|---|---|---|
| Q1 | How far does CasePath agree with what the insurer did, and compared with a single prompt? | Agreement of CasePath's document requests, step and next action with the insurer's practice at the decision point (P) and later (P-later); the same for a single-prompt comparator |
| Q2 | What do five experts do with the same items? | Agreement among the five per item; items changed by at least three of five; reliance on document requests against practice; change after the reveal on the first case |
| Q3 | What does work with CasePath look like? | Time, interventions, letter change, closing form (descriptive) |
| Q4 | Does CasePath improve from corrections on a case whose corrections it has not seen, without harm? | Change in agreement with P on the held-out case after Knowledge learned from the other two, with a nested gate |
| Q5 | Why do experts change things? | Distribution of the six reasons; agreement of reasons where several experts change the same item |

## 3. Participants and cases

- **Experts.** Five claims experts of the insurer's legal-protection unit. No more will be recruited. Each agrees individually, may withdraw at any time and may have their records removed. The insurer's consent is in place. No expert time is used beyond the sessions.
- **Cases.** Eleven closed dossiers of an internal hackathon, all tenancy-defect (mould) cases, for which the insurer's explicit process reference exists. **Study cases**: D2, D4, D7. **Reserve**: D5, held back in the same way as the study cases. **Development dossiers**: D1, D3, D6, D8, D9, D10, D11 (seven). The three study cases share a process family with each other and with the development dossiers.
- **Inclusion criterion.** The three study cases route to the common workflow. This is checked from routing alone, before the freeze, and recorded.
- **Reserve rule.** D5 replaces a study case only before the first session, and only for a reason listed here in advance: the inclusion criterion fails, the cut copy cannot be made, or a leak cannot be removed. Never after the first session. If D5 is not used, it is reported as unused and is not analysed.
- **Development dossiers.** They carry **development labels**, made by a single labeller who also builds the product. Their results are reported separately under that name, never pooled with the study cases, and no test (section 10) uses them. D8 is also the case of the formative step (section 4.5) and stays a development dossier.
- **Practice case.** One synthetic case, five minutes, before the study cases.
- **Inference** is conditional on these three cases, this insurer, this process and these five experts. No population claim is made.

### 3.1 Decision point

The dossiers are whole closed files. On the full file, document status is confounded (documents count as present
because they arrived later) and "next action" is undefined. Each study case is therefore cut at one **decision point**.

1. **Rule.** The decision point is the state of the file immediately before the insurer's first outgoing request for documents or information in that case (to the client or to the other party). If a case has no such request, it is the state before the case's first outgoing action of any kind. The point is fixed by this rule, not by choice. Its date and the rule's application (which outgoing action, and why it is the first) are recorded per case before any run on the cut copy.
2. **Cut copy.** A case copy holding only the documents (or page ranges) dated up to the decision point. The frozen run, the four variation runs, the single-prompt comparator, the own-answer view, the experts' work and the replay for Q4 all use the cut copy. Nobody in a session sees anything dated after the decision point.
3. **Second decision point (optional, secondary).** A second, later point per case may be added for the system only, with no expert time. If it is done, it is done for all three cases, its rule is the state before the insurer's second outgoing action, its status source is the insurer's second action (recorded like P), and it is reported as exploratory.

### 3.2 Development exposure

The three study cases and the reserve are among the eleven dossiers the product was developed on until the seal. This
is a limit of the study. It is reduced as follows:

1. **Seed Knowledge** is rebuilt without D2, D4, D7 and D5; its content hash is in the freeze record. The seed Knowledge is built from the insurer's request letters on the development dossiers; the letters of the study cases and the reserve are excluded.
2. **New cut copies.** No run on a cut copy exists before the frozen run, and none may be made before the freeze except the frozen and variation runs themselves.
3. **Development-exposure record**, made before the freeze from the product's commit history: the commits before the seal whose change was derived from D2, D4, D7 or D5, listed by hash with one line each.
4. **Consequences for claims.** Q1 on the study cases is agreement on cases seen in development and is labelled so; performance on unseen cases comes from the outside experiments on sealed synthetic claims. Q2, Q3 and Q5 describe what experts do with the stored items and do not need the cases to be unseen. Q4's held-out case is held out from the corrections, not from development, and this is said wherever Q4 is reported.

### 3.3 The process reference is the workflow's source

The process CasePath executes for these cases was built from the process reference (R). Therefore the structure of the
process (its steps, the conditions, and the documents each step demands) is the reference by construction and is not
scored. Q1 measures where CasePath places the case on a given process and what it asks for, against what the insurer
did; it is not evidence that the process itself is right, and not evidence about process discovery.

## 4. Materials produced before the first session

### 4.1 Frozen runs

1. The product commit, workflow catalogue and Knowledge store are fixed. The Knowledge store is the seed Knowledge rebuilt without D2, D4, D7 and D5 (section 3.2). The parity manifest and the seed Knowledge content hash are recorded.
2. Each of the three cut copies (section 3.1) is run once. The stored run is the **frozen run**. Its record holds: the run, the hash of its result (SHA-256 of canonical JSON), the item list (section 5) and its hash, and the parity manifest.
3. Each cut copy is run four more times under the same manifest. These **variation runs** are never shown to an expert. They give run-to-run variation (section 9.6). No other run is made on a cut copy before the freeze.
4. During the study period the Knowledge store is read-only, no run is started on a study case, no re-check is made, and no model call is made in a session.
5. Each expert works on their own copy of each cut copy, with a `source_case` field naming the study case. Every copy points to the frozen run. A session starts only if the copy's item-list hash equals the frozen run's and its cut hash equals the recorded one. Nothing learned from one expert reaches the next.

### 4.2 Comparator

On each cut copy, one run of the same model with a single prompt, given the same case files (the same text
extraction), the same workflow catalogue and the same active Knowledge in context, asked for: the process step, the
documents to request and the next action, each as **catalogue entries** (step ids, document ids, action kinds). The
prompt is fixed in advance and attached to the frozen version of this document. The comparator is scored mechanically
against P with the same catalogue mapping; no blind labelling is done. One run per case is primary. Two more runs per
case are made only if the internal token budget allows (about 6M non-cached tokens in total for the study); if made,
they are secondary.

### 4.3 Where an item's status comes from

There is no gold. Each source below is kept apart in the data; sources are never merged into one label.

| Source | What it is | Made by, and when | Independent of CasePath's result? |
|---|---|---|---|
| **P**, practice | What the insurer did after the decision point, from the later pages of the file: the documents and information requested in its first outgoing request, and its next action | Transcribed and mapped to catalogue entries by the product builder's automated labeller before any run on the cut copy exists; the verbatim passage is kept in the inside export; hashed. The study lead (the paper's corresponding author; not an expert of the insurer, so no expert time) checks the three transcriptions against the file; the check is recorded | yes |
| **P-later** | Documents the insurer requested at any later point of the file | As P, same time, same check | yes |
| **O**, own answers | The experts' pick-list answers on their first study case (two, two and one expert per case), given before CasePath is shown | In the sessions | yes |
| **C**, consensus of the others | For each expert and item, what the other four experts did with it (kept, changed, to what); never the expert's own vote | Derived from the sessions | no: formed under exposure to CasePath's result |
| **R**, the process reference | The process itself | Exists; its structure is not scored (section 3.3) | yes |
| **A**, automated labels | The product builder's labeller, one label per item of every frozen run | Made and hashed before any session | a single non-expert automated labeller; reported as a separate line, never combined with the others |

**Settled and unsettled.** An item is **settled** only where a source independent of CasePath's result speaks to it:
P, P-later or O. Document requests, the next action and the step can be settled; facts, deadlines and document status
mostly cannot. Items that no independent source speaks to are reported as **unsettled**, with what C and A say shown
beside them, and are never called right or wrong.

**Prior handling.** Whether an expert handled a case before is taken from the file's metadata by the labeller (a flag
per expert and case in the inside data). It is not asked.

### 4.4 Cut verification

For each cut copy: the list of included documents or page ranges with their dates, made with the cut copy and checked
by the study lead against the full file for leaks (later-dated pages inside merged PDFs, later notes, stamps,
summaries written after the point, file names that reveal later events), together with the check of P; and the SHA-256
of the cut copy. Both are recorded before the frozen run. A leak found after a session does not change the record: the
affected items are flagged, kept in the primary analyses and removed in a sensitivity analysis.

### 4.5 Formative step (pilot of the protocol)

On day 7 the process owner handles one development dossier, D8, at its decision point, with the same procedure as an
expert (practice case, own answer first, then CasePath's result, the three gestures). This is the pilot of the
protocol. The process owner labels nothing. The process owner takes part only in the formative step: no check, no label and no decision about the study cases is theirs. Changes made to the product on days 7–9 because of it are listed in the
study record (what changed, and what deliberately did not) and precede the freeze. D8 stays a development dossier. The
pilot's events are not part of any analysis.

## 5. Units

- **Item**: one statement of the frozen run on the cut copy, with a stable id; it is a statement about the case at the decision point. Kinds: process step, fact, deadline, document need (whether required, and its status: present, missing, unusable), document request, next action, letter clause, open point, summary field, party, timeline entry.
- **Chain items** (the primary universe for Q2): process step, facts that gate a step or a document, deadlines, document needs and requests, next action. All other kinds are recorded and analysed as exploratory.
- **Own-answer units** (first study case only): the process step (one unit); each catalogue document, requested or not (one unit each, over the union of the documents in P, CasePath's requests and the expert's own answer); the next action (one unit).
- **Not scored**: the structure of the process (section 3.3).
- Denominators are always the items of the frozen run. Items that appear only through propagation of a correction are not in any denominator; they are counted and reported.

## 6. Design and allocation

### 6.1 Session (about 75 minutes)

| Part | Time | What happens |
|---|---|---|
| Opening | 5 min | Consent, purpose, "use is measured to improve CasePath, not you" |
| Practice | 5 min | Synthetic case in the full tool |
| First study case | ≤ 25 min in all | Own answer first, at most 10 minutes: original files of the cut copy only, three pick-lists. Then CasePath's result appears and the expert reviews it like any case |
| Second and third study case | ≤ 20 min each | CasePath's result from the start |

The caps are proposed and must be confirmed by the product session before the freeze. Reaching a cap is an event.
When a cap is reached the screen says so and the current state is kept. A capped own answer is frozen as it stands; an
empty field counts as "not answered". A capped case is closed as it stands. Capped cases stay in the primary analysis
and are flagged; a sensitivity analysis drops them.

### 6.2 Own answer first

The own-answer view shows the original files of the cut copy only: page images or native text, no text read by the
model, no quotes, no highlights, no run output. Three pick-lists: the process step (from the workflow's steps, or "not
in the list"), the documents to request (from the workflow's document catalogue), and the next action (from the action
kinds). At the reveal the answer is frozen and stored with its time. Every later change is a separate event.

### 6.3 Allocation

Case labels A, B, C are assigned to D2, D4, D7 by lot. The case that is first for one expert only (C) is chosen by the
same lot. Expert labels E1–E5 are assigned to the five experts by lot. The lot is drawn by a person outside the
research team, with a recorded seed, before the first session; the table and the seed are in the freeze record.

| Expert | Position 1 (own answer first) | Position 2 | Position 3 |
|---|---|---|---|
| E1 | A | B | C |
| E2 | A | C | B |
| E3 | B | A | C |
| E4 | B | C | A |
| E5 | C | A | B |

The first case rotates: A, B and C are first for two, two and one experts. Positions 2 and 3 each hold every case at
least once.

### 6.4 Other rules

- Experts are asked not to discuss the cases until all five sessions are done.
- Session order (first to fifth) is recorded.
- Prior handling of a case comes from the file's metadata (section 4.3), not from a question.
- If experts are told afterwards which kept items the sources contradict, this happens after the last session, to all five together; it is not part of the study and records nothing.

## 7. Records

The feedback instrument is three gestures:

1. **Leave it.** Closing the case as "erledigt" or "erledigt, mit Vorbehalt" attests what was left unchanged.
2. **Change it in place**, with one of six reasons in one tap, "ohne Angabe" by default: (1) Steht anders in den Akten; (2) Steht nicht in den Akten; (3) Hier nicht relevant; (4) Gilt generell so; (5) Weiss ich von ausserhalb der Akten; (6) Formulierung.
3. **Anmerkung**: a free note on any screen or item, and one optional line at closing.

Every action is an event in an append-only log with a relative time (seconds since session start): case opened, item
on screen (interval), source opened, item confirmed, item corrected (before, after, reason), item dismissed (reason),
item added (what, reason), correction undone, point settled, note added, own answer saved, own answer frozen, reveal,
idle start and end, letter copied (change ratio), case closed (form, attestation), cap reached, technical failure. A
correction's consequences for other items (**propagation**) are recomputed without a model from the log and stored,
each with the id of the correction that caused it.

## 8. (Removed)

The scales and the recall conversation were removed on 2026-11-10 (change note).

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
dismissed. *Kept* = fates 4–6, attested by closing. Items with fate 3 are excluded and counted. The dwell threshold *d*
is 2 seconds (primary); 1 and 4 seconds are sensitivity analyses.

### 9.2 Q1: agreement with what the insurer did

| | Definition |
|---|---|
| What it measures | Agreement with practice, not accuracy. The insurer's action is practice, not proof of correctness; a correct extra request counts as disagreement unless P-later contains it. Labelled "on cases seen in development" (section 3.2) |
| Primary | Documents: of the documents in P, the share in CasePath's request; of CasePath's requests, the share in P, and separately the share in P-later (not in P). Next action: same as P or not. Step: same or not, against the step P's request belongs to in the catalogue mapping (where the mapping names one) and against O. Per case and pooled, for the frozen run, with the range over the four variation runs |
| Comparator | The same measures for the single-prompt comparator, scored mechanically against P with the same catalogue mapping |
| Secondary | The same measures against O (own answers on the first case) |
| Reported separately, not pooled, not tested | The same measures on the seven development dossiers, under the name "development labels" |
| Inference | Three cases; descriptive; no test |

### 9.3 Q2: what five experts do with the same items

| | Definition |
|---|---|
| Primary, agreement | For each chain item of the frozen run: kept or changed by each of the five. Fleiss' kappa and raw agreement, by item kind. The share of items changed by at least three of five (**consensus-changed**). It is only a lower bound on CasePath's errors: errors that fewer than three experts notice, or that all keep under exposure to CasePath's result, are not counted |
| Primary, reliance on document requests | With P as the independent status, per expert: of the documents in P that CasePath lacked, the share the expert added; of CasePath's requests in neither P nor P-later, the share the expert removed; of CasePath's requests in P, the share the expert removed (under-reliance) |
| Test (the only one) | Per expert: (share removed among CasePath's requests in neither P nor P-later) minus (share removed among CasePath's requests in P). One-sided sign test over the five experts; five of five gives p = 1/32, the smallest attainable p. "Not in practice" is not the same as wrong |
| First case | Change after the reveal, as counts over own-answer units (documents and next action): relative AI reliance = units where the own answer disagreed with P, CasePath agreed with P, and the final answer agrees with P / units where the own answer disagreed with P and CasePath agreed; relative self-reliance = units where the own answer agreed with P, CasePath disagreed, and the final answer agrees with P / units where the own answer agreed with P and CasePath disagreed (definitions of Schemmer et al. 2023, with P in place of ground truth). Counts with denominators |
| Checking behaviour | Verified-kept, seen-kept, unseen-kept, by item kind and by settled status, at *d* = 2 s (1 and 4 s as sensitivity) |
| Unsettled items | What C and A say, shown beside each; never called right or wrong |
| Not claimed | Appropriate reliance on facts, deadlines or document status: without an independent status it cannot be judged |
| Sensitivity | Without capped cases; without expert-case pairs flagged as prior handling; without items flagged by a leak (section 4.4) |

### 9.4 Q3: work with CasePath, described

Active time per case (idle excluded); interventions per case by kind (corrections, dismissals, additions, notes);
letter change ratio; closing with or without reservation, against agreement with P. Own-answer time is reported but is
not a baseline. No effort-saving claim and no comparison with unaided handling: the design has no unaided handling of a
whole case.

### 9.5 Q4: learning (model-free replay, leave one case out)

**Proposal rule (mechanical).** From the events of the two training cases, a Knowledge proposal is created for every
addition (document, step or question) that was made with reason 4 ("Gilt generell so") by at least two experts on the
same case, or that was made on both training cases, matched by catalogue id. Its scope is the case's process family and
the node the addition named. Only added documents, steps and questions become proposals (the product cannot turn other
corrections into Knowledge).

**Gate (nested).** A proposal is replayed on the stored runs of the training cases and the seven development dossiers.
It is activated only if it does not lower agreement with P on the training cases (the two document measures of 9.2) or
the development reference scores (share of reference documents requested; share of requests in the reference). The gate
is a mechanical filter, not a test. Knowledge is never applied to its own origin case. The gate never sees the
held-out case.

**Activation in replay.** Every proposal that passes is activated; no person chooses.

| | Definition |
|---|---|
| Folds | Three: each study case held out once; Knowledge from the other two. The held-out case is held out from the corrections, not from development (section 3.2). Replay runs on the cut copies |
| Primary | On the held-out case: the change in agreement with P (the two document measures of 9.2); and the share of consensus additions on the held-out case (additions made by at least three of five experts, by catalogue id) that the replayed Knowledge would have made unnecessary |
| Secondary | Number of proposals made, passed and stopped; leave one expert's events out of the training set, reported as agreement, not as learning; transfer to the development dossiers and to the synthetic claims, as regression checks |
| Scope | Replay changes the process and the checklist only. Knowledge that acts through what the agents read is not measured |
| Counts against the claim | Agreement with P on a held-out case falls; or no proposal passes the gate, in which case "no learning observed" is reported |

### 9.6 Q5: reasons, and other measures

| | Definition |
|---|---|
| Reasons | Distribution of the six reasons and of "ohne Angabe", by item kind |
| Reason agreement | Where two or more experts change the same item: whether they give the same reason (raw agreement, by item kind) |
| Anmerkungen | Counted by where they were left (screen, item kind, closing). Their content is read and grouped inside the insurer by the study owner; the grouping is exported without content. Exploratory |
| Run-to-run variation | For each item key, the share of the five runs (frozen and variation) with the same value |

## 10. Statistics

- **Estimation first.** Every measure is given per case, per expert (unlabelled) and pooled.
- **Intervals.** (a) Bootstrap over items within case, cases fixed, 10,000 resamples with a recorded seed, percentile intervals. (b) Over experts: all five values and the leave-one-expert-out range. (c) Leave-one-case-out range.
- **One test**: the per-expert sign test of section 9.3, one-sided; the smallest attainable p (1/32) is given beside the result.
- **Q4** has three folds; the direction in each fold is reported. No other test is run.
- **Exploratory.** Every analysis not listed in sections 9 and 10 is labelled exploratory.

## 11. Exclusions and handling

| Situation | Handling |
|---|---|
| Incomplete session | Completed cases are kept; missing cases are reported |
| Technical failure | Recorded as an event; the affected case is kept up to the failure and flagged; sensitivity analysis without it |
| Time-capped case | Kept and flagged; sensitivity analysis without it |
| Unsettled item | Reported as unsettled with C and A beside it; never scored right or wrong |
| Leak found in a cut copy after a session | Affected items flagged and kept; sensitivity analysis without them |
| Prior handling flag set | Kept; sensitivity analysis without those expert-case pairs |
| Reserve D5 used | Only before the first session and for a reason listed in section 3; the replaced case and the reason are reported |
| Withdrawal | All records of the expert are removed; the analyses run on the rest; the number is reported |
| Item-list or cut hash mismatch at session start | The session does not start until the copy is restored |

## 12. Privacy

The record measures CasePath. Two exports exist. The **pseudonymous export** holds no case content, only
identifiers, statuses, counts, relative times and randomised expert labels; a guard rejects free text. The
**content export** (item texts, notes, the verbatim passages behind P and P-later) never leaves the insurer. No result
is reported per named person. Per-expert values are shown unlabelled.

## 13. Versioning, timetable and freeze

1. This is version 1.0-rc. It becomes 1.0 at the freeze, when the decision points and hashes are recorded; nothing else may change.
2. **Timetable.** Day 0 is 2026-11-10. Formative step on day 7; changes from it on days 7–9. Freeze on day 10. Status sources recorded and hashed by day 13. First session planned for day 14 (2026-11-24) or soon after. Rule: **no session before the status-source hash exists.**
3. **Freeze**, on day 10, as version 1.0. The freeze commit contains exactly:
   - the commit hash of this document's repository at freeze;
   - the product commit and the parity manifest's source-tree hash;
   - per case: the decision-point date and the rule's application (section 3.1), the cut verification list and the SHA-256 of the cut copy (section 4.4), and the routing check of the inclusion criterion;
   - the P and P-later records per case with their SHA-256, and the study lead's check (section 4.3);
   - the content hash of the seed Knowledge rebuilt without D2, D4, D7 and D5 (section 3.2);
   - the development-exposure record (section 3.2);
   - the formative-step change list (section 4.5);
   - the SHA-256 of each frozen run's result and item list, and of the variation runs;
   - the SHA-256 of the automated label set A;
   - the allocation table after the lot, with the lot seed, and its SHA-256;
   - the SHA-256 of the comparator prompt;
   - the bootstrap seed.
4. **By day 13**, one status-source hash over P, P-later, the study lead's check and A is computed and added as a dated entry (not a deviation).
5. The frozen version is deposited with a timestamp (an internal registry and, if the paper's venue requires, a public registry with the content-free parts).
6. Any other change after the freeze is a dated **deviation**, listed in the paper with its reason.

## 14. Choices settled on 2026-11-10

1. Cases: study cases D2, D4, D7; reserve D5 with its rule; seven development dossiers; the three study cases share a process family with each other and with the development dossiers (section 3).
2. Interface-only design: no expert time beyond the sessions; three gestures; no adjudicator, scales or recall (change note, section 7).
3. Status sources P, P-later, O, C, R, A, kept apart; settled and unsettled items (section 4.3).
4. Session of about 75 minutes; first case rotates (2, 2, 1); proposed caps 25 (own answer ≤ 10), 20 and 20 minutes, to be confirmed by the product session before the freeze (section 6).
5. Formative step on D8 by the process owner on day 7 (section 4.5).
6. Four variation runs per case and the decision-point runs approved; one comparator run per case primary, three only if the budget allows; comparator output in catalogue entries, scored mechanically (section 4.2).
7. Dwell threshold 2 seconds primary; 1 and 4 seconds sensitivity (section 9.1).
8. One pre-stated test: the per-expert sign test on document-request removals (section 9.3).

## 15. Limits

- **No independent human adjudication.** Status rests on practice (P, P-later), own answers (O) and consensus (C). Shared blind spots that none of these reveal stay invisible.
- **Correctness of facts, deadlines and document status is not claimed.** No independent source speaks to them; they are reported as unsettled.
- **Practice is not correctness.** The insurer's action is one way of handling the case. The product's seed Knowledge was built from the same insurer's request letters on the development dossiers (the study cases' and the reserve's letters are excluded), so agreement with practice is partly agreement with what the product learned from that practice.
- **Consensus is formed under exposure** to CasePath's result, so it is not independent of it.
- **The automated labeller** is one non-expert labeller run by the product's builder; its labels are a separate line, never evidence of correctness.
- **No perception data.** What experts think of CasePath is known only from what they do and what they note.
- **Checks by the study lead.** The transcriptions of the insurer's requests and the cut copies are checked by the study lead, who is an author of this work and not a claims expert. The verbatim passages stay in the inside export, so a later check by anyone inside the insurer is possible.
- **The gate uses development labels.** On the development dossiers the gate relies on reference scores made by a single labeller who also builds the product.
- **The formative session shaped the product.** The process owner's session on D8 led to changes before the freeze (section 4.5).
- **Development exposure.** The study cases were among the dossiers the product was developed on (section 3.2).
- **Process reference.** The process CasePath executes was built from the process reference; its structure is not scored, and Q1 is not evidence that the process itself is right.
- **Learning.** Only added documents, steps and questions become Knowledge, and replay changes the process and the checklist only (section 9.5).
- **Scope.** Three cases, one insurer, one process, five experts; inference is conditional on them.
