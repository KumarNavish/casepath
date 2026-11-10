# To the product session: the pre-registration after the interface-only decision

The pre-registration (`PREREGISTRATION_DRAFT.md`, 1.0-rc) is rewritten to the interface-only design.

**1. Claims that no longer stand, and what replaces each**

| No longer claimed | Replaced by |
|---|---|
| Accuracy of CasePath's items | Agreement with what the insurer did at the decision point (P) and later (P-later) |
| Appropriate reliance on all items | Reliance on document requests against P, P-later; facts, deadlines, status reported as unsettled |
| Expert agreement as a check of truth | Expert agreement and "changed by three of five", a lower bound, formed under exposure |
| Effort and influence (own answer against CasePath) | Work described; first-case change after the reveal as counts against P |
| Learning measured on gold | Learning measured as agreement with P on the held-out case; consensus additions made unnecessary |
| Reasons checked by blind recoding | Reason agreement among experts who change the same item |
| Comparator labelled in the blind pass | Comparator in catalogue entries, scored mechanically against P |
| Cases "sealed from development" | Cases seen in development until the seal; development-exposure record; seed Knowledge without D2, D4, D7, D5 |

**2. Needed, and not yet stated in the product's design**
- P and P-later: transcribed, mapped to catalogue entries and hashed before any run on a cut copy; verbatim passages kept inside; the process owner's check recorded.
- The comparator's output in catalogue entries (step ids, document ids, action kinds).
- Exposure events (`item.exposed`) kept, with the other events of `EVENT_FIELDS.md`, including `note.added` and `case.attested`.
- The prior-handling flag from the file's metadata, per expert and case; never asked.
- The caps confirmed: first case 25 minutes (own answer at most 10), second and third 20 each.
- The allocation table with its seed; the formative-step change list (D8, days 7–9) in the study record.

**3. Timetable rule.** Freeze on day 10; status sources recorded and hashed by day 13; no session before the
status-source hash exists.
