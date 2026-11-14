# Areas: the handler's process for any case

Every legal-protection case runs the same chain of handler actions (A1 first request … A12 closing), the same six stages, the same clock and Protekta's letter forms. That part is the **backbone**, `casepath/process/areas/backbone.json`. What differs by legal area is small, and it is one **area module** per file next to it: the routing value, the facts with their customer questions, the documents with their legal reason, first hints, statutory deadlines, the legal frame of the assessment (A5) and of the letter to the other side (A8), and the law it cites. At load, `casepath/process/area.py` composes backbone + module into an ordinary workflow, so routing, evaluation, items and letters do not know the difference.

Shipped, by the routing value `rechtsgebiet` that selects each:

| Module | Routing value | Source |
|---|---|---|
| `mietmangel-handler` | Mietrecht / Mangel | practice and law |
| `miete-kuendigung` | Mietrecht / Kündigung | law |
| `miete-mietzinserhoehung` | Mietrecht / Mietzinserhöhung | law |
| `miete-kaution` | Mietrecht / Kaution und Rückgabe | law |
| `arbeit-kuendigung` | Arbeitsrecht / Kündigung | law |
| `arbeit-lohn` | Arbeitsrecht / Lohn | law |
| `arbeit-zeugnis` | Arbeitsrecht / Arbeitszeugnis | law |
| `vertrag-darlehen` | Vertragsrecht / Darlehen | law |
| `vertrag-kauf` | Vertragsrecht / Kauf mit Mangel | law |
| `werkvertrag-bau` | Vertragsrecht / Werkvertrag (Handwerker, Bau) | law |
| `schaden-unfall` | Schadenersatzrecht / Unfall, Personen- oder Sachschaden | law |
| `erbrecht` | Erbrecht / Ausschlagung, Pflichtteil | law |
| `nachbarrecht` | Nachbarrecht / Einwirkungen, Pflanzen, Grenzen | law |
| `inkasso` | Inkasso-Rechtsschutz / offene Forderung der Kundschaft | law |
| `verkehr` | Strafrecht, Ausweisentzug / Strassenverkehr | law |
| `sozialversicherung` | Sozialversicherungsrecht / Verfügung, Einsprache, Beschwerde | law |
| `privatversicherung` | Privatversicherungsrecht / Leistung der Versicherung | law |
| `betreibung-schuldner` | Schuldbetreibungs- und Konkursrecht / Zahlungsbefehl gegen die Kundschaft | law |
| `allgemein` | Übriges Recht, or nothing established (fallback) | law |

All are `draft`; those from the law alone are shown as «aus dem Gesetz abgeleitet, noch nicht freigegeben». Every area also carries the cover points, their facts and the prescribed letters of `areas/cover.json` (docs/COVER.md); `cover.json` names, per area, the date that stands for the cause of the case (`cause_from`) and the clauses of the conditions for its capacity, legal area and limits (`areas`).

## Add or change an area

Copy the smallest module (`arbeit-zeugnis.json`), change it, check it:

```sh
python -m casepath areas casepath/process/areas/my-area.json      # validates and prints what it contains
python -m casepath areas --law 220=or.html 210=zgb.html            # every passage against the official text (fedlex filestore HTML)
python -m casepath areas --sources <folder>                          # every passage of the backbone and the modules, by the law table's «file»
```

A file in `casepath/process/areas/` ships with CasePath and is on by default. A file of the same format in the deployment's catalogue directory (`CASEPATH_WORKFLOW_CATALOGUE`) is composed the same way and wins over a shipped module of the same id.

**Worked example: a neighbour dispute (Art. 684 ZGB).** Only the new parts are shown; `assessment`, `stages`, `notes` are as in any module.

```json
{"format": "casepath.area/1", "id": "nachbar", "version": "2026-12-01.1", "backbone": "2026-11-14.2",
 "short_title": "Nachbarrecht", "title": "Nachbarstreit: übermässige Einwirkungen (aus dem Gesetz abgeleitet)", "status": "draft",
 "builds_on": ["osm-fallback"],
 "sources": [{"id": "law", "kind": "process_guidance", "title": "Zivilgesetzbuch (SR 210), Nachbarrecht"}],
 "law": {"zgb-684": {"cite": "Art. 684 Abs. 1 ZGB", "sr": "210", "article": "684", "passage": "<copied word for word, at most 40 words>", "verified": false}},
 "applies_when": {"fact": "rechtsgebiet", "is": "Sachenrecht / Nachbarstreit"},
 "facts": [{"id": "rechtsgebiet", "type": "enum", "values": ["Sachenrecht / Nachbarstreit"], "question": "Geht es um einen Streit unter Nachbarn?", "source_refs": ["law#zgb-684"]},
           {"id": "seit", "type": "date", "question": "Seit wann besteht die Störung?", "source_refs": ["law#zgb-684"], "ask_customer": true, "customer_question": "Seit wann werden Sie gestört?"}],
 "documents": [{"id": "protokoll", "title": "Protokoll der Störungen (Datum, Uhrzeit, Art)", "why": "Übermässige Einwirkungen sind verboten (Art. 684 ZGB); sie sind zu belegen.", "source_refs": ["law#zgb-684"], "stage": "klaeren"}],
 "hints": [{"id": "protokoll", "when": true, "text": "Bitte halten Sie jede Störung mit Datum und Uhrzeit fest.", "legal_basis": "Art. 684 ZGB", "source_refs": ["law#zgb-684"]}],
 "deadlines": []}
```

Set `verified` to true only after `--law` finds the passage in the official text. A deadline is one line:

```json
{"id": "anfechtung", "title": "Anfechtung der Kündigung bei der Schlichtungsbehörde", "trigger": "kuendigung_erhalten",
 "period": {"days": 30}, "from": "nach Empfang der Kündigung", "basis": "Art. 273 Abs. 1 OR",
 "missed": "Nach Ablauf dieser Frist ist ein Anfechtungsbegehren verspätet.", "question": "Wann haben Sie die Kündigung erhalten?", "source_refs": ["law#273"]}
```

`period` is `{"days"|"weeks"|"months"|"years": n}`, `{"days_before": n}` or `"sofort"`; optional are `when` (a condition), `direction: "ab"` (an earliest date), `shift: false` (no weekend rule), `check` (a note for the handler), `hint: false` and `period_from` (a text fact of the module holding a period the parties agreed, e.g. a loan's notice period «sechs Wochen», which then governs instead of `period`; one it cannot read as one number and one unit gives «prüfen»). While the trigger date is not in the file, the first request asks the `question` and says a deadline may be running; once it is, the deadline is a computed item with its article. A trigger date that was read but not settled (the source checker rejected it, or two readings differ) never makes its deadline disappear: it is shown as possible (`prüfen`, with the date the reading gives as `candidate`, «Datum prüfen»), the first request says so and asks the date, also where the question is otherwise only offered. A statutory period is never a reading: a deadline fact recorded as «<n> <unit> from …» with the period of one of the area's deadlines is refused at recording and, in a stored run, not listed (it is the area's own computed item, not a rejected fact). Computation follows only what the verified texts of the deadline's procedure say (`counting`, below); «sofort», backwards periods and imprecise trigger dates give «prüfen», never a date.

## Key points: what a specialist looks for first

Each module lists two to five `key_points` (71 in the 19 areas, on 98 article passages, all checked against the official text): an id, a short `statement` for the handler («Kündigung möglicherweise nichtig: Sperrfrist»), the condition on facts under which it applies (`when`), its articles (`law`: references to law entries with their passage), what `follows` from it (one sentence the assessment can use), what still has to be `check`ed, a short `question` for when the condition rests on a fact the file leaves open («Arbeitsunfähigkeit bei Kündigung? Dann Sperrfrist prüfen»), and optionally `answers`, words a customer's question about it would contain. `casepath/process/keypoints.py` evaluates them on the case's facts: a point applies, is a question (never asserted), or is not shown. The card shows at most two, directly under the deadline line, applying ones first, each with its article as a tag that opens the passage (with what follows and what to check) and its facts' source one click away; the reason line then folds into «Warum dieser Schritt». The assessment's «In Ihrem Fall:» starts from the points that apply, each as a sentence with its article, then the marked gap for what only the handler can say; «Zu Ihren Fragen:» lists the customer's own questions (read with the brief, with their quotes, no extra model call), each answered by the point whose words it contains, otherwise a marked gap. The validator refuses a key point without a condition on facts, an article with a passage, or a statement.

```json
{"id": "sperrfrist", "statement": "Kündigung möglicherweise nichtig: Sperrfrist", "question": "Arbeitsunfähigkeit bei Kündigung? Dann Sperrfrist prüfen",
 "when": {"fact": "arbeitsunfaehig", "is": true}, "law": ["law#336c.2", "law#336c"], "follows": "Eine Kündigung, die während einer Sperrfrist … ausgesprochen wird, ist nichtig; …",
 "check": "Beginn der Arbeitsunfähigkeit gegenüber dem Tag der Kündigung …", "answers": ["lohn", "gültig", "krank"]}
```

## Letters the customer sends in his own name

A module may list `customer_letters` (8 in 7 areas): templates for the letter a customer sends himself when that is the obvious next step: notice of a defect with a deadline to remedy it (Art. 257g, 259b OR), demand for repayment of a loan with its six weeks (Art. 318 OR), objection to an abusive dismissal before the notice period ends (Art. 336b OR) and a request for its written reasons (Art. 335 Abs. 2 OR), a request for the reasons of a tenancy's termination (Art. 271 OR, with the 30 days of Art. 273 OR), notice of defects after a purchase (Art. 201 OR), a request to release a deposit (Art. 257e Abs. 3 OR), and for a payment order a short instruction for the objection at the office, not a letter (Art. 74, 75 SchKG). Each has a condition on facts (`when`), parts that each rest on an article with its passage (`law`) or say `"plain": true`, gaps the customer fills in (`fill`, rendered «[einsetzen: …]», never the handler's «[bitte ergänzen: …]»), the deadline the letter sets (`sets`), the customer's statutory deadline it must meet (`must_arrive`: a deadline of the module; the template says by when), how it is sent and further advice, each resting on law (`requires`: words the cited passage must contain) or said as prudence («Wir empfehlen …»).

`casepath/process/customer_letters.py` offers a template whose condition holds with the assessment (A5) and, when its statutory deadline is within 30 days or «sofort», with the first request (A1) too; the insurer's letter refers to it in one sentence, the card lists it as a quiet line «Vorlage für Ihr Schreiben an …» under the letter, copied on its own. It is always marked as the customer's own letter, never as sent by the insurer.

```json
{"id": "begruendung", "title": "Verlangen einer schriftlichen Begründung der Kündigung", "to": "die Arbeitgeberin", "to_dative": "der Arbeitgeberin",
 "when": {"fact": "grund_genannt", "is": false}, "subject": "Begründung der Kündigung", "fill": {"kuendigung_erhalten": "Tag, an dem Sie die Kündigung erhalten haben"},
 "parts": [{"text": "Am {kuendigung_erhalten} habe ich Ihre Kündigung meines Arbeitsverhältnisses erhalten.", "plain": true},
           {"text": "Ich bitte Sie, mir die Kündigung schriftlich zu begründen.", "law": ["law#335"]}],
 "sets": {"days": 10, "text": "zehn Tage für die Antwort", "basis": "prudence"},
 "send": {"text": "Wir empfehlen, das Schreiben eingeschrieben zu senden …", "basis": "prudence"},
 "advice": [{"text": "Die Frist für eine Einsprache … läuft bis zum Ende der Kündigungsfrist", "law": ["law#336b"], "requires": ["Ende der Kündigungsfrist"]}]}
```

## Dates others set

The module's question about a running deadline (the deadline fact `frist`) also asks for a date a court, an authority or the other side set for the customer (a hearing, a period to respond, a payment demanded), recorded as «2025-04-23 · Schlichtungsverhandlung · Schlichtungsbehörde Bern · Vorladung» (the backbone's `set_dates`). No fact is added: a tenancy-defect run reads 40 facts before and after. Such a date is its own deadline item with what is due, who set it and its source; an open one leads the card like a statutory deadline («Termin 10.12.2026 · Schlichtungsverhandlung · laut Vorladung»), a past one says «abgelaufen», and the first letter mentions an open one. A date on the other side's duty that has passed says «abgelaufen» too.

## Decisions at their stage

A handler's decision in the backbone names the stages it belongs to (`stages`: cover at intake, clarifying and assessment; the way to proceed at «Vorgehen»; a settlement with the other side or under the mandate; the payment at «Abwicklung»; ending benefits under a mandate). The Übersicht shows only the decisions of the current stage, besides those the prepared action waits for.

## The law table and the counting rules

A law is any official federal text, identified by its SR number and, where it has one, its short name: the backbone's `laws` lists each with its title, consolidation date, fedlex filestore url and the saved file (`file`, laid out as the sources folder's `index.tsv`); a module may add one under its own `laws`. An «Art. … <short name>» in any text needs a law entry with its verbatim passage, and `python -m casepath areas --sources <folder>` checks every passage against the saved text. Shipped: OR, ZGB, VVG, ZPO, SchKG, StPO, OBG, SVG, ATSG, IVG, BV and SR 173.110.3 (Saturdays).

Each deadline names its procedure, `"counting": "<rule>"` (default `or`), and the composed deadline carries that rule (`counting_rule`), so a stored run keeps it. The backbone's `counting` says, per procedure and resting on verified passages, when a period starts, how days, weeks and months are counted, what a last day on a Saturday, Sunday or holiday does, whether the period stands still and whether the debt-enforcement holidays extend it; a part without a rule states its reason, and a deadline that needs it says «prüfen» with that reason and no date.

| Rule | Start | Days | Weeks / months | Saturday, Sunday, holiday | Standstill |
|---|---|---|---|---|---|
| `or` (OR; VVG through Art. 100 VVG) | next day (Art. 77, 132 OR) | counted | same weekday; same number or the month's last day (Art. 77 Abs. 1 Ziff. 2–3 OR) | Sunday, holiday: next working day (Art. 78 OR); Saturday for statutory and official periods (Art. 1 SR 173.110.3), an agreed period ending on a Saturday: «prüfen» | none |
| `atsg` (social insurance; IVG through Art. 1 IVG) | day after notification (Art. 38 Abs. 1 ATSG) | counted | «prüfen»: not stated | next working day (Art. 38 Abs. 3 ATSG) | 7th day before to 7th day after Easter, 15.7.–15.8., 18.12.–2.1. (Art. 38 Abs. 4 ATSG): those days are not counted |
| `stpo` (penalty order, fine decision) | next day (Art. 90 Abs. 1 StPO) | counted | «prüfen»: not stated | next working day (Art. 90 Abs. 2 StPO) | none (Art. 89 Abs. 2 StPO) |
| `zpo` | next day (Art. 142 Abs. 1 ZPO) | counted | «prüfen»: Art. 142 Abs. 2 ZPO counts months from the day the period «began to run», which the text does not settle | next working day (Art. 142 Abs. 3 ZPO) | as ATSG (Art. 145 Abs. 1 ZPO); served during it, the period starts after it (Art. 146 Abs. 1 ZPO) |
| `zpo-ohne-stillstand` | as `zpo` | counted | «prüfen» | as `zpo` | none: conciliation and summary procedure (Art. 145 Abs. 2 ZPO) |
| `schkg` (payment order, complaint) | next day (Art. 31 SchKG, Art. 142 Abs. 1 ZPO) | counted | «prüfen» | next working day (Art. 142 Abs. 3 ZPO) | no standstill (Art. 63 SchKG, Art. 145 Abs. 4 ZPO); a period ending in the debt-enforcement holidays (7 days before and after Easter and Christmas, 15.–31.7.) runs to the third working day after them (Art. 56 Abs. 1 Ziff. 2, 63 SchKG); a payment order served in them, on a Sunday or holiday (`"served": true`): «prüfen» |
| `schkg-klage` (action before a court, e.g. to deny the debt) | as `schkg` | counted | «prüfen» | as `zpo` | the ZPO standstill (Art. 56 Abs. 2 SchKG, Art. 145 Abs. 4 ZPO) |
| `obg` (fixed fine) | «prüfen»: the Act gives no rule | | | | |
| `kantonal` (with `"period": "kantonal"`) | «prüfen»: cantonal procedure; `period_from` may name the period the decision states, shown with `period_from_label` | | | | |

Weekends and the federal holiday (1 August, Art. 110 Abs. 3 BV) are applied; cantonal holidays are not in the verified texts. A last day that is a public holiday in many cantons (1 and 2 January, Good Friday, Easter Monday, Ascension, Whit Monday, 1 May, 15 August, 1 November, 8 December, 25 and 26 December) gives «prüfen» with the date the count reaches; on any other day the date carries «kantonale Feiertage nicht berücksichtigt».

## What a fact is not

A fact may name the nearest thing that does not count as it, in one line: `"not_this": "eine beiläufige Nachfrage (z.B. «wie läuft es mit dem Geld?») …"` (10 to 300 characters). The reader gets it with the fact (open_process), the second reading with the deciding facts, and the source checker in the claim it judges («… (not: …)»), with no extra call. The cover facts every area carries (`cover.json`: the cause date, a hint of an exclusion, a step without approval, a written demand) name theirs the same way. Shipped on every deadline trigger and wherever a near-miss is plausible: a termination's receipt and its date of writing, the end of the notice period and the day notice was given, delivery and the contract date, a notice clause and an agreed repayment date, a chat question and a demand, a statutory period and a deadline the files set, the customer's own deadline and one set by the other side.

## A document the other side has not issued

A need that exists only once the other side has acted (the landlord's statement, a written reason for a dismissal, a letter that sets a deadline, a handover protocol) depends on a fact the customer can answer, asked in the first request (`ask_customer: true`): asked only on yes; on no it is not needed, and while open it waits and the question is asked.

## Forms never render empty

A form has parts or says why it has no draft (`none`). A part whose placeholders all come out empty is left out with its fixed words (no empty document list). A form that names what it is for, `"asks": ["liste", "fragen"]` (A1), and has none of them filled has no draft and gives its reason (`empty`); lines that are only offered and not ticked are not filled. The validator refuses a form without parts or reason, and `asks` without `empty`, in the backbone and, after composition, in every form of an area (the cover's and a module's own too).

## Leaving the clarifying stage (backbone rules, every area)

Checked in this order: cover refused → closing; first request not yet sent and nothing to ask → assessment (A5) without it (`nichts_anzufordern`: no document is asked now, `items.ask_of`, and no question to the customer is open; offered lines never count; the automatic receipt A0 has acknowledged the case); first request not yet sent → A1; documents complete, or the customer replied since the last request (A1, A4, A6, A7) with the stage's customer points all answered → assessment (A5), which lists what is still missing under «Bitte reichen Sie uns noch nach»; replied with exactly one point open → question back (A4); no reply → the clock (pending, A6, A7); only then, after at least two requests that set a deadline (A1 21 days, A6 25, A7 7; `cooperation` in the backbone; A4 never counts), the last deadline passed and nothing received since → end of benefits (A12). A customer who replies without sending everything is cooperating. An open-ended need («Sämtliche …», or `"open_ended": true`) that is partly present does not hold up completeness. A module may name documents without which no assessment is possible: `"assess_needs": ["<document id>"]` (default none). «Received» is read from the case's files when the case is shown: a document dated after the request whose sender is not the insurer, or, in a live case, a file added later; with no files known it is never silence.

## A stage is not skipped (backbone rule, every area)

Every stage yields something a handler can do: its action kind (A0–A12, with its German title) or, at «Vorgehen festlegen», the handler's decision «Wie soll vorgegangen werden?» with the choices of `vorgehen` (form `vorgehen`, which waits for that decision). The validator refuses a stage that yields neither, an action, follow-up or variant that is not an action kind, and a clock rule naming an unknown kind. A composed workflow carries `stage_actions: true`: a stage with an action is left only when that action is in the case's **dated** history (an «A5» without a date does not count), or a handler decision places the case beyond it (the stage floor below), or the way out says the action is not needed (`"without_action": true`: the automatic receipt; in clarifying a settled matter, nothing to ask, cover refused, documents complete with cover confirmed; silence after the assessment; a settlement with the other side). A case whose customer wants further action but has no assessment is at «Beurteilen und beraten» with A5 prepared; the evaluation names the action it waits for (`held_for`). A stage whose action is done shows its follow-up with its own title (`follow_up_title`, else the kind's title) and a date; a follow-up the clock governs is dated for the day the clock comes due and becomes the clock's action (reason «keine Antwort seit …») only when nothing came in.

**No dead ends.** After composition every stage that is not an ending has a way out some answer can make true, an ending is reachable from every stage, and every incoming kind is answered by the action prepared for it (otherwise its item could never close). `tests/test_stage_rules.py` sweeps histories, decisions, the customer's wish, settlement, payment and an open cost claim and finds a named next step everywhere; the settlement stage with a cost claim open prepares the claim (A11) and closes once it is paid.

## Stage floor (backbone rule, every area)

A case is at least at the latest stage, in backbone order, that its history places it: each action kind names its stage in `action_kinds` (A1, A4 → klären; A5 → beurteilen; A8, A9 → gegenpartei; A10 → mandat), and `floor_decisions` names the stages a handler decision places it (cover refused; the way to proceed decided; benefits ended on the firm's report). A payment (A11) places no floor: under a mandate it also pays the firm's cost notes, so the settlement stage is reached by the settlement itself (`einigung`). The walk starts at the floor when it would stop before it; documents of the stages behind stay listed but never pull the case back. A stage action already in the history is not proposed again: its follow-up comes next, counted from the last dated action (`since`), unless the follow-up is one the clock governs (A6, A7, A12), which waits for the clock. Clock rules name the stages they apply in (`stages`).

## What comes in (backbone overlay, every area)

A case a law firm handles under a mandate moves by what comes in, not by the clock. The backbone's `incoming` list names each kind of item that comes in from a third party and the action it calls for; `casepath/process/incoming.py` evaluates it. Shipped, in priority order: the firm reports that the customer does not cooperate or ends the mandate (the handler's decision «Leistungen einstellen?»: yes → A12 with the end-of-benefits letter, whose clause of the general conditions is a marked gap; no → back to the way to proceed); an offer or reply of the other side (A9, no draft); a cost claim of the firm or a court (A11, no draft until a form exists; it can repeat and keeps the case from closing through the derived fact `kosten_offen`); a payment received (A11, confirm); a report on the state of the matter (a file note, no stage change). Each is observed «in 1 von 7 Dossiers»; outside the observed area the count is dropped like every other practice count. A practice need carries its count as `practice` on its item («in 6 von 7 Fällen verlangt», from the practice rule's evidence or the module's `practice#nofm`), and that count is its tag wherever the handler sees it.

Each kind is read as a short list, one text fact per item, each from its own document with its own located quote: who sent what, its date, and, when the file shows it answered, a mark («beglichen JJJJ-MM-TT», «beantwortet …», «erledigt …»). `fact` holds the latest item, `earlier` at most two before it (`incoming.MAX_ITEMS` = 3 per kind): cost claims three (`eingang_kostenforderung`, `_2`, `_3`), offers and payments two, reports and the firm's report of non-cooperation one. Most files have none, and then nothing is recorded, at no extra cost. That is nine read facts for what comes in (five on the release before, none on the deployed one); `leistungen_einstellen` and `eingang_erledigt_bis` are the handler's, `kosten_offen` is computed.

Each item is its own entry. It is open until the file shows it answered, the handler marks items up to a date done (`eingang_erledigt_bis`, the «erledigt» link beside the reason), or the case's history (A-codes with dates) shows an action of a kind in its `answered_by` dated after it; each such action answers one item only, the oldest open one before it, so one payment does not settle two claims (a kind answered by `"any"` action, a report, uses none up). An item read without a date takes the date of the document its quote is in (the segment of its page); a document without a date is bounded by the dated documents on either side of it (the later of the two, so an action is never counted as answering it too early); a single-document file of a live case by the day it was added. With none of these it stays open until the handler marks it done. The open items in the kind's priority, the oldest first, are the prepared action (outranking the stage's action and the clock) and the «danach» list; the reason line names the item, says when its date is the document's, and has its source one click away. The customer's own statutory deadline still leads the card and caps the follow-up. After an offer is answered the negotiation stage waits: «Antwort der Gegenpartei abwarten (ohne Antwort: mahnen)», dated 14 days on; the clock (A8 or A9, then 14 days of silence) proposes «Gegenpartei mahnen».

**Read twice.** What came in decides the next action, so it rides on the run's one second reading (`team.confirm_facts`): the latest item of every kind is read again (a second reading that finds an item the first missed adds it), an earlier item only when the first reading recorded one; no call is added. Two readings name the same item when they give it the same date. When they differ, the item stays open on the first reading and its reason says «eine zweite Lesung der Akte ergab «…», bitte prüfen»: a disagreement never hides or closes an item.

**Add a kind.** Add its text fact to the backbone's `facts` (question: who sent what, its date as YYYY-MM-DD, from one document, «keine …: nicht erfassen»), then one row in `incoming`:

```json
{"id": "vorschuss", "fact": "eingang_vorschuss", "title": "Kostenvorschuss des Gerichts", "what": "…", "from": ["gericht"], "priority": 6,
 "handler_decision": false, "action": {"kind": "A11", "title": "Kostenvorschuss leisten", "form": "A11_kosten", "next_in_days": 10},
 "answered_by": ["11"], "note": "in 1 von 7 Dossiers beobachtet", "source_refs": ["practice#1of7"]}
```

`from` is among kanzlei, gericht, gegenpartei, kunde; `form` must be a backbone form (one with `none` says why there is no draft); `priority` is the kind's own; `blocks_closing: true` keeps the case from closing while it is open; `decision` names a handler-only fact and the action on yes and on no. The validator refuses a kind without these, with a fact that is not a read text fact, or with an unknown form.

## The running account (backbone `record`, every area)

The reader returns one short entry per document of the file, phone notes included (`record_steps`, at most ten entries per call): date, from and to (`kunde`, `versicherer`, `kanzlei`, `gegenpartei`, `behoerde`, `andere`), the kind of step from the backbone's closed list (`record.kinds`: Meldung, Anforderung, Erinnerung, Antwort, Unterlagen zugestellt, Rechtliche Einschätzung, Telefonnotiz, Schreiben an die Gegenpartei, Angebot, Gegenangebot, Annahme, Mandat, Kostengutsprache, Bericht der Kanzlei, Kostenforderung, Zahlung, Zahlungsbestätigung, Termin oder Vorladung, Entscheid, Abschlussankündigung, Abschluss, Anderes), whether it is a phone note, one line on what it is, and what it asks (of whom, by when, which earlier entry it repeats, whether it warns), answers (which entry), the terms offered or agreed (amount, who pays, by when), what was paid and the next step it states. Every element carries a quote located in that same document; an element whose quote is not found there is dropped and counted (`record.dropped`).

From the entries, by code (`casepath/process/account.py`): the requests ledger (asked by whom of whom, first and last asked, by when, how often, warned, answered by which entry, the answer matching what was asked); the agreement as it stands (the latest agreed terms; an acceptance takes what it does not state from the terms it accepts; earlier terms kept as history) and whether paid; who owes what now; the insurer's actions with their dates (each kind's `code`, `code_to` a party, `again` for a second closing announcement, a phone note `phone_code`), which replace the history facts read one at a time (`handlung_a…`, `bisherige_handlungen`); `einigung` and `zahlung_erhalten` where the reading and the handler leave them open. The clock's silence rules read the ledger (only the party asked ends a silence), as do lack of cooperation, the number of requests and an answer since the last request. An agreed payment past its date and not shown made is the next action («Auszahlung … nachfragen»). «Der Fall» shows the «Stand» lines (agreed, open at the customer, at the other side or the firm, at us, last contact) for any case with more than a first report; the Verlauf shows one row per entry with «nur Offenes»; the file note writes the same lines. A run stored before the account has no entries: it opens as before, without «Stand», and nothing is invented.

Before a file's text goes to a model, text repeated across its documents is left out (`casepath/read/hygiene.py`): a block of at least 120 characters identical in three or more documents, after the first that has it, and a quoted earlier message whose text is its own document. Quotes are located in the original only.

## What the validator refuses

- a law reference (`law#…`) or an «Art. … <short name>» of any law in the table in any text without a law entry, a law entry without `cite`, `sr`, `article`, `passage` or `verified`, a passage over 40 words, an SR number the law table does not list; a law without its title, consolidation date and fedlex filestore url, two laws with one short name;
- practice counts («3 von 7», `practice#3of7`) in a module not observed in practice;
- a fact that repeats a backbone fact, a document on an unknown stage, an assessment without rights, conditions and demand;
- a deadline without a date fact of the module as its trigger, without an article as its basis (a cantonal period: its basis in words), with an unknown period or counting rule, or a cantonal period counted by another rule; a counting rule whose part rests on no verified passage and gives no reason;
- a key point without a condition on facts, an article with its passage, or a statement (and what follows, what to check and its question); a decision's `stages` that are not backbone stages;
- a customer letter without a condition on facts, a legal statement (an article, «muss», «Anspruch» …) without an article and its passage, an instruction whose words the cited passage does not contain, prudence that says «muss», the insurer's name in its parts, or a placeholder that is neither a fact nor a gap;
- a stage that yields neither an action kind nor a handler's decision, `without_action` on a stage without an action, an incoming kind whose own action does not answer it, more than three facts for one kind;
- and, after composition, everything any workflow must satisfy (every rule names a listed source, conditions name known facts and values, every step reachable) and no dead end.

## Routing

The routing fact `rechtsgebiet` names area and concern («Mietrecht / Kündigung»), read from the files with a located quote. One value selects its area; nothing established, or «Übriges Recht», goes to `allgemein`, which names the other areas as candidates for a person to pick. A second topic the reader names that is another area's own (its short title or value) is offered beside the chosen area («Prozess bestätigen»).

Every shipped area joins by default, also with no catalogue directory, so out of the box no case is unmapped. A catalogue directory opts out with a settings file, e.g. `catalogue.json` = `{"format": "casepath.catalogue/1", "shipped_areas": false}`. A workflow or area file in the directory with an area's id wins over the shipped area. An intake an area supersedes (`mietmangel-handler` → `osm-mold`, `vertrag-darlehen` → `osm-loan`, `allgemein` → `osm-fallback`) stays readable for stored runs but is no longer routed.

## Stored runs

The composed tenancy-defect workflow is the former seed field for field (`tests/fixtures/areas/mietmangel-handler.2026-11-12.5.json`), with the same id and version, plus new fields only. A module's version is the composed version while its `backbone` pin matches; after a backbone change it becomes `<module>+<backbone>`, and stored runs fall back to the latest version as they do today. Backbone 2026-11-14.2 (the stage rule, items as lists, the reminder clock) moved every module to 2026-11-14.2. Backbone 2026-11-14.4 (the cover points and prescribed letters, and the further areas) moved every module to 2026-11-14.4. Backbone 2026-11-14.5 (key points, the customer's questions in the assessment, dates others set, decisions at their stage) moved every module to 2026-11-14.5; a stored run opens under it and shows the key points from the facts it read; it read no customer questions, so its assessment has no «Zu Ihren Fragen». Backbone 2026-11-14.6 (key points by stage and the short facts of the mandate and handling stages, `stage_lines`; each key point marked as advice the customer can act on, which the first request carries with its article; continued pay in the dismissal area, Art. 324a and 336c OR) moved every module to 2026-11-14.6. Backbone 2026-11-14.7 (the mandate package, settlement and payout, the fee-note check, the customers' own letters; three handler facts: the guarantee's scope and amount, the settlement confirmed) moved every module to 2026-11-14.7. Backbone 2026-11-15.1 (the running account, `record`; a run stored before it has no entries and shows no «Stand») moved every module to 2026-11-15.1. Backbone 2026-11-15.2 (the two lines joined; the settlement sequence reads the agreement from the account where there is one; the chase of an overdue agreed payment has its letter, `A11_nachfragen`) moved every module to 2026-11-15.2. A run stored under 2026-11-14.1 opens and is evaluated under the new rules without a new run; the screen says «Prozess seit der Vorbereitung aktualisiert». The facts it never read (`eingang_kostenforderung_2` …) are simply not established: its latest item of each kind counts as one item, nothing earlier is invented.
