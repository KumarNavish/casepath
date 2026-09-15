# The authority corpus, and how it is extracted

## Why the extraction method matters

The whole method rests on an exact-quote gate: a proposition is kept only if the substring it cites appears
verbatim in its passage. That gate is worthless if the passage text is not exactly what the source says. So
the extractor was built against a reference and verified before any of it was used.

Three routes were tried.

1. **The Fedlex ELI landing page.** Returns HTTP 200 and a JavaScript shell with no law text at all. Every
   citation "verified" against such a URL is a silent failure.
2. **The HTML twin.** Has the text, but drops the space before lettered list items, so `Vermieter: a. sie`
   becomes `Vermieter:a. sie`. Five of the repository's nineteen passages failed to reproduce.
3. **The Akoma Ntoso XML twin.** Correct. This is also what the repository's own
   `extraction_identity` field says its passages came from.

Extraction identity: visible text of the paragraph, authorial notes dropped, a separator inserted at block
boundaries so list items keep their spacing, whitespace normalised.

**Verification: 18 of the repository's 19 existing passages reproduce byte for byte.** The nineteenth is a
defect in the repository, not the extractor: its Art. 259g Abs. 1 carries two commas around the relative
clause that the consolidation it names does not have. A passage whose text does not match the snapshot it
cites is exactly the kind of thing an exact-quote gate cannot tolerate, and it is recorded rather than
quietly overwritten.

One more trap: the trailing number in the XML filename is a per-act file index, not a constant. It is 4 for
the Code of Obligations and 1 for the tenancy ordinance, so the corpus builder probes for it rather than
assuming.

## What the corpus now holds

| act | SR | consolidation | passages |
|---|---|---|---|
| Obligationenrecht | 220 | 2026-01-01 | 28 |
| Verordnung über die Miete und Pacht | 221.213.11 | 2025-01-01 | 9 |
| Zivilprozessordnung | 272 | 2025-01-01 | 17 |
| Versicherungsvertragsgesetz | 221.229.1 | 2024-01-01 | 9 |
| **total** | | | **63** |

Against the 19 the repository started with, that is a 3.3x expansion, and it adds the two layers the
tenancy statutes alone could not supply: the ordinance that governs the official form and its content, and
the procedural code that governs conciliation, authorisation to sue and the deadlines around them.

VMWG Art. 19a could not be extracted and is recorded as missing rather than approximated. The VAG did not
resolve from the ELIs tried; it is needed only for the legal-expenses scope, not for the strongest one.

## What the enlarged corpus buys

The same two-stage induction, run over 63 passages instead of 19, for the scope the sufficiency gate rated
strongest — a tenant contesting a termination and seeking an extension:

| | 19 passages, arrears scope | 63 passages, contest-and-extend scope |
|---|---|---|
| propositions | 48 | **170** (7 dropped by the quote gate) |
| nodes | 14 (11 supported, 3 uncertain) | 12 (**12 supported, 0 uncertain, 0 unsupported**) |
| transitions | 13 | 11 |
| obligations | 7 | 6 |
| deadlines | 3 | 3 |
| grounding problems | 0 | 1, caught by the validator |

The second graph is the more interesting one because it **spans two acts**. The substantive route comes
from the Code of Obligations — formal compliance, nullity, good faith, hardship, the weighing of interests
— and the procedural route comes from the Code of Civil Procedure: conciliation hearing, agreement recorded
and signed, claimant default deeming the request withdrawn, authorisation to sue, filing with the court.
No single-domain template produced that, and no hand-authored template in this repository contains it.

The three deadlines are right and now include the procedural ones: 30 days from receipt of the termination,
two months from receipt of the application for the hearing, 30 days from the opening of the authorisation
to bring proceedings.

The one grounding problem is the validator doing its job: a transition cited two proposition ids that do
not exist. It was reported, not silently accepted.
