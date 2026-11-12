# Pre-registration: archival agreement and expert review of an agentic case-preparation system

Becomes 1.0 at the freeze (section 13), when the product's freeze hash and the development counts behind the
predictions are recorded. The decision points and the records made after the freeze hash are added as dated entries in
the order of section 4.3 (section 13.4); nothing else may change.

**Change note (2026-11-10).** Rewritten to the interface-only design: no expert time beyond the sessions, and all
expert input through the CasePath interface. Removed: adjudicators and gold labels; accuracy claims (replaced by
agreement with what the insurer did); the hypothesis that experts change wrong items more than right ones over all item
kinds (replaced by reliance on document requests against practice); trust and workload scales; the stimulated-recall
conversation and blind coding of reasons; rater agreement between an adjudicator and the automated labeller; blind
labelling of the comparator; the unaided-versus-aided effort comparison. Verified German wordings of the NASA-TLX and
of two Trust in Automation subscales remain in the repository history (commit `c05cec8a`,
`SCALES_AND_RECALL_GUIDE.md`) if a later study wants them.

**Change note (2026-11-11).** The insurer's process diagrams describe the customer's intake chat, not the handler's
work. Mould cases now route to a handler process written by the product's builders (section 3.3). Changed: the cases
(section 3), the handler process and its source (3.3), a rule against leakage and the order at the freeze (4.3, 13),
the status sources (4.3: R removed; the step is settled only by O), Q1 (2, 9.2), the pick-lists (6.2), the limits (15).
The document stays at 1.0-rc until the freeze.

**Change note (2026-11-12).** The primary endpoint is now an archival comparison on the real files that needs no
expert time. Each of the four sealed dossiers (D2, D4, D7 and the reserve D5) is cut just before every recorded
outgoing action of the insurer. CasePath and the single-prompt comparator are run on each cut copy at the frozen
commit, and their output is compared with what the insurer did next (section 9.2). The expert sessions are the
secondary endpoint. Q1 moved into the primary endpoint; Q2–Q5 and the session procedure are unchanged. Added:
predictions from the builders' development counts (9.2); a second, independent transcription of practice (4.3); the
state of the deciding facts at each decision point (4.6); a registered leave-one-dossier-out replay on the development
dossiers, reported as development evidence (9.7); the requirements to the product's builders (16). Changed: the title,
the system section (1), the research questions (2), the cases (3), the decision points (3.1; the optional second point
is removed, because every later action is now a decision point), development exposure (3.2), the runs and the
comparator (4.1, 4.2), the status sources and the order at the freeze (4.3), cut verification (4.4), units (5), the
measures (9.2, 9.3, 9.5), statistics (10), exclusions (11), privacy (12), timetable and freeze (13), choices (14),
limits (15). No section was renumbered. The document stays at 1.0-rc until the freeze.

| | |
|---|---|
| Document | Pre-registration of the CasePath archival comparison and expert study |
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

**Two instruments.** The primary endpoint needs no expert. It compares CasePath's output on cut copies of four sealed
files with what the insurer did next (section 9.2). For the secondary endpoint, the only instrument is the experts'
ordinary work in CasePath. There is no adjudicator, no questionnaire, no interview and no question outside the
interface.

## 2. Research questions

| | Endpoint | Question | Estimation target |
|---|---|---|---|
| Q1 | Primary | How far does CasePath agree with what the insurer did next, at every decision point of four sealed files, and compared with a single prompt? | Per decision point of D2, D4, D5 and D7 (section 3.1): routing; the documents the insurer requested that CasePath names, and CasePath's extra requests; the same action kind A1–A12 as the insurer's; the follow-up period; and, descriptively, the state of the deciding facts and how CasePath treated them. Counts with exact binomial intervals, per dossier and pooled; the same for a single-prompt comparator given the same handler process and catalogues. Compared with predictions stated before the freeze. No expert time. The step is not part of Q1 |
| Q2 | Secondary | What do five experts do with the same items? | Items kept or changed by each expert; agreement among the five per item; items changed by at least three of five; reliance on document requests against practice; change after the reveal on the first case |
| Q3 | Secondary | What does work with CasePath look like? | Time, interventions, letter change, closing form (descriptive) |
| Q4 | Secondary | Does CasePath improve from corrections on a case whose corrections it has not seen, without harm? | Change in agreement with P on the held-out case after Knowledge learned from the other two, with a nested gate |
| Q5 | Secondary | Why do experts change things? | Distribution of the six reasons; agreement of reasons where several experts change the same item |
| DA | Registered development analysis | What do practice Knowledge items add to the law-derived handler process on a development dossier whose Knowledge was not used? | Leave-one-dossier-out replay on the seven development dossiers, two arms ("law only", "law plus practice"), measures 9.2 (b)–(d). Development evidence, labelled so (section 9.7) |

## 3. Participants and cases

- **Experts.** Five claims experts of the insurer's legal-protection unit, for the secondary endpoint only. No more will be recruited. Each agrees individually, may withdraw at any time and may have their records removed. The insurer's consent is in place. No expert time is used beyond the sessions. The primary endpoint uses no expert time.
- **Cases.** Eleven closed dossiers of an internal hackathon, all tenancy-defect (mould) cases. **Sealed dossiers**: D2, D4, D5, D7. **Study cases** for the expert sessions: D2, D4, D7. **Reserve** for the expert sessions: D5, held back in the same way as the study cases. For the primary endpoint, D5 is a fourth case and is always analysed. **Development dossiers**: D1, D3, D6, D8, D9, D10, D11 (seven). The sealed dossiers share a process family with each other and with the development dossiers.
- **Inclusion criterion (expert sessions).** The three study cases route to the common workflow, the handler process (section 3.3). This is checked from routing alone on the cut copy of the expert decision point (section 3.1), after the product's freeze hash exists (section 4.3), and recorded with the dated entries (section 13.4). The primary endpoint has no inclusion criterion: routing is one of its measures, and a decision point that does not route to the handler process is analysed as it stands.
- **Reserve rule (expert sessions).** D5 replaces a study case only before the first session, and only for a reason listed here in advance: the inclusion criterion fails, the cut copy cannot be made, or a leak cannot be removed. Never after the first session. If D5 is not used in the sessions, it is reported as unused for the secondary endpoint. Whether or not D5 is used in the sessions, all four sealed dossiers stay in the primary endpoint.
- **Development dossiers.** They carry **development labels**, made by a single labeller who also builds the product. Their results are reported separately under that name, never pooled with the sealed dossiers, and no test (section 10) uses them. Their counts are the basis of the predictions (section 9.2) and their replay is the development analysis (section 9.7). D8 is also the case of the formative step (section 4.5) and stays a development dossier.
- **Practice case.** One synthetic case, five minutes, before the study cases.
- **Inference.** The primary endpoint is conditional on these four dossiers, this insurer and this process family. The secondary endpoint is conditional on these three cases, this insurer, this process and these five experts. No population claim is made.

### 3.1 Decision points

The dossiers are whole closed files. On the full file, document status is confounded (documents count as present
because they arrived later) and "next action" is undefined. Each sealed dossier is therefore cut at **decision
points**.

1. **Rule.** A decision point is the state of the file immediately before a recorded outgoing action of the insurer: a letter, email or other message the insurer sent out of the case (to the client, the other party, a lawyer, an expert or a court). Every such action makes a decision point, not only the first. Internal notes are not outgoing actions. Decision points are numbered in the order of the file (DP1, DP2, ...). Outgoing actions dated the same day form one decision point; its requested documents are the union of theirs, and the next action agrees if it is the kind of any of them; the number of such merged points is reported. The points are fixed by this rule, not by choice. For each, the action's date (as an offset in days from the dossier's first document), the action and the rule's application are recorded before any run on its cut copy.
2. **Expert decision point.** For the expert sessions, each study case keeps one decision point, fixed by the rule used so far: the decision point immediately before the insurer's first outgoing request for documents or information in that case (to the client or to the other party); if a case has no such request, DP1. It is one of the decision points of rule 1, and its index is recorded.
3. **Cut copy.** For each decision point, a case copy holding only the documents (or page ranges) that precede the action. Documents of the same day whose order relative to the action cannot be told are left out and listed. All runs at a decision point use its cut copy. The frozen run, the four variation runs, the comparator runs used in Q2, the own-answer view, the experts' work and the replay for Q4 use the cut copy of the expert decision point. Nobody in a session sees anything dated after the expert decision point.
4. **Number of decision points.** It is known only after the cuts are made, after the freeze (section 13). It is not chosen and not capped.
5. **Second decision point.** The optional, system-only second point of earlier versions is removed (2026-11-12). Every later outgoing action is now a decision point of the primary endpoint.

### 3.2 Development exposure

The four sealed dossiers are among the eleven dossiers the product was developed on until the seal. This is a limit of
the study. It is reduced as follows:

1. **Seed Knowledge** is rebuilt without D2, D4, D7 and D5; its content hash is in the freeze record. The seed Knowledge is built from the insurer's request letters on the development dossiers; the letters of the sealed dossiers are excluded.
2. **New cut copies.** No run on a cut copy of a sealed dossier exists before the product's freeze hash, and the only runs made on them are those of sections 4.1 and 4.2.
3. **Development-exposure record**, made before the freeze from the product's commit history: the commits before the seal whose change was derived from D2, D4, D7 or D5, listed by hash with one line each. It also holds a statement by the product's builders of which dossiers' later pages (after the first decision point) any builder had read before the freeze; the expected answer is the seven development dossiers only.
4. **Consequences for claims.** Q1 is agreement on files seen in earlier development but not used for the handler process (section 3.3), and is labelled so. Performance on unseen cases comes from the outside experiments on sealed synthetic claims. Q2, Q3 and Q5 describe what experts do with the stored items and do not need the cases to be unseen. Q4's held-out case is held out from the corrections, not from development, and this is said wherever Q4 is reported. The development analysis (9.7) is in-sample for the handler process and is labelled development evidence.

### 3.3 The handler process and where it comes from

The process diagrams the insurer provided describe the customer's intake chat, not the handler's work. They stay in
the product as the source of intake facts only.

Mould cases route to a **handler process** (`casepath/process/workflow_seed/mietmangel-handler.json`). The product's
builders wrote it, with its catalogue of the handler's action kinds (A1–A12, defined in the product's handler process;
for example A1 first request, A5 assessment, A6 pending with deadline, A12 closing), from two sources: what the
insurer did in the seven development dossiers (D1, D3, D6, D8, D9, D10, D11), and the law. No study case (D2, D4, D7)
was used for it, and not the reserve (D5).

The handler process is therefore the system under study, not a reference. No source scores it as a whole. The
reference for the handler's path is what the insurer did in each file at each decision point (P, section 4.3). On the
four sealed dossiers, agreement with practice is a test on files the handler process was not written from. It is not
evidence that the process is right, and not evidence about process discovery.

## 4. Materials produced before the first session

### 4.1 Frozen runs

1. The product commit, workflow catalogue (with the handler process and its action catalogue, and the law-only variant of section 9.7 if it exists) and Knowledge store are fixed and hashed first, in the order at the freeze (section 4.3). The Knowledge store is the seed Knowledge rebuilt without D2, D4, D7 and D5 (section 3.2). The parity manifest and the seed Knowledge content hash are recorded.
2. **Archival runs.** Every cut copy of every decision point of the four sealed dossiers (section 3.1) is run once at the frozen commit. At the expert decision point of a study case, this run is the frozen run. No run sees another run's output, and nothing is learned between runs.
3. **Frozen run.** The run on the cut copy of each study case's expert decision point. Its record holds: the run, the hash of its result (SHA-256 of canonical JSON), the item list (section 5) and its hash, and the parity manifest.
4. **Variation runs.** Each cut copy of an expert decision point is run four more times under the same manifest. These runs are never shown to an expert. They give run-to-run variation (sections 9.2, 9.6). No other run is made on a cut copy.
5. During the study period the Knowledge store is read-only, no other run is started on a sealed dossier, no re-check is made, and no model call is made in a session.
6. Each expert works on their own copy of each expert cut copy, with a `source_case` field naming the study case. Every copy points to the frozen run. A session starts only if the copy's item-list hash equals the frozen run's and its cut hash equals the recorded one. Nothing learned from one expert reaches the next.

### 4.2 Comparator

On each cut copy of each decision point, one run of the same model with a single prompt, given the same case files
(the same text extraction), the same handler process as text, the same action catalogue (A1–A12) and document
catalogue, and the same active Knowledge in context, asked for: the process step, the documents to request now and
the next action, each as **catalogue entries** (step ids, document ids, action kinds); for the next action its
`next_in_days` and `follow_up`; and for each deciding fact of the step it names, whether it treats the fact as
admitted, presumed or held with a question. The step is recorded but is not part of Q1 (section 9.2). If the
comparator is not given the same handler process and the same catalogues, the comparison is not reported. The prompt
is fixed in advance and its hash is in the freeze record. The comparator is scored mechanically against P with the
same catalogue mapping; no blind labelling is done. One run per decision point is primary. Two more runs per expert
decision point are made only if the internal token budget allows (about 6M non-cached tokens in total for the study);
if made, they are secondary.

### 4.3 Where an item's status comes from

There is no gold. Each source below is kept apart in the data; sources are never merged into one label.

| Source | What it is | Made by, and when | Independent of CasePath's result? |
|---|---|---|---|
| **P**, practice (one record per decision point) | What the insurer did in the outgoing action of the decision point, from the file: the documents and information requested in it; the action as an action kind of the frozen catalogue (or "other"), with `next_in_days` and `follow_up` where the file shows them; and the number of days to the insurer's next recorded outgoing action | Two transcriptions, each mapped to the frozen catalogue after the product's freeze hash exists and before any run on the cut copy (order at the freeze, below). **T1**: the product builder's automated labeller. **T2**: a session that did not build the product and sees neither T1 nor any CasePath or comparator output. Each is hashed. The verbatim passages are kept in the inside export. Where T1 and T2 disagree, the study lead (the paper's corresponding author and one of the product's builders; not an expert of the insurer, so no expert time) settles the disagreement against the file with a logged reason, before any CasePath or comparator run on a cut copy of a sealed dossier is made. Both versions are kept. The settled P is hashed | yes |
| **P-later** | For the expert decision point of a study case: the documents the insurer requested at any later decision point | Derived from the settled P records of the later decision points | yes |
| **O**, own answers | The experts' pick-list answers on their first study case (two, two and one expert per case), given before CasePath is shown | In the sessions | yes |
| **C**, consensus of the others | For each expert and item, what the other four experts did with it (kept, changed, to what); never the expert's own vote | Derived from the sessions | no: formed under exposure to CasePath's result |
| **A**, automated labels | The product builder's labeller, one label per item of every frozen run | Made and hashed before any session | a single non-expert automated labeller; reported as a separate line, never combined with the others |

The handler process is not a status source (section 3.3). P is the reference for document requests, the next action as
an action kind of the catalogue, and the follow-up period. Routing is right when the cut copy routes to the handler
process, the common workflow of these mould cases. An action in the file that fits no catalogue entry
is recorded as "other" and counts as disagreement for every system. The process **step** is not settled by P: it is
settled only by the experts' own answers on their first case (O); otherwise it is unsettled.

**Settled and unsettled (secondary endpoint).** An item is **settled** only where a source independent of CasePath's
result speaks to it: P, P-later or O. Document requests and the next action can be settled by P (and P-later) and by
O; the step only by O, on each expert's first case; facts, deadlines and document status mostly cannot. Items that no
independent source speaks to are reported as **unsettled**, with what C and A say shown beside them, and are never
called right or wrong.

**No reading of later pages before the freeze.** No person and no session that can change the product reads the pages
after a sealed dossier's first decision point (DP1) before the product's freeze hash exists. This holds for all four
sealed dossiers and for every decision point. Finding the decision points, making the cut copies and checking them for
leaks (sections 3.1, 4.4) therefore also come after that hash.

**Order at the freeze.**

1. The product, with the handler process, the action catalogue and the law-only variant (section 9.7, if it exists), is frozen and hashed. The document becomes version 1.0 (section 13).
2. The decision points of the four sealed dossiers are found, the cut copies made and checked for leaks (sections 3.1, 4.4). The records are hashed.
3. T1 and T2 transcribe P at every decision point and classify the deciding facts (section 4.6), each without the other's record and without any run output. Each set is hashed.
4. The study lead settles the disagreements between T1 and T2 against the file, with a logged reason, and both versions are kept. The settled P is hashed. No run on a cut copy of a sealed dossier exists yet, so no output can inform a settlement.
5. The runs are made on the cut copies: the archival runs, with the frozen run and the variation runs at the expert decision points (section 4.1), and the comparator runs (section 4.2). The automated labels A are made on the frozen runs. The hashes are recorded.
6. The archival results (section 9.2) are computed mechanically. One **archival hash** is computed over the records of steps 2–6 and A.
7. No session starts before the archival hash exists.

**Prior handling.** Whether an expert handled a case before is taken from the file's metadata by the labeller (a flag
per expert and case in the inside data). It is not asked.

### 4.4 Cut verification

For each cut copy of each decision point: the list of included documents or page ranges with their dates, made with
the cut copy and checked by the study lead against the full file for leaks (later-dated pages inside merged PDFs, later
notes, stamps, summaries written after the point, file names that reveal later events); and the SHA-256 of the cut
copy. Both are made after the product's freeze hash exists (section 4.3) and recorded before any run on that cut copy.
A leak found after a run does not change the record: the affected decision points (primary endpoint) and items
(secondary endpoint) are flagged, kept in the primary analyses and removed in a sensitivity analysis.

### 4.5 Formative step (pilot of the protocol)

On day 7 the process owner handles one development dossier, D8, at its decision point, with the same procedure as an
expert (practice case, own answer first, then CasePath's result, the three gestures). This is the pilot of the
protocol. The process owner labels nothing. The process owner takes part only in the formative step: no check, no label and no decision about the sealed dossiers is theirs. Changes made to the product on days 7–9 because of it, including changes to the handler process, are listed in the
study record (what changed, and what deliberately did not) and precede the freeze. D8 stays a development dossier. The
pilot's events are not part of any analysis.

### 4.6 Deciding facts at each decision point

A **deciding fact** is a fact that the frozen handler process uses as a condition of a step or of a document need. At
each decision point, T1 and T2 classify every deciding fact of the handler process, from the cut copy only, as
**stated** (the file states it), **open** (the file raises it but does not settle it) or **not addressed** (the file
does not speak to it). They do this with P, before any run and without any run output (order at the freeze, section
4.3). Disagreements are settled as for P. The classification is used only for measure (e) of section 9.2, restricted
to the deciding facts of the steps the system reached at that decision point.

## 5. Units

- **Decision point** (the unit of the primary endpoint): one recorded outgoing action of the insurer in a sealed dossier, with its cut copy (section 3.1). The dossier is the cluster. Documents in P and CasePath's requests are counted within decision points.
- **Deciding fact at a decision point** (measure (e) of the primary endpoint): one deciding fact of a step the system reached, with its state in the file (section 4.6).
- **Item** (secondary endpoint): one statement of the frozen run on the cut copy of the expert decision point, with a stable id; it is a statement about the case at that decision point. Kinds: process step, fact, deadline, document need (whether required, and its status: present, missing, unusable), document request, next action, letter clause, open point, summary field, party, timeline entry.
- **Chain items** (the primary universe for Q2): process step, facts that gate a step or a document, deadlines, document needs and requests, next action. All other kinds are recorded and analysed as exploratory.
- **Own-answer units** (first study case only): the process step (one unit; its status comes from O only); each catalogue document, requested or not (one unit each, over the union of the documents in P, CasePath's requests and the expert's own answer); the next action (one unit, an action kind A1–A12).
- **Expert** (secondary endpoint): per-expert values, as in sections 9.3 and 10.
- **Not scored as a whole**: the handler process; it is the system under study, not a reference (section 3.3).
- For the secondary endpoint, denominators are always the items of the frozen run. Items that appear only through propagation of a correction are not in any denominator; they are counted and reported.

## 6. Design and allocation

This section concerns the expert sessions (secondary endpoint). It is unchanged by the change of 2026-11-12.

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
model, no quotes, no highlights, no run output. Three pick-lists: the process step (from the handler process's steps,
or "not in the list"), the documents to request (from the document catalogue), and the next action (from the action
catalogue A1–A12, defined in the product's handler process). At the reveal the answer is frozen and stored with its time. Every later change is a separate event.

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

The primary endpoint keeps its own records: the decision-point record, the P record with both transcriptions, and the
archival result per system and decision point. They hold counts and ids, no content.

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

### 9.2 Q1 (primary endpoint): archival agreement with practice

| | Definition |
|---|---|
| What it measures | Agreement with the insurer's practice at every decision point of the four sealed dossiers D2, D4, D5, D7 (section 3.1), for CasePath at the frozen commit and for the single-prompt comparator. Agreement, not accuracy: the insurer's action is practice, not proof of correctness. Labelled "on files seen in earlier development, not used for the handler process" (section 3.2). No expert time |
| Unit | The decision point; the dossier is the cluster (section 5) |
| (a) Routing | The run routes the cut copy to the handler process (right) or not. Denominator: decision points |
| (b) Documents | Of the documents and information the insurer requested in the action (P), the number CasePath names to request now. The number of further documents CasePath requests now that are not in P (**extras**), and the share of CasePath's requests now that are in P. Beside it, descriptive: of the extras, the number the insurer requested at a later decision point. Denominators: the documents in P, summed over decision points; CasePath's requests now |
| (c) Next action | The same action kind of the catalogue A1–A12 as the insurer's, or not. P's "other" counts as not; no action given counts as not. Denominator: decision points |
| (d) Follow-up | Where the file shows the insurer's period (P's `next_in_days`): CasePath's `next_in_days` equal to it, or not (count). Otherwise: the difference in days between CasePath's `next_in_days` and the days from the action to the insurer's next recorded outgoing action, given as a list of signed differences with median and range. At a decision point with no later action and no period shown, (d) is not defined and the point is counted as such. `follow_up` the same as P's or not, where the file shows it, descriptive |
| (e) Deciding facts, descriptive | At each decision point, the deciding facts of the steps the system reached: how many were stated in the file, open, or not addressed (section 4.6); the share of open facts in the real file; and for each state, how the system treated the fact: admitted, presumed, held with a question, or none of these. Counts only; no interval, no prediction |
| Reported as | Counts with exact binomial intervals (section 10), per dossier and pooled over the four. At the three expert decision points, the range over the four variation runs is given beside the frozen run |
| Comparator | The same measures (b)–(e) for the single-prompt comparator, scored mechanically against P with the same catalogue mapping. (a) does not apply: the comparator is given the handler process. The comparator must be given the same handler process as text and the same action and document catalogues (section 4.2); if it is not, the comparison is not reported |
| Not part of Q1 | The process step. It is reported under Q2 through the experts' gestures on the step item, and through O in the first-case counts (section 9.3) |
| Agreement of the two transcriptions | Per measure, the agreement of T1 and T2 before settlement (section 4.3): documents requested (per document), action kind, `next_in_days` where the file shows it, days to the next action, fact states (section 4.6). Counts with denominators; the number of settlements and their direction |
| Development, reported separately | The builders' counts on the seven development dossiers, under the name "development labels, in-sample"; the handler process was written from these dossiers, so their agreement is not a test and not evidence |
| Inference | Four dossiers; descriptive; no test (section 10) |

**Predictions (stated before the freeze).** The builders' counts on the seven development dossiers are in-sample, from
one labeller who also builds the product, and are counts only: routing right 7 of 7; of the documents in the insurer's
first request, 20 of 22 named, with 3 extras; next action right 7 of 7; follow-up date equal in the two later actions
tested (2 of 2). They come mostly from the first request of each dossier; the sealed decision points include later
actions. We predict a lower agreement on the sealed dossiers than in-sample.

**Rule.** For each measure in the table below, the exact (Clopper–Pearson) two-sided 80% interval of the development
proportion is computed at the freeze from the development counts recorded then. It is applied to the sealed
denominator of the measure: the lower count is the lower bound times the denominator, rounded down; the upper count is
the upper bound times the denominator, rounded up. A pooled sealed count at or above the lower count is reported as
"consistent with the development result". A pooled sealed count below the lower count is reported as "below the
development result". A count above the upper count is reported as "above the development result". Per-dossier counts
are shown beside the pooled count but are not compared. There is no prediction for (e) or for the comparator.

| Measure | Development count | Sealed denominator | 80% interval of the development proportion | Count interval on the sealed dossiers |
|---|---|---|---|---|
| (a) Routing right | 7 of 7 | sealed decision points | filled at the freeze | after the cuts |
| (b) Insurer's documents named | 20 of 22 | documents in P over all sealed decision points | filled at the freeze | after the cuts |
| (b) CasePath's requests now that are in P | 20 of 23 (3 extras) | CasePath's requests now over all sealed decision points | filled at the freeze | after the runs |
| (c) Next action same kind | 7 of 7 | sealed decision points | filled at the freeze | after the cuts |
| (d) `next_in_days` equal, where the file shows it | 2 of 2 | sealed decision points where P shows `next_in_days` | filled at the freeze | after the transcriptions |

The number of sealed decision points is known only after the cuts are made, after the freeze. If the development
counts change between this version and the freeze, the counts at the freeze are used, and both are recorded.

### 9.3 Q2 (secondary endpoint): what five experts do with the same items

P here is the settled P record of each study case's expert decision point; P-later is derived from the later decision
points (section 4.3).

| | Definition |
|---|---|
| Primary, agreement | For each chain item of the frozen run: kept or changed by each of the five. Fleiss' kappa and raw agreement, by item kind. The share of items changed by at least three of five (**consensus-changed**). It is only a lower bound on CasePath's errors: errors that fewer than three experts notice, or that all keep under exposure to CasePath's result, are not counted |
| Primary, reliance on document requests | With P as the independent status, per expert: of the documents in P that CasePath lacked, the share the expert added; of CasePath's requests in neither P nor P-later, the share the expert removed; of CasePath's requests in P, the share the expert removed (under-reliance) |
| Test (the only one) | Per expert: (share removed among CasePath's requests in neither P nor P-later) minus (share removed among CasePath's requests in P). One-sided sign test over the five experts; five of five gives p = 1/32, the smallest attainable p. "Not in practice" is not the same as wrong |
| First case | Change after the reveal, as counts over own-answer units (documents and next action): relative AI reliance = units where the own answer disagreed with P, CasePath agreed with P, and the final answer agrees with P / units where the own answer disagreed with P and CasePath agreed; relative self-reliance = units where the own answer agreed with P, CasePath disagreed, and the final answer agrees with P / units where the own answer agreed with P and CasePath disagreed (definitions of Schemmer et al. 2023, with P in place of ground truth). Counts with denominators. Beside it: CasePath's and the comparator's documents and next action against O (moved here from Q1 on 2026-11-12) |
| Step | P does not settle the step (section 4.3). On the first case: CasePath's step the same as the expert's own step (O) or not, and the expert's final step against O and against CasePath's, as counts with denominators. On every case: the final fate of the step item (kept or changed, with the reason) |
| Checking behaviour | Verified-kept, seen-kept, unseen-kept, by item kind and by settled status, at *d* = 2 s (1 and 4 s as sensitivity) |
| Unsettled items | What C and A say, shown beside each; never called right or wrong |
| Not claimed | Appropriate reliance on facts, deadlines or document status: without an independent status it cannot be judged |
| Sensitivity | Without capped cases; without expert-case pairs flagged as prior handling; without items flagged by a leak (section 4.4) |

### 9.4 Q3 (secondary endpoint): work with CasePath, described

Active time per case (idle excluded); interventions per case by kind (corrections, dismissals, additions, notes);
letter change ratio; closing with or without reservation, against agreement with P at the expert decision point.
Own-answer time is reported but is not a baseline. No effort-saving claim and no comparison with unaided handling: the
design has no unaided handling of a whole case.

### 9.5 Q4 (secondary endpoint): learning (model-free replay, leave one case out)

**Proposal rule (mechanical).** From the events of the two training cases, a Knowledge proposal is created for every
addition (document, step or question) that was made with reason 4 ("Gilt generell so") by at least two experts on the
same case, or that was made on both training cases, matched by catalogue id. Its scope is the case's process family and
the node the addition named. Only added documents, steps and questions become proposals (the product cannot turn other
corrections into Knowledge).

**Gate (nested).** A proposal is replayed on the stored runs of the training cases and the seven development dossiers.
It is activated only if it does not lower agreement with P on the training cases (the document measures (b) of 9.2 at
the expert decision point: the number of P's documents named, and the share of CasePath's requests now that are in P)
or the development reference scores (share of reference documents requested; share of requests in the reference). The
gate is a mechanical filter, not a test. Knowledge is never applied to its own origin case. The gate never sees the
held-out case.

**Activation in replay.** Every proposal that passes is activated; no person chooses.

| | Definition |
|---|---|
| Folds | Three: each study case held out once; Knowledge from the other two. The held-out case is held out from the corrections, not from development (section 3.2). Replay runs on the cut copies of the expert decision points |
| Primary | On the held-out case: the change in agreement with P (the document measures (b) of 9.2 at the expert decision point); and the share of consensus additions on the held-out case (additions made by at least three of five experts, by catalogue id) that the replayed Knowledge would have made unnecessary |
| Secondary | Number of proposals made, passed and stopped; leave one expert's events out of the training set, reported as agreement, not as learning; transfer to the development dossiers and to the synthetic claims, as regression checks |
| Scope | Replay changes the process and the checklist only. Knowledge that acts through what the agents read is not measured |
| Counts against the claim | Agreement with P on a held-out case falls; or no proposal passes the gate, in which case "no learning observed" is reported |

### 9.6 Q5 (secondary endpoint): reasons, and other measures

| | Definition |
|---|---|
| Reasons | Distribution of the six reasons and of "ohne Angabe", by item kind |
| Reason agreement | Where two or more experts change the same item: whether they give the same reason (raw agreement, by item kind) |
| Anmerkungen | Counted by where they were left (screen, item kind, closing). Their content is read and grouped inside the insurer by the study owner; the grouping is exported without content. Exploratory |
| Run-to-run variation | For each item key, the share of the five runs (frozen and variation) at the expert decision point with the same value |

### 9.7 Development analysis: leave-one-dossier-out replay (registered; development evidence)

| | Definition |
|---|---|
| Dossiers | The seven development dossiers. Their decision points follow the rule of section 3.1. Their P is a development label: made by the automated labeller, one labeller who also builds the product; no second transcription |
| Folds | Seven. In each, one dossier is held out. Practice Knowledge is rebuilt from the other six by the procedure that built the seed Knowledge (section 3.2); every Knowledge item that came wholly or partly from the held-out dossier is left out. The held-out dossier is scored at each of its decision points |
| Arms | **Law only**: the frozen law-only variant of the handler process (law-derived content only), with no practice Knowledge. **Law plus practice**: the same variant with the practice Knowledge of the six |
| Execution | The product's model-free replay on stored runs, where the builders confirm it applies (section 16). No model call is made for this analysis. A decision point where the replay does not apply is listed and left out of both arms |
| Measures | Those of 9.2 (b)–(d), per arm, per fold and pooled; the difference "law plus practice" minus "law only", as counts |
| What it can show | What the practice Knowledge items add to the law-derived process on a development dossier whose Knowledge items were not used |
| Limit | The handler process itself was written from all seven dossiers and the law. Unless a law-only version of the process exists that was written without the held-out dossier's practice, the held-out dossier is not unseen by the process, and the analysis isolates only what the Knowledge items add. The builders state at the freeze how the law-only variant was written; the statement is in the freeze record. The builders read all seven dossiers in any case |
| If a requirement is missing | Without a frozen law-only variant, both arms use the frozen handler process (without and with the practice Knowledge of the six) and the result is reported as "Knowledge items only". Without Knowledge items attributable to their dossiers, or without a replay that applies, the analysis is not run and is reported as not run |
| Label | "Development evidence (leave-one-dossier-out replay; the process is in-sample)", wherever reported. Never pooled with the sealed dossiers; no test; not used for the predictions of 9.2 |

## 10. Statistics

- **Primary endpoint.** Counts with exact (Clopper–Pearson) two-sided 95% intervals, per dossier and pooled over the four sealed dossiers. Pooled intervals treat decision points as independent. Within a dossier they are not, so the pooled intervals are narrower than warranted, and the per-dossier values are always shown beside them. The prediction rule (section 9.2) uses exact 80% intervals of the development proportions. The day differences of (d) and the counts of (e) are given without intervals. **No hypothesis test is run on the archival endpoint: with four dossiers as clusters, no test has useful power.**
- **Agreement of T1 and T2.** Raw agreement per measure as counts with exact 95% intervals; settlements counted.
- **Secondary endpoint, estimation first.** Every measure is given per case, per expert (unlabelled) and pooled.
- **Secondary endpoint, intervals.** (a) Bootstrap over items within case, cases fixed, 10,000 resamples with a recorded seed, percentile intervals. (b) Over experts: all five values and the leave-one-expert-out range. (c) Leave-one-case-out range.
- **One test**: the per-expert sign test of section 9.3, one-sided; the smallest attainable p (1/32) is given beside the result. It is the document's only pre-stated test.
- **Q4** has three folds; the direction in each fold is reported. No other test is run.
- **Development analysis** (section 9.7). Counts with exact 95% intervals per arm, per fold and pooled; the difference between arms as counts. No test. Labelled development evidence.
- **Exploratory.** Every analysis not listed in sections 9 and 10 is labelled exploratory.

## 11. Exclusions and handling

| Situation | Handling |
|---|---|
| A decision point whose action cannot be transcribed (P cannot be stated from the file) | Listed with the reason and excluded for every system (CasePath and comparator) |
| A decision point whose cut copy cannot be made | Listed with the reason and excluded for every system |
| A run that fails at a decision point | Recorded; counted as not agreeing on (a)–(d) for that system and listed; sensitivity analysis without it |
| T1 and T2 disagree | Settled by the study lead with a logged reason; both versions kept; agreement reported before settlement |
| Leak found in a cut copy after a run | Affected decision points and items flagged and kept; sensitivity analysis without them |
| Comparator not given the same handler process and catalogues | The comparison is not reported |
| Incomplete session | Completed cases are kept; missing cases are reported |
| Technical failure in a session | Recorded as an event; the affected case is kept up to the failure and flagged; sensitivity analysis without it |
| Time-capped case | Kept and flagged; sensitivity analysis without it |
| Unsettled item | Reported as unsettled with C and A beside it; never scored right or wrong |
| Prior handling flag set | Kept; sensitivity analysis without those expert-case pairs |
| Reserve D5 used in the sessions | Only before the first session and for a reason listed in section 3; the replaced case and the reason are reported. All four sealed dossiers stay in the primary endpoint |
| Withdrawal | All records of the expert are removed; the analyses run on the rest; the number is reported |
| Item-list or cut hash mismatch at session start | The session does not start until the copy is restored |

## 12. Privacy

The record measures CasePath. Two exports exist. The **pseudonymous export** holds no case content, only
identifiers, statuses, counts, relative times, day offsets and randomised expert labels; a guard rejects free text. The
**content export** (item texts, notes, the verbatim passages behind P and P-later, the decision points' dates and
actions in words) never leaves the insurer. For the primary endpoint, only counts leave the insurer: no case content
and no quotation from a real file appears in any report. Decision points are given as indexes and day offsets from a
dossier's first document, not as calendar dates. The second transcription (T2) runs inside the insurer. No result is
reported per named person. Per-expert values are shown unlabelled.

## 13. Versioning, timetable and freeze

1. This is version 1.0-rc. It becomes 1.0 at the freeze, when the product's freeze hash and the development counts behind the predictions are recorded; nothing else may change. 2026-11-11: the handler process replaced the process reference (change note); the document stays at 1.0-rc until the freeze. 2026-11-12: the archival comparison became the primary endpoint and the expert sessions the secondary endpoint (change note); because the decision points are found only after the freeze hash, they and the records made after it are added as dated entries (item 4), not deviations. The document stays at 1.0-rc until the freeze.
2. **Timetable.** Day 0 is 2026-11-10. Formative step on day 7; changes from it on days 7–9. Freeze on day 10 (2026-11-20). After the product's freeze hash: the decision points of all four sealed dossiers are found and every cut copy is made and checked; T1 and T2 transcribe P and classify the deciding facts at every decision point; the study lead settles the disagreements; only then are the archival, frozen, variation and comparator runs made; the archival results are computed and the archival hash is recorded (order at the freeze, section 4.3). All of this comes after the freeze hash. It may not fit into day 10, and the number of decision points, which sets the work, is not known in advance. The first session was planned for day 14 (2026-11-24); it moves later if the archival hash does not exist by then. Rule: **no session before the archival hash exists.** Rule against leakage: no person and no session that can change the product reads the pages after a sealed dossier's first decision point before the product's freeze hash exists (section 4.3).
3. **Freeze**, on day 10, as version 1.0. The freeze commit contains exactly:
   - the commit hash of this document's repository at freeze;
   - the product commit and the parity manifest's source-tree hash, with the hashes of the handler process and its action catalogue, and of the law-only variant if it exists, with the builders' statement of how it was written (section 9.7);
   - the development counts behind the predictions, with their denominators, and the 80% intervals computed from them (section 9.2);
   - the content hash of the seed Knowledge rebuilt without D2, D4, D7 and D5 (section 3.2);
   - the development-exposure record (section 3.2), including the statement by the product's builders of which dossiers' later pages any builder had read before the freeze (expected: the seven development dossiers only);
   - the formative-step change list (section 4.5);
   - the SHA-256 of the comparator prompt and of the instructions given to T2;
   - the allocation table after the lot, with the lot seed, and its SHA-256, if the lot is drawn by then (otherwise it is a dated entry before the first session);
   - the bootstrap seed.
4. **Dated entries after the freeze** (not deviations), in the order at the freeze (section 4.3):
   - per sealed dossier and decision point: the index, the action's day offset and the rule's application (section 3.1), the cut verification list and the SHA-256 of the cut copy (section 4.4); per study case, the index of the expert decision point and the routing check of the inclusion criterion;
   - the T1 and T2 records (P and deciding-fact states) per decision point with their SHA-256;
   - the study lead's settlements with their logged reasons, and the SHA-256 of the settled P;
   - the SHA-256 of each archival run's result, of each frozen run's result and item list, of the variation runs and of the comparator runs;
   - the SHA-256 of the automated label set A;
   - the archival results and the archival hash over all of the above.
5. The frozen version is deposited with a timestamp (an internal registry and, if the paper's venue requires, a public registry with the content-free parts). The dated entries are added to the deposit as they are made.
6. Any other change after the freeze is a dated **deviation**, listed in the paper with its reason.

## 14. Choices settled on 2026-11-10

1. Cases: study cases D2, D4, D7; reserve D5 with its rule; seven development dossiers; the three study cases share a process family with each other and with the development dossiers (section 3).
2. Interface-only design: no expert time beyond the sessions; three gestures; no adjudicator, scales or recall (change note, section 7).
3. Status sources P, P-later, O, C, A, kept apart; settled and unsettled items (section 4.3).
4. Session of about 75 minutes; first case rotates (2, 2, 1); proposed caps 25 (own answer ≤ 10), 20 and 20 minutes, to be confirmed by the product session before the freeze (section 6).
5. Formative step on D8 by the process owner on day 7 (section 4.5).
6. Four variation runs per case and the decision-point runs approved; one comparator run per case primary, three only if the budget allows; comparator output in catalogue entries, scored mechanically (section 4.2).
7. Dwell threshold 2 seconds primary; 1 and 4 seconds sensitivity (section 9.1).
8. One pre-stated test: the per-expert sign test on document-request removals (section 9.3).

**Change of 2026-11-11.** The insurer's diagrams describe the intake chat; mould cases route to a handler process with
an action catalogue A1–A12, written by the product's builders from the seven development dossiers and the law
(section 3.3). The process reference R is no longer a status source; the step is settled only by O; Q1 covers
documents and the next action kind, with `next_in_days` and `follow_up` beside it (sections 4.3, 9.2). A rule against
leakage and the order at the freeze were added (sections 4.3, 13). Choice 3 lost R. The document stays at 1.0-rc until
the freeze.

**Change of 2026-11-12.** The primary endpoint is the archival agreement with practice at every decision point of the
four sealed dossiers D2, D4, D5, D7, with no expert time (sections 3.1, 9.2); D5 is a fourth case for it and stays the
reserve for the sessions (choice 1). The expert sessions are the secondary endpoint (Q2–Q5, unchanged). P is
transcribed twice, by the automated labeller and by an independent session, and settled by the study lead (choice 3,
section 4.3). Choice 6 now covers one archival run and one comparator run per decision point, with the four variation
runs and the optional extra comparator runs at the expert decision points only. Predictions from the development
counts, with a stated rule, precede the freeze (section 9.2). No test is run on the archival endpoint; the one
pre-stated test stays in the expert part (choice 8). A leave-one-dossier-out replay on the development dossiers is
registered as development evidence (section 9.7). The document stays at 1.0-rc until the freeze.

## 15. Limits

- **Scope of the primary endpoint.** Four dossiers of one insurer and one process family. Inference is conditional on them.
- **Practice is what was done, not what was right.** The insurer's action is one way of handling the case. The product's seed Knowledge was built from the same insurer's request letters on the development dossiers (the sealed dossiers' letters are excluded), so agreement with practice is partly agreement with what the product learned from that practice.
- **The handler process.** The handler process and its action catalogue were written by the product's builders, not by the insurer's process owner, from the seven development dossiers of one insurer and the law. They may copy habits or errors of those seven files. Agreement with P shows agreement with what the insurer did, not that it was right, and Q1 is not evidence that the process itself is right (section 3.3).
- **In-sample development counts are not evidence.** The counts on the seven development dossiers come from one labeller who also builds the product, on the files the handler process was written from. They are used only to state the predictions (section 9.2). They come mostly from the first request, while the sealed decision points include later actions.
- **One automated labeller plus one independent transcription.** P rests on the builder's automated labeller and one independent transcription, settled by the study lead, who is one of the product's builders. Neither is a claims expert.
- **The number of decision points is not known in advance.** The precision of the primary endpoint is therefore not known in advance. Decision points within a dossier are not independent; the pooled intervals are too narrow, and no test has power (section 10).
- **Development exposure.** The sealed dossiers were among the dossiers the product was developed on (section 3.2).
- **The development analysis is in-sample.** The handler process was written from all seven development dossiers; unless the law-only variant was written without the held-out dossier, the replay isolates only what the Knowledge items add (section 9.7).
- **No independent human adjudication.** Status rests on practice (P, P-later), own answers (O) and consensus (C). Shared blind spots that none of these reveal stay invisible.
- **Correctness of facts, deadlines and document status is not claimed.** No independent source speaks to them; they are reported as unsettled. Measure (e) describes the state of the deciding facts in the file and how the system treated them; it does not judge the treatment.
- **Consensus is formed under exposure** to CasePath's result, so it is not independent of it.
- **The automated labels A** are one non-expert labeller run by the product's builder; they are a separate line, never evidence of correctness.
- **No perception data.** What experts think of CasePath is known only from what they do and what they note.
- **Checks by the study lead.** The cut copies are checked, and the disagreements between the two transcriptions settled, by the study lead, who is an author of this work, one of the product's builders and not a claims expert. The settlement comes before any run on a cut copy of a sealed dossier is made (section 4.3). The verbatim passages stay in the inside export, so a later check by anyone inside the insurer is possible.
- **The gate uses development labels.** On the development dossiers the gate relies on reference scores made by a single labeller who also builds the product.
- **The formative session shaped the product.** The process owner's session on D8 (a development dossier) led to changes before the freeze and may change the handler process before the freeze (section 4.5).
- **Learning.** Only added documents, steps and questions become Knowledge, and replay changes the process and the checklist only (section 9.5).
- **Scope of the secondary endpoint.** Three cases, one insurer, one process, five experts; inference is conditional on them.

## 16. Requirements to the product's builders

Needed before or at the freeze unless said otherwise. Each one not met is reported with the consequence named here.

1. **A frozen law-only variant of the handler process**: law-derived content only, hashed at the freeze, with a statement of how it was written and whether any development dossier's practice was used (section 9.7). Without it, the development analysis compares Knowledge items only.
2. **Practice Knowledge items attributable to their dossiers**: each item names the development dossier(s) it came from, so that a fold can leave out every item that came from the held-out dossier (section 9.7). Without it, the development analysis is not run.
3. **The replay command**: confirmation of where the model-free replay on stored runs applies (which measures, which decision points of the development dossiers), whether stored runs exist on cut copies at those decision points, and its output format: per dossier, decision point and arm, the routing, the documents requested now, the action kind, `next_in_days` and `follow_up`, with the hashes of the process variant and of the Knowledge set used (section 9.7).
4. **Development labels at every decision point** of the seven development dossiers, by the rule of section 3.1, from the automated labeller (section 9.7).
5. **The development counts behind the predictions**, with their denominators, recorded at the freeze (section 9.2).
6. **One run at every decision point's cut copy** of the four sealed dossiers at the frozen commit, after the freeze hash, with the run record of the field list, and a mechanical mapping of the run to measures (a)–(e) of section 9.2: routing to the handler process; document items with `ask = now`; the next-action kind, `next_in_days` and `follow_up`; and fact treatment mapped from the product's fact status to admitted, presumed or held with a question.
7. **The deciding facts of the handler process**: the list of facts that are conditions of each step and document need, derivable from the frozen process file (section 4.6).
8. **The comparator prompt**, fixed before the freeze, with the same handler process as text, the same catalogues, and the deciding-fact treatment of section 4.2.
9. **The statement on later pages read**, for the development-exposure record (section 3.2).
10. **The session caps** confirmed (section 6.1), and whether `next_in_days` and `follow_up` enter the item-list hash.
