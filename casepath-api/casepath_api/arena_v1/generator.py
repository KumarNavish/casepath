"""Arena v1 episode generator: latent specification → writer brief → assembled case.

Domain knowledge packs are the only domain-specific bindings (catalog, requirements, standards, narrative
seeds). Everything else (latent sampling, motifs, availability profiles, assembly, evaluator) is fixed.
Natural-language paragraphs are produced by an external writer from the brief; the gold never depends on
the wording, only on the latent specification and the returned-source identities.
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
from typing import Any

PACKS: dict[str, dict[str, Any]] = {
    "heating_defect": {
        "static_category": "rental defect / heating and moisture",
        "catalog": [
            ("A1", "Calibrated overnight temperature or humidity log for the occupied rooms", "measurement service or customer logger", False),
            ("A2", "Contractor service report stating the technical diagnosis and repair plan", "heating contractor", False),
            ("A3", "Landlord or property-manager response history to the defect notice", "property manager", False),
            ("A4", "Written repair deadline letter with the deposit warning", "customer", False),
            ("A5", "Medical confirmation of health effects for an occupant", "physician", False),
            ("A6", "Authenticated property-management case export covering diagnosis and response history", "property manager (authenticated export)", True),
            ("A7", "Photographs of the apartment", "customer", False),
        ],
        "requirements": [
            ("R-COND", "Calibrated overnight conditions in the occupied rooms", [["A1"]], True, None),
            ("R-CAUSE", "Technical cause and repair plan from the contractor", [["A2"], ["A6"]], True, None),
            ("R-NOTICE", "Notice, deadline and landlord response history", [["A3", "A4"], ["A6"]], True, None),
            ("R-HEALTH", "Medical confirmation of health effects (only once a return reports health effects)", [["A5"]], True, "A2"),
        ],
        "irrelevant": ["A7"],
        "static_checklist": ["A1", "A2", "A4", "A7"],
        "families": [
            ("boiler", "repeated boiler failure during freezing weather; part reportedly on order"),
            ("leak", "recurring water leak under the kitchen sink after an expired repair deadline"),
            ("mould", "mould patches in the bedroom with a disputed cause (ventilation vs. structural)"),
            ("access", "uninspected dampness with disputed contractor access at scheduled visits"),
            ("ventilation", "extractor failure and condensation with the manager blaming user behaviour"),
            ("radiator", "cold radiators in two rooms after a botched valve replacement"),
            ("chimney", "gas heater shut-down by the chimney sweep with no follow-up repair"),
            ('thermostat', 'a replaced thermostat that never regulates, the manager calling the setting a tenant preference'),
            ('underfloor', 'underfloor heating cold in half the flat after a screed repair, with two trades blaming each other'),
            ('night_shutoff', 'a shared boiler switched off overnight, justified by house rules the tenant has never seen'),
            ('hot_water', 'hot water falling to lukewarm every evening while the circulation pump is said to have been checked'),
            ('window_seal', 'failed window seals on the weather side with condensation on the frames, blamed on airing habits'),
            ('facade', "a persistently cold child's room after a facade renovation, thermal bridging suspected but unmeasured"),
            ('meter_dispute', 'heating costs billed from a meter the tenant says was never read, in a flat that stayed cold'),
            ('pipe_burst', 'a burst riser pipe patched twice, with the manager treating each repair as final'),
            ('boiler_age', 'an end-of-life boiler kept running on emergency callouts instead of replacement'),
            ('district_heat', 'a district-heating substation delivering below contract temperature, disputed by the supplier'),
            ('solar_backup', 'a solar thermal system whose backup element was never commissioned'),
            ('cellar_damp', "rising damp in a ground-floor flat that the manager attributes to the tenant's furniture"),
            ('roof_leak', 'a roof leak reappearing each storm after a repair declared complete'),
            ('smart_valve', 'smart radiator valves locked to a building schedule the tenant cannot see'),
            ('heat_pump', 'a new heat pump that never reaches setpoint, the installer blaming the building fabric'),
            ('balcony_door', 'a warped balcony door letting cold in, called wear and tear by the manager'),
            ('boiler_noise', 'a boiler cycling loudly through the night, measured by nobody'),
            ('shared_meter', 'a shared heating meter split by a key the tenant has never been shown'),
            ('winter_gap', 'heating switched off between seasons by a building schedule during a cold snap'),
            ('legionella', 'hot water held below the required temperature after a legionella flush'),
            ('draught', 'a persistent draught from an unsealed service duct behind the kitchen units'),
        ],
    },
    "termination_payment": {
        "static_category": "lease termination with disputed payment timing",
        "catalog": [
            ("B1", "Bank export showing the execution and value date of the rent payment", "customer's bank", False),
            ("B2", "Property-manager ledger showing the posting and allocation of the payment", "property manager", False),
            ("B3", "Cure notice with termination warning as served", "landlord", False),
            ("B4", "Termination notice on the official form", "landlord", False),
            ("B5", "Registered-mail or delivery proof for the notices", "postal service", False),
            ("B6", "Authenticated chronology packet from the landlord's system covering notices and service", "landlord (authenticated export)", True),
            ("B7", "Signed lease contract", "customer", False),
        ],
        "requirements": [
            ("R-PAY", "Bank-attested execution and value date of the payment", [["B1"]], True, None),
            ("R-POST", "Manager-side posting and allocation of the payment", [["B2"]], True, None),
            ("R-NOTICES", "Content and service of the cure and termination notices", [["B3", "B4", "B5"], ["B6"]], True, None),
            ("R-ALLOC", "Allocation statement for a mixed demand (only once the ledger shows a mixed demand)", [["B2"]], True, "B2"),
        ],
        "irrelevant": ["B7"],
        "static_checklist": ["B1", "B3", "B4", "B7"],
        "families": [
            ("late_paid", "one month late but paid before the termination; manager says posted afterwards"),
            ("mixed_demand", "rent paid within the period but a fridge invoice unpaid; ledger shows one total"),
            ("wrong_address", "cure notice sent to the old address; termination arrived by ordinary mail"),
            ("family_home", "termination served to one spouse only in a family home"),
            ("standing_order", "standing order executed on the 1st but bank holiday delayed the value date"),
            ("partial_payment", "partial payment accepted verbally by the caretaker before the deadline"),
            ("retaliation", "termination two weeks after a written defect complaint"),
            ('bank_holiday', 'rent credited on the next banking day after a public holiday and treated as late'),
            ('wrong_account', 'payment sent to a closed account named in an old lease annex and returned a week later'),
            ('sublet_payer', "rent paid from the subtenant's own account, which the manager declines to allocate"),
            ('deposit_offset', 'arrears offset against the deposit while the termination is pursued regardless'),
            ('joint_tenant', 'notice served on only one of two joint tenants after a separation'),
            ('estate', "termination after the tenant's death served on the household rather than on the estate"),
            ('cure_window', 'a cure deadline counted from the drafting date rather than from the date of service'),
            ('standing_lapsed', 'a standing order that lapsed silently at a bank migration and went unnoticed for two months'),
            ('rounding', 'a few francs short each month from a rounding error, accumulated into a cure demand'),
            ('charges_arrears', 'arrears consisting only of disputed ancillary charges, used to terminate the lease'),
            ('early_release', 'a replacement tenant proposed and refused, then rent charged for the empty months'),
            ('notice_form', 'a termination sent by ordinary letter where the official form is required'),
            ('agent_change', 'a change of managing agent mid-dispute, with the file not carried across'),
            ('holiday_service', 'notice served during the statutory protected period and backdated'),
            ('double_debit', 'a duplicated direct debit reversed by the bank and counted as a missed month'),
            ('grace_custom', 'a long-standing informal grace period withdrawn without notice'),
            ('guarantor', 'a guarantor payment refused as coming from the wrong party'),
            ('mail_hold', 'notices delivered during a postal hold the landlord had been told about'),
            ('renovation_exit', 'termination framed as renovation need while arrears are alleged in parallel'),
            ('part_month', 'a part-month proration dispute escalated into a cure demand'),
            ('successor', 'a lease successor after a household change treated as having no standing'),
        ],
    },
    "rent_increase": {
        "static_category": "rent-adjustment calculation",
        "catalog": [
            ("C1", "Signed increase notice or form showing the form date and referenced rate or table", "landlord", False),
            ("C2", "Publication excerpt for the referenced rate or calculation table and its effective period", "public register", False),
            ("C3", "Workflow or audit log showing when the final form content was prepared", "property manager", False),
            ("C4", "Calculation worksheet showing the starting basis used for the notice", "property manager", False),
            ("C5", "Authenticated administrative export for the notice, table reference and preparation history", "property manager (authenticated export)", True),
            ("C6", "Renovation cost breakdown supporting a value-added increase", "property manager", False),
            ("C7", "Current rent-payment receipts", "customer", False),
        ],
        "requirements": [
            ("R-SEQ", "Signed form date, exact table with its period, and final preparation time", [["C1", "C2", "C3"], ["C5"]], True, None),
            ("R-BASIS", "Starting calculation basis linked to the notice", [["C4"]], True, None),
            ("R-RENOV", "Renovation cost breakdown (only once the notice reveals a renovation reason)", [["C6"]], True, "C1"),
        ],
        "irrelevant": ["C7"],
        "static_checklist": ["C1", "C2", "C4", "C7"],
        "families": [
            ("rate_date", "reference-rate calculation with a rate dated after the manager's signature"),
            ("no_reason", "official increase form with no stated reason and a market-adjustment e-mail"),
            ("subsidy", "conflicting statements about allocating a renovation subsidy"),
            ("late_form", "form found in the mailbox demanding the higher rent from the first of the month"),
            ("index", "index-linked increase with a disputed base index"),
            ("two_forms", "two forms with different dates and amounts received a week apart"),
            ('cost_increase', 'a general cost-increase surcharge with no cost statement standing behind it'),
            ('renovation_share', 'a value-adding share asserted for works the tenant considers plain upkeep'),
            ('comparables', 'an increase justified by comparable rents that are never identified'),
            ('staggered', 'a staggered-rent clause invoked outside its own schedule'),
            ('charges_shift', 'ancillary charges folded into the net rent without a new calculation basis'),
            ('takeover', "an increase issued right after an ownership change, referring to the previous owner's basis"),
            ('reference_drop', 'an increase that ignores a published fall in the reference interest rate'),
            ('two_stage', 'two increases within one year, the second built on the first'),
            ('net_gross', 'a net and gross rent confusion that hides the real size of the increase'),
            ('missing_form', 'an increase announced by e-mail with the official form promised to follow'),
            ('sublet_surcharge', 'a surcharge for an approved sublet presented as a rent adjustment'),
            ('energy_pass', 'energy-efficiency works passed on in full with no upkeep share deducted'),
            ('service_charge', 'a service-charge rise presented as a net rent increase'),
            ('reference_lag', 'an increase applied before the reference rate it cites took effect'),
            ('area_recalc', 'a floor-area recalculation used to justify a higher rent'),
            ('furnished', 'a furnishing surcharge for items the tenant already owned'),
            ('portfolio', 'a portfolio-wide uplift with no property-specific basis'),
            ('arrears_offset', 'an increase justified by recovering earlier unbilled costs'),
            ('parking', 'a parking allocation withdrawn and rebilled as a rent adjustment'),
        ],
    },
}

AVAILABILITY_PROFILES = ["final_t1", "partial_auto", "partial_followup", "unreadable_followup", "unavailable", "final_t2"]
MOTIFS = ["possession_report", "content_quote", "third_party_relay", "promise_automatic", "denial_nonexistent",
          "conflict", "ambiguous_reference", "existence_only", "stale_then_correct"]
LANGS = ["en", "de"]


def _rng(*parts: Any) -> random.Random:
    seed = int(hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:16], 16)
    return random.Random(seed)


def sample_latent(domain: str, family: str, episode: int, split: str) -> dict[str, Any]:
    pack = PACKS[domain]
    rng = _rng("arena-v1", domain, family, episode, split)
    docs = [row[0] for row in pack["catalog"]]
    irrelevant = set(pack["irrelevant"])
    latent: dict[str, Any] = {"domain": domain, "family": family, "episode": episode, "split": split,
                              "language": rng.choice(LANGS), "style_seed": rng.randint(1, 10_000)}
    availability: dict[str, str] = {}
    for doc in docs:
        if doc in irrelevant:
            availability[doc] = "irrelevant"
        else:
            availability[doc] = rng.choices(AVAILABILITY_PROFILES, weights=[5, 3, 2, 2, 1, 2])[0]
    # the conditional requirement's trigger: activate in ~50% of episodes via the trigger document's final return
    cond = next(r for r in pack["requirements"] if r[4] is not None)
    latent["conditional_active"] = rng.random() < 0.5
    trigger_doc = cond[4]
    if availability[trigger_doc] == "unavailable":
        availability[trigger_doc] = "final_t1"          # a trigger document must be obtainable
    # a requirement with alternatives: the authenticated export may be the only obtainable route
    auth_doc = next(row[0] for row in pack["catalog"] if row[3])
    if rng.random() < 0.3:
        availability[auth_doc] = "final_t1"
    # never make every route of a critical requirement unavailable
    for rid, _desc, sets, critical, trig in pack["requirements"]:
        if trig is None and all(any(availability[d] == "unavailable" for d in option) for option in sets):
            availability[sets[0][0]] = "final_t1"
    latent["availability"] = availability
    motifs = rng.sample(MOTIFS, k=rng.randint(2, 4))
    # bind motifs to documents
    bound: list[dict[str, Any]] = []
    candidates = [d for d in docs if d not in irrelevant]
    for m in motifs:
        doc = rng.choice(candidates)
        if m == "denial_nonexistent":
            doc = next((d for d in candidates if availability[d] == "unavailable"), None)
            if doc is None:
                continue
        if m == "promise_automatic":
            doc = next((d for d in candidates if availability[d] in {"partial_auto", "final_t2"}), None)
            if doc is None:
                continue
        if m == "possession_report":
            availability[doc] = "final_t1" if availability[doc] not in {"unreadable_followup"} else availability[doc]
        if m == "stale_then_correct":
            availability[doc] = "partial_auto"
        bound.append({"motif": m, "document_id": doc})
    latent["motifs"] = bound
    latent["cond_requirement"] = cond[0]
    latent["trigger_doc"] = trigger_doc
    # intake attachments (drawn last so earlier draws are unchanged): documents whose FIRST return is
    # already in the intake packet — partial/unreadable versions create "possessed but insufficient/unreadable",
    # complete versions create "already received" at turn 0, so turn-0 states vary within a family.
    attachable = [d for d in candidates if availability[d] in {"final_t1", "partial_auto", "partial_followup", "unreadable_followup"} and d != trigger_doc]
    rng.shuffle(attachable)
    n_attach = rng.choices([0, 1, 2], weights=[3, 4, 3])[0]
    latent["intake_attached"] = sorted(attachable[:n_attach])
    return latent


def build_brief(latent: dict[str, Any]) -> dict[str, Any]:
    """Semantic paragraph brief for the writer; contains no evaluator labels beyond what the text must convey."""
    pack = PACKS[latent["domain"]]
    fam = next(f for f in pack["families"] if f[0] == latent["family"])
    catalog = {row[0]: {"role": row[1], "holder": row[2], "authenticated": row[3]} for row in pack["catalog"]}
    reqs = {r[0]: r for r in pack["requirements"]}
    motif_by_doc = {m["document_id"]: m["motif"] for m in latent["motifs"]}
    paragraphs: list[dict[str, Any]] = []
    # customer message
    paragraphs.append({"id": "src#p1", "kind": "customer", "must_convey": [f"first-person account of the situation: {fam[1]}", "at least one concrete date and one concrete observation"], "must_not": ["state that any document is attached"]})
    p = 2
    for doc, motif in motif_by_doc.items():
        role = catalog[doc]["role"]
        if motif == "possession_report":
            mc = [f"the customer states they HAVE FOUND / HOLD the document '{role}' at home and can send it", "do not quote its contents"]
        elif motif == "content_quote":
            mc = [f"the customer describes or quotes what the document '{role}' says (a date or an amount) from memory", "the customer does NOT say they are sending it"]
        elif motif == "third_party_relay":
            mc = [f"the customer relays what another party (e.g. the manager, contractor or bank) told them about '{role}' by phone", "second-hand only"]
        elif motif == "promise_automatic":
            mc = [f"the customer reports that the holder of '{role}' ({catalog[doc]['holder']}) will send it automatically without being asked, within days"]
        elif motif == "denial_nonexistent":
            mc = [f"the customer states that no '{role}' was ever produced / never existed"]
        elif motif == "conflict":
            mc = [f"two statements about '{role}' conflict: the customer's own recollection versus what another party claims"]
        elif motif == "ambiguous_reference":
            mc = [f"the customer refers to 'the letter' / 'the document' in a way that could mean '{role}' or another catalog document; do not resolve the ambiguity"]
        elif motif == "existence_only":
            mc = [f"the customer states that '{role}' exists somewhere (e.g. with the manager) without saying what it contains or that they hold it"]
        elif motif == "stale_then_correct":
            mc = [f"the customer mentions an older version of '{role}' whose figures were later corrected"]
        else:
            mc = [f"mention '{role}'"]
        paragraphs.append({"id": f"src#p{p}", "kind": "customer", "document_id": doc, "motif": motif, "must_convey": mc, "must_not": ["use the words 'attached' or 'enclosed'"]})
        p += 1
    paragraphs.append({"id": f"src#p{p}", "kind": "customer", "must_convey": ["what the customer wants checked now (the operational question)", "an explicit statement of what remains unclear to them"], "must_not": []})
    # governing instruction
    h = 1
    gov: list[dict[str, Any]] = []
    for rid, desc, sets, critical, trig in pack["requirements"]:
        routes = " OR ".join(" + ".join(catalog[d]["role"] for d in option) for option in sets)
        if trig is None:
            gov.append({"id": f"gov#h{h}", "kind": "instruction", "requirement_id": rid, "must_convey": [f"before the current decision, establish: {desc}", f"acceptable evidence: {routes}", "a party's description or recollection of a document does not establish its content; the document itself (or the authenticated export) is required"]})
        else:
            gov.append({"id": f"gov#h{h}", "kind": "instruction", "requirement_id": rid, "must_convey": [f"conditional: {desc}", f"this obligation becomes active ONLY if a returned '{catalog[trig]['role']}' reports the triggering circumstance; until then do not request '{catalog[sets[0][0]]['role']}'"]})
        h += 1
    gov.append({"id": f"gov#h{h}", "kind": "instruction", "must_convey": [f"the following are not required for this check: {', '.join(catalog[d]['role'] for d in pack['irrelevant'])}", "readiness means the listed facts are established from the required documents; it does not decide legal entitlement"]})
    # returns per document and scope
    returns: list[dict[str, Any]] = []
    for doc, av in latent["availability"].items():
        role = catalog[doc]["role"]
        related = [rid for rid, _d, sets, _c, _t in pack["requirements"] if any(doc in o for o in sets)]
        is_trigger = doc == latent["trigger_doc"]
        trig_note = (f"; the document MUST explicitly report the circumstance that triggers '{reqs[latent['cond_requirement']][1]}'" if is_trigger and latent["conditional_active"] else (f"; the document must NOT mention any circumstance related to '{reqs[latent['cond_requirement']][1]}'" if is_trigger else ""))
        if av == "irrelevant":
            returns.append({"id": f"ret-{doc}-irrelevant#p1", "document_id": doc, "scope": "irrelevant", "must_convey": [f"content of '{role}' that is genuinely unrelated to the facts under review"]})
        elif av in {"final_t1", "final_t2"}:
            returns.append({"id": f"ret-{doc}-final#p1", "document_id": doc, "scope": "final", "must_convey": [f"the complete '{role}' establishing the fact(s) for {related} with concrete values/dates{trig_note}"]})
        elif av == "partial_auto" or av == "partial_followup":
            motif = motif_by_doc.get(doc)
            if motif == "stale_then_correct":
                returns.append({"id": f"ret-{doc}-partial#p1", "document_id": doc, "scope": "partial_correcting", "must_convey": [f"an OLDER version of '{role}' with figures that are later corrected; it states that a corrected version follows"]})
            else:
                returns.append({"id": f"ret-{doc}-partial#p1", "document_id": doc, "scope": "partial", "must_convey": [f"an incomplete '{role}': it gives part of the information but explicitly lacks a required element (state which)", "it promises that the complete version follows" if av == "partial_auto" else "it does not promise anything further"]})
            returns.append({"id": f"ret-{doc}-final#p1", "document_id": doc, "scope": "final", "must_convey": [f"the complete '{role}' establishing the fact(s) for {related}{trig_note}"]})
        elif av == "unreadable_followup":
            returns.append({"id": f"ret-{doc}-partial#p1", "document_id": doc, "scope": "partial", "must_convey": [f"a cover note stating that the attached scan of '{role}' is illegible / pages missing, so its content cannot be read", "no substantive content"]})
            returns.append({"id": f"ret-{doc}-final#p1", "document_id": doc, "scope": "final", "must_convey": [f"a legible complete '{role}' establishing the fact(s) for {related}{trig_note}"]})
        elif av == "unavailable":
            returns.append({"id": f"ret-{doc}-unavailable#p1", "document_id": doc, "scope": "unavailable", "must_convey": [f"a written statement from {catalog[doc]['holder']} that no '{role}' exists / was ever issued"]})
    brief = {"contract": "casepath.arena-v1-brief/1.0.0", "language": latent["language"], "style_seed": latent["style_seed"],
             "scenario": fam[1], "domain": latent["domain"], "catalog": [{"document_id": d, **v} for d, v in catalog.items()],
             "paragraphs": paragraphs + gov + returns,
             "writer_rules": ["Write every paragraph as natural prose in the requested language (customer paragraphs in the customer's voice, instruction paragraphs as neutral handling guidance, return paragraphs as the document's own text or a cover note).",
                               "Vary sentence openings, register and length across paragraphs; never use meta-labels such as 'partial', 'final', 'hearsay' or the document IDs.",
                               "Never reveal whether a document will be sufficient; convey exactly the semantics in must_convey and nothing that contradicts must_not.",
                               "Return one JSON object mapping each paragraph id to its text."]}
    return brief


def assemble_case(latent: dict[str, Any], brief: dict[str, Any], texts: dict[str, str]) -> dict[str, Any]:
    pack = PACKS[latent["domain"]]
    dom, fam, ep, split = latent["domain"], latent["family"], latent["episode"], latent["split"]
    case_id = f"{dom}.{fam}.e{ep}"
    sid = f"src-{fam}-{ep}"; gid = f"gov-{fam}-{ep}"
    def para(pid: str) -> dict[str, str]:
        return {"id": pid.split("#")[1], "text": texts[pid]}
    src_paras = [para(p["id"]) for p in brief["paragraphs"] if p["id"].startswith("src#")]
    gov_paras = [para(p["id"]) for p in brief["paragraphs"] if p["id"].startswith("gov#")]
    sources = [{"id": sid, "paragraphs": src_paras}, {"id": gid, "paragraphs": gov_paras}]
    store: list[dict[str, Any]] = []
    intake_docs: dict[str, str] = {}
    table: list[dict[str, Any]] = []
    ret_ids: dict[tuple[str, str], str] = {}
    for p in brief["paragraphs"]:
        if not p["id"].startswith("ret-"):
            continue
        # opaque return identities: the scope and document must not leak through the source id
        rid = "ret-" + hashlib.sha256(f"{case_id}|{p['id']}".encode()).hexdigest()[:10]
        ret_ids[(p["document_id"], p["scope"])] = rid
        store.append({"id": rid, "paragraphs": [para(p["id"])]})
    for doc in latent.get("intake_attached", []):
        av = latent["availability"][doc]
        first_scope = "final" if av == "final_t1" else ("partial_correcting" if (doc, "partial_correcting") in ret_ids else "partial")
        rid = ret_ids[(doc, first_scope)]
        intake_docs[rid] = doc
        entry = next(x for x in store if x["id"] == rid)
        store.remove(entry)
        sources.append({"id": rid, "paragraphs": entry["paragraphs"], "provided_document_id": doc})
    for doc, av in latent["availability"].items():
        if av == "irrelevant":
            table.append({"document_id": doc, "earliest_turn_available": 1, "response_source_ids": [ret_ids[(doc, "irrelevant")]], "scope": "irrelevant"})
        elif av == "final_t1":
            table.append({"document_id": doc, "earliest_turn_available": 1, "response_source_ids": [ret_ids[(doc, "final")]], "scope": "final"})
        elif av == "final_t2":
            table.append({"document_id": doc, "earliest_turn_available": 2, "response_source_ids": [ret_ids[(doc, "final")]], "scope": "final"})
        elif av == "unavailable":
            table.append({"document_id": doc, "earliest_turn_available": 1, "response_source_ids": [ret_ids[(doc, "unavailable")]], "scope": "unavailable"})
        elif av in {"partial_auto", "partial_followup", "unreadable_followup"}:
            pscope = "partial_correcting" if (doc, "partial_correcting") in ret_ids else "partial"
            first = ret_ids[(doc, pscope)]; final = ret_ids[(doc, "final")]
            second = {"deliver_at_turn": 2, "source_ids": [final], "scope": "final"}
            second["automatic_after_partial" if av == "partial_auto" else "requires_follow_up_request_at_turn_1"] = True
            table.append({"document_id": doc, "earliest_turn_available": 1,
                          "if_first_requested_at_turn_0": [{"deliver_at_turn": 1, "source_ids": [first], "scope": pscope}, second],
                          "if_first_requested_at_turn_1": [{"deliver_at_turn": 2, "source_ids": [final], "scope": "final"}]})
    # promised/automatic deliveries without request: schedule via the environment's automatic list? E76 has no
    # unrequested automatic delivery; we model "automatic" promises as availability profiles instead.
    requirements = []
    gov_by_req = {p["requirement_id"]: p["id"] for p in brief["paragraphs"] if p.get("requirement_id")}
    need_paras = [p["id"] for p in brief["paragraphs"] if p["id"].startswith("src#")]
    for rid, desc, sets, critical, trig in pack["requirements"]:
        row: dict[str, Any] = {"requirement_id": rid, "decision_id": "current-check", "critical": True,
                               "condition": desc, "satisfying_document_sets": [list(o) for o in sets],
                               "exact_support": [{"source_ref": f"{gid}#{gov_by_req[rid].split('#')[1]}", "exact_sentence": texts[gov_by_req[rid]]}]}
        if trig is not None:
            final_ret = ret_ids.get((trig, "final"))
            if latent["conditional_active"] and final_ret:
                row["activation"] = {"active_if_any_observed": [final_ret]}
            else:
                row["critical"] = False   # never activates in this episode
        requirements.append(row)
    justification: dict[str, Any] = {}
    for doc in [row[0] for row in pack["catalog"]]:
        related = [rid for rid, _d, sets, _c, _t in pack["requirements"] if any(doc in o for o in sets)]
        observed = [f"{r}#p1" for (d, s), r in ret_ids.items() if d == doc]
        justification[doc] = {"need_origin": [f"{sid}#{p.split('#')[1]}" for p in need_paras] if related else [],
                              "handling_instruction": [f"{gid}#{gov_by_req[r].split('#')[1]}" for r in related] or [f"{gid}#h{len(gov_paras)}"],
                              "observed_return": observed}
    case = {"case_id": case_id, "domain": dom, "family": fam, "episode": ep, "split": split, "language": latent["language"],
            "title": brief["scenario"], "aware_at": "2025-03-03T09:00:00+01:00",
            "actor_initial": {"aware_at": "2025-03-03T09:00:00+01:00", "turn": 0, "sources": sources,
                              "document_catalog": [{"document_id": d, "role": v["role"]} for d, v in ((row[0], {"role": row[1]}) for row in pack["catalog"])],
                              "static_category_checklist": {"category": pack["static_category"], "document_ids": list(pack["static_checklist"]),
                                                            "rationale": "A usual intake list for this category; it ignores the trajectory-specific instructions and returns."}},
            "source_store": store, "intake_source_documents": intake_docs, "reference_requirements": requirements, "accepted_justification_refs": justification,
            "action_response_table": table, "latent_sha256": hashlib.sha256(json.dumps(latent, sort_keys=True).encode()).hexdigest()}
    return case


def episode_plan(split_spec: dict[str, Any]) -> list[dict[str, Any]]:
    """split_spec: {"dev": {"heating_defect": {"families": [...], "episodes": n}, ...}, "hidden": ..., "transfer": ...}"""
    out = []
    for split, domains in split_spec.items():
        for domain, spec in domains.items():
            for family in spec["families"]:
                for ep in range(1, spec["episodes"] + 1):
                    out.append(sample_latent(domain, family, ep, split))
    return out
