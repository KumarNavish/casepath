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

Experts can be wrong too, so corrections are scored against gold as well, and a second expert independently reviews a fifth of all corrections (agreement reported).

## The study we can actually run: 5 experts × 3 Hackathon cases

Five Protekta experts, three Hackathon cases for which Protekta's explicit process reference exists. Mobiliar's consent is in place. Fifteen expert-case sessions is small, so the design spends them where they prove most, and takes everything else from replay, which costs no expert time.

**Rules that protect the result**
- **The three study cases are sealed.** No fix, rule or Knowledge item may be derived from them, and they are scored only at the freeze. Seed Knowledge is counted without them.
- **One frozen system for all five experts.** Same code, workflows, Knowledge and model; the parity manifest is recorded with every session. Nothing learned from one expert reaches the next during the study.
- **Fully crossed.** Every expert handles all three cases, so every item has five independent expert judgments.

**The session (about two hours per expert)**
1. Ten minutes on a synthetic practice case, so nobody learns the tool on a study case.
2. The three cases, in an order balanced across experts (Latin square).
3. **One of the three is handled unaided first:** the expert works from the dossier alone in the same tool, states the process step, the documents to request and the next action, and only then sees CasePath's result and may revise. Which case is unaided rotates, so each case is unaided for at least one expert and aided for at least three.
4. Two short validated scales (trust, workload) before and after: ten items in all.
5. Twenty minutes of stimulated recall: the expert is shown their own corrections from the record and says why. Recorded inside Mobiliar and linked to event ids.

**What each part proves**

| Claim | Evidence | Expert time |
|---|---|---|
| Accuracy | CasePath's items against the process reference and gold labels, on the three sealed cases and the eight others | none |
| Appropriate reliance | per item: was it right, and did the expert keep, verify or change it; five judgments per item | the sessions |
| Expert agreement | agreement among five experts on the same items; consensus as a second reference beside Protekta's | the sessions |
| Effort | unaided-first against aided, with case and expert as blocks: time, corrections needed, accuracy; and how far the reveal moves an unaided answer | one case per expert |
| Learning | Knowledge built from the experts' corrections, then replayed model-free: leave one expert out (how many of the fifth expert's corrections would the other four have prevented), leave one case out, and transfer to the eight unseen dossiers and the synthetic claims | none |
| Safe learning | each proposal's replayed effect on gold before activation; proposals stopped because they would lower accuracy | none |
| Why experts change things | the six reasons, plus the recall conversations | twenty minutes each |

**Honest limits, stated in advance**
- Five experts and three cases of one insurer support estimates with intervals and item-level tests that respect the clustering (permutation by expert and by case), not population claims. The experts' learning effect on new live cases is not observed; it is estimated by replay.
- Accuracy on the sealed cases is reported next to accuracy on the cases used for development, so any gap is visible.

## Guard rails

- Consent from Mobiliar is in place. Each expert still agrees individually, can withdraw, and can have their records removed.
- The record measures CasePath. No individual's numbers are reported; exports carry a pseudonym and no case content. A second export with content, for qualitative reading, never leaves Mobiliar.
- Hypotheses, measures and the analysis plan are written down before the first session.
- Study mode is a setting. Outside it, the product records the same events but assigns nothing and asks nothing.

## What the product does with it, every day

- **Auswertung:** accuracy by item kind, corrections by reason, unchecked statements, time per case, the learning difference.
- **Knowledge proposals** from "Gilt generell so" and from repeated corrections, each with its replay.
- **Fix lists by remedy:** the reason column tells the builders whether to work on reading, checking, process conditions or templates.
