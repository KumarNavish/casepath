from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping

from .workspace_corpus import PublicCorpus, digest_value


_INTAKE_ASSESSMENT_CONTRACT_V1_1 = "casepath.deterministic-intake-assessment/1.1.0"
_INTAKE_COMPILER_ID_V1_1 = "casepath.observable-message-policy-compiler/1.1.0"
INTAKE_ASSESSMENT_CONTRACT = _INTAKE_ASSESSMENT_CONTRACT_V1_1
INTAKE_COMPILER_ID = _INTAKE_COMPILER_ID_V1_1
INTAKE_CATALOG_SHA256_V1_1 = "d550af3b4361098e1717f54422f219753b24fee854f8639d4f7bfa4de460b6d1"
INTAKE_ASSESSMENT_ROSTER_SHA256_V1_1 = "96c4886959482aff8ef7004e5637bc83aa7d14ad67079c40eea731a2ef6768d6"

# This catalog is intentionally small, outcome-blind, and fixed in source.  It
# classifies only the public intake family needed to select one of the three
# equally visible static playbooks.  It never reads a benchmark label, hidden
# target, expected action, selected action, or downstream outcome.
_INTAKE_TERM_CATALOG_V1_1 = MappingProxyType({
    "defect_mold_heating": tuple(
        sorted(
            {
                "abwasserrückstau",
                "boiler failure",
                "dampness",
                "feuchtigkeit",
                "heating failure",
                "heizkesselausfall",
                "heizungsausfall",
                "leakage",
                "multi-unit leak",
                "mold",
                "mould",
                "moisture",
                "schimmel",
                "sewage backflow",
                "water leak",
                "wasserleck",
                "wohnungsübergreifende leckage",
                "wiederholter heizungsausfall",
            }
        )
    ),
    "lease_termination_dispute": tuple(
        sorted(
            {
                "arrears termination",
                "family-home termination",
                "familienwohnung",
                "kündigung",
                "termination",
                "termination notice",
                "verzugskündigung",
            }
        )
    ),
    "rent_increase_dispute": tuple(
        sorted(
            {
                "ancillary charges",
                "increase form",
                "mietzinserhöhung",
                "nebenkosten",
                "official increase",
                "officially notified increase",
                "reference-rate",
                "referenzzins",
                "renovation grant",
                "renovation-related increase",
                "rent increase",
                "sanierungsbeitrag",
                "sanierungsbedingte erhöhung",
                "amtlich mitgeteilte erhöhung",
                "erhöhungsformular",
            }
        )
    ),
})
# Public read-only inspection surface. Replay deliberately dispatches to this
# immutable versioned catalog; a successor compiler must receive a new ID and
# retain this implementation for already journaled events.
INTAKE_TERM_CATALOG = _INTAKE_TERM_CATALOG_V1_1


class IntakeCompilationError(ValueError):
    pass


def _copy(value: Any) -> Any:
    # digest_value already rejects non-canonical values.  This conversion keeps
    # the returned packet detached from the corpus object's in-memory objects.
    import json

    return json.loads(json.dumps(value))


def _message_material(claim: Mapping[str, Any]) -> dict[str, Any]:
    message = claim.get("customer_message")
    if not isinstance(message, dict):
        raise IntakeCompilationError("observable claim message is missing")
    required = {"message_id", "subject", "body", "sent_at", "from_role", "to_role"}
    material = {key: message.get(key) for key in sorted(required)}
    if (
        any(not isinstance(material[key], str) or not material[key] for key in required)
        or message.get("message_id") != material["message_id"]
    ):
        raise IntakeCompilationError("observable claim message is invalid")
    return material


def _catalog_material_v1_1(
    catalog: Mapping[str, tuple[str, ...]] = _INTAKE_TERM_CATALOG_V1_1,
) -> list[dict[str, Any]]:
    return [
        {
            "claim_type": claim_type,
            "terms": sorted(catalog[claim_type]),
        }
        for claim_type in sorted(catalog)
    ]


def _score_subject_v1_1(
    subject: str,
    catalog: Mapping[str, tuple[str, ...]] = _INTAKE_TERM_CATALOG_V1_1,
) -> list[dict[str, Any]]:
    return [
        {
            "claim_type": claim_type,
            "matched_terms": [
                term
                for term in sorted(catalog[claim_type])
                if term.casefold() in subject
            ],
            "score": sum(
                term.casefold() in subject for term in sorted(catalog[claim_type])
            ),
        }
        for claim_type in sorted(catalog)
    ]


def _compile_intake_assessment_v1_1(
    corpus: PublicCorpus,
    claim_id: str,
) -> dict[str, Any]:
    """Compile a claim-specific, outcome-blind first workbench step.

    The subject line is the deliberately narrow classification surface.  Body
    text remains fully visible in the workbench but is excluded here because it
    can mention remedies from another family (for example a rent reduction in a
    mould claim).  The selected playbook and every displayed branch are then
    copied from the admitted static policy file, never invented by this method.
    """

    if digest_value(_catalog_material_v1_1()) != INTAKE_CATALOG_SHA256_V1_1:
        raise IntakeCompilationError("v1.1 intake catalog identity drifted")
    binding = corpus.binding(claim_id)
    claim = corpus.claim(claim_id)
    message = _message_material(claim)
    if (
        binding.get("claim_id") != claim_id
        or binding.get("message_id") != message["message_id"]
        or binding.get("subject") != message["subject"]
        or binding.get("claim", {}).get("sha256") is None
        or binding.get("source_registry", {}).get("sha256") is None
    ):
        raise IntakeCompilationError("observable claim binding is inconsistent")

    subject = message["subject"].casefold()
    score_rows = _score_subject_v1_1(subject)
    winning_score = max(row["score"] for row in score_rows)
    winners = [row for row in score_rows if row["score"] == winning_score]
    if winning_score < 1 or len(winners) != 1:
        raise IntakeCompilationError("observable intake family is not uniquely identifiable")
    claim_type = winners[0]["claim_type"]

    policy = corpus.static_policy()
    templates = policy.get("templates")
    if not isinstance(templates, list):
        raise IntakeCompilationError("static policy template roster is invalid")
    matches = [row for row in templates if row.get("domain") == claim_type]
    if len(matches) != 1:
        raise IntakeCompilationError("classified intake has no unique static playbook")
    template = matches[0]
    catalog = template.get("process_catalog")
    nodes = catalog.get("nodes") if isinstance(catalog, dict) else None
    transitions = catalog.get("transitions") if isinstance(catalog, dict) else None
    clauses = template.get("clauses")
    if (
        not isinstance(nodes, list)
        or not nodes
        or not isinstance(transitions, list)
        or not isinstance(clauses, list)
    ):
        raise IntakeCompilationError("classified static playbook is incomplete")
    current_node = nodes[0]
    node_by_id = {row.get("node_id"): row for row in nodes}
    required_node_keys = {"node_id", "label", "responsibility", "terminal"}
    if not required_node_keys.issubset(current_node) or current_node.get("terminal") is not False:
        raise IntakeCompilationError("static playbook has no valid intake node")
    outgoing = [
        {
            "edge_id": row["edge_id"],
            "condition": row["condition"],
            "target_node_id": row["target_node_id"],
            "target_label": node_by_id[row["target_node_id"]]["label"],
            "optional_path": row["optional_path"],
        }
        for row in transitions
        if row.get("source_node_id") == current_node["node_id"]
    ]
    outgoing.sort(key=lambda row: row["edge_id"])
    if not outgoing:
        raise IntakeCompilationError("static playbook intake node has no outgoing branch")

    policy_file = corpus.static_policy_file_identity
    material = {
        "contract": _INTAKE_ASSESSMENT_CONTRACT_V1_1,
        "compiler_id": _INTAKE_COMPILER_ID_V1_1,
        "claim_id": claim_id,
        "binding_sha256": binding["binding_sha256"],
        "claim_file_sha256": binding["claim"]["sha256"],
        "source_registry_sha256": binding["source_registry"]["sha256"],
        "static_template_sha256": binding["static_template_sha256"],
        "static_policy_file_sha256": policy_file["sha256"],
        "message_sha256": digest_value(message),
        "classification_basis": "observable_customer_message_subject_v1",
        "classifier_catalog_sha256": digest_value(_catalog_material_v1_1()),
        "domain_scores": score_rows,
        "claim_type": claim_type,
        "policy_template": {
            "template_id": template["template_id"],
            "title": template["title"],
            "domain": template["domain"],
            "template_sha256": digest_value(template),
        },
        "current_node": {
            key: _copy(current_node[key]) for key in sorted(required_node_keys)
        },
        "outgoing_branches": outgoing,
        "policy_clause_refs": [
            {
                "clause_id": row["clause_id"],
                "content": row["content"],
                "content_sha256": row["content_sha256"],
            }
            for row in clauses
        ],
        "activity": {
            "model_calls": 0,
            "provider_calls": 0,
            "credential_reads": 0,
            "cost_usd": 0,
        },
    }
    return {**material, "assessment_sha256": digest_value(material)}


def compile_intake_assessment(
    corpus: PublicCorpus,
    claim_id: str,
) -> dict[str, Any]:
    return _compile_intake_assessment_v1_1(corpus, claim_id)


def validate_intake_assessment(
    value: Mapping[str, Any],
    *,
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    assessment = _copy(value)
    if assessment != _copy(expected):
        raise IntakeCompilationError("intake assessment differs from source compilation")
    material = dict(assessment)
    stated = material.pop("assessment_sha256", None)
    if stated != digest_value(material):
        raise IntakeCompilationError("intake assessment identity is invalid")
    return assessment


def validate_recorded_intake_assessment(
    value: Mapping[str, Any],
    *,
    corpus: PublicCorpus,
    claim_id: str,
) -> dict[str, Any]:
    """Replay a persisted assessment with its exact versioned compiler."""

    compiler_id = value.get("compiler_id") if isinstance(value, Mapping) else None
    if compiler_id != _INTAKE_COMPILER_ID_V1_1:
        raise IntakeCompilationError("recorded intake compiler is unsupported")
    return validate_intake_assessment(
        value,
        expected=_compile_intake_assessment_v1_1(corpus, claim_id),
    )
