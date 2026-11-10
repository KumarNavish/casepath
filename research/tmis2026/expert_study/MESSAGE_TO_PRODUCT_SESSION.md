# To the product session: review of the feedback and study design

The study is planned for the TMIS paper; the record is specified to serve a separate paper as well.
Files (paper branch, folder `research/tmis2026/expert_study/`): `REVIEW_OF_FEEDBACK_DESIGN.md`,
`PREREGISTRATION_DRAFT.md`, `EVENT_FIELDS.md`, `SCALES_AND_RECALL_GUIDE.md`, `CONTRIBUTION.md`, `SYNTHETIC_CHECK.md`.

The five changes we ask for, most important first (all must exist before the first session):
1. **One stored run per case, the same for all five experts.** Run once, store it with its result and item-list hashes and the parity manifest; one case copy per expert pointing to it; re-check off (`recheck` defaults to true and calls the model); Knowledge store read-only; no model call in a session. Four extra runs per case, never shown, for variation.
2. **An append-only study event log.** Today feedback is overwritten, undo has no time, the propagation diff is not stored, and feedback has no reason field. Log every exposure interval, source opened, confirm, correction (before, after, reason code), dismissal, addition (`item.added`), undo, unaided answer, reveal, close; field list in `EVENT_FIELDS.md`, with a `schema` field on every record.
3. **Item gold by two adjudicators** before session 1, blind to sessions: correct / incorrect / cannot be decided, plus the reference items each run lacks.
4. **Learning as leave-one-case-out with a nested gate** and a mechanical proposal rule. First tell us: do the three cases share a process family with each other and with the eight development dossiers? Knowledge applies only within its family, so otherwise cross-case learning is zero by construction.
5. **A structured unaided answer**, frozen at the reveal, in a view with original files only (no model-read text, no highlights); the allocation table and time caps are in the pre-registration.
6. (sixth) A single-prompt comparator on the three cases, labelled in the same blind pass; it can be produced after the sessions.

For the synthetic check (`SYNTHETIC_CHECK.md`) we need: each round's commit, reachable, with its source-tree hash;
notice before an API route or result field changes, and a `schema` field on the run result; a research-only setting for
deterministic case and file ids (they enter every model request, so the response cache misses today); and a model-free
`python -m casepath replay` that applies a Knowledge version to stored runs (`agents/core.py` `evaluate` already does the
work). We return after each round: strict unsafe errors, requested share, held required documents, premature and
unnecessary requests, cost and calls, and the claims that got worse, paired and against run-to-run spread.

Please answer the open choices at the end of `PREREGISTRATION_DRAFT.md`; then we freeze it as version 1.0.
