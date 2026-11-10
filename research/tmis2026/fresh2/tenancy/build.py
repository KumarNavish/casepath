"""Builder for the fresh2 tenancy claims (Study 3 confirmatory data). No model calls.

Two steps:
  python3 build.py design     seeded design of 24 families x 4 claims: language, channel, the state of every fact
                              (stated true / stated false / absent / open; the routing fact stated, unmentioned,
                              denied or open), how each stated fact is expressed (plain / in passing / implied),
                              persona details and supplied plain-text attachments (each sufficient, or lacking one
                              required content item). Writes build/scenarios/ and build/BRIEFS.md (the author's brief).
  python3 build.py assemble   reads the authored messages and attachments (authored/*.txt), checks their structure
                              against the design, and writes data/claims/, data/references/, cohort.json and the rule
                              pack with the silence clause.

The messages were written by hand from the briefs by a generative model that is not among the evaluated models
(see ../README.md). The reference is computed by the production engine from the true flags under the silence policy,
with exact deferral (supervaluation) for the open fact; the answered plan (open fact at its true value) is recorded.
"""
from __future__ import annotations

import base64
import hashlib
import json
import random
import re
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[1]
sys.path.insert(0, str(TMIS / "harness"))
sys.path.insert(0, str(HERE))
from spec import (ANNOUNCED, CHANNELS, DISPUTE, DOC_LABEL, FACTS, FAMILIES, FIELD_TEXT, LANDLORDS,  # noqa: E402
                  OTHER_DEFECTS, PERSONAS, PLACES, ROUTING, ROUTING_FALSE, SILENCE_CLAUSE, STREETS, STYLES,
                  SUPPLIABLE)
from tenancy_data import REPO, claim_ids as s1_claim_ids, reference as s1_reference, templates as s1_templates  # noqa: E402

sys.path.insert(0, str(REPO / "casepath-api"))
from casepath_api.assessment_grammar_v1 import FAMILY_FLAGS  # noqa: E402
from casepath_api.autonomous_policy_v1 import REQUIRED_FIELDS  # noqa: E402
from casepath_tenancy import plan_from_verified_exact  # noqa: E402

SEED = 20261110
OUT = HERE / "data"
BUILD = HERE / "build"
AUTHORED = HERE / "authored"
FRESH = TMIS / "fresh" / "tenancy"
REQUEST = {"needed_now", "needed_later"}
N_OPEN = 32
N_ATT_CLAIMS = 40

for fam, docs in SUPPLIABLE.items():
    for d in docs:
        assert set(FIELD_TEXT[d]) == set(REQUIRED_FIELDS[d]), d


def hid(*parts) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:16]


# ----------------------------------------------------------------- combinations already used
def used_combinations() -> set:
    """(family, routing true?, active branch flags) of the 150 Study 1 claims and the 72 fresh/ claims."""
    out = set()
    for split in ("dev", "test"):
        for c in s1_claim_ids(split):
            r = s1_reference(c)
            routing = next(iter(r["implicit_flags"].values()), None)
            out.add((r["family"], routing, tuple(sorted(k for k, v in r["scenario"].items() if v))))
    for p in sorted((FRESH / "data" / "references").glob("*.json")):
        r = json.loads(p.read_text())
        routing = next(iter(r["implicit_flags"].values()), None)
        out.add((r["family"], routing, tuple(sorted(k for k, v in r["scenario"].items() if v))))
    return out


# ----------------------------------------------------------------- engine
def policy_verdicts(c: dict, answered: bool) -> dict:
    """Silence policy: stated true -> true; stated false -> false; absent branch fact -> presumed false;
    unmentioned routing fact -> presumed true; raised and left open -> unresolved (or its true value if answered)."""
    out = {}
    for f, s in c["fact_states"].items():
        if s == "open":
            out[f] = ("true" if c["open_value"] else "false") if answered else "unresolved"
        elif s in ("stated_true", "unmentioned"):
            out[f] = "true"
        else:
            out[f] = "false"
    return out


def engine_plan(c: dict, attachments: list[dict], answered: bool = False) -> dict:
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


def truth(c: dict) -> dict:
    routing = ROUTING.get(c["family"])
    t = {f: f in c["combo"] for f in FAMILY_FLAGS[c["family"]] if f != routing}
    if routing:
        t[routing] = c["routing_true"]
    return t


# ----------------------------------------------------------------- design
def persona(rng: random.Random, lang: str, fam: str, combo: set, open_flag: str | None, used_names: set) -> dict:
    city, canton = rng.choice(PLACES)
    rent = rng.randrange(1280, 2780, 10)
    firsts, lasts = PERSONAS[lang]
    uf, ul = {n.split()[0] for n in used_names}, {n.split()[-1] for n in used_names}
    combos = [f"{f} {x}" for f in firsts for x in lasts if f"{f} {x}" not in used_names]
    tenant = rng.choice([n for n in combos if n.split()[0] not in uf and n.split()[-1] not in ul] or
                        [n for n in combos if n.split()[0] not in uf or n.split()[-1] not in ul] or combos)
    used_names.add(tenant)
    stated = combo - {open_flag}
    if fam == "defect_mold_heating":
        parts = []
        if "mold" in stated:
            parts.append(rng.choice(["mould growing behind the wardrobe and along the bedroom ceiling",
                                     "grey-green mould on the bathroom ceiling and a musty smell in the hallway",
                                     "damp patches with black mould spots in the corner of the children's room",
                                     "condensation running down the walls and mould on the window frames"]))
        if "heating" in stated:
            parts.append(rng.choice(["the underfloor heating in the living area has stopped working",
                                     "two of the four radiators stay cold even when turned up fully",
                                     "the heating fails every few days and the flat drops to around 15 degrees",
                                     "the boiler cuts out at night so that the bedrooms are cold in the morning"]))
        defect = " and ".join(parts) if parts else rng.choice(OTHER_DEFECTS + [
            "the bathroom window cannot be closed because its frame is warped",
            "the balcony door cannot be locked because its handle mechanism is broken"])
    else:
        defect = ""
    return {
        "tenant": tenant, "landlord": rng.choice(LANDLORDS), "city": city, "canton": canton,
        "address": f"{rng.choice(STREETS)} {rng.randint(1, 120)}, {city}, {rng.choice(['2.5', '3', '3.5', '4', '4.5', '5.5'])}-room flat",
        "lease_start": f"1 {rng.choice(['March', 'May', 'September', 'December'])} {rng.randint(2009, 2023)}", "rent": rent,
        "utilities": rng.randrange(140, 340, 10),
        "received_at": f"2026-{rng.choice(['08', '09', '10'])}-{rng.randint(1, 28):02d}T{rng.randint(7, 21):02d}:{rng.choice(['05', '20', '35', '50'])}:00+02:00",
        "end_date": f"{rng.choice(['31 January', '30 April', '31 July', '31 October'])} 2027",
        "grounds": "unpaid rent (rent arrears)" if "arrears" in stated else
                   rng.choice(["the owner's son wants to move into the flat", "sale of the building",
                               "conversion of the flats into holiday apartments"]),
        "arrears_amount": rent * rng.choice([2, 3]),
        "defect": defect, "notified_on": f"{rng.randint(1, 28)} {rng.choice(['May', 'June', 'July', 'August'])} 2026",
        "repair_deadline": f"{rng.randint(1, 28)} {rng.choice(['September', 'October', 'November'])} 2026",
        "landlord_position": rng.choice(["the landlord says the tenant's ventilation habits are to blame",
                                         "the landlord accepts that something is wrong but asks for patience",
                                         "the landlord says a contractor has been informed"]),
        "proposed_work": rng.choice(["a visit by the caretaker to assess the problem", "repairs by a contractor in two weeks",
                                     "replacement of the defective part after the supplier delivers it"]),
        "access_date": f"{rng.randint(1, 28)} {rng.choice(['September', 'October', 'November'])} 2026",
        "household": rng.choice(["the tenant's partner", "the tenant's son (8)", "the tenant's daughter (5)",
                                 "the tenant's elderly mother who lives with them", "the tenant"]),
        "health_detail": rng.choice(["asthma attacks", "persistent coughing", "recurring sinus infections"]) if "mold" in stated
                         else rng.choice(["repeated colds and bronchitis", "aching joints made worse by the cold"]) if "heating" in stated
                         else rng.choice(["sleep problems and headaches", "exhaustion from broken sleep"]),
    }


def scenarios() -> list[dict]:
    rng = random.Random(SEED)
    used = used_combinations()
    seen = set()
    for fam, combo, routing in FAMILIES:
        key = (fam, routing, tuple(sorted(combo)))
        assert key not in used, key
        assert key not in seen, key
        seen.add(key)
    assert len(FAMILIES) == 24
    channels = [c for c, n in CHANNELS.items() for _ in range(n)]
    rng.shuffle(channels)
    # open facts: 32 claims. Routing-false families: one open claim each (the defining event left open).
    # Routing-true families (16): eight with two open claims, eight with one, balanced on the open fact's truth.
    rt = [i for i, f in enumerate(FAMILIES) if f[2] is not False]
    two = set(rng.sample(rt, 8))
    n_open = {i: (1 if FAMILIES[i][2] is False else (2 if i in two else 1)) for i in range(24)}
    assert sum(n_open.values()) == N_OPEN
    want = [True] * 16 + [False] * 8  # truth of the 24 open facts in routing-true families
    rng.shuffle(want)
    wi = 0
    claims = []
    for fi, (fam, combo, routing_true) in enumerate(FAMILIES):
        routing = ROUTING.get(fam)
        flags = [f for f in FAMILY_FLAGS[fam] if f != routing]
        langs = ["en", "en", "de-CH", "de-CH"]
        rng.shuffle(langs)
        open_slots = rng.sample(range(4), n_open[fi])
        open_flags = {}
        for slot in open_slots:
            if routing_true is False:
                open_flags[slot] = routing  # the defining event is left open (true value: false)
                continue
            v = want[wi]
            wi += 1
            pool = [f for f in flags if (f in combo) == v and f not in open_flags.values()]
            if routing and v and rng.random() < 0.2:
                pool = [routing]
            if not pool:
                pool = [f for f in flags if f not in open_flags.values()]
            open_flags[slot] = rng.choice(pool)
        routing_mode = {}
        if routing_true is True:
            stated = set(rng.sample(range(4), 2))
            for s in range(4):
                routing_mode[s] = "stated_true" if s in stated else "unmentioned"
        elif routing_true is False:
            for s in range(4):
                routing_mode[s] = "stated_false"
        for slot in range(4):
            of = open_flags.get(slot)
            if of == routing and routing:
                ov = bool(routing_true)
            else:
                ov = (of in combo) if of else None
            claims.append({"family_index": fi, "slot": slot, "family": fam, "combo": sorted(combo),
                           "routing_true": routing_true,
                           "family_id": "f2fam_" + hid("fresh2-tenancy-family", fam, routing_true, tuple(sorted(combo))),
                           "language": langs[slot], "channel": channels[fi * 4 + slot],
                           "open_flag": of, "open_value": ov,
                           "routing_mode": routing_mode.get(slot)})
    assert wi == 24
    # attachments: 40 claims, one or two each, half sufficient overall (drawn among claims that can carry one)
    for c in claims:
        c["rng_state"] = rng.randrange(1 << 30)
    return claims


def realise(c: dict, used_names: set) -> dict:
    c = deepcopy(c)
    rng = random.Random(c["rng_state"])
    fam, combo = c["family"], set(c["combo"])
    routing = ROUTING.get(fam)
    c["claim_id"] = "f2cl_" + hid("fresh2-tenancy-claim", c["family_index"], c["slot"])
    c["message_id"] = "f2msg_" + hid("fresh2-tenancy-message", c["claim_id"])
    c["values"] = persona(rng, c["language"], fam, combo, c["open_flag"], used_names)
    states, styles = {}, {}
    for f in FAMILY_FLAGS[fam]:
        if f == c["open_flag"]:
            states[f] = "open"
        elif f == routing:
            states[f] = c["routing_mode"]
        elif f in combo:
            states[f] = "stated_true"
        else:
            # an inactive branch fact is mostly left unmentioned; sometimes it is explicitly denied
            states[f] = "stated_false" if rng.random() < 0.15 else "absent"
        if states[f] in ("stated_true", "stated_false"):
            styles[f] = rng.choices(list(STYLES), weights=list(STYLES.values()))[0]
    c["fact_states"] = states
    c["styles"] = styles
    return c


def assign_attachments(claims: list[dict]) -> None:
    rng = random.Random(SEED + 1)
    cand = {}
    for c in claims:
        base = engine_plan(c, [])
        docs = [d for d in SUPPLIABLE[c["family"]] if base["document_states"].get(d) in REQUEST]
        if c["fact_states"].get(ROUTING.get(c["family"], "")) == "unmentioned":
            docs = [d for d in docs if d not in ("termination_notice", "rent_increase_notice")]
        if c["open_flag"] == "arrears":
            docs = [d for d in docs if d not in ("termination_notice", "payment_deadline_letter")]
        if c["open_flag"] == "deposit_considered":
            docs = [d for d in docs if d != "written_repair_deadline"]
        if c["open_flag"] in ("mold", "heating"):
            docs = [d for d in docs if d not in ("defect_notification", "landlord_response_history")]
        cand[c["claim_id"]] = docs
    eligible = [c for c in claims if cand[c["claim_id"]]]
    chosen = {c["claim_id"] for c in rng.sample(eligible, N_ATT_CLAIMS)}
    n = {cid: (2 if rng.random() < 0.3 and len(cand[cid]) > 1 else 1) for cid in sorted(chosen)}
    total = sum(n.values())
    suff = [True] * (total // 2) + [False] * (total - total // 2)
    rng.shuffle(suff)
    k = 0
    for c in claims:
        c["attachments"] = []
        if c["claim_id"] not in chosen:
            continue
        docs = rng.sample(cand[c["claim_id"]], n[c["claim_id"]])
        for j, d in enumerate(docs):
            sufficient = suff[k]
            k += 1
            omitted = None if sufficient else rng.choice(REQUIRED_FIELDS[d])
            c["attachments"].append({"artifact_id": "f2att_" + hid("fresh2-tenancy-attachment", c["claim_id"], j),
                                     "document_type": d, "sufficient": sufficient, "omitted_field": omitted})


def brief(c: dict) -> str:
    v, fam = c["values"], c["family"]
    routing = ROUTING.get(fam)
    lines = [f"## {c['claim_id']}  (family {c['family_index'] + 1}, slot {c['slot'] + 1})",
             f"- {c['language']} / {c['channel']} / sender {v['tenant']} / landlord {v['landlord']} / {v['address']} / "
             f"date {v['received_at'][:10]} / rent CHF {v['rent']}",
             f"- situation: {DISPUTE[fam]}" + (f" Defect: {v['defect']}." if v["defect"] else "")]
    for f, s in c["fact_states"].items():
        meaning = (ROUTING_FALSE[f] if (f == routing and c["routing_true"] is False) else
                   ANNOUNCED[f] if (c["routing_true"] is False and f in ANNOUNCED) else FACTS[f]["fact"])
        if s == "open":
            lines.append(f"- OPEN ({f}, true value {c['open_value']}): {meaning} -> {FACTS[f]['open']}")
        elif s == "stated_true":
            extra = {"health_effects": f" [{v['household']}: {v['health_detail']}]",
                     "arrears": f" [about CHF {v['arrears_amount']}]"}.get(f, "")
            lines.append(f"- STATE ({c['styles'][f]}) {f}: {meaning}{extra}")
        elif s == "stated_false":
            lines.append(f"- DENY ({c['styles'][f]}) {f}: NOT so: {meaning}")
        elif s == "absent":
            lines.append(f"- AVOID {f}: {meaning}")
        elif s == "unmentioned":
            lines.append(f"- AVOID-ROUTING {f}: describe the dispute but do not say whether any written notice was received")
    for a in c["attachments"]:
        items = FIELD_TEXT[a["document_type"]]
        must = [t.format(**v) if "{" in t and all(k in v for k in re.findall(r"{(\w+)}", t)) else t
                for k, t in items.items() if k != a["omitted_field"]]
        lines.append(f"- ATTACH {a['artifact_id']} {DOC_LABEL[a['document_type']]}: must contain {must}"
                     + (f"; must NOT contain: {items[a['omitted_field']].split(' (')[0]}" if a["omitted_field"] else ""))
    return "\n".join(lines)


def design() -> None:
    BUILD.mkdir(exist_ok=True)
    used_names: set = set()
    claims = [realise(c, used_names) for c in scenarios()]
    assign_attachments(claims)
    (BUILD / "scenarios").mkdir(parents=True, exist_ok=True)
    for c in claims:
        scen = {k: c[k] for k in ("claim_id", "message_id", "family", "family_id", "family_index", "slot", "combo",
                                  "routing_true", "language", "channel", "fact_states", "styles", "open_flag",
                                  "open_value", "attachments", "values")}
        (BUILD / "scenarios" / f"{c['claim_id']}.json").write_text(json.dumps(scen, ensure_ascii=False, indent=1) + "\n")
    (BUILD / "BRIEFS.md").write_text("# Author's briefs (fresh2 tenancy)\n\n" + "\n\n".join(brief(c) for c in claims) + "\n")
    print(json.dumps({"claims": len(claims), "open": sum(bool(c["open_flag"]) for c in claims),
                      "with_attachments": sum(bool(c["attachments"]) for c in claims),
                      "attachments": sum(len(c["attachments"]) for c in claims)}))


# ----------------------------------------------------------------- authored text
def parse_authored() -> dict:
    """authored/*.txt: blocks '=== <claim_id>', 'subject: ...', '--- body', '--- attachment <artifact_id> <file_name>'."""
    out = {}
    for p in sorted(AUTHORED.glob("*.txt")):
        for block in re.split(r"^=== ", p.read_text(), flags=re.M)[1:]:
            head, _, rest = block.partition("\n")
            cid = head.strip()
            m = re.match(r"subject: (.*)\n--- body\n", rest)
            assert m, cid
            rest = rest[m.end():]
            parts = re.split(r"^--- attachment (\S+) (\S+)\n", rest, flags=re.M)
            body = parts[0].strip()
            atts = [{"artifact_id": parts[i], "file_name": parts[i + 1], "text": parts[i + 2].strip() + "\n"}
                    for i in range(1, len(parts), 3)]
            assert cid not in out, cid
            out[cid] = {"subject": m.group(1).strip(), "body": body, "attachments": atts, "source": p.name}
    return out


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


def build_reference(c: dict, attachments: list[dict]) -> dict:
    plan = engine_plan(c, attachments)
    ans = engine_plan(c, attachments, answered=True)
    by_doc = {a["document_type"]: a for a in attachments}
    states = {d: state_name(r, by_doc.get(d)) for d, r in plan["document_states"].items()}
    ans_states = {d: state_name(r, by_doc.get(d)) for d, r in ans["document_states"].items()}
    routing = ROUTING.get(c["family"])
    t = truth(c)
    return {
        "claim_id": c["claim_id"], "family": c["family"], "family_id": c["family_id"],
        "scenario": {f: t[f] for f in FAMILY_FLAGS[c["family"]] if f != routing},
        "implicit_flags": {routing: bool(c["routing_true"])} if routing else {},
        "fact_states": c["fact_states"],
        "expression": c["styles"],
        "policy_verdicts": policy_verdicts(c, False),
        "open_fact": {"flag": c["open_flag"], "true_value": c["open_value"]} if c["open_flag"] else None,
        "document_states": states, "engine_routes": plan["document_states"],
        "request_set": sorted(d for d, s in states.items() if s in ("required_now", "supplied_insufficient")),
        "held_set": sorted(d for d, s in states.items() if s == "held"),
        "answered": {"document_states": ans_states,
                     "request_set": sorted(d for d, s in ans_states.items() if s in ("required_now", "supplied_insufficient"))},
        "attachments": [{k: a[k] for k in ("artifact_id", "document_type", "sufficient", "omitted_field")} for a in attachments],
        "blind_check_reading": c.get("blind_check_reading"),
        "blind_check_fields": c.get("blind_check_fields"),
        "silence_policy": SILENCE_CLAUSE,
        "engine": "casepath_api.causal_process_v1.evaluate via harness/casepath_tenancy.py::plan_from_verified_exact (supervaluation)",
    }


def assemble() -> None:
    authored = parse_authored()
    blind = {}
    bpath = BUILD / "blind_check" / "readings.json"
    if bpath.exists():
        blind = json.loads(bpath.read_text())
    scen = {p.stem: json.loads(p.read_text()) for p in sorted((BUILD / "scenarios").glob("*.json"))}
    assert set(authored) == set(scen), (set(scen) - set(authored), set(authored) - set(scen))
    rules = HERE / "rules"
    rules.mkdir(exist_ok=True)
    (rules / "static-rule-templates-v3-silence.json").write_text(json.dumps(fresh_templates(), ensure_ascii=False, indent=1) + "\n")
    for d in ("claims", "references"):
        (OUT / d).mkdir(parents=True, exist_ok=True)
        for p in (OUT / d).glob("*.json"):
            p.unlink()
    cohort = []
    for cid, c in sorted(scen.items(), key=lambda kv: (kv[1]["family_index"], kv[1]["slot"])):
        w = authored[cid]
        assert [a["artifact_id"] for a in w["attachments"]] == [a["artifact_id"] for a in c["attachments"]], cid
        c["blind_check_reading"] = blind.get(cid, {}).get("facts")
        c["blind_check_fields"] = blind.get(cid, {}).get("fields")
        atts = []
        for a, wa in zip(c["attachments"], w["attachments"]):
            raw = wa["text"].encode()
            a["sha256"] = hashlib.sha256(raw).hexdigest()
            atts.append({"artifact_id": a["artifact_id"], "file_name": wa["file_name"], "media_type": "text/plain",
                         "content_base64": base64.b64encode(raw).decode(), "sha256": a["sha256"], "size_bytes": len(raw)})
        v = c["values"]
        claim = {"contract": {"name": "casepath_observable_claim", "version": "fresh2-intake-only/1.0.0",
                              "rule": "Pass this object, and only this object, to downstream inference."},
                 "submission": {"claim_id": cid, "channel": c["channel"], "language": c["language"],
                                "received_at": v["received_at"], "canton": v["canton"]},
                 "customer_message": {"message_id": c["message_id"], "subject": w["subject"], "body": w["body"],
                                      "sent_at": v["received_at"],
                                      "from_role": "handler_note" if c["channel"] == "phone_note" else "customer",
                                      "to_role": "claims_inbox", "attachment_ids": [a["artifact_id"] for a in atts]},
                 "attachments": atts}
        (OUT / "claims" / f"{cid}.json").write_text(json.dumps(claim, ensure_ascii=False, indent=1) + "\n")
        ref = build_reference(c, c["attachments"])
        (OUT / "references" / f"{cid}.json").write_text(json.dumps(ref, ensure_ascii=False, indent=1) + "\n")
        cohort.append({"case_id": cid, "family_id": c["family_id"], "domain": c["family"], "combination": c["combo"],
                       "defining_event": c["routing_true"], "language": c["language"], "channel": c["channel"],
                       "split": "fresh2_test"})
    (HERE / "cohort.json").write_text(json.dumps({"contract": "casepath.fresh2-tenancy-cohort/1.0.0", "cases": cohort},
                                                 ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({"claims": len(cohort)}))


if __name__ == "__main__":
    {"design": design, "assemble": assemble}[sys.argv[1]]()
