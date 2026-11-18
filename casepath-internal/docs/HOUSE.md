# The house: which insurer CasePath works for

CasePath prepares the next step of a legal-protection claim. Out of the box it does so for Protekta: nothing needs to be set. Everything that belongs to that one insurer and to no other is named in a **house profile**, one JSON file, and another Swiss legal-protection insurer starts CasePath with its own.

Code: `casepath/house/`. Built-in profile: `casepath/house/protekta.json`. Tests: `tests/test_house.py`, with an invented second house in `tests/fixtures/house/beispiel.json`.

## What a house is

The insurer whose handlers use the workspace: its name, how its files and letters look, its policy conditions, its processes and what it has learned from its own cases. `CASEPATH_HOUSE` names a profile shipped in `casepath/house/` (`protekta`, the default) or is the path of a profile file. The profile is read once per process, at first use; a process works for one house.

## The profile

Format `casepath.house/1`. Every field is required, an unknown field is refused, and the error names the field. Paths are relative to the profile file (an absolute path is taken as it is).

| Field | What the code does with it | Protekta |
|---|---|---|
| `id` | names the house in `/api/health` | `protekta` |
| `name` | the insurer in letters, as a party of the running account («Kundschaft → Protekta»), on the screens, and as the organisation the agents are told they work for | `Protekta` |
| `legal_name` | given to the page with the name; no text is built from it yet | `Protekta Rechtsschutz-Versicherung AG` |
| `recognised_by` | lower-case words that show this insurer in a document's sender or recipient line (who wrote to whom, the receipt of a claim, the last contact) | `protekta`, `rechtsschutz` |
| `claim_number` | regular expression for a claim number in a case title or a file; default of `CASEPATH_REFERENCE_PATTERN` | `\d{4}\.\d{4}\.\d{4}` |
| `conditions.short` | after a clause: «Art. M Ziff. 1 AVB» | `AVB` |
| `conditions.name` | standing alone | `Allgemeine Bedingungen` |
| `conditions.name_inflected` | after «der» and «den»: «Ziffer der Allgemeinen Bedingungen» | `Allgemeinen Bedingungen` |
| `conditions.cover` | the cover points with the clause of each edition (`casepath.cover/1`, docs/COVER.md) | `casepath/process/areas/cover.json` |
| `conditions.texts` | the stored text of each edition; only read to confirm the quoted passages (`python -m casepath cover`), so it may be absent where CasePath runs | `docs/sources/protekta` |
| `writing.case_work` | how the agents' instructions say the language of everything a handler reads; default of `CASEPATH_WRITING_LANGUAGE` | in the language of the case files, usually German, with Swiss spelling (ss, not ß) |
| `writing.photos` | the same for the description of a photo | in German with Swiss spelling (ss, not ß) |
| `letters.greeting` | the greeting when the file names no person | `Sehr geehrte Damen und Herren` |
| `letters.greeting_ms`, `greeting_mr` | with `{name}` (the family name), when the file states «Frau» or «Herr» | `Sehr geehrte Frau {name}`, `Sehr geehrter Herr {name}` |
| `letters.greeting_by_name` | with `{name}` (the full name), when the file states no salutation | `Guten Tag {name}` |
| `letters.closing` | closes a letter the code builds (the template for the customer's own letter); a form of the catalogue carries its own closing line | `Freundliche Grüsse` |
| `catalogue` | the folder with the backbone, the areas, the options and the live forms | `casepath/process/areas` |
| `knowledge_seed` | the knowledge a fresh deployment starts with | `casepath/process/knowledge_seed` |

`writing.photos` of the built-in profile holds a line break after «Swiss»: it is part of the instruction as it always was, kept so that the instruction is unchanged.

The clauses themselves are not in the profile. The code cites the conditions by purpose, and the cover file says which clause that is in each edition (`letter_clauses`):

| Purpose (slot) | Where it is cited | Protekta, Privat 01.2026 | Protekta, Unternehmen 09.2025 |
|---|---|---|---|
| `mitwirkung` | last demand before an end of benefits; end of benefits for lack of cooperation | Art. M Ziff. 1 und 4 | Art. F Ziff. 1 und 4 |
| `aussicht` | refusal for lack of prospects | Art. M Ziff. 7 | Art. F Ziff. 7 |
| `schied` | notice of the disagreement procedure (and `schiedsfrist`: 20 Tage) | Art. M Ziff. 8 | Art. F Ziff. 8 |
| `anwalt` | information of the customer with a mandate | Art. M Ziff. 3 | Art. F Ziff. 3 |
| `vergleich` | the same information; the hint «Ein Vergleich braucht die Zustimmung von …» | Art. M Ziff. 5 | Art. F Ziff. 5 |

## What a new house brings

| | What | Where it lives | Protekta ships with |
|---|---|---|---|
| 1 | The profile | a JSON file; `CASEPATH_HOUSE` | `casepath/house/protekta.json` |
| 2 | The workflow catalogue: its legal areas and the steps of each, its letter forms | the folder `catalogue` points to: `backbone.json` (stages, action kinds A0 to A13, letter forms, the law table), one module per legal area, `options/`, `live/` (docs/AREAS.md). A folder in `CASEPATH_WORKFLOW_CATALOGUE` still joins it: a workflow there with an area's id replaces that area | 19 areas, one of them (tenancy defect) with practice from closed dossiers, the others from the law alone and marked as not yet released |
| 3 | Its policy conditions for the cover check | the file `conditions.cover` points to: the cover points in the order a handler checks them, each with its clause and a verbatim passage per edition, and the clauses the prescribed letters cite; the text of each edition under `conditions.texts` | both editions in force (private 01.2026, business 09.2025), every passage confirmed against the stored text |
| 4 | Its knowledge, learned from its own closed cases | seeded from `knowledge_seed` into an empty store; after that it lives in the case store, where a reviewer activates, refines or retires each item | three practice rules for tenancy defects, from seven first-request letters |

A profile may point 2 to 4 at the shipped folders. The shipped data names Protekta; `house.in_own_name` reads it in the active house's name (and its sender words) at the moment it is loaded, and leaves the files untouched. That is a way to start and to test, not a release: the clauses, the passages, the practice counts and the seeded rules are then still Protekta's, under another name. To make them the house's own, copy the folder, change it and check it:

```sh
python -m casepath areas <folder>/my-area.json     # one area module: validates and prints what it contains
python -m casepath check-catalogue <folder>        # a folder for CASEPATH_WORKFLOW_CATALOGUE
python -m casepath cover                           # the active house's cover points and passages
```

## The same for every house

Not configurable, because it does not differ between Swiss legal-protection insurers:

- **The law.** The statutes an area cites and how periods are counted: OR, ZGB, ZPO, SchKG, StPO, SVG, ATSG and the others of the backbone's law table, each article with a verbatim passage of the official text. The insurance law behind the prescribed letters: Art. 39 and 45 VVG, Art. 167 and 169 AVO (they sit in the cover file beside the clauses, and are the same in every house's file).
- **Data protection and supervision** (docs/SWISS_PRACTICE.md, part B): every fact with its quote, a person decides, a case is opened only by those who may, deletion reaches everything derived, nothing but content-free counts leaves.
- **The handler's journey**: report, clarify, assess, the way to proceed, the other side, a mandate, settlement, closing, with the cover decision on the way; the action kinds A0 to A13; the running account with its parties; what comes in and what it calls for; the deadlines that lead.
- **The product**: the agents, the reading, the case API (docs/contracts), the workspace.

## Start CasePath for another house

```sh
cp casepath/house/protekta.json /etc/casepath/my-house.json     # then edit; repoint the four paths (relative to the new place, or absolute)
CASEPATH_HOUSE=/etc/casepath/my-house.json python -m casepath serve
```

A profile placed in `casepath/house/` is started by its id (`CASEPATH_HOUSE=my-house`). An incomplete profile stops every command: `house invalid: house profile …: the required field «legal_name» is missing`. `GET /api/health` answers with `house` (id, name, legal name, the words for the conditions); the page writes the name from there.

Use a case store for one house only: a prepared case keeps the process it was prepared with, name included.

Still settings of their own, over the profile's defaults: `CASEPATH_ORGANISATION`, `CASEPATH_WRITING_LANGUAGE`, `CASEPATH_REFERENCE_PATTERN`, `CASEPATH_WORKFLOW_CATALOGUE` (docs/DEPLOYMENT.md).

## Still Protekta's after this change

In the data, which a study in progress depends on and which therefore was not touched:

- `casepath/process/areas/backbone.json`: the letter forms are Protekta's wording; the questions and notes name Protekta; the journey and the law table, which every house shares, sit in the same file.
- `casepath/process/areas/cover.json`: Protekta's clauses, passages, editions and public pages. Its shape is also the code's: two editions chosen by the fact `avb_ausgabe`, the five slots above, placeholders named `avb_…`.
- `casepath/process/areas/mietmangel-handler.json`: practice lines and counts from seven closed Protekta dossiers. Three other modules mention Protekta in an open question (`inkasso`, `privatversicherung`, `werkvertrag-bau`).
- `casepath/process/knowledge_seed/osm-mold.pilot.json`: rules from Protekta's first-request letters.
- `casepath/web/i18n/en.json`: the translation memory holds Protekta's wording and the pilot's synthetic examples; a house with other wording gets fewer hits.

In the code:

- `casepath/process/mining.py`: the model's answer for a case course has a field named `protekta_actions`.
- `casepath/agents/team.py`, `casepath/read/reading.py`: the instructions were written and measured on Protekta's dossiers; one of them (the splitting of a file into documents) asks for Swiss spelling in its own words.
- `casepath/process/items.py`: defaults that follow observed practice («in n von 7 Fällen verlangt») were set from Protekta's dossiers; comments say so.
- German grammar: the name stands without an article («Frage an Protekta», «durch Protekta») and takes «s» in one line of the page («aus Protektas ersten Unterlagenanforderungen»); the name of the conditions is a plural.
- `casepath/web/ui/assets/casepath.js`: one default, the built-in house's name and words for its conditions, until `/api/health` has answered.

Around the code: `docs/sources/protekta/`, docs/PROTEKTA_SCOPE.md and docs/COVER.md describe Protekta's conditions; the synthetic files of the tests and of the preview (`tests/episode.py`, `tests/fixtures/`, `deploy/preview/`) are written as Protekta's; `deploy/` is the pilot's deployment.
