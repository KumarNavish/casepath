# W9b revision: recorded sources, steps and later case

This package captures `abd3c4897b69062566a3b1c8712366139901cdc9` after planner changes
[6335602195](https://github.com/KumarNavish/casepath/pull/21#issuecomment-6335602195).
The Process source follows the current node's recorded facts or cited completion,
the Answer shows recorded legal-test steps **2, 3, 3, 5, 5**, and Learning opens
with a 900 ms **Later case** rail before its own source and reused checklist.
No legal-test numbers or later-case outcome are invented.

The planner's [final message](https://github.com/KumarNavish/casepath/pull/21#issuecomment-6335641593)
ends planner review. The user directly authorized **Use self-review, then all final
gates**. [Authorization](proof/w9-self-review-authorization-20261022.json) and
[NORTHSTAR](../../docs/product/NORTHSTAR.md) govern this handoff. W8 and W9a remain
approved. The earlier [W9 capture](../w9-20261021/README.md) and its diagnostics
remain historical evidence.

## Film

- [1920×1200 film](casepath-executive-1920x1200.mp4)
- [1920×1080 projector film](casepath-executive-1920x1080.mp4)
- [24-frame contact sheet](contact-sheet.png)
- [Verification](verification.json), [capture](film-receipt.json),
  [frame index](frame-index.jsonl), [repeat](proof/repeat-receipt.json),
  [live comparison](proof/film-live/live-film-receipt.json),
  [encoded timing](proof/encoded-timing.json)

The complete film is **97.65 seconds**, **5,859 frames at 60 fps**.
Every raw frame has clock `n × 1000/60`, Pause visible and no native animation.
A fresh browser independently replayed and screenshotted all 5,859 frames;
all **98** sampled PNG checksums match exactly. Every encoded packet has
presentation timestamp `n/60`. Both delivery films show the complete picture;
only the permitted half-second white fades are applied. The raw frames and
2880×1800 master remain outside Git in the durable sibling film directory.

The live comparison matched **6/6** mid-motion PNGs byte for byte.
Maximum mean absolute RGB difference is 0; maximum channel difference
is 0. The separate full live run observed 5,858
frames with no native animation: p95 16.7 ms,
p99 16.8 ms, maximum 33.4 ms.
These are measurements on this host, not a universal performance claim.

## Self-review evidence

**Fidelity.** [Three concept comparisons](proof/fidelity/REVIEW.md) include frames,
side-by-side views, overlays and difference images. Mean differences are 6.62%
for Process, 6.04% for Completed process and 4.51% for Learning. The review lists
matched features and deliberate differences; no requested correction is pending.
Recorded text, actual six-step linear processes, read-only controls and checklist
reuse replace unsupported illustrative fields, forks and expert-review claims.

**Motion.** The [served proof](proof/presentation/presentation-receipt.json)
passed 18 geometry views, all 5,859 clock states,
Pause/Resume, exact-source inspection and six reduced-motion states. The committed
recorded-trace tests and capture assert each Process frame's source/fact binding.
Source crossfade precedes cursor arrival, which precedes highlighting. Step rings
and the later-case rail have focused rendered assertions. There are **72 focused
passes**; the initial test's incorrect expected step mapping is retained in
[the failed diagnostic](proof/w9b-r2-presentation.tap), alongside the corrected
[test output](proof/w9b-r2-presentation-fixed.tap). No protected test changed.

**Cold viewer.** A fresh model reviewer received only the 24 evenly spaced decoded
film frames and the four questions. The [unaltered answer and assessment](proof/cold-viewer.json)
record all observations and limitations. This is model review, not human acceptance.
It understood the three required points: evidence-linked legal assessment,
source/fact/legal-question/document reasoning with later checklist reuse and a
person deciding, and less repeated searching with inspectable conclusions.
The review did not establish real-case accuracy, speed or live inference.

I viewed all 24 frames in order. My assessment is based only on those images.

- **What does it do?** CasePath helps a case handler assess a customer’s legal issue and prepare a response. The example concerns faulty heating in a rented home. It concludes that the evidence supports repair and rent-reduction eligibility, while leaving the reduction amount and any award unresolved. A person reviews the answer and decides whether to send a draft letter.

- **How does it reach results?** It reads the customer’s account and supporting documents, highlights passages, and works through specific questions: tenancy, landlord knowledge, responsibility and evidence of the defect. It connects findings to legal references and checks whether the necessary documents are present. A later case reuses the earlier checklist while taking its facts from its own documents.

- **Why is it valuable?** I can see the potential to reduce document searching and repeated assessment work. A handler can inspect why a conclusion was reached and what remains unresolved. Reusing a checklist could make similar cases more consistent. The images do not establish actual time savings or accuracy.

- **What was unclear?** I did not see how a case enters the system, where the legal sources come from, or how their correctness is checked. The five named roles could be automated assistants or sections a person operates; the frames do not settle that. “Building” and “Form process decision” describe activity without explaining the judgment being made. The repeated document passages demand substantial reading before the useful conclusion appears. The later-case sequence explains checklist reuse, but does not show that case’s substantive result or how its uncertain date affects the answer. I also did not see the draft letter itself.

My clearest takeaway is an evidence-linked legal case assistant with human review. The demonstration is explicitly fictional; I would still need evidence of performance on real cases before assessing operational readiness.

**Real function.** The final [strict gate and seven-script walk](../w9-20261021/final-gate/verification.json)
must pass on one frozen W8+W9 source, including all eleven frontend suites,
the Mac-owned protected test and all nine cases. This capture package is not a
substitute for those receipts. A missing or failed final receipt is not a pass.
The film asset hashes must match the final source and served build.

The Mac integration owner retains integration and release. No inference,
original-nine run, provider or ledger writes, hosted writes, merge or deployment
are authorized by this evidence. The exact allowance and ledger check remain in
[the canonical UI receipt](../../docs/product/UI_FINISH_RECEIPT_20261021.md).
