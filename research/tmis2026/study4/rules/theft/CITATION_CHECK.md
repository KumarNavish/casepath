# Citation check: theft rule set (Study 4, step 2a, four-eyes)

Second reader: a session that did not write the rule set. Checked on 2026-11-12 against `rules.json`, `RULES.md`,
`rule_text.md`, `sources/SOURCES.json`, the snapshots, `workflow/*.json`, and the raw documents in `sources/raw/`.
I did not read `rule_review/`, the other regimes, or any analysis of earlier studies.

## What was run

- SHA-256 of the raw files equal `SOURCES.json` (css-avb `cce89481…`, css-form `adde3d2a…`, VVG XML `8b98e586…`).
- `pdftotext` (plain and `-layout`) of both PDFs, and the Fedlex XML of art. 38, 38a, 38b, 39 and 40 with the tags removed,
  using scripts in my scratch folder run with `python3 -I`. Every passage and every context passage of every rule (67
  quotations) occurs in its snapshot character for character and in the raw document. For the PDFs I compared with
  whitespace and line-break hyphens removed. I read each locator against the page layout: Ziff. 8 is on p. 3,
  Ziff. 20 lit. d and Ziff. 23 Einleitung on p. 5, Ziff. 23.3 on p. 7, Ziff. 24.2 on p. 8, Ziff. 29 lit. a on p. 11. The
  form's 3.7 is on p. 2, 3.9 on p. 3 and the declaration on p. 4. VVG art. 38 Abs. 1, 38a Abs. 1 (Satz 2) and 39 Abs. 2
  Ziff. 1 are numbered as cited. Every locator is right. The only imprecise one is the form declaration ("Abschnitt 6,
  Unterschrift, S. 4"): it stands under "Bemerkungen" on p. 4, after section 6, which ends on p. 3. That is harmless.
- `python3 -I tools/check.py` from `study4/rules/theft/`: **ALL CHECKS PASSED** (exit 0). It reports: types 2; facts 14;
  steps 16; 8 documents in the catalogue; stops 4; 11 convention presumptions; rules by basis evidence 7, follows 5,
  states 37, plus convention 1. The existing `tools/__pycache__` was not changed.
- The convention text in `rules.json` equals SPEC.md 6a's quoted block exactly (string comparison after removing the
  `>` marks and normalising whitespace). Each workflow presumption's text ends with the same words.

## Verdicts, one line per rule

Verdicts are agree, agree with change, or disagree. Rules shared by both types appear once per type, because each is a
separate entry in `rules.json`. The last line is a workflow element that has no entry in `rules.json`.

| rule id | kind | basis | verdict | reason (one sentence) | proposed wording if not agree |
|---|---|---|---|---|---|
| convention `intake_convention` | convention | convention | agree | The words equal SPEC 6a exactly. It is marked as a convention and not law (`basis: convention`, source kind `benchmark_convention`, `process_guidance` + `intended_kind` in the workflows). No workflow presumption sits on a defining event, on an `always_stated` fact, or on a fact whose false value ends a process. | (cosmetic) In `applies_to`, "a fact whose value false triggers a stop (none in this set)" should read "(none besides the defining events)". |
| **theft_at_home** / fact `theft_at_home` (defining event) | fact | states | agree with change | The passage is verbatim, but it is cut off just after "nachgewiesene", the word that governs "Schäden". The clause covers only losses "durch Spuren, Zeugen oder nach den Umständen schlüssig nachgewiesen", so a file in which things are merely gone, with nothing pointing to a theft, would still answer yes. | Quote the full sentence of Ziff. 23.3 Abs. 1. Add to `not_this`: "Items that are merely missing, where no trace, witness or circumstance points to a theft (that is open, not true)." The question can stay as it is. |
| theft_at_home / fact `household_perpetrator` | fact | states | agree with change | The passage ("Personen, die … im gleichen Haushalt leben") is rendered correctly. The `not_this` wording "a former household member who no longer lives there" leaves open the moment that counts. | `not_this`: "…a person who had moved out of the household before the theft…". Question: "…a person who lived in the same household as the policyholder at the time". |
| theft_at_home / fact `burglary_or_robbery` | fact | states (+ lit. a, b as context) | agree with change | The question renders lit. a and lit. b faithfully, and `always_stated` is right: these are two ordinary alternatives and neither is the default. The question leaves out lit. a's own exclusion ("Fahrzeuge sind keine Behältnisse"), so a car broken open in the garage could wrongly be answered yes. | Add to `not_this`: "Breaking into a vehicle: a vehicle is not a container (Ziff. 23.3 lit. a, Ausschluss)." Add that passage to the snapshot. |
| theft_at_home / fact `lock_change` | fact | states | agree with change | Lit. d is rendered correctly, but under the Ziff. 20 Einleitung cost cover only reaches costs "die durch ein versichertes Schadenereignis … entstehen". A lock change made for an unrelated reason would still answer yes. | "Does the claim include costs, caused by the theft, of changing or replacing keys, magnetic cards or locks…" Add Ziff. 20 Einleitung as context. |
| theft_at_home / fact `traces_changed` | fact | states | agree with change | The duty in lit. f falls on the policyholder ("hat der Versicherungsnehmer … nicht zu entfernen oder zu verändern"). The question also answers yes when the thief, the weather or a third party not acting for the policyholder altered the traces. | "…have been removed or altered, or are to be removed or altered, by the policyholder or on their behalf…". Add to `not_this`: "traces changed by the thief or by events outside the policyholder's control". |
| theft_at_home / fact `bicycle` | fact | states | agree | The form heading "Fahrrad (bitte Originalkaufbelege beilegen)" supports the fact. Note that it only feeds `bicycle_voucher`, which repeats what `original_vouchers` already requires for every item. | none (optional: say whether an e-bike counts; Ziff. 18 lit. g treats e-bikes up to 45 km/h like bicycles) |
| theft_at_home / fact `vouchers_unobtainable` | fact | follows | agree with change | The inference is one valid step from art. 39 Abs. 2 Ziff. 1. The fact is all-or-nothing, though, while the passage works voucher by voucher ("bestimmte Belege"). With some vouchers obtainable and some not, the answer is false, and the set then demands the unobtainable ones as well. | Keep the question for "all items". Add to `original_vouchers.must_show`: "for each item whose voucher can be obtained without considerable cost". |
| theft_at_home / fact `instruction_due` | fact | states | **disagree** | Art. 38a Abs. 1 is one condition with two parts, and the question demands that the file *state* the ordinary part (no Gefahr im Verzug). A file that only reports measures to be taken is not stated, so it is presumed false under the convention, and the duty is lost in a file to which the passage plainly applies. "Were to be taken" (past) also does not fit a duty to obtain an instruction "über die zu ergreifenden Massnahmen". | Split it in two. `measures_pending`: "Does the file state that measures to reduce the loss are still to be taken (not yet carried out)?" `imminent_danger`: "Does the file state that the measures could not wait for the insurer's instruction because of imminent danger (Gefahr im Verzug)?" The instruction step is then reached when `measures_pending`=true and `imminent_danger`=false. By 6b, true for `imminent_danger` is what the claimant raises. |
| theft_at_home / step `h_event` | step | states | agree | An unconditional check of the defining event, cited to its clause. | — |
| theft_at_home / step `h_exclusion` | step | states | agree | The exclusion stands under Ziff. 23.3 Ausschlüsse and is applied only in this type. | — |
| theft_at_home / step `h_notify` | step | states | agree | Art. 38 Abs. 1 states the duty to notify. That the step also records the policy is a title matter, and the policy has its own rule. | — |
| theft_at_home / step `h_police` | step | states | agree | Lit. f (introduced by "Bei Diebstahl hat der Versicherungsnehmer ferner") states both duties. The step is also reached for pure vandalism ("auch wenn dabei nichts entwendet wurde"), and whether "bei Diebstahl" covers that case is not plain from the text. I leave it standing. | (note) If kept, `rule_text.md` should say so explicitly. |
| theft_at_home / step `h_traces` | step | states | agree | It is reached exactly when traces are, or are to be, removed or altered, which is the condition of lit. f. | — |
| theft_at_home / step `h_instruction_check` | step | states | agree | An always-reached check of whether art. 38a's duty arises. | — |
| theft_at_home / step `h_instruction` | step | states | agree with change | The passage is right. Its condition inherits the defect of `instruction_due`, and "obtain and follow" fits only measures still to be taken. | `reached_when`: `measures_pending`=true and `imminent_danger`=false (see `instruction_due`). |
| theft_at_home / step `h_loss` | step | states | agree | Ziff. 29 lit. a puts the proof of the amount on the policyholder. | — |
| theft_at_home / document `claim_form` | document | evidence | agree with change | The form proves notification, but it is not the only document that does. Art. 38 Abs. 1 Satz 2 lets the contract demand written notice; CSS does not (AVB Ziff. 4: with no form requirement "kann diese auch mündlich erfolgen"). The form itself offers "Alternativ … online unter css.ch/schaden melden". The signature item in `must_show` comes from the form's wording, not from art. 38. | Title: "Record of the claim notification: the CSS form 'Schadenanzeige Hausrat / Gebäude', or CSS's record of an online, written or telephone notification". `must_show`: "that and when CSS was notified of the theft". Move the signature to an optional item, or cite the form declaration as a separate basis. |
| theft_at_home / document `insurance_policy` | document | evidence | agree | Ziff. 23 Einleitung makes cover depend on the peril being "in der Police aufgeführt", so the policy is the proving document, and it also names the insured location (Ziff. 26 lit. a). | — |
| theft_at_home / document `police_report` | document | states | agree | "Kann durch die CSS einverlangt werden" is correctly encoded as needed, not mandatory: the report is due only when CSS asks. | (note) `rule_text.md` already says "only if CSS asks for it". |
| theft_at_home / document `police_consent` | document | evidence | agree with change | Lit. f makes consent the condition. The inference that a "written confirmation" is what ordinarily proves it imports practice from outside the text: police consent at the scene is usually oral, and the cited text names no consent document. The police report, which CSS may request, is the document lit. f itself names. | Inference: "…the police report (which CSS may request, lit. f) or a written police confirmation is the document that can show the consent." Keep it mandatory only if either one counts. |
| theft_at_home / document `stolen_items_list` | document | states | agree with change | "Auf Verlangen" is correctly encoded as not mandatory. However, the claim form's section 3.7 is itself a valued list (Gegenstand / Gekauft bei / Kaufdatum / Ersatzwert, or "Gemäss separater Liste"), so a file with the form already contains the list. Under the same "auf Verlangen" in lit. c the set treats the vouchers as requested by the form but the list as not requested. | Either state that the form's section 3.7 or a separate list satisfies this document, or treat the list as requested by the form exactly as the vouchers are. |
| theft_at_home / document `original_vouchers` | document | states (+ VVG 39 Abs. 2 Ziff. 1 as context) | agree with change | The duty to produce original vouchers is contractual: Ziff. 8 lit. c says "auf Verlangen … Originalbelege beizubringen", and art. 39 Abs. 2 Ziff. 1 speaks of what "der Vertrag" may require. The form's "bitte … beilegen" is CSS's request, not the contract, and a notification made online may never carry it. | Rule passage: Ziff. 8 lit. c ("auf Verlangen, … Originalbelege beizubringen"), with the form 3.7 request as context. Inference: "CSS requests them in its claim form". Add the per-item limit to `must_show` (see `vouchers_unobtainable`). |
| theft_at_home / document `bicycle_voucher` | document | states | agree | The form 3.9 heading states the request. The document duplicates `original_vouchers` for an item that is already among the 3.7 items, which is harmless. | — |
| theft_at_home / document `lock_change_invoice` | document | evidence | agree | The invoice ordinarily proves the "effektive Kosten" (Ziff. 29 lit. a puts the proof on the policyholder). Limiting it to burglary or robbery follows from lit. d's own exclusion "Kosten bei einfachem Diebstahl". | (follows the `lock_change` causation fix) |
| theft_at_home / stop `h_stop_no_event` | stop | follows | agree | Ending this claim type when the defining event is stated false is one step from the clause. The stop says "this claim type does not apply", not "no cover", which is correct. | (note) See finding 5 on burglary and robbery away from home. |
| theft_at_home / stop `h_stop_excluded` | stop | states | agree | The exclusion states that such damage is not insured. The stop needs a stated true value, and silence does not end the process. | — |
| **simple_theft_away** / fact `theft_away` (defining event) | fact | states (+ 23.3 lit. a, b as context) | agree with change | The rendering of 24.2 is faithful, but there are two slips. (a) 24.2 covers "Schäden am Hausrat durch Diebstahl", and the question asks only whether things were "stolen", so items damaged in a theft away are missed. (b) Without lit. a's exclusion "Fahrzeuge sind keine Behältnisse", a theft from a car broken into away from home may be read as burglary and answered no, which wrongly ends this type. | "…household contents were stolen or damaged by a theft outside the insured location that was neither a burglary … nor a robbery…". Add to `not_this`: "Breaking into a vehicle is not a burglary (a vehicle is not a container), and pickpocketing or trick theft is not a robbery: both are simple thefts." |
| simple_theft_away / fact `away_cover_missing` | fact | states | agree with change | Under 6b, "missing" is a circumstance the insurer would raise, so the letter is met. But the supplementary cover is an option ("sofern … gewünscht und in der Police aufgeführt", Ziff. 24 Einleitung), so neither value is the ordinary case. A claimant's narrative will rarely state it; it is settled by the policy. The convention presumption (cover exists) has no text behind it. | Mark it `always_stated: true` (no presumption; the generator states it, for instance through the attached policy, or leaves it open). Cite Ziff. 24 Einleitung, which states the condition directly, beside 23.3 lit. c. |
| simple_theft_away / fact `traces_changed` | fact | states | agree with change | The same as in type 1: the duty is the policyholder's. | The same wording as in type 1. |
| simple_theft_away / fact `bicycle` | fact | states | agree | As in type 1. | — |
| simple_theft_away / fact `vouchers_unobtainable` | fact | follows | agree with change | As in type 1: the passage works per voucher. | As in type 1. |
| simple_theft_away / fact `instruction_due` | fact | states | **disagree** | As in type 1: the conjunctive question demands that the ordinary part be stated. | Split into `measures_pending` and `imminent_danger`, as in type 1. |
| simple_theft_away / step `a_event` | step | states | agree | An unconditional check of the defining event. | — |
| simple_theft_away / step `a_cover` | step | states | agree | Lit. c states that a separate supplementary insurance is needed. | (optional) Add Ziff. 24 Einleitung as context. |
| simple_theft_away / step `a_notify` | step | states | agree | As in type 1. | — |
| simple_theft_away / step `a_police` | step | states | agree | "Bei Diebstahl" plainly covers a simple theft away. | — |
| simple_theft_away / step `a_traces` | step | states | agree | As in type 1. | — |
| simple_theft_away / step `a_instruction_check` | step | states | agree | As in type 1. | — |
| simple_theft_away / step `a_instruction` | step | states | agree with change | As in type 1. | As in type 1. |
| simple_theft_away / step `a_loss` | step | states | agree | As in type 1. | — |
| simple_theft_away / document `claim_form` | document | evidence | agree with change | As in type 1: oral or online notice is allowed (AVB Ziff. 4; the form's own online alternative). | As in type 1. |
| simple_theft_away / document `insurance_policy` | document | evidence | agree with change | The policy is the right proof. Ziff. 24 Einleitung ("sofern … in der Police aufgeführt") states that the supplementary cover must be listed, and it is a better passage than 24.2's sum-insured phrase. | Add Ziff. 24 Einleitung as the passage, or as context. `must_show` may add "the insured location" so that "outside the insured location" can be checked. |
| simple_theft_away / document `police_report` | document | states | agree | As in type 1. | — |
| simple_theft_away / document `police_consent` | document | evidence | agree with change | As in type 1. | As in type 1. |
| simple_theft_away / document `stolen_items_list` | document | states | agree with change | As in type 1. | As in type 1. |
| simple_theft_away / document `original_vouchers` | document | states (+ VVG context) | agree with change | As in type 1. | As in type 1. |
| simple_theft_away / document `bicycle_voucher` | document | states | agree | As in type 1. | — |
| simple_theft_away / stop `a_stop_no_event` | stop | follows | agree | The type is scoped to 24.2, and "this claim type does not apply" is correct. | (note) See finding 5. |
| simple_theft_away / stop `a_stop_no_cover` | stop | follows | agree | "Ist eine separate Zusatzversicherung abzuschliessen" means, in one step, that without it there is no cover for simple theft away. It is triggered only by a stated true value. | (optional) Add Ziff. 24 Einleitung as context. |
| workflow-only: fact `claim_type` (enum; `applies_when` of both workflows) | fact (routing) | none in `rules.json` | agree with change | It routes files and carries `source_refs` (23.3 Abs. 1, 24.2), but it is not in `rules.json` or `rule_text.md`, has no passage entry, and does not say what "other" covers. | List it in `rules.json` with both passages and the `not_this` "burglary or robbery away from home (Ziff. 26 lit. b) and any other peril: other". Mention it in `rule_text.md`. |

## Specific questions of the brief

- **Defining event of `theft_at_home`.** The passage is a verbatim substring, but it begins after "schlüssig
  nachgewiesene", so the quoted words read as an unconditional event. I accept the writer's reason for keeping proof
  out of the intake condition: traces are only one of three alternative means of proof, and the circumstances alone can
  suffice. The quotation should still be the whole sentence. The case of "simply gone, nothing points to theft" should
  be open, not true, together with the exclusion "Verlieren, Verlegen … Veruntreuung" that `not_this` already names.
- **`traces_changed` / `police_consent`.** The condition is right (removal or alteration, done or intended, and not the
  mere existence of traces). It is too broad about who made the change. The proving document is inferred from practice,
  not from the text (see the table).
- **`instruction_due`.** Disagree, as explained in the table.
- **Police report "only on the insurer's request".** `needed_when: true, mandatory: false` and the prose "only if CSS
  asks for it (not mandatory)" render "kann … einverlangt werden" correctly. Notifying the police is a duty, but no
  mandatory document proves it. The claim form's section 4 "Polizeimeldung" (Anzeigedatum, Polizeiposten,
  Polizeibeamter) records it, and the set does not use that section.
- **Original vouchers and art. 39 Abs. 2 Ziff. 1.** The limit "ohne erhebliche Kosten" is correctly turned into a fact
  with the right polarity. Two weaknesses: the limit applies per voucher, and the mandatory need rests on the form's
  request rather than on the contract clause (Ziff. 8 lit. c, "auf Verlangen") that art. 39 refers to.
- **Polarity.** `burglary_or_robbery` as `always_stated` is sound. For `away_cover_missing`, a claimant's file can
  rarely state it; it is answered by the policy, and its convention presumption amounts to presuming cover. I recommend
  `always_stated`.
- **One insurer only.** No CSS clause is applied outside its own contract, and no other insurer's text is used. The
  household exclusion stands only under 23.3 and is correctly not applied to 24.2. The lock-change cost (Ziff. 20,
  "am versicherten Standort") is correctly applied only at home. One mix the texts do not quite support:
  art. 39 Abs. 2 Ziff. 1 limits what the *contract* may require, but here it is attached to a request in the claim form
  (see `original_vouchers`).
- **`rule_text.md` against `rules.json`.** The facts, steps, documents, stops and convention match one for one. The
  differences are omissions only, and none adds or tilts:
  1. the inference of the one `follows` fact (`vouchers_unobtainable`) is not printed, while the inferences of stops and
     evidence documents are;
  2. the context passages are not printed (the lit. a and b definitions are paraphrased in the questions, which is
     enough);
  3. the routing fact `claim_type` and what falls outside both types are not mentioned;
  4. `police_consent` and the other step-bound documents read "needed when always", which is correct only together with
     the step condition printed above them.

## Omissions within the cited clauses and articles (most important first)

1. **Art. 38 Abs. 1 Satz 2 together with AVB Ziff. 4 and the form's online alternative.** The written form of the
   notification is not required by CSS, so a mandatory signed claim form says more than the texts. Fix: `claim_form`.
2. **Ziff. 23.3 lit. a, Ausschluss ("Fahrzeuge sind keine Behältnisse"), and lit. b, Ausschluss (Taschen- und
   Trickdiebstahl).** Both change how `burglary_or_robbery` and `theft_away` are answered, and neither is in the
   snapshot.
3. **The proof clause of Ziff. 23.3 Abs. 1.** It was cut from the quoted passage (see the table).
4. **Ziff. 24 Einleitung ("sofern … gewünscht und in der Police aufgeführt").** This is the direct text for
   `away_cover_missing`, `a_cover`, `a_stop_no_cover` and `insurance_policy` (type 2); 23.3 lit. c is only indirect.
5. **Ziff. 20 Einleitung.** Cost cover only for costs caused by an insured event at the insured location, which is
   missing from the `lock_change` question.
6. **Claim form section 4 "Polizeimeldung".** The form itself records the police notification (date, station,
   officer). It would be the ordinary proof for `h_police`, and the set leaves that step without one.
7. **Ziff. 8 lit. c, first half.** "die für die Begründung … nötigen Angaben zu machen" is unconditional, while the
   list and vouchers are "auf Verlangen". The set treats the list and the vouchers differently under the same words.
8. **VVG art. 38b / Ziff. 8 lit. e (changes to damaged items).** Leaving these out is consistent with the texts: neither
   names a document, lit. e names no consent, and the art. 38b consent is the insurer's own act.
9. **Ziff. 15 (claims against third parties).** Leaving it out is consistent: its condition is that CSS "Leistungen
   erbracht hat", and it names no document.
10. **Ziff. 8 lit. b, g, h and VVG art. 39 Abs. 1 / Abs. 2 Ziff. 2.** Information and cooperation duties, and a deadline
    that starts only on a written demand. Leaving them out is consistent: none names a document for intake.

No cited clause plainly requires a document that the set ignores. The nearest case is item 6, a proof that the set
leaves unused rather than a document a clause requires.

## Counts

| kind | agree | agree with change | disagree | total |
|---|---|---|---|---|
| fact (rules.json) | 2 | 10 | 2 | 14 |
| step | 14 | 2 | 0 | 16 |
| document | 6 | 9 | 0 | 15 |
| stop | 4 | 0 | 0 | 4 |
| convention | 1 | 0 | 0 | 1 |
| **total, rules.json** | **27** | **21** | **2** | **50** |
| workflow-only `claim_type` | 0 | 1 | 0 | 1 |

All 67 quoted passages are verbatim in the snapshot and in the source document, and every locator is right.

## The five findings that matter most

1. **`instruction_due` (both types): disagree.** The question joins "measures to be taken" with the ordinary "no
   imminent danger" and requires the file to state both. Under the convention, a file that reports pending measures
   and is silent about danger is presumed false, which drops art. 38a's duty where it plainly applies. Split it into
   `measures_pending` and `imminent_danger`.
2. **`claim_form` mandatory as "completed and signed".** The duty in art. 38 Abs. 1 is to notify. CSS imposes no form
   (AVB Ziff. 4: oral notice is enough), and its own form offers online notification. The document should be any
   record of the notification, and the signature item should not rest on art. 38.
3. **Vouchers.** The mandatory need is grounded in the form's "bitte … beilegen", not in the contract clause
   (Ziff. 8 lit. c, "auf Verlangen") that art. 39 Abs. 2 Ziff. 1 refers to. The art. 39 limit is all-or-nothing instead
   of per voucher. The valued list, under the same "auf Verlangen" and itself part of form 3.7, is treated
   inconsistently.
4. **The defining events have cut or incomplete text.** The `theft_at_home` passage begins after the word that
   qualifies "Schäden" (the proof clause). Both definitions lack lit. a's "Fahrzeuge sind keine Behältnisse" (and
   lit. b's pickpocket exclusion), so a theft from a car broken into away from home can wrongly stop the away type.
5. **Scope and polarity of type 2.** `away_cover_missing` is settled by the policy, not by a claimant's story; its
   convention presumption presumes cover, and it should be `always_stated` with Ziff. 24 Einleitung cited. Burglary or
   robbery away from home (Ziff. 26 lit. b, basic cover) falls outside both types and both stops. The stops correctly
   say "this claim type does not apply", but `rule_text.md` never says such claims are outside the rules, and the
   routing fact `claim_type` has no entry in `rules.json`.

## Can a reader without legal training verify this rule set?

Mostly yes. With the Fedlex text of the Act and CSS's AVB and claim form open, a careful lay reader can find every
quoted passage at its stated article, paragraph, clause and page. They can also confirm that each step, stop and
document need follows the quoted words, and that the convention is labelled as a convention.

They could not settle, from the text alone:

- whether a given set of facts is "Gefahr im Verzug" (art. 38a);
- whether a voucher can be obtained "ohne erhebliche Kosten" (art. 39 Abs. 2 Ziff. 1);
- whether "bei Diebstahl" in Ziff. 8 also covers pure vandalism under 23.3;
- whether the form's "bitte … beilegen" counts as CSS's "Verlangen" under Ziff. 8 lit. c, and as the "Vertrag" under
  art. 39;
- what "ordinarily proves" a condition for the `evidence` documents: police consent in particular rests on knowledge
  of practice that the texts do not contain;
- edge cases of burglary versus simple theft (keys, vehicles, containers) beyond the definitions in lit. a to c.

Those are the places where the rule set's wording should carry the decision (as proposed above) rather than leave it
to the reader.

## Second look (2026-11-12)

I read `RECONCILIATION.md` and the rebuilt `rules.json`, `RULES.md` (the sections on what was settled and what was left
out), `rule_text.md`, the snapshots and the workflows. Same rules as the first check: no model calls, no network, and
only this file edited.

What I ran:

- `python3 -I tools/check.py`: **ALL CHECKS PASSED** (exit 0). It reports: facts 16 (9 + 7); steps 16; documents
  8 in the catalogue; stops 4; 12 convention presumptions (none on `theft_at_home`, `theft_away`,
  `burglary_or_robbery` or `away_cover_missing`); rules by basis evidence 7, follows 11, states 33, plus convention 1.
  It also notes that theft_at_home now has 9 facts, one more than the product's limit of 8 open facts for exact
  deferral.
- My own scripts re-checked all 114 quotations, including context passages and the routing entry. Every one is found
  in its snapshot character for character and in the raw PDF or Fedlex XML. None is longer than 60 words.
- The new locators are right against the page layout: Ziff. 4 on S. 2, Ziff. 20 Einleitung on S. 4, Ziff. 24
  Einleitung on S. 8, Ziff. 26 lit. b on S. 10. The form's online sentence is on S. 1, section 3.7 on S. 2 and
  section 4 on S. 3.
- A script comparison shows that every question, `not_this`, title, `must_show` item, passage, inference, context
  passage, note, `reading_of_optional` and `outside_both_types` text in `rules.json` occurs verbatim in
  `rule_text.md`, with no misses. `reading_of_optional` is word for word the same in both files.

### 1. My earlier points

| earlier point | status | remaining wording, if any |
|---|---|---|
| `theft_at_home` defining event (passage cut before "nachgewiesene") | resolved | The full sentence is quoted; "merely missing" is answered open. |
| `household_perpetrator` (the moment that counts) | resolved | — |
| `burglary_or_robbery` (vehicle is not a container) | resolved | — (lit. b's pickpocket exclusion is also added; see note A) |
| `lock_change` (caused by the theft) | resolved | — |
| `traces_changed` ×2 (the policyholder's duty) | resolved | — |
| `vouchers_unobtainable` ×2 (limit per voucher) | resolved | "for all of the items", and the per-voucher limit moved into `original_vouchers.must_show`. |
| `instruction_due` ×2 (disagree) | resolved | Split into `measures_pending` and `imminent_danger` (see 2a). |
| `h_instruction`, `a_instruction` | resolved | — |
| `claim_form` ×2 | resolved | Now `notification_record`; the signature item is gone. |
| `police_consent` ×2 | resolved | — |
| `stolen_items_list` ×2 | resolved | Now on lit. c, requested at intake (see 2c). |
| `original_vouchers` ×2 | resolved | Now on lit. c, with the form as the request and the limit per voucher. |
| `theft_away` (damaged items; vehicle and pickpocket) | resolved | — |
| `away_cover_missing` (polarity) | resolved | Now `always_stated`, on Ziff. 24 Einleitung. |
| `insurance_policy` (type 2) | resolved | Ziff. 24 Einleitung, the insured location, and moved to `a_cover`. |
| workflow-only `claim_type` | resolved | Now a `routing` entry, printed in `rule_text.md`. |
| notes: convention `applies_to`, `h_police` vandalism, `a_cover`/`a_stop_no_cover` passage, form section 4, the four `rule_text.md` omissions | resolved | — |
| optional note: e-bike | not taken by the writer | I accept that (see 3). |

**Totals:** of the 24 non-agree items (21 agree with change, 2 disagree, 1 workflow-only), 24 are resolved and 0 are
not. All the notes are resolved too, except the optional e-bike note, which I withdraw.

### 2. The new rules under the nine tests

**a. `measures_pending` and `imminent_danger` (both types): agree.** The verdicts stand on these points:

- Art. 38a Abs. 1 Satz 2 is now two facts with the right polarity. True for `imminent_danger` is the exception the
  claimant raises.
- When the file says nothing about danger, the convention takes it as absent. That matches the article's own
  structure: there is a duty "wenn nicht Gefahr im Verzug liegt".
- No stop and no document hangs on either fact. The check confirms that an unmentioned value creates no document need.

Note B: `measures_pending` covers only measures still to be taken. Measures already taken without an instruction raise
a question of breach under Abs. 2, not an intake step. The step "obtain and follow the instruction" can only concern
pending measures, so I do not count this narrowing as a defect.

**b. `notification_record` (both types): agree.** The record covers any notice: the form, or CSS's record of an
online, written or oral notification. The citations are art. 38 Abs. 1, Ziff. 8 lit. a and Ziff. 4 ("kann diese auch
mündlich erfolgen"), and the form's "Alternativ … online … melden". `must_show` asks only that and when CSS was
notified. The evidence inference no longer imports anything from outside the text.

**c. Vouchers, the valued list and the police report: agree, and the reading is sound on the texts.**

- *Vouchers and list.* Both are due "auf Verlangen" (Ziff. 8 lit. c), and the handler is CSS. CSS's own claim form
  makes the request for every item:
  - section 3.7 says "bitte Originalkaufbelege beilegen";
  - its columns Gegenstand / Gekauft bei / Kaufdatum / Ersatzwert, or "Gemäss separater Liste", are the valued list.

  So treating both as requested at intake is one valid step from the passages, and lit. c now governs them equally.
  The list's `must_show` item "where and when it was bought" comes from the form's columns, which are cited as context,
  so it is grounded.
- *Police report.* "Kann durch die CSS einverlangt werden" leaves the request to CSS, and no CSS document makes it at
  intake: form section 4 asks only for the report's particulars (Anzeigedatum, Polizeiposten). So the report is "not
  needed unless the file contains it" ("optional"), and its absence is never a gap. That is a faithful reading.
- *Remaining dependency.* `police_consent` stays mandatory when traces are changed, and the police report is one of its
  two acceptable forms. That is consistent: the clause names the report, and either form satisfies the need.
- *Consistency between files.* `reading_of_optional` is stated identically in `rules.json` and in `rule_text.md`
  ("Documents requested at intake and documents only on request"), and every document line in the prose says "not
  requested at intake; only if CSS asks for it later (optional)".

**d. Full defining events with the exclusions: agree.**

- Ziff. 23.3 Abs. 1 is quoted whole. "Merely missing" is answered open, consistent with the exclusion "Verlieren,
  Verlegen … Veruntreuung", which is now cited as context.
- "Fahrzeuge sind keine Behältnisse" is stated by the text itself.
- `theft_away` now reads "stolen or damaged".

Note A: rendering lit. b's exclusion "Schäden, verursacht durch Taschen- und Trickdiebstahl" as "pickpocketing and
trick theft are not robbery, so they are simple thefts" is an inference, not a sentence of the text. The exclusion
sits under the robbery definition and has no defining sentence of its own. I accept it as the natural one-step reading:
it denies robbery status, and lit. c defines simple theft as whatever is neither burglary nor robbery. Ziff. 24.2 does
not repeat that exclusion, so a pickpocket theft away from home falls under type 2. This is the one place where a lay
reader has to accept the step rather than read it off the page.

**e. `away_cover_missing` as `always_stated` on the Ziff. 24 Einleitung, with the policy at `a_cover`: agree.**

- The fact has no presumption. When it is unmentioned it is unresolved, and the policy, requested as soon as a simple
  theft away is stated, settles it.
- The stop needs the value true. Silence does not end the process.
- Ziff. 24 Einleitung states the condition directly, and 23.3 lit. c is kept as context.

**f. `claim_type` routing and "outside both types": agree.**

- The passages (Ziff. 23.3 Abs. 1, 24.2, and 26 lit. b, which covers "Diebstahl (ohne einfachen Diebstahl)" only
  during travel and only "vorübergehend") support the statement that burglary or robbery away from home is outside
  both types and is covered, "if at all", under the basic cover.
- The vehicle example placed in type 2 follows from lit. a.
- Note C (wording only): the "holiday flat" example in `outside_both_types` sits close to Ziff. 26 lit. b's own
  exclusion of contents kept permanently in a holiday flat or second home. "If at all" covers it, but "a hotel room or
  a rented holiday flat during a trip" would be the cleaner example. This is not a disagreement.

Tests 1 (verbatim and locator), 6 (convention), 8 (one insurer, no mixing) and 9 (prose equals rules) pass for every
new or changed rule. Art. 39 Abs. 2 Ziff. 1 is now attached to the contract clause lit. c, not to the form, which
removes the mix I raised earlier.

### 3. The e-bike note

I agree with leaving it undecided. The fact's source is the form heading "Fahrrad", and the form offers only
"Herren-/Damenfahrrad" and "Kinderfahrrad". Ziff. 18 lit. g ("Fahrräder und E-Bikes …") defines insured items, not
the form's request, so any decision either way would be imported. To keep the reference unambiguous, I recommend that
the generator not draw e-bikes, or treat a stated e-bike as making `bicycle` open. This is a recommendation for the
generator, not a defect in the rules.

### 4. Still not agreed

None. All rules of the rebuilt set are agree. Notes A to C are observations and need no change.

The theft rule set is ready to be marked reviewed. The 4-eyes record is `CITATION_CHECK.md` (first check and this
second look) together with `RECONCILIATION.md`.

## Second look, revisions 1 and 2 (2026-11-12)

Second reader; I did not write either revision. Read: SPEC.md items 1 to 7 (with 6a, 6b, 6c), the two revision sections of
`RECONCILIATION.md`, `generator/items/theft.json`, and the snapshots `sources/css-avb.txt`, `sources/css-form.txt` and
`sources/vvg.txt` (not `sources/raw/`). Checks run:

- Field-by-field diff of `rev0/rules.json` -> `rev1/rules.json` -> `rules.json`, of both workflows at the same three
  states, and word-level diffs of `rule_text.md`. Every change found is listed. The four `source_refs` added to
  `claim_type` in the workflows are the four context passages that H1 names. No unlisted change.
- With question, `not_this`, title, `must_show` and the routing `context` masked, `rules.json` and both workflows are
  equal to `rev0/`. No fact id, step, `needed_when`, `mandatory`, stop, `source_id`, locator, passage, basis or
  inference changed. The convention text is SPEC 6a's, character for character, in `rules.json` and `rule_text.md`.
  All hashes match the recorded ones.
- Every quoted passage is in the stored snapshot, character for character, and its locator matches the snapshot's
  label (Ziff. 23.3 lit. a Ausschluss, lit. b Ausschluss, Ziff. 23.3 Ausschlüsse erster Strich, Ziff. 24 Einleitung,
  Ziff. 24.2, Ziff. 8 lit. c, Abschnitt 3.7 Spalten, Abschnitt 3.9, VVG Art. 38 Abs. 1, Art. 38a Abs. 1, Art. 39 Abs. 2
  Ziff. 1).
- `python3 -I -B rules/theft/tools/check.py`: ALL CHECKS PASSED (6c: 37 items, 0 conditional); the tree was unchanged.
- `lint/verify_rev2.py` was **not run**: it writes `lint/VERIFY_REV2.json`. I read the stored report only.

### Revision 1

- R1-1 `routing.not_this` (claim_type), added sentences: **agree**. (i) "Breaking into a vehicle is not a burglary (a vehicle is not a container)": Ziff. 23.3 lit. a defines burglary by a building, a room of it or a container, and its Ausschluss says "Fahrzeuge sind keine Behältnisse". (ii) "pickpocketing or trick theft is not a robbery": Ziff. 23.3 lit. b Ausschluss places "Taschen- und Trickdiebstahl" outside robbery. (iii) Such a theft away from the insured location is therefore theft "der weder als Einbruchdiebstahl noch als Beraubung gilt und sich ausserhalb des versicherten Standortes ereignet" (Ziff. 24.2), which is the defining event of `simple_theft_away`. The classification follows step by step from the cited text and moves nothing into a type its defining event does not cover. A burglary or robbery away from home stays "other". (iv) "cover and exclusions decided inside the type": Ziff. 24 Einleitung ("in der Police aufgeführt") is decided by `away_cover_missing` and its stop, and the household exclusion by `household_perpetrator` and its stop in `theft_at_home`. The household thief is given "for example". `simple_theft_away` has no household fact, so there the sentence only says that routing does not decide it, which is true. Routing cannot become narrower than the types.
- R1-2 `household_perpetrator` `not_this`, added "A thief the file only calls unknown or unidentified, with nothing in the file pointing to a member of the household, does not raise this question.": **agree**. The exclusion (Ziff. 23.3 Ausschlüsse, erster Strich) needs a thief who lives in the household. "Täterschaft unbekannt" does not state or suggest that, so under 6a the fact is unmentioned. A suspicion that points to a household member still makes the fact open, and false does not trigger a stop (6b).
- R1-3 `measures_pending` `not_this` (both types): "or recover the items" dropped; steps to get the items back or to stop their use or sale count as measures: **agree**. VVG Art. 38a Abs. 1 ("tunlichst für Minderung des Schadens zu sorgen") draws no line between getting the stolen items back and other ways of reducing the loss, and recovering an item reduces the insured loss directly. Ziff. 8 lit. d of the same snapshot ("für die Erhaltung und Rettung der versicherten Sachen und für die Minderung des Schadens") supports it further; it could be cited as `also`, but that is not needed. The old exclusion had no passage. "Steps only to find the thief" stays excluded, which is no narrower than the passage, since finding the thief does not by itself reduce the loss.

### Revision 2 (must_show)

- R2-1 `notification_record` (both types) "the date (day, month and year) on which the theft was notified to CSS": **agree**. VVG Art. 38 Abs. 1 ("sobald ...") makes the time of notice the point, and a dated record of notice to CSS is what proves it. "That" is implied by a date of notification to CSS. One visible thing.
- R2-2 `insurance_policy` (away) "the supplementary insurance for simple theft away (Ziff. 24.2), listed among the policy's covers as included or as not included": **disagree**. Ziff. 24 Einleitung insures a supplementary cover only "sofern ... in der Police aufgeführt": a cover that is **not** listed is not insured. A policy whose complete list of covers leaves out Ziff. 24.2 therefore shows, by the cited text, that the cover was not taken. The new item would call that policy insufficient and request it again, because it asks for an explicit "not included" entry that the clause does not require. The fix of "or its absence" is right in aim (a policy extract that is silent must not count), but the visible thing should be the complete list. I would accept: "the complete list of the covers included in the policy (the supplementary insurance for simple theft away, Ziff. 24.2, is insured only if it is on that list)". The generator's `checkable_as` ("A cover list that is silent about it does not show this item") would change to match.
- R2-3 `stolen_items_list` (both types) "for each item, where and when it was bought, or, for an item that was not bought, that it was a gift or inherited and when": **disagree, narrowly**. Extending the form's columns "Gekauft bei / Kaufdatum" (Abschnitt 3.7) to items that were not bought is a sound inference. But naming only "a gift or inherited" makes the item impossible to show for an item acquired some other way (won, made, received in an exchange or with a job). That is the same defect the change sets out to fix, and nothing in Ziff. 8 lit. c ("Verzeichnis ... mit Wertangaben") limits it to two ways. I would accept: "for each item, where and when it was bought, or, for an item that was not bought, how and when it was acquired (for example as a gift or by inheritance)".
- R2-4 `original_vouchers` (both types) "an original purchase voucher for each stolen or damaged item, except an item for which the file states that its voucher cannot be obtained without considerable cost": **agree**. Ziff. 8 lit. c, limited voucher by voucher by VVG Art. 39 Abs. 2 Ziff. 1. Under 6a an unstated difficulty is not alleged, so the exception turns on what the file states. Note: a gift or an heirloom is excepted only where the file states that its voucher cannot be obtained. That is what Art. 39 gives (a gift's receipt may be obtainable from the giver), so the earlier gift problem is solved by R2-3, not here.
- R2-5 `bicycle_voucher` (both types) "the bicycle it is for (make, model or type)": **agree**. The old "if" clause was the need condition, already in `needed_when` (`bicycle`, `vouchers_unobtainable`), so moving it out follows 6c. A voucher requested under Abschnitt 3.9 must identify the bicycle, and "make, model or type" is satisfied by any such description.

### Considered and not changed

- (b) `insurance_policy` (away) "its sum insured" against Ziff. 24.2. Ruling: **the sum that matters is the one agreed for simple theft away**. Ziff. 24.2 insures such theft "bis zu der in der Police vereinbarten Versicherungssumme", inside the supplementary cover. The document rule's own inference says the policy shows whether the supplementary insurance was agreed and "for which sum". The household-contents sum that the generator's `checkable_as` asks for is a different figure and does not show the limit of this cover. "Its" is ambiguous and should be made explicit. Because a policy that lists the cover as not included has no such sum (and the stop applies), the item is conditional. I would accept: "Only if the file states that the policy includes the supplementary insurance for simple theft away (Ziff. 24.2): the sum insured agreed for that cover. Otherwise this item does not apply." The attached policy is part of the file, so a policy listing the cover meets the condition. The generator note would change to match.
- `police_report` "that the theft was reported to the police and when" and `police_consent` "that the police consented": agree to keep; both are statements visible on the police document.
- `original_vouchers` and `bicycle_voucher` "where and when ... was bought": agree to keep; a purchase voucher records a purchase.
