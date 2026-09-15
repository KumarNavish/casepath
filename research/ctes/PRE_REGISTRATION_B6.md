# B6, the minimal obvious-fix baseline — pre-registration

Written **before** B6 was implemented and before any B6 result existed.

## 1. The objection this exists to settle

> "This is an obvious deterministic rule wrapped in a typed state representation. Why is it a research
> method rather than ordinary engineering?"

The honest test is not prose. It is to build the intervention a competent engineer would actually write
after reading the result, add it to the strongest existing baseline, and see whether the method still has
anything left.

## 2. What B6 is

`full-artifact-gate`. It starts from `full`, the strongest baseline — process-first decomposition plus an
explicit verification step — and keeps **everything** of it: the same model, the same prompt, the same
byte-identical request, its own model-generated document states, its own process decomposition, its own
verifier, its own request planner, its own readiness mechanism.

One deterministic post-process is added, and nothing else:

1. A document may be recorded `received` or `insufficient` **only if that exact document has been
   returned**. Otherwise the plan is crediting a report *about* the document, and the state is reset to
   `missing`, or to `pending` where the plan itself recorded a pending delivery for it.
2. If any such downgrade occurred and the plan had declared readiness, readiness is withdrawn, and where
   that leaves `next_action` inconsistent it becomes a request for up to two of the downgraded documents.

The gate is **per document**, not per run. It never asks "is there an artifact somewhere". It reads only
metadata the baseline already receives in its own actor JSON, so B6 gets no information `full` lacked; it
gets the rule *enforced* instead of *stated*.

B6 deliberately does **not** receive the typed atom extraction, the deterministic state calculus, the
channel ordering, or the delivery-commitment demotion.

## 3. Where it runs, and what that licenses

- **Diagnostic read, decisive split.** The decisive split has been read once already, so adding an arm to
  it is exploratory by construction and is labelled as such. Its purpose is to get the answer fast.
- **Confirmatory read, submission split.** The same comparison is re-run on a fresh, never-read
  generalization split, pre-registered separately, across several actor model families.

No claim of confirmation is made from the diagnostic read.

## 4. The four cases, and what each obliges me to do

Decided now, before the numbers exist.

**Case A — B6 closes essentially the whole gap.** If B6 matches the method within noise on state accuracy,
premature readiness, readiness accuracy, requests and failure rate, then the larger calculus did not earn
the result. I will say so in the paper's own voice, redesign the contribution around whatever genuinely
survives, or report that the contribution reduces to the minimal rule. I will not submit the method as
though the calculus earned it.

**Case B — B6 fixes readiness but not state estimation.** Then there are two separable contributions: the
minimal artifact-required satisfaction rule, and a typed local state construction that improves evidence
state beyond it. I must identify the exact operation responsible for the second and ablate it specifically.

**Case C — B6 stays clearly below the method on both.** The novelty case strengthens. I must still name the
exact operation responsible and show that removing it removes the advantage.

**Case D — B6 beats the method.** I accept it and either simplify the method to B6 plus whatever still
helps, or keep developing. I do not defend the larger method for narrative reasons.

## 5. Quantities and thresholds

Primary: family-paired state accuracy, `ctes − full-artifact-gate`, with a 5000-sample bootstrap 95%
interval, the same statistic used throughout.

- "Closes the gap" means the interval includes zero **and** the point estimate is below +0.05, which is
  a third of the effect the method shows against `full`.
- "Stays clearly below" means the interval excludes zero.
- Anything between is reported as partial and triggers Case B reasoning.

Secondary, reported for every case: premature readiness, missed readiness, readiness accuracy, requests,
unnecessary and repeat requests, critical evidence acquired, and output-failure count.

## 6. What would make this test unfair, and is therefore forbidden

Weakening B6 to protect the method. B6 must keep `full`'s full pipeline; the gate must be per document and
must use only metadata already in the actor; it must be allowed to re-request after a withdrawal rather
than being stranded in an inconsistent plan. If I find myself tempted to restrict B6 after seeing its
result, that is Case A or D arriving, and the answer is to change the paper, not the baseline.
