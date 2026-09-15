# SOURCE SUFFICIENCY GATE

**CasePath benchmark — admission of claim scopes on the basis of publicly readable, verifiable sources**
Compiled 2026-09-15 from five surveyed-then-adversarially-verified source families.

---

## 0. What this gate does and how it was applied

The benchmark tests one chain, per admitted claim scope:

```
public authoritative sources -> process step -> branch condition -> obligation
  -> required fact -> evidence capability -> document requirement
```

A scope is admitted **only** where the public sources themselves carry that structure. Each candidate
scope below is filled in against a fixed record:

- CLAIM SCOPE
- PUBLIC SOURCES AVAILABLE (with URLs and knowledge kind)
- PROCESS STEPS SUPPORTED
- BRANCH CONDITIONS SUPPORTED (quoted)
- OBLIGATIONS SUPPORTED (deadlines shown explicitly, because the admission test requires one)
- DOCUMENT REQUIREMENTS SUPPORTED (named documents)
- IMPORTANT PROCESS ELEMENTS NOT PUBLICLY SUPPORTED
- REDISTRIBUTION POSITION
- VERDICT

**Admission test.** Several process steps; at least two real branch conditions; at least one deadline;
and named document requirements that *differ by branch*. A scope that yields only a flat document list
is rejected however convenient it is. Two candidates below (private liability; valuables/bicycle) clear
parts of the bar and are still rejected, because the document layer does not move with the branch.

**Knowledge kinds are kept separate and separately attributed throughout:**
NORMATIVE (statute, ordinance, cantonal act) / CONTRACTUAL (published policy wording) /
OPERATIONAL (claim forms, public claims guides, authority procedure pages, ombudsman regulations).

**Provenance rules applied to every entry.**
1. Fedlex ELI landing pages (`fedlex.admin.ch/eli/...`) return HTTP 200 and a ~77 kB JavaScript shell
   with **no law text**. Cite the ELI, fetch the `/filestore/.../html/` or `/pdf-a/` twin, pin the
   consolidation date. Any "url_verified: true" against a bare ELI in the upstream surveys is a silent
   failure and has been replaced here.
2. Paragraph pointers in any article containing an `Abs. 1bis` must be re-derived mechanically. A
   systematic off-by-one was found in the upstream material (VVG Art. 60, VMWG Art. 19, ATSG Art. 43),
   twice citing a paragraph that does not exist. **VMWG Art. 19 is the single most load-bearing document
   source in this whole universe, and its pointers were wrong.** Nothing here may be encoded from a
   hand-transcribed pointer.
3. Tabular PDFs (smile, GVB) place parameter blocks *before* their row labels: naive `pdftotext`
   silently mis-assigns every parameter. Ship page images or hand-aligned extracts.
   The BJ federal model forms are XFA: `extract_text()` returns only Adobe's "Please wait..." placeholder;
   the content is in `/Root /AcroForm /XFA`.
4. Filenames are not editions (LAIEN's `16-06-2023` filename vs its in-force date of 01.07.2016;
   AXA's opaque `accesscode` docstore URL can be re-pointed without changing).
5. One published hash in the upstream material is mistranscribed: Beobachter is
   `9b47821a4c7f898828eaeb2f2c6727b04be5c0098f89deef93b4147911fbaa56` (eighth hex digit `a`, not `8`).
   Since hashing *is* the redistribution strategy, that record must be corrected before use.
6. Sources struck on provenance grounds and **not used** in any scope below: the Helvetia 03.2019
   wording (third-party lettings-platform host, PDF producer metadata `ilovepdf.com`, superseded
   edition); GVB Lex 2023 (fourth reproduction of one Coop drafting, tables collapse under extraction).
   Protekta's AVB is admitted **only with an explicit mirror label** — no first-party fetchable URL exists.

**Repository additions required before any admitted scope can be encoded.** The repository's 19 OR
passages are insufficient for four of the ten admitted scopes. Required, all Fedlex and freely
redistributable: **OR Art. 257e** (deposit release — supplies the entire branch structure of S5);
**OR Art. 267 and 267a** (return of the premises; the landlord's immediate-notice duty with forfeiture —
the legal layer of S6, which otherwise would be taken from insurer marketing copy); **VMWG**
Art. 8/9/11/19/19a/20/21/22; **ZPO** Art. 197–213 plus 198(a), 200, 201(2), 243(2)(c), 244(3), 247(2),
113(2)(c)/114; **VVG** Art. 38–46 and 97/98/98a/99/101; **AVO** Art. 161–177; **VAG** Art. 32/33/46(1)(e).
If the deposit-of-rent branch of S4 is used, **OR Art. 259h/259i must be retrieved and verified first** —
no surveyed source covers them, and no deadline may be encoded on that branch until they are read.

---

# PART 1 — ADMITTED SCOPES

---

## S1. Tenancy — contesting a landlord's termination, and extension of the lease

**CLAIM SCOPE**
A residential tenant receives notice of termination and contests it as contestable under OR 271/271a
and/or requests an extension under OR 272, through the conciliation authority and, on failure, the court.

**PUBLIC SOURCES AVAILABLE**
- OR Art. 266l / 266n / 266o (written form, official form, separate notice to a spouse for the family
  home, nullity) and Art. 271 / 272 / 273 — *normative*, already in the repository, Fedlex
  `https://www.fedlex.admin.ch/eli/cc/27/317_321_377/de` (fetch the filestore twin).
- VMWG Art. 9 (mandatory content of the termination form) — *normative*, Fedlex, Stand 1.10.2025:
  `https://www.fedlex.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/1990/835_835_835/20251001/de/html/fedlex-data-admin-ch-eli-cc-1990-835_835_835-20251001-de-html.html`
- ZPO Art. 197–213, 243(2)(c), 244(3), 247(2) — *normative*, Fedlex, Stand 1.1.2025:
  `https://www.fedlex.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/2010/262/20250101/de/html/fedlex-data-admin-ch-eli-cc-2010-262-20250101-de-html.html`
- Kanton Bern, "Als Mieter/in gegen eine Kündigung vorgehen" — *operational*:
  `https://www.zsg.justice.be.ch/de/start/themen/zivilrecht/mietrecht/beendigung-mietvertrag/mieter-in-vorgehen-gegen-kuendigung.html`
- Kanton Aargau, Schlichtungsgesuch für Wohn- und Geschäftsräume, Stand 25.11.2024 — *operational*,
  sha256 `588ae9817d29420c10f1145c7607ff2867fbcb5ebd8403a7136e8f71242735aa`:
  `https://www.ag.ch/media/kanton-aargau/jb/dokumente/schlichtungsbehoerden/schlichtungsbehoerden-fuer-miete-und-pacht/schlichtungsformular-stand-25-11-2024.pdf`
- Genève, Commission de conciliation en matière de baux et loyers + the *Requête-type congé /
  prolongation* — *operational*:
  `https://justice.ge.ch/fr/contenu/commission-de-conciliation-en-matiere-de-baux-et-loyers` ;
  `https://justice.ge.ch/media/form/2021-02/Requete-type-conge-prolongation-bail-CBL.pdf`
- Ticino, "La locazione" (mandatory-form rule with its nullity consequence) — *operational*:
  `https://www4.ti.ch/poteri/giudiziario/locazione/la-locazione`
- Kanton Zürich / Basel-Stadt official-form hosting pages — *operational*:
  `https://www.zh.ch/de/direktion-der-justiz-und-des-innern/generalsekretariat/formulare-mietwesen.html`
- BJ federal model Schlichtungsgesuch — *operational*, XFA:
  `https://www.bj.admin.ch/dam/de/sd-web/PVuVZprOkJiP/schlichtungsgesuch.pdf`
- Solothurn, Allgemeines Merkblatt zum Schlichtungsverfahren 02.25 — *operational*:
  `https://so.ch/fileadmin/internet/ddi/ddi-ds/Oberaemter/Dokumente/Merkblatt_Schlichtungsverfahren_Version_02.25.pdf`

**PROCESS STEPS SUPPORTED**
(1) Receipt of the termination on the cantonally approved official form; (2) determination of the date of
receipt under the three-limb receipt rule; (3) optional demand that the landlord give reasons
(VMWG 9(1)(c)); (4) filing of the Schlichtungsgesuch within 30 days at the authority for the place where
the premises lie; (5) immediate service on the opposing party with simultaneous summons (ZPO 202(3));
(6) hearing within two months before a parity panel (ZPO 203(1), 200(1)), the authority also acting as a
statutory advice service (ZPO 201(2), VMWG 21(2)); (7) production of documents / inspection at the
hearing (ZPO 203(2)); (8) outcome — recorded settlement (208), Entscheidvorschlag (210(1)(b)) or
Klagebewilligung (209); (9) 20-day rejection window (211(1)); (10) filing in court within 30 days with the
Art. 244(3) annexes; (11) if the challenge is dismissed the court examines extension ex officio (Bern).

**BRANCH CONDITIONS SUPPORTED**
- Receipt rule (Bern): *"Als Erhalt gelten der Empfang im Briefkasten, die Übergabe durch die Post oder
  der erste Tag, an dem Sie die Sendung mit einer Abholungseinladung auf der Post abholen könnten."*
- Form nullity (Ticino, stating the consequence expressly): *"occorre far capo obbligatoriamente ai
  moduli allestiti dal Dipartimento delle istituzioni, pena la nullità delle relative notifiche."*
  Content of that form is fixed by VMWG Art. 9(1): *"a. die Bezeichnung des Mietgegenstandes …;
  b. den Zeitpunkt, auf den die Kündigung wirksam wird; c. den Hinweis, dass der Vermieter die Kündigung
  auf Verlangen des Mieters begründen muss; d. die gesetzlichen Voraussetzungen der Anfechtung der
  Kündigung und der Erstreckung des Mietverhältnisses (Art. 271–273 OR); e. das Verzeichnis der
  Schlichtungsbehörden und ihre örtliche Zuständigkeit."* — each element checkable, each absence feeding
  nullity.
- Family-home branch (OR 266n/266o, repository): a separate notice to each spouse, failing which the
  termination is void — a second, independent nullity route keyed to a civil-status fact.
- Extension excluded (Bern): *"Wenn die Vermieterin oder der Vermieter den Mietvertrag insbesondere wegen
  Zahlungsrückstand oder schwerer Verletzung der Pflicht zur Sorgfalt und Rücksichtnahme gekündigt hat,
  ist eine Erstreckung ausgeschlossen."*
- Fixed vs indeterminate term (Genève, printing OR 273): 30 days from receipt (art. 273 al. 2 let. a CO)
  *"ou au plus tard 60 jours avant l'expiration du contrat lorsqu'il s'agit d'un bail de durée
  déterminée"*; second prolongation *"au plus tard 60 jours avant l'expiration de la première"*.
- Entscheidvorschlag available (ZPO 210(1)(b)): *"sofern die Hinterlegung von Miet- und Pachtzinsen, der
  Schutz vor missbräuchlichen Miet- und Pachtzinsen, der Kündigungsschutz oder die Erstreckung des Miet-
  und Pachtverhältnisses betroffen ist"*; on rejection the Klagebewilligung goes to the rejecting party
  (211(2)(a)); if the action is not filed in time the proposal *"gilt als anerkannt"* (211(3)).
- Representation of the landlord (ZPO 204(3)(c)): the Liegenschaftsverwaltung may appear only if
  *"zum Abschluss eines Vergleichs schriftlich ermächtigt"*.
- Default (ZPO 206(1)): claimant default means the request *"gilt als zurückgezogen"*.

**OBLIGATIONS SUPPORTED**
File within **30 days of receipt** (OR 273 / Bern); appear **personally** (ZPO 204(1)); produce documents
the authority calls for (ZPO 203(2)); file the statutory annexes (ZPO 244(3)); observe the **20-day**
rejection window (ZPO 211(1)) and the **30-day** Klagefrist (ZPO 209(4): *"In Streitigkeiten aus Miete und
Pacht von Wohn- und Geschäftsräumen … beträgt die Klagefrist 30 Tage."*). Authority-side: hearing within
**two months**, procedure closed at the latest after **twelve months** (ZPO 203(1)/(4)). Landlord-side:
use the official form, give reasons on request, serve a separate notice on a spouse.
Aargau adds a filing obligation: *"Die Parteien haben das Schlichtungsgesuch sowie alle Belege und
Urkunden in Papierform und im Doppel einzureichen. Reichen sie von den Urkunden und Belegen immer Kopien
und keine Originale ein."*

**DOCUMENT REQUIREMENTS SUPPORTED**
- Always: the **lease** (Aargau: *"Mietvertrag (sollte dieser nicht mehr vorliegen, so ist dies
  anzugeben)"*; Genève: *"toutes les pièces utiles, notamment le contrat de bail"*), plus documents on any
  contract changes.
- Termination branch (Aargau, verbatim): *"Die angefochtene Kündigung sowie allenfalls Mahnschreiben und
  falls vorhanden eine Kopie des Couverts"* — the **envelope copy** is a document requirement produced
  directly by the receipt-date branch.
- Representation branch: *"eine Vollmacht oder den Verwaltungsvertrag"* (Aargau) / ZPO 244(3)(a).
- Court stage: **Klagebewilligung** or the declaration that conciliation is waived (ZPO 244(3)(b)) plus
  *"die verfügbaren Urkunden, welche als Beweismittel dienen sollen"* (244(3)(c)).
- Copy counts are **canton-conditioned** and genuinely divergent: Aargau two, Zug four, the federal model
  one per party plus one for the authority, Genève one per party plus one for the commission.

**IMPORTANT PROCESS ELEMENTS NOT PUBLICLY SUPPORTED**
What evidence establishes hardship under OR 272 (no public enumeration anywhere in the universe — the
extension branch reaches "obligation" but not "document requirement"); how the Schlichtungsbehörde
internally triages, assigns or prepares a file; the application of the receipt rule to a second delivery
attempt; case law on what makes a termination contestable under OR 271; the competent authority per
commune outside the cantons surveyed (VMWG Art. 22 obliges cantons to publish, but the instruments were
not retrieved).

**REDISTRIBUTION POSITION**
OR, VMWG and ZPO are freely reusable — URG Art. 5(1)(a) verified verbatim: *"Durch das Urheberrecht nicht
geschützt sind: a. Gesetze, Verordnungen, völkerrechtliche Verträge und andere amtliche Erlasse"*. The
cantonal forms, the Bern/Ticino/Zurich pages, the Solothurn leaflet and the BJ model are **URL + hash +
short quoted extract only** (none is an amtlicher Erlass; the Aargau page 3 is expressly marked
"diese Seite ist nicht einzureichen"). Pin Aargau by hash — it is the one artefact already drafted to
post-1.1.2025 ZPO (it uses "Entscheidvorschlag", Fr. 10'000 and Fr. 2'000 correctly).

**VERDICT: ADMIT** — and this is the strongest scope in the universe (see §11.1).

---

## S2. Tenancy — challenging a rent increase, a unilateral contract change, or the initial rent

**CLAIM SCOPE**
A tenant receives an increase or other unilateral change on the official form under OR 269d, or wishes to
challenge the initial rent under OR 270, and contests it as abusive under OR 269/269a within 30 days
(OR 270b).

**PUBLIC SOURCES AVAILABLE**
- OR Art. 269a, 269d, 270b — *normative*, repository, Fedlex (note OR 269d Abs. 4–5 in force 1.10.2025,
  AS 2025 197).
- VMWG Art. 11, 19, 19a, 20 — *normative*, Fedlex, Stand 1.10.2025 (filestore URL as S1). **Re-derive all
  paragraph pointers: Art. 19 contains an Abs. 1bis and every upstream pointer was off by one.**
- ZPO Art. 197–213 (esp. 209(1)(a), 210(1)(b), 211), 244(3) — *normative*, Fedlex, Stand 1.1.2025.
- Aargau Schlichtungsgesuch (per-remedy enclosure table) — *operational*, hash as S1.
- Genève request templates (13 per-remedy forms) — *operational*.
- Zürich / Basel-Stadt official-form pages (forms in the `formulare-neu-ab-nov2025/` path; BS labelled
  "Version ab 1. Oktober 2025") — *operational*.
- Ticino "La locazione" (mandatory form for art. 269d CO notifications, with nullity) — *operational*.

**PROCESS STEPS SUPPORTED**
(1) Service of the increase on the cantonal official form, observing the notice period; (2) optional
demand by the tenant for a **numerical** breakdown of the claimed differential (VMWG 20(1));
(3) contestation at the conciliation authority within 30 days (OR 270b); (4) service and summons
(ZPO 202); (5) hearing within two months, with a right to demand the supporting Belege (VMWG 20(2));
(6) outcome: settlement / Entscheidvorschlag / Klagebewilligung — with the **role reversed**
(ZPO 209(1)(a)); (7) 20-day rejection; (8) filing in court within 30 days with Art. 244(3) annexes.

**BRANCH CONDITIONS SUPPORTED**
- Form content and its defect branch (VMWG Art. 19(1)(a)): the form must state
  *"1. den bisherigen Mietzins und die bisherige Belastung des Mieters für Nebenkosten; 2. den neuen
  Mietzins …; 3. den Zeitpunkt, auf den die Erhöhung in Kraft tritt; 4. die klare Begründung der
  Erhöhung. Werden mehrere Erhöhungsgründe geltend gemacht, so sind diese je in Einzelbeträgen
  auszuweisen; 5. bei Mehrleistungen die Angabe, ob der Vermieter Förderbeiträge für wertvermehrende
  Verbesserungen erhält"*, plus (c) *"1. die gesetzlichen Voraussetzungen der Anfechtung; 2. das
  Verzeichnis der Schlichtungsbehörden und ihre örtliche Zuständigkeit"*. Defect feeds OR 269d(2) nullity.
- Covering-letter branch (VMWG Art. 19 **Abs. 1bis**): if the reasons are given in an accompanying letter,
  the form must expressly point to that.
- Indexed lease (VMWG Art. 19 Abs. 2): *"darf die Mitteilung frühestens nach der öffentlichen Bekanntgabe
  des neuen Indexstandes erfolgen"*.
- Staggered rent (VMWG Art. 19a, in force 1.10.2025): *"Bei gestaffelten Mietzinsen darf die schriftliche
  Mitteilung frühestens vier Monate vor Eintritt jeder Mietzinserhöhung erfolgen."*
- Initial rent, cantonal branch (VMWG Art. 19 Abs. 3): where a canton has made the form compulsory under
  OR 270(2), it must **additionally** state the reference interest rate and the consumer price index level
  applicable to the previous rent.
- Role reversal (ZPO 209(1)(a)): the Klagebewilligung goes *"bei der Anfechtung von Miet- und
  Pachtzinserhöhungen: dem Vermieter oder Verpächter"* — the opposite party bears the 30-day burden.
- Deadline-interaction rule (VMWG Art. 20(1)): a demand for numerical substantiation does not extend the
  clock — *"Die 30-tägige Anfechtungsfrist wird dadurch nicht berührt."*
- Justification route (VMWG Art. 11(1)): a comparator rent is admissible only for premises comparable
  *"nach Lage, Grösse, Ausstattung, Zustand und Bauperiode"* — five required facts that select which
  evidence is capable of supporting the landlord's ground.
- Entscheidvorschlag availability (ZPO 210(1)(b)) covers *"der Schutz vor missbräuchlichen Miet- und
  Pachtzinsen"* — note the Zug cantonal page **silently omits this category**; do not read the rule off it.

**OBLIGATIONS SUPPORTED**
Contest within **30 days** (OR 270b); landlord must serve on the official form with itemised clear
reasons; **four months** earliest notification for staggered increases (VMWG 19a); **20 days** to reject an
Entscheidvorschlag (ZPO 211(1)); **30 days** to file in court (ZPO 209(4)); hearing within **two months**
(ZPO 203(1)). Landlord must, on demand, produce *"für alle geltend gemachten Gründe der
Mietzinserhöhung die sachdienlichen Belege"* in the conciliation procedure (VMWG 20(2)).

**DOCUMENT REQUIREMENTS SUPPORTED**
- Always: the lease; **the contested official form itself** (the instrument whose defect founds nullity).
- Increase branch (Aargau): the contested increase **plus all prior contract changes** — because the
  admissible calculation depends on the rent last validly fixed.
- Reference-rate-reduction branch (Aargau): the tenant's letters to the landlord and any replies, plus all
  prior contract changes.
- Justification branch: the numerical breakdown (VMWG 20(1)) and the **sachdienliche Belege** per ground
  (VMWG 20(2)); for a comparator-based ground, documentation of the five Art. 11(1) attributes.
- Initial-rent branch: the cantonal initial-rent form carrying the reference interest rate and CPI level.
- Court stage: Vollmacht, Klagebewilligung, available Urkunden (ZPO 244(3)).

**IMPORTANT PROCESS ELEMENTS NOT PUBLICLY SUPPORTED**
The substantive calculation of an admissible rent (yield, cost-based and comparator methods are case law
and practice, not text); which documents *prove* a comparator (Art. 11 names attributes, not evidence);
the conciliation authority's internal preparation; whether a given canton has made the initial-rent form
compulsory (cantonal instrument, not retrieved for most cantons).

**REDISTRIBUTION POSITION**
OR + VMWG + ZPO freely redistributable (URG 5(1)(a)) — this scope's entire normative and document-content
layer is shippable in full, which is unusual. Only the cantonal enclosure table and the form templates are
URL + hash + extract.

**VERDICT: ADMIT** — closest rival to S1 and the better choice if the benchmark wants a role-reversal
discriminator that cannot be guessed from the general rule.

---

## S3. Tenancy — arrears under OR 257d, and the eviction fork that follows

**CLAIM SCOPE**
The landlord sets a payment deadline under OR 257d with warning of termination, terminates on expiry, and
the tenant does not hand back the premises; or the tenant contests the termination.

**PUBLIC SOURCES AVAILABLE**
- OR Art. 257d — *normative*, repository (written payment deadline of at least 30 days for residential
  premises, with warning of termination), plus OR 266l/266o and 271–273.
- ZPO Art. 198 lit. a, 244(3), 209(4), 257 route (summary/clear cases) — *normative*, Fedlex 1.1.2025.
- Kanton Bern, "Mieterausweisung (Exmission)" — *operational*:
  `https://www.zsg.justice.be.ch/de/start/themen/zivilrecht/mietrecht/mieterausweisung.html`
- Kanton Bern, "Als Mieter/in gegen eine Kündigung vorgehen" — *operational* (extension excluded on
  arrears).
- BJ model "Gesuch um Rechtsschutz in klaren Fällen" — *operational*, XFA:
  `https://www.bj.admin.ch/de/formulare-fuer-parteieingaben`
- Aargau Schlichtungsgesuch (termination row includes Mahnschreiben) — *operational*.

**PROCESS STEPS SUPPORTED**
(1) Written payment demand with a deadline of at least 30 days and an express warning of termination;
(2) service and expiry; (3) termination on the official form; (4) either the tenant contests within
30 days, or (5) the landlord pursues return of the premises via one of three routes: clear-case summary
protection, enforcement of an existing title, or ordinary conciliation; (6) for the clear-case route,
conciliation **falls away entirely** by ZPO Art. 198 lit. a.

**BRANCH CONDITIONS SUPPORTED**
- Route selection (Bern): *"Ist der Sachverhalt unbestritten oder kann er sofort durch Dokumente bewiesen
  werden und ist die Rechtslage klar … Dies ist zum Beispiel bei Kündigungen wegen Zahlungsverzugs der
  Fall."* — an **evidence capability determines which process applies**: the cleanest such node anywhere
  in this universe.
- The statutory hinge the Bern page does not state, and which must be supplied from statute:
  ZPO Art. 198 lit. a — *"Das Schlichtungsverfahren entfällt: a. im summarischen Verfahren"*.
- Existing-title route (Bern): a Vollstreckungsgesuch where validity and end date were *"bereits in einem
  Vergleich vor der Schlichtungsbehörde oder dem Gericht, in einem Urteilsvorschlag oder in einem
  Gerichtsentscheid festgehalten"*.
- Extension barred (Bern): *"Wenn die Vermieterin oder der Vermieter den Mietvertrag insbesondere wegen
  Zahlungsrückstand … gekündigt hat, ist eine Erstreckung ausgeschlossen."*
- Jurisdiction sub-branch (Bern): the court of the Gerichtsregion where the premises lie, with commercial
  premises exceptionally going to the Handelsgericht.

**OBLIGATIONS SUPPORTED**
Landlord: a **written** demand, a deadline of **at least 30 days** (residential), an express warning of
termination, then termination on the official form. Tenant: **30 days** to contest (OR 273); personal
appearance; annexes under ZPO 244(3). Court route: no conciliation in the summary track.

**DOCUMENT REQUIREMENTS SUPPORTED**
Branch-differentiated and genuinely so:
- Clear-case route: the documents that prove the facts *immediately* — the lease, the OR 257d demand
  showing the deadline and the warning, proof of its service, the termination on the official form, and
  proof of continued non-payment. (Bern expressly declines to specify; the set is derived from OR 257d's
  own elements, which is precisely the reasoning the benchmark wants.)
- Enforcement route: the Vergleich, Entscheidvorschlag or Gerichtsentscheid itself.
- Conciliation route: Schlichtungsgesuch plus the Aargau enclosure set, which for terminations names
  *"Die angefochtene Kündigung sowie allenfalls Mahnschreiben und falls vorhanden eine Kopie des
  Couverts"*.

**IMPORTANT PROCESS ELEMENTS NOT PUBLICLY SUPPORTED**
What "sofort durch Dokumente bewiesen" requires in practice — the Bern page explicitly declines
(*"ist es empfehlenswert, juristischen Rat zu suchen"*); the enforcement authority's own procedure; the
Betreibungs interface (SchKG not retrieved); the court's internal handling.

**REDISTRIBUTION POSITION**
OR + ZPO freely redistributable. Bern pages and BJ models URL + hash + extract; the BJ clear-case model is
XFA and must be extracted from `/Root /AcroForm /XFA`. Note the Bern page still uses the pre-2025 term
"Urteilsvorschlag".

**VERDICT: ADMIT**

---

## S4. Tenancy — defects, rent reduction, damages and deposit of rent (OR 259a / 259g)

**CLAIM SCOPE**
The tenant notifies a defect, demands remedy, and — on failure — reduces the rent, claims damages, or
deposits the rent with the office designated by the canton, then asserts claims at the conciliation
authority.

**PUBLIC SOURCES AVAILABLE**
- OR Art. 259a and 259g — *normative*, repository, Fedlex. **Dependency: OR 259h/259i are not covered by
  any surveyed source; they must be retrieved and verified before any deadline is encoded on the
  deposit branch.**
- ZPO Art. 197–213 (esp. 210(1)(b) covering *"die Hinterlegung von Miet- und Pachtzinsen"*), 244(3),
  247(2)(b) — *normative*, Fedlex 1.1.2025.
- Aargau Schlichtungsgesuch (per-remedy enclosure table, defect row) — *operational*, hashed.
- Genève templates (consignation and its release; réduction de loyer) — *operational*.
- Assista/TCS AVB Art. 5.3(a) — *contractual*, relevant where the dispute is run under legal-expenses
  cover (low-quantum branch).
- Solothurn Merkblatt (Mitwirkungspflicht, ZPO 160–165 restated; the authority *"kann von sich aus bei den
  Parteien die Herausgabe wesentlicher Urkunden verlangen"*) — *operational*.

**PROCESS STEPS SUPPORTED**
(1) Written notification of the defect to the landlord; (2) setting a deadline to remedy; (3) on failure,
election among remedy, reduction, damages, or deposit of rent; (4) deposit with the designated office and
notification to the landlord; (5) assertion of claims at the conciliation authority; (6) hearing with
document production and possible Augenschein (ZPO 203(2)); (7) Entscheidvorschlag available on the
deposit branch (ZPO 210(1)(b)); (8) 20-day rejection, 30-day Klagefrist, Art. 244(3) annexes.

**BRANCH CONDITIONS SUPPORTED**
- Remedy-first condition (OR 259g, repository): deposit is available only after a written deadline to
  remedy has been set and has passed — the branch that distinguishes a valid deposit from an unlawful
  withholding of rent.
- Entscheidvorschlag (ZPO 210(1)(b)) available where the deposit of rent is concerned; on rejection the
  Klagebewilligung goes to the rejecting party (211(2)(a)) and, if the action is not filed in time, the
  proposal *"gilt als anerkannt"* (211(3)).
- Ex officio fact-finding (ZPO 247(2)(b)(1)) extends to other tenancy disputes up to CHF 30'000 —
  materially changing what the claimant must produce.
- Legal-expenses overlay (Assista Art. 5.3(a)): internal advice is covered irrespective of quantum, but
  external services only from CHF 2'000 — *"Liegt der Streitwert unter CHF 2'000.–, besteht ein
  Versicherungsschutz für externe Leistungen, falls der Versicherte gerichtlich belangt wird und dabei
  die Gegenpartei durch einen Anwalt vertreten wird."* Two **conjunctive** conditions revive cover: a
  low-quantum rent-reduction defence is exactly the shape that tests this.

**OBLIGATIONS SUPPORTED**
Notify the defect; set a written remedy deadline before depositing; appear personally; produce the
documents the authority calls for (ZPO 203(2), Solothurn). Deadlines: **20 days** to reject an
Entscheidvorschlag; **30 days** Klagefrist (ZPO 209(4)); hearing within **two months**, procedure closed
within **twelve months** (ZPO 203). No court vacations apply in conciliation (Solothurn).

**DOCUMENT REQUIREMENTS SUPPORTED**
- Defect branch (Aargau, verbatim): *"Mängelschreiben und Antworten, Fotos, Rechnungen"* — a
  branch-specific set that differs sharply from the termination row and the Nebenkosten row on the same
  form.
- Always: the lease; contract-change documents.
- Deposit branch: the deposit confirmation from the designated office (the office is cantonal; the
  artefact is named by the process, not enumerated in any surveyed source — flag as a derivation, not a
  citation).
- Nebenkosten branch (same form): the contested statements plus documents received, with the tenant
  required to state what is disputed.
- Court stage: Vollmacht, Klagebewilligung, available Urkunden (ZPO 244(3)).

**IMPORTANT PROCESS ELEMENTS NOT PUBLICLY SUPPORTED**
The quantum of a rent reduction (practice, not text); what makes a defect "schwer" vs "mittelschwer";
OR 259h/259i forfeiture of deposited rents (unverified — must not be encoded until retrieved); the
designated deposit office per canton; the landlord's internal repair process.

**REDISTRIBUTION POSITION**
OR + ZPO freely redistributable. Aargau, Genève, Solothurn URL + hash + extract. Assista AVB
(sha256 `37e0f51e…`) URL + hash + extract, copyrighted.

**VERDICT: ADMIT** — conditional on retrieving OR 259h/259i before the deposit branch is used.

---

## S5. Tenancy — release of the rent deposit (Kaution) at the end of the tenancy

**CLAIM SCOPE**
The tenancy has ended; the tenant seeks release of a bank deposit under OR 257e or of a deposit-guarantee
certificate, and the landlord either consents, asserts a claim, or stays silent.

**PUBLIC SOURCES AVAILABLE**
- **OR Art. 257e** — *normative*, Fedlex, **not currently in the repository and required**. It supplies
  the entire branch structure of this scope in freely redistributable law.
- SwissCaution, AVB Mietkautionsversicherung für einen Privatmietvertrag, Ausgabe 12.2023 — *contractual*,
  sha256 `6cc63dbd4a46a295a43baacf8552f164efda3f3fa9eb5fdc0d7224c458dfc1be`:
  `https://static.swisscaution.ch/docs/cga/bh/current/CGA_PDF_BH_DE.pdf`
- SwissCaution, "Wie kann Ihre Mietkaution freigegeben werden?" — *operational*:
  `https://www.swisscaution.ch/de/blog/post/wie-kann-ihre-mietkaution-freigegeben-werden/`
- Allianz Wohnungsübergabe-Checkliste (the deposit payout request as a completion criterion) —
  *operational*, sha256 `00f8455f0cf27f79b337f7f3b90d87b7aa43392a63752ac9a759e78b5b2e95e1`.
- Aargau Schlichtungsgesuch (Rechtsbegehren menu includes release of the deposit) — *operational*.
- ZPO Art. 197–213, 243(2)(c), 244(3) — *normative*.

**PROCESS STEPS SUPPORTED**
(1) End of tenancy and handover; (2) tenant requests release, countersigned where the provider requires
it; (3) provider informs the landlord; (4) landlord either consents, asserts a claim, or does nothing;
(5) where the landlord asserts a claim without agreement, he must produce an enforceable title;
(6) after one year of inaction the tenant may demand release; (7) escalation ladder where the landlord
stalls — registered letter naming the amount, then the guarantee insurer or bank, then *"die zuständige
Schlichtungsstelle für das Mietwesen"*, then the Mietgericht.

**BRANCH CONDITIONS SUPPORTED**
- Statutory three-way branch (OR 257e Abs. 3, verbatim): *"Die Bank darf die Sicherheit nur mit Zustimmung
  beider Parteien oder gestützt auf einen rechtskräftigen Zahlungsbefehl oder auf ein rechtskräftiges
  Gerichtsurteil herausgeben. Hat der Vermieter innert einem Jahr nach Beendigung des Mietverhältnisses
  keinen Anspruch gegenüber dem Mieter rechtlich geltend gemacht, so kann dieser von der Bank die
  Rückerstattung der Sicherheit verlangen."*
- Counter-deadline running against the **other** party (SwissCaution Art. 4 Ziff. 2 lit. c, verbatim):
  *"Nach dessen Erhalt informiert SwissCaution Ihren Vermieter. Falls dieser nicht innerhalb von 14 Tagen
  den Nachweis erbringt, dass er … gerichtlich gegen Sie vorgegangen ist, oder eine Betreibung eingeleitet
  hat, entfällt die Verpflichtung von SwissCaution von Rechts wegen."*
- Title-quality branch (SwissCaution Art. 5 Ziff. 2): the Zahlungsbefehl must be *"vollstreckbar und nicht
  ganz oder teilweise mit einem Rechtsvorschlag belegt"*, or be supplemented by a definitive judgment
  removing the Rechtsvorschlag.
- Sub-tenancy branch (Art. 1 Ziff. 4a): guarantees for sub-tenancies are excluded only *"ohne die
  schriftliche Zustimmung des Vermieters"* — conditional, not absolute.
- Co-tenant branch (Art. 3): joint and several liability, each co-tenant empowered to bind the others.
- Cost branch (Art. 1 Ziff. 3): on a draw-down the tenant must reimburse plus *"CHF 100.- an
  Verwaltungskosten"*.

**OBLIGATIONS SUPPORTED**
Tenant: request release and, per Art. 7 Ziff. 3, *"Es liegt in Ihrer Verantwortung, gegebenenfalls die
notwendigen Formalitäten beim Vermieter zu erfüllen, damit SwissCaution die Bestätigung des Endes der
Mietkaution erhält."* Landlord: assert any claim legally within **12 months**, and within **14 days** of
being informed produce proof that he has sued or commenced Betreibung. Ancillary: **30 days** to pay a
premium, **14-day** formal payment deadline on default, **14-day** withdrawal right, **30 days'** notice to
change the AVB. Conciliation overlay: **30-day** Klagefrist (ZPO 209(4)).

**DOCUMENT REQUIREMENTS SUPPORTED** — this is the cleanest branch-to-document mapping in the tenancy half
- Consent branch: the dated **original certificate signed by both tenant and landlord**
  (*"doppelte Unterschrift erforderlich"*), and on termination the certificate returned *"versehen mit
  einer Freigabeerklärung des Vermieters"*.
- Enforcement branch: the **original Zahlungsbefehl or a certified copy**, expressly including
  *"(Beweisstücke über die Schuld wie Reparaturrechnungen betreffend den Schaden an der Wohnung
  inbegriffen)"* — which ties this scope directly to S6's handover-damage evidence.
- Judgment branch: a definitive, legally binding **original judgment or certified copy**.
- One-year branch: proof that the tenancy ended and the object was vacated more than a year ago.
- Escalation branch: the **Einschreiben naming the deposit amount**; the countersigned *Freigabeantrag*
  addressed directly to the insurer or bank; the **Wohnungsabgabeprotokoll** as the trigger document.
- Conciliation branch: lease, the Aargau baseline enclosures, Vollmacht.

**IMPORTANT PROCESS ELEMENTS NOT PUBLICLY SUPPORTED**
The bank's or guarantee provider's internal release workflow; the Betreibungsamt's procedure (SchKG not
retrieved — only OR 257e's own naming of Zahlungsbefehl and Gerichtsurteil is grounded; *Rechtsvorschlag*
is an imported concept); the substantive standard for what the landlord may deduct (that is S6);
cantonal supplementary rules permitted by OR 257e Abs. 4.

**REDISTRIBUTION POSITION**
OR 257e freely redistributable and load-bearing — the statutory branch must be cited from Fedlex, **not**
from the SwissCaution blog, which restates it loosely (it describes the judgment as one *"in dem eine
Geldstrafe verhängt wird"*, importing a criminal-law term that does not belong). SwissCaution AVB and blog
are copyrighted: URL + hash + short extract. The AVB is a two-column PDF requiring a column-aware parse.

**VERDICT: ADMIT**

---

## S6. Tenancy — handover damage and the tenant's liability, under private liability cover

**CLAIM SCOPE**
At the end of the tenancy the landlord alleges damage or excessive wear; the tenant's liability is
assessed against normal wear and time value, and the tenant's private liability insurer is notified.

**PUBLIC SOURCES AVAILABLE**
- **OR Art. 267 and 267a** — *normative*, Fedlex, **not currently in the repository and required**.
  Without them this scope's legal layer would be taken from insurer marketing copy, which the brief
  forbids.
- Allianz Suisse, Merkblatt "SCHÄDEN AN MIETSACHE", Ausgabe 0918 — *operational*, sha256
  `d248fe6d4480630a6166149c91adf870d6a04599ab838abc13e890e960287b26`:
  `https://www.allianz.ch/content/dam/onemarketing/azch/common/allianz/de/allianz-haushaltsversicherung-merkblatt-schaeden_mietsachen.pdf`
  (403 to bare curl; a browser User-Agent is required).
- Allianz Wohnungsübergabe-Checkliste, Ausgabe 1120 — *operational*, sha256 `00f8455f…`.
- Mieterinnen- und Mieterverband, Lebensdauertabelle page (computation rule and worked example) —
  *mixed, private inter-association standard*:
  `https://www.mieterverband.ch/mietrecht/unterlagen-und-tools/lebensdauertabelle/`
- SVV SLK-Empfehlung Nr. 1/2013, Mieterschäden bei Versichererwechsel — *operational, non-binding*:
  `https://svv.ch/sites/default/files/media/documents/2022-12/2013_01_Empfehlung%20Mieterschaden%20bei%20Versichererwechsel.pdf`
- CSS Privathaftpflicht AVB Form. 518_d, Ausgabe 02.2024 — *contractual*:
  `https://www.css.ch/content/dam/css/de/documents/privatkunden/richtig-versichert/avb/518_d_avb_privathaftpflicht.pdf`
- VVG Art. 38, 38a, 39, 45 — *normative*, Fedlex Stand 1.1.2024 (filestore).

**PROCESS STEPS SUPPORTED**
(1) Prepare the handover: clear and clean, perform the *kleiner Unterhalt*, notify the administration
early of larger damage; (2) attend the handover **personally**; (3) inspect against the move-in protocol;
(4) sign, refuse to sign, or sign with defined reservations; (5) do **not** place repair orders;
(6) refuse offsetting against the deposit; (7) notify the liability insurer and, where applicable, the
legal-expenses insurer; (8) the insurer conducts negotiations with the landlord; (9) quantify at time
value using the lifespan table.

**BRANCH CONDITIONS SUPPORTED**
- Landlord forfeiture (OR 267a Abs. 1/2, verbatim): *"Bei der Rückgabe muss der Vermieter den Zustand der
  Sache prüfen und Mängel, für die der Mieter einzustehen hat, diesem sofort melden."* … *"Versäumt dies
  der Vermieter, so verliert er seine Ansprüche, soweit es sich nicht um Mängel handelt, die bei
  übungsgemässer Untersuchung nicht erkennbar waren."* — a deadline expressed as a standard, with
  forfeiture, and a hidden-defect carve-out that allocates an evidential burden.
- Normal wear (OR 267 Abs. 1): *"Der Mieter muss die Sache in dem Zustand zurückgeben, der sich aus dem
  vertragsgemässen Gebrauch ergibt"*; Abs. 2 voids advance agreements to pay beyond actual damage.
- Signature branch (Allianz): *"Unterzeichnen Sie nur dann, wenn die im Protokoll aufgeführten Mängel
  tatsächlich vorhanden sind … Wenn das Protokoll aus Ihrer Sicht nicht korrekt ist, unterzeichnen Sie es
  nicht oder nur mit klar definierten Vorbehalten betreffend die strittigen Punkte."*
- Maintenance-scope branch (Allianz): *"Sobald ein Fachbetrieb beigezogen werden muss, ist es kein kleiner
  Unterhalt mehr."*
- Cover branch (Allianz): *"Nicht versichert sind Schäden, die allmählich entstehen (z.B. vergilbte Wände
  aufgrund starken Rauchens) oder zu erwarten sind"*, nor reversal of tenant alterations.
- Amortisation branch (MV): *"Ist die Lebensdauer ganz abgelaufen, muss die Mieterschaft keine Kosten mehr
  übernehmen."* Computation stated in words: *"zieht man von der Lebensdauer des Gegenstands das
  tatsächliche Alter des Gegenstands ab"*; worked example — a 6-year Spannteppich against a 10-year life,
  tenant pays 40%.
- Which insurer handles it (SLK 1/2013, verbatim): *"1. Die Schadenregulierung gegenüber dem Vermieter
  wird … von demjenigen Versicherer vorgenommen, mit welchem der Mieter im Zeitpunkt der Schadenmeldung in
  einem laufenden Versicherungsvertragsverhältnis steht. 2. Vorbehalten bleiben Schäden, die dem
  Vorversicherer bereits gemeldet wurden …"* — the **date of notification**, not the date of damage,
  selects the counterparty.
- Conduct prohibition (CSS 518_d cl. 28(b)): no direct negotiation, acknowledgement, settlement or payment
  without the insurer's consent; sanction under VVG 45(1) with the (a)/(b) exculpation defences.

**OBLIGATIONS SUPPORTED**
Tenant: attend personally; return in contract-conforming condition; notify the insurer on acquiring
knowledge (VVG 38(1)) and, on request, answer every question (VVG 39(1)); take no step that binds the
insurer. Landlord: inspect and notify defects **sofort**, on pain of forfeiture (OR 267a). The only
numeric deadlines in this scope come from the policy side (e.g. CSS 518_d cl. 27: **24 hours** where the
event results in death; **14 days** to terminate after a claim) and from any legal-expenses wording layered
on top (Generali/Fortuna: **10 days** to produce documents, on pain of release from liability).

**DOCUMENT REQUIREMENTS SUPPORTED**
- Preparation branch: *"Nehmen Sie das Übernahmeprotokoll des Einzugs und die Mietvertragsunterlagen mit"*
  — the **move-in protocol** and the **lease documents**.
- Disputed-point branch: *"Machen Sie Fotos zu den strittigen Punkten (z.B. Parkettstellen, Wände)"* — and
  the handover protocol carrying the written reservations.
- Quantification branch: item age and lifespan evidence for each contested item (MV table), and where the
  tenant performed work, the receipts and logged hours.
- Insurer branch: on request a valued inventory of the affected items plus **Originalbelege**
  (CSS 518_d cl. 8(c); CSS 519_d cl. 8(c) on the contents side).
- Deposit-interaction branch: the payout request for the full deposit amount (Allianz checklist:
  *"Antrag auf Auszahlung des vollumfänglichen Betrags des Mietkautionskontos wurde gestellt"*).
- Insurer-change branch (SLK): the notification date, which determines which insurer's file applies.

**IMPORTANT PROCESS ELEMENTS NOT PUBLICLY SUPPORTED**
What "sofort" means numerically in OR 267a (case law); the insurer's internal assessment of excessive
wear; current lifespan figures — the free MV page is expressly *"ein Auszug"*, the full 83-page brochure
costs CHF 12.80, the table was revised with effect from 1 February 2024, and no surveyed source verified a
single current figure (the Allianz 8-year Anstrich example is from a 2018 leaflet and the publisher is a
downstream adopter of the same standard, not an independent witness).

**REDISTRIBUTION POSITION**
OR 267/267a freely redistributable. The Allianz leaflets, the CSS AVB and the SLK recommendation are
URL + hash + extract. **The MV/HEV lifespan table is a paywalled private standard and cannot be shipped at
all** — only the computation rule and the one published worked example may be quoted. The prices in the
table are MV-only (*"Die kursiv gesetzten Richtpreisangaben … sind nicht Bestandteil der paritätisch
festgelegten Richtwerte"*); only the lifespans are parity-agreed. Do **not** cite the
mietkautionschweiz.ch K-Tipp reprint as MV/HEV or K-Tipp text: its most-quoted sentences are a deposit
vendor's own wrapper page, and the reprint is two revisions stale.

**VERDICT: ADMIT** — with the standing caveat that the quantification half of the chain terminates in a
private, non-redistributable standard whose current figures are unverified.

---

## S7. Legal-expenses insurance — cover confirmation, refusal, and the disagreement procedure
### (instantiated on a Swiss tenancy dispute)

**CLAIM SCOPE**
An insured with a private legal-expenses policy notifies a tenancy dispute; the insurer checks cover,
grants or refuses a cost undertaking, and the insured either proceeds, invokes the contractual
disagreement procedure, or self-funds.

**PUBLIC SOURCES AVAILABLE**
*Normative, redistributable spine:*
- AVO Art. 161–170 (Rechtsschutzversicherung) — Fedlex, cite the ELI
  `https://www.fedlex.admin.ch/eli/cc/2005/735/de`, fetch
  `…/eli/cc/2005/735/20260101/de/html/fedlex-data-admin-ch-eli-cc-2005-735-20260101-de-html-4.html`
- VAG Art. 32 (and Art. 46(1)(e); AVO Art. 117 on abuse) — Fedlex filestore, Stand 1.1.2024.
- VVG Art. 38, 38a, 39, 40, 41, 44, 45, 46, 97/98/98a/99/101 — Fedlex filestore, Stand 1.1.2024.
*Contractual, seven independent drafting families (URL + hash + extract only):*
- Fortuna/Generali AVB Rechtsschutz Privat 02.2024, sha256 `ccfe7cfc…` —
  `https://www.generali.ch/content/dam/generali/pdf/produktdokumente/avb-ki/rechtsschutz/avb-rechtsschutz-privat-de.pdf`
- Coop Rechtsschutz AVBPP24, sha256 `a21c9fca…` —
  `https://www.cooprecht.ch/de/crs_avb_privatrechtsschutz-paket_web_de/`
- Protekta/Mobiliar 01.2026, sha256 `652fc87e…` — **mirror only**, label it as such:
  `https://mzo.ch/wp-content/uploads/Mobiliar-AVB-RS-01.26.pdf`
- AXA-ARAG 2021, sha256 `6f0d8db7…` — `https://www.axa.ch/servlets/external/docstoredocument?accesscode=aguy3`
- Orion Private (DE/FR/IT/EN parallel), sha256 `c45eb116…` —
  `https://www.orion.ch/storage/files/shares/Produkte/Orion_Private/de/AVB%20Orion%20Private.pdf`
- Dextra Flex 05.2022, sha256 `39d6f437…` —
  `https://dextra.ch/assets/content/documents/AVB-Privatpersonen-Flex-2022_DE.pdf`
- Assista/TCS 2011 (Ausgabe 2025), sha256 `37e0f51e…` —
  `https://www.tcs.ch/mam/Digital-Media/PDF/Terms-and-Conditions/avb-privatrechtsschutz-2011-de-2025.pdf`
*Variants (same carriers, for parameter contrast only — never as corroboration):* Beobachter
(sha256 `9b47821a4c7f898828eaeb2f2c6727b04be5c0098f89deef93b4147911fbaa56`), smile/Helvetia,
Orion-for-HEV (sha256 `e9c2c419…`), Zurich (sha256 `7e63a6e0…`).
*Operational:* CAP Checkliste (sha256 `614cc8d9…`); Protekta "Rechtsfall melden"
(`https://protekta.mobiliar.ch/rechtsfall-melden`); the Orion Fallanmeldung published by CSS
(sha256 `70a9613d…`, **patient/foreign legal protection only**); Ombudsman Reglement + filing page.

**PROCESS STEPS SUPPORTED**
(1) Notification of the case (channel and medium prescribed per wording: Dextra *online* and electronic;
Orion to a named Rechtszentrum, all other correspondence to the Basel head office; Generali in writing or
text form); (2) the insurer discusses further steps and decides internal vs external handling; (3) the
insurer must inform the insured of the free-choice right, and where claims handling is not outsourced must
do so *"mittels Brief mit Zustellnachweis unverzüglich"* after receiving the claim notification
(AVO 163); (4) document production and grant of powers of attorney and secrecy release; (5) consent gate
before instructing counsel, initiating proceedings, settling or appealing; (6) Kostengutsprache, which may
be limited in amount, time and procedural stage; (7) on refusal, a reasoned written position pointing to
the disagreement procedure (AVO 169(2)); (8) arbitration or expert assessment within the contractual
window; (9) self-funding with reimbursement if the insured beats the insurer's stated view (AVO 169(4)).

**BRANCH CONDITIONS SUPPORTED**
- The keystone (AVO Art. 169(3), verbatim): *"Sieht der Versicherungsvertrag kein Verfahren nach Absatz 1
  vor oder unterlässt es das Versicherungsunternehmen …, die versicherte Person im Zeitpunkt der Ablehnung
  der Leistungspflicht darüber zu informieren, so gilt das Rechtsschutzbedürfnis der versicherten Person im
  entsprechenden Fall als anerkannt."* — a procedural omission by the insurer converts directly into cover.
- Free choice (AVO Art. 167(1)): *"a. falls im Hinblick auf ein Gerichts- oder Verwaltungsverfahren ein
  Rechtsvertreter oder eine Rechtsvertreterin eingesetzt werden muss; b. bei Interessenkollisionen."*
- Secrecy-waiver override (AVO Art. 168): the clause *"ist nicht anwendbar, wenn ein Interessenkonflikt
  besteht und die Weitergabe der verlangten Information an das Versicherungsunternehmen für die
  versicherte Person nachteilig sein kann"* — a normative rule overriding a clause every wording imposes,
  and directly testable against the Orion claim form's signed waiver.
- Policy-dependent parameter (Dextra, verbatim): *"Die Wartefrist hängt davon ab, welche Leistungsoptionen
  (0, 30, 60 Tage) gewählt wurden. Die gewählte Wartefrist ist in der Police festgehalten."* — an agent
  reasoning from public material **must** conclude the policy document is required.
- Advice is not cover (Dextra F2(e)): *"Berät und unterstützt Dextra die versicherte Person vorbehaltlos,
  gilt dies nicht als Deckungszusage."*
- Document forfeiture (Generali C1 Art. 2): *"Fortuna kann dafür eine Frist von 10 Tagen ansetzen. Wird
  dieser Aufforderung nicht nachgekommen, ist Fortuna von der Leistungspflicht befreit."*
- Escalating document forfeiture (Orion for HEV): *"Reicht der Versicherte die Akten trotz Aufforderung der
  Orion nicht ein, setzt ihm diese eine angemessene Frist, unter der Androhung, dass der
  Versicherungsanspruch untergeht, wenn die Akten nicht fristgemäss und vollständig eingereicht werden."*
- Cost-advance forfeiture (Orion E6(1)): *"Wird der Kostenvorschuss von einer Partei nicht geleistet,
  anerkennt diese damit die Rechtsauffassung der Gegenpartei."*
- Capacity branch (tenant vs landlord): Generali covers tenancy *"sofern das Mietobjekt von der
  versicherten Person selbst bewohnt bzw. selbst genutzt wird"* and landlord capacity only under the paid
  *"Zusatzoption: Mietrecht als Vermieter"*; smile R.2.1.5 makes landlord-side cover *"gold: CHF 3'000"* /
  *"silver: nicht versichert"*; Coop 16.6 restricts self-occupied properties with more than three units;
  AXA-ARAG B1 insures additional self-used units *"mit einem Miet- oder Pachtzins bis max. CHF 500 pro
  Monat … ohne Aufführung in der Police"*.
- Low-quantum branch (Assista 5.3(a)) with the two conjunctive revival conditions quoted at S4.
- Post-termination notification window (AXA-ARAG A4): notification within the policy term or
  *"spätestens drei Monate nach Beendigung des Versicherungsvertrags"*.
- Normative overlay on all of the above: VVG Art. 45(1)(a)/(b) exculpation; VVG Art. 45(3) faultless
  late performance; VVG Art. 46(2) invalidating shorter contractual time restrictions **subject to the
  express reservation of Art. 39(2)(2)**; VVG Art. 39(2)(1) limiting required documents to those
  obtainable *"ohne erhebliche Kosten"*.

**OBLIGATIONS SUPPORTED**
Notify promptly; transmit all case-relevant documents completely and truthfully; hand over items of
evidence without delay; grant powers of attorney and release counsel from professional secrecy; obtain
consent before any step; observe the disagreement window. **Deadlines, divergent across wordings:**
document production 10 days (Generali) or an "angemessene Frist" under warning (Orion/HEV);
disagreement window **14 days** (Dextra), **20 days** (Protekta, Orion, AXA-ARAG), **90 days** (Generali,
Assista), **silent** (the whole Coop family); waiting periods 0 / 30 / 60 (Dextra, policy-recorded),
60 days or 0 (Generali Basic/Top), 3 months tenancy (Coop, Beobachter, smile, Orion-HEV), none stated
(AXA-ARAG — see the correction below); AXA-ARAG 3 months after contract end to notify.

**DOCUMENT REQUIREMENTS SUPPORTED**
- **The policy** — the only place the waiting period, the product tier (gold/silver, Basic/Top) and the
  module composition live. This is the scope's signature derivation: the public sources *say* the answer
  is in a document the public does not have.
- The AVB edition in force for that contract.
- Named document classes: *"Korrespondenz, Bussenverfügungen, Vorladungen und Entscheide"* (Protekta);
  *"Sämtliche mit dem Fall zusammenhängende Akten wie Bussenverfügungen, Vorladungen, Urteile,
  Korrespondenzen usw."* (Orion), with Orion's purpose clause making the set a function of the questions
  asked — *"die zur Beurteilung der Versicherungsdeckung oder der Prozessaussichten nötigen Unterlagen"*.
- Protekta's first-party reporting page enumerates a **wider** set than its own AVB:
  *"Verfügungen von Gerichten, Verträge, Korrespondenzen, Offerten, Auftragsbestätigungen, AGB, Rapporte,
  Rechnungen, Quittungen, Bewilligungen, Einsprachen oder Fotos"* — for a tenancy case the additions that
  matter are the lease, Bewilligungen, Einsprachen and the invoices for a reduction quantum.
- Powers of attorney; the secrecy-release declaration.
- Insurer-side artefacts that become evidence: the AVO 163 registered letter, the reasoned written
  refusal, the Kostengutsprache, the Schadenanzeigeformular (AVO 166(3) requires the free-choice right to
  be highlighted *in the claim notification form itself*).

**IMPORTANT PROCESS ELEMENTS NOT PUBLICLY SUPPORTED**
Everything insurer-internal: intake, triage, file opening, allocation, reserving, the **method** by which
prospects of success are assessed (AVO 169 requires reasons and a procedure, never a method), internal
escalation, service standards. There is **no public tenancy legal-expenses claim form** anywhere: the one
public Orion Fallanmeldung is scoped to patient and foreign legal protection and its medical and traffic
fields must not seed a tenancy document list. CAP's own private AVB is not obtainable first-party.

**REDISTRIBUTION POSITION**
AVO, VAG and VVG shippable in full (URG 5(1)(a) — limb (a) expressly names *Verordnungen*). Every AVB,
the CAP checklist, the claim form and the insurer pages are copyrighted: **URL + hash + short quoted
extract**, with three specific fragility warnings — AXA's `accesscode` URL can be silently re-pointed at a
new edition; Coop's stable redirect resolves to a dated upload path that will move; Protekta has **no**
first-party fetchable URL at all.

**VERDICT: ADMIT** — and this is the scope that carries the two-wordings experiment (see §11.2).

---

## S8. Household contents — theft

**CLAIM SCOPE**
Insured household contents are stolen; the policyholder notifies the insurer and the police, substantiates
existence and value, and the insurer pays, reduces or declines.

**PUBLIC SOURCES AVAILABLE**
- VVG Art. 38–41, 45, 46 — *normative*, Fedlex filestore, Stand 1.1.2024.
- CSS Hausratversicherung AVB Form. 519_d, Ausgabe 02.2024 — *contractual*, sha256
  `cce8948157d794094847da343b09b9bdce1e4789e4bcd8d3511c06f952426c1d`:
  `https://www.css.ch/content/dam/css/de/documents/privatkunden/richtig-versichert/avb/519_d_avb_hausratversicherung.pdf`
- CSS Schadenanzeige Hausrat / Gebäude, Form. 15d-08.26 — *operational*, sha256
  `262da3f4791623ac05fdb723012dcfc4131189f150a8ff6418881172f130d356`:
  `https://www.css.ch/content/dam/css/de/documents/privatkunden/richtig-versichert/formulare/15_d_formular_schadenanzeige_hausrat.pdf`
- SVV Musterbedingungen Hausratversicherung 2022 — *contractual, non-binding model*:
  `https://svv.ch/sites/default/files/media/documents/2024-02/AVB%20Hausratversicherung%202022.pdf`
- Simpego Home AVB 12.2024 — *contractual*: `https://simpego.ch/dam/AVB_Simpego_Home_de.pdf`
- AXA Haushaltversicherung AVB 10.2021 — *contractual*, sha256 `c6bd6d66…`:
  `https://www.axa.ch/servlets/external/docstoredocument?accesscode=ag58y`
- Generali Haushaltversicherung AVB — *contractual*:
  `https://www.generali.ch/content/dam/generali/pdf/produktdokumente/avb-ki/hausrat-haftpflicht/avb-haushaltversicherung-de.pdf`
- Suisse ePolice theft wizard — *operational*, **settled negative**: `https://www.suisse-epolice.ch/theft-case`

**PROCESS STEPS SUPPORTED**
(1) Mitigate and preserve (VVG 38a, 38b); (2) notify the police *unverzüglich* and request an official
investigation; (3) leave the Tatspuren untouched without police consent; (4) notify the insurer;
(5) classify the loss on the claim form; (6) compile a valued inventory of the affected items;
(7) produce original receipts and, on demand, the police report; (8) declare other insurance;
(9) insurer determines quantum (CSS cl. 29; SVV F2 parties / joint expert / Sachverständigenverfahren);
(10) payment four weeks after the insurer has sufficient information (VVG 41(1)); (11) on declination,
the contractual forfeiture or limitation regime.

**BRANCH CONDITIONS SUPPORTED**
- Peril branch inside one wording (CSS 519_d cl. 8): the a)–e) duties apply to every loss, then
  *"Bei Diebstahl hat der Versicherungsnehmer ferner:"* opens f)–h) — notify the police *umgehend*,
  request an official investigation, do not remove or alter Tatspuren without police consent,
  cooperate on identifying the perpetrator, report recovered goods — and *"Ein entsprechender
  Polizeirapport kann durch die CSS einverlangt werden."*
- Same branch in the market model (SVV F1): *"Bei Diebstahl oder Beraubung hat er zusätzlich:"* …
- Same branch again (AXA I3.2): *"Bei Diebstahl hat die versicherte Person die Polizei unverzüglich zu
  benachrichtigen. Ohne Zustimmung der Polizei darf er die Tatspuren nicht entfernen oder verändern."*
- Value branch that defeats cover (Simpego exclusion 15): scheduled valuables or single objects with an
  insurance value of at least CHF 1'000 are excluded *"wenn im Schadenfall keine Quittung oder ein
  Wertgutachten eines Sachverständigen vorgewiesen werden kann"*.
- Consent-threshold branch (Simpego cl. 6): repairs need consent where costs are expected to exceed
  CHF 500.
- Burden branch (CSS cl. 29(a)): *"Der Versicherungsnehmer muss die Schadenhöhe beweisen. Die
  Versicherungssummen bilden keinen Beweis für das Vorhandensein sowie den Wert der versicherten Sachen."*
- Maturity suspension (SVV E8): maturity is suspended while it is unclear who is lawfully entitled, or
  while the police or investigating authorities are investigating.
- Sanction branch (VVG 45(1)(a)/(b)) with the burden on the policyholder to prove absence of causal
  influence; AXA J4.1 preserves that defence verbatim — *"Keine Kürzung erfolgt, wenn der
  Anspruchsberechtigte beweist, dass das Verhalten den Schaden nicht beeinflusst hat."*
- Bicycle sub-branch (CSS form 3.9): *"War das Fahrrad abgeschlossen? Ja / Nein"* plus Rahmennummer.
- Double-insurance branch (CSS form §6, *"in jedem Fall auszufüllen"*).

**OBLIGATIONS SUPPORTED**
Notify police and insurer; preserve the scene; produce an inventory and receipts on request; answer truthfully
(the form's signed declaration enacts VVG Art. 40). **Deadlines:** VVG 41(1) **four weeks** to maturity;
VVG 46(1) **five-year** limitation; SVV E9 a **two-year forfeiture** — *"Lehnt der Versicherer die
Entschädigungsforderung ab, muss sie der Anspruchsberechtigte innert 2 Jahren nach Eintritt des
Ereignisses gerichtlich geltend machen, andernfalls er seine Rechte verliert (Verwirkung)"* — **triggered
by declination but running from the EVENT**; SVV F3 **14 days** to appoint an expert; CSS has no
forfeiture clause at all.

**DOCUMENT REQUIREMENTS SUPPORTED**
- Every loss: a signed valued inventory of the items present before and after and of the damaged items
  (CSS cl. 8(c); SVV F1: *"auf Ersuchen ein unterzeichnetes Verzeichnis … mit Wertangaben zu erstellen,
  wobei der Versicherer angemessene Fristen ansetzen kann"*), plus **Originalbelege** — the CSS form makes
  this unconditional on its face: *"bitte Originalkaufbelege beilegen"*.
- Theft branch only: the **police report**, evidencing the four facts the form demands —
  *Anzeigeerstatter, Anzeigedatum, Polizeiposten, Polizeibeamter*.
- Valuables branch (Simpego): a **Quittung or a Wertgutachten** — here the document is a precondition of
  cover, not a filing step.
- Bicycle branch: purchase receipt, frame number, a detailed estimate with photograph (Generali).
- Third-party-causer branch (CSS form 3.5/3.6): the liable party's insurer name and policy/claim number.
- Payment: payee and IBAN.

**IMPORTANT PROCESS ELEMENTS NOT PUBLICLY SUPPORTED**
**What the police require for, or issue as, a theft report.** This is a settled negative: the Suisse
ePolice wizard's first step (an eight-category *"Was wurde gestohlen?"* triage) and two
*Vorabklärungen* gates are publicly visible, but everything after is behind *"Um mit Ihrer Meldung
weiterfahren zu können, müssen Sie sich zuerst anmelden"*, and material behind registration is not public
and therefore inadmissible here. The benchmark must stop at "the claimant must produce a police report
evidencing those four facts". Also unsupported: insurer-internal fraud triage; the loss adjuster's method;
any notification day-count (VVG 38 has a relative trigger only — *"sobald er von diesem Ereignisse und
seinem Anspruche aus der Versicherung Kenntnis erlangt"* — so "notify within N days" is always a contract
fact, never a statutory one).

**REDISTRIBUTION POSITION**
VVG shippable. Every AVB, the SVV model and the CSS form are copyrighted: URL + hash + extract. Note two
provenance caveats: the SVV Hausrat model is **no longer listed on SVV's own Musterbedingungen index**
(reachable only by direct URL — label it "2022 model wording retrieved by direct URL"), and it is
self-described as *"unverbindliche Musterbedingungen"*. German-language searches for Swiss claim forms
return predominantly **German** insurers governed by German law — a live contamination risk for anyone
extending this corpus.

**VERDICT: ADMIT** — strongest single-insurer chain in the insurance half (VVG 39(2)(1) → CSS 519_d
cl. 8(c)/8(f)/29(a) → CSS form §1 classification → §3.7 receipts → §4 police-report facts).

---

## S9. Household contents — fire and natural hazard, across the private-market / cantonal-monopoly fork

**CLAIM SCOPE**
Contents are damaged by fire or a natural hazard. Depending on the canton and the object, the claim runs
against a private insurer under the VVG plus the compulsory AVO regime, or against a cantonal public-law
establishment under cantonal statute.

**PUBLIC SOURCES AVAILABLE**
- AVO Art. 171–177 (compulsory fire and natural-hazard cover) — *normative*, Fedlex, Stand 1.1.2026:
  `https://fedlex.data.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/2005/735/20260101/de/pdf-a/fedlex-data-admin-ch-eli-cc-2005-735-20260101-de-pdf-a.pdf`
- VAG Art. 33 — *normative*, Fedlex filestore.
- VVG Art. 38–41, 45, 46 — *normative*.
- SVV Musterbedingungen Hausrat 2022 (clause E7 reproduces AVO Art. 176 almost verbatim) —
  *contractual*.
- CSS 519_d, AXA Haushalt, Generali Haushalt, Simpego Home — *contractual*.
- Nidwalden, Sachversicherungsgesetz NSVG (NG 867.1) — *normative, cantonal*, via lexfind:
  `https://www.lexfind.ch/tolv/63249/de`
- Vaud, LAIEN 963.41 — *normative, cantonal*:
  `https://www.eca-vaud.ch/files/202306/loi-assurance-batiment-mobilier-incendie-elements-naturel-LAIEN-16-06-2023.pdf`
  (in force since 01.07.2016 — the filename is **not** the edition).
- ECA Vaud "Déclarer un sinistre" and its FAQ — *operational*: `https://www.eca-vaud.ch/sinistre/`

**PROCESS STEPS SUPPORTED**
Private track: mitigate → notify → preserve the state of the damaged objects until the loss is determined
(VVG 38b) → inventory and substantiate → determination (parties / joint expert / Sachverständigenverfahren)
→ maturity four weeks after sufficient information (VVG 41(1)).
Nidwalden track: report use changes within a month (Art. 49) → notify the loss *unverzüglich nach
Feststellung* (Art. 51) → mitigate (Art. 52) → make no change to the damaged object (Art. 53) → assessment
→ Einsprache within 20 days (Art. 66).
Vaud/ECA track: declare by portal, telephone or the dedicated address → immediate self-help (ventilate and
dry, photograph, engage a specialist cleaner, obtain a quote) → three-expert evaluation where the parties
disagree (Art. 51) → contest a decision within ten days (Art. 68(1)) → reconstruct within two years
(Art. 57(1)).

**BRANCH CONDITIONS SUPPORTED**
- Objective peril threshold (AVO Art. 173(2), verbatim): *"Als Sturm gilt ein Wind von mindestens 75 km/h,
  der in der Umgebung der versicherten Sachen Bäume umwirft oder Gebäude abdeckt."* — the single most
  concrete required-fact / evidence-capability pair in this universe: wind speed from MeteoSwiss, or the
  felled-trees / stripped-roofs proxy from dated photographs.
- Single-event rule (AVO Art. 176(4)): *"Zeitlich und räumlich getrennte Schäden bilden ein Ereignis, wenn
  sie auf die gleiche atmosphärische oder tektonische Ursache zurückzuführen sind"* — determines how many
  CHF 500 deductibles apply (Art. 175(1)); Art. 176(5) requires the contract to have been in force at the
  event's inception.
- Causation exclusions (AVO Art. 173(3)): subsidence, poor building ground, faulty construction, deficient
  maintenance, omitted protective measures, groundwater, recurrent watercourse flooding, sewer backflow,
  earthquake and volcanic eruption — each a checkable negative.
- Compulsory coupling (AVO Art. 171(1) with VAG 33(1)): an insurer covering the fire risk must also cover
  natural hazards at full value — with the Art. 172(1) enumerated exceptions.
- Two-condition late-notice branch (NSVG Art. 51(2)): refusal or reduction only *"soweit infolge schuldhaft
  verspäteter Anzeige die Ursache oder das Ausmass des Schadens nicht mehr zweifelsfrei festgestellt werden
  kann"* — culpable lateness alone is insufficient.
- Absolute forfeiture (NSVG Art. 51(3)): *"Der Entschädigungsanspruch erlischt in jedem Fall, wenn der
  Schaden nicht binnen Jahresfrist seit dem Schadenereignis gemeldet wird."*
- Proportionality cap (LAIEN Art. 58(3)): *"La réduction est proportionnée à la gravité de la faute; elle
  ne peut excéder la moitié de l'indemnité."*
- Water-origin branch (ECA): *inondation* vs *dégât d'eau* — cover turns on the origin of the water,
  because ECA covers natural elements but not ordinary escape of water.
- Peril routing out of the monopoly (GVZ, for the neighbouring building line): *"Schäden infolge von
  Leitungsbruch, Rückstau, Grundwasser oder undichten Konstruktionen, sowie Schäden an Mobiliar sind nicht
  bei der GVZ versichert."*

**OBLIGATIONS SUPPORTED**
Notify; mitigate; preserve; prove. **Deadlines:** NSVG — one month for use changes, *unverzüglich* for the
loss, **one year absolute forfeiture**, **20 days** Einsprache. LAIEN/ECA — **two-year prescription**
(Art. 67(1): *"Toute prétention à une indemnité se prescrit par deux ans dès la date du sinistre"*),
**two years** to reconstruct (Art. 57(1)), **ten days** to contest (Art. 68(1)). Private — VVG 41(1) four
weeks; VVG 46(1) five years; SVV E9 two years from the event; SVV F3 14 days to appoint an expert.

**DOCUMENT REQUIREMENTS SUPPORTED — and they diverge by regime, which is the point**
- Private market: valued inventory before and after; **original purchase receipts**; repair firm, address,
  telephone, estimate and offers for building damage; year of construction (CSS form §3.8).
- Vaud/ECA: photographs or videos of the damage; **devis** from approved contractors; **quittances
  d'achat for materials the insured buys when doing the work themselves**; logged hours for self-performed
  work — and, expressly, **no purchase receipts for the contents themselves**: *"Sur le principe, nous
  n'avons pas besoin de la quittance d'achat des biens faisant partie de votre inventaire avant sinistre.
  Nos prestations en cas de dommages sont calculées sur la valeur de rachat de vos biens."*
- Vaud statute: *"de fournir toutes pièces nécessaires motivant son droit à l'indemnité"* (Art. 48(1)(3))
  — open-textured, naming nothing.
- Nidwalden: **no document whatsoever is named in the statute**. A genuine negative: this track carries a
  case only to the obligation and required-fact layer, never to the document layer, unless an
  establishment-side artefact is separately retrieved.

**IMPORTANT PROCESS ELEMENTS NOT PUBLICLY SUPPORTED**
The private insurer's internal loss-adjustment; how MeteoSwiss data is obtained and admitted; the cantonal
establishments' internal assessment beyond their published steps; whether the ECA's dedicated declaration
e-mail address is what an upstream survey asserted (the page does not print one — do not cite it); and the
GVZ telephone-report facts list, which **is not on the page it was attributed to**.

**REDISTRIBUTION POSITION**
AVO, VAG, VVG shippable. NSVG and LAIEN are amtliche Erlasse and therefore redistributable, but both were
retrieved from an aggregator (lexfind) and from the establishment's own copy respectively — record the
provenance, since the cantons' own registers are JavaScript applications. ECA's web copy is **not** an
amtlicher Erlass: URL + retrieval date + short quotation. AVO Art. 175/176 being reproduced almost verbatim
in SVV clause E7 gives a demonstrable normative-to-contractual derivation whose statutory half ships free
and whose contractual half does not.

**VERDICT: ADMIT**

---

## S10. Escalation to the Ombudsman of Private Insurance after a refusal

**CLAIM SCOPE**
A private insurer has refused or reduced a claim; the insured escalates to the neutral ombudsman rather
than, or before, going to court.

**PUBLIC SOURCES AVAILABLE**
- Reglement für die Ombudsstelle, approved 15.12.2025, in force 1.01.2026, replacing the 2024 edition —
  *operational*: `https://versicherungsombudsman.ch/wp-content/uploads/2026/01/OM-reglement-de.pdf`
- Leitlinien zu Kommunikation, Verhalten und KI-Nutzung — *operational*, **incorporated by reference into
  the Reglement's cooperation gate, therefore not optional**:
  `https://versicherungsombudsman.ch/wp-content/uploads/2026/01/OM-leitlinien_de.pdf`
- Beschwerdeformular — *operational*:
  `https://versicherungsombudsman.ch/wp-content/uploads/2021/10/Beschwerdeformular.pdf`
- "Beschwerde einreichen" filing-requirements page — *operational*:
  `https://versicherungsombudsman.ch/beschwerde-einreichen/`
- FAQ — *operational*, carries the only stated intake-triage sequence in the universe:
  `https://versicherungsombudsman.ch/haeufig-gestellte-fragen/`
- "Angebot" numbered procedure — *operational*: `https://versicherungsombudsman.ch/angebot/`
- FINMA "Sie haben ein Problem mit einer Versicherung" (forum-selection boundary) — *normative context*:
  `https://www.finma.ch/de/finma-public/fragen-und-probleme/zu-einer-versicherung/`
- Ombudsstelle Krankenversicherung (routing target for health cover) — *operational, partially verified
  lead*: `https://om-kv.ch/beratung-anfordern/`

**PROCESS STEPS SUPPORTED**
(1) Complain to the insurer in writing and demand a written answer; (2) wait for it; (3) if none within
four weeks, send a Mahnung with its own deadline; (4) if still none, send copies of the unanswered letters;
(5) file by the Beschwerdeformular by post or the online platform — *"Eingaben per E-Mail werden nicht
entgegengenommen"*; (6) the office checks **jurisdiction**, then whether the facts show
*Anhaltspunkte … wonach ein Fehlverhalten des Versicherers vorliegen könnte*, then whether mediation
appears futile from the outset — three ordered gates before it approaches the insurer at all; (7) written
mediation; (8) on failure, the office communicates the insurer's reasoning, may confirm its own contrary
view, and may recommend recourse to the courts and/or a lawyer, informing the insurer of that
recommendation.

**BRANCH CONDITIONS SUPPORTED**
- Time-bar gate: the office acts only *"solange die bestehenden Forderungen … nicht bereits verjährt oder
  verwirkt sind"*.
- Representation gate: no action where applicants *"durch einen Rechtsanwalt, eine Rechtsschutzversicherung
  oder anderweitig, namentlich durch eine Fachperson in Versicherungsfragen, professionell vertreten
  sind"*, with re-entry *"nach definitiver Niederlegung des Mandats durch die involvierte Vertretung"*.
  **This makes S7 and S10 mutually exclusive on the same file** — which escalation route is open turns on
  whether legal-expenses cover was confirmed or refused.
- Litigation gate: nothing *"die vor Vermittlungsämtern oder Gerichten rechtshängig sind, oder zu denen
  bereits eine Frist zur Einreichung einer Einsprache (UVG/MVG) oder einer Beschwerde (UVG/MVG) läuft"*.
- Supervisory gate: nothing *"welche in die Zuständigkeit der Aufsichtsbehörden fallen"* — the mirror image
  of the FINMA boundary, which supplies its own testable criterion: an abuse exists where disadvantages
  *"sich wiederholen oder einen breiten Personenkreis betreffen könnten"*.
- Cooperation gate: *"Die Ombudsstelle kann das Eintreten auf ein Anliegen von der angemessenen Mitwirkung
  abhängig machen und Fristen setzen"*, with the content of "angemessene Mitwirkung" fixed by the
  Leitlinien, whose stage-3 measures are themselves a branch set: restricting channels, restricting
  frequency, *"Unterbrechung der Bearbeitung bis zur notwendigen Mitwirkung"*, and
  *"Einstellung oder Ablehnung der Vermittlungstätigkeit"*.
- Conditional document procurement (FAQ): the office will obtain missing documents from the insurer only
  *"Sofern Sie erfolglos schriftlich versucht haben, fehlende Unterlagen vom Versicherer erhältlich zu
  machen"*.
- Subject-matter routing: health and supplementary health go to the separate Ombudsstelle
  Krankenversicherung; social insurance (AHV/IV/EO) is out of scope entirely.

**OBLIGATIONS SUPPORTED**
File the complete file unprompted or on request; cooperate in establishing the facts; use the prescribed
channel. **Deadlines:** wait **four weeks** for the insurer's written answer, then a self-set Mahnfrist;
the office may set its own deadlines to expedite. And the decisive **negative** deadline rule, which is
what makes this scope worth encoding at all: *"Die Anrufung der Ombudsstelle hat keine
verjährungsunterbrechende Wirkung und hemmt den Lauf von Fristen nicht"*, with responsibility expressly on
the applicant *"insbesondere auch für diejenigen, deren Ablauf bei Einreichen der Beschwerde unmittelbar
droht"*. Against the repository's OR 270b and OR 273 windows that is decisive: escalating does **not**
preserve a tenancy deadline.

**DOCUMENT REQUIREMENTS SUPPORTED**
- Always (filing page, verbatim): *"die Personalien der Beschwerde führenden Person; das Ziel, das Sie mit
  der Beschwerde erreichen wollen (z. B. Zahlung eines bestimmten Geldbetrages, Vertragsauflösung); eine
  kurze Beschreibung des Sachverhalts; den Namen der Versicherungsgesellschaft; wichtige Unterlagen (z.B.
  Vertragsunterlagen, Korrespondenzen)"*.
- Form checklist: *"Versicherungspolice oder Vorsorgereglement"*; *"Allgemeine Versicherungsbedingungen
  oder Reglement"*; *"Korrespondenzen mit der Versicherung inkl. schriftliche Stellungnahme"*;
  *"Weitere Unterlagen zum Sachverhalt"*; a signed Vollmacht where a private person represents.
- **Answered branch:** the insurer's **written reasoned position** — a precondition, since
  *"ist nebst Ihrer Beschwerde auch eine schriftliche Stellungnahme des Versicherers zu den strittigen
  Fragen notwendig"*.
- **Unanswered branch:** copies of the unanswered letters and the Mahnung instead.
- Evidence types named by the FAQ: *"Arztberichte, Schadenfotos, Rechnungen, schriftliche Beweise"*.

**IMPORTANT PROCESS ELEMENTS NOT PUBLICLY SUPPORTED**
What the insurer must do in response (nothing binding); any enforceable timetable; what the underlying
contents, liability or tenancy claim required in the first place; the office's internal case handling
beyond the three published gates. The FAQ is undated, unversioned web prose and must be pinned by content
hash plus retrieval date; where it and the Reglement differ, the Reglement wins.

**REDISTRIBUTION POSITION**
A private foundation's procedural regulation and web copy — **not** an amtlicher Erlass, so URL + hash +
short extract only. Version churn is real: the Reglement replaced the 2024 edition on 1.1.2026, while the
Beschwerdeformular still in service is the 2021 file, predating the online platform the Reglement now
mandates. The 2021 Reglement PDF is a 2.4 MB scan whose extracted footers carry OCR corruption — quote from
the body only.

**VERDICT: ADMIT**

---

# PART 2 — REJECTED SCOPES

Each rejected candidate is recorded in the same schema, compressed. A negative finding recorded here is
worth more than a hopeful admission, and several of these are rejections of scopes whose sources are
genuinely good.

---

## R1. Private liability (generic, non-tenancy)

- **SOURCES:** CSS 518_d (contractual); Simpego Schadenmeldung Privathaftpflicht (operational,
  `https://www.simpego.ch/dam/jcr:fe86c806-faa1-4e80-b659-a7de4c4b5ac7/Schadenformular_Privathaftpflicht.pdf`);
  Generali Haushalt; AXA I3.1; VVG Art. 59, 60 (normative).
- **PROCESS STEPS:** notify *umgehend schriftlich*; hand conduct to the insurer; grant a Vollmacht to any
  appointed Verteidiger; abstain from acknowledging, settling or paying.
- **BRANCH CONDITIONS:** real and several — CSS cl. 27 *"Hat das Ereignis den Tod einer Person zur Folge,
  so ist dies der CSS innert 24 Stunden anzuzeigen"*; cl. 28(a) the insurer takes over only above the
  deductible; the Simpego form's *"Ist ein Sachschaden entstanden?"* / *"Ist ein Personenschaden
  entstanden?"* split; VVG 60 Abs. 1bis direct claim.
- **OBLIGATIONS / DEADLINES:** 24 hours on death; 14 days to terminate after a claim; five-year limitation.
- **DOCUMENTS:** a valued inventory and Originalbelege *auf Verlangen* (CSS cl. 8(c)) — and nothing else.
  The Simpego form only **invites**: *"Bei Vorliegen von Fotos der Beschädigung, Quittungen oder weiterer
  Informationen, können Sie uns diese Unterlagen gerne per E-Mail zustellen."*
- **NOT PUBLICLY SUPPORTED:** any branch-specific document set. The personal-injury branch multiplies the
  required **facts** about the injured person (Beruf, Arbeitgeber, Arzt/Spital, Art der Verletzung) but
  names **no** document, because the loss is a third party's and the evidence sits with them.
- **REDISTRIBUTION:** VVG shippable; all wordings and forms URL + hash + extract.
- **VERDICT: REJECT.** It clears steps, branches and a deadline but fails the decisive test: the document
  layer does not move with the branch. Retain this material as branch and required-fact content inside S6,
  where Allianz supplies the missing document layer for the tenancy slice of liability.

## R2. Motor compulsory liability / injured third party's direct claim (SVG)

- **SOURCES:** SVG Art. 63–66, 76 (normative, Fedlex filestore 1.1.2024); VVG 59(3), 60; VAG 46(1)(e).
- **BRANCH CONDITIONS:** excellent — SVG 65(2) is a **blanket** bar on contractual and VVG defences against
  the injured party, broader than VVG 59(3)'s enumerated list, with **mandatory** recourse under 65(3)
  where the driver was intoxicated or committed an Art. 90(4) speeding offence; 66(1) pro-rata reduction;
  76(6) subsidiarity to property and social insurance.
- **DOCUMENTS:** none. **DEADLINES:** none for the claimant.
- **NOT PUBLICLY SUPPORTED:** the entire operational layer, which sits in the Verkehrsversicherungsverordnung
  SR 741.31 — **not retrieved** (a guessed ELI returned the JavaScript shell).
- **VERDICT: REJECT.** No documents, no claimant deadline, and the implementing ordinance is unread. Keep
  SVG 65(2)/(3) as a *trap* item inside S8/R1 design: an agent that transplants the VVG Art. 38/45 sanction
  apparatus into a motor third-party fact pattern will be wrong, because those defences are switched off
  against the third party and survive only as recourse.

## R3. Social insurance claims procedure (ATSG)

- **SOURCES:** ATSG Art. 2, 29, 30, 31, 43, 43a, 49, 52, 52a, 60 (normative, Fedlex filestore 1.1.2024).
- Ironically **the most complete statutory claims procedure in Swiss law**: official form completed
  *"vollständig und wahrheitsgetreu"* by claimant, employer and treating doctor; misdirected filings
  preserved with their original date; ex officio investigation with oral information recorded in writing;
  a written Mahnung with notice of consequences and *"eine angemessene Bedenkzeit"* before a file-based
  decision; Verfügung → 30-day Einsprache → 30-day Beschwerde.
- **VERDICT: REJECT**, and wall it off. ATSG Art. 2 verified verbatim: *"Die Bestimmungen dieses Gesetzes
  sind auf die bundesgesetzlich geregelten Sozialversicherungen anwendbar, wenn und soweit die einzelnen
  Sozialversicherungsgesetze es vorsehen."* It therefore never applies to VVG private insurance. A private
  insurer issues no Verfügung, there is no Einsprache, and the route is an ordinary civil action.
  Importing ATSG steps into any admitted scope would make every derived obligation wrong. No Einzelgesetz
  (UVG/IVG/KVG) was retrieved, so it cannot be admitted even on its own terms.

## R4. Supplementary health insurance procedural track (ZPO Art. 7)

- **SOURCES:** ZPO Art. 7, 198(f), 113(2)(f), 114(e), 243(2)(f), 247(2)(a) (normative).
- **BRANCHES:** one genuine fork — has the canton designated a single instance? If so: no conciliation
  (**Art. 198 lit. f**, not Art. 199(3), which covers Arts. 5, 6 and 8 only), no court costs at either
  stage, simplified procedure regardless of value, facts established ex officio.
- **DOCUMENTS:** none. **DEADLINES:** none specific.
- **VERDICT: REJECT** as a scope. Retain as a **discriminating contrast item** against tenancy: tenancy is
  exempt from Gerichtskosten in conciliation (Art. 113(2)(c)) but **not** in the decision procedure
  (Art. 114's list a–g omits it), whereas supplementary health is exempt in both. That asymmetry is easy
  to state, hard to guess, and verifiable in one document.

## R5. Insurer-internal claims handling — intake, triage, escalation, reserving, service standards

- **SOURCES:** none. This is the central negative finding of the whole survey and it is unanimous across
  all five families.
- What exists publicly is only the *outputs* the regulator mandates: the AVO 163 registered letter, the
  AVO 169(2) reasoned written refusal with the pointer to the disagreement procedure, the AVO 166(3)
  claim notification form, the Kostengutsprache. The VAG contains **zero** occurrences of "ombuds", no
  complaint-handling procedure, no service standard and no claims-handling deadline; the only claims
  supervision mandate in the whole Act is Art. 46(1)(e), and it is confined to motor liability.
- **VERDICT: REJECT**, permanently. The earlier hand-authored operational layer must not return under any
  name. The benchmark's task must be reframed from "reconstruct the handler's workflow" to
  "reconstruct the claimant-facing process and the insurer's regulated outputs".

## R6. Police theft reporting as a process

- **SOURCES:** Suisse ePolice (operational). Publicly visible: the eight-category *"Was wurde gestohlen?"*
  triage and two *Vorabklärungen* gates. Everything else is behind mandatory account registration.
- **VERDICT: REJECT.** Material behind registration is not public and is inadmissible under this
  benchmark's own rule; creating an account on a user's behalf is not an option. Status: **settled
  negative**, not "pending verification". S8 stops at "a police report evidencing Anzeigeerstatter,
  Anzeigedatum, Polizeiposten, Polizeibeamter" and asserts nothing about how it is obtained.

## R7. Cantonal building insurance procedure (GVZ) as a contents scope

- **SOURCES:** GVZ "Vorgehen im Schadensfall" (operational) — which, unusually, *does* publish an ordered
  stateful procedure: notify → document with photographs → emergency measures needing no release →
  assessment with the policyholder → **written cover confirmation** → only then restoration → Antrag auf
  Schadenabrechnung with Kostenaufstellung and Rechnungskopien. Deductibles branch by peril; compensation
  over CHF 20'000 bears interest; *"Der Schaden muss innert zweier Jahre behoben werden."*
- **VERDICT: REJECT** for this domain, on four grounds, despite clearing the mechanical bar: (a) GVZ does
  not insure Hausrat at all — the large monopoly establishments outside NW and VD insure buildings only,
  so their well-structured forms cannot be borrowed for a contents scope; (b) the page cites no legal
  basis, so the published procedure is administrative practice, not law, and the ZH
  Gebäudeversicherungsgesetz was not retrieved; (c) the intake document list attributed to it upstream
  (*"Gebäudeadresse und Gebäudenummer …"*) **is not on that page**; (d) redistribution unknown, no licence
  stated. Admissible later only as an owner-side **building** scope, and only after (b) and (c) are fixed.

## R8. Household contents — valuables, bicycle and travel baggage as a standalone scope

- **SOURCES:** Generali Haushalt (real per-coverage lists: Rechnungen, Quittungen, Schätzungen; Kaufbeleg,
  detaillierter Kostenvoranschlag with photo, Polizeibeleg, Arztzeugnis, witnesses, a copy of the
  household policy), with two clean missing-document-to-refusal rules — *"Bei Fehlen eines Arztzeugnisses
  oder des Polizeibelegs kann eine Entschädigung verweigert werden"* and, for Cyber, refusal where
  *"Sie legen uns keinen Kostenvoranschlag vor"*; Simpego exclusion 15; CSS form §3.9.
- **VERDICT: REJECT** as a standalone scope: within a single wording there is no claimant-side deadline,
  only relative standards and the insurer-side four-week maturity. Fold the material into S8, where it
  supplies the best branch-conditioned document requirements in the family. (Note in passing that
  Generali's two refusal rules **falsify** the upstream claim that Simpego's CHF 1'000 rule is the only
  place a missing document defeats cover; Generali's are better items, because there the document is a
  filing step rather than a precondition of cover.)

## R9. Inter-insurer recourse and loss allocation (SVV SLK index; Ad-hoc-Kommission Schaden UVG)

- **SOURCES:** the SLK index of 19 recommendations 1980–2021
  (`https://svv.ch/de/fachdokumente/empfehlungen/empfehlungen-der-schadenleiterkommission-slk`) and the
  UVG ad-hoc index, the latter overwhelmingly dated 1983–1989 and unverified at clause level.
- **VERDICT: REJECT.** With the single exception of SLK 1/2013 (admitted as one node inside S6), none
  touches the claimant-facing chain: no intake, no documents, no claimant deadlines. Admitting them would
  pad the source list without supporting any admitted scope. The UVG set additionally imports a whole
  public-law procedural regime (see R3).

## R10. FINMA as a complaint or claims route

- **SOURCES:** FINMA "Meldung erstatten" and "Ombudsstellen für Finanzdienstleister".
- **VERDICT: REJECT.** A report to the regulator is not a legal procedure and confers no party rights, no
  feedback entitlement and no deadlines. FINMA's one usable contribution is the competence boundary and its
  stated criterion, already carried inside S10. Do not expand FINMA coverage beyond that page.

## R11. Cross-lingual consistency; risk-carrier identification; claim-payment-and-dispute (maturity,
limitation, forfeiture)

- **VERDICT: REJECT as scopes.** None is a process: they are *item axes* that belong inside admitted
  scopes. Cross-lingual testing rides on Orion's genuine DE/FR/IT/EN parallel first-party publications and
  Dextra's FR/IT editions (S7). Risk-carrier identification rides on AVO Art. 165(1)(b) and 166(2), which
  require the claims-settlement company to be named with its registered office and claims to be asserted
  **only** against it (S7). Maturity, limitation and forfeiture ride on VVG 41/41a/46 against the
  contractual clauses in S7/S8/S9.

---

# PART 3 — THE FOUR QUESTIONS, ANSWERED DIRECTLY

## 11.1 Which scopes are admitted, and which single scope is strongest?

**Ten scopes are admitted.**

| # | Scope | Basis |
|---|---|---|
| S1 | Tenancy — contesting a termination, and extension | OR 266l/266n/266o/271–273 + VMWG 9 + ZPO + AG/GE/BE/TI |
| S2 | Tenancy — rent increase, unilateral change, initial rent | OR 269a/269d/270b + VMWG 11/19/19a/20 + ZPO + AG/GE/ZH/BS |
| S3 | Tenancy — arrears (OR 257d) and the eviction fork | OR 257d + ZPO 198(a)/244 + Bern + BJ clear-case model |
| S4 | Tenancy — defects, reduction, damages, deposit of rent | OR 259a/259g + ZPO 210(1)(b)/247(2) + AG/GE/SO (+ OR 259h/259i to retrieve) |
| S5 | Tenancy — release of the rent deposit | **OR 257e** + SwissCaution CGA + ZPO |
| S6 | Tenancy — handover damage and tenant liability | **OR 267/267a** + Allianz + MV table + SLK 1/2013 + CSS/VVG |
| S7 | Legal expenses — cover, refusal, disagreement procedure | AVO 161–170 + VAG 32 + VVG + seven independent wordings |
| S8 | Household contents — theft | VVG 39 + CSS 519_d + CSS form + SVV + Simpego + AXA + Generali |
| S9 | Household contents — fire and natural hazard, private vs monopoly | AVO 171–177 + VVG + NSVG + LAIEN + ECA |
| S10 | Escalation to the ombudsman after refusal | Reglement 2026 + Leitlinien + Beschwerdeformular + FAQ |

**Strongest: S1 — contesting a termination and seeking extension.** Not because it is the most familiar,
but because it is the only scope where every link of the chain is publicly grounded and almost all of it is
redistributable:

- **Steps:** eleven, from service of the form to the court's ex officio examination of extension.
- **Deadlines:** five independent regimes — 30 days from receipt (OR 273); 60 days before expiry for a
  fixed-term prolongation and again before the expiry of a first prolongation (OR 273 al. 2/3, printed on
  the Geneva form); 20 days to reject an Entscheidvorschlag (ZPO 211(1)); 30 days Klagefrist
  (ZPO 209(4)); two months to hearing and twelve months to close (ZPO 203).
- **Branch conditions:** two *independent nullity routes*, each keyed to a checkable fact — the five-element
  content of the official form (VMWG 9(1)) and the separate notice to a spouse for the family home
  (OR 266n/266o) — plus a three-limb receipt rule, an extension bar tied to the ground of termination, a
  role-allocation rule on rejection, and a written-authorisation requirement for the managing agent.
- **Required fact → evidence capability → document:** the receipt date is the fact that starts the clock;
  the evidence capability is postal; the document is named in a current cantonal form —
  *"falls vorhanden eine Kopie des Couverts"*. That is the benchmark's whole chain in one line, and it
  cannot be produced by pattern-matching a flat document list.
- **Redistribution:** OR + VMWG + ZPO ship in full under URG Art. 5(1)(a); only the cantonal enclosure
  table is pinned by hash, and the Aargau form is the most current cantonal artefact in the universe
  (25.11.2024 but already drafted to post-1.1.2025 ZPO).
- **Composability:** the same case run under a legal-expenses policy chains S1 into S7, giving the deepest
  multi-hop item available: VMWG 9 → OR 266o → OR 273 → ZPO 209(4)/244(3) → AVB waiting period and consent
  gate → AVO 169(3).

**Close second: S2.** If the benchmark wants a discriminator that punishes generalisation, S2's role
reversal (ZPO 209(1)(a): on a rent-increase challenge the Klagebewilligung goes *to the landlord*) plus
VMWG 20(1)'s explicit non-extension of the 30-day window are the two hardest-to-guess correct answers in
the corpus. **Strongest on the insurance side: S8** — the only chain that runs end to end inside a single
insurer (VVG → CSS 519_d → CSS form) with a clean, honest stopping point at the police report.

## 11.2 Is there a scope where two published policy wordings govern the same loss event and imply
materially different obligations?

**Yes — and it is the most valuable experiment the universe supports. It lives in S7, with a second,
structurally different instance in S8/S9.**

**Primary instance (S7).** Hold the loss event fixed — *a tenant receives a rent increase on the official
form and wants to contest it within 30 days* — and vary only the legal-expenses wording. Seven
independently drafted wordings are publicly available for the identical event, and they imply materially
different obligations, required facts and documents:

| Wording | Waiting period for this event | Document production | Disagreement window | Distinctive required fact |
|---|---|---|---|---|
| Fortuna/Generali | 60 days from inception (Basic) / 0 (Top) | **10 days**, failing which *"ist Fortuna von der Leistungspflicht befreit"* | **90 days** from service of the refusal, else deemed waiver | self-occupancy of the let object |
| Coop Privatrechtsschutz-Paket | 3 months from *"Zeitpunkt des den Streit auslösenden Ereignisses"* | forward incoming documents *"ohne Verzug"*, no deadline | **none stated at all** | date of the triggering event |
| Beobachter (same carrier) | 3 months from *"Zeitpunkt des Gesetzesverstosses"* | as Coop | none stated | date of the **breach** — a different trigger, same carrier |
| smile (same carrier) | 3 months; Mindeststreitwert CHF 300 | insurer determines evidence-securing steps | none stated | gold vs silver tier |
| Protekta | per the policy, with pro-rata crediting on a switch | named Akten classes, *"unverzüglich"* | **20 days**, else deemed waiver | the A2 causation row |
| AXA-ARAG | AVB **silent** (see correction below) | named classes on request | **20 days**, and the insured carries all case deadlines from the date of the refusal letter | notification at the latest **3 months after the contract ends** |
| Dextra Flex | **0/30/60 — recorded only in the Police** | all documents, **electronically**, via the online notification and the lawyer portal | **14 days** | which option the policy records |
| Assista/TCS | 3 months for contractual disputes | *"alle verfügbaren Unterlagen und Beweismittel"* | **90 days** | amount in dispute ≥ CHF 2'000 for external services, unless sued **and** the opponent is lawyer-represented |

Why this is a real experiment and not a lookup: the same public normative layer sits over all of them and
partly **contradicts** them. VVG Art. 46(2) invalidates contractual terms imposing shorter time
restrictions — *but expressly reserves Art. 39(2)(2)*, so Generali's 10-day forfeiture is lawful in
principle and testable against the statutory *"angemessen"* standard, while a 14-day window to demand an
arbitrator is a different question. VVG Art. 45(3) lets a faultless defaulter perform late. AVO Art. 169(3)
means the Coop family's **silence** on a disagreement window may convert a refusal into acknowledged cover.
So the correct answer differs by wording *and* is not readable off any single document.

**Design constraints, without which the experiment produces a false result:**
1. **Deduplicate white-labels.** Coop Rechtsschutz is the carrier behind Beobachter, smile and GVB Lex;
   Orion is the carrier behind the Zurich booklet and the HEV products. Those are one drafting each, not
   four and three. Counting them as independent inflates apparent industry consensus fourfold.
2. **Deduplicate statutory boilerplate.** Protekta's M4 exculpation clause and AXA-ARAG's matching clause
   are near-transcriptions of VVG Art. 45(1)(a)/(b), which is mandatory law. They are two insurers copying
   a statute, not two insurers agreeing.
3. **Compare wordings, not marketing.** AXA-ARAG's "no waiting period" is **not** in the AVB — the word
   *Wartefrist* does not occur in it once. It appears only on the product page
   (`https://www.axa.ch/de/privatkunden/angebote/recht-cyber/rechtsschutzversicherung/privatrechtsschutz.html`:
   *"Der Versicherungsschutz gilt ab dem ersten Versicherungstag, ohne Wartefrist"*). Derive it from the
   AVB's silence plus clause A4, or cite the page as what it is.

**Second instance (S8/S9), structurally different and arguably better for a contents case.** Take one loss —
a watch destroyed in a fire or stolen — and three published regimes disagree about the *same* document:
- **CSS claim form**, unconditional on its face: *"bitte Originalkaufbelege beilegen"*.
- **Simpego** exclusion 15: for items with an insurance value of at least CHF 1'000, **cover fails**
  *"wenn im Schadenfall keine Quittung oder ein Wertgutachten eines Sachverständigen vorgewiesen werden
  kann"* — the document is a precondition of cover, not a filing step.
- **ECA Vaud** (a public-law establishment, same country, same peril): *"Sur le principe, nous n'avons pas
  besoin de la quittance d'achat des biens faisant partie de votre inventaire avant sinistre."* Because it
  works from a pre-loss inventory, post-loss receipts are expressly unnecessary.
That is a divergence in operating model, not merely in parameters, and it cannot be answered by
pattern-matching a single document.

**Third instance, smaller but sharp:** the post-declination forfeiture. SVV model E9 requires court action
*"innert 2 Jahren nach Eintritt des Ereignisses"* — triggered by declination but **running from the
event**, so a late declination can leave almost no time; CSS 519_d has **no forfeiture clause at all** and
a five-year limitation. One model wording and one first-party wording, same loss, materially different
consequence for an identical delay.

## 11.3 What must be dropped from the existing tenancy domains because it is internal procedure with no
public source?

**Drop, without replacement, every element of the hand-authored operational layer.** Concretely:

1. **All insurer-internal claims handling.** File opening; intake triage and case categorisation performed
   by a handler; severity, priority or complexity assignment; reserving; allocation to internal vs external
   handling *as an internal decision rule*; escalation to a senior handler or committee; four-eyes review;
   internal QA; fraud-referral thresholds; turnaround targets and SLAs. None of this appears in the VAG
   (zero occurrences of "ombuds"; no complaint procedure, no service standard, no claims deadline), in the
   AVO, in any AVB, or on any insurer page. Only the **outputs** survive: the AVO 163 registered letter,
   the AVO 169(2) reasoned refusal naming the disagreement procedure, the Kostengutsprache, and the
   AVO 166(3) claim notification form.
2. **The insurer's method of assessing prospects of success.** AVO Art. 169 requires a written reasoned
   position and an objective disagreement procedure; it prescribes no method, and no public source does.
3. **Any step framed as "the handler asks first for X".** Replace with claimant-facing duties from
   VVG 38/38a/39, the AVB, and the forms. The closest public artefact to a triage step is the CSS claim
   form's section 1, and that is the **claimant** classifying the loss, not a handler acting — and even
   there, the six boxes are independent AcroForm CheckBoxes, so "exactly one" is an inference the artefact
   does not support.
4. **Conciliation-authority internal procedure.** How a Schlichtungsbehörde triages, assigns, prepares or
   pre-assesses a file. What is public is only ZPO 202/203 timing, ZPO 200 parity composition, ZPO 201(2)
   and VMWG 21 advisory duties, and VMWG 22's publication duty.
5. **Bank / guarantee-provider internal release workflow** (S5) and the **Betreibungsamt's** procedure —
   OR 257e names the instruments, nothing names the workflow.
6. **Numeric notification deadlines attributed to statute.** VVG Art. 38(1) has only a relative dual-knowledge
   trigger. "Notify within N days" is always a contract fact and must carry an AVB citation with an edition
   and a hash, or be dropped.
7. **The police theft-report procedure** (R6) — settled negative.
8. **Specific defective assertions that must be struck from the existing material:**
   - The claim that the Vaud two-year declaration limit exists "solely on ECA's website" — it is
     **LAIEN Art. 67(1)**, statutory; and the ten-day contestation deadline said to be missing is
     **Art. 68(1)**; the two-year reconstruction rule is **Art. 57(1)**, not Art. 43. Every "contradiction"
     built on that reading must be withdrawn.
   - The Generali legal-expenses exclusion warning: Betreibung / Zwangsvollstreckung /
     Bauhandwerkerpfandrecht sits under *"Zusätzliche Deckungseinschränkungen Immobilienrechtsschutz"* and
     is limited to *"über die versicherte Immobilie"* — it does **not** bite on a tenant's Mietrecht claim.
     Encoding it would put a false exclusion in the tenancy gold answer.
   - SwissCaution "Art. 5 a/b/c" — those branches are **Art. 4 Ziff. 2**; Art. 5 is a different article.
   - The GVZ telephone-report document list, which is not on the cited page.
   - The Lebensdauertabelle sentences attributed to K-Tipp or MV/HEV that are in fact a deposit vendor's
     wrapper page; and the 2006 reprint generally, superseded by the MV page and two revisions stale.
   - Zug's truncated ZPO 210(1)(b) list, which silently drops *"Schutz vor missbräuchlichen Miet- und
     Pachtzinsen"*; Geneva's stale CHF 5'000 threshold (now CHF 10'000).
   - The Helvetia mirror (consumer PDF re-export, superseded edition, lettings-platform host) and GVB Lex.
   - Any ATSG-shaped Verfügung / Einsprache sequence appearing in a private-insurance scope.
9. **Finally, drop the framing itself.** The task cannot be "reconstruct the operational process an insurer
   or authority runs internally". It must be "reconstruct the claimant-facing process and the regulated
   outputs, and derive from them which documents this case still requires". Every admitted scope above is
   written to that reframing.

## 11.4 What is the honest ceiling — what will a reviewer say this source universe cannot establish?

A fair reviewer will grant that the sources are real, verified and unusually well checked, and will then
say the following. All of it is true.

1. **It cannot establish any insurer-internal or authority-internal process.** That is not a gap to be
   filled later; it is structural. No public Swiss source describes intake, triage, reserving or escalation
   inside a claims operation. Any benchmark item that claims to test that is testing an invention.
2. **It cannot supply a statutory notification deadline for private insurance.** VVG Art. 38 gives a
   relative trigger only. Every number is a contract fact, so every deadline item is only as durable as a
   pinned copy of a copyrighted PDF.
3. **Policy-dependent facts are unresolvable from public material by construction.** The waiting period
   (Dextra: *"Die gewählte Wartefrist ist in der Police festgehalten"*), the module composition, the
   gold/silver or Basic/Top tier, the sums insured — the honest public-only answer is often "the policy
   document is required". That is a legitimate and valuable answer, but it caps how deep the derivation
   can go before it stops.
4. **Cantonal variation limits generality.** Copy counts (Aargau two, Zug four, federal one per party),
   whether the initial-rent form is compulsory, which office receives deposited rent, whether a single
   cantonal instance exists — all depend on cantonal instruments, most of which were never retrieved.
   Many correct answers are canton-conditioned and cannot be stated flatly.
5. **Case law is absent.** *"Sofort"* in OR 267a, *"unverzüglich"*, *"angemessene Frist"* under
   VVG 39(2)(2), the burden of proof on VVG 38(2)/(3), what makes a termination abusive under OR 271, the
   quantum of a rent reduction — these are standards whose application is judicial. The benchmark can test
   that the standard exists and what it attaches to; it cannot test correct application to borderline facts.
6. **Known unread sources leave live holes.** OR 135 ff. on interruption of prescription (unfetched, and
   VVG 46 says nothing about interruption); **SR 221.229.11**, the ordinance under VVG Art. 99 that can
   disapply the Art. 98 protections — the citation and ELI are confirmed but the text has never been read,
   so every AVB-enforceability item is provisional; SR 741.31; OR 259h/259i; the cantonal Gebäudeversicherungs-
   gesetze; the Ticino LLL; the Ombudsstelle Krankenversicherung's own regulation.
7. **The redistributable corpus contains almost no document requirements outside VMWG.** The federal
   statutes name exactly one document class (VVG 39(2)(1), *"insbesondere auch ärztliche Bescheinigungen"*).
   VMWG Art. 9 and 19 are the honourable exception and are the reason the tenancy scopes are stronger than
   the insurance ones. Everything else operational — forms, guides, ombudsman regulations, the lifespan
   table, insurer wordings, public-body web copy — is URL + hash + short extract, and public-body web copy
   is **not** an amtlicher Erlass either. A reviewer will fairly say that most of this "public source
   universe" is a set of pinned hashes that can rot: AXA's `accesscode` URL can be silently re-pointed,
   Coop's redirect resolves to a dated upload path, the MV lookup is a JavaScript application, Protekta has
   no first-party URL at all, and the ombudsman FAQ is undated prose.
8. **Version churn is faster than a static benchmark.** ZPO 1.1.2025 (Entscheidvorschlag; CHF 10'000);
   OR and VMWG 1.10.2025 (AS 2025 197 / AS 2025 191); the Ombudsman Reglement 1.1.2026; cantonal forms on
   different clocks (ZH `neu-ab-nov2025`, BS "Version ab 1. Oktober 2025"); the Jahresbericht now in its
   53rd edition. Every gold answer must carry a consolidation date, or it will be wrong within a year.
9. **Apparent agreement is partly an artefact.** Seven "insurers" are about five drafting families, and
   several shared clauses are mandatory-law transcriptions. Without deduplication the corpus will appear to
   show industry consensus where it shows compliance.
10. **Citation precision is a live hazard, not a hypothetical one.** The `1bis` off-by-one produced two
    citations to paragraphs that do not exist, in the two most load-bearing articles of their families.
    Fedlex ELI pages return 200 with no text. XFA forms extract as "Please wait...". Tabular AVB invert
    label and block. Filenames masquerade as editions. One published hash is mistyped. Every pointer must
    be re-derived mechanically from parsed text and asserted against its own label.
11. **There is no observed ground truth anywhere.** No authority publishes a worked case with its correct
    document set. Every gold answer here is *derived* by the same reasoning the benchmark is testing.
    That is defensible for a reasoning benchmark, but a reviewer will say — correctly — that it measures
    fidelity to a constructed derivation, not agreement with real-world outcomes.

---

## Appendix A — Corrections that must be applied before encoding

| # | Correction |
|---|---|
| A1 | Re-derive **every** paragraph pointer in articles containing an `Abs. 1bis`: VVG Art. 60 (direct claim is **Abs. 1bis**, not Abs. 2; the naming duty is **Abs. 3** — there is no Abs. 4); VMWG Art. 19 (covering-letter rule is **Abs. 1bis**; the cantonal form-availability duty is **Abs. 4**, not "19(5)"); ATSG Art. 43 (examination duty **Abs. 2**, written Mahnung **Abs. 3**). |
| A2 | VVG Art. 8 lists **six** situations, not five. |
| A3 | The supplementary-health conciliation exemption is **ZPO Art. 198 lit. f**, not Art. 199(3). |
| A4 | VVG Art. 46(2) reserves Art. 39(2)(2) — quote the second sentence. |
| A5 | SVV E9's two-year forfeiture runs **from the event**, not from the declination. |
| A6 | ATSG Art. 43a(5)'s 30-day cap is **extensible by up to a further six months**. |
| A7 | AXA-ARAG has no *Wartefrist* clause; the AVB is silent. Cite the AVB's silence plus A4, or the product page as non-contractual. |
| A8 | Beobachter hash: `9b47821a4c7f898828eaeb2f2c6727b04be5c0098f89deef93b4147911fbaa56`. |
| A9 | Editions: CSS 518_d is **Ausgabe 02.2024** (518_d is the form number); LAIEN is in force since **01.07.2016** (the filename says 16-06-2023); the Aargau form is post-1.1.2025 drafting despite its 25.11.2024 date. |
| A10 | Cite the SVV Hausrat model as a 2022 model wording **retrieved by direct URL** — it is no longer on SVV's own Musterbedingungen index. Pin post-redirect SVV URLs. |
| A11 | Label the Protekta AVB explicitly as a **third-party mirror**; no first-party fetchable URL exists. |
| A12 | Do not cite the ECA e-mail address (not printed on the page); do not cite the GVZ intake list from the "Vorgehen im Schadensfall" page; do not cite the ombudsman "forwards the complaint to the insurer" step from the filing page. |

## Appendix B — Extraction and fetching rules for the ingest pipeline

1. Fedlex: cite the ELI, fetch `/filestore/.../{html,pdf-a}/`, record the `Stand` date. Treat a
   77'151-byte response as a failure, not a document.
2. Any tabular AVB (smile, GVB): ship page images or hand-aligned extracts; never raw `pdftotext`.
3. BJ model forms: read `/Root /AcroForm /XFA`; a page-1 text of "Please wait..." means the ingest failed.
4. SwissCaution CGA and LAIEN: column-aware parse; naive extraction interleaves columns.
5. Dextra: use the **Flex** PDF, not Pakete (the Pakete cover pages extract as letter-spaced garbage).
6. Generali legal expenses: section labels `E.1.2.1` extract as `E.1. 2.1`; do not conclude they are absent.
7. Orion: percent-encode spaces in the file paths; the FR/IT/EN twins are separate first-party files.
8. Allianz PDFs: 403 to bare curl; a browser User-Agent returns 200.
9. Assert the extracted paragraph or clause label against the citation before storing any pointer.
10. German-language searches for Swiss claim forms return predominantly **German** insurers; filter by
    jurisdiction before ingesting anything new.

## Appendix C — Redistribution matrix

| Class | Position |
|---|---|
| Federal statute and ordinance (OR, ZPO, VVG, VMWG, AVO, VAG, SVG, ATSG) | **Ship in full.** URG Art. 5(1)(a): *"Gesetze, Verordnungen, völkerrechtliche Verträge und andere amtliche Erlasse"*. |
| Cantonal statute (NSVG, LAIEN) | Ship; record that retrieval was via aggregator / establishment copy. |
| Authority decisions and reports | URG Art. 5(1)(c) would cover them if any are later admitted; none is currently. |
| Insurer AVB, claim forms, insurer guides and web pages | **URL + SHA-256 + short quoted extract only.** |
| SVV model wordings and SLK recommendations | URL + hash + extract; non-binding, association-authored. |
| Ombudsman Reglement, Leitlinien, form, FAQ | URL + hash + retrieval date; a private foundation's material, not an Erlass. |
| Public-body web copy (ECA, GVZ, cantonal court pages) | URL + hash + retrieval date; **not** an amtlicher Erlass. |
| MV/HEV Lebensdauertabelle | **Cannot be shipped.** Paywalled private standard; quote the computation rule and the one published worked example only; the italicised prices are MV-only, not parity-agreed. |
