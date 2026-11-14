# Protekta legal-protection claims handling: scope from public sources

Compiled 2026-11-14 from public pages and documents only. The two sets of conditions it quotes are kept as text under `docs/sources/protekta/`, with `index.tsv` listing every source (URL, date fetched, what it is); file names in this report refer to the folders of that index.

Abbreviations:

- **P01.2026** = Protekta, Rechtsschutzversicherung für Privatpersonen, Kundeninformationen und Allgemeine Bedingungen, Ausgabe 01.2026 (RSP-01.2026). File: `15-avb-privat-RSP-01-2026/rsp-01-2026.json`, with text renderings `rsp-01-2026-full.txt` and `rsp-01-2026.txt`.
- **U09.2025** = Rechtsschutzversicherung für Unternehmen, Ausgabe 09.2025. File: `11-avb-unternehmen/avb-unternehmen.pdf`, with text versions `avb-unternehmen-flow.txt` and `avb-unternehmen.txt`.

---

## 1. Products, AVB documents, editions, structure

The AVB index page is https://protekta.mobiliar.ch/rechtliche-hinweise/allgemeine-versicherungsbedingungen (`01-avb-page/avb-page.html`). protekta.ch redirects to protekta.mobiliar.ch, which was reachable.

| AVB | Edition | Source / file | Format |
|---|---|---|---|
| Rechtsschutzversicherung für Privatpersonen (Privat-, Verkehrs-, Immobilien-Rechtsschutz) | **01.2026** (textReference RSP-01.2026, dateOfAvailability 2026-02-19) | Viewer https://oiv.protekta.ch/de/avb/RSP-01-2026/. Data from the public API https://sec-api-b2c.app.mobiliar.ch/oiv/viewer/xml/retrieve?urlName=RSP-01-2026&language=de → `15-avb-privat-RSP-01-2026/rsp-01-2026.json` | Structured XML in JSON. **No PDF is offered.** |
| Rechtsschutzversicherung für Unternehmen (Betriebs-, Verkehrs-, Immobilien-Rechtsschutz) | **09.2025** | https://protekta.mobiliar.ch/media/72/download?inline=1 → `11-avb-unternehmen/avb-unternehmen.pdf` | PDF |
| Rechtsschutzversicherung für Unternehmen GastroSuisse | **01.2024** | https://protekta.mobiliar.ch/media/71/download?inline=1 → `12-avb-gastrosuisse/avb-unternehmen-gastrosuisse.pdf` | PDF (not analysed in detail) |
| Private, previous edition | 08.2023 | Third-party copy (lch.ch) → `13-avb-privat-lch/protekta-avb-privat-lch.pdf` | PDF |

- There is no separate "combined" product. The private AVB covers all three private modules. Customers choose packages Minima, Classic or Comfort (`04-privat/privat-rechtsschutz.html`).
- For businesses, `07-unternehmen/unternehmen.html` lists add-ons: «Rechtsschutzversicherung für Landwirtschaftsbetriebe», «Rechtsschutzversicherung für GastroSuisse-Mitglieder», «Rechtschutz für Gemeinden und Behörden», «Rechtsschutzversicherung für Medizinalpersonen». Their own conditions were **not obtained**.

**Structure of P01.2026**

- Kundeninformationen 1.–9.
- A Gemeinsame Bestimmungen: A1 Allgemeines zum Versicherungsvertrag, A2 Zeitlicher Geltungsbereich, A3 Örtlicher Geltungsbereich, A4 Versicherte Leistungen, A5 Selbstbehalt, A6 Leistungseinschränkungen.
- Privat-Rechtsschutz: B Versicherte Personen, C Versicherte Eigenschaften, D Versicherte Streitigkeiten (D1 Alltag & Familie, D2 Arbeit, D3 Wohnen & Bauen, D4 Behörden, D5 Gesundheit & Versicherungen, D6 Beratung).
- Verkehrs-Rechtsschutz: E Versicherte Personen, Eigenschaften und Fahrzeuge; F Versicherte Streitigkeiten (F1 Mobilität); G Ergänzende Deckungseinschränkungen.
- Immobilien-Rechtsschutz: H Versicherte Personen, Immobilien und Ereignisse; I Versicherte Streitigkeiten (I1 Liegenschaft, I2 Vermieten & Verpachten).
- J Einschränkungen aus sachlichen Gründen, K aus personenbezogenen Gründen, L für bestimmte Risiken und Situationen.
- **M Abwicklung von Rechtsstreitigkeiten** (Ziff. 1–8).
- N Datenschutz.

**Structure of U09.2025**

- A Allgemeiner Teil: A1 Allgemeines, A2 Versichertes Unternehmen, A3 Zeitlicher Geltungsbereich, A4 Örtlicher Geltungsbereich, A5 Versicherte Leistungen, A6 Selbstbehalt, A7 Leistungseinschränkungen.
- B Betriebs-Rechtsschutz: B1 Versicherte Personen, B2 Tätigkeitsbereiche und Eigenschaften, B3 Versicherte Objekte, B4 Versicherte Streitigkeiten (Ziff. 1–30).
- C Verkehrs-Rechtsschutz: C1 Fahrzeug-Rechtsschutz, C2 Lenker-Rechtsschutz, C3 Versicherte Streitigkeiten (Ziff. 1–8), C4 Ergänzende Deckungseinschränkungen.
- D Immobilien-Rechtsschutz: D1, D2 (Ziff. 1–13).
- E Allgemeine Deckungseinschränkungen: E1 (lit. a–u), E2 (lit. a–d), E3 (lit. a–l).
- **F Abwicklung von Rechtsstreitigkeiten** (Ziff. 1–8).
- G Datenschutz.

**Note on "F 1":**

- In U09.2025 and in the private edition 08.2023, the duty to report and hand over documents is **F Ziff. 1**.
- In the current private edition P01.2026 the identical text is **M Ziff. 1**; "F1" there is the traffic legal-area list «Mobilität».
- The private 08.2023 section F was identified from its table of contents only.

**Covered legal areas ("versicherte Rechtsgebiete"). Each list is introduced by «Ihre Police gibt darüber Auskunft, welche der folgenden Rechtsgebiete versichert sind.»**

- **P01.2026 D1–D6 (Privat):**
  - D1: Konsumenten- und Vertragsrecht; Sachenrecht; Schadenersatzrecht; Schulrecht; Persönlichkeitsrecht und Internet-Rechtsschutz; Inkasso-Rechtsschutz; Urheberrecht; Eherecht, eingetragene Partnerschaft und Konkubinat; Erbrecht.
  - D2: Arbeitsrecht; Vertragsrecht aus selbständiger Nebenerwerbstätigkeit.
  - D3: Miet- und Pachtrecht; Nachbarrecht; Sachenrecht; Bauherren-Rechtsschutz; Hypothekarstreitigkeiten; Kauf und Verkauf von Immobilien; Öffentliches Baurecht; Enteignungsrecht.
  - D4: Strafrecht; Steuerrecht.
  - D5: Patientenrecht; Sozialversicherungsrecht; Privatversicherungsrecht.
  - D6: Beratungs-Rechtsschutz.
- **P01.2026 F1 (Verkehr):** Konsumenten- und Vertragsrecht; Sachenrecht; Schadenersatzrecht; Strafrecht; Ausweisentzug und Fahrzeugbesteuerung; Patientenrecht; Sozialversicherungsrecht; Privatversicherungsrecht.
- **P01.2026 I1–I2 (Immobilien, landlord / not owner-occupied):**
  - I1: Konsumenten- und Vertragsrecht; Sachenrecht; Schadenersatzrecht; Arbeitsrecht; Nachbarrecht; Bauherren-Rechtsschutz; Hypothekarstreitigkeiten; Strafrecht; Sozialversicherungsrecht; Privatversicherungsrecht; Öffentliches Baurecht; Enteignungsrecht.
  - I2: Miet- und Pachtrecht (als Vermieter und Verpächter).
- **U09.2025 B4 (Betrieb):**
  - Betrieb: 1 Sachenrecht, 2 Schadenersatzrecht, 3 Datenschutzrecht, 4 Abwehr von Verantwortlichkeitsansprüchen, 5 Tarifstreitigkeiten, 6 Wirtschaftlichkeit und Delegation, 7 Vertragsrecht, 8 Persönlichkeitsrecht und Internet-Rechtsschutz, 9 Inkasso-Rechtsschutz, 10 Kartellrecht, 11 Unlauterer Wettbewerb, 12 Immaterialgüterrecht.
  - Mitarbeitende: 13 Arbeitsrecht, 14 Aufenthaltsbewilligungen.
  - Geschäftsräume & Bauen: 15 Miet- und Pachtrecht, 16 Nachbarrecht, 17 Sachenrecht, 18 Bauherren-Rechtsschutz, 19 Hypothekarstreitigkeiten, 20 Öffentliches Baurecht, 21 Enteignungsrecht.
  - Behörden: 22 Strafrecht, 23 Betriebliche Bewilligungen, 24 Produktesicherheitsgesetz, 25 Direktzahlungen, 26 Preisüberwachungsgesetz, 27 Steuerrecht.
  - Versicherungen: 28 Sozialversicherungsrecht, 29 Privatversicherungsrecht.
  - Beratung: 30 Beratungs-Rechtsschutz.
- **U09.2025 C3 (Fahrzeuge und Lenker):** 1 Vertragsrecht, 2 Sachenrecht, 3 Schadenersatzrecht, 4 Strafrecht, 5 Führerausweis, 6 Fahrzeugausweis und -besteuerung, 7 Sozialversicherungsrecht, 8 Privatversicherungsrecht.
- **U09.2025 D2 (Liegenschaft / Vermieten):** 1 Vertragsrecht, 2 Sachenrecht, 3 Schadenersatzrecht, 4 Arbeitsrecht, 5 Nachbarrecht, 6 Bauherren-Rechtsschutz, 7 Hypothekarstreitigkeiten, 8 Strafrecht, 9 Sozialversicherungsrecht, 10 Privatversicherungsrecht, 11 Öffentliches Baurecht, 12 Enteignungsrecht, 13 Miet- und Pachtrecht.

**Sums insured and deductibles from the product pages** (`04-privat/privat-rechtsschutz.html`, `05-verkehr/verkehrs-rechtsschutz.html`; not from the AVB):

| Package | Cover per case, Switzerland or Europe | Cover worldwide | Deductible |
|---|---|---|---|
| Minima | up to CHF 300 000 | — | CHF 2 000 |
| Classic | up to CHF 1 000 000 | up to CHF 200 000 | — |
| Comfort | up to CHF 1 500 000 | up to CHF 300 000 | — |

Minima covers «14 Rechtsgebiete».

---

## 2. AVB passages for checking cover and handling a case (verbatim)

All passages are from **P01.2026** unless the row says otherwise. Where U09.2025 has the same rule, its section is given.

| Topic | Section (P01.2026) | Verbatim | U09.2025 |
|---|---|---|---|
| Who: household | A1 Ziff. 2 | «Sie sind gemäss Angaben auf Ihrer Police als Einzelperson oder als Mehrpersonenhaushalt versichert.» | – (A2 «Versichert sind: 1 Das in der Police bezeichnete Unternehmen.») |
| Who: persons | B (table, row 1 and row 4) | «Versichert sind die folgenden Personen mit Wohnsitz in der Schweiz oder im Fürstentum Liechtenstein:» … «Dauerhaft mit Ihnen im gemeinsamen Haushalt lebende Personen.» | B1 Ziff. 1–7 |
| Who: children | B (table, row 3) | «Ihre Kinder die minderjährig sind und für die Sie das gemeinsame oder alleinige Sorgerecht haben; die unter umfassender Beistandschaft stehen.» | – |
| Household change | B (table, row 8) | «Vorausgesetzt wird, dass die Veränderung der Protekta innerhalb von 3 Monaten gemeldet und rückwirkend auf den Zeitpunkt der Veränderung eine den veränderten Verhältnissen eigene Privat-Rechtsschutzversicherung abgeschlossen bzw. die bisherige Police auf eigenen Namen weitergeführt wird.» | – |
| Capacity | C Ziff. 1 | «Als Privatperson, insbesondere als Fussgänger und Benützer von Fahrzeugen, für welche sie keinen Führerausweis benötigen sowie als Passagier eines öffentlichen oder privaten Transportmittels.» | B2 «Die versicherten Personen bei der Ausübung ihrer beruflichen Tätigkeit gemäss Police für das versicherte Unternehmen.» |
| Capacity: tenant | C Ziff. 3 | «Als Mieter oder Pächter von selbstbewohntem Wohnraum, von selbstbenutzten Garagen, Parkplätzen oder Grundstücken zur Selbstversorgung.» | B3 Ziff. 1 |
| Capacity: traffic | E (table, row 2) | «als Eigentümer, Halter, Lenker und vertraglich Berechtigter von Land- oder Wasserfahrzeugen (inklusive Zubehör und Anhänger), für die ein Führerausweis erforderlich ist;» | C1, C2 |
| Where | A3 Ziff. 1 | «Der örtliche Geltungsbereich richtet sich nach Ihrer Police.» | A4 Ziff. 1 |
| Where | A3 Ziff. 4 | «Der Versicherungsschutz besteht, soweit für die Beurteilung des Rechtsstreits Gerichte oder Verwaltungsbehörden im versicherten Gebiet zuständig sind, entsprechendes Landes- oder Gemeinschaftsrecht zur Anwendung kommt und im versicherten Gebiet vollstreckt werden kann.» | A4 Ziff. 4 («im bezeichneten Gebiet vollstreckt») |
| Where | A3 Ziff. 5 | «Nicht versichert sind Verfahren vor internationalen und überstaatlichen Gerichten und Behörden.» | A4 Ziff. 5 |
| When | A2 Ziff. 1 | «Ein Rechtsfall ist gedeckt, wenn seine Ursache und der Bedarf nach Rechtsschutz während der für das betroffene Risiko geltenden Vertragsdauer eintreten. Nicht gedeckt ist ein Rechtsfall, dessen Ursache bei Antragsstellung bereits eingetreten ist.» | A3 Ziff. 1 (first sentence only) |
| Cause | A2 Ziff. 2 | «Im Allgemeinen gilt die erstmalige tatsächliche oder angebliche Rechts- oder Vertragsverletzung als Ursache.» | A3 Ziff. 2 |
| Cause: special | A2 Ziff. 3 | «bei Strafverfahren: die tatsächliche oder angebliche Widerhandlung.» «bei Administrativ- und Verwaltungsverfahren: die erste förmliche Ankündigung der Behörde bzw. die angebliche oder tatsächliche Widerhandlung, je nachdem, was zuerst eintritt.» «im Eherecht, bei eingetragener Partnerschaft und im Konkubinat: die Auflösung des gemeinsamen Haushaltes, spätestens jedoch das Einreichen einer gerichtlichen Eingabe.» «bei erbrechtlichen Streitigkeiten: der Tod des Erblassers.» | A3 Ziff. 3 lit. a–h (lit. h: Verantwortlichkeitsansprüche) |
| Waiting period | A2 Ziff. 4 | «Vorbehalten bleiben die Wartefristen gemäss Ihrer Police. Die Wartefristen beginnen ab Inkrafttreten dieses Vertrages oder ab Einschluss neuer Risiken. Nicht versichert ist ein Rechtsfall, dessen Ursache innerhalb einer Wartefrist eintritt.» | A3 Ziff. 4 |
| Waiting period: switching insurer | A2 Ziff. 4 | «Die Wartefrist entfällt bei einer Vertragserneuerung bzw. -anpassung oder bei nahtlosem Wechsel vom Vorversicherer, wenn das entsprechende Risiko bereits versichert war und die ursprüngliche Wartefrist abgelaufen ist.» | A3 Ziff. 4 |
| Waiting period: length and areas (product page `04-privat`, **not AVB**) | FAQ | «Generell gelten beim Abschluss einer Privat-Rechtsschutzversicherung drei Monate Wartefrist.» «In folgenden Bereichen entfällt die Wartefrist:» Schadenersatzrecht, Strafrecht, Patientenrecht, Sozialversicherungsrecht, Privatversicherungsrecht | – |
| Pre-existing / after the contract (Kundeninformationen 3.) | KI 3. | «Streitigkeiten, deren Ursache vor dem Abschluss der Versicherung oder innerhalb der festgelegten Wartefrist eingetreten ist;» «Streitigkeiten, bei denen der Bedarf nach Rechtsschutz erst nach Vertragsende entsteht.» | KI 3. |
| Sums in the policy | A1 Ziff. 1 | «Diese Dokumente nennen insbesondere die von Ihnen gewählten Deckungen und Leistungen, die zugehörigen Versicherungssummen, die örtlichen Geltungsbereiche sowie allfällige Wartefristen und Selbstbehalte.» | A1 Ziff. 1 |
| Amount in dispute: employment | D2 Ziff. 1 | «Es gilt voller Versicherungsschutz bis zu dem in der Police genannten Streitwert. Übersteigt der tatsächliche Streitwert den in der Police genannten Streitwert, übernehmen wir Kosten gemäss Art. A4 Ziff. 3 nur anteilsmässig» | not in B4 Ziff. 13 |
| Amount in dispute: how counted | D2 Ziff. 1 | «Dieser richtet sich nach der gesamten Forderung und nicht nach allfällig zulässigen Teilklagen. Wird Widerklage erhoben, werden die Streitwerte zusammengezählt.» | – |
| Amount in dispute: boats | G Ziff. 2 | «übersteigt der Streitwert CHF 50 000, übernehmen wir Kosten gemäss Art. A4 Ziff. 3 nur anteilsmässig, und zwar im prozentualen Verhältnis von CHF 50 000 zum Streitwert.» | – |
| Minimum: debt collection | D1 Ziff. 6 | «Bis zu zwei Mal pro Kalenderjahr das Inkasso unbestrittener, fälliger und nicht verjährter Forderungen.» «Die Forderung beträgt mindestens CHF 500 und» «Sie haben bereits eine schriftliche Mahnung gesendet.» | B4 Ziff. 9 («Bis zu zehn Mal pro Kalenderjahr») |
| Limit: side income | D2 Ziff. 2 | «Streitigkeiten aus obligationenrechtlichen Verträgen, sofern der tatsächliche oder erwartete Bruttojahresumsatz CHF 20 000 nicht übersteigt.» | – |
| Limit: building project | D3 Ziff. 4 | «Der Versicherungsschutz besteht, wenn die Kosten des gesamten Bauvorhabens den in der Police genannten Betrag nicht übersteigen.» | B4 Ziff. 18, D2 Ziff. 6 |
| Tax | D4 Ziff. 2 | «Beschwerdeverfahren nach Erhalt eines Einspracheentscheides betreffend Staats- und Gemeindesteuer und direkte Bundessteuer.» | B4 Ziff. 27 (also MWST, Verrechnungssteuer) |
| Aggregation | A6 Ziff. 2 lit. b | «Ergeben sich aus einem Schadenereignis oder aus einem zusammenhängenden Sachverhalt mehrere Rechtsstreitigkeiten, so gelten diese gesamthaft als ein Rechtsstreit und wir erbringen die Leistung gesamthaft nur einmal.» | A7 Ziff. 2 lit. c |
| Several insureds | A6 Ziff. 2 lit. c | «Können aus einem Schadenereignis oder aus einem zusammenhängenden Sachverhalt mehrere versicherte Personen Leistungen beanspruchen, erbringen wir die Leistung gesamthaft nur einmal.» | A7 Ziff. 2 lit. d |
| Several dwelling units | A6 Ziff. 2 lit. d | «Betrifft eine Streitigkeit im Immobilien-Rechtsschutz mehrere versicherte Wohneinheiten, wird die Versicherungssumme mit dieser Anzahl Wohneinheiten multipliziert, sie beträgt jedoch höchstens CHF 1,5 Mio.» | A7 Ziff. 2 lit. e (CHF 1 Mio.) |
| Exclusions: general | J lit. a–b | «vorstehend nicht aufgeführte Bereiche;» «Abwehr ausservertraglicher Haftpflichtansprüche;» | E1 lit. a–b |
| Exclusions: liability insurer | J lit. c | «Abwehr vertraglicher Haftpflichtansprüche aus gedeckten Rechtsgebieten, soweit eine Haftpflichtversicherung Ihre Interessen wahren muss;» | E1 lit. c |
| Exclusions: public law | J lit. m | «öffentliches Recht, insbesondere öffentlich-rechtliche Verträge, Steuer- und Abgaberecht, öffentliches Baurecht, Planungsrecht, Zollstreitigkeiten, Geldwäscherei, Enteignungen, Prämienverbilligung und Sozialhilfe. Vorbehalten bleiben die ausdrücklich vereinbarten Deckungen gemäss Ihrer Police;» | E1 lit. m |
| Exclusions: intent | J lit. n | «Strafverfahren wegen des Vorwurfs vorsätzlicher Verletzung strafrechtlicher Vorschriften. Endet jedoch ein solches Verfahren durch rechtskräftigen Entscheid mit einer Nichtanhandnahme, einer Einstellung oder einem Freispruch, so erbringen wir die versicherten Leistungen am Ende des Verfahrens rückwirkend.» | E1 lit. n |
| Exclusions: drink-driving | J lit. p | «wenn Ihnen vorgeworfen wird, in angetrunkenem Zustand mit einem Mindestalkoholgehalt von 1,6 ‰ oder 0,8 mg/Liter Atemluft ein Fahrzeug geführt zu haben;» | E1 lit. p |
| Exclusions: SchKG | J lit. u | «Schuldbetreibungs- und Konkursrecht, mit Ausnahme des Inkassos in einem versicherten Rechtsfall (Art. A4 Ziff. 3 lit. g) und der ausdrücklich vereinbarten Deckung «Inkasso-Rechtsschutz» (Art. D1 Ziff. 6).» | E1 lit. u |
| Exclusions: persons | K lit. a, c | «Streitigkeiten mit der Protekta und ihren Organen; versichert sind hingegen Streitigkeiten mit anderen Gesellschaften der Gruppe Mobiliar;» «Streitigkeiten unter den durch diesen Vertrag versicherten Personen, mit Ausnahme der Wahrnehmung der rechtlichen Interessen des Versicherungsnehmers selbst;» | E2 lit. a, c |
| Exclusions: self-employment | L lit. a | «haupt- oder nebenberufliche selbständige Erwerbstätigkeit. Vorbehalten bleibt die Deckung «Vertragsrecht aus selbständiger Nebenerwerbstätigkeit» (Art. D2 Ziff. 2);» | E3 (lit. a: Geschäftsbetriebe im Ausland) |
| Exclusions: traffic | G Ziff. 1 lit. d | «wenn Ihnen das Überschreiten der zulässigen Höchstgeschwindigkeit (nach Abzug der Toleranz) vorgeworfen wird: innerorts: ab 30 km/h; ausserorts und auf Autostrassen: ab 40 km/h; auf Autobahnen und richtungsgetrennten Autostrassen: ab 50 km/h.» | C4 Ziff. 3 |
| Services | A4 Ziff. 1–2 | «Telefonische Rechtsauskünfte durch unsere JurLine, unabhängig davon, ob ein gedeckter Rechtsfall vorliegt.» «Beratung und Interessenwahrung in gedeckten Fällen durch unsere Juristen.» | A5 Ziff. 1–2 |
| Paid: lawyer, mediation | A4 Ziff. 3 lit. a | «Mediations- und Anwaltshonorare;» | A5 Ziff. 3 lit. a |
| Paid: first-hour lawyer | A4 Ziff. 3 lit. b | «Anwalt der ersten Stunde: Für einen von Ihnen für die erste Einvernahme beigezogenen Strafverteidiger übernehmen wir vorab bis zu CHF 5000. Vorschussleistungen, für welche gemäss Art. J lit. n keine Versicherungsdeckung besteht, sind uns zurückzuerstatten;» | A5 Ziff. 3 lit. b |
| Paid: expert opinions | A4 Ziff. 3 lit. c | «Gutachten, die vom Gericht, von der Protekta oder im Einvernehmen mit der Protekta von Ihrem Anwalt veranlasst worden sind;» | A5 Ziff. 3 lit. c |
| Paid: court costs | A4 Ziff. 3 lit. d | «Gerichtsgebühren oder andere Verfahrenskosten, die zu Ihren Lasten gehen;» | A5 Ziff. 3 lit. d |
| Paid: penalty-order costs | A4 Ziff. 3 lit. e | «die in einem Strafbefehl oder einer Verfügung des Strassenverkehrsamtes aufgeführten Kosten übernehmen wir bis CHF 500 pro Kalenderjahr;» | A7 Ziff. 2 lit. a |
| Paid: party costs | A4 Ziff. 3 lit. f | «Parteientschädigungen an die Gegenpartei. Auf die Ihnen zugesprochenen Prozess- oder Parteientschädigungen haben wir Anspruch, soweit wir die Kosten dafür übernommen haben. Auf Verlangen sind uns diese Ansprüche abzutreten;» | A5 Ziff. 3 lit. e |
| Paid: collection | A4 Ziff. 3 lit. g | «das Inkasso einer Ihnen aus einem versicherten Fall zustehenden Forderung, sofern der Schuldner diese bestreitet. Dies bis zur Ausstellung eines Pfändungsverlustscheines, eines Gesuches um Nachlassstundung, einer Konkursandrohung oder eines Pfandausfallscheines;» | A5 Ziff. 3 lit. f |
| Paid: bail | A4 Ziff. 3 lit. i | «Strafkautionen (vorschussweise) zur Vermeidung der Untersuchungshaft;» | A5 Ziff. 3 lit. i |
| Paid: advice | A4 Ziff. 3 lit. j | «Beratungen durch einen Anwalt, Notar oder anerkannten Mediator bis zu CHF 1000 pro Kalenderjahr im Rahmen des Beratungs-Rechtsschutzes gemäss Art. D6 Ziff. 1;» | A5 Ziff. 3 lit. j (amount per policy) |
| Paid: abroad | A4 Ziff. 3 lit. k | «notwendige Reisen an Gerichtsverhandlungen im Ausland und für Übersetzungen in Streitigkeiten mit Auslandbezug bis zum Gesamtbetrag von CHF 5000;» | A5 Ziff. 3 lit. k |
| Not paid | A6 Ziff. 1 | «Finanzielle Leistungen mit Strafcharakter, namentlich Bussen;» «Schadenersatz und Kosten, die zu Lasten eines Haftpflichtigen oder eines Haftpflichtversicherers gehen;» «Erfolgshonorare an Anwälte;» «Konkursverfahren.» | A7 Ziff. 1 |
| Deductible | A5 Ziff. 1–2 | «Bei der Beratung und Interessenwahrung durch die Juristen der Protekta gemäss Art. A4 Ziff. 1 und 2 gilt kein Selbstbehalt.» «Für die Kostenübernahme gemäss Art. A4 Ziff. 3 gilt ein Selbstbehalt, wenn er in Ihrer Police vereinbart ist.» | A6 |
| Gross negligence | A6 Ziff. 3 | «Bei grober Fahrlässigkeit verzichtet die Protekta ausdrücklich auf das ihr gesetzlich zustehende Recht, Leistungen zu kürzen.» | A7 Ziff. 3 |
| Premium arrears | A1 Ziff. 4 | «Wenn Sie die Prämie trotz Mahnung nicht bezahlen, ruht unsere Leistungspflicht bis zur vollständigen Bezahlung der rückständigen Prämie samt Zinsen und Kosten. Für in der Zwischenzeit eingetretene Schäden erbringen wir keine Leistungen» | A1 Ziff. 3 (first sentence only) |
| Sanctions | A1 Ziff. 10 | «Ungeachtet anderslautender Vertragsbestimmungen gewährt dieser Versicherungsvertrag keinen Versicherungsschutz oder sonstige Leistungen des Versicherers, soweit und solange anwendbare gesetzliche Wirtschafts-, Handels- oder Finanzsanktionen entgegenstehen.» | A1 Ziff. 10 |
| **Reporting, documents** | **M Ziff. 1** | «Wenn Sie unsere Leistungen beanspruchen möchten, müssen Sie uns unverzüglich informieren und uns alle Unterlagen (z.B. Korrespondenz, Bussenverfügungen, Vorladungen und Entscheide) betreffend den Rechtsfall zustellen.» | **F Ziff. 1** |
| Reporting (customer information) | KI 6. | «Versicherte Streitigkeiten müssen Sie uns sofort melden. Für den Beizug eines Anwalts oder für die Einleitung von Verfahrensschritten müssen Sie vorgängig unsere Genehmigung einholen.» | KI 6. |
| In-house vs external | M Ziff. 2 | «In versicherten Fällen beraten wir Sie juristisch und nehmen Ihre Interessen wahr. Um eine bestmögliche Bearbeitung von Rechtsfällen zu gewährleisten, arbeiten wir mit externen Fachpersonen (z.B. Anwälten) zusammen. In einigen Fällen kann es notwendig sein, einen Fall ohne vorherige Rücksprache mit Ihnen weiterzuleiten.» | F Ziff. 2 |
| Free choice, cost guarantee | M Ziff. 3 | «Ist der Beizug eines Anwaltes erforderlich oder besteht eine Interessenkollision, dürfen Sie einen Anwalt mit Sitz im Gebiet des für die Beurteilung des Rechtsstreits zuständigen Gerichtes frei wählen und vorschlagen. Vor Beauftragung des Anwaltes müssen Sie unsere Zustimmung und unsere Kostengutsprache einholen.» | F Ziff. 3 |
| Lawyer rejected | M Ziff. 3 | «Lehnen wir den von Ihnen vorgeschlagenen Anwalt ab, dürfen Sie drei andere Vertreter aus unterschiedlichen Anwaltskanzleien vorschlagen, von denen wir einen akzeptieren müssen. Wir müssen die Ablehnung eines Anwaltes nicht begründen.» | F Ziff. 3 |
| Breach of duties | M Ziff. 4 | «Werden Melde- oder Verhaltenspflichten verletzt, wird einem Anwalt das Mandat erteilt oder entzogen, werden Rechtsmassnahmen getroffen oder erfolgt ein Weiterzug, bevor wir unsere Genehmigung erteilt haben, so können wir unsere Leistungen ablehnen oder kürzen.» | F Ziff. 4 |
| Breach: exceptions | M Ziff. 4 | «Dieser Nachteil tritt nicht ein, wenn Sie beweisen, dass die Verletzung der Melde- oder Verhaltenspflicht unverschuldet war oder die Verletzung keinen Einfluss auf den Eintritt des befürchteten Ereignisses und auf den Umfang der von uns geschuldeten Leistungen gehabt hat.» | F Ziff. 4 |
| Secrecy, settlement | M Ziff. 5 | «Sie entbinden Ihren Anwalt uns gegenüber von seinem Berufsgeheimnis. Vor Abschluss eines Vergleiches müssen Sie bzw. Ihr Anwalt unsere Zustimmung einholen.» | F Ziff. 5 |
| Buy-out | M Ziff. 6 | «Prozessauskauf: Wir sind berechtigt, statt die versicherten Leistungen zu erbringen, das wirtschaftliche Interesse ganz oder teilweise zu ersetzen.» | F Ziff. 6 |
| No prospects: own action | M Ziff. 7 | «Lehnen wir es ab, einen Rechtsfall weiterzuführen, weil wir das entsprechende Vorgehen als aussichtslos beurteilen, so können Sie selbst die Ihnen gut scheinenden Massnahmen ergreifen.» | F Ziff. 7 («die entsprechende Vorkehr») |
| No prospects: reimbursement | M Ziff. 7 | «Wenn Sie auf diesem Weg ein Resultat erreichen, das in der Hauptsache günstiger ist als die von uns bei der Ablehnung vorgeschlagene Erledigung, so ersetzen wir Ihnen die Kosten des Verfahrens.» | F Ziff. 7 |
| Disagreement: arbitration | M Ziff. 8 | «Bestehen Meinungsverschiedenheiten über die Erfolgsaussichten des Rechtsstreits oder die von uns vorgeschlagene Erledigung oder Vorgehensweise, so können Sie innert 20 Tagen nach Erhalt unseres Entscheides bei uns ein Schiedsverfahren beantragen. Leiten Sie innerhalb dieser Frist kein Schiedsverfahren ein, gilt dies als Verzicht.» | F Ziff. 8 («seit Erhalt») |
| Arbitrator | M Ziff. 8 | «Schiedsrichter ist eine gemeinsam von Ihnen und uns bestimmte, unabhängige und fachkundige Person. Es gelten die Bestimmungen der Schweizerischen Zivilprozessordnung (ZPO).» | F Ziff. 8 |
| Hourly rate (internal advice) | – | – | **B4 Ziff. 30 lit. a**: «Diese internen Leistungen werden mit CHF 200 pro Stunde an den Betrag gemäss Art. B4 Ziff. 30 lit. d angerechnet.» |
| Advice: scope | – | – | B4 Ziff. 30 lit. c: «Nicht versichert ist beispielsweise das Verfassen von Verträgen und Rechtsschriften sowie Korrespondenz mit Dritten.» |

**Not in the AVB:**

- No rule on external lawyers' hourly rates, cost notes or the form or amount of a cost guarantee beyond the M Ziff. 3 / F Ziff. 3 requirement of «Zustimmung und […] Kostengutsprache».
- No limitation or claim-deadline clause, so VVG Art. 46 applies.
- No clause on cancellation after a claim, so VVG Art. 42 applies.
- Customer deadlines in the AVB: «unverzüglich» (M Ziff. 1); 20 days to request arbitration (M Ziff. 8); 3 months to report a household change (B, E).

---

## 3. Statutory frame (fedlex consolidated texts, filestore HTML)

The URLs were found through the fedlex SPARQL endpoint https://fedlex.data.admin.ch/sparqlendpoint. The paragraph numbers below were checked in the HTML.

**AVO, SR 961.011, version 2026-02-26**, file `20-fedlex-AVO/avo-sr961.011-20260226.html`

- Art. 161: «Durch den Rechtsschutzversicherungsvertrag verpflichtet sich das Versicherungsunternehmen gegen Bezahlung einer Prämie, durch rechtliche Angelegenheiten verursachte Kosten zu vergüten oder in solchen Angelegenheiten Dienste zu erbringen.»
- Art. 163 (Informationspflicht; composite insurers only): «[…] informiert nach Eingang einer Schadenanzeige die versicherte Person mittels Brief mit Zustellnachweis unverzüglich über das Wahlrecht nach Artikel 32 Absatz 1 Buchstabe b VAG.»
- Art. 164 Abs. 4: «Die mit der Schadenbehandlung betrauten Beschäftigten des Schadenregelungsunternehmens dürfen keine vergleichbare Tätigkeit für ein Kompositversicherungsunternehmen ausüben.»
- Art. 166 Abs. 3: «[…] so muss dieses Recht in den Anträgen, Policen, allgemeinen Versicherungsbedingungen und Schadenanzeigeformularen erwähnt und jeweils besonders kenntlich gemacht werden.»
- Art. 167 Abs. 1: «Im Rechtsschutzversicherungsvertrag muss der versicherten Person die freie Wahl einer rechtlichen Vertretung, welche die Qualifikation des auf das Verfahren anwendbaren Rechts erfüllt, eingeräumt werden: a. falls im Hinblick auf ein Gerichts- oder Verwaltungsverfahren ein Rechtsvertreter oder eine Rechtsvertreterin eingesetzt werden muss; b. bei Interessenkollisionen.»
- Art. 167 Abs. 2: «Der Vertrag kann vorsehen, dass bei Ablehnung der gewählten Vertretung durch das Versicherungsunternehmen oder das Schadenregelungsunternehmen die versicherte Person das Recht hat, drei andere Personen für die rechtliche Vertretung vorzuschlagen, von denen eine akzeptiert werden muss.»
- Art. 167 Abs. 3: «Tritt eine Interessenkollision ein, so muss das Versicherungsunternehmen oder das Schadenregelungsunternehmen die versicherte Person auf sein Recht hinweisen.»
- Art. 168: «Die Klausel im Versicherungsvertrag, mit der sich die versicherte Person verpflichtet, ihren Rechtsvertreter […] vom Berufsgeheimnis zu entbinden, ist nicht anwendbar, wenn ein Interessenkonflikt besteht und die Weitergabe der verlangten Information an das Versicherungsunternehmen für die versicherte Person nachteilig sein kann.»
- Art. 169 Abs. 1: «Für den Entscheid von Meinungsverschiedenheiten zwischen der versicherten Person und dem Versicherungsunternehmen oder dem Schadenregelungsunternehmen hinsichtlich der Massnahmen zur Schadenerledigung sieht der Versicherungsvertrag ein Verfahren vor, das vergleichbare Garantien für die Objektivität wie ein Schiedsgerichtsverfahren bietet.»
- Art. 169 Abs. 2: «Lehnt das Versicherungsunternehmen oder das Schadenregelungsunternehmen eine Leistung für eine Massnahme wegen Aussichtslosigkeit ab, so sind die vorgeschlagene Lösung unverzüglich schriftlich zu begründen und die versicherte Person auf die Möglichkeit des Verfahrens nach Absatz 1 hinzuweisen.»
- Art. 169 Abs. 3: «Sieht der Versicherungsvertrag kein Verfahren nach Absatz 1 vor oder unterlässt es das Versicherungsunternehmen […], die versicherte Person im Zeitpunkt der Ablehnung der Leistungspflicht darüber zu informieren, so gilt das Rechtsschutzbedürfnis der versicherten Person im entsprechenden Fall als anerkannt.»
- Art. 169 Abs. 4: «Leitet die versicherte Person bei Ablehnung der Leistungspflicht auf eigene Kosten einen Prozess ein und erlangt sie ein Urteil, das für sie günstiger ausfällt als die ihr […] schriftlich begründete Lösung […], so übernimmt das Versicherungsunternehmen die dadurch entstandenen Kosten bis zum Höchstbetrag der Versicherungssumme.»
- Art. 170: «Das Versicherungsunternehmen und das Schadenregelungsunternehmen dürfen sich keinen Anteil an einem allfälligen Erfolg der versicherten Person versprechen lassen.»

**VAG, SR 961.01, version 2024-09-01**, file `29-fedlex-VAG/vag-sr961.01.html`

- Art. 32 Abs. 1: «Ein Versicherungsunternehmen, welches die Rechtsschutzversicherung gleichzeitig mit anderen Versicherungszweigen betreiben will, muss: a. die Erledigung von Schadenfällen des Zweiges Rechtsschutz einem rechtlich selbstständigen Unternehmen (Schadenregelungsunternehmen) übertragen; oder b. […]»

**VVG, SR 221.229.1, version 2024-01-01**, file `21-fedlex-VVG/vvg-sr221.229.1-20240101.html`

- Art. 14 Abs. 2: «Hat der Versicherungsnehmer oder der Anspruchsberechtigte das Ereignis grobfahrlässig herbeigeführt, so ist das Versicherungsunternehmen berechtigt, seine Leistung in einem dem Grade des Verschuldens entsprechenden Verhältnisse zu kürzen.» Protekta waives this right in A6 Ziff. 3.
- Art. 38 Abs. 1: «Ist das befürchtete Ereignis eingetreten, so muss der Anspruchsberechtigte, sobald er von diesem Ereignisse und seinem Anspruche aus der Versicherung Kenntnis erlangt, das Versicherungsunternehmen benachrichtigen.»
- Art. 38 Abs. 2: «Hat der Anspruchsberechtigte die Anzeigepflicht schuldhafterweise verletzt, so ist das Versicherungsunternehmen befugt, die Entschädigung um den Betrag zu kürzen, um den sie sich bei rechtzeitiger Anzeige gemindert haben würde.»
- Art. 38 Abs. 3: «Das Versicherungsunternehmen ist an den Vertrag nicht gebunden, wenn der Anspruchsberechtigte die unverzügliche Anzeige in der Absicht unterlassen hat, das Versicherungsunternehmen an der rechtzeitigen Feststellung der Umstände […] zu hindern.»
- Art. 39 Abs. 1: «Der Anspruchsberechtigte muss auf Begehren des Versicherungsunternehmens jede Auskunft über solche ihm bekannte Tatsachen erteilen, die zur Ermittlung der Umstände, unter denen das befürchtete Ereignis eingetreten ist, oder zur Feststellung der Folgen des Ereignisses dienlich sind.»
- Art. 39 Abs. 2 Ziff. 2: «[…] bei Verlust des Versicherungsanspruches, binnen bestimmter, angemessener Frist gemacht werden müssen. Die Frist läuft von dem Tage an, an dem das Versicherungsunternehmen den Anspruchsberechtigten, unter Androhung der Säumnisfolgen, schriftlich aufgefordert hat, diese Mitteilungen zu machen.»
- Art. 40: «Hat der Anspruchsberechtigte oder sein Vertreter Tatsachen, welche die Leistungspflicht des Versicherungsunternehmens ausschliessen oder mindern würden, zum Zwecke der Täuschung unrichtig mitgeteilt oder verschwiegen […], so ist das Versicherungsunternehmen gegenüber dem Anspruchsberechtigten an den Vertrag nicht gebunden.»
- Art. 41 Abs. 1: «Die Forderung aus dem Versicherungsvertrage wird mit dem Ablaufe von vier Wochen, von dem Zeitpunkte an gerechnet, fällig, in dem das Versicherungsunternehmen Angaben erhalten hat, aus denen es sich von der Richtigkeit des Anspruches überzeugen kann.»
- Art. 42 Abs. 1–2: «Ist nur ein Teilschaden eingetreten und wird dafür Ersatz beansprucht, so ist das Versicherungsunternehmen wie der Versicherungsnehmer berechtigt, spätestens bei der Auszahlung der Entschädigung vom Vertrage zurückzutreten.» «Wird der Vertrag gekündigt, so erlischt die Haftung des Versicherungsunternehmens 14 Tage, nachdem der anderen Partei die Kündigung mitgeteilt wurde.»
- Art. 45 Abs. 1: «Ist vereinbart worden, dass der Versicherungsnehmer oder der Anspruchsberechtigte wegen Verletzung einer Obliegenheit von einem Rechtsnachteil betroffen wird, so tritt dieser Nachteil nicht ein, wenn: a. die Verletzung den Umständen nach als eine unverschuldete anzusehen ist; oder b. […] keinen Einfluss […] gehabt hat.»
- Art. 45 Abs. 3: «Wo der Vertrag oder dieses Gesetz den Bestand eines Rechtes aus der Versicherung an die Beobachtung einer Frist knüpft, ist der Versicherungsnehmer oder der Anspruchsberechtigte befugt, die ohne Verschulden versäumte Handlung sofort nach Beseitigung des Hindernisses nachzuholen.»
- Art. 46 Abs. 1: «Die Forderungen aus dem Versicherungsvertrag verjähren unter Vorbehalt von Absatz 3 fünf Jahre nach Eintritt der Tatsache, welche die Leistungspflicht begründet.»
- Art. 46 Abs. 2: «Vertragsabreden, die den Anspruch gegen das Versicherungsunternehmen einer kürzern Verjährung oder einer zeitlich kürzern Beschränkung unterwerfen, sind ungültig. Vorbehalten bleibt die Bestimmung des Artikels 39 Absatz 2 Ziffer 2 dieses Gesetzes.»

---

## 4. What Protekta says publicly about how a case runs

Sources: `02-rechtsfall-melden/rechtsfall-melden.html` (https://protekta.mobiliar.ch/rechtsfall-melden), `03-jurline/jurline.html`, `08-ueber-uns/ueber-uns.html` and the product pages `04-privat`, `05-verkehr`, `06-immobilien`.

**Reporting a case**

- The online form is at https://schadenmeldung.mobiliar.ch/protekta/public/osm/1?language=de. It is a JavaScript application. A plain fetch returned 404, so **the form's fields were not read**.
- The report page says: «Melden Sie Ihren Schaden online an und teilen Sie uns mit, was passiert ist und zu welchem Zeitpunkt.»
- Documents requested: «Dies sind in der Regel Verfügungen von Gerichten, Verträge, Korrespondenzen, Offerten, Auftragsbestätigungen, AGB, Rapporte, Rechnungen, Quittungen, Bewilligungen, Einsprachen oder Fotos.»
- Reasons the page gives for when a case exists: «Wenn Fristen laufen» (e.g. «Einsprache, Strafbefehl, Betreibung oder Kündigung»); «Wenn Sie Post von einer Behörde oder Gegenseite erhalten»; «Wenn die Gegenseite Ihrer Forderung nicht nachkommt».

**After the report**

- «Ihre Schadenmeldung wird an eine spezialisierte Juristin oder einen spezialisierten Juristen übergeben, welche für Ihr Anliegen zuständig sind. Wir kontaktieren Sie innerhalb von drei Arbeitstagen und teilen Ihnen die Referenznummer mit.»
- «Sobald wir die fallrelevanten Unterlagen erhalten haben, prüfen wir bereits die Versicherungsdeckung und beurteilen die Sach- und Rechtslage.»
- This is the only handling-time statement found.

**Lawyer bills:** «Für den Beizug eines Anwalts oder für die Einleitung von Verfahrensschritten müssen Sie vorgängig unsere Genehmigung einholen.»

**JurLine**

- 0848 82 00 82, «Montag bis Freitag von 8:00 bis 17:00 Uhr kostenlos».
- «Bitte beachten Sie, dass die JurLine keine Unterlagen prüft.»
- It «prüft, ob es sich um einen versicherten Rechtsfall handelt».
- Callers are identified, «am einfachsten […] mit der Policennummer».

**Staff:** «Heute zählt die Protekta rund 250 Mitarbeitende, davon 200 Juristinnen und Anwälte sowie über 400’000 Kundinnen und Kunden.» (`08-ueber-uns`)

**Mediation:** the AVB cover «Mediations- und Anwaltshonorare» (A4 Ziff. 3 lit. a). In the family-law cover (D1 Ziff. 8): «übernehmen wir die Kosten für eine Mediation oder alternativ die Kosten für einen gemeinsam beauftragten Anwalt zum Aufsetzen einer Trennungs- oder Scheidungskonvention.»

**Published example cases:**

- `04-privat`: divorce mediation, inheritance, photo published without consent, travel, pet ownership, overtime after dismissal, employment reference, domestic employee, neighbour's trees, scratched glass in a construction contract, landlord's notice, wrong medication, insurer after burglary, accident insurer refusing to pay, tax deduction appeal, criminal proceedings after a fire, gift tax.
- `05-verkehr`: criminal case after a collision on ice, used car not accident-free, damages after a right-of-way accident, licence withdrawal, accident and disability insurers after whiplash.
- `06-immobilien`: heating contractor, cracks from a construction site, objections to a building permit, neighbour's rotten trees, tenant staying after notice, rent reduction claim.

---

## 5. Which legal areas generate most cases

- **AXA-ARAG, media release 2026-03-31** (`30-axa-arag-ranking-2026/axa-rechtsstreit-ranking-2026.html`): «beim Thema Wohnen mit den Rechtsgebieten Mietrecht, Nachbarrecht, Baurecht, Vertrags- und Persönlichkeitsrecht mit rund 46 Prozent die meisten Rechtsfälle». «Mit 18,5 Prozent kommt es auch vermehrt zu Rechtsfällen im Bereich Mobilität». «Auch rund ums Arbeitsrecht kommt es mit einem Anteil von 17 Prozent häufig zu Unstimmigkeiten.» «Bei den verbleibenden Fällen handelt es sich meist um gesundheits- oder familienrechtliche Themen.»
- **TCS Streitbarometer** (`31-tcs-streitbarometer-2019/tcs-streitbarometer-2019.html`; the URL says 2019 but the content compares 2024 with 2019):
  - «Der Bereich Wohnen, der sowohl Miete als auch Eigentum umfasst, ist in der Schweiz nach wie vor die weitaus häufigste Quelle für Rechtsstreitigkeiten. Diese machen fast ein Drittel aller Rechtsfälle aus».
  - Konsum und Internet ranks second, ahead of Gesundheit und Versicherungen.
  - «Im Schnitt dauerte es bei Fällen aus dem Bereich Gesundheit & Versicherungen 315 Tage».
- **Ombudsman der Privatversicherung und der Suva, Jahresbericht 2025** (`33-ombudsman-jb-2025/OM-Jahresbericht_2025.pdf`): «Ein grosser Anstieg der Fallzahlen fand insbesondere auch in der Rechtsschutz-Branche von 375 auf 660 (76%) statt.» It reports many complaints about insurers cancelling policies after a claim under VVG Art. 42.
- **Protekta:** no breakdown by legal area found. The Mobiliar Geschäftsbericht 2025 (`34-mobiliar-gb-2025/Mobiliar-Geschaeftsbericht-2025.pdf`) shows premiums only («Rechtsschutzversicherung 186 885», in CHF thousand; prior year 175 876).
- **SVV:** no statistics found.

---

## 6. Conclusions (Inference unless a source is cited)

### 6(a) Cover-decision checklist (Inference: order and grouping)

P = needs policy data; F = answerable from the customer's file. The passages are verbatim from P01.2026; the U09.2025 column shows the corresponding section and notes differences.

| # | Question | Verbatim basis (P01.2026, section) | U09.2025 | P/F |
|---|---|---|---|---|
| 1 | Is a policy in force and the premium not in arrears? | A1 Ziff. 3: «Der Versicherungsschutz beginnt unter Vorbehalt der Wartefrist mit dem auf der Police genannten Datum und gilt für die vereinbarte Dauer.» A1 Ziff. 4: «Wenn Sie die Prämie trotz Mahnung nicht bezahlen, ruht unsere Leistungspflicht bis zur vollständigen Bezahlung der rückständigen Prämie samt Zinsen und Kosten.» | A1 Ziff. 2–3 | P |
| 2 | Is the claimant an insured person? | A1 Ziff. 2: «Sie sind gemäss Angaben auf Ihrer Police als Einzelperson oder als Mehrpersonenhaushalt versichert.» B: «Versichert sind die folgenden Personen mit Wohnsitz in der Schweiz oder im Fürstentum Liechtenstein:» | A2 (insured company), B1 (persons), C1 Ziff. 2, C2 Ziff. 1, D1 Ziff. 1 | F + P |
| 3 | In an insured capacity? | C: «Die Personen gemäss Art. B sind in den folgenden Eigenschaften versichert:» E: «bei Ereignissen und Reisen im privaten oder öffentlichen Verkehr und aus Rechtsfällen, die ein versichertes Fahrzeug betreffen» H Ziff. 3: «Streitigkeiten, die im direkten Zusammenhang mit einer versicherten Immobilie oder einer versicherten beweglichen Sache gemäss Art. H Ziff. 2 stehen.» | B2 (professional activity per policy), B3, C1 Ziff. 3, C2 Ziff. 2, D1 Ziff. 3 | F |
| 4 | Is the legal area covered and included in the policy? | D, F, I: «Ihre Police gibt darüber Auskunft, welche der folgenden Rechtsgebiete versichert sind.» J lit. a: «vorstehend nicht aufgeführte Bereiche;» | B4, C3, D2; E1 lit. a | F (classify) + P (inclusion) |
| 5 | Area conditions met? | D2 Ziff. 1: «Es gilt voller Versicherungsschutz bis zu dem in der Police genannten Streitwert.» D1 Ziff. 6: «Die Forderung beträgt mindestens CHF 500 und» D3 Ziff. 4: «Der Versicherungsschutz besteht, wenn die Kosten des gesamten Bauvorhabens den in der Police genannten Betrag nicht übersteigen.» D4 Ziff. 2: «Nicht versichert sind das Einspracheverfahren bei der Steuerverwaltung und Verfahren betreffend Nach- und Strafsteuern.» | B4 Ziff. 9 («Bis zu zehn Mal pro Kalenderjahr»), Ziff. 18, Ziff. 27; no amount-in-dispute clause in B4 Ziff. 13 | F + P |
| 6 | Did the cause and the need for cover arise within the contract, with the cause not before the application? | A2 Ziff. 1: «Ein Rechtsfall ist gedeckt, wenn seine Ursache und der Bedarf nach Rechtsschutz während der für das betroffene Risiko geltenden Vertragsdauer eintreten. Nicht gedeckt ist ein Rechtsfall, dessen Ursache bei Antragsstellung bereits eingetreten ist.» A2 Ziff. 2: «Im Allgemeinen gilt die erstmalige tatsächliche oder angebliche Rechts- oder Vertragsverletzung als Ursache.» | A3 Ziff. 1–3 (no explicit sentence on the application date) | F (dates) + P (start, risk inclusion) |
| 7 | Is the cause outside the waiting period? | A2 Ziff. 4: «Nicht versichert ist ein Rechtsfall, dessen Ursache innerhalb einer Wartefrist eintritt.» | A3 Ziff. 4 | P (+ prior-insurer data) |
| 8 | Is the forum, law and enforcement within the insured territory? | A3 Ziff. 4: «Der Versicherungsschutz besteht, soweit für die Beurteilung des Rechtsstreits Gerichte oder Verwaltungsbehörden im versicherten Gebiet zuständig sind, entsprechendes Landes- oder Gemeinschaftsrecht zur Anwendung kommt und im versicherten Gebiet vollstreckt werden kann.» | A4 Ziff. 4 | F + P (territory per area) |
| 9 | Does no exclusion apply? | J: «Kein Versicherungsschutz besteht im Zusammenhang mit Folgendem:» (lit. a–u); K (lit. a–d); L (lit. a–l); G Ziff. 1 (traffic) | E1 (a–u), E2 (a–d), E3 (a–l), C4 | F |
| 10 | Is intent alleged in criminal proceedings? | J lit. n: «Endet jedoch ein solches Verfahren durch rechtskräftigen Entscheid mit einer Nichtanhandnahme, einer Einstellung oder einem Freispruch, so erbringen wir die versicherten Leistungen am Ende des Verfahrens rückwirkend.» A4 Ziff. 3 lit. b: «Vorschussleistungen, für welche gemäss Art. J lit. n keine Versicherungsdeckung besteht, sind uns zurückzuerstatten;» | E1 lit. n; A5 Ziff. 3 lit. b | F |
| 11 | What limits apply (sum insured, deductible, aggregation)? | A1 Ziff. 1: «die zugehörigen Versicherungssummen […] sowie allfällige Wartefristen und Selbstbehalte.» A5 Ziff. 2: «Für die Kostenübernahme gemäss Art. A4 Ziff. 3 gilt ein Selbstbehalt, wenn er in Ihrer Police vereinbart ist.» A6 Ziff. 2 lit. b: «so gelten diese gesamthaft als ein Rechtsstreit» | A1 Ziff. 1, A6, A7 | P |
| 12 | Were the duties met (reporting, documents, no unapproved steps)? | M Ziff. 1: «Wenn Sie unsere Leistungen beanspruchen möchten, müssen Sie uns unverzüglich informieren und uns alle Unterlagen […] betreffend den Rechtsfall zustellen.» M Ziff. 4: «so können wir unsere Leistungen ablehnen oder kürzen. Dieser Nachteil tritt nicht ein, wenn Sie beweisen, dass […]» | F Ziff. 1, F Ziff. 4 | F |
| 13 | Is a lawyer needed or is there a conflict of interest? | M Ziff. 3: «Ist der Beizug eines Anwaltes erforderlich oder besteht eine Interessenkollision, dürfen Sie einen Anwalt […] frei wählen und vorschlagen. Vor Beauftragung des Anwaltes müssen Sie unsere Zustimmung und unsere Kostengutsprache einholen.» | F Ziff. 3 | F |
| 14 | Are there sufficient prospects of success? | M Ziff. 7: «Lehnen wir es ab, einen Rechtsfall weiterzuführen, weil wir das entsprechende Vorgehen als aussichtslos beurteilen, […]» M Ziff. 8: «[…] so können Sie innert 20 Tagen nach Erhalt unseres Entscheides bei uns ein Schiedsverfahren beantragen.» | F Ziff. 7–8 | F |
| 15 | Do sanctions stand in the way? | A1 Ziff. 10: «[…] soweit und solange anwendbare gesetzliche Wirtschafts-, Handels- oder Finanzsanktionen entgegenstehen.» | A1 Ziff. 10 | F |

### 6(b) Further legal areas deserving their own module, with statutory deadlines

**Inference:** the ranking is mine, based on AXA-ARAG (mobility 18.5%), TCS (consumption second, then health and insurance) and Protekta's published example cases. All passages below are verbatim from the saved fedlex texts; "verified" means the wording was checked there. Each passage is at most 40 words.

**1. Traffic criminal and administrative proceedings**

| Law | Article | Version, file | Verbatim | Status |
|---|---|---|---|---|
| StPO, SR 312.0 | Art. 354 Abs. 1 | 2025-04-01, `24-fedlex-StPO/stpo-sr312.0-20250401.html` | «Gegen den Strafbefehl können bei der Staatsanwaltschaft innert 10 Tagen schriftlich Einsprache erheben: a. die beschuldigte Person;» | verified |
| StPO, SR 312.0 | Art. 354 Abs. 3 | same | «Ohne gültige Einsprache wird der Strafbefehl zum rechtskräftigen Urteil.» | verified |
| StPO, SR 312.0 | Art. 396 Abs. 1 | same | «Die Beschwerde gegen schriftlich oder mündlich eröffnete Entscheide ist innert 10 Tagen schriftlich und begründet bei der Beschwerdeinstanz einzureichen.» | verified |
| Cantonal | licence-withdrawal appeal deadlines | – | – | **not verified** |

**2. Damages and personal injury**

| Law | Article | Version, file | Verbatim | Status |
|---|---|---|---|---|
| OR, SR 220 | Art. 60 Abs. 1 | 2026-10-01, `22-fedlex-OR/or-sr220-20261001.html` | «Der Anspruch auf Schadenersatz oder Genugtuung verjährt mit Ablauf von drei Jahren von dem Tage an gerechnet, an welchem der Geschädigte Kenntnis vom Schaden und von der Person des Ersatzpflichtigen erlangt hat, jedenfalls aber mit Ablauf von zehn Jahren […]» | verified |
| OR, SR 220 | Art. 60 Abs. 1bis | same | «Bei Tötung eines Menschen oder bei Körperverletzung verjährt der Anspruch […] jedenfalls aber mit Ablauf von zwanzig Jahren, vom Tage an gerechnet, an welchem das schädigende Verhalten erfolgte oder aufhörte.» | verified. Correction: the earlier hand-back called this «Abs. 2»; it is Abs. 1bis. |
| SVG, SR 741.01 | Art. 83 Abs. 1 | 2026-07-01, `26-fedlex-SVG/svg-sr741.01-20260701.html` | «Schadenersatz- und Genugtuungsansprüche aus Unfällen mit Motorfahrzeugen, Fahrrädern und fahrzeugähnlichen Geräten verjähren nach den Bestimmungen des Obligationenrechts über die unerlaubten Handlungen.» | verified |

**3. Social insurance**

| Law | Article | Version, file | Verbatim | Status |
|---|---|---|---|---|
| ATSG, SR 830.1 | Art. 52 Abs. 1 | 2024-01-01, `25-fedlex-ATSG/atsg-sr830.1-20240101.html` | «Gegen Verfügungen kann innerhalb von 30 Tagen bei der verfügenden Stelle Einsprache erhoben werden; davon ausgenommen sind prozess- und verfahrensleitende Verfügungen.» | verified |
| ATSG, SR 830.1 | Art. 60 Abs. 1 | same | «Die Beschwerde ist innerhalb von 30 Tagen nach der Eröffnung des Einspracheentscheides oder der Verfügung, gegen welche eine Einsprache ausgeschlossen ist, einzureichen.» | verified |
| ATSG, SR 830.1 | Art. 60 Abs. 2 | same | «Die Artikel 38–41 sind sinngemäss anwendbar.» | verified; Art. 38–41 were later extracted and are the social-insurance counting rule (docs/AREAS.md) |

**4. Private insurance**

| Law | Article | Version, file | Verbatim | Status |
|---|---|---|---|---|
| VVG, SR 221.229.1 | Art. 46 Abs. 1 | 2024-01-01, `21-fedlex-VVG/vvg-sr221.229.1-20240101.html` | «Die Forderungen aus dem Versicherungsvertrag verjähren unter Vorbehalt von Absatz 3 fünf Jahre nach Eintritt der Tatsache, welche die Leistungspflicht begründet.» | verified |
| VVG, SR 221.229.1 | Art. 41 Abs. 1 | same | «Die Forderung aus dem Versicherungsvertrage wird mit dem Ablaufe von vier Wochen, von dem Zeitpunkte an gerechnet, fällig, in dem das Versicherungsunternehmen Angaben erhalten hat, aus denen es sich von der Richtigkeit des Anspruches überzeugen kann.» | verified |

**5. Consumer and sale of goods (incl. used cars)**

| Law | Article | Version, file | Verbatim | Status |
|---|---|---|---|---|
| OR, SR 220 | Art. 201 Abs. 1 | 2026-10-01, `22-fedlex-OR/or-sr220-20261001.html` | «Der Käufer soll, sobald es nach dem üblichen Geschäftsgange tunlich ist, die Beschaffenheit der empfangenen Sache prüfen und, falls sich Mängel ergeben, für die der Verkäufer Gewähr zu leisten hat, diesem sofort Anzeige machen.» | verified |
| OR, SR 220 | Art. 210 Abs. 1 | same | «Die Klagen auf Gewährleistung wegen Mängel der Sache verjähren mit Ablauf von zwei Jahren nach deren Ablieferung an den Käufer, selbst wenn dieser die Mängel erst später entdeckt, […]» | verified |

**6. Construction and building owners**

| Law | Article | Version, file | Verbatim | Status |
|---|---|---|---|---|
| OR, SR 220 | Art. 367 Abs. 1bis | 2026-10-01, `22-fedlex-OR/or-sr220-20261001.html` | «Die Frist für die Mängelrüge beträgt bei einem unbeweglichen Werk 60 Tage. Die Vereinbarung einer kürzeren Frist ist unwirksam.» | verified |
| OR, SR 220 | Art. 371 Abs. 1 | same | «Die Ansprüche des Bestellers wegen Mängel des Werkes verjähren mit Ablauf von zwei Jahren nach der Abnahme des Werkes.» | verified |
| OR, SR 220 | Art. 371 Abs. 2 | same | «Die Ansprüche des Bestellers eines unbeweglichen Werkes wegen allfälliger Mängel des Werkes verjähren gegen den Unternehmer sowie gegen den Architekten oder den Ingenieur, die zum Zwecke der Erstellung Dienste geleistet haben, mit Ablauf von fünf Jahren seit der Abnahme des Werkes.» | verified |
| ZGB, SR 210 | Art. 839 Abs. 2 | 2026-07-01, `28-fedlex-ZGB/zgb-sr210-20260701.html` | «Die Eintragung hat bis spätestens vier Monate nach der Vollendung der Arbeit zu erfolgen.» | verified |

**7. Debt collection and enforcement**

| Law | Article | Version, file | Verbatim | Status |
|---|---|---|---|---|
| SchKG, SR 281.1 | Art. 74 Abs. 1 | 2026-01-01, `27-fedlex-SchKG/schkg-sr281.1-20260101.html` | «Will der Betriebene Rechtsvorschlag erheben, so hat er dies sofort dem Überbringer des Zahlungsbefehls oder innert zehn Tagen nach der Zustellung dem Betreibungsamt mündlich oder schriftlich zu erklären.» | verified |
| SchKG, SR 281.1 | Art. 83 Abs. 2 | same | «Der Betriebene kann indessen innert 20 Tagen nach der Rechtsöffnung auf dem Weg des ordentlichen Prozesses beim Gericht des Betreibungsortes auf Aberkennung der Forderung klagen.» | verified |
| OR, SR 220 | Art. 128 | 2026-10-01, `22-fedlex-OR/or-sr220-20261001.html` | «Mit Ablauf von fünf Jahren verjähren die Forderungen: 1. für Miet-, Pacht- und Kapitalzinse sowie für andere periodische Leistungen; […] 3. aus Handwerksarbeit, Kleinverkauf von Waren, […] sowie aus dem Arbeitsverhältnis von Arbeitnehmern.» | verified |

**8. Inheritance**

| Law | Article | Version, file | Verbatim | Status |
|---|---|---|---|---|
| ZGB, SR 210 | Art. 567 Abs. 1–2 | 2026-07-01, `28-fedlex-ZGB/zgb-sr210-20260701.html` | «Die Frist zur Ausschlagung beträgt drei Monate.» «Sie beginnt für die gesetzlichen Erben, soweit sie nicht nachweisbar erst später von dem Erbfall Kenntnis erhalten haben, mit dem Zeitpunkte, da ihnen der Tod des Erblassers bekannt geworden, […]» | verified |
| ZGB, SR 210 | Art. 533 Abs. 1 | same | «Die Herabsetzungsklage verjährt mit Ablauf eines Jahres von dem Zeitpunkt an gerechnet, da die Erben von der Verletzung ihrer Rechte Kenntnis erhalten haben, und in jedem Fall mit Ablauf von zehn Jahren, […]» | verified |

**Cross-cutting civil procedure**

| Law | Article | Version, file | Verbatim | Status |
|---|---|---|---|---|
| ZPO, SR 272 | Art. 209 Abs. 3 | 2026-07-01, `23-fedlex-ZPO/zpo-sr272-20260701.html` | «Nach Eröffnung berechtigt die Klagebewilligung während dreier Monate zur Einreichung der Klage beim Gericht.» | verified |
| ZPO, SR 272 | Art. 209 Abs. 4 | same | «In Streitigkeiten aus Miete und Pacht von Wohn- und Geschäftsräumen sowie aus landwirtschaftlicher Pacht beträgt die Klagefrist 30 Tage.» | verified |
| ZPO, SR 272 | Art. 311 Abs. 1 | same | «Die Berufung ist bei der Rechtsmittelinstanz innert 30 Tagen seit Zustellung des begründeten Entscheides beziehungsweise seit der nachträglichen Zustellung der Entscheidbegründung (Art. 239) schriftlich und begründet einzureichen.» | verified |
| ZPO, SR 272 | Art. 145 Abs. 1 | same | «Gesetzliche und gerichtliche Fristen stehen still: a. vom siebten Tag vor Ostern bis und mit dem siebten Tag nach Ostern; b. vom 15. Juli bis und mit dem 15. August; c. vom 18. Dezember bis und mit dem 2. Januar.» | verified |
| ZPO, SR 272 | Art. 145 Abs. 2 | same | «Dieser Fristenstillstand gilt nicht für: a. das Schlichtungsverfahren; b. das summarische Verfahren.» | verified |

**Also extracted, for the existing tenancy and employment modules** (OR, SR 220, version 2026-10-01, `22-fedlex-OR/or-sr220-20261001.html`, all verified):

- Art. 273 Abs. 1: «Will eine Partei die Kündigung anfechten, so muss sie das Begehren innert 30 Tagen nach Empfang der Kündigung der Schlichtungsbehörde einreichen.»
- Art. 270b Abs. 1: «Der Mieter kann eine Mietzinserhöhung innert 30 Tagen, nachdem sie ihm mitgeteilt worden ist, bei der Schlichtungsbehörde als missbräuchlich im Sinne der Artikel 269 und 269a anfechten.»
- Art. 336b Abs. 1: «Wer gestützt auf Artikel 336 und 336a eine Entschädigung geltend machen will, muss gegen die Kündigung längstens bis zum Ende der Kündigungsfrist beim Kündigenden schriftlich Einsprache erheben.»
- Art. 336b Abs. 2 (excerpt): «Wird nicht innert 180 Tagen nach Beendigung des Arbeitsverhältnisses eine Klage anhängig gemacht, ist der Anspruch verwirkt.»

### 6(c) Insurer duties with a legally required form or content

The legal basis of each point is cited. Where a point is my conclusion rather than the source's wording, it is marked **Inference**.

1. **Refusal for lack of prospects (AVO Art. 169 Abs. 2–3).** The proposed solution must be reasoned in writing without delay, and the decision must point to the disagreement procedure. If either is missing, the need for cover is deemed accepted.
   - **Inference:** the AVB (M Ziff. 7–8 / F Ziff. 7–8) do not themselves state this duty to give reasons, so the tool should enforce the required form and content in every refusal letter. A decision letter should also state the 20-day arbitration deadline from M Ziff. 8.
2. **Conflict of interest (AVO Art. 167 Abs. 3).** The insurer must tell the customer about the free choice of lawyer. After rejecting a lawyer, it must accept one of three alternatives (Art. 167 Abs. 2; AVB M Ziff. 3).
3. **Professional-secrecy waiver (AVO Art. 168).** The waiver in M Ziff. 5 is not applicable where there is a conflict of interest and disclosure would harm the customer.
4. **No share in the outcome (AVO Art. 170).**
5. **Information requests (VVG Art. 39 Abs. 2 Ziff. 2).** Losing the claim for missing information requires a written demand, a reasonable deadline and a warning of the consequences.
6. **Due date (VVG Art. 41).** The benefit falls due 4 weeks after the insurer has the information it needs.
7. **Breach of duties (VVG Art. 38 Abs. 2, Art. 45).** A disadvantage applies only with fault and causal effect. For late notice, the reduction is limited to the amount the loss would have been smaller.
   - **Inference:** M Ziff. 4 («ablehnen oder kürzen») is worded more broadly, so a breach reduction should be computed and justified against these articles.
8. **Cancellation after a claim (VVG Art. 42).** It must be given at the latest when the indemnity is paid; the ombudsman report 2025 reads this, for legal protection, as with the last legal-protection benefit. Liability ends 14 days after notice.
9. **Limitation (VVG Art. 46).** Five years; contractual shortening is invalid.
10. **Composite-insurer rules (AVO Art. 163, 166 Abs. 3).** These require a letter with proof of delivery about the right to choose, and prominent mention in forms.
    - **Inference, not verified:** they apply to composite insurers. Protekta writes only legal-protection insurance, so they likely do not apply to it.

---

## 7. Not found or not verified

- Protekta publishes no PDF of the private AVB 01.2026; the content here comes from the public viewer API.
- The fields of the online reporting form (JavaScript app, 404 without a browser).
- Protekta's own case statistics by legal area, and overall handling times beyond «innerhalb von drei Arbeitstagen».
- Amount-in-dispute caps per package for employment law: they are in the policy or premium calculator, not in the static pages.
- The waiting-period list comes from the product page FAQ, not the AVB.
- Conditions for agriculture, medical professionals and municipalities/authorities.
- The GastroSuisse AVB 01.2024 was fetched but not compared.
- SVV statistics.
- Cantonal deadlines (licence withdrawal, tax). ATSG Art. 38–41, the StPO, ZPO and SchKG counting rules, the OBG, the IVG and the federal holiday (BV Art. 110 Abs. 3) were extracted later for the counting rules (docs/AREAS.md); their files are 36–39 in the sources index.
- The private AVB 08.2023 was checked only through its table of contents.
