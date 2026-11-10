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

## Comparisons that make the claims credible

1. **Learning, counterfactually (no extra work for anyone).** Evaluation needs no model, so every handled case is re-evaluated under the Knowledge as it was at the start and as it is now. The difference is what learning changed for that very case. This is recorded continuously.
2. **Learning, experimentally.** Two phases. Phase 1: Knowledge frozen at the seed. Then corrections are reviewed, replayed and activated. Phase 2: updated Knowledge. Handlers are in two groups with the case sets swapped between phases, so the phase effect is not a case-set effect. Each case is handled by at least two handlers.
3. **Effort, with a comparison.** On one study case in five, chosen at random, the handler first notes in half a minute which documents they would request and what they would do next, before CasePath's result appears ("erst selbst, dann CasePath"). This gives the expert's unaided answer on the same case, shows how much CasePath changes it, and costs little. It applies to study cases only, never to live work.
4. **The safety gate.** Every Knowledge proposal is replayed on stored cases before activation. We record what the replay predicted, what the reviewer decided and what then happened. Proposals that would have lowered the gold score, and were stopped, are the evidence that the gate works.

## Perception, kept small

Three times (before first use, between the phases, at the end), two short validated scales: trust in the system and workload. Two minutes each. A conversation of twenty minutes with a few handlers at the end. No per-case questions.

## Guard rails

- Taking part is voluntary and consented; a handler can withdraw and have their records removed.
- The record measures CasePath. No individual's numbers are reported; exports carry a pseudonym and no case content. A second export with content, for qualitative reading, never leaves Mobiliar.
- Hypotheses, measures and the analysis plan are written down before the first study session.
- Study mode is a setting. Outside it, the product records the same events but assigns nothing and asks nothing.

## What the product does with it, every day

- **Auswertung:** accuracy by item kind, corrections by reason, unchecked statements, time per case, the learning difference.
- **Knowledge proposals** from "Gilt generell so" and from repeated corrections, each with its replay.
- **Fix lists by remedy:** the reason column tells the builders whether to work on reading, checking, process conditions or templates.
