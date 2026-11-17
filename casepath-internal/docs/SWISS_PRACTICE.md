# Swiss claims practice and supervision: what CasePath rests on

Two public-source reviews of 17 November 2026, mapped onto the product: how legal-protection claims handling runs in Switzerland and how an operation is measured (part A, C), and what data-protection and supervisory law expect of an AI system that prepares claims work (part B). `docs/PROTEKTA_SCOPE.md` holds the earlier review of Protekta's own conditions and of AVO Art. 161–170, VAG Art. 32 and VVG Art. 14–46 with their wording; this file does not repeat it.

**How far each part is verified.** Part B was read in the consolidated texts on fedlex.admin.ch and in the documents on finma.ch, edoeb.admin.ch, bj.admin.ch and eur-lex. Part A rests on search-result excerpts only: the insurers', the ombudsman's and the bar association's pages could not be opened in that session, so its quotes are as the excerpts showed them and its figures are indicative. A deadline or article named in part A counts in the product only where an area module already cites it against the official text (`python -m casepath areas --law …`, docs/AREAS.md). Nothing here is legal advice; a jurist releases what a letter says (Wissen → Rechtsgebiete).

## A. How a legal-protection case runs, and where the product stands

| Practice (source) | In the product | Status |
|---|---|---|
| Report by phone, form, e-mail; file opened; cover check; first contact by a jurist (insurer pages; practitioner checklist law.ch) | Files dropped or added make and update the case; the first contact is due three working days from the report (docs/COVER.md) | met |
| Cover check as its own decision: insured person and capacity, legal area, date of the cause against policy start and waiting period, exclusions (insurers' conditions) | `process/cover.py`, `areas/cover.json`: each cover point with its clause by edition and the fact it rests on; the handler confirms or refuses; a refusal gets its own letter (`process/refusal.py`) | met |
| During a waiting period some insurers give telephone advice only (Coop business conditions) | Not a separate outcome; Protekta's JurLine advises regardless of cover | not built, low value here |
| A deadline the customer must meet leads everything else (Art. 273, 270b, 336b OR; Art. 74 SchKG; Art. 52 ATSG; Art. 354 StPO; defect notices) | `process/urgent.py` with the deadlines of each area module, counted by the rules in docs/AREAS.md; «Frist wahren» is prepared first and cover is examined in parallel | met for the areas shipped |
| Criminal complaint within three months (Art. 31 StGB); land purchase defects 60 days since 1 January 2026 (Art. 219a OR) | No module cites them | open: needs the official text on file and a jurist |
| In-house handling first; a law firm only with the insurer's consent; free choice of lawyer where proceedings need one or interests collide, three proposals after a rejection (AVO Art. 167; conditions) | The stage «Mandat» with the customer's information `A10_kunde` (free choice, consent before instructing, consent before a settlement) | met; the three-proposal step is not a guided sequence |
| Cost guarantee names parties, subject, amount in dispute, fee terms, a ceiling and the instance; a restriction is written and works for the future only; a new guarantee per instance (joint recommendations of insurers and bar association, 2019) | `process/mandate.py`: the mandate package with the cost guarantee (scope chosen by the handler: out of court, with conciliation, first instance; an amount only if entered) and a one-page summary for the firm; the firm's cost claim is checked against it | met in substance; fee terms and a written restriction are free text |
| Refusal for lack of prospects: written reasons at once and the notice of the disagreement procedure; otherwise the need counts as accepted (AVO Art. 169 Abs. 2–3). The procedure covers measures, not cover (BGE 132 III 726) | `A5_aussichtslos` with required parts the screen refuses to drop; the cover refusal is a different letter | met |
| Settlement, payout, bank details, closing (observed in the development dossiers) | `process/settlement.py`, the running account `process/account.py` | met |
| Cash settlement instead of proceedings: the economic interest paid, calculated from the amount in dispute and the litigation risk (Orion, CAP conditions) | Not offered | open: Protekta's own clause must be read first |
| Mediation costs are covered by most insurers | Not a path | open |
| Awarded party costs go back to the insurer up to what it paid (conditions; bar recommendation) | The account records payments; no recovery ledger | open |
| Cancellation after a claim at the latest with the last benefit (VVG Art. 42; ombudsman 2025) | Not handled (a contract matter, not a case step) | out of scope |

Complaints to the ombudsman about legal protection rose from 375 to 660 in 2025 (trade press on the 2025 report); the grounds are not broken down publicly. The consumer survey of lawyers (2016) names the failure patterns a tool can address: slow answers, cost guarantees handled badly, cases wrongly called hopeless, the chosen lawyer rejected. CasePath's answer to each is in the table: dates that lead, the guarantee as a prepared package, the prescribed refusal letter, the customer's information on free choice.

**What practice does not support automating** (and CasePath does not): judging prospects or refusing cover without a person's written reasons; choosing or rejecting the lawyer; closing or cancelling by itself. CasePath prepares; a named person decides and sends.

## B. Data protection and supervision: the rules the product is held to

L = legal requirement, S = supervisory expectation, I = our inference. «Organisation» marks what the insurer, not the software, must do before real use.

| # | Rule | Source | In the product |
|---|---|---|---|
| 1 | L. No refusal, reduction or other adverse decision reaches a customer without a person's decision. A decision that rests on automated processing alone must be disclosed, with the right to be heard and to a review by a person; granting what was asked is exempt | DSG Art. 21 | Nothing is sent by CasePath. Every letter is approved by a named person (`action.approved`, with what stood on the screen: «Stand bei Freigabe»); decisions are asked as decisions and never taken for the handler |
| 2 | L. A refusal for lack of prospects carries reasons and the notice of the procedure, without delay | AVO Art. 169 Abs. 2–3 | Required parts of `A5_aussichtslos`; copy is refused while one is missing |
| 3 | L. The person can be told what was processed, from where, and whether an automated decision existed with its logic, within 30 days | DSG Art. 25 Abs. 2, 7 | Each fact carries its passage; the case report exports the file's state; no automated decision exists (rule 1) |
| 4 | L. Data are destroyed when no longer needed; deletion reaches what was derived | DSG Art. 6 Abs. 4 | Deleting a case removes files, runs, events, edits, drafts and cached translations and reaches the volume; the deletion itself is recorded without content. Model-side retention is the gateway's (Organisation) |
| 5 | L. Who entered or changed what and when can be established; where sensitive data are processed at scale, storing, changing, disclosing, deleting and accessing are logged and the log is kept a year apart from the system | DSV Art. 3 Abs. 3, Art. 4 | The append-only event log per case (opened, source opened, corrected, approved, copied, dispatched, closed) with person and time; keeping it apart for a year is Organisation |
| 6 | L. Privacy notice names the purpose, recipients, countries; record of processing; impact assessment before go-live; processor contract with security check, sub-processors approved | DSG Art. 19, 12, 22, 9, 16 | Organisation. The product helps by running inside the insurer's own workspace with its own model gateway and by sending a model only what a step needs |
| 7 | L. Records that substantiate a payment are kept ten years, changes detectable | OR Art. 958f, GeBüV Art. 3 | The case report and the approval package are exports for the file of record; CasePath is not the archive (Organisation) |
| 8 | L. Handlers and auxiliaries keep secret what they learn | DSG Art. 62 | Need-to-know: a case is opened by its owner, deputy or a reviewer; others see the number and the owner only |
| 9 | S. Central inventory with risk class, owner, purpose, limits, fallback | FINMA Aufsichtsmitteilung 08/2024, 2.1, 2.2, 2.5 | Organisation; the facts for the entry are in docs/DEPLOYMENT.md and the manifest (`/api/manifest`: code, process and Knowledge versions) |
| 10 | S. Tests before release and in operation; analysis of the cases where users ignored or changed the output | 08/2024, 2.4 | The test bed and replay (docs/PARITY.md); «Auswertung» counts corrections per case, their reasons, the same correction made again, and how many letters were approved as prepared |
| 11 | S. What the system says can be explained to the customer and the auditor | 08/2024, 2.6 | Every fact with its passage, every step with its reason («weil»), every rule with its origin and the cases it was applied in (Wissen), the picture of how a step was prepared |
| 12 | S. Responsibility for a decision cannot be delegated to AI | FINMA risk monitor 2023 | Rule 1 |
| 13 | S. A model service that performs an essential function is an outsourcing: approval in the business plan, audit rights, exit plan, early contact with FINMA | FINMA circular 2018/3; AI survey 2025 | Organisation |
| 14 | I. An approval is a real look, not a click: the log holds who approved, when, and what they saw | from 1 | «Stand bei Freigabe»; approval is refused while a decision the letter rests on is open |
| 15 | I. Each run records the model deployment, the process version and the files it read | from 5, 9 | `runs`: deployment, workflow version, files hash, token use |
| 16 | I. Refusals are watched for unequal treatment that cannot be justified | AVO Art. 117 Abs. 2 | «Auswertung» counts cover decisions and refusals; a breakdown by group is not built and would need data CasePath does not hold |
| 17 | I. The customer is told that software helped prepare the letter | EDÖB note of 8 May 2025; DSG Art. 19 | Not in the letters. A decision for Protekta's jurists and data-protection adviser, not for the tool |

Not applicable or not found: FINMA circular 2023/1 (operational risks) addresses banks, not insurers (for insurers VAG Art. 22, 27 and AVO Art. 98 apply); VAG and AVO contain no duty to run complaints handling; the EU AI Act lists risk assessment and pricing in life and health insurance as high-risk (Annex III Nr. 5 Bst. c), not claims handling in legal protection; Switzerland has no AI statute (consultation planned for spring 2027).

## C. The measures on «Auswertung»

Recognised claims measures, applied to a line whose benefit is mostly legal service. Each is computed from the cases, the runs and the event log, without content, and says how many cases it rests on (`quality/auswertung.py`, `operations`).

| Measure | Definition here | Why it is the right one |
|---|---|---|
| Until the first step is prepared | receipt of the case → its first finished preparation (median) | the part of time to first contact that CasePath itself controls |
| Until the first letter is sent | receipt → first dispatch confirmed by the handler (median, days) | time to first contact; Protekta's public promise is three working days |
| Until cover is decided | receipt → the handler's first cover decision (median, days) | time to decision; VVG Art. 41 starts the four weeks only once the insurer can judge the claim |
| From receipt to closing | receipt → the closing that stands (median, days; closed cases) | cycle time; TCS reports an average of 207 days for its cases (2020) |
| Open cases by age | open cases in the bands up to 7, 8–30, 31–90, over 90 days | backlog and ageing |
| Opened and closed in 30 days; opened again | counts; reopened of all cases ever closed | closure ratio and reopen rate |
| Letters approved as prepared | approvals with no word changed, of all approvals with a word count | the override analysis FINMA asks for; with corrections per case, the honest measure of what CasePath saves |
| Cover refused | of cover decisions taken | the basis for watching unequal treatment |

Not measured, on purpose: a straight-through rate (no source supports full automation of legal assessment; CasePath sends nothing by itself), cost per case and cases per jurist (no public figure to anchor them), satisfaction (needs a survey outside the tool).

## Sources

Law: DSG SR 235.1 and DSV SR 235.11; VAG SR 961.01; AVO SR 961.011; VVG SR 221.229.1; OR SR 220 (Art. 958f); GeBüV SR 221.431; StGB SR 311.0 (Art. 321), all on fedlex.admin.ch. Supervision: FINMA Aufsichtsmitteilung 08/2024, circular 2018/3, risk monitor 2023, AI survey of 24 April 2025 (finma.ch); EDÖB note of 8 May 2025 (edoeb.admin.ch); Federal Office of Justice and OFCOM pages on AI regulation; Regulation (EU) 2024/1689. Practice (excerpts only): conditions and service pages of Swiss legal-protection insurers; the joint checklists of the insurance association and the bar association on legal-protection mandates (2019); the insurance ombudsman's annual reports 2024 and 2025; FINMA insurance market report 2024; a consumer magazine's survey of lawyers (2016); industry definitions of cycle time, closure ratio, reopen rate and leakage.
