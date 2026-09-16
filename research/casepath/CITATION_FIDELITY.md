# Citation fidelity: what the gate can and cannot measure across contracts

## The measurement that does not work

Running the verbatim gate across the four scope contracts produces these numbers, and they should **not** be read
as fabrication rates.

| contract | quotes | attributable to a corpus statute | matched verbatim | apparent rate |
|---|---|---|---|---|
| rent_increase (gated, this work) | 44 | 44 | 44 | 100.0% |
| rent_increase (25-decision draft) | 130 | 114 | 68 | 59.6% |
| termination | 106 | 85 | 43 | 50.6% |
| legal_expenses | 100 | 31 | 11 | 35.5% |
| theft | 145 | 43 | 11 | 25.6% |

The four richer contracts store `authorities` and `quotes` as **parallel lists with no mapping between them**. A
decision cites, say, OR 266l, ZPO 200, a Zurich court leaflet and a Ticino guide, and then lists eight quotes. The
check has no way to know which quote came from which source, so it tests every quote against the statutory
citations — and a quote taken from a cantonal guide cannot appear in a statute.

Inspecting the failures confirms this is the dominant mode, not fabrication:

- `"Als Erhalt gelten der Empfang im Briefkasten, die Übergabe durch die Post…"` — plainly from a court's public
  leaflet on how notice periods are counted, tested against OR 273 and ZPO 142.
- `"occorre far capo obbligatoriamente ai moduli allestiti dal Dipartimento delle istituzioni…"` — plainly from the
  Ticino guide, tested against OR 266l.

These are correctly sourced quotes scored as failures by a check that could not see their source. The 25–60%
figures are an artifact of my measurement and are reported here only to retract them.

## The measurement that does work, and why the gated contract is different

The gated contract stores evidence as `{authority_id, quote}` **pairs**. Each quote is tested against the passage
it is actually attributed to, so a pass means that passage contains that span and nothing weaker. That is why its
rate is 100%: the gate is constitutive, not descriptive — an unverifiable quote never entered the artifact. Its 14
dropped quotes are listed in its own audit block.

The lesson is about artifact design rather than about models: **a legal artifact that lists sources and quotes
separately cannot be verified at all**, by any checker, however honest its author. Pairing them costs nothing at
authoring time and is the difference between an artifact that can be audited and one that cannot.

## The one confirmed fabrication

Independent of quote matching, and unaffected by the attribution problem above: the first rent-increase spine
cited `vmwg-art-19a-20251001-de`.

- Fedlex serves **no VMWG consolidation dated 2025-10-01**. Ten citations carried that date; re-resolved against
  the real consolidation, nine recovered — the article text was right and only the date was invented.
- **VMWG has no Art. 19a at any consolidation.** The tenth had nothing behind it. Its quote is fluent, correctly
  styled Swiss regulatory German, and sourceless.

This one does not depend on knowing which source a quote came from, because the cited provision does not exist. It
is the case for fetching and checking rather than reading carefully: a wrong date is recoverable and a careful
reader would likely catch it, while a fabricated article carrying a plausible quote looks exactly like the 44 that
verified.

## What the paper may say

That a fabricated provision reached a reference contract authored specifically to be authoritative, and that a
mechanical existence-and-substring check caught it. Not a fabrication rate across scopes — the artifacts as
authored do not support computing one, and this document records why.
