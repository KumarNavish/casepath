You are a careful reader doing a reading-comprehension check. Do NOT use any tools, do not open files, do not search: answer only from the text in this message. Reply with one JSON object and nothing else.

TASK
You read incoming tenancy claims (a message and possibly attachments) received by a Swiss legal-expenses insurer. You know nothing else about the cases. For each claim and each listed fact, report exactly one status:
- stated_true: the message or an attachment states, or clearly implies, that the fact is so;
- stated_false: it states, or clearly implies, that the fact is not so;
- open: the fact is raised but explicitly left uncertain or undecided;
- not_mentioned: the fact is not addressed at all.
For termination and rent-increase claims: if no termination or increase has formally been issued, judge the other facts with respect to the termination or increase that the landlord has announced or intends.
Quote the decisive words (at most 15 words, copied exactly; empty if not mentioned). For each attachment and each listed content item, report whether the attachment explicitly shows that item (true/false). Judge only what the text says; read as a careful claims handler would.
Output format (one JSON object, all claims below):
{"<claim_id>": {"facts": {"<fact_id>": {"status": "...", "quote": "..."}}, "attachments": {"<file_name>": {"<item_id>": true|false}}}}
Use the bare item_id (e.g. "recipient"), not the document kind.
