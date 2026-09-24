"""Deterministic, source-bound request drafts. No dispatch is available here."""

from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping

from .workspace_corpus import digest_value

CONTRACT = "casepath.workspace-request-draft/1.0.0"


def _source_quote(assessment: Mapping[str, Any], document: Mapping[str, Any]) -> str | None:
    flag = document.get("condition_flag")
    conditions = assessment["conditions"]
    if flag and conditions.get(flag, {}).get("quote"):
        return str(conditions[flag]["quote"])
    kind = str(document["document_type"])
    if kind == "proof_of_receipt":
        for entry in ("termination_received", "claim_received"):
            if conditions.get(entry, {}).get("quote"):
                return str(conditions[entry]["quote"])
    preferred = {
        "proof_of_receipt": ("arrived", "received", "mitgeteilt"),
        "notice_period_evidence": ("end of", "juni", "july", "juli"),
        "rent_increase_notice": ("increase form", "new form"),
        "defect_notification": ("verwaltung", "management"),
        "proof_of_notification": ("verwaltung", "management"),
    }.get(kind, ())
    for item in assessment["noticed"]:
        if any(term in item["text"].casefold() for term in preferred):
            return str(item["text"])
    return str(assessment["noticed"][0]["text"]) if assessment["noticed"] else None


def _article(document: Mapping[str, Any]) -> str | None:
    authority = document.get("authority")
    if not authority:
        return None
    article = str(authority["article"])
    if "-para1-" in str(authority.get("authority_id", "")):
        article += " Abs. 1"
    return article


def _condition_label(flag: str, language: str) -> str:
    labels = {
        "arrears": ("arrears", "Mietrückstand"),
        "retaliation_screen": ("retaliation concern", "missbräuchliche Kündigung"),
        "heating": ("heating problem", "Heizungsproblem"),
        "specialist_needed": ("technical cause", "technische Ursache"),
        "deposit_considered": ("rent deposit", "Mietzinshinterlegung"),
        "renovation": ("renovation reason", "Umbau als Begründung"),
        "family_home": ("family-home service", "Zustellung an beide Ehegatten"),
        "reference_rate": ("reference-rate reason", "Referenzzinssatz"),
        "health_effects": ("health effects", "gesundheitliche Auswirkungen"),
        "mold": ("mould", "Schimmel"),
    }
    pair = labels.get(flag, (flag.replace("_", " "), flag.replace("_", " ")))
    return pair[1] if language.startswith("de") else pair[0]


_GERMAN_DOCUMENTS = {
    "lease_contract": "Mietvertrag", "termination_notice": "Kündigungsschreiben",
    "proof_of_receipt": "Zustellnachweis", "notice_period_evidence": "Nachweis der Kündigungsfrist",
    "stated_reason": "angegebener Kündigungsgrund", "spouse_notice_copy": "Kopie der Kündigung an den Ehepartner",
    "payment_deadline_letter": "Zahlungsfristansetzung", "rent_ledger_payment_evidence": "Mietzinsabrechnung",
    "prior_rights_correspondence": "frühere Korrespondenz zu Mieterrechten",
    "housing_search_log": "Dokumentation der Wohnungssuche", "landlord_correspondence": "Korrespondenz mit der Vermieterschaft",
    "defect_notification": "Mängelanzeige", "proof_of_notification": "Nachweis der Mängelmeldung",
    "dated_photos": "datierte Fotos", "landlord_response_history": "Antworten der Verwaltung",
    "humidity_temperature_log": "Feuchtigkeits- und Temperaturprotokoll",
    "heating_service_report": "Heizungsservicebericht", "medical_confirmation": "ärztliche Bestätigung",
    "technical_inspection": "technische Untersuchung", "written_repair_deadline": "schriftliche Reparaturfrist",
    "caretaker_correspondence": "Korrespondenz mit dem Hauswart",
    "rent_increase_notice": "Mietzinserhöhungsanzeige", "current_rent_evidence": "Nachweis des aktuellen Mietzinses",
    "prior_rent_adjustment": "frühere Mietzinsanpassung", "stated_calculation": "angegebene Berechnung",
    "reference_rate_basis": "Grundlage des Referenzzinssatzes",
    "renovation_cost_breakdown": "Aufstellung der Umbaukosten",
}

_GERMAN_STEPS = {
    "lt_intake": "Aussteller, Zugang und Endtermin erfassen",
    "lt_deadline": "Frist für Anfechtung oder Erstreckung sichern",
    "lt_form": "Form und Zustellung prüfen", "lt_type": "Kündigungsart bestimmen",
    "lt_arrears": "Voraussetzungen bei Mietrückstand prüfen",
    "lt_family": "getrennte Zustellung an Ehegatten prüfen",
    "lt_abuse": "Kündigungsgrund und Treu und Glauben prüfen",
    "lt_extension": "Unterlagen zur Erstreckung prüfen",
    "lt_evidence": "Unterlagen zur Kündigungsart sammeln",
    "lt_resolution": "Anfechtung, Erstreckung oder Einigung vorbereiten",
    "lt_close": "Ergebnis der Kündigung festhalten",
    "dh_intake": "Mangel und betroffene Räume erfassen",
    "dh_safety": "unmittelbare Gesundheits- oder Sicherheitsgefahr abklären",
    "dh_scope": "Mangel zeitlich einordnen", "dh_notice": "Meldung an die Vermieterschaft belegen",
    "dh_cause": "Ursache bis zur Klärung offenhalten",
    "dh_evidence": "objektive Belege zum Mangel sammeln",
    "dh_response": "Antwort und Zugang der Vermieterschaft prüfen",
    "dh_specialist": "technische Untersuchung einholen",
    "dh_deposit": "Voraussetzungen der Mietzinshinterlegung prüfen",
    "dh_resolution": "Reparatur oder Weiterleitung festhalten",
    "dh_close": "Fall abschliessen oder übergeben",
    "ri_intake": "Erhöhung und Zugang erfassen",
    "ri_deadline": "Anfechtungsfrist sichern", "ri_form": "Form und Zeitpunkt prüfen",
    "ri_reason": "angegebenen Grund bestimmen",
    "ri_reference": "Berechnung zum Referenzzinssatz prüfen",
    "ri_renovation": "Umbaukosten prüfen",
    "ri_evidence": "fehlende Berechnungsgrundlagen sammeln",
    "ri_assessment": "belegte Fakten und offene Fragen trennen",
    "ri_resolution": "Anfechtung oder Einigung vorbereiten",
    "ri_close": "Ergebnis festhalten",
}

_OPEN_QUESTIONS = {
    "arrears": ("Were any rent payments overdue?", "Waren Mietzinszahlungen ausstehend?"),
    "retaliation_screen": ("Could the termination relate to an earlier request you made?", "Könnte die Kündigung mit einer früheren Forderung zusammenhängen?"),
    "heating": ("Is the heating affected?", "Ist die Heizung betroffen?"),
    "specialist_needed": ("Is a technical inspection needed?", "Wird eine technische Untersuchung benötigt?"),
    "deposit_considered": ("Are you considering a rent deposit?", "Wird eine Mietzinshinterlegung erwogen?"),
    "renovation": ("Does the form cite renovation costs?", "Werden Umbaukosten als Grund genannt?"),
    "family_home": ("Were both spouses served separately?", "Wurde beiden Ehegatten getrennt zugestellt?"),
    "reference_rate": ("Does the form cite the reference rate?", "Wird der Referenzzinssatz genannt?"),
}


def compile_draft_request(
    claim_id: str, assessment: Mapping[str, Any], *, edited_body: str | None = None,
) -> dict[str, Any]:
    if not isinstance(assessment, Mapping) or not isinstance(assessment.get("documents"), list):
        raise ValueError("accepted claim assessment is required")
    language = str(assessment["language"])
    german = language.startswith("de")
    steps = {step["node_id"]: step for step in assessment["steps"]}
    missing_page = any("page two is absent" in item["text"].casefold() for item in assessment["noticed"])
    requested, held, not_requested = [], [], []
    for document in assessment["documents"]:
        route = document["route_state"]
        flag = document.get("condition_flag")
        step = next((steps[node] for node in document["required_at_node_ids"] if node in steps), None)
        item = {
            "document_type": document["document_type"],
            "label": _GERMAN_DOCUMENTS.get(document["document_type"], document["label"]) if german else document["label"],
            "route_state": route,
            "step": (_GERMAN_STEPS.get(step["node_id"], step["label"]) if german else step["label"]) if step else None,
            "condition": _condition_label(flag, language) if flag else None,
            "condition_quote": assessment["conditions"].get(flag, {}).get("quote") if flag else None,
            "article": _article(document),
            "customer_quote": _source_quote(assessment, document),
        }
        if route == "needed_now":
            requested.append(item)
        elif route == "held_not_reviewed":
            held.append(item)
            if missing_page and document["document_type"] in {"termination_notice", "spouse_notice_copy"}:
                name = "spouse notice" if document["document_type"] == "spouse_notice_copy" else "termination notice"
                requested.append({**item, "label": f"Complete {name} (page two)", "route_state": "incomplete_copy"})
        elif route in {"not_needed", "held_behind_question"}:
            condition = _condition_label(flag, language) if flag else None
            reason = (
                f"{condition} is still a question" if route == "held_behind_question"
                else f"{condition} is inactive on this path"
            )
            if german:
                reason = (
                    f"{condition} ist noch ungeklärt" if route == "held_behind_question"
                    else f"{condition} ist auf diesem Pfad nicht aktiv"
                )
            not_requested.append({**item, "reason": reason})
    questions = []
    deadline = assessment.get("candidate_deadline")
    if deadline and deadline.get("question"):
        questions.append(str(deadline["question"]))
    if missing_page:
        questions.append("Can you send the complete second page of each notice?")
    for flag, condition in assessment["conditions"].items():
        if condition["verdict"] != "unresolved" or flag not in {
            row.get("condition_flag") for row in assessment["documents"]
        }:
            continue
        pair = _OPEN_QUESTIONS.get(flag)
        label = _condition_label(flag, language)
        question = pair[1 if german else 0] if pair else (f"Ist {label} betroffen?" if german else f"Does {label} apply?")
        if question not in questions:
            questions.append(question)
    specialist = assessment["conditions"].get("health_effects", {}).get("verdict") == "true"
    kind = "specialist_handoff" if specialist else "customer_request"
    if german:
        lines = ["# Entwurf für die Fachperson" if specialist else "# Entwurf der Kundenanfrage", "", "Entwurf, nicht gesendet", "", "## Benötigte Unterlagen"]
    else:
        lines = ["# Draft request", "", "Draft, not sent", "", "## Please send"]
    for item in requested:
        detail = f"{item['label']} — {item['step']}" if item["step"] else item["label"]
        if item["condition"]:
            detail += f"; {item['condition']}"
        if item["article"]:
            detail += f"; {item['article']}"
        if item["customer_quote"]:
            detail += f"; “{item['customer_quote']}”"
        lines.append(f"- {detail}")
    lines += ["", "## Schon vorhanden" if german else "## Already held"]
    for item in held:
        lines.append(f"- {item['label']}: {'vorhanden, noch nicht geprüft' if german else 'held, not reviewed'}")
    lines += ["", "## Offene Fragen" if german else "## Questions"]
    lines += [f"- {question}" for question in questions]
    lines += ["", "## Nicht angefordert" if german else "## Not requested"]
    for item in not_requested:
        lines.append(f"- {item['label']}: {item['reason']}")
    body = edited_body if edited_body is not None else "\n".join(lines) + "\n"
    if not isinstance(body, str) or not 1 <= len(body) <= 30_000:
        raise ValueError("draft body is invalid")
    material = {
        "contract": CONTRACT,
        "claim_id": claim_id,
        "kind": kind,
        "language": language,
        "source_assessment_sha256": assessment["assessment_sha256"],
        "requested": requested,
        "held": held,
        "not_requested": not_requested,
        "questions": questions,
        "body_markdown": body,
        "body_sha256": sha256(body.encode("utf-8")).hexdigest(),
        "edited_by_handler": edited_body is not None,
        "status": "draft_not_sent",
    }
    return {**material, "draft_sha256": digest_value(material)}
