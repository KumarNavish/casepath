# Expert feedback: one design for the product and for research

**Principle.** A handler only ever does their work. What they do is recorded so precisely that the same record improves CasePath and answers the research questions. Nothing is asked twice, and nothing is asked that the work itself already shows.

## What we want to know

| | Question | Why the product needs it | Why research needs it |
|---|---|---|---|
| Q1 | How often is what CasePath asserts right? | what to fix next | system accuracy against gold |
| Q2 | Do experts catch what is wrong and leave what is right? | where to put a point in front of the handler | appropriate reliance: over- and under-reliance |
| Q3 | How much work is left for the expert? | the product's promise | effort, with a credible comparison |
| Q4 | Does CasePath get better from corrections, safely? | the Knowledge loop | learning effect and its safety gate |
| Q5 | Why do experts change things? | which kind of fix helps | a taxonomy of human corrections of agent work |

## The unit: one assertion, one fate

Everything CasePath states about a case is an **item** with a stable id: a fact, a party, a deadline, a document's status, a process step, a need, a letter line, the next action. Each item carries what CasePath said, its evidence, whether it was stated as established or put to the handler, and the versions it came from.

Each item ends in exactly one **fate** per handler:

| Fate | How we know |
|---|---|
| verified and kept | the handler opened its source or confirmed it, and left it |
| seen and kept | it was on screen long enough to read; never opened, never changed |
| not seen | it was never on screen |
| corrected | before → after, with a reason |
| dismissed | "nicht nötig", with a reason |

**Silence is not agreement.** Without the middle rows, "accepted" would mix trust with not looking. This distinction is what makes Q2 answerable, and it tells the product which statements nobody checks.

## The reason, in one tap

Six reasons, chosen so each points to a different remedy and they do not overlap:

| Reason shown to the handler | Means | Remedy |
|---|---|---|
| Steht anders in den Akten | CasePath misread the file | reading |
| Steht nicht in den Akten | CasePath asserted without support | checking |
| Hier nicht relevant | right in general, not for this case | process condition |
| Gilt generell so | a rule is missing or wrong | Knowledge proposal |
| Weiss ich von ausserhalb der Akten | the expert has information the file lacks | none: not an error of CasePath |
| Formulierung | wording only | letter templates |

The fifth reason matters most for honest numbers: it separates CasePath's errors from what it could not have known. A note is optional. Skipping the reason is allowed and recorded as "ohne Angabe".

## Closing a case

"Erledigt" has two forms: **erledigt** and **erledigt, mit Vorbehalt**. The second flags the case for a colleague's look (useful at once) and gives a confidence signal per case that can be compared with how right the result was (calibration), with no questionnaire.

## What is recorded besides corrections

- **Exposure:** which items were on screen and for how long, which sources were opened. No mouse trails, no keystrokes.
- **Time:** active time per case, idle time excluded.
- **The letter:** how much of the draft was changed before copying, as a ratio; the text itself stays in the case.
- **Versions:** every run and every event carries the parity manifest (code, workflow, Knowledge versions, model, prompts), so any number can be tied to the exact system that produced it.

## Where truth comes from

The Hackathon cases have gold labels made independently of any handler session. With gold, each item is right or wrong, and each fate is appropriate or not:

| | expert kept it | expert changed it |
|---|---|---|
| CasePath right | appropriate | under-reliance |
| CasePath wrong | **over-reliance** | appropriate |

Experts can be wrong too, so corrections are scored against gold as well, and since all five experts judge the same items, their agreement is reported for every item.

## The study we can actually run: 5 experts × 3 mould dossiers, nothing but the interface

Five Protekta experts, three sealed mould dossiers (D2, D4, D7), each as it stood at one decision point, measured against the mould process the process owner drew. Mobiliar's consent is in place. **There is no adjudicator, no questionnaire and no interview.** Everything an expert contributes, they contribute by working in CasePath.

**The whole feedback instrument is three gestures**
1. **Leave it.** Closing the case ("erledigt" or "erledigt, mit Vorbehalt") attests what was left unchanged.
2. **Change it where it is,** with the reason in one tap.
3. **"Anmerkung"** on any screen or item, and one optional line when closing the case.

**The session (about seventy-five minutes per expert)**
1. Five minutes on a synthetic practice case.
2. **Case 1, own answer first:** from the original files alone, the expert picks the process step, ticks the documents to request and picks the next action (three pick-lists, a few minutes after reading). Then CasePath's result appears and they review it like any case.
3. Cases 2 and 3, with CasePath from the start.
Every expert handles all three cases on one frozen system; which case comes first rotates.

**Where truth comes from, without an adjudicator**

| Source | What it settles | Independent of CasePath? |
|---|---|---|
| The file after the decision point | what Protekta then asked for and did | yes: it is what happened |
| The experts' own answers on their first case | step, documents, next action | yes: given before CasePath is shown |
| The other four experts on the same item | every item; an expert is always compared with the consensus of the others, never with their own vote | partly: they saw CasePath |
| The process owner's process | the path | yes |
| The bridge's labels, made before any session | every item, as a second line | yes, but a single non-expert labeller |

An item's status is reported with the sources that agree on it. Where all experts keep an item that the file or the own answers contradict, that is over-reliance; where the sources cannot settle an item, it is reported as unsettled rather than forced.

**What each part proves**

| Claim | Evidence | Extra expert time |
|---|---|---|
| Accuracy | CasePath's items against what Protekta did, the experts' own answers and consensus | none |
| Appropriate reliance | kept, verified or changed, against the item's status | none |
| Expert agreement | five judgments per item | none |
| Effort and influence | own answer first against CasePath's result on the same case: what the expert had alone, what changed after the reveal, time | a few minutes on one case |
| Learning | Knowledge from the corrections on two cases, replayed model-free on the third; transfer to the development dossiers and the synthetic claims | none |
| Safe learning | each proposal's replayed effect before activation | none |
| Why experts change things | the six reasons and the Anmerkungen | none |

**Rules that protect the result**
- The three study cases and the reserve (D5) are sealed from development and scored only at the freeze.
- One frozen system for all five; the parity manifest is recorded with every session; nothing learned from one expert reaches the next.

**Honest limits, stated in advance**
- Five experts, three cases, one insurer, one process: estimates with intervals, no population claims.
- No independent human adjudication. Truth rests on what Protekta did, the experts' own answers and their consensus; shared blind spots that none of these reveal stay invisible.
- No perception scales: what experts think of CasePath is known only from what they do and what they note.

## Adopted from the paper session's review (binding before the first session)

The paper session reviewed this design against the code (its branch, `research/tmis2026/expert_study/`). These points are adopted; where they differ from the text above, they win.

1. **One stored run per case, the same for all five experts.** Each expert works on their own copy of the case, and every copy points to the frozen run. In a session: no re-check, no model call, Knowledge read-only. A session starts only if the copy's item-list hash equals the frozen run's. Four further runs per case, never shown, give run-to-run variation.
2. **An append-only study event log**, with the fields of `EVENT_FIELDS.md` and a schema field on every record. It includes the time of every undo, the stored difference each correction propagates, the reason, and an "item added" event, so that what CasePath failed to state is counted.
3. **No adjudicators (decided by Navish: no expert time beyond the sessions).** Item status comes from the sources in the table above; the bridge's labels are made before any session.
4. **Learning is leave-one-case-out**, with a gate that sees only the training cases' gold and a mechanical rule from correction to proposal. Leave-one-expert-out is reported as agreement, not as learning. It applies only if the three cases share a process family; otherwise the cross-case claim is dropped.
5. **The unaided answer is structured and frozen at the reveal**, given as three pick-lists, in a view with the original files only (text read from scans is model output and is not shown there). It is always the expert's first study case.
6. **A single-prompt comparator** on the three cases, labelled in the same blind pass; it may run after the sessions.
7. **The parity manifest hashes Knowledge by content fields only**, so use statistics do not change it.
8. **For the outside check on synthetic claims:** each round's commit with its source-tree hash, notice before an API route or result field changes, a research-only setting for deterministic case and file ids, and a model-free `python -m casepath replay` that applies a Knowledge version to stored runs.
9. **Feedback to experts** on which kept items the sources contradict is given to all five together after the last session.

## Guard rails

- Consent from Mobiliar is in place. Each expert still agrees individually, can withdraw, and can have their records removed.
- The record measures CasePath. No individual's numbers are reported; exports carry a pseudonym and no case content. A second export with content, for qualitative reading, never leaves Mobiliar.
- Hypotheses, measures and the analysis plan are written down before the first session.
- Study mode is a setting. Outside it, the product records the same events but assigns nothing and asks nothing.

## What the product does with it, every day

- **Auswertung:** accuracy by item kind, corrections by reason, unchecked statements, time per case, the learning difference.
- **Knowledge proposals** from "Gilt generell so" and from repeated corrections, each with its replay.
- **Fix lists by remedy:** the reason column tells the builders whether to work on reading, checking, process conditions or templates.
