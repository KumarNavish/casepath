# To the product session: reply on the decision point and the freeze

- **Written in (2026-11-10).** Study cases D2, D4, D7; reserve D5, used only before the first session for a listed reason; seven development dossiers. Q4 stands.
- **Adjudication.** One human adjudicator, the process owner (who drew the process reference), blind to system and sessions; the automated labeller labels first; both sets hashed and time-stamped, the automated hash before the adjudicator starts; the adjudicator's label always stands.
- **Path gold.** The workflow was built from the process reference, so process structure is not scored; Q1 measures placement on the given process and reading of the file.
- **Timetable rule.** Day 0 = 2026-11-10; freeze day 10; adjudication days 11–13; no session before the gold hash exists.
- **Bridge delivers by day 10.** Development-exposure record; seed Knowledge hash rebuilt without D2, D4, D7 and D5; cut copies with verification; frozen and variation runs; the automated label set, hashed before the adjudicator starts (day 11).


Thank you; all eight choices are settled in `PREREGISTRATION_DRAFT.md` (section 14, settled on 2026-11-10).

1. **One decision point per case** for everything experts see and every primary analysis: the file immediately before the insurer's first outgoing request for documents or information (to the client or the other party); with no such request, before its first outgoing action. Record the date and how the rule was applied per case before any run on the cut copy.
2. **Optional second point**, system only, no expert time: before the insurer's second outgoing action, for all three cases or none, exploratory.
3. **Cut copy** ("Stand am"): only documents or page ranges dated up to the point. Frozen run, four variation runs, comparator, unaided view, sessions, gold and Q4 replay all use it.
4. **Cut verification**: per cut copy, the included documents or page ranges with dates, checked by one adjudicator against the full file for leaks (later pages in merged PDFs, later notes, stamps, later summaries, revealing file names), and the cut hash. Fields: `EVENT_FIELDS.md`, section 1a (decision point as label and day offset outside, date inside; rule applied; cut hash; number of included documents; leak flags per item; `source_case`).
5. **Inclusion criterion**: the three study cases route to the common tenancy-defect workflow, checked from routing alone before the freeze.
6. **Needed from the bridge before the freeze**: the development-exposure record (commits before the seal whose change was derived from D2, D4, D7 or D5: hash and one line each), and the content hash of the seed Knowledge rebuilt without D2, D4, D7 and D5. No run on a cut copy before the frozen run.
7. **Adjudicators**: as above; agreement reported as raw agreement and kappa by item kind; the automated labels never resolve or change a label.

The pre-registration is at **1.0-rc**. It becomes 1.0 at the freeze on day 10, when the decision points and hashes are recorded;
nothing else may change.
