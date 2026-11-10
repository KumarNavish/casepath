# Second-editor review summary

Scope: all 98 original rules in `rules.json`, each reviewed against the passages it cites. The output has 99 rules because one rule was split (`overlay_rule_020.a` is new).

## Decisions

| Decision | Rules |
|---|---|
| unchanged | 77 |
| changed | 8 |
| ambiguous-unchanged | 13 |

## Change types

| Change type | Count |
|---|---|
| route split into alternatives | 2 |
| condition added | 2 |
| rule split (fact moved) | 1 |
| document removed | 1 |
| condition narrowed | 1 |
| document added | 2 |

## Changed rules

- overlay_rule_016: route split into alternatives (theft-source-0191)
- overlay_rule_020: condition added (theft-source-0193); rule split (fact moved) (theft-source-0045)
- overlay_rule_023: document removed (theft-source-0023)
- overlay_rule_042: condition narrowed (theft-source-0165)
- overlay_rule_049: document added (theft-source-0043)
- overlay_rule_068: condition added (theft-source-0090)
- overlay_rule_071: document added (theft-source-0129)
- overlay_rule_074: route split into alternatives (theft-source-0159)

## Ambiguous, left unchanged

- overlay_rule_002: D07 is the only route for the police notification fact. CSS says the police report is required only when CSS calls for it ('Ein entsprechender Polizeirapport kann durch die CSS einverlangt werden', 0043), while Generali/Simpego require police notification on every theft. The sources differ by insurer, so the rule is left as it is.
- overlay_rule_003: Police consent (D26) and insurer consent (D27) are needed only if traces or items were actually altered ('ohne Zustimmung der Polizei die Tatspuren nicht zu entfernen oder zu verändern', 0043). The rule fires whenever traces exist. Its must_show already says 'if changed', so it is left as it is.
- overlay_rule_010: D14 ('who caused the loss and his liability insurer') is requested on every claim. The form question 'Wer hat den Schaden verursacht?' (0114) presupposes a known causer, but no cited words restrict it, so the rule is left as it is.
- overlay_rule_011: D04 (signed inventory) is a sole or alternative route on every claim. The inventory duty is 'auf Verlangen' only in passages this rule does not cite (0048/0086/0163), so the cited passages give no quotable mismatch.
- overlay_rule_014: The CSS AVB require original vouchers only 'auf Verlangen' (0048/0134), but the CSS form asks to attach them for all damaged or stolen items ('bitte Originalkaufbelege beilegen', 0176). The disjunctive condition reflects both, so it is left as it is.
- overlay_rule_017: Each insurer requires its own document (Generali medical certificate 0079; Simpego doctor release 0057, only 'Bei Unfällen mit Personenschaden'). The catalogue marks D28 and D29 as alternatives, but no cited passage accepts either one, so the separate items are left. The joint D28+D29 confirming route is also left.
- overlay_rule_018: The catalogue says D16 is to be completed in every case, but the 'in jedem Fall auszufüllen' passage (0094) is not cited here, so no route was added.
- overlay_rule_029: 0021 lifts the limit for jewellery kept in a locked safe without naming the theft type, while 0182 lifts it only for burglary. It is unclear whether the first branch of the condition (simple theft) should also exclude safe storage, so the rule is left as it is.
- overlay_rule_038: Generali (0018) and AXA (0125) join the two conditions with 'und', but CSS (0095) uses 'oder' ('ermitteln oder ein Strafverfahren ... nicht abgeschlossen ist'). The sources conflict, so the 'and' condition is left as it is.
- overlay_rule_062: 'Policen-Nr. / Schaden-Nr.' (0075) sits in form section s35 on the person who caused the loss and that person's liability insurer, so it may not mean the insured's own policy number. The cited words alone do not show this.
- overlay_rule_070: The cited fragment 0128 ('wobei der Versicherer angemessene Fristen ansetzen kann') concerns the inventory in its context. The condition is broader, and D20 (a demand under warning of default) is not named by 0128. The fragment alone is ambiguous.
- overlay_rule_084: D33 refers to misuse of 'card data' with a police report, while 0185 concerns misuse of SIM cards. Both times (report and misuse) are needed, so the joint route is plausible. Left as it is.
- overlay_rule_095: 'Name der Versicherungsgesellschaft' (0089) sits in form section s35 (liability insurer of the person who caused the loss), whereas the rule asks for the insured's own insurer via D03 on every claim. The cited words alone do not show this.

## Validation

`python3 ../validate.py reviewed_rules.json` reports VALID: 99 rules, 12 diff entries.
