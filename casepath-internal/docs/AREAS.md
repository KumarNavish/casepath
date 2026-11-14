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
| `allgemein` | Übriges Recht, or nothing established (fallback) | law |

All are `draft`; those from the law alone are shown as «aus dem Gesetz abgeleitet, noch nicht freigegeben». Every area also carries the cover points, their facts and the prescribed letters of `areas/cover.json` (docs/COVER.md); `cover.json` names, per area, the date that stands for the cause of the case (`cause_from`) and the clauses of the conditions for its capacity, legal area and limits (`areas`).

## Add or change an area

Copy the smallest module (`arbeit-zeugnis.json`), change it, check it:

```sh
python -m casepath areas casepath/process/areas/my-area.json      # validates and prints what it contains
python -m casepath areas --law 220=or.html 210=zgb.html            # every passage against the official text (fedlex filestore HTML)
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

`period` is `{"days"|"weeks"|"months"|"years": n}`, `{"days_before": n}` or `"sofort"`; optional are `when` (a condition), `direction: "ab"` (an earliest date), `shift: false` (no weekend rule), `check` (a note for the handler), `hint: false` and `period_from` (a text fact of the module holding a period the parties agreed, e.g. a loan's notice period «sechs Wochen», which then governs instead of `period`; one it cannot read as one number and one unit gives «prüfen»). While the trigger date is not in the file, the first request asks the `question` and says a deadline may be running; once it is, the deadline is a computed item with its article. A trigger date that was read but not settled (the source checker rejected it, or two readings differ) never makes its deadline disappear: it is shown as possible (`prüfen`, with the date the reading gives as `candidate`, «Datum prüfen»), the first request says so and asks the date, also where the question is otherwise only offered. A statutory period is never a reading: a deadline fact recorded as «<n> <unit> from …» with the period of one of the area's deadlines is refused at recording and, in a stored run, not listed (it is the area's own computed item, not a rejected fact). Computation follows only what the verified texts say: the trigger day is not counted, months and years end on the day with the same number or the month's last day (Art. 77, 132 OR), a Saturday or Sunday moves to the next weekday (Art. 78 OR, SR 173.110.3). Cantonal holidays are not known; «sofort», backwards periods and imprecise trigger dates give «prüfen», never a date.

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

## What the validator refuses

- a law reference (`law#…`) or an «Art. … OR/ZGB» in any text without a law entry, a law entry without `cite`, `sr`, `article`, `passage` or `verified`, a passage over 40 words, an SR number the backbone does not list;
- practice counts («3 von 7», `practice#3of7`) in a module not observed in practice;
- a fact that repeats a backbone fact, a document on an unknown stage, an assessment without rights, conditions and demand;
- a deadline without a date fact of the module as its trigger, without an article as its basis, or with an unknown period;
- a stage that yields neither an action kind nor a handler's decision, `without_action` on a stage without an action, an incoming kind whose own action does not answer it, more than three facts for one kind;
- and, after composition, everything any workflow must satisfy (every rule names a listed source, conditions name known facts and values, every step reachable) and no dead end.

## Routing

The routing fact `rechtsgebiet` names area and concern («Mietrecht / Kündigung»), read from the files with a located quote. One value selects its area; nothing established, or «Übriges Recht», goes to `allgemein`, which names the other areas as candidates for a person to pick. A second topic the reader names that is another area's own (its short title or value) is offered beside the chosen area («Prozess bestätigen»).

Every shipped area joins by default, also with no catalogue directory, so out of the box no case is unmapped. A catalogue directory opts out with a settings file, e.g. `catalogue.json` = `{"format": "casepath.catalogue/1", "shipped_areas": false}`. A workflow or area file in the directory with an area's id wins over the shipped area. An intake an area supersedes (`mietmangel-handler` → `osm-mold`, `vertrag-darlehen` → `osm-loan`, `allgemein` → `osm-fallback`) stays readable for stored runs but is no longer routed.

## Stored runs

The composed tenancy-defect workflow is the former seed field for field (`tests/fixtures/areas/mietmangel-handler.2026-11-12.5.json`), with the same id and version, plus new fields only. A module's version is the composed version while its `backbone` pin matches; after a backbone change it becomes `<module>+<backbone>`, and stored runs fall back to the latest version as they do today. Backbone 2026-11-14.2 (the stage rule, items as lists, the reminder clock) moved every module to 2026-11-14.2. Backbone 2026-11-14.4 (the cover points and prescribed letters, and the further areas) moved every module to 2026-11-14.4. A run stored under 2026-11-14.1 opens and is evaluated under the new rules without a new run; the screen says «Prozess seit der Vorbereitung aktualisiert». The facts it never read (`eingang_kostenforderung_2` …) are simply not established: its latest item of each kind counts as one item, nothing earlier is invented.
