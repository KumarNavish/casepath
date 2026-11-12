# Clean arm on revision 3 (Study 4, step 2: last paid run)

**DEVELOPMENT material, post hoc, in-sample: the rule wording and the files were repaired on these same files. No baseline is run and no comparison between designs is made. Not a result.** Product at the tested commit (worktree read-only), gpt-6-luna, readings 3, open rule any, checklist scope, reasoning on, one run per file, current rule sets (revision 3), caching transport and ledger under `lint/runs/` (arm label `LINT-clean_rev3-<regime>`, stores `results_clean_rev3_<regime>_gpt-6-luna.json`). Plan, estimate and stop line written before the first call: `REV3_PLAN.json`. Scoring: `analyse.py` part (d), unchanged; attribution: `diagnose.py`'s rule.

rev0 = the stored first clean arm (rules `rev0/`) on the same files. The eight denied-event texts rewritten in repair round 3 were read in their old form by rev0 (listed per regime); references are unchanged for every kept file. UR = requests that should not be made, MR = requests missed, UH = holds where the file settles the fact, MH = holds missed, E = errors per file; RF = routing failures (denied-event / other).

## tenancy: 28 of 59 files run (INCOMPLETE: stopped at the budget line; not a regime figure); stored rev0 run for 28 of them

| Split | Files | E rev3 (rev0) | UR | MR | UH | MH | RF denied | RF other |
|---|---|---|---|---|---|---|---|---|
| overall | 28 | 0.25 (0.393) | 0.143 (0.143) | 0.071 (0.036) | 0.036 (0.214) | 0.0 (0.0) | 2 (2) | 0 (0) |
| level_0 | 6 | 0.0 (0.167) | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.167) | 0.0 (0.0) | 0 (0) | 0 (0) |
| level_10 | 10 | 0.5 (0.3) | 0.2 (0.2) | 0.2 (0.1) | 0.1 (0.0) | 0.0 (0.0) | 0 (0) | 0 (0) |
| level_25 | 6 | 0.167 (0.167) | 0.167 (0.167) | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 1 (1) | 0 (0) |
| level_50 | 6 | 0.167 (1.0) | 0.167 (0.167) | 0.0 (0.0) | 0.0 (0.833) | 0.0 (0.0) | 1 (1) | 0 (0) |
| denied_event | 4 | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 2 (2) | 0 (0) |
| open_fact | 6 | 0.333 (0.333) | 0.167 (0.167) | 0.167 (0.0) | 0.0 (0.167) | 0.0 (0.0) | 0 (0) | 0 (0) |
| other | 18 | 0.278 (0.5) | 0.167 (0.167) | 0.056 (0.056) | 0.056 (0.278) | 0.0 (0.0) | 0 (0) | 0 (0) |

Errors by cause, rev3 (rev0 on the same files):

| Cause | rev3 | rev0 |
|---|---|---|
| document judgment: sufficient judged insufficient | 3 | 2 |
| document judgment: insufficient judged sufficient | 1 | 0 |
| document judgment: not supplied judged present | 1 | 0 |
| fact reading: readings disagreed and it held although the file states the fact | 1 | 6 |
| document judgment: present judged missing (source checker rejected the finding) | 1 | 2 |
| text against recorded state | 0 | 1 |

Routing failures: ten_429b182434cf (denied, rent_increase_dispute -> None, answer None, 0 errors); ten_776e0e61986b (denied, defect_mold_heating -> None, answer None, 0 errors).

## theft: 56 of 56 files run (complete); stored rev0 run for 56 of them

Files named in the repair lists since rev0 (rewritten or re-checked in repair rounds 3 and 4; where a text was rewritten, rev0 read the old text): the_0cd1b047049a, the_1024620d6055, the_1dfba8facf5e, the_2774fb90433e, the_6634ab23ee99, the_685edf55333b, the_7d2b6a2bdce4, the_819379d12c03, the_86b4e22a87e7, the_86e739ec9184, the_9355c558630a, the_a529fff2269d.

| Split | Files | E rev3 (rev0) | UR | MR | UH | MH | RF denied | RF other |
|---|---|---|---|---|---|---|---|---|
| overall | 56 | 0.607 (1.089) | 0.25 (0.304) | 0.0 (0.214) | 0.268 (0.464) | 0.089 (0.107) | 8 (8) | 2 (8) |
| level_0 | 15 | 0.467 (0.867) | 0.133 (0.333) | 0.0 (0.2) | 0.333 (0.333) | 0.0 (0.0) | 2 (2) | 0 (2) |
| level_10 | 14 | 0.5 (1.357) | 0.429 (0.286) | 0.0 (0.429) | 0.071 (0.571) | 0.0 (0.071) | 2 (2) | 0 (3) |
| level_25 | 14 | 0.571 (0.929) | 0.214 (0.143) | 0.0 (0.214) | 0.286 (0.5) | 0.071 (0.071) | 2 (2) | 1 (2) |
| level_50 | 13 | 0.923 (1.231) | 0.231 (0.462) | 0.0 (0.0) | 0.385 (0.462) | 0.308 (0.308) | 2 (2) | 1 (1) |
| denied_event | 8 | 0.0 (3.0) | 0.0 (1.0) | 0.0 (0.0) | 0.0 (2.0) | 0.0 (0.0) | 8 (8) | 0 (0) |
| open_fact | 13 | 0.769 (0.846) | 0.308 (0.154) | 0.0 (0.231) | 0.077 (0.0) | 0.385 (0.462) | 0 (0) | 2 (3) |
| other | 35 | 0.686 (0.743) | 0.286 (0.2) | 0.0 (0.257) | 0.4 (0.286) | 0.0 (0.0) | 0 (0) | 0 (5) |

Errors by cause, rev3 (rev0 on the same files):

| Cause | rev3 | rev0 |
|---|---|---|
| fact reading: readings disagreed and it held although the file states the fact | 10 | 2 |
| document judgment: present judged missing (source checker rejected the finding) | 5 | 1 |
| document judgment: sufficient judged insufficient | 5 | 4 |
| routing, other file | 5 | 18 |
| text against recorded state: readings disagreed and it held although the file states the fact | 5 | 5 |
| document judgment: present judged missing | 4 | 0 |
| routing, denied-event file | 0 | 24 |
| text against recorded state | 0 | 4 |
| fact reading: read an unmentioned fact as open | 0 | 3 |

Routing failures: the_1dfba8facf5e (denied, theft_at_home -> None, answer other, 0 errors); the_32a656cb56cf (not denied, simple_theft_away -> None, answer None, 1 errors); the_5ee356013cfc (denied, simple_theft_away -> None, answer other, 0 errors); the_6634ab23ee99 (denied, theft_at_home -> None, answer other, 0 errors); the_685edf55333b (denied, theft_at_home -> None, answer other, 0 errors); the_86b4e22a87e7 (denied, theft_at_home -> None, answer other, 0 errors); the_86e739ec9184 (denied, simple_theft_away -> None, answer other, 0 errors); the_a529fff2269d (denied, simple_theft_away -> None, answer other, 0 errors); the_c7620535798b (denied, simple_theft_away -> None, answer other, 0 errors); the_d76f5df60f83 (not denied, simple_theft_away -> None, answer None, 4 errors).

## dismissal: 58 of 58 files run (complete); stored rev0 run for 58 of them

Files named in the repair lists since rev0 (rewritten or re-checked in repair rounds 3 and 4; where a text was rewritten, rev0 read the old text): dis_188837a70acc, dis_408b774aa7db, dis_827bbd04ddc9, dis_c5e1bd4a1483, dis_dd12420e6a78, dis_f5520e9336bd, dis_fb44c47f6ec7, dis_ff1e9056d2c3.

| Split | Files | E rev3 (rev0) | UR | MR | UH | MH | RF denied | RF other |
|---|---|---|---|---|---|---|---|---|
| overall | 58 | 0.569 (0.793) | 0.121 (0.172) | 0.121 (0.155) | 0.276 (0.466) | 0.052 (0.0) | 8 (8) | 3 (4) |
| level_0 | 15 | 0.667 (1.6) | 0.133 (0.333) | 0.0 (0.067) | 0.533 (1.2) | 0.0 (0.0) | 2 (2) | 0 (1) |
| level_10 | 14 | 0.286 (0.357) | 0.143 (0.214) | 0.071 (0.071) | 0.071 (0.071) | 0.0 (0.0) | 2 (2) | 0 (0) |
| level_25 | 14 | 1.071 (0.643) | 0.071 (0.071) | 0.357 (0.286) | 0.429 (0.286) | 0.214 (0.0) | 2 (2) | 3 (1) |
| level_50 | 15 | 0.267 (0.533) | 0.133 (0.067) | 0.067 (0.2) | 0.067 (0.267) | 0.0 (0.0) | 2 (2) | 0 (2) |
| denied_event | 8 | 0.0 (0.625) | 0.0 (0.25) | 0.0 (0.0) | 0.0 (0.375) | 0.0 (0.0) | 8 (8) | 0 (0) |
| open_fact | 14 | 0.571 (0.5) | 0.214 (0.214) | 0.0 (0.071) | 0.357 (0.214) | 0.0 (0.0) | 0 (0) | 0 (0) |
| other | 36 | 0.694 (0.944) | 0.111 (0.139) | 0.194 (0.222) | 0.306 (0.583) | 0.083 (0.0) | 0 (0) | 3 (4) |

Errors by cause, rev3 (rev0 on the same files):

| Cause | rev3 | rev0 |
|---|---|---|
| fact reading: readings disagreed and it held although the file states the fact | 14 | 15 |
| routing, other file | 7 | 10 |
| document judgment: sufficient judged insufficient | 4 | 2 |
| document judgment: present judged missing (source checker rejected the finding) | 3 | 5 |
| document judgment: not supplied judged present | 2 | 0 |
| document judgment: insufficient judged sufficient | 1 | 0 |
| fact reading: read an unmentioned fact as open | 1 | 0 |
| fact reading: several facts jointly | 1 | 3 |
| routing, denied-event file | 0 | 5 |
| text against recorded state | 0 | 4 |
| document judgment: present judged missing | 0 | 1 |
| fact reading: read a stated fact as not stated | 0 | 1 |

Routing failures: dis_05af0871cd70 (denied, wrongful_termination -> None, answer None, 0 errors); dis_0f89215979d2 (denied, protected_period_notice -> None, answer None, 0 errors); dis_4ee0866843c9 (denied, protected_period_notice -> None, answer None, 0 errors); dis_5215d587db4b (denied, wrongful_termination -> None, answer None, 0 errors); dis_5adf4d2aec3c (not denied, wrongful_termination -> protected_period_notice, answer protected_period_notice, 1 errors); dis_827bbd04ddc9 (denied, immediate_dismissal -> None, answer None, 0 errors); dis_930a1b5e1bdc (denied, protected_period_notice -> None, answer None, 0 errors); dis_f5520e9336bd (not denied, wrongful_termination -> protected_period_notice, answer protected_period_notice, 3 errors); dis_f8a12a35738c (not denied, wrongful_termination -> None, answer None, 3 errors); dis_fea630e08ab3 (denied, protected_period_notice -> None, answer None, 0 errors); dis_ff1e9056d2c3 (denied, immediate_dismissal -> None, answer None, 0 errors).

## Overall, complete regimes only (theft, dismissal)

114 files: E 0.588 (rev0 0.939); UR 0.184 (0.237), MR 0.061 (0.184), UH 0.272 (0.465), MH 0.07 (0.053); routing failures denied 16 (16), other 5 (12); failed runs 0.

Causes: fact reading: readings disagreed and it held although the file states the fact 24; routing, other file 12; document judgment: sufficient judged insufficient 9; document judgment: present judged missing (source checker rejected the finding) 8; text against recorded state: readings disagreed and it held although the file states the fact 5; document judgment: present judged missing 4; document judgment: not supplied judged present 2; document judgment: insufficient judged sufficient 1; fact reading: read an unmentioned fact as open 1; fact reading: several facts jointly 1.

## The two largest causes, with two quotations each

- **fact reading: readings disagreed and it held although the file states the fact** (24 errors)
  - theft the_12ee892d56f4: vouchers_unobtainable (designed stated_true), a reading answered true: "Quittungen habe ich keine mehr, für gar nichts davon." [verdicts not_stated 2, true 1]
  - theft the_1595e412e131: theft_at_home (designed stated_true), a reading answered true: "jemand ist hereinspaziert." [every reading gave the designed value; 1 quotation(s) not found word for word (the reading altered the words (a capital letter at the start of a quoted part sentence, or other wording))]
- **routing, other file** (12 errors)
  - theft the_32a656cb56cf: routing answer None: "(no quotation)"
  - theft the_d76f5df60f83: routing answer None: "(no quotation)"

## Spend

This run: USD 0.603975 (1307 paid calls; LINT-clean_rev3-dismissal USD 0.287217; LINT-clean_rev3-tenancy USD 0.10731; LINT-clean_rev3-theft USD 0.209448). Step total from the ledgers: USD 3.823342 (before this run USD 3.219367).

## What remains that is the product's behaviour

Product behaviour that remains, by size, in errors per file over the two complete regimes (theft and dismissal, 114 files; tenancy ran 28 of 59 files and is not a regime figure): (1) supplied-document judgments, 24 errors, 0.21 per file: sufficient documents judged insufficient (9), findings the second judgment or the source checker did not confirm (8), present documents judged missing (4), and three the other way; not re-reviewed against the rewritten must_show items, so some may be text against recorded state; (2) stated facts held because one reading's quotation was not found word for word (a capital letter, scan noise corrected), 14 errors, 0.12 per file, most of them on defining events that hold a whole type; (3) stated facts held because one reading of three answered otherwise (household member, vouchers, incapacity, probation, order of notice and protected period), about 12 errors, 0.11 per file, of which the_248aa95805a8's household reading (4) is the open reading also seen in rev0 and 5 more are carried over as text against recorded state; (4) routing, 12 errors, 0.11 per file: 5 in two theft files whose defining event is designed open (benchmark design) and 7 in three dismissal wrongful_termination files routed to protected_period_notice or left unrouted under the revised routing question, which the next design cycle should read before any further wording change. No run failed.

