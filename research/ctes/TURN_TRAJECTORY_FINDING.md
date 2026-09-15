# The headline metric hides a decline, and one actor could not run at all

Found during the submission-closure pass. **This file replaces an earlier version of itself that overstated
the finding against the method.** That version said a plain direct planner finishes ahead on four of five
runs. Recomputed on valid records only, it finishes ahead on two of five. The correction is recorded here
rather than made silently, because an error against the method is still an error.

## The decline is real

State accuracy is averaged over the three turns of an episode. Per turn, on **every** run, the method
starts far ahead and declines, while the baselines hold or rise. Failed turns are excluded throughout;
counts and failures are shown as `value(n)-Kf`.

| run | arm | turn 0 | turn 1 | turn 2 |
|---|---|---|---|---|
| decisive, `gpt-5.4-mini` | method | 0.864 | 0.803 | **0.745** |
| | direct end-to-end | 0.633 | 0.667 | **0.752** |
| decisive, rewritten by a second model | method | 0.861 | 0.806 | **0.697** |
| | direct end-to-end | 0.619 | 0.660 | **0.741** |
| submission, `gpt-5.4-mini` | method | 0.824 | 0.819 | 0.719 |
| | direct end-to-end | 0.693 | 0.645 | 0.702 |
| submission, `gpt-5.6-terra` | method | 0.893 | 0.826 | 0.698 |
| | obvious-fix baseline | 0.810 | 0.776 | **0.736** |
| | direct end-to-end | 0.726 | 0.712 | 0.690 |

**What is established.** The method's advantage is concentrated at the start of an episode and erodes as
documents arrive. Its turn-0 lead of 0.15 to 0.23 over the baselines falls to between −0.04 and +0.03 by
the turn on which the agent actually decides.

**What is established more narrowly than the earlier version claimed.** A baseline finishes ahead of the
method at the final turn on **two** of the five runs — direct end-to-end on both decisive-split runs — and
the obvious-fix baseline finishes ahead on the strong actor. On the two `gpt-5.4-mini` runs the method is
still ahead at the final turn.

**Why it still matters.** Turn 2 is when the decision is taken. A metric averaged over turns rewards being
right early, which is the regime where deterministic construction helps most and the baselines have least
information. The pre-registration fixed the averaged metric before any of this was visible; that was in
good faith and is documented, but it is not the quantity a reader will care about, and the paper cannot
lead with it without also showing this table.

## The third actor did not execute the protocol

`anthropic/claude-sonnet-5` could not complete the frozen protocol at its 8000-token budget. It truncated
or returned empty completions throughout, and the damage is heavily asymmetric because it falls on whichever
arm emits the longest output:

| arm | failed turn-records, of 180 | at turn 2, of 60 |
|---|---|---|
| method | 71 | **41** |
| obvious-fix baseline | 50 | 23 |
| strongest baseline | 50 | 23 |
| direct end-to-end | **9** | 4 |

A failed turn scores zero state accuracy, so the method's apparent final-turn collapse to 0.276 on this
actor is an artifact of 41 of 60 episodes failing, not a property of the method. **On its surviving
records the method is the most accurate arm on this actor at every turn** (0.878 / 0.865 / 0.872 against
direct end-to-end's 0.722 / 0.802 / 0.857).

**This run is therefore void as a comparison and is excluded from the generalization hypotheses.** It is
reported as what it is: evidence that the protocol needs a larger token budget for a reasoning-heavy model,
and that the method is the most sensitive arm to that budget because it emits the most structure. Both of
those are real limitations. Neither is a measured difference in accuracy.

## Where that leaves generalization

Of three pre-registered actor models, two produced valid reads:

| actor | method vs obvious fix, state accuracy | verdict |
|---|---|---|
| `openai/gpt-5.4-mini` | +0.094 [+0.039, +0.150], 21/8, p = 0.0008 | established |
| `openai/gpt-5.6-terra` | +0.032 [−0.006, +0.068], 19/11, p = 0.103 | not established |
| `anthropic/claude-sonnet-5` | void — 14% of records failed, asymmetrically | no read |

The honest statement is that the advantage over the obvious fix is established on the economical actor,
not established on the strong one, and unmeasured on the third. The pre-registration required an interval
excluding zero on at least two of three; that is not met, and the contribution is **model-specific on the
evidence available**. Re-running the third actor at a larger budget, for all arms equally, would give it a
real read and is the one experiment that could still change this.
