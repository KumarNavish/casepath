from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from typing import Any


LAW_REGISTRY_CONTRACT = "casepath.legal-context/2.0.0"
LAW_REGISTRY_VERSION = "ch-tenancy-official-snapshot/2026-08-12"
FEDLEX_OR_SNAPSHOT_URL = (
    "https://www.fedlex.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/"
    "27/317_321_377/20230901/de/pdf-a/"
    "fedlex-data-admin-ch-eli-cc-27-317_321_377-20230901-de-pdf-a-9.pdf"
)
FEDLEX_OR_SNAPSHOT_SHA256 = (
    "6a958ae86cf67f71b1d36b798775b1659f06a9f0130fb9649f6ef045ce409966"
)
BWO_CONCILIATION_URL = "https://www.bwo.admin.ch/de/schlichtungsverfahren"
BWO_CONCILIATION_SNAPSHOT_SHA256 = (
    "27700e4ed06b60510b992676823c44d9a11aefb94192fdc3bec872df1c843af6"
)


def _passage_hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _official_source(
    *,
    source_id: str,
    title: str,
    url: str,
    source_type: str,
    version_date: str,
    location: str,
    passage_language: str,
    passage_text: str,
    passage_summary: str,
    operational_interpretation: str,
    role: str,
    snapshot_url: str,
    snapshot_sha256: str,
    snapshot_scope: str,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "title": title,
        "url": url,
        "source_type": source_type,
        "jurisdiction": "CH",
        "version_date": version_date,
        "location": location,
        "passage_language": passage_language,
        "passage_text": passage_text,
        "passage_sha256": _passage_hash(passage_text),
        "passage_summary": passage_summary,
        "operational_interpretation": operational_interpretation,
        "review_status": "qualified_review_pending",
        "role": role,
        "approved": False,
        "retrieval": {
            "method": "versioned_official_source_registry_lookup",
            "retrieved_at": "2026-08-12",
            "registry_version": LAW_REGISTRY_VERSION,
            "snapshot_url": snapshot_url,
            "snapshot_sha256": snapshot_sha256,
            "snapshot_scope": snapshot_scope,
        },
    }


LAW_SOURCES = [
    _official_source(
        source_id="fedlex-or-256",
        title="Swiss Code of Obligations, Art. 256",
        url="https://www.fedlex.admin.ch/eli/cc/27/317_321_377/en",
        source_type="official_statute",
        version_date="2023-09-01",
        location="Article 256; official German PDF page 66",
        passage_language="de",
        passage_text=(
            "Der Vermieter ist verpflichtet, die Sache zum vereinbarten Zeitpunkt "
            "in einem zum vorausgesetzten Gebrauch tauglichen Zustand zu übergeben "
            "und in demselben zu erhalten."
        ),
        passage_summary=(
            "The landlord must hand over and maintain the premises in a condition "
            "fit for their intended use."
        ),
        operational_interpretation=(
            "Deterministic reference interpretation: fitness for intended use makes "
            "the alleged condition relevant to the handling process, but does not "
            "establish technical cause or responsibility."
        ),
        role=(
            "Makes the condition and maintenance question relevant without deciding "
            "causation."
        ),
        snapshot_url=FEDLEX_OR_SNAPSHOT_URL,
        snapshot_sha256=FEDLEX_OR_SNAPSHOT_SHA256,
        snapshot_scope="official_pdf_bytes",
    ),
    _official_source(
        source_id="fedlex-or-257g",
        title="Swiss Code of Obligations, Art. 257g",
        url="https://www.fedlex.admin.ch/eli/cc/27/317_321_377/en",
        source_type="official_statute",
        version_date="2023-09-01",
        location="Article 257g; official German PDF page 68",
        passage_language="de",
        passage_text=(
            "Der Mieter muss Mängel, die er nicht selber zu beseitigen hat, dem "
            "Vermieter melden. Unterlässt der Mieter die Meldung, so haftet er für "
            "den Schaden, der dem Vermieter daraus entsteht."
        ),
        passage_summary=(
            "A tenant must report defects they are not responsible for remedying and "
            "may be liable for loss caused by failing to report them."
        ),
        operational_interpretation=(
            "Deterministic reference interpretation: notification is a relevant fact; "
            "written evidence can help establish that it occurred. The provision is "
            "not represented as imposing a statutory writing requirement."
        ),
        role="Makes notification a relevant fact; written evidence helps establish it.",
        snapshot_url=FEDLEX_OR_SNAPSHOT_URL,
        snapshot_sha256=FEDLEX_OR_SNAPSHOT_SHA256,
        snapshot_scope="official_pdf_bytes",
    ),
    _official_source(
        source_id="fedlex-or-259a",
        title="Swiss Code of Obligations, Art. 259a et seq.",
        url="https://www.fedlex.admin.ch/eli/cc/27/317_321_377/en",
        source_type="official_statute",
        version_date="2023-09-01",
        location="Article 259a; official German PDF page 69",
        passage_language="de",
        passage_text=(
            "Entstehen an der Sache Mängel, die der Mieter weder zu verantworten "
            "noch auf eigene Kosten zu beseitigen hat, oder wird der Mieter im "
            "vertragsgemässen Gebrauch der Sache gestört, so kann er verlangen, "
            "dass der Vermieter: a. den Mangel beseitigt; b. den Mietzins "
            "verhältnismässig herabsetzt; c. Schadenersatz leistet; d. den "
            "Rechtsstreit mit einem Dritten übernimmt."
        ),
        passage_summary=(
            "The provision lists remedies for defects the tenant neither caused nor "
            "must remedy at their own expense, or for interference with contractual use."
        ),
        operational_interpretation=(
            "Deterministic reference interpretation: remedy questions follow supported "
            "defect and attribution facts; the provision itself does not establish causation."
        ),
        role="Frames possible remedy questions without deciding causation or attribution.",
        snapshot_url=FEDLEX_OR_SNAPSHOT_URL,
        snapshot_sha256=FEDLEX_OR_SNAPSHOT_SHA256,
        snapshot_scope="official_pdf_bytes",
    ),
    _official_source(
        source_id="bwo-conciliation",
        title="Federal Housing Office - tenancy conciliation",
        url=BWO_CONCILIATION_URL,
        source_type="official_guidance",
        version_date="2024-07-16",
        location="Schlichtungsverfahren Miete und Pacht; introductory passage",
        passage_language="de",
        passage_text=(
            "Bei zivilrechtlichen Streitigkeiten wird vor dem richterlichen "
            "Entscheidverfahren ein Schlichtungsversuch vor der Schlichtungsbehörde "
            "durchgeführt. Bei Streitigkeiten aus Miete und Pacht von Wohn- und "
            "Geschäftsräumen besteht die Schlichtungsbehörde aus einer unabhängigen "
            "vorsitzenden Person und der paritätischen Mieter- und Vermietervertretung. "
            "Das Verfahren richtet sich nach der Schweizerischen Zivilprozessordnung (ZPO)."
        ),
        passage_summary=(
            "A conciliation attempt precedes judicial proceedings in civil disputes; "
            "tenancy conciliation bodies are independently chaired with parity tenant "
            "and landlord representation under the Civil Procedure Code."
        ),
        operational_interpretation=(
            "Deterministic reference interpretation: conciliation may become relevant "
            "after the supported remedy remains disputed; case-specific escalation "
            "still requires qualified review."
        ),
        role="Explains the institutional route without deciding whether this claim should escalate.",
        snapshot_url=BWO_CONCILIATION_URL,
        snapshot_sha256=BWO_CONCILIATION_SNAPSHOT_SHA256,
        snapshot_scope="normalized_official_passage_utf8",
    ),
]


HANDLING_PRINCIPLES = [
    {
        "source_id": "handling-causation",
        "title": "Deterministic handling proposal: preserve disputed causation",
        "source_type": "operational_interpretation",
        "role": (
            "A party allegation does not establish technical cause. Responsibility "
            "remains open until competent evidence distinguishes plausible explanations."
        ),
        "validation_status": "generated_reference_not_expert_approved",
        "producer": "deterministic_application",
    },
    {
        "source_id": "handling-evidence-order",
        "title": "Deterministic handling proposal: least-burdensome competent evidence first",
        "source_type": "operational_interpretation",
        "role": (
            "Request the first competent assessment before broader or more invasive "
            "tests unless current evidence already justifies them."
        ),
        "validation_status": "candidate_not_expert_approved",
        "producer": "deterministic_application",
    },
]


LEGAL_QUESTIONS = [
    {
        "question_id": "tenancy_scope_and_fitness",
        "text": "Does Swiss residential-tenancy defect handling apply, and why does the alleged condition matter?",
        "source_ids": ["fedlex-or-256"],
        "interpretation_ids": [],
        "process_node_ids": ["scope", "defect", "building_defect"],
        "consequence": "Establish scope and treat fitness for intended use as relevant without deciding technical cause.",
    },
    {
        "question_id": "defect_notification",
        "text": "Was the landlord notified of the alleged defect, and what evidence establishes notification?",
        "source_ids": ["fedlex-or-257g"],
        "interpretation_ids": [],
        "process_node_ids": ["notification", "formal_notice"],
        "consequence": "Keep notification as an explicit fact and distinguish the duty to report from proof of how it was reported.",
    },
    {
        "question_id": "causation_before_responsibility",
        "text": "Which competent evidence is needed before cause and responsibility can be assessed?",
        "source_ids": ["fedlex-or-256"],
        "interpretation_ids": ["handling-causation", "handling-evidence-order"],
        "process_node_ids": ["causation", "responsibility", "evidence_gap"],
        "consequence": "Preserve disputed causation and seek the least-burdensome competent evidence before attribution.",
    },
    {
        "question_id": "defect_remedies",
        "text": "Which remedy questions become available if the relevant defect and attribution facts are supported?",
        "source_ids": ["fedlex-or-259a"],
        "interpretation_ids": [],
        "process_node_ids": ["building_defect", "responsibility", "remedy"],
        "consequence": "Do not select a remedy before the defect and attribution conditions in the official provision are supported.",
    },
    {
        "question_id": "conciliation_route",
        "text": "When would conciliation or another escalation route become relevant?",
        "source_ids": ["bwo-conciliation"],
        "interpretation_ids": [],
        "process_node_ids": ["escalation"],
        "consequence": "Present the official institutional route without deciding that this claim should escalate.",
    },
]


def legal_context() -> dict[str, Any]:
    node_links: dict[str, list[str]] = {}
    for question in LEGAL_QUESTIONS:
        authority_ids = [
            *question["source_ids"],
            *question["interpretation_ids"],
        ]
        for node_id in question["process_node_ids"]:
            retained = node_links.setdefault(node_id, [])
            for source_id in authority_ids:
                if source_id not in retained:
                    retained.append(source_id)
    return {
        "contract": LAW_REGISTRY_CONTRACT,
        "registry_version": LAW_REGISTRY_VERSION,
        "lookup_method": "versioned_official_source_registry_lookup",
        "questions": deepcopy(LEGAL_QUESTIONS),
        "sources": deepcopy(LAW_SOURCES),
        "handling_principles": deepcopy(HANDLING_PRINCIPLES),
        "node_links": node_links,
        "review_status": (
            "Operational translation not yet approved by a qualified Swiss "
            "tenant-law reviewer"
        ),
    }


__all__ = [
    "BWO_CONCILIATION_SNAPSHOT_SHA256",
    "FEDLEX_OR_SNAPSHOT_SHA256",
    "HANDLING_PRINCIPLES",
    "LAW_REGISTRY_CONTRACT",
    "LAW_REGISTRY_VERSION",
    "LAW_SOURCES",
    "LEGAL_QUESTIONS",
    "legal_context",
]
