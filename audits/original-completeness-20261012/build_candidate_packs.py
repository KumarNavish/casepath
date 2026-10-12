#!/usr/bin/env python3
"""Author the nine explicitly fictional supplemental candidate packets.

These are new synthetic fixture sources, not facts about the original corpus,
real communications, expert commissions, accepted events or model outputs.
Original IDs/bytes and baseline audit remain immutable and separately bound.
Fresh independent legal review is required before final designation.
"""
import base64
import hashlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent
PACKS = OUT / "candidate-packs"
ORIGINAL_MANIFEST_SHA = "7c885d3fd112dfc7314719d661fa73449f72b7bdf5b83159da9fa3e0b9a1b7eb"
BASE = "ae0ec12de331898280bd9000fb6548c848ce48b1"
AUTHOR_DATE = "2026-10-12"

DEFECTS = [
    {"number": 33, "tenant": "Riley Foster", "address": "Synthetic Rosenweg 33, 8008 Zurich", "net_rent": 1800,
     "notice_dates": ["2025-02-01", "2025-02-08", "2025-02-17"], "measured_temperature": "15.8"},
    {"number": 48, "tenant": "Nina Steiner", "address": "Synthetic Rosenweg 48, 8008 Zurich", "net_rent": 1650,
     "notice_dates": ["2025-01-21", "2025-01-24", "2025-01-28"], "measured_temperature": "16.1"},
    {"number": 88, "tenant": "Nina Frei", "address": "Synthetic Rosenweg 88, 8008 Zurich", "net_rent": 1920,
     "notice_dates": ["2025-01-17", "2025-01-24", "2025-02-02"], "measured_temperature": "15.9"},
]
TERMINATIONS = [
    {"number": 9, "tenant": "Taylor Miller", "manager": "Nova Régie SA", "address": "Seefeldstrasse 28, 8008 Zurich", "receipt": "2026-05-08T10:30:00+02:00", "early_awareness": "2026-05-04"},
    {"number": 38, "tenant": "Simon Steiner", "manager": "Limmat Verwaltungs GmbH", "address": "Zollikerstrasse 67, 8008 Zurich", "receipt": "2026-05-04T11:00:00+02:00", "early_awareness": "2026-04-30"},
    {"number": 49, "tenant": "Lea Meier", "manager": "Riva Hausverwaltung GmbH", "address": "Zollikerstrasse 58, 8008 Zurich", "receipt": "2026-05-08T10:00:00+02:00", "early_awareness": "2026-05-04"},
]
INCREASES = [
    {"number": 29, "tenant": "Noah Frei", "manager": "Domus Amministrazioni SA", "address": "Bergstrasse 27, 8008 Zurich", "receipt": "2025-11-17T17:15:00+01:00", "email_date": "2025-11-20"},
    {"number": 58, "tenant": "Elin Ziegler", "manager": "Verde Gestion SA", "address": "Seefeldstrasse 67, 8008 Zurich", "receipt": "2025-11-18T16:20:00+01:00", "email_date": "2025-11-21"},
    {"number": 81, "tenant": "Drew Shaw", "manager": "Nova Régie SA", "address": "Zollikerstrasse 11, 8008 Zurich", "receipt": "2025-11-22T18:00:00+01:00", "email_date": "2025-11-25"},
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def source(record, sequence, role, name, dated, text):
    cid = record["claim_id"]
    asof = (datetime.fromisoformat(record["received_at"]) + timedelta(days=1)).date().isoformat()
    banner = (
        "SYNTHETIC SUPPLEMENT — FICTIONAL DEMONSTRATION SOURCE\n"
        "Authored for a synthetic CasePath candidate on 2026-10-12.\n"
        "No real communication was sent, no real expert was commissioned, and no production event occurred.\n"
        "Historical dates below are fictional scenario dates; this is newly authored evidence, not an original intake fact.\n"
        f"Original claim ID: {cid}\nOriginal corpus manifest SHA256: {ORIGINAL_MANIFEST_SHA}\n"
        f"Fictional source date: {dated}\nFictional review as-of: {asof}\n"
        "Fixture author: independent audit worker /root/original_completeness_audit\n\n"
    )
    body = banner + text.rstrip() + "\n"
    data = body.encode("utf-8")
    directory = PACKS / cid
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{sequence:02}-{name}.txt"
    path.write_bytes(data)
    return {"artifact_id": f"audit_supp_{cid}_{sequence:02}", "role": role,
            "file_name": path.name, "media_type": "text/plain; charset=utf-8",
            "path": str(path.relative_to(OUT)), "sha256": sha(data), "size_bytes": len(data),
            "content_base64": base64.b64encode(data).decode(), "dated": dated,
            "provenance": "new_operator_authored_synthetic_source; no_original_source_or_real_action",
            "received": "present_in_supplemental_candidate_profile_only; not_admitted_to_original_or_production_journal"}


def cited(s, text, fact):
    data = (OUT / s["path"]).read_bytes()
    body = data.decode()
    start = body.index(text)
    return {"fact": fact, "source_artifact_id": s["artifact_id"], "source_sha256": s["sha256"],
            "source_path": s["path"], "quote": text, "start": start, "end": start+len(text),
            "offset_unit": "Unicode code points, zero-based, exclusive end", "state": "supported_in_explicitly_synthetic_supplement"}


def originals(record):
    return {"claim_id": record["claim_id"], "original_manifest_file_sha256": ORIGINAL_MANIFEST_SHA,
            "original_source_manifest_file_sha256": "638630886a1d291dfe9009839eb0519130e56700bb4d454277ce2e45c6044f4c",
            "original_binding_sha256": record["binding_sha256"],
            "original_claim": record["claim_receipt"], "original_registry": record["registry_receipt"],
            "original_observable_sources": [{k: a[k] for k in ("artifact_id", "path", "file_name", "media_type", "sha256", "size_bytes")} for a in record["artifacts"]]}


def finish(record, new_sources, path, laws, checklist, contradictions, limits, documents):
    asof = (datetime.fromisoformat(record["received_at"]) + timedelta(days=1)).date().isoformat()
    packet = {"contract": "casepath.synthetic-audit-candidate-supplement/1.0.0",
              "status": "candidate_for_fresh_independent_legal_review_not_final_designation",
              "profile_id": "synthetic-original150-plus-audit-nine-candidates-v1",
              "domain": record["domain"], "original_identity": originals(record),
              "authored_on": AUTHOR_DATE, "fictional_as_of": asof,
              "new_sources": new_sources, "active_path": path,
              "relevant_CO_articles": laws, "active_fact_checklist": checklist,
              "active_document_checklist": documents,
              "original_uncertainty_resolution": contradictions,
              "remaining_limits_outside_active_path": limits,
              "handling_boundary": "Assess entitlement/notice objection and prepare permissible next handling. No sent notice, filed challenge, paid/deposited rent, commissioned real report, accepted event, court decision or provider/model call is asserted.",
              "baseline_unchanged": True, "fresh_legal_review_required": True}
    path_out = PACKS / record["claim_id"] / "candidate.json"
    save(path_out, packet)
    return {"claim_id": record["claim_id"], "domain": record["domain"], "candidate_path": str(path_out.relative_to(OUT)),
            "candidate_sha256": sha(path_out.read_bytes()), "active_path": path,
            "original_binding_sha256": record["binding_sha256"], "fictional_as_of": asof,
            "new_source_count": len(new_sources), "status": packet["status"]}


def defect(record, c):
    asof = (datetime.fromisoformat(record["received_at"]) + timedelta(days=1)).date().isoformat()
    first = c["notice_dates"][0]
    tenancy = f"I, {c['tenant']}, am the tenant under an indefinite ordinary residential lease for {c['address']}, canton Zurich. The landlord in this fictional supplement is Synthetische Wohnraum AG. Current monthly net rent is CHF{c['net_rent']}; the landlord maintains the fixed central heating and circulation pump. The lease requires usable heated living rooms in winter."
    relief = "My active request is removal of the continuing heating defect and assessment of proportional rent-reduction eligibility from the landlord's first knowledge until remedy. I report no incurred monetary loss, no health-compensation claim, no self-help expense and no deposit/withholding request. The repair is not complete; no reduction percentage or award has been agreed."
    customer = source(record, 1, "synthetic_customer_clarification_and_relevant_tenancy_terms", "customer-and-tenancy-clarification", asof, tenancy + "\n\n" + relief)
    measurement = f"On {asof} at07:30, a calibrated digital instrument (fictional calibration check2024-12-15, uncertainty±0.2C) measured the living room at{c['measured_temperature']}C after overnight normal operation. Main living rooms stayed15.5–16.3C in the seven-day logger record. Resets restore heat briefly; the pump cuts out repeatedly. The fixed circulation pump has an internal bearing/control failure; it is part of landlord-maintained equipment, outside ordinary small tenant maintenance. Normal ventilation and unobstructed radiators were observed; no tenant alteration or misuse explains the failure."
    persists = "The defect persists at this report's as-of time; no lasting pump repair or replacement has been completed. Heating is inadequate for the contracted winter residential use of the principal living rooms. The proposed remedy is a landlord-arranged pump repair/replacement, with temporary heat while pending. This fictional service finding makes no legal decision, awards no compensation and claims no real commissioned inspection."
    technical = source(record, 2, "synthetic_technical_observation", "heating-service-observation", asof, "Fictional service author: Mira Keller, synthetic building-heating technician.\nProperty: " + c["address"] + "\n\n" + measurement + "\n\n" + persists)
    calls = f"Our fictional call log records {c['tenant']}'s three heating-failure reports on {', '.join(c['notice_dates'])}. Each report identified the same rented flat and recurrent stoppage of the fixed heating. We received the first report on{first}; this is the landlord's first documented knowledge of the defect."
    ack = "We confirm the tenant was using the heating normally and did not cause this pump failure. Repeated resets did not remove the continuing defect. We acknowledge the dated service observation and remain responsible for arranging pump repair; no lasting repair has yet occurred as of this acknowledgment."
    landlord = source(record, 3, "synthetic_landlord_acknowledgment", "landlord-knowledge-and-repair-status", asof, "Fictional speaker: Synthetische Wohnraum AG property manager.\nProperty: " + c["address"] + "\n\n" + calls + "\n\n" + ack)
    facts = [cited(customer, tenancy, "Residential tenancy, relevant contractual use, rent and landlord maintenance"),
             cited(customer, relief, "Defined actual relief; no deposit/damages/self-help route asserted"),
             cited(technical, measurement, "Reliable objective severity, recurrent defect and non-tenant landlord-maintained cause"),
             cited(technical, persists, "Continuing contractual-use impairment and unfinished repair"),
             cited(landlord, calls, "Exact landlord knowledge date and three notice records"),
             cited(landlord, ack, "Landlord acknowledges responsibility and persistence")]
    return finish(record, [customer, technical, landlord], "defect_removal_and_rent_reduction_eligibility", ["257g", "259a", "259d"], facts,
                  ["Original approximate/unreliable temperature is preserved; new calibrated observations supply a separate measurement.", "Original unknown service cause is resolved only within the new explicitly fictional service source.", "Original three calls are preserved and dated in the new fictional landlord log; original first-awareness text is not used as a legal receipt proxy.", "Any original unknown onset is distinguished from the newly sourced landlord-knowledge date."],
                  ["No precise reduction percentage, money award, successful filing, damage entitlement, tenant termination or official deposit is established or included in the active checklist.", "Defect continues as of the historical fixture review date; future repair completion and final reduction period remain open without blocking current removal/reduction-eligibility assessment."],
                  [{"requirement": "Relevant tenancy/use/rent basis", "source_artifact_ids": [customer["artifact_id"]], "status": "received_and_source_supported"},
                   {"requirement": "Reliable current impairment/cause record", "source_artifact_ids": [technical["artifact_id"]], "status": "received_and_source_supported"},
                   {"requirement": "Landlord notice/knowledge and persistence", "source_artifact_ids": [landlord["artifact_id"]], "status": "received_and_source_supported"}])


def termination(record, c):
    asof = (datetime.fromisoformat(record["received_at"]) + timedelta(days=1)).date().isoformat()
    original = record["artifacts"][1]
    receipt_day = datetime.fromisoformat(c["receipt"]).date()
    precautionary = (receipt_day + timedelta(days=30)).isoformat()
    account = f"I, {c['tenant']}, rent the dwelling at{c['address']} under an indefinite residential lease in canton Zurich. {c['manager']} is the authorized landlord's managing agent for this flat. I live alone, am unmarried and have no registered partner; the rented dwelling is not a family home."
    delivered = f"I first received the actual termination email and its sole attached PDF on{c['receipt']}. The attachment is exactly {original['file_name']} with SHA256 {original['sha256']}. My earlier awareness entry {c['early_awareness']} concerned the developing dispute, not receipt of the termination; I preserve that distinction. The sole PDF has one physical page and is the full attachment, not a cropped scan."
    scope = "My active request is an assessment of the received landlord notice's approved-form/nullity defect and preparation of a protective objection. I do not request a hardship extension, an own-use/motive decision or a court outcome. No communication has been sent and no challenge has been filed by this candidate packet."
    customer = source(record, 1, "synthetic_customer_packet_and_receipt_clarification", "sole-packet-and-tenant-clarification", asof, account + "\n\n" + delivered + "\n\n" + scope)
    authority = f"Fictional issuance archive of {c['manager']}: we were authorized to issue landlord communications for{c['address']}. On{c['receipt']} we transmitted the sole plain termination PDF identified above to{c['tenant']}'s current email account, and the email delivery/open record confirms receipt at that time."
    sole = "The original transmitted PDF had the blank signature line visible in the received file; no handwritten or qualified electronic signature was applied. It was a plain letter, not a canton-approved termination form. No other attachment, approved form, separate notice, post to the old or current address, portal notice, replacement or correction was issued up to the fictional review as-of date. This archive confirmation records the fictional factual packet only; it does not assert a legal decision."
    archive = source(record, 2, "synthetic_landlord_issuance_archive", "issuer-authority-and-complete-channel-archive", asof, authority + "\n\n" + sole)
    facts = [cited(customer, account, "Residential landlord tenancy and conditional family-home applicability"),
             cited(customer, delivered, "Exact formal receipt and unchanged complete original plain-PDF binding"),
             cited(customer, scope, "Bounded notice objection; no actual filing/action/outcome"),
             cited(archive, authority, "Authorized landlord issuer and corroborated delivery date"),
             cited(archive, sole, "Sole full notification packet, plain form, blank signature and no unknown later channel")]
    return finish(record, [customer, archive], "received_landlord_notice_form_nullity_assessment", ["266l", "266o", "273"], facts,
                  ["Original uncertainty about old-address post is resolved only by the new fictional complete-channel archive.", "Earlier original awareness date is preserved separately from actual formal delivery.", "Original next-contractual-date wording remains unchanged and supplies no definite end date; this does not cure the received letter's independent approved-form failure."],
                  [f"Raw calendar arithmetic only: receipt date+30days={precautionary}; NOT a verified273 filing deadline or expiry. The active path is nullity assessment, not filing. Weekend/public-holiday rollover and applicable procedural rules require separate official-source verification before any deadline conclusion. Conservative handling target: prepare/review now at the fictional as-of date; no filing is asserted.", "Assessing formal nullity does not establish a hardship extension, landlord motive or any later hypothetical termination."],
                  [{"requirement": "Actual complete received termination document", "original_artifact_ids": [original["artifact_id"]], "status": "unchanged_original_plain_one_page_PDF_received"},
                   {"requirement": "Tenancy/issuer/sole-packet/service facts", "source_artifact_ids": [customer["artifact_id"], archive["artifact_id"]], "status": "received_and_source_supported"}])


def increase(record, c):
    asof = (datetime.fromisoformat(record["received_at"]) + timedelta(days=1)).date().isoformat()
    original = record["artifacts"][1]
    receipt_day = datetime.fromisoformat(c["receipt"]).date()
    precautionary = (receipt_day + timedelta(days=30)).isoformat()
    tenancy = f"I, {c['tenant']}, rent the dwelling at{c['address']} under an indefinite ordinary residential lease in canton Zurich. The rent is not indexed or stepped, and there is no Article269c agreed increase. Current binding net rent is CHF1850 plus heating/warm-water advanceCHF180 and water/other advanceCHF60, grossCHF2090. The next ordinary lease termination date is31March2026 with three months' notice."
    packet = f"The landlord's managing agent {c['manager']} notified this proposed increase on{c['receipt']}. The sole contemporaneous attachment was {original['file_name']}, SHA256 {original['sha256']}: all three pages1/3,2/3,3/3, new netCHF1975 from1April2026 and unchanged advances, grossCHF2215. No contemporaneous accompanying reason letter, email reason, calculation sheet, or earlier advance reason notification was issued or received. The printed reason field was blank; its standard separate-letter label did not correspond to an attached letter."
    request = "My active request is assessment of the original notice's missing-reasons/nullity ground and preparation of a protective objection. I do not seek a finding of excessive rent, a reference-rate calculation or a cost allocation decision. The original unknown date/basis is clarified by this new fictional packet confirmation; no original bytes are rewritten and no challenge or communication has actually been filed/sent."
    customer = source(record, 1, "synthetic_customer_and_full_notification_packet_record", "ordinary-tenancy-and-original-notification-packet", asof, tenancy + "\n\n" + packet + "\n\n" + request)
    email = f"Fictional email archive: From{c['manager']} to{c['tenant']}; Date{c['email_date']} at10:00+01:00; Subject: Reply to your question about the rent increase. Message text: 'The rent is being adjusted to the market.' No calculation or other attachment accompanied this reply. This reply was sent after the tenant asked about the already received notice; it did not accompany the original communication."
    confirm = "The fictional managing agent confirms it was authorized to notify the increase for this dwelling, that the complete original notification packet contained only the three-page form, and that no substantive reason was communicated at original notification. The later reply is retained as adverse/contextual evidence rather than silently treated as an original reason. The form's mechanically reproduced signature is not relied on as a defect."
    reply = source(record, 2, "synthetic_later_email_and_landlord_packet_confirmation", "later-email-and-original-absence-of-reasons", c["email_date"], email + "\n\n" + confirm)
    facts = [cited(customer, tenancy, "Ordinary residential rent, actual binding amounts and absence of stepped-rent exception"),
             cited(customer, packet, "Exact notification date and complete unchanged three-page packet lacking substantive reasons"),
             cited(customer, request, "Defined original notice-nullity assessment rather than substantive excessive-rent adjudication"),
             cited(reply, email, "Actual text and chronology of later reported email, with no attachment"),
             cited(reply, confirm, "Authorized issuer confirms original no-reason packet; mechanical signature not rejected")]
    return finish(record, [customer, reply], "original_increase_missing_reasons_nullity_assessment", ["269d", "270b"], facts,
                  ["Original full3page form remains unchanged; new packet confirmation resolves whether any separate reason accompanied it.", "Original later-email uncertainty is resolved by newly supplied fictional dated email text and source distinction.", "Original unknown prior binding rent is independently clarified within the fictional ordinary tenancy statement, matching the original form's old amounts.", "November2025 dates fall after269d(4)/(5)'s1Oct2025 effective date; mechanically reproduced signature is not asserted invalid; the ordinary lease is not269c stepped rent."],
                  [f"Raw calendar arithmetic only: notification date+30days={precautionary}; NOT a verified270b filing deadline or expiry. No actual filing is asserted; nullity assessment is the active path. Weekend/public-holiday rollover and procedural rules require separate official-source verification before a deadline conclusion. Conservative handling target: prepare/review now at the fictional as-of date.", "No excessive-return, market-rent, reference-rate or renovation-cost merits finding is made; these are outside the clarified active nullity request.", "Later email cannot be assumed part of original notification; legal significance remains for fresh independent reviewer to assess."],
                  [{"requirement": "Actual complete original form including reason field", "original_artifact_ids": [original["artifact_id"]], "status": "unchanged_original_three_page_PDF_received"},
                   {"requirement": "Notification/ordinary tenancy/original reasons packet", "source_artifact_ids": [customer["artifact_id"], reply["artifact_id"]], "status": "received_and_source_supported"},
                   {"requirement": "Later email as separately dated contextual source", "source_artifact_ids": [reply["artifact_id"]], "status": "received_and_source_supported"}])


def main():
    records = json.loads((OUT / "source_receipts.json").read_text())
    PACKS.mkdir(exist_ok=True)
    candidates = []
    for c in DEFECTS:
        candidates.append(defect(records[c["number"]-1], c))
    for c in TERMINATIONS:
        assert c["address"].split(",")[0] in records[c["number"]-1]["artifacts"][1]["pages"][0]["text"], "Original PDF property identity mismatch"
        candidates.append(termination(records[c["number"]-1], c))
    for c in INCREASES:
        assert c["address"].split(",")[0] in records[c["number"]-1]["artifacts"][1]["pages"][0]["text"], "Original PDF property identity mismatch"
        candidates.append(increase(records[c["number"]-1], c))
    assert len(candidates) == 9 and len({c["claim_id"] for c in candidates}) == 9
    manifest = {"contract": "casepath.synthetic-audit-supplemental-profile/1.0.0",
                "profile_id": "synthetic-original150-plus-audit-nine-candidates-v1",
                "authored_on": AUTHOR_DATE, "base_commit": BASE,
                "original_manifest_file_sha256": ORIGINAL_MANIFEST_SHA,
                "original_corpus_count": 150, "supplemented_candidate_count": 9,
                "new_source_count": sum(c["new_source_count"] for c in candidates),
                "candidate_status": "pending_fresh_independent_legal_review_not_final_selection",
                "original_authority_or_journals_modified": False, "new_fictional_sources_only": True,
                "candidates": candidates}
    save(PACKS / "manifest.json", manifest)
    # Deterministic mechanical proof: all emitted source bytes/base64/hash and
    # every explicitly authored checklist quotation agree. No semantic model.
    for c in candidates:
        packet = json.loads((OUT / c["candidate_path"]).read_text())
        for s in packet["new_sources"]:
            data = (OUT / s["path"]).read_bytes()
            assert sha(data) == s["sha256"] and len(data) == s["size_bytes"]
            assert data == base64.b64decode(s["content_base64"], validate=True)
            assert data.startswith("SYNTHETIC SUPPLEMENT".encode())
        for fact in packet["active_fact_checklist"]:
            body = (OUT / fact["source_path"]).read_text()
            assert body[fact["start"]:fact["end"]] == fact["quote"]
    print(json.dumps({"candidates": len(candidates), "new_sources": manifest["new_source_count"],
                      "profile_sha256": sha((PACKS / 'manifest.json').read_bytes()),
                      "status": manifest["candidate_status"]}, indent=2))


if __name__ == "__main__":
    main()
