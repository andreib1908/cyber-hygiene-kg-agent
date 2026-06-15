"""Cypher retrieval templates for Neo.

These templates are intentionally predefined instead of fully LLM-generated.
The goal is to retrieve source-grounded graph context safely and then let the
LLM answer only from that retrieved context.
"""

from __future__ import annotations


RETRIEVE_BY_KU_IDS = """
UNWIND range(0, size($ku_ids) - 1) AS idx
WITH $ku_ids[idx] AS ku_id, idx

MATCH (ku:KnowledgeUnit {id: ku_id})

OPTIONAL MATCH (ku)-[:IN_CATEGORY]->(c:CyberHygieneCategory)
OPTIONAL MATCH (ku)-[:ADDRESSES_THREAT]->(t:Threat)
OPTIONAL MATCH (ku)-[:RECOMMENDS_PRACTICE]->(p:Practice)
OPTIONAL MATCH (ku)-[:HAS_EVIDENCE]->(e:Evidence)-[:FROM_SOURCE]->(s:Source)
OPTIONAL MATCH (ku)-[:HAS_VALIDITY_FACT]->(vf:ValidityFact)
OPTIONAL MATCH (ku)-[:HAS_TRACEABILITY_REQUIREMENT]->(tr:TraceabilityRequirement)
OPTIONAL MATCH (ku)-[:HAS_ANSWER_GUIDANCE]->(g:AgentAnswerGuidance)
OPTIONAL MATCH (ku)-[:HAS_QUESTION_TEMPLATE]->(qt:QuestionTemplate)

RETURN
  idx AS retrieval_rank,
  ku.id AS ku_id,
  ku.title AS ku_title,

  collect(DISTINCT {
    id: ku.id,
    title: ku.title,
    claim: ku.claim,
    explanation: ku.explanation,
    recommended_actions: ku.recommended_actions,
    evidence_strength: ku.evidence_strength
  }) AS knowledge_units,

  collect(DISTINCT qt.text) AS question_templates,

  collect(DISTINCT {
    id: c.id,
    name: c.name,
    definition: c.definition
  }) AS categories,

  collect(DISTINCT {
    id: t.id,
    name: t.name,
    definition: t.definition,
    support_status: t.support_status,
    support_notes: t.support_notes
  }) AS threats,

  collect(DISTINCT {
    id: p.id,
    name: p.name,
    description: p.description,
    source_ids: p.source_ids
  }) AS practices,

  collect(DISTINCT {
    evidence_id: e.evidence_id,
    support_type: e.support_type,
    text: e.exact_supporting_text,
    page: e.page,
    section: e.section,
    paragraph: e.paragraph,
    citation_key: s.citation_key,
    source_id: s.id,
    source_title: s.title,
    authors: s.authors,
    url: s.url,
    year: s.year
  }) AS evidence,

  collect(DISTINCT {
    fact_id: vf.fact_id,
    fact: vf.fact,
    source_id: vf.source_id,
    evidence_id: vf.evidence_id
  }) AS validity_facts,

  collect(DISTINCT {
    requires_citation: tr.requires_citation,
    acceptable_sources: tr.acceptable_sources,
    citation_granularity: tr.citation_granularity,
    minimum_traceability_requirement: tr.minimum_traceability_requirement
  }) AS traceability,

  collect(DISTINCT {
    answer_style: g.answer_style,
    must_include: g.must_include,
    avoid_claims: g.avoid_claims
  }) AS answer_guidance

ORDER BY retrieval_rank
LIMIT $limit
"""

VECTOR_SEARCH_KNOWLEDGE_UNITS = """
CALL db.index.vector.queryNodes($index_name, $top_k, $query_vector)
YIELD node, score
RETURN node.id AS ku_id, node.title AS title, score
ORDER BY score DESC
"""