# Sources of the 197 passages

The cases in this dataset are synthetic, but the passages the rules were built
from are real. They are short verbatim excerpts from seven public documents. Each
row gives the edition that was used and the SHA-256 of the retrieved copy; every
copy was fetched again on 24 September 2026 and matched these bytes. BibTeX
entries are in `sources/sources.bib`, and `sources/passage-attribution.json`
gives the document that contains each passage.

| Key | Issuer | Document | Edition | Passages | Retrieved copy (SHA-256, bytes) |
|---|---|---|---|---|---|
| `fedlex2024vvg` | Swiss Confederation (Fedlex) | Bundesgesetz über den Versicherungsvertrag (VVG), SR 221.229.1, Arts. 38 to 41a, 45 and 46 | consolidated version of 1 January 2024 | 26 | `8498c33ac85675f0566a89c6746b59cdce4451bdb2b01e47e88e51ab6bca761a`, 182,164 |
| `css2024hausratavb` | CSS Versicherung AG | Hausratversicherung, Allgemeine Versicherungsbedingungen (AVB), Form. 519d-01.24-eff | Ausgabe 02.2024 | 67 | `cce8948157d794094847da343b09b9bdce1e4789e4bcd8d3511c06f952426c1d`, 123,925 |
| `css2026schadenanzeige` | CSS Versicherung AG | Schadenanzeige Hausrat / Gebäude (claim form), Form. 15d-08.26 | 08.2026 | 19 | `262da3f4791623ac05fdb723012dcfc4131189f150a8ff6418881172f130d356`, 568,572 |
| `axa2021haushaltavb` | AXA Versicherungen AG | Allgemeine Vertragsbedingungen (AVB) Haushaltversicherung, 16162DE | Ausgabe 10.2021 | 17 | `c6bd6d66e3a5bb6f18bba24d754d0ff64bacf1f776473b79e6a8b6f7b6c664e3`, 487,657 |
| `generali2026haushaltavb` | Generali Allgemeine Versicherungen AG | Allgemeine Versicherungsbedingungen (AVB) Haushaltversicherung | Ausgabe 2026 (06.2026) | 25 | `4a4b9a8113863f134e78a8f183cda7420ee212ef85ef3e6a9816809c094a9a3b`, 448,420 |
| `simpego2024homeavb` | Simpego Versicherungen AG | Simpego Haushaltversicherung Home, Allgemeine Versicherungsbedingungen (AVB) | Ausgabe Dezember 2024 | 9 | `72d560a0d5dd9772a2ea5c432c83b4c74ce902ccafd1bbff5080136c58304a4f`, 407,353 |
| `svv2022hausratavb` | Schweizerischer Versicherungsverband SVV | Allgemeine Bedingungen (AVB) für die Hausratversicherung, non-binding model conditions | Version 01.04.2022 | 38 | `6d5e431b8527d85bf81022900bbabbcd580289c3562680893f03f44ae485b80b`, 253,438 |

The passage counts sum to 201 because three passages appear word for word in
more than one document (0064: AXA and SVV; 0095: CSS AVB and SVV; 0190: AXA,
CSS AVB and SVV). The URLs are in `sources/sources.bib`; an issuer may later
serve a newer edition at the same address, so the edition and hash above are the
reference.

## Corrections to the frozen source labels

The benchmark files are kept exactly as evaluated, so their source labels are not
edited. In `benchmark/benchmark/SOURCE_SNAPSHOT_V2.json`, 109 passages carry a
single source label and 88 carry several candidate labels. Matching the text
confirmed 101 single labels and resolved all 88 candidates. Eight single labels
name a document that does not contain the passage; the text is verbatim in
another document of the corpus:

| Passage | Frozen label | Found in |
|---|---|---|
| theft-source-0019 | Simpego A5-7 | `generali2026haushaltavb` |
| theft-source-0029 | CSS AVB clause 29d | `css2026schadenanzeige` |
| theft-source-0058 | AXA D7-3-1 | `svv2022hausratavb` |
| theft-source-0095 | AXA J5 | `css2024hausratavb`, `svv2022hausratavb` |
| theft-source-0110 | AXA I3-2 | `simpego2024homeavb` |
| theft-source-0172 | CSS AVB clause 25d | `svv2022hausratavb` |
| theft-source-0189 | Generali theft definition | `svv2022hausratavb` |
| theft-source-0196 | SVV G8 | `css2024hausratavb` |

The labels record where a passage came from; the passage texts themselves are
verbatim. The frozen identifiers also call the Generali
document "2022", while the retrieved copy with the recorded hash is the 2026
edition, which is the one cited here.

## Copyright

Federal enactments such as the VVG are not protected by copyright in Switzerland
(Article 5 of the Copyright Act). The policy terms, the claim form and the SVV
model conditions belong to their issuers. They appear here only as short,
attributed quotations (see Article 25 of the Swiss Copyright Act), and they are
excluded from this dataset's CC BY 4.0 grant. No full insurer document is
included.
