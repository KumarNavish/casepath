"""Write the blind-check payloads: for each claim only what a reader of the claim would see (channel, subject,
body, attachment texts) plus the list of facts and attachment content items to report on. No flag, fact state,
design value, sufficiency or reference is included. Claims are shuffled and split into four parts.
Output: build/blind_check/part_<n>.json, part_<n>.txt (the text pasted into each reader session after the
instructions READER and GLOSSARY.txt) and INSTRUCTIONS.md (= READER).

The files in build/blind_check/ are the record of what was read. Rerunning this script regenerates them from the
current data, which differs for the one claim corrected after the reading (see ../BLIND_CHECK.md); the re-read of
that claim is in reading_reread_*.json."""
from __future__ import annotations

import base64
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from spec import FACTS, FIELD_TEXT  # noqa: E402

READER = """You are a careful reader doing a reading-comprehension check. Do NOT use any tools, do not open files, do not search: answer only from the text in this message. Reply with one JSON object and nothing else.

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
Use the bare item_id (e.g. "recipient"), not the document kind."""


def generic(text: str) -> str:
    return text.split(" (")[0]


def main() -> None:
    out = HERE / "build" / "blind_check"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in sorted((HERE / "data" / "claims").glob("*.json")):
        claim = json.loads(p.read_text())
        ref = json.loads((HERE / "data" / "references" / p.name).read_text())
        msg = claim["customer_message"]
        atts = []
        for a, r in zip(claim["attachments"], ref["attachments"]):
            atts.append({"file_name": a["file_name"], "text": base64.b64decode(a["content_base64"]).decode(),
                         "content_items": {k: generic(t) for k, t in FIELD_TEXT[r["document_type"]].items()}})
        rows.append({"claim_id": claim["submission"]["claim_id"], "channel": claim["submission"]["channel"],
                     "subject": msg["subject"], "body": msg["body"], "attachments": atts,
                     "facts": {f: FACTS[f]["fact"] for f in ref["fact_states"]}})
    random.Random(7).shuffle(rows)
    for i in range(4):
        part = rows[i::4]
        (out / f"part_{i + 1}.json").write_text(json.dumps(part, ensure_ascii=False, indent=1) + "\n")
    (out / "INSTRUCTIONS.md").write_text(READER + "\n")
    for i in range(4):
        lines = []
        for r in rows[i::4]:
            lines.append(f"### CLAIM {r['claim_id']} (channel: {r['channel']})\nSubject: {r['subject']}\n{r['body']}")
            for a in r["attachments"]:
                lines.append(f"[ATTACHMENT {a['file_name']}]\n{a['text'].strip()}")
            lines.append("FACTS: " + ", ".join(r["facts"]))
            for a in r["attachments"]:
                kind = next(d for d, items in FIELD_TEXT.items() if set(items) == set(a["content_items"])
                            and all(generic(items[k]) == a["content_items"][k] for k in items))
                lines.append(f"ITEMS {a['file_name']}: " + ", ".join(f"{kind}/{k}" for k in a["content_items"]))
            lines.append("")
        (out / f"part_{i + 1}.txt").write_text("\n".join(lines))
    print(json.dumps({"claims": len(rows), "parts": [len(rows[i::4]) for i in range(4)]}))


if __name__ == "__main__":
    main()
