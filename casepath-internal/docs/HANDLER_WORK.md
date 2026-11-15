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

**Built on these forms** (`casepath/process/mandate.py`, `settlement.py`, `customer_letters.py`):
- **Mandate package (A10), one action, four letters each copied on its own**: the request to the firm (customer, other side, the task by the guarantee's scope), the cost guarantee (`A10_kostengutsprache`: «nach den bekannten Modalitäten», the scope the handler picks from the backbone's options, out of court by default; an amount only when the handler enters one; prior contact for any extension; regular reports and copies of the main documents), a one-page summary for the firm (`A10_zusammenfassung`, built from what CasePath established: parties, request, facts in time order, key points with articles, what the file holds by kind, what is open, deadlines and set dates, the customer's aim; each line with its page or article, «nicht in der Akte» where silent) and the customer's information (`A10_kunde`). The file note lists all four and which were copied.
- **Settlement and payout (A11, the insurer conducting the case)**: Einigung festhalten (amount, payer, date from the file, with the source; the handler confirms) → Bankverbindung erfragen, once (an IBAN of the customer in the file is shown and not asked) → Auszahlung ankündigen → Zahlungseingang bestätigen → Dossier schliessen. A step done (its letter copied, or the file shows it) is not proposed again. The running account of the case, once kept, plugs in at `settlement.agreement(account=…)`.
- **Fee-note check (A11_kosten)**: guarantee given on (date) with scope, extension, the firm's reports (count, last), the claim's amount and period, each with its source or «nicht in der Akte», and the scope as a question («Gerichtliche Schritte abgerechnet? …»). Then pay (payment system), query (`A11_rueckfrage`) or refuse in part with the reason as a gap (`A11_teilablehnung`).
- **Customer letters**: templates per area the customer sends in his own name (docs/AREAS.md).

The cover decision is prepared as ten points with their clauses, and letters whose content the law prescribes are guarded: see docs/COVER.md.

The handler's own process, written from this and the law, is the backbone `casepath/process/areas/backbone.json` with the area module `casepath/process/areas/mietmangel-handler.json` (composed at load, see docs/AREAS.md): Eingang → Deckung und Sachverhalt klären → Beurteilen und beraten → Vorgehen (selbst | Mandat) → Abwicklung → Abschluss (Stillschweigen | Beratung | Zahlung | fehlende Mitwirkung). Each stage names the action it ends in. Cover and the way to proceed are the handler's decisions. The OSM+ flow stays the intake.

## What follows for the product

1. **The centre of the screen is the prepared action**, not the case description. "Vorbereitet: Eingangsbestätigung mit Unterlagenanforderung", the draft in Protekta's form, ready to adjust and use. Der Fall is its context; the points needing judgment are what stands between the draft and sending it.
2. **Every action shows its reasons as a chain the handler can pull on.** This letter, because the case is at this step, because these facts hold (each with its sentence), asking for these documents (each because of a step or an article). Clicking any link shows it; changing any link changes everything after it, at once.
3. **Feedback is the handler finishing the work, nothing else.** They strike a document from the request, add one, change a fact, reword a paragraph, pick another action. Each of those is a precise statement about what CasePath got wrong, and the one-tap reason says which kind of wrong.
4. **A case has a next date.** After an action goes out, CasePath proposes when to look again and what for ("Unterlagen bis … erwartet"). Deadlines found in the file and deadlines the handler's own letter sets are the same list.
5. **When something arrives, CasePath is already there.** New files move the case to its next action without anyone asking; the handler opens it and sees what came, what changed, and the next piece of work prepared.
6. **The file note writes itself.** What was received, what was decided and why, what went out, what is awaited: one paragraph the handler can paste into the case system.

## What comes in, and what the handler hears

A case runs for weeks or months, and most of the work is reacting to what comes in: an e-mail of the customer, a letter of the other side, a fee note of the firm, a phone call. CasePath keeps the case where it lives:

- **«Aktualisieren»** (`core.update`, run kind «update»). Files added to a prepared case are shown under «Neu eingegangen» with their name and the day they came; the draft is greyed and not copied until they are read («trotzdem verwenden» unblocks it, logged). One primary button, with the time earlier updates took, starts a run that reads only them, building on the latest completed run (which must hold the running account; a run made before it needs one full preparation, said and offered). The reader gets the new documents in full and the case so far in one compact view (the account's entries one line each, the deciding facts with their values and status, the open requests); it records entries for the new documents only, numbered after the existing ones and linked to earlier entries, and changes a deciding fact or establishes one only with a quote from a new document (what came in takes its place among its kind's items by date; nothing the new documents do not speak to is touched). The document finder checks only whether the new files meet a need still missing or replace one present; the second reading and the source checker see only what changed; the result checker does not run (its summary, short assessment, open points and learning proposals stay those of the run built on). Code re-derives the account, the evaluation, the items and the next action from the merged result as for a full run. The update keeps its own tokens and seconds, and the run profile never mixes it with full runs. «Ganz neu vorbereiten» in «Mehr» stays for a full preparation. After an update, «Was sich geändert hat» lists what changed and the account's new entries.
- **The handler's own entries** («Notiz hinzufügen», and «Telefonnotiz erfassen» for the action A2). One compact card: kind (Telefon, Gespräch, Notiz, E-Mail ausserhalb der Akte), with whom (a name optional), the day (today), what was said, and, each behind one tap, one row of what was agreed (what, amount, who pays, by when), asked (what, of whom, by when) and the next step (what, by when, who). It is an entry of the account from Protekta to that party (a note: to no one), with «Fallbearbeitung» and the user as its source instead of a quote, marked in the Verlauf, and it can be changed or removed (each logged). It counts at once, without a model: «Stand», the dates, the follow-up and the next action are recomputed. An agreement entered by phone is the settlement the sequence then handles (the step «Einigung festhalten» is the handler's entry itself); a date the party asked gives («die Unterlagen folgen bis 15.12.») becomes the date of its open requests («zugesagt bis …») and the follow-up follows it. The file note names what the handler entered since it was last copied.
- **The Verlauf** is one table in time order: the report as row 1, then every document, every entry the handler made and every gesture (a decision, a document struck or added, a letter copied, a date set, the case closed), with undo where a change can still be undone. While a run works, «Der Fall» fills in as entries and facts arrive and the viewer beside it shows what is read.

## The screen, re-centred

```
┌ Übersicht ─────────────────────────────────────────────┬ Der Fall ─────────────────────┐
│ Frist wahren                                    ändern │ Anliegen   (two lines, more)  │
│ Weil: Ohne gültige Einsprache wird der Strafbefehl …   │ Fragen     «…»                │
│ Frist 16.11.2026 · Einsprache gegen den … · noch 1 Tag │ Parteien   Name · Rolle       │
│ [Deckung · 3 aus der Akte geklärt  (bestätigen)(ablehnen)] (only a decision that blocks)│
│ Brief an die Kundschaft ✓ | Vorlage an die Staatsanw.  │ Als Nächstes  open with whom, │
│ Guten Tag …                                            │               by when         │
│  ☑ Mietvertrag                                         │ Fristen    each once, by date │
│  + Weitere Vorschläge · 4   + Unterlage hinzufügen     │ Deckung    one line           │
│ (Brief kopieren)  Wiedervorlage 06.12.  [Erledigt ▾]   │ Rechtliches (not in letter)   │
└────────────────────────────────────────────────────────┴───────────────────────────────┘
```

- **The card head says four things, each once:** what this step is (the case list's «Als Nächstes» in the same words), why in one line («Weil: …», its source when opened), the one deadline that leads (the customer's or ours, open within 30 days, else the latest passed while the case has not gone past it; article, rule and source when opened), and the one open decision that blocks this step with its answers. Nothing else; what it states is not said again in «Der Fall». A payout shows its progress line instead of a decision. The server decides all of it once (`casepath/process/screen.py`), for every tab and the list.
- **What goes out is tabs** (the letter by whom it goes to, a template for the customer's own letter, the mandate package, the fee note's chosen answer), each ticked once copied; after a copy the next one not copied is shown.
- **The document list in the letter is the checklist.** A tick is a request; unticking or adding is a correction with its reason in one tap. A line shows no tag: its reason (why, how often practice asks, the article's passage, its source) opens from the line, by click or keyboard. Offered lines wait folded under «Weitere Vorschläge». The text around is the letter, editable on a click; a gap only the handler can fill is highlighted, and the card's one button is then «n Lücken füllen», which goes to the first.
- **The action bar has one primary button** (the open decision's answer, else the document to copy, else Erledigt), the follow-up date (for «Frist wahren»: what follows), and Erledigt with «mit Vorbehalt».
- **«Der Fall»** holds what the head does not: the request, the customer's questions, the parties by role, what is open with whom and by when (from the running account, only when it has something), the deadlines each once by date (a deadline depending on an open fact once, «nur bei …»; two ending the same day one row), the cover in one line once decided or settled by the stage, at most three legal points the letter does not state, «Aktennotiz kopieren» and «Notiz hinzufügen». No decision buttons.
- **The Prozess tab** shows the steps in order, the current one, and for each step passed the facts that decided it with their sources; at the current step what is still open and the stage's decisions (the cover check with its points, a handler's own decision, what a prescribed letter rests on), answered there as on the card.
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
