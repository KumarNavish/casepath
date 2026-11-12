# Planted-defect test of the rule lint (Study 4, step 2d)

**DEVELOPMENT material, post hoc, not a result.** Product at the tested commit 6a72159c (worktree read-only), checklist-only run scope, reasoning on, gpt-6-luna, one run per file (run index 0), through the caching transport with the ledger under `study4/lint/runs/`. Design sealed before any call on the development files: `DESIGN.json` SHA-256 `2194e41d9132a79a09c0077fecd16f10cba91e220bd199c3a75c0c1c4e06182b`, written 2026-11-12T13:48:38Z. The widened wordings were written by the same session that knows the lint and wrote this analysis.

## Rules

**Lint.** For each condition (fact) of a type, over the files of that type in which the recorded state of that fact (design.json `facts`; for files flagged kept_as_read these are the states as read) is "stated false" or "not mentioned": the share of files in which the product's readings admit the fact as true. Admitted true = the product's own admission: the fact's row in the run result has status "established" with value true (the product establishes a deciding fact only when all three readings give that value, each with a quotation located word for word in the files). Also reported: the share in which at least one reading answered true (from the stored reading responses). A condition is flagged when the admitted-true share is at least one half with at least five such files; with fewer than five files it is "not assessable". For calibration, the admitted-true share over files where the recorded state is "stated true" and over files where it is "open" is reported too. A file whose run failed or whose run did not read this type's facts (routed elsewhere, or no readings) is not counted in the denominator and is listed.

**Detection and false alarms.** A planted condition is detected in an arm when it is flagged in that arm and was not flagged in the clean arm. False alarm: an untouched condition (branch condition not widened in that arm, defining events reported separately) that is flagged; counted in the clean arm and in each widened arm.

**Arms run.** tenancy: blunt, clean, subtle; theft: blunt, clean; dismissal: blunt, clean. The estimate exceeded the stop line, so the sealed fallback applied: clean and blunt everywhere, subtle on tenancy only.

## Planted defects

| Regime | Condition | Original | Blunt | Subtle (dropped qualifier) |
|---|---|---|---|---|
| tenancy | defect_mold_heating.deposit_intended | Does the claim state that the tenant intends to pay the rent on deposit with the office designated by the canton instead of to the landlord, or has begun to do so? | Does the claim state that the tenant wants the defect remedied, or is considering steps to make the landlord remedy it? | Does the claim state that the tenant intends to stop paying the rent to the landlord, or has begun to do so? ('on deposit with the office designated by the canton' (withholding the rent now counts)) |
| tenancy | defect_mold_heating.rent_deposited | Does the claim state that at least one rent payment has already been paid into deposit with the office designated by the canton? | Does the claim state that the tenant has already done something about the defect (for example reported it, complained about it, or taken a step concerning the rent)? | Does the claim state that at least one rent payment is paid, or is to be paid, into deposit with the office designated by the canton? ('already' (a planned deposit now counts)) |
| tenancy | lease_termination_dispute.extension_requested | Does the tenant seek an extension of the lease because having to leave by the end date would be a hardship for the tenant or the tenant's family? | Does the tenant want to stay in the dwelling, or need time before moving out? | - |
| tenancy | lease_termination_dispute.family_residence | Does the claim state that the tenant is married or in a registered partnership and that the rented dwelling serves as the family home? | Does the claim state that the tenant lives in the rented dwelling? | Does the claim state that the tenant lives in the rented dwelling with a partner or family members, so that it serves as their family home? ('married or in a registered partnership' (a cohabiting partner now counts)) |
| tenancy | rent_increase_dispute.graduated_rent | Does the claim state that the increase is a step fixed in advance in the lease, by which the rent rises periodically by fixed amounts (graduated rent)? | Does the claim state by how much, or to what amount, the rent is to rise? | - |
| tenancy | rent_increase_dispute.index_clause | Does the claim state that the increase applies a clause of the lease linking the rent to an index (such as the Swiss consumer price index)? | Does the increase notice or the claim give a reason or a basis for the increase? | - |
| theft | simple_theft_away.bicycle | Is a bicycle among the stolen or damaged items? (Not this: A motor scooter or motorcycle; bicycle parts or accessories alone. A stated e-bike leaves the fact open: the form's word 'Fahrrad' does not decide it.) | Is something the policyholder had with them or used outside the home (for example a bag, a phone, a bicycle or sports equipment) among the stolen or damaged items? | Is a bicycle, an e-bike, or a part or accessory of a bicycle among the stolen or damaged items? (Not this: A motor scooter or motorcycle.) ('bicycle parts or accessories alone' are not a bicycle, and the e-bike rule (parts, accessories and e-bikes now count)) |
| theft | simple_theft_away.traces_changed | Does the file state that traces of the theft (for example pry marks, a broken lock, window or container) have been removed or altered, or are to be removed or altered, by the policyholder or on their behalf, for example by repair or cleaning? (Not this: Traces that exist and are left as they were, or were only photographed; the police examining the scene; traces changed by the thief or by events outside the policyholder's control.) | Does the file describe the place or the items after the theft, or what was done there afterwards? | Does the file state that traces of the theft (for example pry marks, a broken lock, window or container) have been removed or altered, or are to be removed or altered, for example by repair or cleaning? (Not this: Traces that exist and are left as they were, or were only photographed.) ('by the policyholder or on their behalf' (traces changed by the thief or by others now count)) |
| theft | theft_at_home.burglary_or_robbery | Was the theft a burglary (the thief forcibly entered the building or a room of it, or broke open a container in it, or unlocked it with the correct keys or codes that the thief had obtained by burglary or robbery; a vehicle is not a container) or a robbery (theft under threat or use of violence against the policyholder or a member of the household, or while they could not resist because of unconsciousness, accident or death; pickpocketing and trick theft are not robbery), and so not a simple theft? (Not this: A theft through a door or window left open or unlocked, without force and without violence against a person: that is a simple theft. Breaking into a vehicle is not a burglary (a vehicle is not a container), and pickpocketing or trick theft is not a robbery: both are simple thefts.) | Does the file describe how the thief got at the stolen or damaged items? | - |
| theft | theft_at_home.imminent_danger | Does the file state that the measures could not wait for the insurer's instruction because of imminent danger (Gefahr im Verzug)? (Not this: The claimant simply acted quickly or found it convenient, without a danger of further loss before the insurer could be asked.) | Does the file state that the policyholder did something soon after discovering the theft (for example called the police, secured the home, or informed the insurer)? | Does the file state that measures to reduce the loss were taken without waiting for the insurer's instruction? ('because of imminent danger (Gefahr im Verzug)' (acting quickly for any reason now counts)) |
| theft | theft_at_home.measures_pending | Does the file state that measures to reduce the loss are still to be taken (not yet carried out)? (Not this: Measures already carried out; the notification of the claim itself; steps to find the thief or recover the items.) | Does the file state that something still has to be done or settled after the theft (for example repairs, replacements, or the claim itself)? | - |
| dismissal | immediate_dismissal.fixed_term | Was the employment relationship agreed for a fixed term, with an agreed end date, rather than for an unlimited period? | Does the file state what kind of employment contract the employee had, or when the employment began? | - |
| dismissal | immediate_dismissal.incapacity_cause | Does the employer give as the cause of the dismissal the employee's absence from work, and does the employee say they were prevented from working through no fault of their own (for instance illness, accident or a non-voluntary legal obligation)? | Does the employer give a cause for the dismissal, or does the employee say why it happened? | Does the employer give as the cause of the dismissal the employee's absence from work, and does the employee give a reason for the absence? ('through no fault of their own' (any stated reason for the absence now counts)) |
| dismissal | protected_period_notice.compulsory_service | Was the employee performing Swiss compulsory military service, civil defence service or alternative civilian service on the day notice was given or while the notice period was running, or, for such a service lasting more than eleven days, did either of those fall within the four weeks before or after it? | Was the employee absent from work, or unable to work, for some reason (for example illness, accident, service, pregnancy or leave) around the time of the notice? | Was the employee performing Swiss compulsory military service, civil defence service or alternative civilian service at some time during the employment relationship? (the time window 'on the day notice was given or while the notice period was running (or within four weeks of a service over eleven days)') |
| dismissal | protected_period_notice.notice_during_probation | Was the notice given while the probation period was still running, counting any extension of the probation period under art. 335b para. 3 (a probation period interrupted by illness, accident or a non-voluntary legal obligation is extended accordingly)? | Does the file state when the employment began, or how long the employee had worked there when notice was given? | - |
| dismissal | protected_period_notice.notice_period_varied | Does the file say that a written individual employment contract, a standard employment contract or a collective employment contract sets notice periods different from the statutory ones (seven days during probation, art. 335b para. 1; one month in the first year of service, two months in the second to ninth years, three months thereafter)? | Does the file mention a notice period, an employment contract, or the date on which the employment is to end? | - |
| dismissal | wrongful_termination.action_in_time | Did the employee make the compensation claim pending (German: "Klage anhängig gemacht") within 180 days of the end of the employment relationship? | Has the employee taken, or does the employee plan, any step against the notice (for example an objection, a letter, or legal advice)? | - |
| dismissal | wrongful_termination.notice_period_ended | Has the notice period (from the notice to the end of the employment relationship) already ended? | Does the file state the date on which the notice was given, or the date on which the employment ends or ended? | Has the employee's last working day already passed? ('the notice period (from the notice to the end of the employment relationship)' (a release from work before the end now counts)) |
| dismissal | wrongful_termination.retaliation_for_claims | Was the notice given because the employee had asserted, in good faith, claims arising from the employment relationship? | Does the employee say that the notice was unfair or given for a wrong reason? | Was the notice given after the employee had asserted, in good faith, claims arising from the employment relationship? ('because' (a coincidence in time now counts)) |

## (b) Detection and false alarms

- **blunt, tenancy:** planted 6; detected (flagged here, not in clean) 4 ['defect_mold_heating.rent_deposited', 'lease_termination_dispute.family_residence', 'rent_increase_dispute.graduated_rent', 'rent_increase_dispute.index_clause']; flagged but also flagged in clean []; not flagged ['defect_mold_heating.deposit_intended', 'lease_termination_dispute.extension_requested']; not assessable ['defect_mold_heating.deposit_intended']. Untouched branch conditions 7: flagged 0 []; not assessable []. Defining events flagged: none.
- **blunt, theft:** planted 5; detected (flagged here, not in clean) 3 ['simple_theft_away.traces_changed', 'theft_at_home.imminent_danger', 'theft_at_home.measures_pending']; flagged but also flagged in clean []; not flagged ['simple_theft_away.bicycle', 'theft_at_home.burglary_or_robbery']; not assessable []. Untouched branch conditions 9: flagged 0 []; not assessable []. Defining events flagged: none.
- **blunt, dismissal:** planted 8; detected (flagged here, not in clean) 3 ['protected_period_notice.notice_period_varied', 'wrongful_termination.action_in_time', 'wrongful_termination.notice_period_ended']; flagged but also flagged in clean []; not flagged ['immediate_dismissal.fixed_term', 'immediate_dismissal.incapacity_cause', 'protected_period_notice.compulsory_service', 'protected_period_notice.notice_during_probation', 'wrongful_termination.retaliation_for_claims']; not assessable ['immediate_dismissal.fixed_term']. Untouched branch conditions 12: flagged 0 []; not assessable []. Defining events flagged: none.
- **subtle, tenancy:** planted 3; detected (flagged here, not in clean) 0 []; flagged but also flagged in clean []; not flagged ['defect_mold_heating.deposit_intended', 'defect_mold_heating.rent_deposited', 'lease_termination_dispute.family_residence']; not assessable ['defect_mold_heating.deposit_intended']. Untouched branch conditions 10: flagged 0 []; not assessable []. Defining events flagged: none.
- **clean, tenancy:** branch conditions 13; flagged 0 []; not assessable ['defect_mold_heating.deposit_intended']; defining events flagged: none.
- **clean, theft:** branch conditions 14; flagged 0 []; not assessable []; defining events flagged: none.
- **clean, dismissal:** branch conditions 20; flagged 0 []; not assessable ['immediate_dismissal.fixed_term']; defining events flagged: none.

## (a) Per condition

Assessed = files of the type whose recorded state is stated false or not mentioned and whose run read the type's facts. Admitted = product established true. Calibration: admitted-true share where the recorded state is stated true (T) and open (O).

### tenancy, clean arm

| Condition | Planted | Assessed | Admitted true | Some reading true | Flagged | T (n) | O (n) | All files of type (n) |
|---|---|---|---|---|---|---|---|---|
| defect_mold_heating.defect_present (defining event) | - | 0 | 0 (-) | 0 (-) | not assessable | 92% (13) | - (0) | 92% (13) |
| defect_mold_heating.landlord_unaware | - | 7 | 0 (0%) | 0 (0%) | no | 100% (4) | 0% (2) | 31% (13) |
| defect_mold_heating.notice_oral_only | - | 11 | 0 (0%) | 0 (0%) | no | 100% (2) | - (0) | 15% (13) |
| defect_mold_heating.damages_claimed | - | 10 | 0 (0%) | 0 (0%) | no | 100% (2) | 0% (1) | 15% (13) |
| defect_mold_heating.deposit_intended | - | 3 | 0 (0%) | 0 (0%) | not assessable | 100% (9) | 0% (1) | 69% (13) |
| defect_mold_heating.rent_deposited | - | 6 | 0 (0%) | 0 (0%) | no | 100% (6) | 0% (1) | 46% (13) |
| lease_termination_dispute.notice_received (defining event) | - | 1 | 0 (0%) | 0 (0%) | not assessable | 100% (17) | - (0) | 94% (18) |
| lease_termination_dispute.family_residence | - | 8 | 0 (0%) | 0 (0%) | no | 100% (10) | - (0) | 56% (18) |
| lease_termination_dispute.arrears_termination | - | 10 | 0 (0%) | 0 (0%) | no | 100% (6) | 0% (2) | 33% (18) |
| lease_termination_dispute.asserted_claims | - | 10 | 0 (0%) | 0 (0%) | no | 67% (6) | 0% (2) | 22% (18) |
| lease_termination_dispute.extension_requested | - | 9 | 0 (0%) | 0 (0%) | no | 100% (9) | - (0) | 50% (18) |
| rent_increase_dispute.increase_applied (defining event) | - | 4 | 0 (0%) | 0 (0%) | not assessable | 100% (16) | 0% (2) | 73% (22) |
| rent_increase_dispute.graduated_rent | - | 15 | 0 (0%) | 0 (0%) | no | 100% (5) | 0% (2) | 23% (22) |
| rent_increase_dispute.index_clause | - | 18 | 0 (0%) | 0 (0%) | no | 75% (4) | - (0) | 14% (22) |
| rent_increase_dispute.cost_or_services_reason | - | 18 | 0 (0%) | 0 (0%) | no | 100% (4) | - (0) | 18% (22) |
| rent_increase_dispute.termination_with_increase | - | 19 | 0 (0%) | 0 (0%) | no | 100% (3) | - (0) | 14% (22) |

Files not counted: ten_429b182434cf (routed to None); ten_776e0e61986b (routed to None); ten_b4d4cb05336f (routed to lease_termination_dispute); ten_c1e4987669e8 (routed to None); ten_c2a72cbf1698 (routed to None); ten_e4858b3af131 (routed to lease_termination_dispute)

### tenancy, blunt arm

| Condition | Planted | Assessed | Admitted true | Some reading true | Flagged | T (n) | O (n) | All files of type (n) |
|---|---|---|---|---|---|---|---|---|
| defect_mold_heating.defect_present (defining event) | - | 0 | 0 (-) | 0 (-) | not assessable | 100% (13) | - (0) | 100% (13) |
| defect_mold_heating.landlord_unaware | - | 7 | 0 (0%) | 0 (0%) | no | 100% (4) | 0% (2) | 31% (13) |
| defect_mold_heating.notice_oral_only | - | 11 | 0 (0%) | 0 (0%) | no | 100% (2) | - (0) | 15% (13) |
| defect_mold_heating.damages_claimed | - | 10 | 0 (0%) | 0 (0%) | no | 100% (2) | 0% (1) | 15% (13) |
| defect_mold_heating.deposit_intended | blunt | 3 | 2 (67%) | 2 (67%) | not assessable | 100% (9) | 0% (1) | 85% (13) |
| defect_mold_heating.rent_deposited | blunt | 6 | 3 (50%) | 4 (67%) | yes | 100% (6) | 100% (1) | 77% (13) |
| lease_termination_dispute.notice_received (defining event) | - | 1 | 0 (0%) | 0 (0%) | not assessable | 100% (17) | - (0) | 94% (18) |
| lease_termination_dispute.family_residence | blunt | 8 | 7 (88%) | 8 (100%) | yes | 100% (10) | - (0) | 94% (18) |
| lease_termination_dispute.arrears_termination | - | 10 | 0 (0%) | 0 (0%) | no | 100% (6) | 0% (2) | 33% (18) |
| lease_termination_dispute.asserted_claims | - | 10 | 0 (0%) | 0 (0%) | no | 67% (6) | 0% (2) | 22% (18) |
| lease_termination_dispute.extension_requested | blunt | 9 | 0 (0%) | 1 (11%) | no | 100% (9) | - (0) | 50% (18) |
| rent_increase_dispute.increase_applied (defining event) | - | 4 | 0 (0%) | 0 (0%) | not assessable | 100% (16) | 0% (2) | 73% (22) |
| rent_increase_dispute.graduated_rent | blunt | 15 | 9 (60%) | 10 (67%) | yes | 80% (5) | 100% (2) | 68% (22) |
| rent_increase_dispute.index_clause | blunt | 18 | 13 (72%) | 13 (72%) | yes | 75% (4) | - (0) | 73% (22) |
| rent_increase_dispute.cost_or_services_reason | - | 18 | 0 (0%) | 0 (0%) | no | 100% (4) | - (0) | 18% (22) |
| rent_increase_dispute.termination_with_increase | - | 19 | 0 (0%) | 0 (0%) | no | 100% (3) | - (0) | 14% (22) |

Quotations the readings relied on, flagged conditions:

- defect_mold_heating.rent_deposited (ten_2249a3b45704, recorded stated_false): "Die Mängelmeldung vom 4. August mit meiner Beschreibung lege ich Ihnen bei."
- defect_mold_heating.rent_deposited (ten_68f29695fb98, recorded not_mentioned): "I reported it to Mr Henry Palmer by e-mail on 20 January 2026"
- lease_termination_dispute.family_residence (ten_060ca05c5691, recorded not_mentioned): "Ich wohne seit Dezember 2022 in einer Genossenschaftswohnung der Talgrund Genossenschaft an der Hauptstrasse 23 in Frauenfeld"
- lease_termination_dispute.family_residence (ten_094dc11f4ef9, recorded not_mentioned): "Ich bitte deshalb darum, dass ich deutlich länger bleiben darf als bis zum Termin in der Kündigung"
- rent_increase_dispute.graduated_rent (ten_2dff5fa7a980, recorded not_mentioned): "by CHF 262.50"
- rent_increase_dispute.graduated_rent (ten_49dab8d40787, recorded stated_false): "That is CHF 850 more every month."
- rent_increase_dispute.index_clause (ten_2dff5fa7a980, recorded not_mentioned): "the rents for similar flats along the lake have "risen considerably" and that mine should be brought into line with them."
- rent_increase_dispute.index_clause (ten_49dab8d40787, recorded stated_false): "my rent is "well below what comparable flats in Neuchâtel cost today"."

Files not counted: ten_429b182434cf (routed to None); ten_776e0e61986b (routed to None); ten_b4d4cb05336f (routed to lease_termination_dispute); ten_c1e4987669e8 (routed to None); ten_c2a72cbf1698 (routed to None); ten_e4858b3af131 (routed to lease_termination_dispute)

### tenancy, subtle arm

| Condition | Planted | Assessed | Admitted true | Some reading true | Flagged | T (n) | O (n) | All files of type (n) |
|---|---|---|---|---|---|---|---|---|
| defect_mold_heating.defect_present (defining event) | - | 0 | 0 (-) | 0 (-) | not assessable | 100% (13) | - (0) | 100% (13) |
| defect_mold_heating.landlord_unaware | - | 7 | 0 (0%) | 0 (0%) | no | 100% (4) | 0% (2) | 31% (13) |
| defect_mold_heating.notice_oral_only | - | 11 | 0 (0%) | 0 (0%) | no | 100% (2) | - (0) | 15% (13) |
| defect_mold_heating.damages_claimed | - | 10 | 0 (0%) | 0 (0%) | no | 100% (2) | 0% (1) | 15% (13) |
| defect_mold_heating.deposit_intended | subtle | 3 | 0 (0%) | 0 (0%) | not assessable | 100% (9) | 0% (1) | 69% (13) |
| defect_mold_heating.rent_deposited | subtle | 6 | 2 (33%) | 2 (33%) | no | 100% (6) | 0% (1) | 62% (13) |
| lease_termination_dispute.notice_received (defining event) | - | 1 | 0 (0%) | 0 (0%) | not assessable | 100% (17) | - (0) | 94% (18) |
| lease_termination_dispute.family_residence | subtle | 8 | 0 (0%) | 0 (0%) | no | 100% (10) | - (0) | 56% (18) |
| lease_termination_dispute.arrears_termination | - | 10 | 0 (0%) | 0 (0%) | no | 100% (6) | 0% (2) | 33% (18) |
| lease_termination_dispute.asserted_claims | - | 10 | 0 (0%) | 0 (0%) | no | 67% (6) | 0% (2) | 22% (18) |
| lease_termination_dispute.extension_requested | - | 9 | 0 (0%) | 0 (0%) | no | 100% (9) | - (0) | 50% (18) |
| rent_increase_dispute.increase_applied (defining event) | - | 4 | 0 (0%) | 0 (0%) | not assessable | 100% (16) | 0% (2) | 73% (22) |
| rent_increase_dispute.graduated_rent | - | 15 | 0 (0%) | 0 (0%) | no | 100% (5) | 0% (2) | 23% (22) |
| rent_increase_dispute.index_clause | - | 18 | 0 (0%) | 0 (0%) | no | 75% (4) | - (0) | 14% (22) |
| rent_increase_dispute.cost_or_services_reason | - | 18 | 0 (0%) | 0 (0%) | no | 100% (4) | - (0) | 18% (22) |
| rent_increase_dispute.termination_with_increase | - | 19 | 0 (0%) | 0 (0%) | no | 100% (3) | - (0) | 14% (22) |

Files not counted: ten_429b182434cf (routed to None); ten_776e0e61986b (routed to None); ten_b4d4cb05336f (routed to lease_termination_dispute); ten_c1e4987669e8 (routed to None); ten_c2a72cbf1698 (routed to None); ten_e4858b3af131 (routed to lease_termination_dispute)

### theft, clean arm

| Condition | Planted | Assessed | Admitted true | Some reading true | Flagged | T (n) | O (n) | All files of type (n) |
|---|---|---|---|---|---|---|---|---|
| simple_theft_away.theft_away (defining event) | - | 0 | 0 (-) | 0 (-) | not assessable | 94% (16) | - (0) | 94% (16) |
| simple_theft_away.away_cover_missing | - | 14 | 0 (0%) | 0 (0%) | no | 100% (2) | - (0) | 12% (16) |
| simple_theft_away.traces_changed | - | 14 | 0 (0%) | 0 (0%) | no | 100% (2) | - (0) | 12% (16) |
| simple_theft_away.bicycle | - | 7 | 0 (0%) | 0 (0%) | no | 100% (7) | 0% (2) | 44% (16) |
| simple_theft_away.vouchers_unobtainable | - | 9 | 0 (0%) | 0 (0%) | no | 100% (7) | - (0) | 44% (16) |
| simple_theft_away.measures_pending | - | 10 | 0 (0%) | 0 (0%) | no | 40% (5) | 0% (1) | 12% (16) |
| simple_theft_away.imminent_danger | - | 12 | 0 (0%) | 0 (0%) | no | 100% (4) | - (0) | 25% (16) |
| theft_at_home.theft_at_home (defining event) | - | 0 | 0 (-) | 0 (-) | not assessable | 100% (24) | - (0) | 100% (24) |
| theft_at_home.household_perpetrator | - | 20 | 0 (0%) | 0 (0%) | no | 75% (4) | - (0) | 12% (24) |
| theft_at_home.burglary_or_robbery | - | 17 | 0 (0%) | 0 (0%) | no | 100% (7) | - (0) | 29% (24) |
| theft_at_home.lock_change | - | 11 | 0 (0%) | 0 (0%) | no | 100% (10) | 0% (3) | 42% (24) |
| theft_at_home.traces_changed | - | 19 | 0 (0%) | 0 (0%) | no | 75% (4) | 0% (1) | 12% (24) |
| theft_at_home.bicycle | - | 14 | 0 (0%) | 0 (0%) | no | 90% (10) | - (0) | 38% (24) |
| theft_at_home.vouchers_unobtainable | - | 15 | 0 (0%) | 0 (0%) | no | 100% (7) | 0% (2) | 29% (24) |
| theft_at_home.measures_pending | - | 20 | 0 (0%) | 0 (0%) | no | 25% (4) | - (0) | 4% (24) |
| theft_at_home.imminent_danger | - | 15 | 0 (0%) | 0 (0%) | no | 88% (8) | 0% (1) | 29% (24) |

Files not counted: the_0cd1b047049a (routed to None); the_12ee892d56f4 (routed to None); the_1dfba8facf5e (routed to simple_theft_away); the_248aa95805a8 (routed to None); the_32a656cb56cf (routed to None); the_5ee356013cfc (routed to None); the_6634ab23ee99 (routed to simple_theft_away); the_685edf55333b (routed to simple_theft_away); the_819379d12c03 (routed to None); the_86b4e22a87e7 (routed to simple_theft_away); the_86e739ec9184 (routed to theft_at_home); the_9355c558630a (routed to None); the_a529fff2269d (routed to theft_at_home); the_c50e0bd7b054 (routed to None); the_c7620535798b (routed to None); the_d37fc3c54b4b (routed to None); the_d76f5df60f83 (routed to None); the_d9579f891719 (routed to None); the_dd72ec4e53dd (routed to None)

### theft, blunt arm

| Condition | Planted | Assessed | Admitted true | Some reading true | Flagged | T (n) | O (n) | All files of type (n) |
|---|---|---|---|---|---|---|---|---|
| simple_theft_away.theft_away (defining event) | - | 0 | 0 (-) | 0 (-) | not assessable | 100% (16) | - (0) | 100% (16) |
| simple_theft_away.away_cover_missing | - | 14 | 0 (0%) | 0 (0%) | no | 100% (2) | - (0) | 12% (16) |
| simple_theft_away.traces_changed | blunt | 14 | 13 (93%) | 14 (100%) | yes | 100% (2) | - (0) | 94% (16) |
| simple_theft_away.bicycle | blunt | 7 | 2 (29%) | 4 (57%) | no | 100% (7) | 0% (2) | 56% (16) |
| simple_theft_away.vouchers_unobtainable | - | 9 | 0 (0%) | 0 (0%) | no | 100% (7) | - (0) | 44% (16) |
| simple_theft_away.measures_pending | - | 10 | 0 (0%) | 0 (0%) | no | 40% (5) | 0% (1) | 12% (16) |
| simple_theft_away.imminent_danger | - | 12 | 0 (0%) | 0 (0%) | no | 100% (4) | - (0) | 25% (16) |
| theft_at_home.theft_at_home (defining event) | - | 0 | 0 (-) | 0 (-) | not assessable | 100% (24) | - (0) | 100% (24) |
| theft_at_home.household_perpetrator | - | 20 | 0 (0%) | 0 (0%) | no | 75% (4) | - (0) | 12% (24) |
| theft_at_home.burglary_or_robbery | blunt | 17 | 6 (35%) | 9 (53%) | no | 100% (7) | - (0) | 54% (24) |
| theft_at_home.lock_change | - | 11 | 0 (0%) | 0 (0%) | no | 100% (10) | 0% (3) | 42% (24) |
| theft_at_home.traces_changed | - | 19 | 0 (0%) | 0 (0%) | no | 100% (4) | 0% (1) | 17% (24) |
| theft_at_home.bicycle | - | 14 | 0 (0%) | 0 (0%) | no | 100% (10) | - (0) | 42% (24) |
| theft_at_home.vouchers_unobtainable | - | 15 | 0 (0%) | 0 (0%) | no | 100% (7) | 0% (2) | 29% (24) |
| theft_at_home.measures_pending | blunt | 20 | 11 (55%) | 18 (90%) | yes | 100% (4) | - (0) | 62% (24) |
| theft_at_home.imminent_danger | blunt | 15 | 8 (53%) | 11 (73%) | yes | 100% (8) | 0% (1) | 67% (24) |

Quotations the readings relied on, flagged conditions:

- simple_theft_away.traces_changed (the_12e3d532c09d, recorded stated_false): "the cable lock was lying on the ground, cut through."
- simple_theft_away.traces_changed (the_2774fb90433e, recorded not_mentioned): "the phone is still unblocked for the moment."
- theft_at_home.measures_pending (the_281214c010bb, recorded not_mentioned): "Ich hoffe, wir finden eine Lösung."
- theft_at_home.measures_pending (the_314b305efe2d, recorded not_mentioned): "Die Verwaltung, die Birkenrain Betriebs AG, klärt im Moment ab, ob sie nur meinen Zylinder ersetzt oder gleich die ganze Schliessanlage im Haus."
- theft_at_home.imminent_danger (the_1487759fc403, recorded not_mentioned): "The serial numbers went to the police the same week"
- theft_at_home.imminent_danger (the_1595e412e131, recorded not_mentioned): "Ich habe noch am selben Abend Anzeige erstattet"

Files not counted: the_0cd1b047049a (routed to None); the_12ee892d56f4 (routed to None); the_1dfba8facf5e (routed to simple_theft_away); the_248aa95805a8 (routed to None); the_32a656cb56cf (routed to None); the_5ee356013cfc (routed to None); the_6634ab23ee99 (routed to simple_theft_away); the_685edf55333b (routed to simple_theft_away); the_819379d12c03 (routed to None); the_86b4e22a87e7 (routed to simple_theft_away); the_86e739ec9184 (routed to theft_at_home); the_9355c558630a (routed to None); the_a529fff2269d (routed to theft_at_home); the_c50e0bd7b054 (routed to None); the_c7620535798b (routed to None); the_d37fc3c54b4b (routed to None); the_d76f5df60f83 (routed to None); the_d9579f891719 (routed to None); the_dd72ec4e53dd (routed to None)

### dismissal, clean arm

| Condition | Planted | Assessed | Admitted true | Some reading true | Flagged | T (n) | O (n) | All files of type (n) |
|---|---|---|---|---|---|---|---|---|
| immediate_dismissal.dismissed_immediately (defining event) | - | 0 | 0 (-) | 0 (-) | not assessable | 94% (18) | - (0) | 94% (18) |
| immediate_dismissal.reasons_requested | - | 15 | 0 (0%) | 0 (0%) | no | 67% (3) | - (0) | 11% (18) |
| immediate_dismissal.incapacity_cause | - | 12 | 0 (0%) | 0 (0%) | no | 100% (5) | 0% (1) | 28% (18) |
| immediate_dismissal.fixed_term | - | 3 | 0 (0%) | 0 (0%) | not assessable | 92% (13) | 0% (2) | 67% (18) |
| immediate_dismissal.notice_period_varied | - | 12 | 0 (0%) | 0 (0%) | no | 100% (5) | 0% (1) | 28% (18) |
| immediate_dismissal.other_earnings | - | 9 | 0 (0%) | 0 (0%) | no | 100% (6) | 0% (3) | 33% (18) |
| protected_period_notice.employer_gave_notice (defining event) | - | 0 | 0 (-) | 0 (-) | not assessable | 93% (14) | - (0) | 93% (14) |
| protected_period_notice.notice_during_probation | - | 13 | 0 (0%) | 0 (0%) | no | 100% (1) | - (0) | 7% (14) |
| protected_period_notice.probation_varied | - | 7 | 0 (0%) | 0 (0%) | no | 100% (7) | - (0) | 50% (14) |
| protected_period_notice.incapacity_illness_accident | - | 8 | 0 (0%) | 0 (0%) | no | 80% (5) | 0% (1) | 29% (14) |
| protected_period_notice.compulsory_service | - | 7 | 0 (0%) | 0 (0%) | no | 83% (6) | 0% (1) | 36% (14) |
| protected_period_notice.pregnancy_or_birth | - | 5 | 0 (0%) | 0 (0%) | no | 100% (8) | 0% (1) | 57% (14) |
| protected_period_notice.notice_before_protected_period | - | 9 | 0 (0%) | 1 (11%) | no | 100% (4) | 0% (1) | 29% (14) |
| protected_period_notice.notice_period_varied | - | 6 | 0 (0%) | 0 (0%) | no | 100% (8) | - (0) | 57% (14) |
| wrongful_termination.employer_gave_notice (defining event) | - | 0 | 0 (-) | 0 (-) | not assessable | 93% (14) | - (0) | 93% (14) |
| wrongful_termination.notice_period_ended | - | 6 | 0 (0%) | 0 (0%) | no | 100% (8) | - (0) | 57% (14) |
| wrongful_termination.objection_submitted | - | 9 | 0 (0%) | 0 (0%) | no | 67% (3) | 0% (2) | 14% (14) |
| wrongful_termination.agreed_to_continue | - | 13 | 0 (0%) | 0 (0%) | no | - (0) | 0% (1) | 0% (14) |
| wrongful_termination.more_than_180_days | - | 9 | 0 (0%) | 0 (0%) | no | 100% (5) | - (0) | 36% (14) |
| wrongful_termination.action_in_time | - | 10 | 0 (0%) | 0 (0%) | no | 100% (4) | - (0) | 29% (14) |
| wrongful_termination.reasons_requested | - | 8 | 0 (0%) | 0 (0%) | no | 100% (6) | - (0) | 43% (14) |
| wrongful_termination.retaliation_for_claims | - | 9 | 0 (0%) | 0 (0%) | no | 40% (5) | - (0) | 14% (14) |
| wrongful_termination.employee_representative | - | 8 | 0 (0%) | 0 (0%) | no | 100% (6) | - (0) | 43% (14) |

Files not counted: dis_05af0871cd70 (routed to None); dis_0f89215979d2 (routed to None); dis_14b7db92a192 (routed to None); dis_1bf62841defb (routed to None); dis_4ee0866843c9 (routed to None); dis_5215d587db4b (routed to None); dis_827bbd04ddc9 (routed to None); dis_930a1b5e1bdc (routed to None); dis_bf38c7dfb616 (routed to wrongful_termination); dis_c50430dbdfa1 (routed to wrongful_termination); dis_fea630e08ab3 (routed to None); dis_ff1e9056d2c3 (routed to wrongful_termination)

### dismissal, blunt arm

| Condition | Planted | Assessed | Admitted true | Some reading true | Flagged | T (n) | O (n) | All files of type (n) |
|---|---|---|---|---|---|---|---|---|
| immediate_dismissal.dismissed_immediately (defining event) | - | 0 | 0 (-) | 0 (-) | not assessable | 94% (18) | - (0) | 94% (18) |
| immediate_dismissal.reasons_requested | - | 15 | 0 (0%) | 0 (0%) | no | 67% (3) | - (0) | 11% (18) |
| immediate_dismissal.incapacity_cause | blunt | 12 | 1 (8%) | 1 (8%) | no | 100% (5) | 0% (1) | 33% (18) |
| immediate_dismissal.fixed_term | blunt | 3 | 3 (100%) | 3 (100%) | not assessable | 92% (13) | 0% (2) | 83% (18) |
| immediate_dismissal.notice_period_varied | - | 12 | 0 (0%) | 0 (0%) | no | 100% (5) | 0% (1) | 28% (18) |
| immediate_dismissal.other_earnings | - | 9 | 0 (0%) | 0 (0%) | no | 100% (6) | 0% (3) | 33% (18) |
| protected_period_notice.employer_gave_notice (defining event) | - | 0 | 0 (-) | 0 (-) | not assessable | 100% (14) | - (0) | 100% (14) |
| protected_period_notice.notice_during_probation | blunt | 13 | 5 (38%) | 6 (46%) | no | 100% (1) | - (0) | 43% (14) |
| protected_period_notice.probation_varied | - | 7 | 0 (0%) | 1 (14%) | no | 100% (7) | - (0) | 50% (14) |
| protected_period_notice.incapacity_illness_accident | - | 8 | 0 (0%) | 0 (0%) | no | 60% (5) | 0% (1) | 21% (14) |
| protected_period_notice.compulsory_service | blunt | 7 | 3 (43%) | 5 (71%) | no | 100% (6) | 0% (1) | 64% (14) |
| protected_period_notice.pregnancy_or_birth | - | 5 | 0 (0%) | 0 (0%) | no | 100% (8) | 0% (1) | 57% (14) |
| protected_period_notice.notice_before_protected_period | - | 9 | 0 (0%) | 0 (0%) | no | 50% (4) | 0% (1) | 14% (14) |
| protected_period_notice.notice_period_varied | blunt | 6 | 6 (100%) | 6 (100%) | yes | 100% (8) | - (0) | 100% (14) |
| wrongful_termination.employer_gave_notice (defining event) | - | 0 | 0 (-) | 0 (-) | not assessable | 100% (14) | - (0) | 100% (14) |
| wrongful_termination.notice_period_ended | blunt | 6 | 6 (100%) | 6 (100%) | yes | 100% (8) | - (0) | 100% (14) |
| wrongful_termination.objection_submitted | - | 9 | 0 (0%) | 0 (0%) | no | 100% (3) | 0% (2) | 21% (14) |
| wrongful_termination.agreed_to_continue | - | 13 | 0 (0%) | 0 (0%) | no | - (0) | 0% (1) | 0% (14) |
| wrongful_termination.more_than_180_days | - | 9 | 0 (0%) | 0 (0%) | no | 100% (5) | - (0) | 36% (14) |
| wrongful_termination.action_in_time | blunt | 10 | 5 (50%) | 8 (80%) | yes | 100% (4) | - (0) | 64% (14) |
| wrongful_termination.reasons_requested | - | 8 | 0 (0%) | 0 (0%) | no | 100% (6) | - (0) | 43% (14) |
| wrongful_termination.retaliation_for_claims | blunt | 9 | 0 (0%) | 0 (0%) | no | 100% (5) | - (0) | 36% (14) |
| wrongful_termination.employee_representative | - | 8 | 0 (0%) | 0 (0%) | no | 100% (6) | - (0) | 43% (14) |

Quotations the readings relied on, flagged conditions:

- protected_period_notice.notice_period_varied (dis_064eeecaeb0d, recorded not_mentioned): "The letter said my last day would be 14 February."
- protected_period_notice.notice_period_varied (dis_32d79153a27f, recorded not_mentioned): "my written contract set a trial period of three months, not the usual single month."
- wrongful_termination.notice_period_ended (dis_188837a70acc, recorded stated_false): "Hiermit kundigen wir das mit Ihnen bestehende Arbeitsverhä1tnis unter Einhaltung der Kundigungsfrist auf den 31. Mai 2026."
- wrongful_termination.notice_period_ended (dis_408b774aa7db, recorded stated_false): "Die Kündigung selbst hat mir Frau Keller am 29. September 2026 im Büro übergeben"
- wrongful_termination.action_in_time (dis_188837a70acc, recorded not_mentioned): "Ich habe gegen meine Kündigung schriftlich Einsprache gemacht, rechtzeitig und mit eingeschriebenem Brief an die Firma."
- wrongful_termination.action_in_time (dis_3a4e06ed3132, recorded stated_false): "On 24 July I wrote a short letter saying that I don't accept being let go"

Files not counted: dis_05af0871cd70 (routed to None); dis_0f89215979d2 (routed to None); dis_14b7db92a192 (routed to None); dis_1bf62841defb (routed to None); dis_4ee0866843c9 (routed to None); dis_5215d587db4b (routed to None); dis_827bbd04ddc9 (routed to None); dis_930a1b5e1bdc (routed to None); dis_bf38c7dfb616 (routed to wrongful_termination); dis_c50430dbdfa1 (routed to wrongful_termination); dis_fea630e08ab3 (routed to None); dis_ff1e9056d2c3 (routed to wrongful_termination)

## (c) What the clean-arm false alarms are

No untouched condition is flagged in the clean arm on any regime (0 of 13 tenancy, 0 of 14 theft, 0 of 20 dismissal branch conditions; also no defining event). No condition in the clean arm has a single admitted-true file where the recorded state is stated false or not mentioned; the largest some-reading-true count there is 1 (dismissal protected_period_notice.notice_before_protected_period, 1 of 9). There are therefore no false alarms to read for part (c). Also no untouched condition is flagged in any widened arm.

## (d) The clean arm scored (a first look at the tested core; no baseline, no comparison)

Clean arm only, against each file's final/<id>/reference.json. Product checklist = harness/product/run_product.to_plan `plan` (conservative view, as Study 3's scorer): requests = needs with required "yes" and status missing or unusable (workflow needs and needs the process builder added), holds = needs with required "depends". Per document of the routed type's catalogue, one error at most, decided by the reference state: reference hold -> product not holding it is a missed hold; reference request (state request, or present_insufficient, i.e. reference `request` true) -> product holding it is a hold where the file settles the fact, product neither requesting nor holding it is a missed request; reference not_needed or present_sufficient -> product requesting it is a request that should not be made, holding it a hold where the file settles the fact. A need the process builder added (not in the catalogue) counts as a request that should not be made when requested, as a hold where the file settles the fact when held. Supplied documents: present_sufficient means no request is due (the product's unusable/missing for it is a request that should not be made); present_insufficient means a request is due (the product's present for it is a missed request). Optional documents (mandatory false): the reference's `request` field decides as for any document (the reference never requests an unsupplied optional document). Errors per file = the sum of the four kinds. A failed run is scored as an empty plan; a run routed to no workflow (deferred) or to the wrong type is scored with the plan it produced (deferred = empty) and listed as a routing failure. Splits: share level (0, 10, 25, 50), denied-event files, open-fact files, others; overall. No baseline is run; no comparison is made.

Means per file. UR = requests that should not be made, MR = requests missed, UH = holds where the file settles the fact, MH = holds missed, E = errors per file (sum).

| Regime | Split | Files | UR | MR | UH | MH | E | Files without error |
|---|---|---|---|---|---|---|---|---|
| tenancy | overall | 59 | 0.153 | 0.085 | 0.119 | 0.0 | 0.356 | 45 |
| tenancy | level_0 | 15 | 0.067 | 0.067 | 0.067 | 0.0 | 0.2 | 12 |
| tenancy | level_10 | 15 | 0.2 | 0.067 | 0.0 | 0.0 | 0.267 | 12 |
| tenancy | level_25 | 15 | 0.133 | 0.0 | 0.0 | 0.0 | 0.133 | 13 |
| tenancy | level_50 | 14 | 0.214 | 0.214 | 0.429 | 0.0 | 0.857 | 8 |
| tenancy | denied_event | 8 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 8 |
| tenancy | open_fact | 13 | 0.154 | 0.0 | 0.077 | 0.0 | 0.231 | 10 |
| tenancy | others | 38 | 0.184 | 0.132 | 0.158 | 0.0 | 0.474 | 27 |
| tenancy | routed_correctly_only | 53 | 0.17 | 0.019 | 0.132 | 0.0 | 0.321 | 41 |
| theft | overall | 59 | 0.288 | 0.305 | 0.441 | 0.102 | 1.136 | 31 |
| theft | level_0 | 15 | 0.333 | 0.2 | 0.333 | 0.0 | 0.867 | 10 |
| theft | level_10 | 15 | 0.267 | 0.467 | 0.533 | 0.067 | 1.333 | 6 |
| theft | level_25 | 15 | 0.133 | 0.467 | 0.467 | 0.067 | 1.133 | 8 |
| theft | level_50 | 14 | 0.429 | 0.071 | 0.429 | 0.286 | 1.214 | 7 |
| theft | denied_event | 8 | 1.0 | 0.0 | 2.0 | 0.0 | 3.0 | 2 |
| theft | open_fact | 14 | 0.143 | 0.286 | 0.0 | 0.429 | 0.857 | 8 |
| theft | others | 37 | 0.189 | 0.378 | 0.27 | 0.0 | 0.838 | 21 |
| theft | routed_correctly_only | 40 | 0.225 | 0.0 | 0.25 | 0.0 | 0.475 | 27 |
| dismissal | overall | 58 | 0.172 | 0.155 | 0.466 | 0.0 | 0.793 | 35 |
| dismissal | level_0 | 15 | 0.333 | 0.067 | 1.2 | 0.0 | 1.6 | 6 |
| dismissal | level_10 | 14 | 0.214 | 0.071 | 0.071 | 0.0 | 0.357 | 10 |
| dismissal | level_25 | 14 | 0.071 | 0.286 | 0.286 | 0.0 | 0.643 | 9 |
| dismissal | level_50 | 15 | 0.067 | 0.2 | 0.267 | 0.0 | 0.533 | 10 |
| dismissal | denied_event | 8 | 0.25 | 0.0 | 0.375 | 0.0 | 0.625 | 7 |
| dismissal | open_fact | 14 | 0.214 | 0.071 | 0.214 | 0.0 | 0.5 | 9 |
| dismissal | others | 36 | 0.139 | 0.222 | 0.583 | 0.0 | 0.944 | 19 |
| dismissal | routed_correctly_only | 46 | 0.174 | 0.109 | 0.391 | 0.0 | 0.674 | 28 |
| all_regimes | overall | 176 | 0.205 | 0.182 | 0.341 | 0.034 | 0.761 | 111 |
| all_regimes | level_0 | 45 | 0.244 | 0.111 | 0.533 | 0.0 | 0.889 | 28 |
| all_regimes | level_10 | 44 | 0.227 | 0.205 | 0.205 | 0.023 | 0.659 | 28 |
| all_regimes | level_25 | 44 | 0.114 | 0.25 | 0.25 | 0.023 | 0.636 | 30 |
| all_regimes | level_50 | 43 | 0.233 | 0.163 | 0.372 | 0.093 | 0.86 | 25 |
| all_regimes | denied_event | 24 | 0.417 | 0.0 | 0.792 | 0.0 | 1.208 | 17 |
| all_regimes | open_fact | 41 | 0.171 | 0.122 | 0.098 | 0.146 | 0.537 | 27 |
| all_regimes | others | 111 | 0.171 | 0.243 | 0.333 | 0.0 | 0.748 | 67 |
| all_regimes | routed_correctly_only | 139 | 0.187 | 0.043 | 0.252 | 0.0 | 0.482 | 96 |

Routing failures: ['dismissal/dis_05af0871cd70', 'dismissal/dis_0f89215979d2', 'dismissal/dis_14b7db92a192', 'dismissal/dis_1bf62841defb', 'dismissal/dis_4ee0866843c9', 'dismissal/dis_5215d587db4b', 'dismissal/dis_827bbd04ddc9', 'dismissal/dis_930a1b5e1bdc', 'dismissal/dis_bf38c7dfb616', 'dismissal/dis_c50430dbdfa1', 'dismissal/dis_fea630e08ab3', 'dismissal/dis_ff1e9056d2c3', 'tenancy/ten_429b182434cf', 'tenancy/ten_776e0e61986b', 'tenancy/ten_b4d4cb05336f', 'tenancy/ten_c1e4987669e8', 'tenancy/ten_c2a72cbf1698', 'tenancy/ten_e4858b3af131', 'theft/the_0cd1b047049a', 'theft/the_12ee892d56f4', 'theft/the_1dfba8facf5e', 'theft/the_248aa95805a8', 'theft/the_32a656cb56cf', 'theft/the_5ee356013cfc', 'theft/the_6634ab23ee99', 'theft/the_685edf55333b', 'theft/the_819379d12c03', 'theft/the_86b4e22a87e7', 'theft/the_86e739ec9184', 'theft/the_9355c558630a', 'theft/the_a529fff2269d', 'theft/the_c50e0bd7b054', 'theft/the_c7620535798b', 'theft/the_d37fc3c54b4b', 'theft/the_d76f5df60f83', 'theft/the_d9579f891719', 'theft/the_dd72ec4e53dd']. Failed runs: none.

## (e) Spend (from the ledgers under study4/lint/runs/)

Total USD 2.7947.

| Ledger arm label | USD | Paid calls | Files with paid calls |
|---|---|---|---|
| LINT-blunt-dismissal | 0.2531 | 504 | 49 |
| LINT-blunt-tenancy | 0.2305 | 499 | 55 |
| LINT-blunt-theft | 0.2109 | 423 | 46 |
| LINT-clean-dismissal | 0.2931 | 672 | 58 |
| LINT-clean-tenancy | 0.2659 | 663 | 59 |
| LINT-clean-tenancy-gpt-6.1-terra | 1.1634 | 333 | 39 |
| LINT-clean-theft | 0.2151 | 498 | 59 |
| LINT-subtle-tenancy | 0.1628 | 350 | 33 |

Estimate (first five files): USD 0.00638 per file; clean+blunt on all regimes USD 2.24, three arms USD 3.25. three arms everywhere exceed the USD 3.20 stop line: run clean and blunt on every regime and subtle on tenancy only (DESIGN.json arm_fallback); order clean (tenancy, theft, dismissal), then widened tenancy (blunt, subtle), dismissal blunt, theft blunt. Estimated total about USD 2.5; the frontier arm needs a total under USD 2.00 after both arms and is therefore not expected to run.

Failed outputs: [{'store': 'results_clean_tenancy_gpt-6.1-terra.json', 'file': 'ten_5aecbb73131b', 'status': 'failed', 'error': 'schema_mismatch: The model answer did not match its schema: $.facts: array length outside bounds (2 items; allowed 0 to 1)'}].

## Frontier arm (gpt-6.1-terra, clean, tenancy): partial

39 of the regime's files were run (manifest order, stopped at the launch threshold); files not counted: ten_429b182434cf (routed to None); ten_580485dac025 (routed to None); ten_5aecbb73131b (failed run); ten_776e0e61986b (routed to None); ten_8572ddc89110 (routed to None); ten_8c54d4a61b0a (routed to None); ten_a743587360f3 (not run); ten_aba30f049af3 (not run); ten_b2a5ace905ae (not run); ten_b4d4cb05336f (not run); ten_ba90f9b8b195 (not run); ten_c1e4987669e8 (not run); ten_c2a72cbf1698 (not run); ten_c4ccb65aff87 (not run); ten_c934efc0b1bc (not run); ten_c95735ae0bf4 (not run); ten_cf02cc821948 (not run); ten_db552dbb3c23 (not run); ten_e4858b3af131 (not run); ten_e6d795ab2a91 (not run); ten_e94fb7461784 (not run); ten_ed10120c904e (not run); ten_eec676341229 (not run); ten_efa24ba18ce3 (not run); ten_f1871d924ee4 (not run); ten_fb2a18deebee (not run).

| Condition | Assessed | Admitted true | Some reading true | Flagged | T (n) | O (n) |
|---|---|---|---|---|---|---|
| defect_mold_heating.defect_present | 0 | 0 | 0 | not assessable | 100% (9) | - (0) |
| defect_mold_heating.landlord_unaware | 6 | 0 | 0 | no | 100% (1) | 0% (2) |
| defect_mold_heating.notice_oral_only | 7 | 0 | 0 | no | 100% (2) | - (0) |
| defect_mold_heating.damages_claimed | 6 | 0 | 0 | no | 100% (2) | 0% (1) |
| defect_mold_heating.deposit_intended | 3 | 0 | 0 | not assessable | 100% (5) | 0% (1) |
| defect_mold_heating.rent_deposited | 5 | 0 | 0 | no | 100% (4) | - (0) |
| lease_termination_dispute.notice_received | 1 | 0 | 0 | not assessable | 100% (13) | - (0) |
| lease_termination_dispute.family_residence | 6 | 0 | 0 | no | 100% (8) | - (0) |
| lease_termination_dispute.arrears_termination | 9 | 0 | 0 | no | 100% (3) | 0% (2) |
| lease_termination_dispute.asserted_claims | 7 | 0 | 0 | no | 100% (6) | 0% (1) |
| lease_termination_dispute.extension_requested | 6 | 0 | 0 | no | 100% (8) | - (0) |
| rent_increase_dispute.increase_applied | 1 | 0 | 0 | not assessable | 100% (9) | - (0) |
| rent_increase_dispute.graduated_rent | 8 | 0 | 0 | no | 100% (2) | - (0) |
| rent_increase_dispute.index_clause | 9 | 0 | 0 | no | 0% (1) | - (0) |
| rent_increase_dispute.cost_or_services_reason | 9 | 0 | 0 | no | 100% (1) | - (0) |
| rent_increase_dispute.termination_with_increase | 9 | 0 | 0 | no | 100% (1) | - (0) |

## Notes and limits

- Label: DEVELOPMENT, post hoc, not a result. The same session that knows the lint wrote the widened wordings (after the seeded draw was printed) and this analysis.
- Routing check before the main runs (one file per type, clean arm, the first paid calls): all 8 types routed correctly. The product loads and validates all nine catalogues (clean, blunt, subtle per regime) through its own parity command and validate_workflow; settings readings 3, open rule any, run scope checklist, reasoning on, tested source tree 030480203f7d...; worktree unmodified. The applies_when routing facts were presented as the rule sets already encode them (one enum routing fact per regime: dispute_family / claim_type), the same pattern as Study 3's tenancy workflows; nothing was changed.
- Routing over all 176 clean-arm files: 37 routing failures (tenancy 6, theft 19, dismissal 12) - a finding about these new workflows on the tested product, not patched. 26 are handed over unrouted (tenancy 4, theft 13, dismissal 9: routing 'needs_facts', or in theft claim_type read as 'other' in 12 files), 11 go to another type (tenancy 2, theft 6, dismissal 3). Denied-event files make up 19 of the 37 (tenancy 3, theft 8, dismissal 8); all 6 theft misroutings are denied-event files sent to the other theft type. Where the event is not denied, theft's claim_type was read as 'other' in 10 files (9 simple_theft_away, 1 theft_at_home): the claim_type question's 'Not this' clause (a burglary or robbery away from home is 'other') appears to pull simple thefts away (a bag from a car seat, a rucksack) into 'other'. Two rent-increase files went to lease_termination_dispute, two protected_period_notice files to wrongful_termination; two dismissal and one tenancy non-denied files were left unrouted.
- Lint denominators exclude files whose run did not read the type's facts (routing failure); this removes most denied-event files from the lint, which is why the defining events have 0 to 4 assessed files. The same files are identical across arms because the routing call is cached, so the exclusions are the same in every arm.
- Cache: requests identical across arms are answered from the cache (the routing call; every call of a type whose workflow an arm leaves unchanged, e.g. rent_increase_dispute in the subtle arm). Those files have identical readings in both arms; this is intended (same request, same answer) and stated in DESIGN.json.
- Why blunt widenings were missed (manipulation check, column 'All files of type'): in these generated files a 'not mentioned' fact usually means the topic is absent from the text, and a 'stated false' fact is written as an explicit denial of the original. The readings then answer the widened question not_stated (topic absent) or false (citing the denial), e.g. wrongful_termination.retaliation_for_claims widened to 'the notice was unfair or given for a wrong reason': 0 of 9 admitted, the stated-false files say 'Mit Forderungen von meiner Seite hat diese Kündigung nichts zu tun'. Several blunt wordings were therefore not true in most files of the type, contrary to their intent; detection here measures the lint and the wording together.
- Not assessable (fewer than five files with the state false or not mentioned): tenancy defect_mold_heating.deposit_intended (3 files; blunt arm 2 of 3 admitted true) and dismissal immediate_dismissal.fixed_term (3 files, always_stated; blunt arm 3 of 3 admitted true). Both planted defects would be flagged at a lower minimum; the minimum of five was fixed in the design.
- Subtle widenings: run on tenancy only (sealed fallback). 0 of 3 flagged; rent_deposited (planned deposit now counts) reached 2 of 6.
- Scoring (d): a file handed over unrouted is scored with an empty plan; in denied-event files the reference is the stop (nothing needed), so an unrouted denied file scores zero errors. A misrouted file's requests are all outside its type's catalogue and count as requests that should not be made, and its reference documents as missed. The table gives a routed-correctly-only row as well.
- Inputs: text.txt and attachments/<doc>.txt (degraded where scan_noise), attachments uploaded as attachment_<n>.txt in sorted document-id order; case titles 'Tenancy claim', 'Theft claim', 'Employment claim'. The set's file names (document ids) were not given to the product.
- Spend against the estimate: luna arms USD 1.631 in all (clean 0.774 for 176 files incl. the routing check, i.e. 0.0044 per file; blunt 0.695; subtle tenancy 0.163) against an estimate of 1.12 per full arm from the first five files (0.00638 per file); the first five happened to be costlier than the average, and widened arms reused cached routing calls. Because the total after both arms (1.63) stayed under USD 2.00, the frontier arm ran although ESTIMATE.json, written before, did not expect it.
- Frontier arm (gpt-6.1-terra, clean, tenancy): launched only while the ledger total was under USD 2.75 with 3 workers (so that runs in flight could not pass USD 3.20; the largest frontier file cost about 0.11). It stopped after 39 of 59 files in manifest order (levels 0, 10 and part of 25), USD 1.163; it is partial and not a random subset. One run failed (ten_5aecbb73131b: routing answer did not match its schema, two facts where at most one is allowed). Routing failures on this model among the 39: 5 unrouted (ten_429b182434cf, ten_580485dac025, ten_776e0e61986b, ten_8572ddc89110, ten_8c54d4a61b0a). As on luna, no condition has an admitted-true file where the recorded state is stated false or not mentioned; nothing is flagged.
- Total spend from the ledgers: USD 2.795 (cap 3.50, stop line 3.20). Failed outputs: one (the frontier run above); none on luna.

