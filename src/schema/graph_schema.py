"""Neo knowledge graph schema constants.

This module defines the canonical node labels, relationship types, and
important node properties used by the Neo cyber hygiene knowledge graph.

Keep this file as the single source of truth for:
- graph ingestion
- retrieval query templates
- Cypher prompt generation
- documentation/schema export
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Node labels
# ---------------------------------------------------------------------------

SOURCE = "Source"
CYBER_HYGIENE_CATEGORY = "CyberHygieneCategory"
THREAT = "Threat"
PRACTICE = "Practice"
KNOWLEDGE_UNIT = "KnowledgeUnit"
EVIDENCE = "Evidence"
VALIDITY_FACT = "ValidityFact"
TRACEABILITY_REQUIREMENT = "TraceabilityRequirement"
AGENT_ANSWER_GUIDANCE = "AgentAnswerGuidance"
QUESTION_TEMPLATE = "QuestionTemplate"

NODE_LABELS: tuple[str, ...] = (
    SOURCE,
    CYBER_HYGIENE_CATEGORY,
    THREAT,
    PRACTICE,
    KNOWLEDGE_UNIT,
    EVIDENCE,
    VALIDITY_FACT,
    TRACEABILITY_REQUIREMENT,
    AGENT_ANSWER_GUIDANCE,
    QUESTION_TEMPLATE,
)


# Relationship types

# Source support relationships
SUPPORTS_CATEGORY = "SUPPORTS_CATEGORY"
SUPPORTS_THREAT = "SUPPORTS_THREAT"
SUPPORTS_PRACTICE = "SUPPORTS_PRACTICE"
SUPPORTS_KNOWLEDGE_UNIT = "SUPPORTS_KNOWLEDGE_UNIT"

# KnowledgeUnit-centered relationships
IN_CATEGORY = "IN_CATEGORY"
ADDRESSES_THREAT = "ADDRESSES_THREAT"
RECOMMENDS_PRACTICE = "RECOMMENDS_PRACTICE"
HAS_EVIDENCE = "HAS_EVIDENCE"
HAS_VALIDITY_FACT = "HAS_VALIDITY_FACT"
HAS_TRACEABILITY_REQUIREMENT = "HAS_TRACEABILITY_REQUIREMENT"
HAS_ANSWER_GUIDANCE = "HAS_ANSWER_GUIDANCE"
HAS_QUESTION_TEMPLATE = "HAS_QUESTION_TEMPLATE"

# Evidence and validity relationships
FROM_SOURCE = "FROM_SOURCE"
SUPPORTED_BY_EVIDENCE = "SUPPORTED_BY_EVIDENCE"
SUPPORTED_BY_SOURCE = "SUPPORTED_BY_SOURCE"

# Practice/threat/category relationships
BELONGS_TO_CATEGORY = "BELONGS_TO_CATEGORY"
MITIGATES = "MITIGATES"
RELATED_TO_CATEGORY = "RELATED_TO_CATEGORY"

RELATIONSHIP_TYPES: tuple[str, ...] = (
    SUPPORTS_CATEGORY,
    SUPPORTS_THREAT,
    SUPPORTS_PRACTICE,
    SUPPORTS_KNOWLEDGE_UNIT,
    IN_CATEGORY,
    ADDRESSES_THREAT,
    RECOMMENDS_PRACTICE,
    HAS_EVIDENCE,
    HAS_VALIDITY_FACT,
    HAS_TRACEABILITY_REQUIREMENT,
    HAS_ANSWER_GUIDANCE,
    HAS_QUESTION_TEMPLATE,
    FROM_SOURCE,
    SUPPORTED_BY_EVIDENCE,
    SUPPORTED_BY_SOURCE,
    BELONGS_TO_CATEGORY,
    MITIGATES,
    RELATED_TO_CATEGORY,
)


# Canonical relationship directions

RELATIONSHIP_DIRECTIONS: tuple[tuple[str, str, str], ...] = (
    # Source support
    (SOURCE, SUPPORTS_CATEGORY, CYBER_HYGIENE_CATEGORY),
    (SOURCE, SUPPORTS_THREAT, THREAT),
    (SOURCE, SUPPORTS_PRACTICE, PRACTICE),
    (SOURCE, SUPPORTS_KNOWLEDGE_UNIT, KNOWLEDGE_UNIT),

    # KnowledgeUnit as central answer unit
    (KNOWLEDGE_UNIT, IN_CATEGORY, CYBER_HYGIENE_CATEGORY),
    (KNOWLEDGE_UNIT, ADDRESSES_THREAT, THREAT),
    (KNOWLEDGE_UNIT, RECOMMENDS_PRACTICE, PRACTICE),
    (KNOWLEDGE_UNIT, HAS_EVIDENCE, EVIDENCE),
    (KNOWLEDGE_UNIT, HAS_VALIDITY_FACT, VALIDITY_FACT),
    (KNOWLEDGE_UNIT, HAS_TRACEABILITY_REQUIREMENT, TRACEABILITY_REQUIREMENT),
    (KNOWLEDGE_UNIT, HAS_ANSWER_GUIDANCE, AGENT_ANSWER_GUIDANCE),
    (KNOWLEDGE_UNIT, HAS_QUESTION_TEMPLATE, QUESTION_TEMPLATE),

    # Evidence and facts
    (EVIDENCE, FROM_SOURCE, SOURCE),
    (VALIDITY_FACT, SUPPORTED_BY_EVIDENCE, EVIDENCE),
    (VALIDITY_FACT, SUPPORTED_BY_SOURCE, SOURCE),

    # Practice/threat/category links
    (PRACTICE, BELONGS_TO_CATEGORY, CYBER_HYGIENE_CATEGORY),
    (PRACTICE, MITIGATES, THREAT),
    (PRACTICE, SUPPORTED_BY_SOURCE, SOURCE),
    (THREAT, RELATED_TO_CATEGORY, CYBER_HYGIENE_CATEGORY),
    (THREAT, SUPPORTED_BY_SOURCE, SOURCE),
)


# Uniqueness constraints


# Format:
# constraint_name: (node_label, unique_property)
UNIQUE_CONSTRAINTS: dict[str, tuple[str, str]] = {
    "source_id": (SOURCE, "id"),
    "category_id": (CYBER_HYGIENE_CATEGORY, "id"),
    "threat_id": (THREAT, "id"),
    "practice_id": (PRACTICE, "id"),
    "knowledge_unit_id": (KNOWLEDGE_UNIT, "id"),
    "evidence_id": (EVIDENCE, "evidence_id"),
    "validity_fact_id": (VALIDITY_FACT, "fact_id"),
    "traceability_requirement_id": (TRACEABILITY_REQUIREMENT, "id"),
    "agent_answer_guidance_id": (AGENT_ANSWER_GUIDANCE, "id"),
    "question_template_id": (QUESTION_TEMPLATE, "id"),
}


# Search indexes


# Format:
# index_name: (node_label, indexed_property)
SEARCH_INDEXES: dict[str, tuple[str, str]] = {
    "source_citation_key": (SOURCE, "citation_key"),
    "category_name": (CYBER_HYGIENE_CATEGORY, "name"),
    "threat_name": (THREAT, "name"),
    "practice_name": (PRACTICE, "name"),
    "knowledge_unit_title": (KNOWLEDGE_UNIT, "title"),
    "question_template_text": (QUESTION_TEMPLATE, "text"),
}


# Helper text for Cypher prompts / documentation

def relationship_schema_text() -> str:
    """Return a human-readable relationship schema for prompts/docs."""
    lines = []
    for start_label, relationship, end_label in RELATIONSHIP_DIRECTIONS:
        lines.append(f"(:{start_label})-[:{relationship}]->(:{end_label})")
    return "\n".join(lines)


def allowed_schema_text() -> str:
    """Return allowed labels and relationships as prompt-ready text."""
    labels = ", ".join(f":{label}" for label in NODE_LABELS)
    rels = ", ".join(f":{relationship}" for relationship in RELATIONSHIP_TYPES)

    return (
        "Allowed node labels:\n"
        f"{labels}\n\n"
        "Allowed relationship types:\n"
        f"{rels}\n\n"
        "Allowed relationship directions:\n"
        f"{relationship_schema_text()}"
    )
