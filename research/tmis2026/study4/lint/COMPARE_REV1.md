# Part C: the clean arm with the revised rule wording (Study 4, step 2d follow-up)

**DEVELOPMENT material, post hoc, in-sample: the wording fixes were designed on these same files, so the change measures how well the fixes fit the files they were made from, not how they generalise. Not a result.** Cost-efficient model gpt-6-luna, one run per file (run index 0), product at the tested commit, caching transport and ledger under `lint/runs/` (arm label `LINT-clean_rev1-<regime>`). Before = the stored clean arm (rules in `rules/<regime>/rev0/`); after = `results_clean_rev1_<regime>_gpt-6-luna.json` (rules as revised). Both on the same files: those the re-run stored (selection and order fixed in `REV1_PLAN.json` before the first rev1 call). Scoring is `lint/analyse.py` part (d), unchanged.

UR = requests that should not be made, MR = requests missed, UH = holds where the file settles the fact, MH = holds missed, E = errors per file; RF = routing failures, denied-event / other.

| Regime | Split | Files | E before | E after | UR b/a | MR b/a | UH b/a | MH b/a | RF denied b/a | RF other b/a | No error b/a |
|---|---|---|---|---|---|---|---|---|---|---|---|
| tenancy | all re-run | 31 | 0.677 | 0.419 | 0.29 / 0.323 | 0.161 / 0.0 | 0.226 / 0.097 | 0.0 / 0.0 | 3 / 4 | 3 / 0 | 17 / 21 |
| tenancy | level_0 | 8 | 0.375 | 0.125 | 0.125 / 0.125 | 0.125 / 0.0 | 0.125 / 0.0 | 0.0 / 0.0 | 1 / 1 | 1 / 0 | 5 / 7 |
| tenancy | level_10 | 6 | 0.667 | 0.667 | 0.5 / 0.5 | 0.167 / 0.0 | 0.0 / 0.167 | 0.0 / 0.0 | 0 / 1 | 0 / 0 | 3 / 3 |
| tenancy | level_25 | 7 | 0.286 | 0.571 | 0.286 / 0.286 | 0.0 / 0.0 | 0.0 / 0.286 | 0.0 / 0.0 | 1 / 1 | 0 / 0 | 5 / 5 |
| tenancy | level_50 | 10 | 1.2 | 0.4 | 0.3 / 0.4 | 0.3 / 0.0 | 0.6 / 0.0 | 0.0 / 0.0 | 1 / 1 | 2 / 0 | 4 / 6 |
| tenancy | denied_event | 8 | 0.0 | 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 3 / 4 | 0 / 0 | 8 / 8 |
| tenancy | not denied | 23 | 0.913 | 0.565 | 0.391 / 0.435 | 0.217 / 0.0 | 0.304 / 0.13 | 0.0 / 0.0 | 0 / 0 | 3 / 0 | 9 / 13 |
| tenancy | group P1 | 3 | 1.333 | 0.333 | 0.0 / 0.333 | 1.333 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0 / 0 | 3 / 0 | 1 / 2 |
| tenancy | group P2 | 8 | 0.0 | 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 3 / 4 | 0 / 0 | 8 / 8 |
| tenancy | group P3 | 6 | 0.667 | 0.167 | 0.167 / 0.167 | 0.167 / 0.0 | 0.333 / 0.0 | 0.0 / 0.0 | 0 / 0 | 0 / 0 | 3 / 5 |
| tenancy | group P4 | 5 | 0.0 | 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0 / 0 | 0 / 0 | 5 / 5 |
| tenancy | group P5 | 9 | 1.444 | 1.222 | 0.889 / 0.889 | 0.0 / 0.0 | 0.556 / 0.333 | 0.0 / 0.0 | 0 / 0 | 0 / 0 | 0 / 1 |
| theft | all re-run | 42 | 1.524 | 1.238 | 0.333 / 0.476 | 0.429 / 0.0 | 0.619 / 0.643 | 0.143 / 0.119 | 8 / 8 | 11 / 2 | 17 / 18 |
| theft | level_0 | 12 | 1.083 | 1.25 | 0.417 / 0.5 | 0.25 / 0.0 | 0.417 / 0.75 | 0.0 / 0.0 | 2 / 2 | 2 / 0 | 7 / 6 |
| theft | level_10 | 10 | 1.8 | 1.3 | 0.2 / 0.4 | 0.7 / 0.0 | 0.8 / 0.9 | 0.1 / 0.0 | 2 / 2 | 4 / 0 | 3 / 3 |
| theft | level_25 | 9 | 1.778 | 0.889 | 0.111 / 0.333 | 0.778 / 0.0 | 0.778 / 0.444 | 0.111 / 0.111 | 2 / 2 | 3 / 1 | 3 / 4 |
| theft | level_50 | 11 | 1.545 | 1.455 | 0.545 / 0.636 | 0.091 / 0.0 | 0.545 / 0.455 | 0.364 / 0.364 | 2 / 2 | 2 / 1 | 4 / 5 |
| theft | denied_event | 8 | 3.0 | 3.0 | 1.0 / 1.0 | 0.0 / 0.0 | 2.0 / 2.0 | 0.0 / 0.0 | 8 / 8 | 0 / 0 | 2 / 2 |
| theft | not denied | 34 | 1.176 | 0.824 | 0.176 / 0.353 | 0.529 / 0.0 | 0.294 / 0.324 | 0.176 / 0.147 | 0 / 0 | 11 / 2 | 15 / 16 |
| theft | group P1 | 9 | 2.111 | 1.111 | 0.0 / 0.444 | 2.0 / 0.0 | 0.0 / 0.667 | 0.111 / 0.0 | 0 / 0 | 9 / 0 | 2 / 2 |
| theft | group P2 | 8 | 3.0 | 3.0 | 1.0 / 1.0 | 0.0 / 0.0 | 2.0 / 2.0 | 0.0 / 0.0 | 8 / 8 | 0 / 0 | 2 / 2 |
| theft | group P3 | 15 | 1.067 | 1.0 | 0.2 / 0.333 | 0.0 / 0.0 | 0.533 / 0.333 | 0.333 / 0.333 | 0 / 0 | 2 / 2 | 8 / 7 |
| theft | group P4 | 5 | 0.0 | 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0 / 0 | 0 / 0 | 5 / 5 |
| theft | group P5 | 5 | 1.0 | 0.6 | 0.6 / 0.6 | 0.0 / 0.0 | 0.4 / 0.0 | 0.0 / 0.0 | 0 / 0 | 0 / 0 | 0 / 2 |
| dismissal | all re-run | 22 | 0.909 | 0.227 | 0.136 / 0.045 | 0.182 / 0.045 | 0.591 / 0.136 | 0.0 / 0.0 | 8 / 8 | 4 / 0 | 15 / 20 |
| dismissal | level_0 | 7 | 1.714 | 0.571 | 0.429 / 0.143 | 0.0 / 0.0 | 1.286 / 0.429 | 0.0 / 0.0 | 2 / 2 | 1 / 0 | 4 / 6 |
| dismissal | level_10 | 3 | 0.0 | 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 2 / 2 | 0 / 0 | 3 / 3 |
| dismissal | level_25 | 3 | 0.667 | 0.0 | 0.0 / 0.0 | 0.667 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 2 / 2 | 1 / 0 | 2 / 3 |
| dismissal | level_50 | 9 | 0.667 | 0.111 | 0.0 / 0.0 | 0.222 / 0.111 | 0.444 / 0.0 | 0.0 / 0.0 | 2 / 2 | 2 / 0 | 6 / 8 |
| dismissal | denied_event | 8 | 0.625 | 0.0 | 0.25 / 0.0 | 0.0 / 0.0 | 0.375 / 0.0 | 0.0 / 0.0 | 8 / 8 | 0 / 0 | 7 / 8 |
| dismissal | not denied | 14 | 1.071 | 0.357 | 0.071 / 0.071 | 0.286 / 0.071 | 0.714 / 0.214 | 0.0 / 0.0 | 0 / 0 | 4 / 0 | 8 / 12 |
| dismissal | group P1 | 4 | 2.5 | 0.25 | 0.0 / 0.0 | 1.0 / 0.25 | 1.5 / 0.0 | 0.0 / 0.0 | 0 / 0 | 4 / 0 | 0 / 3 |
| dismissal | group P2 | 8 | 0.625 | 0.0 | 0.25 / 0.0 | 0.0 / 0.0 | 0.375 / 0.0 | 0.0 / 0.0 | 8 / 8 | 0 / 0 | 7 / 8 |
| dismissal | group P3 | 5 | 1.0 | 0.8 | 0.2 / 0.2 | 0.0 / 0.0 | 0.8 / 0.6 | 0.0 / 0.0 | 0 / 0 | 0 / 0 | 3 / 4 |
| dismissal | group P4 | 5 | 0.0 | 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0 / 0 | 0 / 0 | 5 / 5 |
| all | all re-run | 95 | 1.105 | 0.737 | 0.274 / 0.326 | 0.284 / 0.011 | 0.484 / 0.347 | 0.063 / 0.053 | 19 / 20 | 18 / 2 | 49 / 59 |

## Files whose score or routing changed

- tenancy ten_00bf58d82a2b (P3, not denied, level 0, type lease_termination_dispute): before routed lease_termination_dispute, 1 errors {'UH': 1}; after routed lease_termination_dispute, 0 errors {}.
- tenancy ten_0c74f4037e13 (P3, not denied, level 50, type lease_termination_dispute): before routed lease_termination_dispute, 1 errors {'UH': 1}; after routed lease_termination_dispute, 0 errors {}.
- tenancy ten_270f84d8acff (P5, not denied, level 50, type defect_mold_heating): before routed defect_mold_heating, 4 errors {'UH': 4}; after routed defect_mold_heating, 0 errors {}.
- tenancy ten_5822f6df0cb7 (P3, not denied, level 10, type lease_termination_dispute): before routed lease_termination_dispute, 2 errors {'UR': 1, 'MR': 1}; after routed lease_termination_dispute, 1 errors {'UR': 1}: claims_and_reasons unneeded_request.
- tenancy ten_5aecbb73131b (P5, not denied, level 10, type rent_increase_dispute): before routed rent_increase_dispute, 1 errors {'UR': 1}; after routed rent_increase_dispute, 2 errors {'UR': 1, 'UH': 1}: cost_breakdown unwarranted_hold; lease_contract unneeded_request.
- tenancy ten_8572ddc89110 (P2, denied, level 10, type rent_increase_dispute): before routed rent_increase_dispute, 0 errors {}; after routed None, 0 errors {}.
- tenancy ten_a743587360f3 (P5, not denied, level 50, type rent_increase_dispute): before routed rent_increase_dispute, 2 errors {'UR': 1, 'UH': 1}; after routed rent_increase_dispute, 1 errors {'UR': 1}: lease_contract unneeded_request.
- tenancy ten_b4d4cb05336f (P1, not denied, level 50, type rent_increase_dispute): before routed lease_termination_dispute, 0 errors {}; after routed rent_increase_dispute, 1 errors {'UR': 1}: rent_increase_notice unneeded_request.
- tenancy ten_c2a72cbf1698 (P1, not denied, level 50, type defect_mold_heating): before routed None, 3 errors {'MR': 3}; after routed defect_mold_heating, 0 errors {}.
- tenancy ten_e4858b3af131 (P1, not denied, level 0, type rent_increase_dispute): before routed lease_termination_dispute, 1 errors {'MR': 1}; after routed rent_increase_dispute, 0 errors {}.
- tenancy ten_eec676341229 (P5, not denied, level 25, type lease_termination_dispute): before routed lease_termination_dispute, 1 errors {'UR': 1}; after routed lease_termination_dispute, 3 errors {'UR': 1, 'UH': 2}: hardship_evidence unwarranted_hold; payment_demand unwarranted_hold; termination_notice unneeded_request.
- theft the_0cd1b047049a (P1, not denied, level 10, type simple_theft_away): before routed None, 0 errors {}; after routed simple_theft_away, 1 errors {'UR': 1}: insurance_policy unneeded_request.
- theft the_12ee892d56f4 (P1, not denied, level 10, type simple_theft_away): before routed None, 4 errors {'MR': 3, 'MH': 1}; after routed simple_theft_away, 1 errors {'UH': 1}: original_vouchers unwarranted_hold.
- theft the_2412f755f636 (P5, not denied, level 0, type theft_at_home): before routed theft_at_home, 1 errors {'UH': 1}; after routed theft_at_home, 0 errors {}.
- theft the_248aa95805a8 (P1, not denied, level 0, type theft_at_home): before routed None, 0 errors {}; after routed theft_at_home, 4 errors {'UH': 4}: insurance_policy unwarranted_hold; notification_record unwarranted_hold; police_consent unwarranted_hold; stolen_items_list unwarranted_hold.
- theft the_506c9909edc4 (P3, not denied, level 25, type theft_at_home): before routed theft_at_home, 3 errors {'UH': 3}; after routed theft_at_home, 1 errors {'UR': 1}: stolen_items_list unneeded_request.
- theft the_7d2b6a2bdce4 (P5, not denied, level 50, type simple_theft_away): before routed simple_theft_away, 1 errors {'UH': 1}; after routed simple_theft_away, 0 errors {}.
- theft the_819379d12c03 (P1, not denied, level 25, type simple_theft_away): before routed None, 3 errors {'MR': 3}; after routed simple_theft_away, 1 errors {'UR': 1}: notification_record unneeded_request.
- theft the_9355c558630a (P1, not denied, level 0, type simple_theft_away): before routed None, 3 errors {'MR': 3}; after routed simple_theft_away, 1 errors {'UH': 1}: original_vouchers unwarranted_hold.
- theft the_c50e0bd7b054 (P1, not denied, level 50, type simple_theft_away): before routed None, 1 errors {'MR': 1}; after routed simple_theft_away, 1 errors {'UR': 1}: original_vouchers unneeded_request.
- theft the_d37fc3c54b4b (P1, not denied, level 10, type simple_theft_away): before routed None, 3 errors {'MR': 3}; after routed simple_theft_away, 1 errors {'UR': 1}: original_vouchers unneeded_request.
- theft the_d9579f891719 (P1, not denied, level 25, type simple_theft_away): before routed None, 4 errors {'MR': 4}; after routed simple_theft_away, 0 errors {}.
- theft the_dd72ec4e53dd (P1, not denied, level 10, type simple_theft_away): before routed None, 1 errors {'MR': 1}; after routed simple_theft_away, 0 errors {}.
- theft the_fefc066e8269 (P3, not denied, level 0, type simple_theft_away): before routed simple_theft_away, 0 errors {}; after routed simple_theft_away, 1 errors {'UR': 1}: notification_record unneeded_request.
- dismissal dis_14b7db92a192 (P1, not denied, level 25, type protected_period_notice): before routed None, 2 errors {'MR': 2}; after routed protected_period_notice, 0 errors {}.
- dismissal dis_1bf62841defb (P1, not denied, level 50, type protected_period_notice): before routed None, 1 errors {'MR': 1}; after routed protected_period_notice, 1 errors {'MR': 1}: termination_letter missed_request.
- dismissal dis_bf38c7dfb616 (P1, not denied, level 50, type protected_period_notice): before routed wrongful_termination, 4 errors {'MR': 1, 'UH': 3}; after routed protected_period_notice, 0 errors {}.
- dismissal dis_c50430dbdfa1 (P1, not denied, level 0, type protected_period_notice): before routed wrongful_termination, 3 errors {'UH': 3}; after routed protected_period_notice, 0 errors {}.
- dismissal dis_fb44c47f6ec7 (P3, not denied, level 50, type wrongful_termination): before routed wrongful_termination, 1 errors {'UH': 1}; after routed wrongful_termination, 0 errors {}.
- dismissal dis_ff1e9056d2c3 (P2, denied, level 0, type immediate_dismissal): before routed wrongful_termination, 5 errors {'UR': 2, 'UH': 3}; after routed None, 0 errors {}.

## The changed facts: product state by designed state, on the re-run files

- tenancy lease_termination_dispute.asserted_claims: before {'not_mentioned -> established False': 1, 'not_mentioned -> not read': 1, 'not_mentioned -> presumed False': 1, 'stated_false -> established False': 2, 'stated_true -> established true': 4, 'stated_true -> unknown None': 2}; after {'not_mentioned -> established False': 1, 'not_mentioned -> not read': 1, 'not_mentioned -> presumed False': 1, 'stated_false -> established False': 2, 'stated_true -> established true': 6}
- theft theft_at_home.household_perpetrator: before {'not_mentioned -> not read': 3, 'not_mentioned -> presumed False': 5, 'not_mentioned -> unknown None': 1, 'stated_false -> established False': 5, 'stated_false -> not read': 1, 'stated_true -> established true': 3, 'stated_true -> not read': 1, 'stated_true -> unknown None': 1}; after {'not_mentioned -> not read': 3, 'not_mentioned -> presumed False': 6, 'stated_false -> established False': 5, 'stated_false -> not read': 1, 'stated_true -> established true': 3, 'stated_true -> unknown None': 2}
- theft theft_at_home.measures_pending: before {'not_mentioned -> not read': 4, 'not_mentioned -> presumed False': 5, 'not_mentioned -> unknown None': 1, 'stated_false -> established False': 5, 'stated_false -> not read': 1, 'stated_true -> established true': 1, 'stated_true -> unknown None': 3}; after {'not_mentioned -> not read': 4, 'not_mentioned -> presumed False': 5, 'not_mentioned -> unknown None': 1, 'stated_false -> established False': 6, 'stated_true -> established true': 4}
- theft simple_theft_away.measures_pending: before {'not_mentioned -> not read': 8, 'not_mentioned -> presumed False': 2, 'stated_false -> established False': 1, 'stated_false -> not read': 1, 'stated_true -> established true': 2, 'stated_true -> not read': 5, 'stated_true -> presumed False': 3}; after {'not_mentioned -> not read': 3, 'not_mentioned -> presumed False': 7, 'stated_false -> established False': 1, 'stated_false -> not read': 1, 'stated_true -> established true': 8, 'stated_true -> not read': 2}
- dismissal wrongful_termination.retaliation_for_claims: before {'not_mentioned -> not read': 1, 'stated_false -> not read': 1, 'stated_true -> established true': 2, 'stated_true -> unknown None': 3}; after {'not_mentioned -> not read': 1, 'stated_false -> not read': 1, 'stated_true -> established true': 5}

## Spend (ledger rows of the rev1 arm labels)

USD 0.424673 in 900 paid calls: LINT-clean_rev1-dismissal USD 0.092193 (196 calls); LINT-clean_rev1-tenancy USD 0.132368 (283 calls); LINT-clean_rev1-theft USD 0.200111 (421 calls). Ledger total before part C: USD 2.794694; launch stop at USD 3.194694.

## Reading the comparison

- Coverage: 95 of 176 files were re-run (tenancy 31 of 59, theft 42 of 59, dismissal 22 of 58), in the order fixed in
  REV1_PLAN.json: P1 the 16 non-denied routing failures owed to wording, P2 all 24 denied-event files, P3 the files of
  the changed fact wordings, P4 five seeded error-free control files per regime, P5 the remaining files with errors
  until the stop line (tenancy 9 of 9, theft 5 of 8, dismissal 0 of 16). The selection is weighted to the files the
  fixes target, so the after-figures are not regime estimates.
- Each "after" is a new single run: every reading and routing request changed text, so it is a fresh draw. Changes in
  files the fixes do not touch (for example ten_270f84d8acff from 4 holds to 0, ten_eec676341229 from 1 to 3 errors,
  the_fefc066e8269 from 0 to 1) show the run-to-run variation of the product; differences of one or two errors are
  within it.
- Routing failures, denied-event files: the count rises from 19 to 20 because ten_8572ddc89110 (denied) is now left
  unrouted, which is the empty plan the rule text gives (0 errors before and after). dis_ff1e9056d2c3 (an immediate
  dismissal denied by stating an ordinary notice) is now unrouted too, which removes its 5 errors against the stop
  reference; under the rule text it belongs to type 1 or 2 (benchmark design, DIAGNOSIS.md). The 6 theft denied files
  routed to the other type stay so (24 errors, benchmark design).
- the_248aa95805a8 (flatmate theft at home, household_perpetrator stated true) is now routed to theft_at_home, but two
  readings of three still answer that whether the flatmate did it is open, so the product holds the exclusion's four
  documents (4 holds; before, the unrouted empty plan coincided with the stop reference: 0 errors). The routing fix
  exposes the household reading of the_656f9aad39e5's kind (DIAGNOSIS.md, cause 6), not a new defect.
- Non-denied routing failures left after the revision: the_32a656cb56cf and the_d76f5df60f83, whose defining event is
  designed open and is itself the routing question (benchmark design).

