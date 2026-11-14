# Areas: the handler's process for any case

Every legal-protection case runs the same chain of handler actions (A1 first request … A12 closing), the same six stages, the same clock and Protekta's letter forms. That part is the **backbone**, `casepath/process/areas/backbone.json`. What differs by legal area is small, and it is one **area module** per file next to it: the routing value, the facts with their customer questions, the documents with their legal reason, first hints, statutory deadlines, the legal frame of the assessment (A5) and of the letter to the other side (A8), and the law it cites. At load, `casepath/process/area.py` composes backbone + module into an ordinary workflow, so routing, evaluation, items and letters do not know the difference.

Shipped: `mietmangel-handler` (from practice and law), `miete-kuendigung`, `miete-mietzinserhoehung`, `miete-kaution`, `arbeit-kuendigung`, `arbeit-lohn`, `arbeit-zeugnis`, `vertrag-darlehen`, `vertrag-kauf`, and `allgemein`, the fallback for everything else. All are `draft`; the new ones are shown as «aus dem Gesetz abgeleitet, noch nicht freigegeben».

## Add or change an area

Copy the smallest module (`arbeit-zeugnis.json`), change it, check it:

```sh
python -m casepath areas casepath/process/areas/my-area.json      # validates and prints what it contains
python -m casepath areas --law 220=or.html 210=zgb.html            # every passage against the official text (fedlex filestore HTML)
```

A file in `casepath/process/areas/` ships with CasePath and is on by default. A file of the same format in the deployment's catalogue directory (`CASEPATH_WORKFLOW_CATALOGUE`) is composed the same way and wins over a shipped module of the same id.

**Worked example: a neighbour dispute (Art. 684 ZGB).** Only the new parts are shown; `assessment`, `stages`, `notes` are as in any module.

```json
{"format": "casepath.area/1", "id": "nachbar", "version": "2026-12-01.1", "backbone": "2026-11-14.1",
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

`period` is `{"days"|"weeks"|"months"|"years": n}`, `{"days_before": n}` or `"sofort"`; optional are `when` (a condition), `direction: "ab"` (an earliest date), `shift: false` (no weekend rule), `check` (a note for the handler) and `hint: false`. While the trigger date is not in the file, the first request asks the `question` and says a deadline may be running; once it is, the deadline is a computed item with its article. Computation follows only what the verified texts say: the trigger day is not counted, months and years end on the day with the same number or the month's last day (Art. 77, 132 OR), a Saturday or Sunday moves to the next weekday (Art. 78 OR, SR 173.110.3). Cantonal holidays are not known; «sofort», backwards periods and imprecise trigger dates give «prüfen», never a date.

## Leaving the clarifying stage (backbone rules, every area)

Checked in this order: cover refused → closing; first request not yet sent → A1; documents complete, or the customer replied since the last request (A1, A4, A6, A7) with the stage's customer points all answered → assessment (A5), which lists what is still missing under «Bitte reichen Sie uns noch nach»; replied with exactly one point open → question back (A4); no reply → the clock (pending, A6, A7); only then, after at least two requests that set a deadline (A1 21 days, A6 25, A7 7; `cooperation` in the backbone; A4 never counts), the last deadline passed and nothing received since → end of benefits (A12). A customer who replies without sending everything is cooperating. An open-ended need («Sämtliche …», or `"open_ended": true`) that is partly present does not hold up completeness. A module may name documents without which no assessment is possible: `"assess_needs": ["<document id>"]` (default none). «Received» is read from the case's files when the case is shown: a document dated after the request whose sender is not the insurer, or, in a live case, a file added later; with no files known it is never silence.

## What the validator refuses

- a law reference (`law#…`) or an «Art. … OR/ZGB» in any text without a law entry, a law entry without `cite`, `sr`, `article`, `passage` or `verified`, a passage over 40 words, an SR number the backbone does not list;
- practice counts («3 von 7», `practice#3of7`) in a module not observed in practice;
- a fact that repeats a backbone fact, a document on an unknown stage, an assessment without rights, conditions and demand;
- a deadline without a date fact of the module as its trigger, without an article as its basis, or with an unknown period;
- and, after composition, everything any workflow must satisfy (every rule names a listed source, conditions name known facts and values, every step reachable).

## Routing

The routing fact `rechtsgebiet` names area and concern («Mietrecht / Kündigung»), read from the files with a located quote. One value selects its area; nothing established, or «Übriges Recht», goes to `allgemein`, which names the other areas as candidates for a person to pick. A second topic the reader names that is another area's own (its short title or value) is offered beside the chosen area («Prozess bestätigen»).

Every shipped area joins by default, also with no catalogue directory, so out of the box no case is unmapped. A catalogue directory opts out with a settings file, e.g. `catalogue.json` = `{"format": "casepath.catalogue/1", "shipped_areas": false}`. A workflow or area file in the directory with an area's id wins over the shipped area. An intake an area supersedes (`mietmangel-handler` → `osm-mold`, `vertrag-darlehen` → `osm-loan`, `allgemein` → `osm-fallback`) stays readable for stored runs but is no longer routed.

## Stored runs

The composed tenancy-defect workflow is the former seed field for field (`tests/fixtures/areas/mietmangel-handler.2026-11-12.5.json`), with the same id and version, plus new fields only. A module's version is the composed version while its `backbone` pin matches; after a backbone change it becomes `<module>+<backbone>`, and stored runs fall back to the latest version as they do today.
