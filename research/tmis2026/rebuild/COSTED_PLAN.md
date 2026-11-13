# Costed plan for the fixes and Study 4 (gate 1, for Navish, 2026-11-13)

Nothing below has been spent. Costs are model credits in USD from a cost model built on the stored ledgers
(`rebuild/plan/COST_MODEL.md`, `STUDY4_COST.md`; the design is data in `study4_cost.py`). Every figure for files
longer than today's (575 words, four attachments) is an extrapolation; the low figure is the central estimate, the
high one adds 25% and lets output grow with length. Work by writing and checking sessions costs no credits.

## 1. What the figure drafts found, and what it changes

1. **The hold can be taught to a prompt.** On Study 3's sealed tenancy claims the prompt that may hold holds 97 of 100
   requests that depend on an open fact; CasePath's core holds 99.6 on the cost-efficient model and 87 on the frontier
   model. The difference today is on the other side: of 100 requests the file settles, that prompt holds or drops 10,
   the core 4, and the core's needless holds sit on claims that deny their event. The paper's first question is
   answered by all columns of Figure 4, not by one.
2. **"Nothing else moves" is not true yet.** One changed sentence moved exactly one line in 12 of 144 stored theft
   pair-runs of the core; in 130 another line moved too, because readings of other facts differ between runs. The same
   theft text gave the same checklist in all three runs for 8 of 128 texts (tenancy: 70 of 96).
3. **Three readings are not better than one.** In the core, one reading gives 0.55 deviations per tenancy claim, three
   give 0.74: the extra readings add needless holds.
4. **Cost is not in the re-reading.** Reading again only where the first reading does not settle a fact would save 6 to
   7% per file. 62% of the core's cost is the judging of supplied documents, and each of about ten calls carries the
   whole file. On a 2,500-word file the core as tested would cost about 40 times the prompt that may hold.
5. **After a rule edit, the stored readings are enough.** One edited line changed 15 of 421 stored checklist lines
   with no model call, 14 of them exactly as the edited rule requires. Read again without any edit, CasePath's
   checklist lines differ as often as a prompt's (about 6 against 7%): the gain is from not reading again.

## 2. Fixes, on development data only

| # | Fix | Aimed at | Measured on development files by |
|---|---|---|---|
| a | A quoted denial of the defining event counts as a denial | needless holds on denied events (finding 1) | errors on the 24 denied-event files |
| b | One reading; a second and third only where the first is not a quoted true or false | findings 3 and 4 | errors and cost per file against three readings |
| c | The file is the fixed first part of every call, so later calls read it from the cache; supplied documents judged in one call | finding 4 | cost per file by length; target at most three times the prompt that may hold on a long file |
| d | The same text gives the same checklist: fixed sampling where the provider allows it, and a stored reading is reused when the quoted words are still in the file | finding 2 | identical checklists over five runs; lines moved in one-sentence twins |
| e | Quotation matching that tolerates scan noise; the dismissal routing question | first use of the benchmark | holds caused by unmatched quotations; routing failures |
| f | Rule conditions from cited text with a "not this" line | the two over-broad conditions | done: the lint flags 0 of 47 conditions of the public rule sets |

Every baseline gets what it can use: the corrected rules, the hold option, routing as a first step if it helps, the
same budget for self-consistency. The strongest prompt per model is named from development data and frozen.

## 3. The benchmark, extended (no credits)

- **Length:** three levels: about 330 words with zero to four attachments (today's), 800 words with three
  attachments, 2,500 words with six attachments, a fifth of them scanned.
- **Rules:** the same files are read with the rules of one regime, of three regimes and of four regimes in one
  catalogue.
- **Open facts:** share of files with an open fact 0, 10, 25 and 50%.
- **Twins:** for some files a second file one sentence apart.
- **A fourth regime**, added from public text by a session that has not seen the system, following the six steps;
  its hours and sessions are recorded.
- About 930 sealed files are written by a model family that is not evaluated and checked blind, as before.

## 4. Study 4 (one registered test, after a freeze with an external timestamp)

- **Cells:** three regimes × two models × five designs (CasePath's core; the prompt that may hold; self-consistency
  at CasePath's cost; the model executing the rules; ReAct). The main table shows every cell.
- **Files per regime:** 160 for the open-fact sweep (40 per level, short); 40 medium and 40 long at the 25% level;
  the 40 short files of that level read again with the larger catalogues; 30 twins; 20 files run ten times on the
  cost-efficient model and three times on the frontier model. Fourth regime: 120 short files.
- **Measures:** all deviations per file against the clean-room reference (a needless hold is an error); the share of
  files with the same checklist in every run; cost per file.
- **Rule change:** three edits per regime. For every design: lines changed as the edit requires, lines changed that it
  does not reach, model calls. One edit adds a fact, so CasePath's cost for that case is measured too.
- **Hypotheses, per model, frozen in order before the run:** at the hard end of each axis (long files, four regimes,
  half the files open) CasePath makes fewer errors than the strongest prompt; at the easy end it makes no more
  (margin 0.15 per file); after the rule edits it changes more of the right lines, fewer of the wrong ones, with fewer
  calls. A lost cell is reported as lost.

## 5. Cost

| | Cost-efficient model | Frontier model | Total |
|---|---|---|---|
| Development cycle (fixes, priced pilot of long files, three frontier gate rounds) | | | 44 to 61 |
| **A.** Sealed test as in section 4 | 56 to 72 with development | 272 to 353 | 327 to 424 |
| **B.** As A; on the frontier model half the files in every cell | 56 to 72 | 148 to 193 | 203 to 264 |
| **C.** As B; self-consistency and ReAct on the cost-efficient model only | 56 to 72 | 82 to 110 | 138 to 182 |
| A, if fix (c) halves the core's cost | 33 to 42 | 169 to 220 | 202 to 262 |

Totals include the development cycle. The largest items are the core and its cost-matched self-consistency on long
files on the frontier model (38 to 59 each).

## 6. Order, and what the paper can claim at each stop

1. **Development cycle, capped at USD 60.** Ends with a report: each fix's measured effect, the measured cost of long
   files, and which cells are won, tied or lost on development data against the strongest prompt. Claim after this
   stop: none new; the paper stays a mechanism paper with Study 3 and the fair-prompt check.
2. **Benchmark extension and the fourth regime** (no credits), in parallel with 1.
3. **Freeze** (artefact, baselines, plan, order of hypotheses, generator seed), timestamped outside our control, at
   least three days before the run. You choose A, B or C here, with the pilot's prices in hand.
4. **Study 4, once.** Claim after this stop: what comes out, cell by cell.
5. **Cold-reader test of the figures, then the 18 pages.**

## 7. Decisions I need

1. Approve the development cycle (cap USD 60) and the benchmark extension now; choose A, B or C at the freeze.
   My recommendation today is B: every cell is run on both models, and the frontier model carries half the files.
2. The fourth regime. Proposal: air-passenger rights under Regulation (EC) 261/2004 (delay, cancellation, denied
   boarding). Alternative: warranty for defective goods under the Code of Obligations, arts. 197 to 210.
3. Fix (d) changes what the artefact is: it stores readings and reuses them. I think the thesis asks for it ("code
   decides" includes deciding what need not be read again). Say if you see it differently.
4. Product frames for "what the system is" must come from the product session; I will write the request when you
   confirm the five items.
5. One north star I could not read: the OpenAI page refuses automated readers. If you want its structure followed
   closely, paste the text or a PDF of it.
