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
- **A cost keeps its identity** (`process/claims.py`). A cost the customer claims is its place in the brief with a current version, a state and its history. A later statement about it amends it (the earlier amount becomes history, and an earlier receipt no longer settles the corrected amount by its name), withdraws it (its question is «erledigt», its receipts are no longer owed, the letter that asked them keeps what it asked), is a further cost (another period or invoice number), or is an older statement uploaded later (history, by the day it was said, not the day it came). The reader names the relation and the cost it means; the decision is code's. Where nothing says which amount holds, the handler gets one decision beside the two passages («CHF 120 ersetzt CHF 85», «weitere Kosten», «bleibt bei CHF 85»), undoable, never a silent merge. A customer's own message naming an amount is never its receipt.
- **An arrival prepares what it enables** (`assessment.follow_on`, form `A5_nachtrag`, texts in the area's options file under `follow_on`). When the receipts an assessment asked for arrive and document the cost, the next letter is not the assessment again but a short «Nachtrag zur Einschätzung»: what came, what it documents, the rule of the question that waited, the next step with a prefilled template for the customer's own claim, and «gilt im Übrigen unverändert». Decisions already taken (cover, the adopted recommendation) are not asked again; the card names what the receipt settles and what it does not establish (the damage through the defect, no exculpation). A receipt covering part of a corrected amount prepares a letter that asks only the rest; several receipts of one cost that add up to it document it together. The follow-on's texts are review elements («nachtrag.…»), not yet reviewed by a jurist.
- **The handler's own entries** («Notiz hinzufügen», and «Telefonnotiz erfassen» for the action A2). One compact card: kind (Telefon, Gespräch, Notiz, E-Mail ausserhalb der Akte), with whom (a name optional), the day (today), what was said, and, each behind one tap, one row of what was agreed (what, amount, who pays, by when), asked (what, of whom, by when) and the next step (what, by when, who). It is an entry of the account from Protekta to that party (a note: to no one), with «Fallbearbeitung» and the user as its source instead of a quote, marked in the Verlauf, and it can be changed or removed (each logged). It counts at once, without a model: «Stand», the dates, the follow-up and the next action are recomputed. An agreement entered by phone is the settlement the sequence then handles (the step «Einigung festhalten» is the handler's entry itself); a date the party asked gives («die Unterlagen folgen bis 15.12.») becomes the date of its open requests («zugesagt bis …») and the follow-up follows it. The file note names what the handler entered since it was last copied.
- **A judgment is one question, and its answer writes the letter** (`process/live.py`, data in `process/areas/live/formulare.json`, live cases only). An offer of the other side is the customer's to accept: while nothing was said with the customer since it came, the step is «Kundschaft zum Angebot befragen» (a call, noted), not the answer. After the note the offer still waits (talking to the customer does not answer the other side) and the card asks one question, «Angebot der Gegenpartei: wie antworten?», with what follows each answer beside it: annehmen, ablehnen, Gegenangebot. One click (`POST /api/cases/{id}/offer/stance`, «offer.stance», attributed, per offer, the same click again takes it back) prepares the letter to the other side like any other; what a counter-offer offers is a gap the handler fills. A matter the file shows as done has its short closing letter, and «Erledigt» without a letter stays possible. These letters are review elements («backbone:live.<form>.<part>») and are not reviewed. Not built: an accepted offer does not yet enter the agreement by itself; the handler enters it («Notiz hinzufügen», «vereinbart») and the settlement sequence follows.
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
│ (Freigeben und kopieren)  Wiedervorlage 06.12.         │ Rechtliches (not in letter)   │
└────────────────────────────────────────────────────────┴───────────────────────────────┘
```

- **The card head says four things, each once:** what this step is (the case list's «Als Nächstes» in the same words), why in one line («Weil: …», its source when opened), the one deadline that leads (the customer's or ours, open within 30 days, else the latest passed while the case has not gone past it; article, rule and source when opened), and the one open decision that blocks this step with its answers. Nothing else; what it states is not said again in «Der Fall». A payout shows its progress line instead of a decision. The server decides all of it once (`casepath/process/screen.py`), for every tab and the list.
- **What goes out is tabs** (the letter by whom it goes to, a template for the customer's own letter, the mandate package, the fee note's chosen answer), each ticked once copied; after a copy the next one not copied is shown.
- **The document list in the letter is the checklist.** A tick is a request; unticking or adding takes effect at once and asks no reason (what it should mean beyond this letter is an optional follow-up beside the line). A line shows no tag: its reason (why, how often practice asks, the article's passage, its source) opens from the line, by click or keyboard. Offered lines wait folded under «Weitere Vorschläge». The text around is the letter, editable on a click; a gap only the handler can fill is highlighted, and the card's one button is then «n Lücken füllen», which goes to the first.
- **The action bar has one primary button** (the open decision's answer, else the document to copy, else Erledigt), the follow-up date (for «Frist wahren»: what follows), and Erledigt with «mit Vorbehalt».
- **«Der Fall»** holds what the head does not: the request, the customer's questions, the parties by role, what is open with whom and by when (from the running account, only when it has something), the deadlines each once by date (a deadline depending on an open fact once, «nur bei …»; two ending the same day one row), the cover in one line once decided or settled by the stage, at most three legal points the letter does not state, «Aktennotiz kopieren» and «Notiz hinzufügen». No decision buttons.
- **The Prozess tab** shows the steps in order, the current one, and for each step passed the facts that decided it with their sources; at the current step what is still open and the stage's decisions (the cover check with its points, a handler's own decision, what a prescribed letter rests on), answered there as on the card.
- During a run this same screen fills in, as section U of the handler bar describes.

## Supervising the prepared work (17 November 2026)

A fresh-eyes audit of the running product (twelve journeys clicked through on synthetic cases) and a baseline measured before any change set this list. Each point is what the audit saw, then what is built.

- **Working through, not hunting.** Before: every case was opened from the list and left for the list again (5 clicks and 2 pages per letter that only needed approval). Now «Fälle durchgehen» on the start page opens the first case that needs the reader; a settled case (its letter went out, or it waits for its date) carries «Nächster Fall» as its one primary button, and the header carries it for a case left untouched. The walk follows the list's order and what the list is narrowed to, offers no case twice, and ends at the list with one line. Measured on the same five cases: 3 clicks and 1 page per letter.
- **«Freigeben und kopieren» is one gesture.** The approval puts the approved text on the clipboard (the measured copy is recorded as before); where the browser refuses, «Brief kopieren» stays the next step. «Versandt am» then confirms the dispatch.
- **The page scrolls as one document.** Before, the card had the window's height and the letter scrolled inside it: on the assessment after a reply a letter 1,554 px tall stood in a 383 px box, and through a slot of about 116 px once the cover check was open. Now the letter and every opened detail stand at full height, the card's action bar stays at the bottom of the window, and «Der Fall» stays beside it.
- **The decisions of a step are one set** (`completion.decided`, with `open_decisions`). The card says how many are open and lists them all: those taken with their answer and «ändern» (the decision's own edit undone, or the adoption taken back: `DELETE /api/cases/{id}/recommendation`), the one asked now, those still to come. Confirming the cover names what it includes («bestätigt auch die n Punkte, die nur die Police klärt») and keeps that with the decision.
- **The reader's own changes stand above the letter they change.** The change just made with what it moved (step, letter, documents: before and after) and its undo, and under it every earlier change still in force since CasePath last prepared the case and since the last letter went out, each taken back there. The list is read from the case's own log, so it is the same after a reload and can never differ from the Verlauf.
- **One more document is one action.** Typed and entered, it is requested at once. «in solchen Fällen immer» beside it proposes it for similar cases afterwards (`POST /api/edits/{id}/general`: proposed once, released under «Wissen» after its replay, changing no case by itself). A line unticked is left out of this letter; «in diesem Fall nicht» and «in solchen Fällen nie» are the two optional answers that take it out of what the case needs.
- **A letter changed after its approval is approved again before it is marked as sent.** «Versandt am» is not offered on a stale approval; that the earlier version already went out is said on purpose («die freigegebene Fassung ging schon hinaus»), and the check that follows («Abgleich erledigt») stands on the resting card, not only in the head of an open step.
- **The call about an offer is prepared** (`live.call_sheet`, data in `areas/live/formulare.json`). Under the head, which already states the offer, its amount and its deadline with the source, the card lists three questions for the call; the note is written in the card and filed with the customer (it was preset to the other side, which let the case wait past the offer's own deadline). After the note the card asks the one question as before.
- **«was hinausging» is read in place** (`GET /api/cases/{id}/actions/{version}/letter`): the sent letter and what was enclosed, read back from the stored package, with who approved it when and to which address; the package itself is one link beside it.
- **«Heute» narrows the list.** A count is a filter (the cases behind it and nothing else; pressed again, all). The status beside «Als Nächstes» says only what that column does not («überfällig», not the step's name again). Enter on a single search hit opens it.
- **The jurists' state is not said in the handler's word.** «freigegeben» is the handler's approval; the area's state reads «juristisch noch nicht geprüft», and the count of reviewed elements is shown to reviewers only. A letter that is no assessment (a reminder, a status inquiry) lists no answers or recommendations as what it rests on (`completion.relied_elements`).
- Not built from the audit, said plainly: the Prozess tab and the three-column layout stay; a free-text edit of the letter is saved per part but still has no marker and no «Original wiederherstellen»; a jurist still cannot change wording in the product; the Auswertung still shows no time figure; recipient, subject and letter are still three copies (a mail link was left out on purpose: no dependence on a mail program).

## How it looks and moves (17 November 2026)

The rules the screens are held to, so a later change does not undo them:

- **White ground, one typeface, one accent.** The page is white; what is read or acted on is a card with a hairline and a soft shadow, never a box inside a box. Inter in few sizes: large tight headings, small tracked labels. Crimson is the one primary button, the step asked now, and what is late or newly arrived; a quiet fill is the pale tint. No gradients, no decorative colour.
- **One control, one fill.** The tabs, the list's filter, the letters of a step and the language are each one rounded control with the current choice filled; when the choice changes the fill slides to it.
- **Read in order, top to bottom.** On a case: what CasePath did and when (one small line), the step, why (one line), what the news means (one sentence; «was sich geändert hat» opens from it), the decisions as one numbered list, the letter, the action bar as a dock at the foot of the window.
- **Secondary things wait folded.** «Der Fall» is a stacked list; a section longer than a line or two folds to its name, how many entries it has and how it begins. A file's documents wait folded under the file (open on the Akte tab). Deadlines never fold.
- **States are words, not capsules.** A status, a source, an answer's state is said in type; only what needs a hand is a button.
- **Movement marks a moment and nothing else.** Each plays once, when its moment happens, never on a mere re-render, and none with «reduce motion»:
  - a case arrives (from the right when the reader went on to it); a tab or a page arrives with its blocks and then its rows in the order they are read;
  - on «Prozess» the path is walked step after step, a step done has its tick drawn, the step now breathes; on «Akte» what the findings rest on lights up, and a source opened at its passage answers with a pulse;
  - a decision taken is ticked, the action bar answers a change of state, the list's rows come in again when the filter changes and a row under the hand shows its way in.
- **CasePath at work.** Three cards on a dotted ground joined by moving lines: its steps ticked as they finish, what it reads now (with the reader's own stop), what it found so far (counts that bump when one is added, and the latest finding).
- **What CasePath completed.** When it finishes while the reader watches, every step is ticked, it says so for a moment, and the prepared step arrives with the trail of its work ticked in turn: files and pages read, facts found, entries in the history, documents on file of those needed, the letter written, the decisions left for the reader. Each leads to where it can be checked (Akte, Verlauf, Unterlagen). Later the trail is one press on the line «CasePath · vorbereitet …» away. From another case, a quiet notice at the lower right and the count in the tab's title.
- **The day.** A greeting, the day in one sentence, how far the reader's own day has come (`GET /api/today` → `done`), the next five working days with what falls due on each (a day pressed narrows the list), «Fälle durchgehen», and one bar: the filter at the left («Alle · Zu entscheiden · Fällig · Versandbereit · Wartet»), the search at the right. A filter, a day or a typed search narrows the cases already there at once; the search folds case and accents and finds what a row shows (reference with or without dots, names, next step, due date, status). Each case is a row of its own, and a case opened is read from its top.
- **Hands on the keyboard.** On the list: arrow keys or j/k move through the rows, Enter opens. On a case: Ctrl+Enter (⌘+Enter) presses the card's one primary button.
- **«Auswertung»** leads with four figures and lists only the cases something was done in.

## The case as a picture (17 November 2026)

The work is shown as a picture that builds itself, drawn from the case's own state and never from a recording. One engine (`web/ui/assets/story.js`, `story.css`; no library) draws every one of them: cards in lanes, lines between them, a camera that goes to what a moment is about, one sentence saying what happened and one saying on what it rests, and a line under the picture with one mark per moment (press or drag to see the case as it stood then; Space, ←/→, Home/End on the keyboard). A card opens the real thing: the file at its page, the row in the table below, the tab. With «reduce motion» each moment is simply shown.

- **While CasePath works** (Übersicht): the run's events as they arrive. A file comes in, a finding rises from it joined to its passage, a document is found or marked missing, the case is placed on its process. The picture stands in a layer of its own, so the page's redraws never cut a movement, and a run that is ahead is caught up with, never skipped.
- **How a step was prepared** («Ansehen, wie es entstand» on the prepared step): the same picture replayed from the finished run's events, on to what practice taught, the letter and the decisions left.
- **Prozess**: the way the case came with the facts that took it from step to step, where it stands, what is open there, and the branches from here with what decides them.
- **Verlauf**: who wrote to whom, a column per party, in the order it happened; a request is joined to its answer and what is open stays marked. The line under it is the case's time.
- **Unterlagen**: what the case needs and why (what closed cases asked for, what the law asks), what the files hold of it with the page, what is missing.
- **Akte**: the documents the file holds in the order of their dates and what was taken from each, joined by the page; what stands without a passage of its own is said last. A card opens its page in the reader below.
- **Wissen**: where each rule came from (a case, a case worker's change, the first request letters of practice) and the cases it was applied in since, one moment per case in the order it happened; a rule's card opens from its node.
- **The list's rows** carry a quiet track (how far the case is along its process: the steps that lead on, then its closing, the step it is at marked) and a peek for the hand that rests on a row or the keyboard that stands on it: the step by name, the one reason for what comes next, the whole status. The row carries both; nothing is asked again.
- **The keyboard** («?» in the bar says it): J/K and Enter in the list, «/» to search; in a case 1 to 5 for its tabs, Ctrl+Enter for the step's main action, N for the next case, L for the list; V for a picture large and back. Keys do nothing while a field is being written in.
- **The list**: a case whose status changed since the list was last on this screen says what it was before, once, on its row.
- **Auswertung**: the operation in the measures claims handling knows (docs/SWISS_PRACTICE.md, part C); the open cases by age are one bar that grows to its shares.
- **Read at a glance, large on demand.** A finished picture rests at a size that can be read, on where the case stands now, with as much of the rest as its frame holds; «Ganzes Bild» shows all of it and «Gross ansehen» (or V) puts it over the page with room, Esc brings it back. A long way of the camera is travelled with a step back, so the reader sees where it goes.
- **Picture and list are one thing seen twice.** A row under the hand brings its card forward with its lines and what they lead to (the camera goes to it if it is out of the frame); a card under the hand marks its row; a card pressed opens its row or its page. Lines that would be a bundle saying one thing (what practice asked for, in Unterlagen and Wissen) are drawn while their moment plays and for the card under the hand.
- **Never a crowd**: a picture holds what a reader can take in (Wissen the eight rules that moved last and the ten cases they reached; Unterlagen twelve documents; Akte ten documents with three facts each) and says what it leaves to the list below; one that would hold more than 44 cards is not shown.
- **A tab's picture** stands as far as the case had come and plays only what is current; when the case changes under the reader's eyes (an entry added, a document arrived) the new part arrives as its own movement. It can be put away with its ✕ and stays away in that browser until «Als Bild zeigen».
- **List and case**: a case opened from the list grows out of its row (its name travels) and goes back into it.

Rules for a later change: the picture's model is built in `casepath.js` from data the page already holds (`storyModel` from run events; `processStory`, `historyStory`, `documentsStory` from the case), every text goes in as text, nothing in it is staged, and a movement that says nothing is left out.

## One calm system for every screen (18 November 2026)

Every screen is drawn from one small system, taken from the best current product design for work of this kind and held
to it strictly, because calm comes from sameness: the reader learns one look and then only reads content.

- **Layout.** A light sidebar at the left holds the product's name, who works, and the ways through the product
  (Fälle; for reviewers Wissen and Auswertung). In a case the same column continues with the case (its name, parties
  and state in one card), its parts (Der Fall, Belege, CasePath) and its files. The page beside it is white. Its top
  bar holds only that page's own views as one segmented control, and its tools at the right.
- **Colour.** Ink `#101215`, quiet text `#6e7174`, hairline `#e2e4e5`, pale tray `#f3f4f4`, white. Three signals and no
  others: blue `#2f6fed` for what is current and what leads on (where the case stands, the way it took, focus), green
  for what is done, red `#c62445` for what needs a hand (missing, overdue, to decide). The main button is ink, never a
  colour.
- **Shapes.** A card is white with a hairline ring (half a pixel of ink at an eighth strength and a one-pixel soft
  shadow), radius 12 to 14; nothing has a heavy border or a tinted fill. A choice among few is one pale tray with the
  chosen part in white. A button is a pill, 36 px high (30 px small). A list inside a card sits in the pale tray.
- **Type.** Inter; titles at weight 510 with tight spacing (−0.022 em); text 14.5 px; small labels 11.5 to 13 px in the
  quiet grey; figures tabular.
- **Motion.** 150 ms on colour for anything under the hand; 300 to 400 ms with an ease-out for what arrives; rows in
  the order they are read; the pictures move only to show a change of the case.

The values live once, as tokens at the head of the last block of `web/ui/assets/casepath.css`; the pictures
(`story.css`, `flow.css`) read the same tokens. A colour written anywhere else is a defect; a test holds that.

A file held over a case shows where it belongs before it is let go: on «Unterlagen» the rows of the documents still
missing turn blue and say «hier ablegen», and the sidebar's «Unterlagen» lights up on every tab. Dropped anywhere on
the page the file is added as before; the hint only says what the case is waiting for.

Under a prepared letter one quiet row says what it rests on: the person it is written to, the claim number, the day
it asks an answer by, each fact of the file whose words stand in it (with its page) and each document it asks for
(with «Praxis» where closed cases taught the request). A chip under the hand marks its words in the letter, using the
browser's own highlight so the editable text is never touched; pressed, it opens the passage or «Unterlagen». Only
what literally stands in the letter is shown; nothing is inferred.

On «Verlauf» the case's time is one band above the table: every dated entry at its day (customer above the line,
Protekta on it, everyone else below), what is open ringed in red, today marked. A silence of more than forty days is
drawn short and says how long it really was («7,4 Jahre», «3 Monate»), so an old contract does not press the exchange
into a corner, and the band says how long nothing has happened since the last entry. A dot under the hand names its
entry and marks its row; pressed, the page goes to the row.

On the case list a day of the week strip shows its cases before anything is pressed: under the hand, the rows due that
day stay and the others step back; pressing the tile filters as before.

### Prozess as a flow

The process of a case is a flow on a dotted ground (`web/ui/assets/flow.js`, `flow.css`): each step is a block with
its name in a coloured band (green done, blue where the case stands, grey ahead) and, inside, its rows: what CasePath
prepares there, the decision that is the handler's (offered on the block as two small buttons while it is open, shown
as its value once taken), what is still open, the documents missing, and each way out by its own name with what
decides it. A way leads by a right-angled line into the next block, or ends in a small pill for a closing. The way the
case took is drawn in blue; ways still open are grey. The picture is the case's real state: a decision taken on a
block is taken by the page's own control (one rule for both), and the same picture takes the change up without being
drawn again. It can be seen large (`v`), panned, and reset to «Wo der Fall steht» or «Ganzer Prozess». Seen from
far («Ganzer Prozess») each block says only its name, at a readable size, and a closing is a small flag; the rows come
back with the closer look. In the page the picture takes the height the window gives (440 to 640 px).

## The case in parts, under the hand (18 November 2026)

The rail of a prepared case names what CasePath established, once, in three short groups: «Der Fall» (Anliegen,
Parteien, Deckung, Fristen, Rechtliches), «Belege» (Angaben, Unterlagen, Verlauf) and «CasePath» (Prozess,
Vorbereitung, Wissen). Beside a name stands the one thing worth knowing before looking (a count, or in crimson what
needs a hand: «zu entscheiden», «1 fehlt», «2 offen»). A part with nothing to show is not named.

Resting the hand on a name shows that part on a stage at the right, as it stands now: the cover points with what the
file settled and what the policy must confirm, the facts with their page, the documents with what is missing first, the
last entries of the correspondence with the open request marked, the process with the ways on from where the case
stands, what CasePath did to get here, and the rules from closed cases applied to this one. Rows arrive in the order
they are read and what is settled is ticked as it arrives. On the Übersicht the stage takes the place of «Der Fall» and
gives it back when the hand leaves; on the other tabs it stands at the right over the page. Pressing a name keeps the
stage; Escape, the cross or another case puts it away. A row with a passage opens the passage in the Akte; «öffnen»
leads to the tab the part belongs to.

The stage reads; it decides nothing. A decision is taken where it always was (on the step, or under «Prozess»), so a
glance can never change a case. It is built in the page from what the page already holds: no request is made, nothing
is stored, and it is not shown while CasePath works, in the study, or before a case is prepared.

## Reading in another language (17 November 2026)

Cases are worked in German. A reader of English switches the page with the control at the right of the header (DE | EN): the page turns in place, where it stands, and the choice is kept in the browser.

- **Everything CasePath says and writes is translated**: the product's own wording, the legal areas' catalogues (documents, questions, steps, passages of law), the summary, facts, questions, decisions, history and status of a case, its letters and the pages of its files.
- **Nothing in a case changes for that** (`casepath/web/translate.py`). The API answers as always; for a reader of another language (header `x-casepath-lang`) each answer carries, under `_tr`, the translation of every text in it. The page shows the translation where it shows the text (`esc()`), and keeps the original for everything it stores, sends or puts into a field (`raw()`): a value is saved as entered, an id is an id.
- **What the page puts together itself is asked for too.** A name the page shortens or composes (a fact's short name in a picture, a line joined from parts) is in no answer of the API, so the page asks for it once (`POST /api/translate`); the memory answers at once and costs nothing, the model is asked only where the deployment lets it translate.
- **A letter goes out as written.** In English it is shown translated to read, with the line «Translated to read · it goes out in German, as written»; «show and edit the original» turns it into the German letter, which is the only one that is edited, approved, copied and sent. The ticks of its lines work in both views.
- **A file is read line by line in English**, a line a finding cites marked as a whole; «Original» shows the file as written, with the cited words marked exactly.
- **Where a translation comes from**, in this order: the memory shipped with the product (`casepath/web/i18n/en.json`: its wording, the catalogues and the examples; numbers and dates are slots, so one entry serves every count and every day; a text put together from parts is translated part by part); what this deployment's model translated before (the store's table `translations`, deleted with its case); and, where the deployment allows it (`CASEPATH_TRANSLATE=model`, within `CASEPATH_TRANSLATE_TOKENS` a day, default 300,000), the model, in the background, a batch at a time. The page asks again and the text changes when it is there; a file's pages are only translated when a reader opens that file. With `memory` (the default) nothing is sent to a model and a text the memory does not know stays as written; `off` offers no translation.
- **Keeping the memory.** `GET /api/translate/missing` (reviewers) lists the texts readers were shown untranslated; with `casepath.trmiss` set in the browser, `window.casepathMissing()` lists what a page showed untranslated. Both are how the shipped memory was filled from the examples.
- Not built: other languages than English; translating a file written in another language into German.

## What each handler gesture teaches

| The handler | CasePath learns | Improves |
|---|---|---|
| unticks a document, «in diesem Fall nicht» | the need's condition is too wide | the process's document requirements (precision) |
| unticks, «in solchen Fällen nie» | the need should not be asked at this step at all | Knowledge, after replay |
| adds a document, then «in solchen Fällen immer» | a need is missing at this step | Knowledge, after replay (completeness) |
| adds a document and says nothing more | nothing beyond this case | the honesty of the numbers |
| changes a fact, "steht anders in den Akten" | a reading error, with the sentence | the reader |
| picks another action or step | the path was wrong: which fact or condition sent it there | the process (workflow accuracy) |
| rewords the letter | the form or tone is not Protekta's | the letter forms |
| changes the proposed date | the waiting time for this action | follow-up rules |
| closes "mit Vorbehalt" | the case needs a second look | where CasePath is least trusted |

What is built of this table, and how a change lands:

- **One strike.** Unticking a document in the letter and answering «in diesem Fall nicht» or «in solchen Fällen nie» takes it out of what the case needs (`remove_document`, undoable), not only out of this letter. Unticking alone keeps the need and leaves the line out of this letter.
- **«In solchen Fällen immer» and «nie» propose, or say why not.** An added document, question or step, and a struck document, become a candidate under «Wissen» with the replay of its effect; a struck document is a note for whoever keeps the process (it changes no case by itself). Where a correction cannot be said in general (a fact of this case) the answer says «Gilt in diesem Fall …» in place of the silent drop.
- **The repeat detector compares the thing, not the step** (`store.similar_edits`): an added document is the same by its name, a struck one by its id, a fact by fact and value. The same correction in two other cases makes the third a proposal («wiederholt»); three different documents on one step no longer do.
- **A strike counts against the rule that asked** (`knowledge.struck`): once per case, in the item's history; two such cases outweighing its confirmations mark it for review.
- **A rule change lands visibly** (`app.landed`). Releasing or withdrawing an item writes a line into the log of every open case whose requirements it changes («Regel freigegeben: … · neu verlangt: …», by «Wissen · who»); study copies and closed cases are not touched. An approved, unsent letter of such a case is stale («Regel geändert») by its own record: the approval keeps the Knowledge versions and the requirements it was given on (`completion.stand`).
- **«Stand bei Freigabe»** (`completion.stand`, `stand_record`). The approval's event keeps, without case content, the process version, the Knowledge items with their versions and a hash each of the requirements and the established facts. The Versandpaket keeps the same in words, as the page `Stand bei Freigabe.txt` and as `manifest.stand`: each document and question the letter asks with where the need comes from (process, Knowledge, handler) and its legal basis, each fact with its value and its source (file and page, the handler, or computed by the process's rule), and which parts of the letter are the form's wording and which the handler's own. A third person can say from the package alone why the letter went out as it did.
- **Recall** (`GET /api/recall`, reviewers; in «Wissen» under each item «Briefe, die darauf beruhen»). Every approved letter, in any case, whose case carried a Knowledge item (any version or one), that rests on a reviewed element, or that was approved on a version of the process: the case, the letter, who approved it when, and whether it went out.
- **Review in the letter** (`GET /api/cases/{id}/letter-review`, page `#/knowledge/brief/<case>`). Beside the area's state the case says «Dieser Brief: n von m Bausteinen geprüft»: the reviewed elements this letter rests on (`completion.relied_elements`), counted as they are marked now. One click shows the letter as prepared and, below it, exactly those elements with their wording and passages; a jurist marks them there with the same three marks as everywhere, and a mark holds wherever the element is used, so the next letter of the area starts checked. A need a Knowledge item added is practice, released under «Wissen», and is not counted. The release unit is the letter, not the area's whole catalogue.
- **Release by use** (`GET /api/review/by-use`, reviewers; in «Wissen» under the areas as «Zuerst prüfen»). The elements approved letters rest on, the unchecked first, by how many letters carry them, each opened in the latest such letter. Before any letter is approved the list says so and the way in is the case's own line.
- Not built: rewording a proposal or giving it a condition in «Wissen»; learning from a reworded letter, another action picked or a changed date; a jurist's proposed wording still reaches the letters only through a build.

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
