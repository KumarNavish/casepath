# Four-eyes reconciliation

- **Editor A:** first review, in `../reviewed_rules.json`.
- **Editor B:** second review, in `../second/`.

A change is adopted only if both editors made it, or if one made it and the other approved it. Every other rule is exactly as in `rules.json`. The final file has 99 rules: the 98 originals plus the split rule `overlay_rule_020.a`.

**Validator:** `python3 ../validate.py reviewed_rules.json` reports VALID: 99 rules, 13 diff lines, all from adopted changes.

## Changed rules

| Rule | Editor A | Editor B | Decision | Deciding quotation |
|---|---|---|---|---|
| 016 | D09+D10 joint split into D09 \| D10 (fact c01 and confirming evidence) | Identical | Adopted (both) | "Wertsachenversicherung: Rechnungen, Quittungen, Schätzungen usw." (theft-source-0191) |
| 074 | D09+D10 joint split into D09 \| D10 | Identical | Adopted (both) | "wenn im Schadenfall keine Quittung oder ein Wertgutachten eines Sachverständigen vorgewiesen werden kann" (theft-source-0159) |
| 023 | D20 removed from confirming route; D21 kept | Identical | Adopted (both) | "Unterlässt eine Partei die Ernennung ihres Sachverständigen innert 14 Tagen, nachdem sie dazu schriftlich aufgefordert wurde" (theft-source-0023). The request is to appoint an expert; D20 is a demand for communications. |
| 049 | D07 police report added to f01.c01 | Identical | Adopted (both) | "Ein entsprechender Polizeirapport kann durch die CSS einverlangt werden" (theft-source-0043) |
| 068 | Condition added: "The policyholder demands a partial payment four weeks or more after the loss occurred." | Condition added: "A loss has occurred and a partial payment is sought." | Adopted (both added a condition). **A's wording** is used, because the versions differ in substance: B's condition also fires before four weeks. | "4 Wochen nach Eintritt des Schadens können Sie eine Teilzahlung ... verlangen" (theft-source-0090) |
| 030 | Condition broadened to the policy-agreed deductible or the CHF 200 default | Unchanged, then approved in `cross_check_030.json` without a smaller change | Adopted (A, approved by B). The confirming evidence's must_show and citations were aligned with the new condition text. | "Der Anspruchsberechtigte hat pro Ereignis den in der Police vereinbarten Selbstbehalt zu tragen." (theft-source-0167); "Ohne abweichende Vereinbarung ... CHF 200" (theft-source-0081) only sets the default. |
| 020 + 020.a | Unchanged | Condition added: route is joint expert or expert proceedings. Fact f02 (policyholder's assistance) moved unconditioned to 020.a. | Adopted (B, approved by A) | "Der Schaden wird entweder durch die Parteien, durch einen gemeinsamen Experten oder im Sachverständigenverfahren ermittelt." (theft-source-0193). The parties' own determination produces no expert document, yet the rule demanded D23 or D21+D22 on every claim. The split is needed because "Die CSS ermittelt den Schaden unter Mithilfe des Versicherungsnehmers und/oder mit einem gemeinsamen Experten" (theft-source-0045) applies on every route. |
| 042 | Unchanged | Condition: "a third party caused or increased the loss" became "the loss was caused or increased through the fault of a third party"; "has claims" became "could assert claims" | Adopted (B, approved by A) | "sofern der Schaden oder Verlust durch die Schuld eines Dritten entstanden oder vergrössert worden ist" (theft-source-0165); "für welche der Versicherungsnehmer gegenüber Dritten Ansprüche geltend machen könnte" (theft-source-0055) |
| 071 | Unchanged (A missed it) | D18 added to f01.c01, which had no route | Adopted (B, approved by A) | "Leistungsansprüche gegenüber der CSS darf der Versicherungsnehmer nur mit schriftlicher Zustimmung der CSS an Dritte abtreten." (theft-source-0129) |

No change was rejected.

## Review queue (14 rules; ambiguous to A, B or both, all left as in `rules.json`)

| Rule | Marked by | Question for a jurist |
|---|---|---|
| 002 | B | The CSS police report is due only on request (0043), but police notification is a duty on every theft. Should D07 be the sole evidence of notification for every insurer? |
| 003 | B | Should police or insurer consent (D26/D27) be requested whenever traces exist, or only when traces or items were actually altered? |
| 004 | A | Should perpetrator-identification and recovery measures (0056, 0099, under the theft clauses) be required after any insured event, or only after theft? |
| 010 | B | Should the causer section (D14) be requested on every claim, or only where a person who caused the loss is known? |
| 011 | B | May a signed inventory (D04) be demanded on every claim, given that the inventory duty is "auf Verlangen" (0048/0086/0163)? |
| 014 | A, B | Does the form's "bitte Originalkaufbelege beilegen" (0176) create a duty to supply original vouchers for every damaged or stolen item, or only on request as in the AVB (0048/0134)? |
| 017 | A, B | Are the medical certificate (Generali 0079) and the release from confidentiality (Simpego 0057) cumulative, or alternatives as the catalogue states? |
| 018 | B | Must the double-insurance declaration (D16) be requested on every claim, given "in jedem Fall auszufüllen" (0094), a passage this rule does not cite? |
| 029 | B | Does safe storage (0021) also lift the jewellery limit for simple theft, or only for burglary (0182)? |
| 038 | A, B | Is payment postponed when investigation **and** proceedings are pending (Generali 0018, AXA 0125), or when **either** is pending (CSS/SVV 0095)? Should the rule be split per insurer? |
| 062 | A, B | Does "Policen-Nr. / Schaden-Nr." (form s35/s36) refer to the liable person's insurer? If so, the rule needs a condition. |
| 070 | B | Does the reasonable time limit (0128) concern only the inventory? Is D20 the right confirming document? |
| 084 | A, B | Is a bank statement for "card data" misuse (D33) proper evidence of the time of SIM-card misuse (0185), jointly with the D32 report? |
| 095 | A, B | Does "Name der Versicherungsgesellschaft" (form s35/s36) mean the liable person's insurer (D14) rather than the claimant's own policy (D03)? |
