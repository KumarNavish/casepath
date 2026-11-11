# Built around the handler's work

## The idea in one line

A handler does not want facts, a graph or a checklist. A handler wants the **next piece of work, already done**: the letter written, the decision reasoned, the follow-up dated. CasePath's job is to hand them that, show why, and learn from what they change before it goes out.

## How a handler's work actually runs

A case is not one task. It is a chain of **actions**, each triggered by something arriving in the file and each ending in something leaving it:

| Something arrives | The handler decides | Something leaves |
|---|---|---|
| the claim | is it ours, is it covered, what is missing | acknowledgement and request for documents |
| the documents | what is the legal position, what can the customer claim | assessment to the customer; advice or a draft for them to send |
| the other side's answer, or silence | escalate, wait, or close | letter to the other side, a deadline set, conciliation request, mandate to a lawyer |
| a deadline approaching | act before it lapses | a reminder, a filing, a note |
| the matter settled | nothing further | closing letter and file note |

Between actions the case waits. A handler holds dozens of waiting cases; what they fear is the one where a deadline passed or a document was never asked for.

**These rows are a hypothesis.** The eleven Hackathon dossiers are closed files and contain everything Protekta actually did, in order. The real chain is read from them (section "What we take from the dossiers") and replaces this table.

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
