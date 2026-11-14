# Cover decision prepared, letters whose content is prescribed

Data: `casepath/process/areas/cover.json` (format `casepath.cover/1`, skipped when the areas are composed). Code: `casepath/process/cover.py`. Tests: `tests/test_cover.py`. Check: `python -m casepath cover [--sources <folder with the saved fedlex HTML and web pages>]`.

## Cover points

Ten points, in the order a handler checks them (section 6(a) of PROTEKTA_SCOPE.md, checked against the text of the conditions):

| Point | Answered from | Private 01.2026 | Business 09.2025 |
|---|---|---|---|
| Police in Kraft, Prämie bezahlt | policy | A1 Ziff. 3, 4 | A1 Ziff. 2, 3 |
| Versicherte Person | policy (the file shows the name) | A1 Ziff. 2, B | A2 Ziff. 1, B1 |
| Versicherte Eigenschaft | file (legal area) | C Ziff. 1 / 3 by area | B2, policy |
| Rechtsgebiet versichert | file, then policy | D1/D2/D3 Ziff. 1 by area, else D | B4 Ziff. 7/13/15, else B4 |
| Ursache nach Antrag, in der Vertragsdauer | file (cause date), then policy (start date) | A2 Ziff. 1, 2 | A3 Ziff. 1, 2 (no sentence on the application) |
| Ausserhalb der Wartefrist | policy, with the cause date | A2 Ziff. 4 | A3 Ziff. 4 |
| Örtlicher Geltungsbereich | policy | A3 Ziff. 4 | A4 Ziff. 4 |
| Keine Deckungseinschränkung | file | J–L | E1–E3 |
| Melde- und Verhaltenspflichten | file | M Ziff. 1, 4 | F Ziff. 1, 4 |
| Summe, Selbstbehalt, Streitwert | policy | A1 Ziff. 1 (+ D2 Ziff. 1 for employment) | A1 Ziff. 1 |

Each clause carries a verbatim passage (at most 50 words); the tests find each word for word in `docs/sources/protekta`.

**What a run reads** (four facts added to every area): `ursache_datum` (the first actual or alleged breach; asked in the first request when the file does not state it, only offered where the area itself asks for a date that stands for it, e.g. «Seit wann besteht der Mangel?»), `ausschluss_hinweis`, `vorab_schritte`, `mahnung_androhung`. **What the handler sets**: the edition (`avb_ausgabe`: Privat 01.2026 by default, Unternehmen 09.2025, andere Ausgabe → clause tags «Ziffer prüfen» and marked gaps in letters), the policy start date (`police_beginn`), one tick per policy point (`police_*`), the cover decision (`deckung`) and, on refusal, the failing point (`deckung_grund`). All are ordinary `set_fact` edits and write `item.corrected` events.

**States**: aus der Akte geklärt (with its quote) · kein Hinweis in der Akte · in der Police prüfen (with what to look up and the dates that help) · in der Police geprüft · bei der Kundschaft erfragt · Hinweis (the passage that makes it fail). Waiting periods are «gemäss Police; allgemein drei Monate» (the private product page, not the conditions): a date computed from three months is labelled as such and never stated as a fact of the policy. The decision stays the handler's.

**Screen**: «Der Fall» → Deckung: the summary line; opened, one line per point with its state, the clause as a quiet tag (the passage on click) and for policy points the tick; below, [bestätigen] [ablehnen] (refusing asks which point fails).

**Items**: kind `cover` (key = point id, plus `summary`), kind `check`, kind `contact`. Their state is hashed like any item: `items_sha256` of every existing case changes once (new fact items and these items); a study frozen before this change no longer matches and must be frozen again.

## Letters whose content is prescribed

Forms in `cover.json` mark parts as `required`, each with its basis (`law#…` verified against fedlex, `avb#…` a clause in each edition) and a marker. `area.compose` refuses a module that drops or rewords one; the screen refuses to copy a letter whose marker is gone or whose gap is open.

- **Refusal for lack of prospects** (`A5_aussichtslos`, the assessment when the handler's decision `aussichten` is «nicht genügend»): reasons (gap), proposed solution (gap), own action at own cost with reimbursement on a better result (M/F Ziff. 7), the arbitration procedure with its 20 days (M/F Ziff. 8). Basis Art. 169 Abs. 2 AVO; without it the need for cover counts as accepted (Abs. 3).
- **End of benefits for lack of cooperation**: before the ending (clarifying stage, or the firm's report), the check «written demand with the consequences stated» (Art. 39 Abs. 2 Ziff. 2 VVG). Not in the file → the prepared action is the demand `A6_androhung` (what is missing, a date, the consequence); the handler may still end benefits («Leistungen trotzdem einstellen»). With it → `A12_mitwirkung` naming the demand's date. Clause by edition (M/F Ziff. 1 und 4). A quiet note: a disadvantage needs fault and causal effect (Art. 45 Abs. 1 VVG), a check, not a conclusion.
- **Mandate**: `A10_kunde` goes with the mandate letter: free choice of lawyer (Art. 167 Abs. 1 AVO; M/F Ziff. 3), consent and cost guarantee before instructing a lawyer, consent before a settlement (M/F Ziff. 5). An open offer of the other side shows the settlement check (M/F Ziff. 5).

## First contact

Three working days from the report's date in the file (a document of kind «…meldung», else the earliest dated document, else the first file's arrival), weekends skipped, public holidays not counted and said so; shown on the card and in the case list until an insurer contact (A1, A2, A4–A8, A10) is in the history. Source: Protekta's report page «Wir kontaktieren Sie innerhalb von drei Arbeitstagen …».

## Changing it

Edit `cover.json`: a clause is `"<edition>:<short>": {"cite", "passage"}`; a point names its clauses per edition by short key; an area mapping (`areas`, by the prefix of `rechtsgebiet`) adds capacity and legal-area clauses. Then run `python -m casepath cover --sources <folder>` and the tests. Set `verified` on a law entry only when `--sources` finds it.
