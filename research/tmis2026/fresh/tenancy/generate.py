"""Released generator for the fresh tenancy claims (Study 2).

Pipeline (seeded, resumable; model responses are cached by request):
1. scenarios(): 18 families (dispute family x true-flag combination unused in Study 1) x 4 claims,
   with language, channel, the state of every fact (stated true / absent / raised and left open;
   the routing fact stated or unmentioned), persona details and supplied plain-text attachments
   (each sufficient, or lacking one required content item).
2. reference(): the production engine computes every document's state from the true flags under
   the silence policy (absent -> false, routing fact -> true, open fact -> unresolved), with exact
   deferral (supervaluation) for the open fact; the answered plan (open fact at its true value)
   is recorded as well.
3. write(): a model that is not evaluated in the study writes the message and the attachments
   from the scenario only (no rules, no document lists).
4. check(): the same model, in a fresh context without the scenario, reads the message and the
   attachments and reports each fact's status and each attachment's content items. A claim whose
   check disagrees is rewritten at most twice (with feedback naming the fact or item, never a
   rule); otherwise it is replaced by a new claim with the same design.

Usage: TMIS_BUDGET_USD=<ledger spend + 2.00> python3 generate.py [--dry]
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import random
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[1]
sys.path.insert(0, str(TMIS / "harness"))
sys.path.insert(0, str(HERE))
from spec import (CHANNELS, DISPUTE, DOC_LABEL, FACTS, FAMILIES, FIELD_TEXT, LANDLORDS, OTHER_DEFECTS,  # noqa: E402
                  PERSONAS, PLACES, ROUTING, SILENCE_CLAUSE, STREETS, SUPPLIABLE)
from tenancy_data import REPO, claim_ids as s1_claim_ids, reference as s1_reference, templates as s1_templates  # noqa: E402

sys.path.insert(0, str(REPO / "casepath-api"))
from casepath_api.assessment_grammar_v1 import FAMILY_FLAGS  # noqa: E402
from casepath_api.autonomous_policy_v1 import REQUIRED_FIELDS  # noqa: E402
from casepath_tenancy import plan_from_verified_exact  # noqa: E402

MODEL = "anthropic/claude-haiku-5.5"
SEED = 20261109
FRESH_BUDGET = 2.00
OUT = HERE / "data"
BUILD = HERE / "build"
REQUEST = {"needed_now", "needed_later"}
_lock = threading.Lock()

for fam, docs in SUPPLIABLE.items():
    for d in docs:
        assert set(FIELD_TEXT[d]) == set(REQUIRED_FIELDS[d]), d


# ----------------------------------------------------------------- rule pack with the silence clause
def fresh_templates() -> dict:
    t = deepcopy(s1_templates())
    for tpl in t["templates"]:
        start = len(tpl["content"]) + 1
        tpl["content"] = tpl["content"] + " " + SILENCE_CLAUSE
        tpl["clauses"].append({"clause_id": f"policy-{tpl['domain']}-v1.clause-silence", "content": SILENCE_CLAUSE,
                               "content_sha256": hashlib.sha256(SILENCE_CLAUSE.encode()).hexdigest(),
                               "start_char": start, "end_char": start + len(SILENCE_CLAUSE)})
    t["contract"] = str(t.get("contract")) + "+silence-policy"
    return t


# ----------------------------------------------------------------- scenarios
def study1_combinations() -> set:
    out = set()
    for split in ("dev", "test"):
        for c in s1_claim_ids(split):
            r = s1_reference(c)
            out.add((r["family"], tuple(sorted(k for k, v in r["scenario"].items() if v))))
    return out


def hid(*parts) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:16]


def persona(rng: random.Random, lang: str, fam: str, active: set, open_flag: str | None) -> dict:
    city, canton = rng.choice(PLACES)
    rent = rng.randrange(1350, 2650, 10)
    stated = active - {open_flag}
    if fam == "defect_mold_heating":
        parts = []
        if "mold" in stated:
            parts.append(rng.choice(["black mould spreading on the bedroom wall and around the bathroom window",
                                     "mould stains and damp patches in the children's room"]))
        if "heating" in stated:
            parts.append(rng.choice(["the radiators in the living room and bedrooms stay cold",
                                     "the heating keeps failing so that the flat cools down to about 16 degrees"]))
        defect = " and ".join(parts) if parts else rng.choice(OTHER_DEFECTS)
    else:
        defect = ""
    v = {
        "tenant": rng.choice(PERSONAS[lang]), "landlord": rng.choice(LANDLORDS), "city": city, "canton": canton,
        "address": f"{rng.choice(STREETS)} {rng.randint(2, 88)}, {city}, {rng.choice(['2', '3', '3.5', '4', '4.5'])}-room flat",
        "lease_start": f"1 {rng.choice(['April', 'October', 'June'])} {rng.randint(2012, 2022)}", "rent": rent,
        "utilities": rng.randrange(160, 320, 10),
        "received_at": f"2026-{rng.choice(['09', '10', '11'])}-{rng.randint(1, 28):02d}T{rng.randint(8, 18):02d}:{rng.choice(['00', '15', '30', '45'])}:00+01:00",
        "end_date": f"{rng.choice(['31 March', '30 June', '30 September'])} 2027",
        "grounds": "unpaid rent (rent arrears)" if "arrears" in stated else
                   rng.choice(["the landlord needs the flat for a close relative", "planned total renovation of the building"]),
        "arrears_amount": rent * rng.choice([2, 3]),
        "new_rent": rent + rng.randrange(80, 260, 10), "effective_date": f"1 {rng.choice(['April', 'July'])} 2027",
        "increase_reasons": "the rise of the mortgage reference interest rate from 1.75 % to 2.0 % and the value-enhancing renovation of the kitchens and windows",
        "calculation_inputs": "reference rate +0.25 points = +3.0 %; renovation costs of CHF 420,000, 50 % value-enhancing, allocated to 12 flats",
        "prior_date": f"1 {rng.choice(['April', 'October'])} {rng.randint(2019, 2023)}",
        "prior_rent": rent - rng.randrange(40, 160, 10), "prior_rate": rng.choice(["1.25", "1.5"]),
        "defect": defect, "notified_on": f"{rng.randint(1, 28)} {rng.choice(['June', 'July', 'August'])} 2026",
        "repair_deadline": f"{rng.randint(1, 28)} {rng.choice(['October', 'November'])} 2026",
        "landlord_position": "the landlord acknowledges the report and says the matter will be looked at",
        "proposed_work": rng.choice(["a repair by a contractor", "an inspection by the caretaker followed by repairs"]),
        "access_date": f"{rng.randint(1, 28)} {rng.choice(['October', 'November'])} 2026",
        "health_detail": {"mold": "breathing problems", "heating": "repeated colds and bronchitis"}.get(
            next((f for f in ("mold", "heating") if f in stated), ""), "sleep problems and headaches"),
    }
    return v


def scenarios() -> list[dict]:
    rng = random.Random(SEED)
    used = study1_combinations()
    for fam, combo in FAMILIES:
        assert (fam, tuple(sorted(combo))) not in used, (fam, combo)
    assert len(set(FAMILIES)) == len(FAMILIES) == 18
    channels = [c for c, n in CHANNELS.items() for _ in range(n)]
    rng.shuffle(channels)
    open_truth_toggle = 0
    claims = []
    for fi, (fam, combo) in enumerate(FAMILIES):
        flags = [f for f in FAMILY_FLAGS[fam] if f != ROUTING.get(fam)]
        langs = ["en", "en", "de-CH", "de-CH"]
        rng.shuffle(langs)
        open_slot = rng.randrange(4)
        routing_stated = set(rng.sample(range(4), 2)) if fam in ROUTING else set()
        for slot in range(4):
            open_flag, open_value = None, None
            if slot == open_slot:
                want_true = open_truth_toggle % 2 == 0
                pool = [f for f in flags if (f in combo) == want_true] or flags
                open_flag = rng.choice(pool)
                open_value = open_flag in combo
                open_truth_toggle += 1
            claims.append({"family_index": fi, "slot": slot, "family": fam, "combo": list(combo),
                           "family_id": "ffam_" + hid("fresh-tenancy-family", fam, combo),
                           "language": langs[slot], "channel": channels[fi * 4 + slot],
                           "open_flag": open_flag, "open_value": open_value,
                           "routing_stated": (slot in routing_stated) if fam in ROUTING else None})
    # attachments: about 40% of claims, one or two each, half sufficient overall
    with_att = set(rng.sample(range(len(claims)), 29))
    specs = []
    for i, c in enumerate(claims):
        c["n_attachments"] = (2 if rng.random() < 0.35 else 1) if i in with_att else 0
    total = sum(c["n_attachments"] for c in claims)
    suff = [True] * (total // 2) + [False] * (total - total // 2)
    rng.shuffle(suff)
    k = 0
    for c in claims:
        c["sufficient_draws"] = suff[k:k + c["n_attachments"]]
        k += c["n_attachments"]
        c["rng_state"] = rng.randrange(1 << 30)
        specs.append(c)
    return specs


def realise(c: dict, replacement: int) -> dict:
    """Concrete claim from its design slot (a replacement draws new persona details and attachments)."""
    c = deepcopy(c)
    rng = random.Random(c["rng_state"] + 7919 * replacement)
    fam, active = c["family"], set(c["combo"])
    c["replacement"] = replacement
    c["claim_id"] = "fcl_" + hid("fresh-tenancy-claim", c["family_index"], c["slot"], replacement)
    c["message_id"] = "fmsg_" + hid("fresh-tenancy-message", c["claim_id"])
    c["values"] = persona(rng, c["language"], fam, active, c["open_flag"])
    states = {}
    for f in FAMILY_FLAGS[fam]:
        if f == ROUTING.get(fam):
            states[f] = "stated_true" if c["routing_stated"] else "unmentioned"
        elif f == c["open_flag"]:
            states[f] = "open"
        else:
            states[f] = "stated_true" if f in active else "absent"
    c["fact_states"] = states
    # attachments: suppliable documents the claim requires now (never one held behind the open fact),
    # never one that would reveal an unmentioned routing fact or settle the open fact
    base = reference_plan(c, [])
    candidates = [d for d in SUPPLIABLE[fam] if base["document_states"].get(d) in REQUEST]
    if not c["routing_stated"]:
        candidates = [d for d in candidates if d not in ("termination_notice", "rent_increase_notice")]
    if c["open_flag"] in ("arrears",):
        candidates = [d for d in candidates if d not in ("termination_notice", "payment_deadline_letter")]
    if c["open_flag"] in ("reference_rate", "renovation"):
        candidates = [d for d in candidates if d not in ("stated_calculation", "prior_rent_adjustment")]
    n = min(c["n_attachments"], len(candidates))
    docs = rng.sample(candidates, n)
    c["attachments"] = []
    for j, (d, sufficient) in enumerate(zip(docs, c["sufficient_draws"])):
        omitted = None if sufficient else rng.choice(REQUIRED_FIELDS[d])
        c["attachments"].append({"artifact_id": "fatt_" + hid("fresh-tenancy-attachment", c["claim_id"], j),
                                 "document_type": d, "sufficient": sufficient, "omitted_field": omitted})
    return c


# ----------------------------------------------------------------- reference by the production engine
def policy_verdicts(c: dict, answered: bool) -> dict:
    out = {}
    for f, s in c["fact_states"].items():
        if s == "open":
            out[f] = ("true" if c["open_value"] else "false") if answered else "unresolved"
        elif s in ("stated_true", "unmentioned"):  # unmentioned only for the routing fact: presumed to have occurred
            out[f] = "true"
        else:  # absent: presumed absent
            out[f] = "false"
    return out


def reference_plan(c: dict, attachments: list[dict], answered: bool = False) -> dict:
    verified = {"category": {"family": c["family"], "summary": "", "citations": []},
                "conditions": [{"flag": f, "verdict": v, "summary": "", "citations": []}
                               for f, v in policy_verdicts(c, answered).items()],
                "documents": [{"document_type": a["document_type"], "artifact_id": a["artifact_id"],
                               "assessment": "sufficient" if a["sufficient"] else "insufficient", "summary": "",
                               "citations": [], "independently_verified": True} for a in attachments],
                "steps": [], "item_rejections": []}
    srcs = [{"artifact_id": a["artifact_id"], "role": "supporting_document", "file_name": a["artifact_id"] + ".txt",
             "media_type": "text/plain", "sha256": a.get("sha256", "0" * 64)} for a in attachments]
    return plan_from_verified_exact(c["claim_id"], verified, srcs)


def state_name(route: str, supplied: dict | None) -> str:
    if route in REQUEST:
        return "supplied_insufficient" if supplied is not None else "required_now"
    if route == "held_behind_question":
        return "held"
    if route == "established":
        return "supplied_sufficient"
    return "not_needed"


def build_reference(c: dict, attachments: list[dict]) -> dict:
    plan = reference_plan(c, attachments)
    ans = reference_plan(c, attachments, answered=True)
    by_doc = {a["document_type"]: a for a in attachments}
    states = {d: state_name(r, by_doc.get(d)) for d, r in plan["document_states"].items()}
    ans_states = {d: state_name(r, by_doc.get(d)) for d, r in ans["document_states"].items()}
    routing = ROUTING.get(c["family"])
    return {
        "claim_id": c["claim_id"], "family": c["family"], "family_id": c["family_id"],
        "scenario": {f: f in c["combo"] for f in FAMILY_FLAGS[c["family"]] if f != routing},
        "implicit_flags": {routing: True} if routing else {},
        "fact_states": c["fact_states"],
        "policy_verdicts": policy_verdicts(c, False),
        "open_fact": {"flag": c["open_flag"], "true_value": c["open_value"]} if c["open_flag"] else None,
        "document_states": states, "engine_routes": plan["document_states"],
        "request_set": sorted(d for d, s in states.items() if s in ("required_now", "supplied_insufficient")),
        "held_set": sorted(d for d, s in states.items() if s == "held"),
        "answered": {"document_states": ans_states,
                     "request_set": sorted(d for d, s in ans_states.items() if s in ("required_now", "supplied_insufficient"))},
        "attachments": [{k: a[k] for k in ("artifact_id", "document_type", "sufficient", "omitted_field")} for a in attachments],
        "silence_policy": SILENCE_CLAUSE,
        "engine": "casepath_api.causal_process_v1.evaluate via harness/casepath_tenancy.py::plan_from_verified_exact (supervaluation)",
    }


# ----------------------------------------------------------------- writer and blind checker
WRITER_SYSTEM = """You write realistic synthetic correspondence that arrives in the claims inbox of a Swiss legal-expenses insurer
(tenancy disputes). You receive a scenario and must follow it exactly:
- State every fact under "state_clearly" unambiguously, in the sender's own words, with the given details.
- If there is an "open_fact", raise it and leave it explicitly open (for example "I am not sure whether ...",
  "we have not yet ..."). Never resolve it in either direction.
- Never mention, hint at, or deny anything listed under "do_not_mention". Do not add other legally relevant facts.
- If attachments are listed, the message may refer to them briefly. Write each attachment as the plain text of that
  document, containing every item under "must_contain" with the given details and none of the items under
  "must_not_contain" (not even indirectly). Attachments are sober, realistic documents.
- Channel: email = a normal e-mail; portal = a web-form submission written by the tenant; chat = a few informal chat
  turns by the tenant joined into one text; phone_note = a handler's note of a phone call, in the third person.
- Language: "en" = English; "de-CH" = Swiss Standard German (write "ss" instead of "ß"; umlauts ä, ö, ü as usual).
- The message body must have between 140 and 210 words (attachments not counted).
Return only the JSON object."""

CHECK_SYSTEM = """You read one incoming tenancy claim (a message and possibly attachments) received by a Swiss legal-expenses
insurer. You know nothing else about the case. For each listed fact, report exactly one status:
- stated_true: the message or an attachment clearly states that the fact is so;
- stated_false: it clearly states that the fact is not so;
- open: the fact is raised but explicitly left uncertain or undecided;
- not_mentioned: the fact is not addressed at all.
Quote the decisive words (empty if not mentioned). For each attachment and each listed content item, report whether
the attachment explicitly shows that item. Judge only what the text says. Return only the JSON object."""


def generic(text: str) -> str:
    return text.split(" (")[0]


def writer_payload(c: dict, feedback: list[str]) -> dict:
    v, fam = c["values"], c["family"]
    detail = {"health_effects": f"(details: {v['health_detail']})",
              "arrears": f"(details: arrears of about CHF {v['arrears_amount']})"}
    state, avoid = [], []
    for f, s in c["fact_states"].items():
        if s == "stated_true":
            state.append(FACTS[f]["fact"] + (" " + detail[f] if f in detail else ""))
        elif s == "absent":
            avoid.append(FACTS[f]["fact"])
        elif s == "unmentioned":
            avoid.append(FACTS[f]["fact"] + " (describe the dispute itself, but do not say whether or when any written "
                                            "notice or notification was received)")
    situation = DISPUTE[fam] + (f" The defect: {v['defect']}." if v["defect"] else "")
    att = []
    for a in c["attachments"]:
        items = FIELD_TEXT[a["document_type"]]
        att.append({"document": DOC_LABEL[a["document_type"]],
                    "must_contain": [t.format(**v) for k, t in items.items() if k != a["omitted_field"]],
                    "must_not_contain": [generic(items[a["omitted_field"]])] if a["omitted_field"] else []})
    p = {"language": c["language"], "channel": c["channel"], "sender": v["tenant"], "landlord": v["landlord"],
         "flat": v["address"], "date": v["received_at"][:10], "situation": situation, "state_clearly": state,
         "do_not_mention": avoid, "attachments": att}
    if c["open_flag"]:
        p["open_fact"] = f"{FACTS[c['open_flag']]['fact']} -> {FACTS[c['open_flag']]['open']}"
    if feedback:
        p["corrections_to_previous_draft"] = feedback
    return p


def writer_schema(n_att: int) -> dict:
    att = {"type": "object", "properties": {"file_name": {"type": "string"}, "text": {"type": "string"}},
           "required": ["file_name", "text"], "additionalProperties": False}
    return {"type": "object", "properties": {"subject": {"type": "string"}, "body": {"type": "string"},
                                             "attachments": {"type": "array", "items": att, "minItems": n_att, "maxItems": n_att}},
            "required": ["subject", "body", "attachments"], "additionalProperties": False}


def check_payload(c: dict, written: dict) -> tuple[dict, dict]:
    flags = list(c["fact_states"])
    facts = [{"fact_id": f, "fact": FACTS[f]["fact"]} for f in flags]
    atts = [{"file_name": w["file_name"], "text": w["text"],
             "content_items": [{"item_id": k, "item": generic(t)} for k, t in FIELD_TEXT[a["document_type"]].items()]}
            for a, w in zip(c["attachments"], written["attachments"])]
    payload = {"message": {"channel": c["channel"], "subject": written["subject"], "body": written["body"]},
               "attachments": atts, "facts": facts}
    item = {"type": "object", "properties": {"item_id": {"type": "string"}, "shown": {"type": "boolean"}},
            "required": ["item_id", "shown"], "additionalProperties": False}
    schema = {"type": "object", "properties": {
        "facts": {"type": "array", "items": {"type": "object", "properties": {
            "fact_id": {"type": "string", "enum": flags},
            "status": {"type": "string", "enum": ["stated_true", "stated_false", "open", "not_mentioned"]},
            "quote": {"type": "string"}}, "required": ["fact_id", "status", "quote"], "additionalProperties": False}},
        "attachments": {"type": "array", "items": {"type": "object", "properties": {
            "file_name": {"type": "string"}, "items": {"type": "array", "items": item}},
            "required": ["file_name", "items"], "additionalProperties": False}}},
        "required": ["facts", "attachments"], "additionalProperties": False}
    return payload, schema


EXPECTED = {"stated_true": "stated_true", "absent": "not_mentioned", "open": "open", "unmentioned": "not_mentioned"}


def compare(c: dict, written: dict, verdict: dict) -> dict:
    got = {r["fact_id"]: r["status"] for r in verdict["facts"]}
    facts = {f: {"expected": EXPECTED[s], "got": got.get(f)} for f, s in c["fact_states"].items()}
    fields = []
    for a, rep in zip(c["attachments"], verdict["attachments"] + [None] * len(c["attachments"])):
        shown = {r["item_id"]: r["shown"] for r in (rep or {}).get("items", [])}
        for k in REQUIRED_FIELDS[a["document_type"]]:
            fields.append({"document_type": a["document_type"], "field": k, "expected": k != a["omitted_field"],
                           "got": shown.get(k)})
    words = len(written["body"].split())
    return {"facts": facts, "fields": fields, "words": words, "length_ok": 130 <= words <= 220,
            "facts_agree": all(x["expected"] == x["got"] for x in facts.values()),
            "fields_agree": all(x["expected"] == x["got"] for x in fields)}


def feedback_for(cmp: dict, c: dict) -> list[str]:
    fb = []
    for f, x in cmp["facts"].items():
        if x["expected"] != x["got"]:
            want = {"stated_true": "be stated clearly", "not_mentioned": "not be mentioned at all", "open": "be raised but left explicitly open"}[x["expected"]]
            fb.append(f"A reader took this as '{x['got']}', but it must {want}: {FACTS[f]['fact']}")
    for x in cmp["fields"]:
        if x["expected"] != x["got"]:
            item = generic(FIELD_TEXT[x["document_type"]][x["field"]])
            fb.append(f"In {DOC_LABEL[x['document_type']]}, {item} must be {'clearly shown' if x['expected'] else 'absent'}.")
    if not cmp["length_ok"]:
        fb.append(f"The body had {cmp['words']} words; it must have between 140 and 210.")
    return fb


def fresh_spend() -> float:
    import llm
    total = 0.0
    if llm.LEDGER.exists():
        for line in llm.LEDGER.read_text().splitlines():
            r = json.loads(line)
            if (r.get("tag") or {}).get("exp") == "fresh_generation":
                total += float(r.get("cost") or 0)
    return total


def call(system, payload, schema, name, run, tag):
    import llm
    with _lock:
        if fresh_spend() >= FRESH_BUDGET - 0.05:
            raise llm.BudgetExceeded("fresh generation budget reached")
    for attempt in range(4):  # the client retries HTTP errors but not a connection reset during the read
        try:
            return llm.call(system=system, user=json.dumps(payload, ensure_ascii=False), schema=schema, schema_name=name,
                            run=run, tag={"exp": "fresh_generation", **tag}, model=MODEL, max_tokens=4000)
        except (ConnectionError, OSError) as exc:
            if attempt == 3:
                return {"result": None, "error": f"{type(exc).__name__}: {exc}"}
            import time
            time.sleep(5 * (attempt + 1))


def produce(slot: dict) -> dict:
    """Write and check one design slot: up to three drafts per claim, up to three claims per slot."""
    log = {"slot": [slot["family_index"], slot["slot"]], "claims": []}
    for replacement in range(3):
        c = realise(slot, replacement)
        feedback, attempts = [], []
        for attempt in range(3):
            w = call(WRITER_SYSTEM, writer_payload(c, feedback), writer_schema(len(c["attachments"])), "fresh_claim",
                     attempt, {"step": "write", "claim": c["claim_id"]})
            if not w["result"]:
                attempts.append({"attempt": attempt, "error": w["error"]})
                continue
            payload, schema = check_payload(c, w["result"])
            k = call(CHECK_SYSTEM, payload, schema, "blind_check", attempt, {"step": "check", "claim": c["claim_id"]})
            if not k["result"]:
                attempts.append({"attempt": attempt, "error": k["error"]})
                continue
            cmp = compare(c, w["result"], k["result"])
            attempts.append({"attempt": attempt, **cmp})
            if cmp["facts_agree"] and cmp["fields_agree"] and cmp["length_ok"]:
                log["claims"].append({"claim_id": c["claim_id"], "accepted": True, "attempts": attempts})
                return {"claim": c, "written": w["result"], "log": log}
            feedback = feedback_for(cmp, c)
        log["claims"].append({"claim_id": c["claim_id"], "accepted": False, "attempts": attempts})
    return {"claim": None, "written": None, "log": log}


# ----------------------------------------------------------------- output
def save(c: dict, written: dict) -> None:
    atts = []
    for a, w in zip(c["attachments"], written["attachments"]):
        raw = w["text"].encode()
        a["sha256"] = hashlib.sha256(raw).hexdigest()
        name = w["file_name"] if w["file_name"].endswith(".txt") else w["file_name"].rsplit(".", 1)[0] + ".txt"
        atts.append({"artifact_id": a["artifact_id"], "file_name": name, "media_type": "text/plain",
                     "content_base64": base64.b64encode(raw).decode(), "sha256": a["sha256"], "size_bytes": len(raw)})
    claim = {"contract": {"name": "casepath_observable_claim", "version": "fresh-intake-only/1.0.0",
                          "rule": "Pass this object, and only this object, to downstream inference."},
             "submission": {"claim_id": c["claim_id"], "channel": c["channel"], "language": c["language"],
                            "received_at": c["values"]["received_at"], "canton": c["values"]["canton"]},
             "customer_message": {"message_id": c["message_id"], "subject": written["subject"], "body": written["body"],
                                  "sent_at": c["values"]["received_at"], "from_role": "handler_note" if c["channel"] == "phone_note" else "customer",
                                  "to_role": "claims_inbox", "attachment_ids": [a["artifact_id"] for a in atts]},
             "attachments": atts}
    (OUT / "claims").mkdir(parents=True, exist_ok=True)
    (OUT / "references").mkdir(parents=True, exist_ok=True)
    (OUT / "claims" / f"{c['claim_id']}.json").write_text(json.dumps(claim, ensure_ascii=False, indent=1) + "\n")
    ref = build_reference(c, c["attachments"])
    (OUT / "references" / f"{c['claim_id']}.json").write_text(json.dumps(ref, ensure_ascii=False, indent=1) + "\n")
    scen = {k: c[k] for k in ("claim_id", "family", "family_id", "combo", "language", "channel", "fact_states",
                              "open_flag", "open_value", "routing_stated", "attachments", "values", "replacement")}
    (BUILD / "scenarios").mkdir(parents=True, exist_ok=True)
    (BUILD / "scenarios" / f"{c['claim_id']}.json").write_text(json.dumps(scen, ensure_ascii=False, indent=1) + "\n")


def main() -> None:
    BUILD.mkdir(exist_ok=True)
    rules = HERE / "rules"
    rules.mkdir(exist_ok=True)
    (rules / "static-rule-templates-v3-silence.json").write_text(json.dumps(fresh_templates(), ensure_ascii=False, indent=1) + "\n")
    slots = scenarios()
    if "--dry" in sys.argv:
        for s in slots[:6]:
            c = realise(s, 0)
            print(json.dumps(writer_payload(c, []), ensure_ascii=False, indent=1))
            print(json.dumps(build_reference(c, c["attachments"]), indent=1)[:1500])
        return
    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(produce, slots))
    logs, cohort = [], []
    for r in results:
        logs.append(r["log"])
        if r["claim"]:
            save(r["claim"], r["written"])
            c = r["claim"]
            cohort.append({"case_id": c["claim_id"], "family_id": c["family_id"], "domain": c["family"],
                           "combination": c["combo"], "language": c["language"], "channel": c["channel"], "split": "fresh_test"})
    (HERE / "cohort.json").write_text(json.dumps({"contract": "casepath.fresh-tenancy-cohort/1.0.0", "cases": cohort},
                                                 ensure_ascii=False, indent=1) + "\n")
    (BUILD / "generation_log.json").write_text(json.dumps({"model": MODEL, "seed": SEED, "slots": logs,
                                                            "fresh_generation_spend_usd": fresh_spend()}, indent=1) + "\n")
    print(json.dumps({"claims": len(cohort), "slots": len(slots), "spend": round(fresh_spend(), 4)}))


if __name__ == "__main__":
    main()
