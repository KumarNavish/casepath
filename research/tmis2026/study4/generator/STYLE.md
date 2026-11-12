# Style sheet for the writing session

Every file is a message a claimant sends to the organisation that handles the claim (an e-mail or a web-form
message), plus the short documents attached to it. Follow this sheet for every file.

## The message

1. **Voice.** A lay claimant writing about their own situation, in the first person, as people write when they
   are worried or annoyed: concrete events, dates, names, amounts, what they want to happen. Not a lawyer, not a
   clerk, not a form.
2. **Length.** 150 to 400 words for the message body (attachments not counted). Vary the length across files.
3. **Language.** The language the bundle names. German means Swiss Standard German (write "ss", never "ß"; Swiss
   usage such as "Vermieterin", "Hauswart", "Lohn"). English means plain international English.
4. **Words.** No legal terms a lay person would not use. Never quote or name an article, paragraph, section or
   statute, and never use a term that appears in a question only because the question is precise (for example
   "designated by the canton", "registered partnership", "non-voluntary legal obligation") unless an ordinary
   person in this situation would say it. Say what happened, not what it is called in law.
5. **No mirroring.** No headings, bullet lists or paragraph breaks that follow the questions. One paragraph may
   carry several topics; one topic may be spread over two paragraphs. Never number the topics.
6. **Order.** Bring up the topics in the order the bundle lists under `topics_in_order` (it is shuffled per
   file). Greeting and closing are free.
7. **Absence.** No sentence says that something is not the case unless the bundle's designed answer for that
   question is "no". A question marked "not mentioned" is not touched at all: not denied, not hinted at, not
   answered by an attachment, not raised as a worry.
8. **Questions marked "no".** Say it in the claimant's words, once, plainly enough that a careful reader answers
   "no" without guessing ("He never wrote to me about it, I only told him on the phone" is a clear no to "Did the
   landlord learn of it in writing?").
9. **Questions marked "yes".** Make it clear; it may be plain ("I paid the October rent into the deposit account")
   or follow unmistakably from what is told ("the letter says the rent goes up because the mortgage rate rose").
   Do not rely on a hint a careful reader could read two ways.
10. **Open questions.** The claimant raises the matter and leaves it unsettled. Vary how (never the same phrase in
    two files):
    - not knowing: "I'm not sure whether the letter ever reached my wife separately." / "Ob die Hausverwaltung
      davon weiss, kann ich nicht sagen."
    - undecided: "I haven't decided yet whether to ask for more time in the flat." / "Ich überlege noch, ob ich
      Schadenersatz verlange."
    - disputed: "She says she sent it in March; I never got anything." / "Er behauptet, ich hätte das selbst
      verursacht, das stimmt so nicht, aber geklärt ist es nicht."
    - pending: "The caretaker said someone would find out; I've heard nothing since."
    What is **not** open: a plain yes or no said with hesitation ("I think I told him in writing, yes, the e-mail
    of 3 May" is a yes); a matter the claimant asks the reader to decide when the facts themselves are stated (the
    facts decide); silence (that is "not mentioned").
11. **Dates and amounts.** Use the story seed's names, places, dates and amounts; invent nothing that contradicts
    them. Where a question depends on a time span, the bundle gives dates on both sides of the span: use the one
    that makes the designed answer true. Dates must make every designed answer true and none of the
    "not mentioned" questions answerable.
12. **Attachments in the message.** The claimant may say that they attach a document the bundle lists. Never
    mention a document that is not attached, never promise one, never list what the organisation might need.
13. **No meta-text.** No word about questions, designs, tests, benchmarks or rules. No placeholders.
14. **A denied central event.** Where the bundle has `central_event_denied`, the question it names asks about the
    central event of the claim and its answer is "no": the claimant says that this event did not take place at all
    (nothing was stolen, no notice was given, the rent was never raised). The message and the attachments state none
    of the events asked about under `must_not_state`, neither as what happened instead nor as a correction nor as a
    possibility: never "not this, but that" ("it was not stolen at home, it was taken at the gym"; "I was not
    dismissed on the spot, I was given notice with the usual period"). What the claimant does write about (what they
    want, what worries them, what did happen) is free as long as it is none of those events.
15. **What a question does not cover.** Each question carries a `not_this` line naming the nearest thing it does not
    cover. Read it with the question: an answer must hold under the question's words as the `not_this` line limits
    them. Never give a "yes" through something the `not_this` line names, and never use such a thing to make a
    "not mentioned" question answerable or an "open" one settled.

## The attachments

1. Each attachment is a short synthetic document (60 to 200 words, plain text) written in the voice of its author:
   a contract excerpt, a letter, a receipt, a notice, a form, a record. Use the story seed's names, dates and
   amounts; give it a date and a sender where a real one would have them.
2. It shows every item listed under `must_show`, except the item named under `leave_out` (if any), which it
   leaves out entirely without remarking on the gap. Items under `show_only_if_it_applies` appear only where the
   story makes them apply and nothing under `must_not_show` forbids them; items under `does_not_apply_leave_out`
   do not appear. Where `checkable_as` describes an item, write literally what it says.
3. It contains nothing listed under `must_not_show`: in particular it never answers a question marked "not
   mentioned", never settles an open question, never contradicts a designed answer.
4. Language: the file's language, unless an English-speaking claimant in Switzerland would plausibly receive a
   German document (then German is allowed for that attachment).
