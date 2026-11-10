# Rule review summary

Scope: all 98 rules in `rules.json`, each checked against the passages it cites. Output is in `reviewed_rules.json`, with per-rule detail in `review_log.json`. `python3 validate.py reviewed_rules.json` reports VALID: 98 rules, 7 diff lines.

## Counts by decision

| Decision | Rules |
|---|---|
| unchanged | 85 |
| ambiguous-unchanged | 7 (004, 014, 017, 038, 062, 084, 095) |
| changed | 6 (016, 023, 030, 049, 068, 074) |

## Counts by change type (7 changes in 6 rules)

| Change type | Count |
|---|---|
| route split into alternatives | 3 (016 fact, 016 confirming evidence, 074) |
| condition broadened | 1 (030) |
| condition added | 1 (068) |
| document added | 1 (049) |
| document removed | 1 (023 confirming evidence) |
| condition narrowed / removed, routes merged | 0 |

## Most consequential changes

Only 7 changes were justified, so they are all listed below. Positions 8 to 10 are the three most consequential unresolved points.

1. **016 — valuables evidence.** The rule required a receipt and an expert valuation together. It now accepts either one.
   Source: "Wertsachenversicherung: Rechnungen, Quittungen, Schätzungen usw." (theft-source-0191) lists examples, not cumulative requirements.
2. **074 — listed valuables of CHF 1,000 or more.** A receipt and an expert valuation were joint; either now suffices.
   Source: "wenn im Schadenfall keine Quittung oder ein Wertgutachten ... vorgewiesen werden kann" (theft-source-0159).
3. **030 — deductible.** The condition excluded every policy with an agreed deductible, so the rule could never deduct one. It now covers the policy-agreed deductible, or CHF 200 by default.
   Source: "den in der Police vereinbarten Selbstbehalt zu tragen" (theft-source-0167).
4. **016 — confirming evidence.** The same receipt-and-valuation route was split into two alternatives.
   Source: theft-source-0191, as in item 1.
5. **049 — police report on CSS request.** The evidence item had no document. The police report (D07) has been added.
   Source: "Ein entsprechender Polizeirapport kann durch die CSS einverlangt werden" (theft-source-0043).
6. **068 — partial-payment amount (Generali).** The rule had no condition. It now applies only when a partial payment is demanded four weeks or more after the loss.
   Source: "4 Wochen nach Eintritt des Schadens können Sie eine Teilzahlung ... verlangen" (theft-source-0090).
7. **023 — confirming evidence.** Removed D20, the insurer's demand for communications, which is a different document from the written request to appoint an expert.
   Source: "nachdem sie dazu schriftlich aufgefordert wurde" (theft-source-0023), which refers to a request to appoint an expert.
8. **(open) 095 and 062.** The claim-form fields "Name der Versicherungsgesellschaft" and "Policen-Nr. / Schaden-Nr." share section s35/s36 with the liability questions. They probably refer to the liable person's insurer (D14), not the claimant's own policy (D03).
   Left unchanged because the bare field labels do not say this. A decision needs the form layout.
9. **(open) 038 — payment not yet due.** Generali and AXA require an investigation **and** unconcluded proceedings; CSS/SVV accept either (theft-source-0095 says "oder"). The rule uses the conjunctive reading.
   Left unchanged because the sources conflict. A per-insurer split would resolve it.
10. **(open) 004 and 014 — conditions broader than their sources.** In 004, perpetrator-identification and recovery duties (theft clauses only) sit under an any-event condition. In 014, original vouchers are requested for every damaged or stolen item, based on the claim form's "bitte ... beilegen".
    Both left unchanged because no cited words contradict them directly.

## Systematic observations

- Where a source accepts several kinds of evidence, the alternatives were extracted as one joint route. This happened for both receipt-or-valuation passages (016, 074).
- Rules merge provisions from five insurers and the VVG into one condition. Where insurers differ (038, 017, 008 "innerhalb der Schweiz"), the merged rule cannot be faithful to all of them, because rules carry no insurer dimension.
- Bare claim-form field labels were extracted without their section context (062, 095).
- Confirming-evidence routes often name documents that the cited passages do not mention (005, 015, 017 join several documents). They were left as they are unless a cited passage contradicted them (023).
