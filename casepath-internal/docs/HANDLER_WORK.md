# Built around the handler's work

## The idea in one line

A handler does not want facts, a graph or a checklist. A handler wants the **next piece of work, already done**: the letter written, the decision reasoned, the follow-up dated. CasePath's job is to hand them that, show why, and learn from what they change before it goes out.

## How a handler's work actually runs (from the seven development dossiers)

Every document Protekta itself produced in D1, D3, D6, D8, D9, D10 and D11, read as the record of a handler's work. Counts are dossiers out of 7.

| Kind | Action | In | Triggered by |
|---|---|---|---|
| A0 | Automatic receipt of the online claim | 6 | the claim |
| A1 | First request: provisional registration, document list, 1–3 questions on facts, often first legal hints, the deadline sentence | 7 | a claim with too few documents; 0–2 working days |
| A2 | Phone call and file note (also "nicht erreicht") | 4 | unclear facts, the customer calling |
| A3 | Upload link | 2 | large files, after a call |
| A4 | Question back on one point (an expert's visit, a measurement) | 2 | an answer that leaves one point open |
| A5 | Legal assessment to the customer: rights, conditions, what follows here, recommendation | 3 | documents arrived, or "what can I do" |
| A6 | Pending with a deadline: "ohne Rückmeldung bis <Datum> … schliessen" | 2 | after a call or silence; 3–4 weeks out |
| A7 | Status inquiry announcing closure | 1 | months of silence |
| A8 | Letter to the other side for the customer (representation, unpräjudiziell, demand with deadline), draft to the customer first | 1 | the customer wants action and the matter is standard |
| A9 | Negotiation: offer, counter-offer, acceptance with reservations, reminders | 1 | a reply from the other side or its lawyer |
| A10 | Mandate to a law firm: request, cost guarantee, transfer link, information to the customer, all on one day | 1 | value or complexity beyond advice |
| A11 | Payment handling: IBAN, payout chased, receipt confirmed | 1 | a settlement |
| A12 | Closing, or end of benefits for lack of cooperation | 2 (others close silently after A6/A7) | payment, silence, documents still missing after repeated requests |

**What this says about the work.**
1. **Most of it is waiting and chasing.** After A1 every case runs on dates: pending until X, reminder, closing. The product needs a clock.
2. **The phone is a main channel.** Decisions are taken on calls and written as short dated notes; notes are evidence.
3. **A1 is not only a document list.** It asks one to three questions and often gives first legal hints.
4. **Three ways a case ends:** silence (A6, A7), payment (A11, A12), lack of cooperation (A12).
5. **Two more actors:** the other side or its lawyer, and an external law firm under a cost guarantee; the handler decides "selbst führen oder mandatieren".
6. **Drafts to the other side go to the customer first.**

**Forms** (structure and standard wording). Every letter: "Unsere Referenz <Nr>" → greeting → "Vielen Dank für …" → body → "Für Ihre Kenntnisnahme und Bemühungen danken wir Ihnen bestens. Bei Fragen stehen wir Ihnen gerne zur Verfügung." → signature.
A1: registration → "Um die Versicherungsdeckung prüfen und die Sach- und Rechtslage beurteilen zu können, brauchen wir insbesondere noch:" → list ending "allfällige weitere relevante Unterlagen und Informationen" → questions → hints (Art. 257g OR, Mängelrüge per Einschreiben, document continuously) → "bis zur definitiven Deckungsprüfung … selbst für die Einhaltung allfällig laufender Fristen zuständig".
A6/A7: thanks for the call or the time since the last contact → state of things → "Ohne Ihre Rückmeldung bis <Datum> gehen wir davon aus, dass sich der Fall erledigt hat, und wir Ihr Dossier daher schliessen können."
A5: "Grundsätzlich hat die Mieterschaft …" → rights → conditions → this case → recommendation.
A8: "zeigen Ihnen an, dass wir die Interessen … vertreten" → "unpräjudiziell und ohne Anerkennung einer Rechtspflicht" → facts → defects → demand and deadline.
A10: "Kostengutsprache nach den bekannten Modalitäten wie folgt: Abklärung der Sach- und Rechtslage sowie aussergerichtliche Bemühungen" → prior contact for any extension → copies of the main documents.
A12 (end of benefits): what was asked, when, still missing → benefits end.

The handler's own process, written from this and the law, is the backbone `casepath/process/areas/backbone.json` with the area module `casepath/process/areas/mietmangel-handler.json` (composed at load, see docs/AREAS.md): Eingang → Deckung und Sachverhalt klären → Beurteilen und beraten → Vorgehen (selbst | Mandat) → Abwicklung → Abschluss (Stillschweigen | Beratung | Zahlung | fehlende Mitwirkung). Each stage names the action it ends in. Cover and the way to proceed are the handler's decisions. The OSM+ flow stays the intake.

## What follows for the product

1. **The centre of the screen is the prepared action**, not the case description. "Vorbereitet: Eingangsbestätigung mit Unterlagenanforderung", the draft in Protekta's form, ready to adjust and use. Der Fall is its context; the points needing judgment are what stands between the draft and sending it.
2. **Every action shows its reasons as a chain the handler can pull on.** This letter, because the case is at this step, because these facts hold (each with its sentence), asking for these documents (each because of a step or an article). Clicking any link shows it; changing any link changes everything after it, at once.
3. **Feedback is the handler finishing the work, nothing else.** They strike a document from the request, add one, change a fact, reword a paragraph, pick another action. Each of those is a precise statement about what CasePath got wrong, and the one-tap reason says which kind of wrong.
4. **A case has a next date.** After an action goes out, CasePath proposes when to look again and what for ("Unterlagen bis … erwartet"). Deadlines found in the file and deadlines the handler's own letter sets are the same list.
5. **When something arrives, CasePath is already there.** New files move the case to its next action without anyone asking; the handler opens it and sees what came, what changed, and the next piece of work prepared.
6. **The file note writes itself.** What was received, what was decided and why, what went out, what is awaited: one paragraph the handler can paste into the case system.

## The screen, re-centred

```
┌ Übersicht ─────────────────────────────────────────────────────────────┐
│ Vorbereitet                                        Vorher zu klären · 2 │
│ ┌────────────────────────────────────────────┐     ○ Vermieter informiert? [ja][nein]
│ │ Eingangsbestätigung · Unterlagenanforderung │     ○ Prozess bestätigen: auch «…»
│ │ Sehr geehrte …                              │
│ │ … brauchen wir insbesondere noch:           │   Warum dieser Schritt
│ │  ☑ Mietvertrag                    Art. 253  │     Stand: Sachverhalt klären
│ │  ☑ Sämtliche Korrespondenz        6 von 7   │     weil: Mangel gemeldet (S. 3) …
│ │  ☐ Fotos über die Dauer    liegen z. T. vor │
│ │  + Unterlage hinzufügen                     │   Der Fall
│ │ [Kopieren]  [Erledigt]  [mit Vorbehalt]     │     Anliegen · Parteien · Fristen
│ └────────────────────────────────────────────┘     Nächste Wiedervorlage: …
└────────────────────────────────────────────────────────────────────────┘
```

- **The document list in the letter is the checklist.** A tick is a request; unticking or adding is a correction with its reason in one tap; each line carries why it is there. The surrounding text stays editable as text.
- **"Vorher zu klären" holds only what blocks this action.** When it is empty the draft is ready.
- **"Warum dieser Schritt"** is the chain: step, the facts that led there with their sources, and what the step demands.
- During a run this same screen fills in, as section U of the handler bar describes.

## What each handler gesture teaches

| The handler | CasePath learns | Improves |
|---|---|---|
| unticks a document, "hier nicht relevant" | the need's condition is too wide | the process's document requirements (precision) |
| unticks, "gilt generell so" | the need should not be asked at this step at all | Knowledge, after replay |
| adds a document, "gilt generell so" | a need is missing at this step | Knowledge, after replay (completeness) |
| adds a document, "weiss ich von ausserhalb" | nothing: CasePath could not have known | the honesty of the numbers |
| changes a fact, "steht anders in den Akten" | a reading error, with the sentence | the reader |
| picks another action or step | the path was wrong: which fact or condition sent it there | the process (workflow accuracy) |
| rewords the letter | the form or tone is not Protekta's | the letter forms |
| changes the proposed date | the waiting time for this action | follow-up rules |
| closes "mit Vorbehalt" | the case needs a second look | where CasePath is least trusted |

## What we take from the dossiers (development dossiers only)

Read each of the seven development dossiers whole, as the record of a handler's work, and report in general terms, never case content:

1. **The chain of actions:** every document Protekta itself produced, in order: what kind of action, what had arrived just before, how long after, what it asks or states, what date it sets. One table of action kinds with how often each occurs and what triggers it.
2. **The form of each action's letter:** its parts in order and what each part does. Structure and standard wording only.
3. **What the handler had to know to write it:** which facts and which documents each action evidently rests on. That is the action's justification chain, and it tells us what CasePath must have established before it may prepare that action.
4. **Where the handler waited or chased:** reminders sent, documents asked for twice, questions asked back. These are the frustrations, and each one is a place where CasePath can be there first.
5. **File notes,** if the dossiers contain any: their form.

From this comes the list of actions CasePath prepares, in the order they occur most often, and the form of each. The first is already built (the first request). The second and third most frequent are built next.

## The bar

A handler opens a case and the next piece of work is lying there, in their own form, with its reasons one click away. They change what they would change anyway, in the place where it is, and use it. Nothing else is asked of them, and every change they made makes the next case need fewer.
