# Evaluator A: theft semantics

Program: `evaluate.py` (run `PYTHONDONTWRITEBYTECODE=1 python3 -I evaluate.py catalogue.json designs.json reference.json`).
Each step and each document's "needed when" condition is encoded as a boolean expression, evaluated in
three-valued (Kleene) logic over true / false / unresolved.

## Fact states

- `stated_true` -> true; `denied` -> false.
- `raised_and_left_open` -> unresolved ("A fact that the file raises and leaves unsettled is open.").
- `not_mentioned`:
  - defining events `theft_at_home`, `theft_away` -> unresolved ("The defining event is never presumed: if the file
    does not mention it, it is unresolved.");
  - `burglary_or_robbery`, `away_cover_missing` -> unresolved: each is marked "(always stated or open in a file; no
    presumption)", which I read as overriding the general "taken as not alleged";
  - every other fact -> false ("A fact that the file does not mention is taken as not alleged, and the rules are
    applied as if it were absent."). No other stop is triggered by a fact being false, so the "Silence never ends a
    process" clause changes nothing else.

## Defining event

- False: stop "this claim type does not apply"; every document is `not_needed` (all are on steps whose condition
  requires the defining event true).
- Open / not mentioned: documents on steps requiring it are `hold`, waiting for it.

## Steps and documents

- A document's state is decided from (step condition) AND (its "needed when" condition); in this text the latter
  already restates the step condition.
- True -> `request`; unresolved -> `hold` with `waits_for` = the unresolved facts the result depends on (catalogue
  order); false -> `not_needed`.
- `insurance_policy` in simple_theft_away is on step a_cover, reached when theft_away = true, so it is requested
  even when the cover-missing stop then applies ("Documents of steps reached before the stop keep the state they
  had; a document requested there remains requested."). In theft_at_home it is on h_notify, after the exclusion
  stop.

## Optional and conditional documents

- `police_report` (optional): "At intake the handler does not request it; a reference evaluator marks it 'not
  needed' unless the file contains it, in which case it is assessed as present and sufficient or insufficient. Its
  absence is never a gap." Implemented: not supplied -> `not_needed` (whatever its condition); supplied and its
  step reached -> `present_sufficient` / `present_insufficient`; supplied and step not reached -> `not_needed`;
  supplied and step held -> `hold`.
- `stolen_items_list`, `original_vouchers`, `bicycle_voucher` are mandatory at intake ("CSS makes that request in
  its own claim form, so they are requested at intake (mandatory: true)").
- `lock_change_invoice` needs lock_change = true and burglary_or_robbery = true ("Costs after a simple theft are
  excluded ... so the invoice is needed only after a burglary or robbery").

## Supplied documents

Needed and supplied -> present_* as designed. Supplied but held or not needed -> stays `hold` / `not_needed` (no
design in this set produces that case except the optional police report rule above, which did not trigger either).

## Stops

Both stops of each type are written into every later step's condition (household_perpetrator = false,
away_cover_missing = false), so evaluating the step conditions applies them; earlier steps (h_event, h_exclusion,
a_event, a_cover) keep their documents.

## Ambiguities

1. `burglary_or_robbery` / `away_cover_missing` not mentioned: the general convention says "taken as not alleged",
   the fact text says "no presumption". Chose unresolved (specific over general). Effect: with
   away_cover_missing not mentioned, every document after a_cover holds on it; for lock_change_invoice it would hold
   only if lock_change were true. In this design set the choice has no effect: away_cover_missing is unmentioned
   only where theft_away is denied, and burglary_or_robbery is unmentioned only where lock_change is not true or
   an earlier stop applies.
2. Optional police report when not supplied but its step is held: chose `not_needed` ("Its absence is never a gap").
   When supplied but its step not reached (a stop): chose `not_needed`, because a document "is decided when that
   step is reached". No design in this set exercises either sub-case with a supplied report.
3. "e-bike leaves the fact open" and similar notes are design-level; designs' fact states are taken as given.
4. h_instruction / a_instruction steps (measures_pending, imminent_danger) have no documents, so those facts never
   affect a document.
