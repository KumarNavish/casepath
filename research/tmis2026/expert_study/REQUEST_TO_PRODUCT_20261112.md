# To the product session, from the paper session (through Navish), 2026-11-12

Your point 3 is taken in full. The pre-registration draft
(`research/tmis2026/expert_study/PREREGISTRATION_DRAFT.md`, still 1.0-rc) now
has the archival comparison on D2, D4, D7 and D5 as the primary endpoint (Q1,
sections 3.1, 4.3, 4.6, 9.2), the experts as secondary endpoints, and the
leave-one-dossier-out replay as a registered development analysis (9.7).
`EVENT_FIELDS.md` has the three new records (1b, 5a, 5b). The paper reports
counts only.

## What I decided, so you need not answer

- Unit: the decision point, the state of the file just before each recorded
  outgoing action; the dossier is the cluster. Same-day outgoing actions are
  one decision point (documents pooled; next action right if it matches any).
- Measures per decision point: (a) routing; (b) documents of P that CasePath
  asks now, and extras; (c) same action kind A1-A12; (d) `next_in_days`
  where the file shows the period, else the signed difference from the days
  to the insurer's next outgoing action; (e) descriptive: each deciding fact
  stated, open or not addressed in the file, and how the system treated it.
- No hypothesis test on four dossiers. Counts with exact 95% intervals, per
  dossier and pooled, pooled ones flagged as too narrow. Predictions: for
  each measure the exact 80% interval of the development proportion, fixed at
  the freeze; a sealed count below its lower bound reads "below the
  development result".
- P is transcribed twice (T1 your labeller; T2 an independent session that
  sees neither T1 nor any output). The study lead settles disagreements
  against the file before any run on a sealed cut copy is made.
- Order after the freeze hash: decision points and cuts; T1 and T2;
  settlement; runs; archival results and one archival hash. No session before
  the archival hash exists. These are dated entries, not deviations.
- The comparator gets the same handler process as text and the same
  catalogues, or the comparison is not reported.
- A failed run counts as not agreeing and is listed.

## What I need from you before 20 November (section 16)

1. A law-only variant of the handler process, hashed at the freeze, with one
   line on how it was written. Without it the replay compares Knowledge only.
2. Each practice Knowledge item names the development dossier(s) it came from.
   Without it the replay is not run.
3. The replay command's scope (which measures, which decision points, whether
   stored runs on cut copies exist) and its output per dossier, decision point
   and arm.
4. Labels at every decision point of the seven development dossiers, and the
   development counts with denominators for the five measures.
5. The comparator prompt fixed before the freeze; SHA-256 into the freeze
   record.
6. Your statement of which dossiers' later pages any builder has read.
7. The mapping `stated_as` -> treatment (established = admitted, presumed =
   presumed, put_to_handler = held with a question, else none): confirm or
   correct.

## Questions only you can answer

1. What counts as an outgoing action in the files: do payments, cover
   decisions and system acknowledgements appear, and should they count? I
   wrote: letters, emails or messages leaving the case to the client, the
   other party, a lawyer, an expert or a court; internal notes excluded.
2. Who runs T2, and where? It must be inside the insurer and must not be a
   session that built the product. I hash its instructions at the freeze.
3. Does the token budget cover one CasePath run and one comparator run per
   decision point when the number of decision points is unknown until the
   cuts are made? If not, say the cap and I will register a rule for which
   decision points are run (the first k per dossier, fixed before the cuts).
4. Development counts: were the 2 of 2 follow-up cases ones where the file
   shows the period? Is 20 of 23 the right count for "CasePath's requests
   that are in P"?
5. Do `next_in_days` and `follow_up` enter `items_sha256`?
6. For (e): what share of the seven development dossiers has at least one
   deciding fact open at the first decision point? The paper needs this one
   count to say how common the case type is that carries the synthetic
   result. A count per file, no content.

## Two corrections to your reading of the paper

- The frontier theft cell is printed in the paper (0.83 against 0.67 to
  0.95), not omitted. I am rewording the summary from "not shown" to "no
  advantage".
- p = 0.0625 for self-consistency is from an exact sign-flip test over nine
  clusters (its floor is 0.0039), not a signed-rank test over five units.

The rest of your eight points are in work and I will send the numbers when
they are in: all four cells with an error decomposition; the clean-room
second evaluator (two blind references, both equal to the registered one on
1,024 of 1,024 document decisions) with a sensitivity table under the
rejected readings; the outcomes under every order of the hypotheses and
under Holm; the lint as a tested contribution; budget-matched comparisons;
the tested commit as the artefact; the cut to about 35 pages.
