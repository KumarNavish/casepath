#!/usr/bin/env python3
"""Compile hand-reviewed verdicts and verify exact quote/receipt bindings.

No semantic inference, model/provider calls, runtime engine imports or product
state writes. Decisions are in reviewed_paths.py, made after original reading.
"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from reviewed_paths import JPEG_OBSERVATIONS, PATHS

OUT = Path(__file__).resolve().parent


def dump(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def quote(record, text):
    body = record["message_body"]
    start = body.index(text)
    assert body[start:start + len(text)] == text
    return {"claim_file": record["claim_receipt"], "json_pointer": "/customer_message/body",
            "body_projection": record["body_projection_receipt"],
            "offset_unit": "Unicode code points, zero-based, exclusive end",
            "start": start, "end": start + len(text), "quote": text}


def main():
    sources = json.loads((OUT / "source_receipts.json").read_text())
    mapping = {}
    for numbers, path, laws, unknown, needed, adverse in PATHS:
        for n in numbers:
            assert n not in mapping
            mapping[n] = (path, laws, unknown, needed, adverse)
    assert set(mapping) == set(range(1, 151))
    results = []
    for source in sources:
        n = source["number"]
        path, laws, unknown, needed, adverse = mapping[n]
        paragraphs = source["message_body"].split("\n\n")
        assert len(paragraphs) >= 6
        evidence = [{"status": "reported_customer_account_not_adjudicated_fact",
                     **quote(source, paragraphs[1])},
                    {"status": "explicit_customer_uncertainty", **quote(source, paragraphs[2])},
                    {"status": "requested_handling_scope", **quote(source, paragraphs[3])}]
        observations = []
        documents = []
        for a in source["artifacts"][1:]:
            ref = {k: a[k] for k in ("artifact_id", "path", "sha256", "file_name", "media_type", "size_bytes")}
            d = {**ref, "received": True, "understood": "bounded_source_reading",
                 "sufficient_for_full_requested_path": False}
            if a["media_type"] == "application/pdf":
                d["physical_pages"] = a["physical_page_count"]
                d["extracted"] = "machine_visible_text_each_page_and_native_render_inspected"
                d["visible_page_markers"] = [p["text"].split()[-1] if p["text"].split()[-1] in ("1/2", "2/2", "1/3", "2/3", "3/3") else None for p in a["pages"]]
                d["quote_first_physical_page"] = a["pages"][0]["text"]
                d["quote_representation"] = "PyMuPDF visible page text; Unicode whitespace retained, sort=True"
                if n in [5, 17, 83, 104, 111, 144]:
                    observations.append({**ref, "page": 1, "status": "observed_received_copy_defect",
                                         "fact": "Physical page count1; printed1/2; page2 not in this received PDF. Actual served original completeness unknown."})
                elif n in [8, 10, 47, 96, 138, 145]:
                    observations.append({**ref, "page": 1, "status": "observed_received_copy",
                                         "fact": "Tenant PDF complete physical2/printed2; spouse PDF physical1/printed1/2. Different June/July dates; year not entered. Actual served originals unknown."})
                elif n in [9, 38, 49, 73, 85, 89]:
                    observations.append({**ref, "page": 1, "status": "observed_received_notice_form_defect",
                                         "fact": "Plain one-page termination letter; blank visible signature line; no canton-approved form or statutory challenge guidance in this PDF. Additional notification channels remain unknown."})
                elif n in [29, 58, 81, 108, 149]:
                    observations.append({**ref, "page": 1, "status": "observed_received_notice_reason_defect",
                                         "fact": "All3 physical and printed pages present. No substantive reason in page1 reason field; standard separate-accompanying-letter label appears. No separate reason letter received. Net1850→1975; effective1Apr2026. Later email not received."})
                elif n in [6, 22, 68, 112, 135]:
                    observations.append({**ref, "page": 1, "status": "observed_received_notice_content",
                                         "fact": "All3 physical/printed pages present. Net1650→1790; heating advance210→82; gross1900→1912; effective1Apr2026; reason Kostenanpassung. These establish what notice says, not binding prior contractual rent."})
                elif n in [24, 27, 72, 80, 95, 103, 127]:
                    observations.append({**ref, "page": 1, "status": "observed_received_demand_content",
                                         "fact": "One complete payment-demand page; rent1680, fridge420, fees35, total2135;30days after receipt; warning refers to Art257d. No bank receipt, allocation ledger or actual termination attached."})
            else:
                assert a["media_type"] == "image/jpeg" and n in JPEG_OBSERVATIONS
                d["extracted"] = "no_machine_text_extraction; native_JPEG_view_inspected"
                d["pixel_size"] = a["pixel_size"]
                observations.append({**ref, "status": "native_visible_image_observation",
                                     "fact": JPEG_OBSERVATIONS[n],
                                     "limit": "Image condition only; no diagnosis, capture-date inference, legal notice or source causation inferred."})
            documents.append(d)
        limited = n in [9, 38, 49, 73, 85, 89, 29, 58, 81, 108, 149]
        closure = n in [21, 51, 86, 141, 148]
        repair_account = n in [2, 30, 54, 56, 113, 33, 48, 88, 106, 137]
        threat_account = n in [26, 43, 59, 62, 65]
        founded = "founded_limited_received_notice_objection" if limited else "founded_limited_reported_repair_request" if repair_account else "founded_limited_reported_termination_threat_objection" if threat_account else "not_applicable_administrative_closure" if closure else "indeterminate"
        founded_reason = (
            "The received plain landlord termination letter supports a tenant form/nullity objection under266l(2)/266o; sole/current tenancy termination and any separate later notice remain unestablished. This is a challenge ground, not a finding that tenant rights are invalid."
            if n in [9, 38, 49, 73, 85, 89] else
            "Received page-complete form has no substantive printed reason, providing a founded issue for269d(2)(b) nullity review. Whether original communication included separate contemporaneous reasons is unknown; overall increase nullity/substantive merits remain indeterminate."
            if limited else
            "Administrative record/closure is the actual request; repaired-and-dry report gives no current removal demand or new legal compensation claim. Bounded administrative closure advice is complete on that account; exact historical duration remains unknown but does not block this task."
            if closure else
            "Firsthand cold-room/heating-failure account and reported calls/phone response supply a prima facie narrow259a repair-request basis. Technical cause or calibration is not a mandatory prerequisite. Full further-remedies/deposit scope, dates/quantum and any responsibility defence remain unknown; no complete legal-merit nomination is made."
            if repair_account else
            "The express customer account of increase-or-termination supports a limited269d(2)(c) nullity objection. A missing attached letter or uncertain delivery alone does not defeat this reported ground. Stepped-rent form relaxation is distinct from the prohibition on accompanying termination threats; full communication/applicability remain unverified."
            if threat_account else
            "The reported facts engage the cited legal route, but material factual/documentary predicates for the full requested assessment remain unresolved. This does not establish a failed legal requirement or an invalid tenant claim."
        )
        results.append({
            "number": n, "claim_id": source["claim_id"], "domain": source["domain"],
            "family_id_navigation_only": source["family_id"], "subject": source["subject"],
            "received_at": source["received_at"], "canton": source["canton"],
            "path": path, "relevant_CO_articles": laws,
            "official_citations": ["https://www.fedlex.admin.ch/eli/cc/27/317_321_377/de#art_" + code[:-1] + "_" + code[-1] if code[-1].isalpha() else "https://www.fedlex.admin.ch/eli/cc/27/317_321_377/de#art_" + code for code in laws],
            "law_provenance": "Official_DE_CO_1Jan2026_current_text_public_extract_relayed_by_Mac_via_coordinator; corrected_actual_headings_read;272/272a_still_missing_for_extension_paths; historical_versions_unverified; see_official_law_receipt.json",
            "message_receipt": {k: source["artifacts"][0][k] for k in ("artifact_id", "path", "sha256", "media_type", "file_name", "size_bytes")},
            "claim_receipt": source["claim_receipt"], "registry_receipt": source["registry_receipt"],
            "established_source_facts": observations,
            "reported_facts_and_explicit_unknown_quotes": evidence,
            "missing_or_unknown_facts": unknown,
            "required_documents_for_actual_path": needed,
            "unknown_applicability": "Tenancy terms, statutory exceptions and family-home facts apply only when relevant to this route; taxonomy is not substantive proof. Scope/receipt uncertainty is preserved; intake awareness dates are not substituted for legal service dates.",
            "adverse_or_limiting_facts": adverse,
            "received_documents": documents,
            "document_completeness": "sufficient_for_bounded_administrative_closure_on_customer_account; exact_historical_duration_unknown_nonblocking" if closure else "incomplete_for_full_requested_path; received sources preserved and individually assessed",
            "complete_verdict": "complete_for_bounded_administrative_closure" if closure else "incomplete",
            "complete_reason": "Customer reports repair and continuing dryness; those facts suffice for bounded administrative closure advice. Exact historical duration remains unknown, but tenancy/expert/deposit documents are not mandatory for that task. No live substantive legal remedy is asserted." if closure else unknown + " " + needed,
            "foundation_verdict": founded, "foundation_reason": founded_reason,
            "overall_verdict": "administrative_closure_supported_not_legal_merit_demo" if closure else "indeterminate_for_full_legal_route",
            "complete_and_founded_nomination": False,
            "source_review": "All150 customer narratives read individually; all47PDF/73physical pages and10JPEG native views inspected by /root/original_completeness_audit on host656813ef2295,12Oct2026.",
        })
    assert len(results) == 150 and len({r["claim_id"] for r in results}) == 150
    dump("audit_150.json", results)
    keys = ["number", "claim_id", "domain", "received_at", "path", "relevant_CO_articles", "complete_verdict", "foundation_verdict", "overall_verdict", "missing_or_unknown_facts", "required_documents_for_actual_path", "adverse_or_limiting_facts", "foundation_reason", "complete_and_founded_nomination"]
    with (OUT / "audit_150.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys, lineterminator="\n")
        writer.writeheader()
        for result in results:
            writer.writerow({k: "|".join(result[k]) if isinstance(result[k], list) else result[k] for k in keys})
    summary = {}
    for domain in sorted({r["domain"] for r in results}):
        selected = [r for r in results if r["domain"] == domain]
        summary[domain] = {"claims": len(selected), "complete": dict(Counter(r["complete_verdict"] for r in selected)),
                           "foundation": dict(Counter(r["foundation_verdict"] for r in selected)),
                           "overall": dict(Counter(r["overall_verdict"] for r in selected)),
                           "complete_and_founded": 0, "qualified_nominations": [], "gap_to_three": 3}
    dump("baseline_counts.json", summary)
    law_receipt = json.loads((OUT / "official_law_receipt.json").read_text())
    dump("criteria.json", {
        "contract": "casepath.original-completeness-audit-criteria/1.0.0",
        "decision_source": "hand-reviewed original narratives and native attachments; no semantic/model automation",
        "complete_definition": "Sufficient material facts and relevant documents for the disclosed actual path; not every catalog document or every immaterial question.",
        "foundation_definition": "Source-supported predicates for an identified tenant request or objection; limited notice objections do not establish overall rights/timeliness.",
        "no_professional_report_universal_requirement": True,
        "received_extracted_understood_sufficient_are_separate": True,
        "administrative_closure_can_be_complete_without_substantive_legal_merit": True,
        "law_receipt": "official_law_receipt.json",
        "primary_articles_pending": law_receipt["missing_actual_articles_pending_primary_relay"],
        "current_primary_articles_for_active_nine_received": law_receipt["current_text_primary_articles_needed_for_active_nine_received"],
        "older_consolidation_pdf_verified": law_receipt["historical_consolidation_pdf_verified"],
        "paths": [{"reviewed_original_numbers": numbers, "path": path, "relevant_CO_articles": laws,
                   "material_unknowns": unknown, "route_relevant_documents_or_equivalent_reliable_evidence": needed,
                   "adverse_or_limiting_facts": adverse} for numbers, path, laws, unknown, needed, adverse in PATHS]})
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
