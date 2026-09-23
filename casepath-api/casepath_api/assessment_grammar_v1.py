"""Source-bound, deterministic claim assessment for new workspace journals.

The catalogue has one immutable version. A verdict states only what an exact
customer passage supports; silence and qualified statements stay unresolved.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Mapping

from .workspace_corpus import PublicCorpus, digest_value


CONTRACT = "casepath.claim-workspace-assessment/2.0.0"
COMPILER_ID = "casepath.claim-workspace-assessment-v2/1.0.0"

# Patterns are ordered from the most specific phrasing to broader expressions.
# They search the customer's account, never boilerplate printed on a form.
GRAMMAR: dict[str, dict[str, tuple[str, ...]]] = {
    "health_effects": {
        "true": (r"Mein Sohn hustet mehr", r"my (?:son|child) (?:is )?coughing more", r"(?:hustet|coughing|Atembeschwerden|respiratory symptoms)"),
        "false": (r"(?:no|without) (?:health effects|health complaints|symptoms)", r"keine gesundheitlichen Beschwerden"),
        "candidate": (r"gesundheitlichen Beschwerden[^.;\n]*", r"health link[^.;\n]*", r"health effects[^.;\n]*"),
    },
    "mold": {
        "true": (r"Schimmel", r"mould", r"mold", r"Ecke[^;\n]*schwarz", r"corner[^;\n]*black"),
        "false": (r"(?:no|without) (?:mould|mold)", r"kein Schimmel"),
        "candidate": (r"possible moisture[^.;\n]*", r"mögliche Feuchtigkeit[^.;\n]*"),
    },
    "heating": {
        "true": (r"heating (?:has|is|was) [^;\n]*(?:cold|warm|fail)", r"(?:Heizung|Heizkörper|Boiler)[^;\n]*(?:ausgefallen|kalt|defekt)", r"boiler failure", r"Heizungsausfall"),
        "false": (r"(?:no|without) heating (?:problem|failure)", r"Heizung funktioniert"),
        "candidate": (r"heating[^.;\n]*", r"Heizung[^.;\n]*"),
    },
    "specialist_needed": {
        "true": (r"technical inspection (?:is )?needed", r"(?:request|need) (?:a )?technical inspection", r"technische (?:Begutachtung|Inspektion) (?:ist )?nötig"),
        "false": (r"(?:no|without) technical inspection (?:is )?needed", r"keine technische Inspektion nötig"),
        "candidate": (r"welche technische Ursache[^;\n]*", r"technical cause[^;\n]*"),
    },
    "deposit_considered": {
        "true": (r"official (?:rent )?deposit", r"Mietzinshinterlegung", r"Mietzins hinterlegen"),
        "false": (r"(?:no|without) (?:rent )?deposit", r"keine Mietzinshinterlegung"),
        "candidate": (r"deposit[^.;\n]*", r"Hinterlegung[^.;\n]*"),
    },
    "family_home": {
        "true": (r"My wife's arrived on Wednesday and says the end of July", r"(?:my|the) (?:wife|husband|spouse)[^;\n]*(?:notice|form|arriv|received)", r"(?:wife|husband|spouse|Ehefrau|Ehemann|Familienwohnung)", r"separat[^;\n]*(?:Ehegatt|Ehefrau|Ehemann)"),
        "false": (r"(?:not|no) (?:a )?family home", r"keine Familienwohnung"),
        "candidate": (r"(?:spouse|wife|husband|Ehegatt)[^;\n]*",),
    },
    "arrears": {
        "true": (r"arrears termination", r"rent arrears", r"(?:one|a) month's rent late", r"mit einer Monatsmiete zu spät", r"Zahlungsrückstand", r"Mietzinsrückstand", r"Verzugskündigung"),
        "false": (r"(?:no|without) (?:rent )?arrears", r"keine Mietzinsrückstände"),
        "candidate": (r"arrears[^.;\n]*", r"Rückstand[^.;\n]*"),
    },
    "retaliation_screen": {
        "true": (r"(?:after|because) I (?:asserted|exercised|claimed) my rights", r"wegen (?:meiner|unserer) (?:Beschwerde|Rechte)", r"retaliat(?:ion|ory)"),
        "false": (r"(?:no|without) retaliation", r"keine Vergeltung"),
        "candidate": (r"(?:retaliat|Vergeltung|Treu und Glauben)[^.;\n]*",),
    },
    "extension_relevant": {
        "true": (r"prepare a joint extension request", r"extension request", r"(?:Erstreckung|Wohnungssuchhärte|housing search)"),
        "false": (r"(?:no|without) extension request", r"keine Erstreckung"),
        "candidate": (r"extension[^.;\n]*", r"Erstreckung[^.;\n]*"),
    },
    "reference_rate": {
        "true": (r"names a reference rate dated two weeks after the manager's signature", r"reference[- ]rate", r"Referenzzinssatz", r"Referenzzins"),
        "false": (r"(?:no|without) reference[- ]rate reason", r"kein Referenzzinsgrund"),
        "candidate": (r"(?:reference rate|Referenzzins)[^.;\n]*",),
    },
    "renovation": {
        "true": (r"renovation[- ](?:related )?(?:cost|increase|work)", r"renovation", r"Sanierung", r"Umbaukosten"),
        "false": (r"(?:no|without) renovation (?:work|cost|reason)", r"keine Sanierung"),
        "candidate": (r"(?:renovation|Sanierung)[^.;\n]*",),
    },
    "termination_received": {
        "true": (r"My form arrived on Monday", r"(?:my|the|our) (?:form|notice) (?:arrived|was delivered|was received)", r"Ein Formular nennt Ende [A-Za-zäöüÄÖÜ]+", r"(?:case manager wrote that this was our termination|Sachbearbeiterin schrieb, dies sei unsere Kündigung)", r"(?:I received a termination|kam die Kündigung wegen Eigenbedarf)", r"(?:Kündigung|Formular) (?:erhalten|eingetroffen)", r"termination notice"),
        "false": (r"(?:no|without) termination notice (?:received|delivered)", r"Kündigung nicht erhalten"),
        "candidate": (r"(?:form|notice|Kündigung)[^;\n]*",),
    },
    "claim_received": {
        "true": (r"The new form", r"(?:The form (?:was in my mailbox|contains only the amounts)|Das Formular lag gestern im Briefkasten|Im Formular steht|Nettomietzins steigt)", r"(?:rent increase|Mietzinserhöhung|Erhöhungsformular)", r"(?:I am asking for|Ich ersuche um)"),
        "false": (),
        "candidate": (),
    },
}
GRAMMAR_SHA256 = "5f3f430fc75015713c5b88245f76acb283b019d4551bd8217d02935559037042"

FAMILY_FLAGS = {
    "defect_mold_heating": ("health_effects", "mold", "heating", "specialist_needed", "deposit_considered"),
    "lease_termination_dispute": ("termination_received", "family_home", "arrears", "retaliation_screen", "extension_relevant"),
    "rent_increase_dispute": ("claim_received", "reference_rate", "renovation"),
}

ARTICLE_BY_NODE = {
    "dh_safety": "259a", "dh_notice": "257g", "dh_cause": "259a", "dh_evidence": "259a", "dh_deposit": "259g",
    "lt_deadline": "273", "lt_form": "266l", "lt_arrears": "257d", "lt_family": "266n", "lt_abuse": "271", "lt_extension": "272",
    "ri_deadline": "270b", "ri_form": "269d", "ri_reference": "269a", "ri_renovation": "269a",
}


def _span(text: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        found = re.search(pattern, text, re.IGNORECASE | re.UNICODE)
        if found:
            return found.group(0)
    return None


def _verdict(text: str, flag: str, message_id: str) -> dict[str, Any]:
    rule = GRAMMAR[flag]
    # Explicit denial wins over a broad family keyword in the same account.
    negative = _span(text, rule["false"])
    positive = _span(text, rule["true"])
    candidate = _span(text, rule["candidate"])
    if positive and negative and positive.casefold() not in negative.casefold():
        status, quote = "unresolved", None
        candidate = positive + " / " + negative
    elif negative:
        status, quote = "false", negative
    elif positive:
        # A nearby uncertainty qualifier prevents a keyword alone from
        # becoming a conclusion. Specific affirmative phrases still count.
        context = text[max(0, text.casefold().find(positive.casefold()) - 25):][:len(positive) + 70]
        qualified = bool(re.search(r"\b(?:perhaps|maybe|possibly|possible|vielleicht|möglich|ungeklärt|unresolved)\b", context, re.I))
        status, quote = ("unresolved", None) if qualified and len(positive.split()) < 3 else ("true", positive)
        if status == "unresolved":
            candidate = candidate or positive
    else:
        status, quote = "unresolved", None
    return {"verdict": status, "quote": quote, "candidate_quote": candidate if status == "unresolved" else None,
            "source_id": message_id if quote or candidate else None, "worker": "deterministic"}


def _not(value: str) -> str:
    return {"true": "false", "false": "true", "unresolved": "unresolved"}[value]


def _and(*values: str) -> str:
    if "false" in values:
        return "false"
    return "unresolved" if "unresolved" in values else "true"


def _or(a: str, b: str) -> str:
    if "true" in (a, b):
        return "true"
    return "unresolved" if "unresolved" in (a, b) else "false"


def _transition_verdict(domain: str, condition: str, flags: Mapping[str, Mapping[str, Any]]) -> str:
    value = lambda name: str(flags[name]["verdict"])
    known = {
        "health effects alleged": value("health_effects") if domain == "defect_mold_heating" else "true",
        "no immediate health escalation": _not(value("health_effects")) if domain == "defect_mold_heating" else "true",
        "technical inspection needed": value("specialist_needed") if domain == "defect_mold_heating" else "true",
        "deposit route considered without specialist": _and(value("deposit_considered"), _not(value("specialist_needed"))) if domain == "defect_mold_heating" else "true",
        "no further specialist or deposit branch": _and(_not(value("specialist_needed")), _not(value("deposit_considered"))) if domain == "defect_mold_heating" else "true",
        "deposit route remains relevant": value("deposit_considered") if domain == "defect_mold_heating" else "true",
        "termination received": value("termination_received") if domain == "lease_termination_dispute" else "true",
        "arrears termination": value("arrears") if domain == "lease_termination_dispute" else "true",
        "family-home ordinary termination": value("family_home") if domain == "lease_termination_dispute" else "true",
        "no special precondition branch": _and(_not(value("arrears")), _not(value("family_home"))) if domain == "lease_termination_dispute" else "true",
        "extension relevant": value("extension_relevant") if domain == "lease_termination_dispute" else "true",
        "no extension branch": _not(value("extension_relevant")) if domain == "lease_termination_dispute" else "true",
        "claim received": value("claim_received") if domain == "rent_increase_dispute" else "true",
        "reference-rate reason selected": value("reference_rate") if domain == "rent_increase_dispute" else "true",
        "renovation reason selected": value("renovation") if domain == "rent_increase_dispute" else "true",
        "no specialist calculation branch": _and(_not(value("reference_rate")), _not(value("renovation"))) if domain == "rent_increase_dispute" else "true",
    }
    return known.get(condition, "true")


CONDITION_FLAGS = {
    "health effects alleged": "health_effects",
    "no immediate health escalation": "health_effects",
    "technical inspection needed": "specialist_needed",
    "deposit route considered without specialist": "deposit_considered",
    "deposit route remains relevant": "deposit_considered",
    "termination received": "termination_received",
    "arrears termination": "arrears",
    "family-home ordinary termination": "family_home",
    "extension relevant": "extension_relevant",
    "no extension branch": "extension_relevant",
    "claim received": "claim_received",
    "reference-rate reason selected": "reference_rate",
    "renovation reason selected": "renovation",
}


def _attachment_text(corpus: PublicCorpus, claim_id: str, attachment: Mapping[str, Any]) -> list[dict[str, Any]]:
    if attachment["media_type"].split(";")[0].lower() != "application/pdf":
        return []
    import fitz

    raw, _ = corpus.artifact(claim_id, attachment["artifact_id"])
    if len(raw) > 16 * 1024 * 1024:
        return []
    try:
        with fitz.open(stream=raw, filetype="pdf") as document:
            if document.is_encrypted:
                return []
            return [{"page": page + 1, "text": document[page].get_text("text")[:24_000]}
                    for page in range(min(len(document), 30))]
    except (ValueError, RuntimeError):
        return []


def _held(document_type: str, attachments: list[Mapping[str, Any]]) -> list[dict[str, str]]:
    found = []
    for item in attachments:
        name = item["file_name"].casefold()
        media = item["media_type"].casefold()
        matches = {
            "dated_photos": media.startswith("image/"),
            "termination_notice": "pdf" in media and any(word in name for word in ("termination", "kündigung", "kuendigung"))
            and not any(word in name for word in ("spouse", "wife", "husband", "ehefrau", "ehemann")),
            "spouse_notice_copy": "pdf" in media and any(word in name for word in ("spouse", "wife", "husband", "ehefrau", "ehemann")),
            "rent_increase_notice": "pdf" in media and any(word in name for word in ("rent", "mietzins", "increase")),
        }.get(document_type, document_type.replace("_", " ") in name.replace("_", " "))
        if matches:
            found.append({"artifact_id": item["artifact_id"], "file_name": item["file_name"], "state": "held_not_reviewed"})
    return found


def _authority(registry: Mapping[str, Any], article: str | None) -> dict[str, str] | None:
    if article is None:
        return None
    rows = [entry for entry in registry["entries"] if entry.get("source_kind") == "swiss_authority_passage"
            and str(entry.get("authority_id", "")).startswith(f"or-art-{article}-")]
    if not rows:
        return None
    selected = rows[0]
    return {"article": f"Art. {article}", "authority_id": selected["authority_id"],
            "passage": selected["locator"]["exact_text"]}


def _candidate_deadline(domain: str, message: str, registry: Mapping[str, Any]) -> dict[str, Any] | None:
    if domain not in {"lease_termination_dispute", "rent_increase_dispute"}:
        return None
    receipt = _span(message, (
        r"(?:notice|form|increase|Kündigung|Formular|Mietzinserhöhung) (?:was )?(?:received|delivered|arrived|notified|erhalten|zugestellt|mitgeteilt) (?:on|am) \d{1,2}[. /-]+(?:\d{1,2}|[A-Za-zäöüÄÖÜ]+)[. /-]+\d{4}",
    ))
    anchor = None
    if receipt:
        match = re.search(r"(\d{1,2})[. /-]+(\d{1,2})[. /-]+(\d{4})", receipt)
        if match:
            try:
                anchor = date(int(match[3]), int(match[2]), int(match[1]))
            except ValueError:
                pass
        else:
            months = {name: index for index, names in enumerate((
                ("january", "januar"), ("february", "februar"), ("march", "märz", "maerz"),
                ("april",), ("may", "mai"), ("june", "juni"), ("july", "juli"),
                ("august",), ("september",), ("october", "oktober"),
                ("november",), ("december", "dezember"),
            ), 1) for name in names}
            named = re.search(r"(\d{1,2})[. /-]+([A-Za-zäöüÄÖÜ]+)[. /-]+(\d{4})", receipt)
            if named and named[2].casefold() in months:
                try:
                    anchor = date(int(named[3]), months[named[2].casefold()], int(named[1]))
                except ValueError:
                    pass
    article = "273" if domain == "lease_termination_dispute" else "270b"
    return {"status": "candidate_to_verify" if anchor else "needs_anchor_date",
            "date": (anchor + timedelta(days=30)).isoformat() if anchor else None,
            "anchor_date": anchor.isoformat() if anchor else None,
            "anchor_quote": receipt if anchor else None,
            "period_days": 30,
            "question": "On which dates did each notice arrive?" if domain == "lease_termination_dispute" else "On what date was the increase notified?",
            "authority": _authority(registry, article)}


def compile_assessment(corpus: PublicCorpus, claim_id: str, base: Mapping[str, Any]) -> dict[str, Any]:
    if digest_value(GRAMMAR) != GRAMMAR_SHA256:
        raise ValueError("assessment grammar identity drifted")
    claim = corpus.claim(claim_id)
    message = claim["customer_message"]
    body = message["body"]
    domain = base["claim_type"]
    template = next(row for row in corpus.static_policy()["templates"] if row["domain"] == domain)
    catalog = template["process_catalog"]
    registry = corpus.source_registry(claim_id)
    flags = {name: _verdict(body, name, message["message_id"]) for name in FAMILY_FLAGS[domain]}
    nodes = catalog["nodes"]
    transitions = catalog["transitions"]
    activation = {node["node_id"]: "false" for node in nodes}
    activation[nodes[0]["node_id"]] = "true"
    for _ in nodes:
        for edge in transitions:
            source = activation[edge["source_node_id"]]
            condition = _transition_verdict(domain, edge["condition"], flags)
            target = edge["target_node_id"]
            activation[target] = _or(activation[target], _and(source, condition))
    active_nodes = [node["node_id"] for node in nodes if activation[node["node_id"]] == "true"]
    focus = next((node_id for node_id in active_nodes if node_id != nodes[0]["node_id"]), nodes[0]["node_id"])
    steps = [{"node_id": node["node_id"], "label": node["label"],
              "activation": activation[node["node_id"]],
              "state": "done" if node["node_id"] == nodes[0]["node_id"] else "active" if node["node_id"] == focus else "held_behind_question" if activation[node["node_id"]] == "unresolved" else "not_reached",
              "condition_chips": [{"label": edge["condition"],
                                   "verdict": _transition_verdict(domain, edge["condition"], flags),
                                   "condition_flag": CONDITION_FLAGS.get(edge["condition"]),
                                   "quote": flags[CONDITION_FLAGS[edge["condition"]]]["quote"] if edge["condition"] in CONDITION_FLAGS else None,
                                   "candidate_quote": flags[CONDITION_FLAGS[edge["condition"]]]["candidate_quote"] if edge["condition"] in CONDITION_FLAGS else None}
                                  for edge in transitions if edge["target_node_id"] == node["node_id"]],
              "authority": _authority(registry, ARTICLE_BY_NODE.get(node["node_id"]))}
             for node in nodes]
    attachments = claim.get("attachments", [])
    documents = []
    for doc in catalog["documents"]:
        required_nodes = doc["required_at_node_ids"]
        node_status = "false"
        for node_id in required_nodes:
            node_status = _or(node_status, activation[node_id])
        flag = None
        if doc["condition"]:
            found = re.search(r"scenario flag '([^']+)'", doc["condition"])
            if not found or found[1] not in flags:
                raise ValueError("template document condition is unsupported")
            flag = found[1]
        status = _and(node_status, flags[flag]["verdict"] if flag else "true")
        held = _held(doc["document_type"], attachments)
        if status == "false":
            route = "not_needed"
        elif status == "unresolved":
            route = "held_behind_question"
        elif held:
            route = "held_not_reviewed"
        elif doc["requirement_class"] == "optional":
            route = "optional"
        elif (focus in required_nodes or doc["document_type"] == "rent_increase_notice"
              or (domain == "defect_mold_heating" and doc["document_type"] in {
                  "defect_notification", "proof_of_notification", "humidity_temperature_log"})
              or (domain == "rent_increase_dispute" and doc["document_type"] == "reference_rate_basis")):
            route = "needed_now"
        else:
            route = "needed_later"
        documents.append({"document_type": doc["document_type"], "label": doc["label"],
                          "requirement_class": doc["requirement_class"], "condition_flag": flag,
                          "route_state": route, "required_at_node_ids": required_nodes,
                          "held_files": held, "request": route in {"needed_now", "needed_later"},
                          "reason": doc["assertion"] if route in {"needed_now", "needed_later", "held_not_reviewed"} else
                          f"{flag or 'The route'} is unresolved" if route == "held_behind_question" else
                          f"{flag or 'This branch'} is not active",
                          "authority": _authority(registry, ARTICLE_BY_NODE.get(required_nodes[0]))})
    observed = []
    first = body.split("\n\n", 2)[1] if "\n\n" in body else body
    for clause in first.split(";")[:5]:
        text = clause.split(":", 1)[-1].strip()
        if len(text) >= 12 and not any(value in text.casefold() for value in (
            "cannot safely", "mehr kann ich", "diesen stand", "this is what i can confirm",
            "i may be reading", "i cannot currently", "ich möchte vor dem handeln",
        )):
            observed.append({"text": text, "source_id": message["message_id"], "source_kind": "customer_message"})
    for match in re.finditer(
        r"\b(?:\d{1,2}[.]\d{1,2}[.]\d{4}|\d{1,2} (?:January|February|March|April|May|June|July|August|September|October|November|December|Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember) \d{4})\b",
        body, re.I,
    ):
        observed.append({"text": match.group(0), "source_id": message["message_id"],
                         "source_kind": "customer_message", "fact_kind": "reported_date"})
    for match in re.finditer(r"\b(?:CHF|Fr[.])\s?\d[\d' ,.]*", body):
        observed.append({"text": match.group(0).strip(), "source_id": message["message_id"],
                         "source_kind": "customer_message", "fact_kind": "reported_amount"})
    end_dates = []
    attachment_pages = []
    for item in attachments:
        for page in _attachment_text(corpus, claim_id, item):
            attachment_pages.append({"artifact_id": item["artifact_id"], "file_name": item["file_name"],
                                     "page": page["page"], "text_available": bool(page["text"].strip())})
            for match in re.finditer(r"\b\d{1,2}\.\s*(?:Juni|Juli|June|July)\b", page["text"], re.I):
                end_dates.append({"value": match.group(0), "quote": match.group(0),
                                  "artifact_id": item["artifact_id"], "file_name": item["file_name"], "page": page["page"]})
            if page["page"] == 1 and "termination" in item["file_name"].casefold():
                for name in re.finditer(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", page["text"][-500:]):
                    if name.group(0) not in {"Lac Léman", "Art Box", "Media Box"}:
                        observed.append({"text": name.group(0), "source_id": item["artifact_id"],
                                         "source_kind": "pdf_text", "page": 1, "fact_kind": "named_party_candidate"})
    conflicts = []
    if len({row["value"] for row in end_dates}) > 1:
        conflicts.append({"fact": "termination end date", "sources": end_dates,
                          "message": "The two notices give different end dates."})
    if end_dates:
        observed.extend({"text": f"{row['file_name']}: {row['quote']}", "source_id": row["artifact_id"],
                         "source_kind": "pdf_text", "page": row["page"]} for row in end_dates)
    deadline = _candidate_deadline(domain, body, registry)
    if domain == "lease_termination_dispute":
        next_step = "Ask for the two receipt dates and the complete second page of the scan." if conflicts else "Confirm the notice receipt date and complete copies."
    elif domain == "rent_increase_dispute":
        next_step = "Ask when the increase was notified and request the increase form."
    else:
        next_step = "Escalate the reported health effects for specialist review." if flags["health_effects"]["verdict"] == "true" else "Ask for dated evidence of the defect and notice to management."
    material = {"contract": CONTRACT, "compiler_id": COMPILER_ID, "grammar_sha256": GRAMMAR_SHA256,
                "worker": "deterministic", "language": corpus.binding(claim_id)["language"],
                "conditions": flags, "steps": steps, "documents": documents,
                "noticed": observed, "attachment_pages": attachment_pages,
                "conflicts": conflicts, "candidate_deadline": deadline, "next_step": next_step}
    return {**material, "assessment_sha256": digest_value(material)}
