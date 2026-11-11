# Four-eyes reconciliation of the lint review

- **Starting point:** `rule_review/final/reviewed_rules.json` (99 rules).
- **Input to both editors:** `analysis/rule_lint.md` (15 flagged conditions, one rule each).
- **Editor A:** `../editor_a/` (`LINT_REVIEW.md`, `changes.json`, `reviewed_rules.json`, cross-check of B's three proposals in `CROSS_CHECK.md`).
- **Editor B:** `../editor_b/` (same files; cross-check of A's three proposals).

A change is adopted only if both editors made it, or if one made it and the other approved it in the cross-check. Every other rule is exactly as in the starting file. The final file has 100 rules: the 99 of the starting file plus the split rule `overlay_rule_004.a`.

**Assembly:** start from editor A's `reviewed_rules.json`, restore `overlay_rule_042` from the starting file (A's narrowing was rejected by B), and take `overlay_rule_014` from editor B's `reviewed_rules.json` (B's narrowing, approved by A). Checked by comparing the parsed JSON:
- Both editors' files are identical on every rule they both made unconditional (condition and confirming evidence set to null).
- Rules 003 and 073 equal editor A's file, 014 equals editor B's file, and 042 equals the starting file.
- `overlay_rule_004.a` carries fact `overlay_rule_004.f02` unchanged (fact id, capability id, citations, D25 route), the assumption under which B approved the split.
- No other rule differs from the starting file.

**Validator:** `python3 ../../bundle/validate.py reviewed_rules.json --original ../../final/reviewed_rules.json` reports VALID: 100 rules, 24 diff lines, all from adopted changes. Against the bundle's `rules.json` (its default), it reports VALID: 100 rules, 37 diff lines, including the 13 from the earlier review.

## Flagged rules

| Rule | Editor A | Editor B | Cross-check | Decision | Deciding quotation |
|---|---|---|---|---|---|
| 001 | Condition removed | Condition removed | – | Adopted (both) | "Ist das befürchtete Ereignis eingetreten, so muss der Anspruchsberechtigte, sobald er von diesem Ereignisse und seinem Anspruche aus der Versicherung Kenntnis erlangt, das Versicherungsunternehmen benachrichtigen." (theft-source-0040) |
| 002 | Condition removed | Condition removed | – | Adopted (both) | "Bei allen Schäden im Zusammenhang mit Diebstahl oder dem Versuch dazu ist unverzüglich bei der örtlichen Polizei Anzeige zu erstatten." (theft-source-0110) |
| 003 | Narrowed: traces removed or altered, loss location or damaged items altered, repaired or disposed of, help services engaged, or such a change planned; existing but unchanged traces or items do not count | Narrowed to an equivalent text ("altered or disposed of", "assistance services", "intended") | A: "accept either wording as equivalent in substance" | Adopted (both). **A's wording**, by A's own statement that the texts are equivalent | "ohne Zustimmung der Polizei die Tatspuren nicht zu entfernen oder zu verändern" (theft-source-0043) |
| 004 | Condition removed; fact f02 (insurer's instruction, D25) split off to 004.a | Condition removed from the whole rule, f02 included | A rejects B's version and keeps the split. B approves A's split as written | Adopted: 004 (f01) unconditional (both). The split and the condition of 004.a are A's, approved by B | "Der Anspruchsberechtigte ist verpflichtet, nach Eintritt des befürchteten Ereignisses tunlichst für Minderung des Schadens zu sorgen." (theft-source-0116) |
| 004.a | New rule, fact f02 under: "After the event, measures were to be taken to reduce the loss or to preserve or rescue insured items and there was no imminent danger preventing the claimant from first obtaining the insurer's instruction, or the insurer gave instructions (Weisung / Anordnung) on measures to be taken; the occurrence of the event alone does not count." | – (f02 unconditional in B's version) | B: "approve as written" | Adopted (A, approved by B) | "Er muss, wenn nicht Gefahr im Verzug liegt, über die zu ergreifenden Massnahmen die Weisung des Versicherungsunternehmens einholen und befolgen." (theft-source-0116) |
| 005 | Condition removed | Condition removed | – | Adopted (both) | "Diebstahl: Versichert sind Schäden am Hausrat, wenn sie durch folgende Ereignisse verursacht wurden und wenn dies durch Spuren, Zeugen oder die Umstände schlüssig nachgewiesen wurde." (theft-source-0124) |
| 006 | Condition removed | Condition removed | – | Adopted (both) | "Bei Diebstahl hat der Versicherungsnehmer ferner:" (theft-source-0028) |
| 008 | Kept | Kept | – | Unchanged | "Der Versicherungsschutz gilt zu Hause, d.h. an den in der Police aufgeführten Standorten innerhalb der Schweiz." (theft-source-0149) |
| 014 | Kept (passages conflict; jurist) | Narrowed: "The insurer has asked the claimant to produce original purchase vouchers (Originalbelege) for the affected items, either by a request in the claim file or through the insurer's claim form used for this claim, which asks for them to be attached; not merely that items were damaged or stolen." | A: "approve as written" | Adopted (B, approved by A). **B's wording** | "auf Verlangen, ein Verzeichnis der vom Schaden betroffenen Sachen mit Wertangaben zu erstellen und Originalbelege beizubringen;" (theft-source-0134); "Beschädigte oder gestohlene Sachen (bitte Originalkaufbelege beilegen)" (theft-source-0176) |
| 026 | Condition removed | Condition removed | – | Adopted (both) | "bei Fahrhabe (Hausrat) der Neuwert. Das ist der Betrag, den die Neuanschaffung zum Zeitpunkt des Schadenfalles erfordert;" (theft-source-0150) |
| 042 | Narrowed: an identified person other than the policyholder is liable or caused or increased the loss through their fault; an unidentified thief does not count | Kept (whether the unidentified thief is "ein Dritter" is a legal question) | B: "reject" ("'z. B. eine Transportfirma' is an example, not a limit"; the proposal also drops the CSS precondition and adds "is liable") | **Rejected.** Rule unchanged from the starting file. A's text is kept for a sensitivity check only, in `../pending_jurist/reviewed_rules_with_042.json` (not adopted) | "Sie müssen den Rückgriff gegen Dritte (z. B. eine Transportfirma) sicherstellen, sofern der Schaden oder Verlust durch die Schuld eines Dritten entstanden oder vergrössert worden ist." (theft-source-0165) |
| 044 | Condition removed | Condition removed | – | Adopted (both) | "Die Forderungen aus dem Versicherungsvertrag verjähren unter Vorbehalt von Absatz 3 fünf Jahre nach Eintritt der Tatsache, welche die Leistungspflicht begründet." (theft-source-0131) |
| 057 | Condition removed | Condition removed | – | Adopted (both) | "Bei Diebstahl hat der Versicherungsnehmer ferner:" (theft-source-0028) |
| 061 | Condition removed | Condition removed | – | Adopted (both) | "Die Verpflichtungen aus den Versicherungen sind in der Schweiz und in schweizerischer Währung zu erfüllen." (theft-source-0074) |
| 073 | Narrowed: "The claim is made under a CSS cover whose terms list the insured theft risk as 'Diebstahl (ohne einfachen Diebstahl)', that is theft excluding simple theft; a cover that includes simple theft does not count." | Kept (wording uncheckable; jurist) | B: "approve as written" | Adopted (A, approved by B) | "Diebstahl (ohne einfachen Diebstahl)" (theft-source-0153) |
| 094 | Kept | Kept | – | Unchanged | "Die CSS Versicherung AG (nachfolgend «CSS» genannt) versichert die Gefahren von Feuer, Elementarereignissen, Erdbeben und vulkanischen Eruptionen, Wasser, Diebstahl sowie Glasbruch." (theft-source-0088) |

No adopted change departs from what both editors made or what one made and the other approved.

## Points for a jurist (both editors, merged)

1. **002 (police report on every theft).** Every cited insurer makes police notification a duty on every theft. Under CSS, however, the police report itself "kann durch die CSS einverlangt werden" (0043). Should D07 be the evidence of notification for every insurer, or for CSS only on request? (A 6, B 1; review-queue item 002.)
2. **003 (scope of the narrowed condition).**
   - VVG 0156 and CSS 0148 restrict the duty to changes "welche die Feststellung der Schadensursache oder des Schadens erschweren oder vereiteln könnte", while Simpego 0096 and Generali 0033 forbid any change. Should the condition be limited to changes that could hinder establishing the cause or amount of the loss?
   - Do mitigation or public-interest changes (for example repairing a forced door) need D26 or D27 at all?
   - Does the "help services" arm, which comes only from Simpego 0096, apply under the other insurers' terms?
   - (A 4, B 2; review-queue item 003.)
3. **004 / 004.a (insurer's instruction, D25).** Is the duty to obtain the insurer's instruction (VVG 0116) triggered in every claim, through the notification itself? Or only where mitigation, preservation or rescue measures were to be taken, as now narrowed? CSS 0170 and Simpego 0100 require only following instructions that were given. Earlier review-queue item 004 (perpetrator-identification and recovery measures after any event) is moot in a theft-only workflow. (A 3, B 3.)
4. **008 (at home).** "Zu Hause" is defined by the passages as the policy-listed locations, so read strictly the condition assumes the fact the rule is meant to test. Should it be restated as "the claim is made under the home cover (theft at the claimant's dwelling or premises), not theft away from home"? Or should the location be checked against the policy on every household-theft claim, which would make the rule unconditional? (B 4.)
5. **014 (original vouchers).** Is the claim form's printed "bitte Originalkaufbelege beilegen" (0176) a "Verlangen" in the sense of the AVB (0048/0134)? If not, drop the second limb of the narrowed condition. Does VVG 0109 ("deren Beschaffung ihm ohne erhebliche Kosten möglich ist") limit which vouchers may be demanded? (A 1, B 5; review-queue item 014.)
6. **042 (third party).** Is a thief who has not been identified "ein Dritter" whose fault caused the loss (0165)? Can claims "gegenüber Dritten" be "geltend gemacht" (0055) against such a perpetrator? If not, the condition should say "an identified third party". If so, D15 is due on every theft paid by CSS or Generali. Confirm in either case that an identified or caught thief counts. (A 5, B 6.)
7. **073 (theft cover without simple theft).** Which CSS cover does clause 26's list item "Diebstahl (ohne einfachen Diebstahl)" (0153) belong to, and is the narrowed condition literal to it? (A 2, B 7.)
8. **Insurer scope (general).** Rules 057 and 061 (CSS passages only) are now unconditional; 002 and 004 never named an insurer. Should CSS-only rules carry an "insurer is CSS" condition? (B 8; outside this lint.)
