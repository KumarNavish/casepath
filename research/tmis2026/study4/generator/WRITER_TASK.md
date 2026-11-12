# Writing session: fixed instruction

You write synthetic claim files for a research benchmark. Each file is a message from a lay claimant plus short
attached documents, written from a bundle that says exactly what the file must and must not say.

## What you may read

- this instruction;
- the bundles you are given (`writer_bundles/<file_id>.json`), each with the style sheet inside it (`style_sheet`);
- in a rewrite round, the rewrite request for the file (`rewrite/<file_id>.json`) and your own earlier output for
  that file.

Nothing else: no other file of the repository, no rule text, no program, no other session's output. Do not look
anything up. Do not call any other model or service.

## What you do, per bundle

1. Read `questions`. Each has a `designed_answer` (yes, no, open, not mentioned) and an `instruction`. The file
   (message and attachments together) must give every question exactly its designed answer to a careful reader
   who sees only the file and the questions. A `note` on a question is binding. A `time_span` gives dates on both
   sides of a span: follow its `use`.
2. Write the message in `language`, `length_words` long, following `style_sheet`, bringing up the topics in
   `topics_in_order` (labels refer to `questions` and `attachments`; a question marked "not mentioned" is not a
   topic and is never touched).
3. Use the `story`: names (claimant, the other party as a person and as an organisation, a third person), place,
   street, dates (`date_written` is the date of the message, `date_main_event` the date of the central event,
   `earlier_dates` for anything before), amounts in CHF. Where `claimant_sex` is given, the claimant is a woman
   ("female") or a man ("male"); write accordingly. Assign roles as the questions require (the other party is
   whoever the claimant is in dispute with or claims from); invent no further named person or organisation.
4. Write each attachment in `attachments`: show every `must_show` item, leave out `leave_out` entirely (if it is
   not null), show `show_only_if_it_applies` items only where the story makes them apply and nothing in
   `must_not_show` forbids them, leave out every item under `does_not_apply_leave_out`, and include nothing in
   `must_not_show`. Where `checkable_as` describes an item, the document must contain literally what it says for
   the item to count as shown (and, for the `leave_out` item, must not contain it).
5. Check before you finish: word count within range; every question gets its designed answer and nothing more;
   no sentence states that something is not the case unless the designed answer is "no"; no legal term or article
   number in the message; no label (Q1, A1) and no word about questions, designs or rules in the text.

## Output, per file

One UTF-8 JSON file, `written/<file_id>.json` (first round) or `written/<file_id>.r2.json` (rewrite round):

```
{"file_id": "<file_id>",
 "round": 1,
 "language": "de" | "en",
 "text": "<the message, plain text, paragraphs separated by a blank line>",
 "attachments": [{"label": "A1", "text": "<the attachment, plain text>"}]}
```

Every label of the bundle's `attachments` appears exactly once; no other attachment. Write the JSON with the text
as a JSON string (newlines as `\n`).

## Rewrite round

A rewrite request (`rewrite/<file_id>.json`) lists the questions and attachments on which a blind reader's reading
differed from the design (`designed` and `read_as`) and carries the file's `bundle` as it now stands: work from
that bundle, not from the round-1 one. Where `answers_changed` lists a question, another answer or an attachment
of the file already answers it, so the bundle's designed answer for it has changed from "not mentioned" to the
answer named; give it that answer. Rewrite the whole file once so that every question and attachment gets its
designed answer, keeping everything else as it was where possible, and write `written/<file_id>.r2.json` with
`"round": 2`. Only one rewrite is made; a file that still differs is dropped.
