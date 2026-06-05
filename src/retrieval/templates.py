"""Cypher retrieval templates for Neo.

These templates are intentionally predefined instead of fully LLM-generated.
The goal is to retrieve source-grounded graph context safely and then let the
LLM answer only from that retrieved context.
"""

from __future__ import annotations


RETRIEVE_BY_THREAT = """
MATCH (t:Threat)
WHERE toLower(t.name) CONTAINS toLower($keyword)
   OR toLower(t.id) CONTAINS toLower($keyword)

OPTIONAL MATCH (ku:KnowledgeUnit)-[:ADDRESSES_THREAT]->(t)
OPTIONAL MATCH (ku)-[:RECOMMENDS_PRACTICE]->(p:Practice)
OPTIONAL MATCH (ku)-[:HAS_EVIDENCE]->(e:Evidence)-[:FROM_SOURCE]->(s:Source)
OPTIONAL MATCH (ku)-[:HAS_VALIDITY_FACT]->(vf:ValidityFact)
OPTIONAL MATCH (ku)-[:HAS_TRACEABILITY_REQUIREMENT]->(tr:TraceabilityRequirement)
OPTIONAL MATCH (ku)-[:HAS_ANSWER_GUIDANCE]->(g:AgentAnswerGuidance)

RETURN
  t.id AS threat_id,
  t.name AS threat_name,
  t.definition AS threat_definition,
  t.support_status AS threat_support_status,
  t.support_notes AS threat_support_notes,

  collect(DISTINCT {
    id: ku.id,
    title: ku.title,
    claim: ku.claim,
    explanation: ku.explanation,
    recommended_actions: ku.recommended_actions,
    evidence_strength: ku.evidence_strength
  }) AS knowledge_units,

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

LIMIT $limit
"""


RETRIEVE_BY_CATEGORY = """
MATCH (c:CyberHygieneCategory)
WHERE toLower(c.name) CONTAINS toLower($keyword)
   OR toLower(c.id) CONTAINS toLower($keyword)

OPTIONAL MATCH (ku:KnowledgeUnit)-[:IN_CATEGORY]->(c)
OPTIONAL MATCH (ku)-[:RECOMMENDS_PRACTICE]->(p:Practice)
OPTIONAL MATCH (ku)-[:ADDRESSES_THREAT]->(t:Threat)
OPTIONAL MATCH (ku)-[:HAS_EVIDENCE]->(e:Evidence)-[:FROM_SOURCE]->(s:Source)
OPTIONAL MATCH (ku)-[:HAS_VALIDITY_FACT]->(vf:ValidityFact)
OPTIONAL MATCH (ku)-[:HAS_TRACEABILITY_REQUIREMENT]->(tr:TraceabilityRequirement)
OPTIONAL MATCH (ku)-[:HAS_ANSWER_GUIDANCE]->(g:AgentAnswerGuidance)

RETURN
  c.id AS category_id,
  c.name AS category_name,
  c.definition AS category_definition,
  c.examples AS category_examples,

  collect(DISTINCT {
    id: ku.id,
    title: ku.title,
    claim: ku.claim,
    explanation: ku.explanation,
    recommended_actions: ku.recommended_actions,
    evidence_strength: ku.evidence_strength
  }) AS knowledge_units,

  collect(DISTINCT {
    id: p.id,
    name: p.name,
    description: p.description,
    source_ids: p.source_ids
  }) AS practices,

  collect(DISTINCT {
    id: t.id,
    name: t.name,
    definition: t.definition,
    support_status: t.support_status
  }) AS threats,

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

LIMIT $limit
"""


RETRIEVE_BY_PRACTICE = """
MATCH (p:Practice)
WHERE toLower(p.name) CONTAINS toLower($keyword)
   OR toLower(p.id) CONTAINS toLower($keyword)

OPTIONAL MATCH (ku:KnowledgeUnit)-[:RECOMMENDS_PRACTICE]->(p)
OPTIONAL MATCH (ku)-[:ADDRESSES_THREAT]->(t:Threat)
OPTIONAL MATCH (p)-[:BELONGS_TO_CATEGORY]->(c:CyberHygieneCategory)
OPTIONAL MATCH (ku)-[:HAS_EVIDENCE]->(e:Evidence)-[:FROM_SOURCE]->(s:Source)
OPTIONAL MATCH (ku)-[:HAS_VALIDITY_FACT]->(vf:ValidityFact)
OPTIONAL MATCH (ku)-[:HAS_TRACEABILITY_REQUIREMENT]->(tr:TraceabilityRequirement)
OPTIONAL MATCH (ku)-[:HAS_ANSWER_GUIDANCE]->(g:AgentAnswerGuidance)

RETURN
  p.id AS practice_id,
  p.name AS practice_name,
  p.description AS practice_description,
  p.source_ids AS practice_source_ids,

  collect(DISTINCT {
    id: c.id,
    name: c.name,
    definition: c.definition
  }) AS categories,

  collect(DISTINCT {
    id: t.id,
    name: t.name,
    definition: t.definition,
    support_status: t.support_status
  }) AS threats,

  collect(DISTINCT {
    id: ku.id,
    title: ku.title,
    claim: ku.claim,
    explanation: ku.explanation,
    recommended_actions: ku.recommended_actions,
    evidence_strength: ku.evidence_strength
  }) AS knowledge_units,

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

LIMIT $limit
"""


RETRIEVE_BY_QUESTION_TEMPLATE = """
MATCH (qt:QuestionTemplate)
WHERE toLower(qt.text) CONTAINS toLower($keyword)

MATCH (ku:KnowledgeUnit)-[:HAS_QUESTION_TEMPLATE]->(qt)
OPTIONAL MATCH (ku)-[:IN_CATEGORY]->(c:CyberHygieneCategory)
OPTIONAL MATCH (ku)-[:ADDRESSES_THREAT]->(t:Threat)
OPTIONAL MATCH (ku)-[:RECOMMENDS_PRACTICE]->(p:Practice)
OPTIONAL MATCH (ku)-[:HAS_EVIDENCE]->(e:Evidence)-[:FROM_SOURCE]->(s:Source)
OPTIONAL MATCH (ku)-[:HAS_VALIDITY_FACT]->(vf:ValidityFact)
OPTIONAL MATCH (ku)-[:HAS_TRACEABILITY_REQUIREMENT]->(tr:TraceabilityRequirement)
OPTIONAL MATCH (ku)-[:HAS_ANSWER_GUIDANCE]->(g:AgentAnswerGuidance)

RETURN
  qt.text AS matched_question_template,

  collect(DISTINCT {
    id: ku.id,
    title: ku.title,
    claim: ku.claim,
    explanation: ku.explanation,
    recommended_actions: ku.recommended_actions,
    evidence_strength: ku.evidence_strength
  }) AS knowledge_units,

  collect(DISTINCT {
    id: c.id,
    name: c.name,
    definition: c.definition
  }) AS categories,

  collect(DISTINCT {
    id: t.id,
    name: t.name,
    definition: t.definition,
    support_status: t.support_status
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

LIMIT $limit
"""


RETRIEVE_GENERAL_DEFINITION = """
MATCH (ku:KnowledgeUnit {id: "KU-CYBER-HYGIENE-DEFINITION-001"})
OPTIONAL MATCH (ku)-[:IN_CATEGORY]->(c:CyberHygieneCategory)
OPTIONAL MATCH (ku)-[:HAS_EVIDENCE]->(e:Evidence)-[:FROM_SOURCE]->(s:Source)
OPTIONAL MATCH (ku)-[:HAS_VALIDITY_FACT]->(vf:ValidityFact)
OPTIONAL MATCH (ku)-[:HAS_TRACEABILITY_REQUIREMENT]->(tr:TraceabilityRequirement)
OPTIONAL MATCH (ku)-[:HAS_ANSWER_GUIDANCE]->(g:AgentAnswerGuidance)

RETURN
  collect(DISTINCT {
    id: ku.id,
    title: ku.title,
    claim: ku.claim,
    explanation: ku.explanation,
    recommended_actions: ku.recommended_actions,
    evidence_strength: ku.evidence_strength
  }) AS knowledge_units,

  collect(DISTINCT {
    id: c.id,
    name: c.name,
    definition: c.definition
  }) AS categories,

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

LIMIT $limit
"""

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

FULLTEXT_SEARCH_QUESTION_TEMPLATES = """
CALL db.index.fulltext.queryNodes("question_template_fulltext", $query)
YIELD node, score
MATCH (ku:KnowledgeUnit)-[:HAS_QUESTION_TEMPLATE]->(node)
RETURN DISTINCT ku.id AS ku_id, ku.title AS title, score, "QuestionTemplate" AS match_type
ORDER BY score DESC
LIMIT $limit
"""


FULLTEXT_SEARCH_KNOWLEDGE_UNITS = """
CALL db.index.fulltext.queryNodes("knowledge_unit_fulltext", $query)
YIELD node, score
RETURN DISTINCT node.id AS ku_id, node.title AS title, score, "KnowledgeUnit" AS match_type
ORDER BY score DESC
LIMIT $limit
"""


FULLTEXT_SEARCH_PRACTICES = """
CALL db.index.fulltext.queryNodes("practice_fulltext", $query)
YIELD node, score
MATCH (ku:KnowledgeUnit)-[:RECOMMENDS_PRACTICE]->(node)
RETURN DISTINCT ku.id AS ku_id, ku.title AS title, score, "Practice" AS match_type
ORDER BY score DESC
LIMIT $limit
"""


FULLTEXT_SEARCH_THREATS = """
CALL db.index.fulltext.queryNodes("threat_fulltext", $query)
YIELD node, score
MATCH (ku:KnowledgeUnit)-[:ADDRESSES_THREAT]->(node)
RETURN DISTINCT ku.id AS ku_id, ku.title AS title, score, "Threat" AS match_type
ORDER BY score DESC
LIMIT $limit
"""


FULLTEXT_SEARCH_CATEGORIES = """
CALL db.index.fulltext.queryNodes("category_fulltext", $query)
YIELD node, score
MATCH (ku:KnowledgeUnit)-[:IN_CATEGORY]->(node)
RETURN DISTINCT ku.id AS ku_id, ku.title AS title, score, "Category" AS match_type
ORDER BY score DESC
LIMIT $limit
"""