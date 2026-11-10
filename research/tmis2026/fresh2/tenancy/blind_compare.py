"""Compare the blind readings (build/blind_check/reading_part_*.json) with the design of each claim. No model calls.

The reader saw only the message, the attachments and the list of facts and content items (build/blind_check/
part_*.txt, GLOSSARY.txt). Here each reading is compared with the fact state of the design:

  design state       strict expectation   also accepted (reference unchanged under the silence policy)
  stated_true        stated_true          -
  stated_false       stated_false         not_mentioned, for a branch fact only (absent = presumed false)
  absent             not_mentioned        stated_false (false either way)
  open               open                 -
  unmentioned        not_mentioned        stated_true (routing fact presumed true either way)

and each attachment content item with "shown" (every item except the omitted one). Quotes are checked to occur in
the claim text (whitespace-normalised). Output: build/blind_check/comparison.json and a summary on stdout.
"""
from __future__ import annotations

import base64
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
BC = HERE / "build" / "blind_check"
sys.path.insert(0, str(HERE))
from spec import ROUTING  # noqa: E402

STRICT = {"stated_true": "stated_true", "stated_false": "stated_false", "absent": "not_mentioned", "open": "open",
          "unmentioned": "not_mentioned"}


def accepted(state: str, got: str, routing: bool) -> bool:
    if got == STRICT[state]:
        return True
    if state == "absent" and got == "stated_false":
        return True
    if state == "unmentioned" and got == "stated_true":
        return True
    if state == "stated_false" and got == "not_mentioned" and not routing:
        return True
    return False


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().strip(".").lower()


def main(final: bool = True) -> dict:
    """final=False: the first reading of every claim as authored at the time; final=True: with the re-reading of
    claims corrected after the first reading (reading_reread_*.json), against the data as sealed."""
    readings = {}
    for p in sorted(BC.glob("reading_part_*.json")):
        readings.update(json.loads(p.read_text()))
    if final:
        for p in sorted(BC.glob("reading_reread_*.json")):
            readings.update(json.loads(p.read_text()))
    rows, fields, claims = [], [], {}
    for p in sorted((HERE / "build" / "scenarios").glob("*.json")):
        sc = json.loads(p.read_text())
        cid = sc["claim_id"]
        claim = json.loads((HERE / "data" / "claims" / f"{cid}.json").read_text())
        text = claim["customer_message"]["subject"] + "\n" + claim["customer_message"]["body"] + "\n" + "\n".join(
            base64.b64decode(a["content_base64"]).decode() for a in claim["attachments"])
        r = readings[cid]
        routing = ROUTING.get(sc["family"])
        crow = {"facts": {}, "fields": []}
        for f, st in sc["fact_states"].items():
            got = r["facts"][f]["status"]
            q = r["facts"][f]["quote"]
            row = {"claim_id": cid, "fact": f, "state": st, "expression": sc["styles"].get(f), "got": got,
                   "strict": got == STRICT[st], "accepted": accepted(st, got, f == routing),
                   "quote_found": (not q) or norm(q) in norm(text), "routing": f == routing}
            rows.append(row)
            crow["facts"][f] = {k: row[k] for k in ("state", "expression", "got", "strict", "accepted", "quote_found")}
        names = {a["artifact_id"]: a["file_name"] for a in claim["attachments"]}
        for a in sc["attachments"]:
            shown = r["attachments"][names[a["artifact_id"]]]
            for k, v in shown.items():
                fr = {"claim_id": cid, "artifact_id": a["artifact_id"], "document_type": a["document_type"], "item": k,
                      "expected": k != a["omitted_field"], "got": v}
                fr["agree"] = fr["expected"] == fr["got"]
                fields.append(fr)
                crow["fields"].append(fr)
        crow["all_accepted"] = all(x["accepted"] for x in crow["facts"].values()) and all(x["agree"] for x in crow["fields"])
        crow["all_strict"] = all(x["strict"] for x in crow["facts"].values()) and all(x["agree"] for x in crow["fields"])
        claims[cid] = crow
    by_state = Counter((x["state"], x["got"]) for x in rows)
    by_expr = Counter((x["expression"], x["strict"]) for x in rows if x["expression"])
    summary = {
        "claims_read": len(claims), "fact_judgements": len(rows), "content_item_judgements": len(fields),
        "facts_strict_agreement": sum(x["strict"] for x in rows), "facts_accepted": sum(x["accepted"] for x in rows),
        "content_items_agreement": sum(x["agree"] for x in fields),
        "claims_all_strict": sum(c["all_strict"] for c in claims.values()),
        "claims_all_accepted": sum(c["all_accepted"] for c in claims.values()),
        "quotes_not_found": [(x["claim_id"], x["fact"]) for x in rows if not x["quote_found"]],
        "state_x_reading": {f"{a} -> {b}": n for (a, b), n in sorted(by_state.items())},
        "stated_facts_strict_by_expression": {f"{e}:{'read' if s else 'misread'}": n for (e, s), n in sorted(by_expr.items())},
        "disagreements": [{k: x[k] for k in ("claim_id", "fact", "state", "expression", "got", "routing")}
                          for x in rows if not x["accepted"]],
        "accepted_non_strict": [{k: x[k] for k in ("claim_id", "fact", "state", "got")} for x in rows
                                if x["accepted"] and not x["strict"]],
        "content_item_disagreements": [{k: x[k] for k in ("claim_id", "document_type", "item", "expected", "got")}
                                       for x in fields if not x["agree"]],
    }
    if final:
        (BC / "comparison.json").write_text(json.dumps({"summary": summary, "claims": claims}, ensure_ascii=False, indent=1) + "\n")
        (BC / "readings.json").write_text(json.dumps({cid: {"facts": {f: x["got"] for f, x in c["facts"].items()},
                                                            "fields": [{k: y[k] for k in ("artifact_id", "item", "got")} for y in c["fields"]]}
                                                      for cid, c in claims.items()}, ensure_ascii=False, indent=1) + "\n")
    return summary


if __name__ == "__main__":
    first = main(final=False)
    (BC / "comparison_first_reading.json").write_text(json.dumps(first, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({"first_reading": first, "final": main(final=True)}, ensure_ascii=False, indent=1))
