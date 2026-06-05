"""Build the Neo cyber hygiene knowledge graph in Neo4j.

This script imports the curated cyber hygiene KB JSON into Neo4j.

Expected input:
    data/knowledge_base/cyber_hygiene_kb_data.json

Run from project root:
    python -m src.ingestion.build_graph

Or:
    python src/ingestion/build_graph.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

# Allow running both as module and as direct script.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.schema.graph_schema import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_SIMILARITY,
    KNOWLEDGE_UNIT_VECTOR_INDEX,
    SEARCH_INDEXES,
    UNIQUE_CONSTRAINTS,
)
from src.retrieval.embeddings import build_ku_document, embed_documents

# Paths

KB_DATA_PATH = PROJECT_ROOT / "data" / "knowledge_base" / "cyber_hygiene_kb_data.json"
ENV_PATH = PROJECT_ROOT / ".env"
LEGACY_ENV_PATH = PROJECT_ROOT / "neo4j_db.env"


# Terminal formatting

BOLD = "\033[1m"
RESET = "\033[0m"
GREEN = "\033[92m"
RED = "\033[91m"
ORANGE = "\033[38;5;214m"


# Helpers

def load_environment() -> None:
    """Load .env first, then legacy neo4j_db.env as fallback."""
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH)
    elif LEGACY_ENV_PATH.exists():
        load_dotenv(LEGACY_ENV_PATH)
    else:
        raise RuntimeError(
            "No .env or neo4j_db.env file found. "
            "Please create one with NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD."
        )


def get_driver():
    """Create a Neo4j driver from environment variables."""
    load_environment()

    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    if not uri or not username or not password:
        raise RuntimeError(
            "Missing Neo4j credentials. Required variables: "
            "NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD."
        )

    return GraphDatabase.driver(uri, auth=(username, password))


def load_kb_data() -> dict[str, Any]:
    """Load the cyber hygiene KB JSON."""
    if not KB_DATA_PATH.exists():
        raise FileNotFoundError(f"Could not find KB data file: {KB_DATA_PATH}")

    with open(KB_DATA_PATH, encoding="utf-8") as file:
        return json.load(file)


def as_list(value: Any) -> list[Any]:
    """Return value as a list, preserving existing lists."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def compact_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Remove nested dict/list fields that should not be stored directly."""
    return {
        key: value
        for key, value in data.items()
        if not isinstance(value, (dict, list))
    }


# Schema setup

def clear_graph(tx) -> None:
    """Delete all nodes and relationships from the current database."""
    tx.run("MATCH (n) DETACH DELETE n")


def create_constraints(tx) -> None:
    """Create uniqueness constraints from graph_schema.py."""
    for name, (label, prop) in UNIQUE_CONSTRAINTS.items():
        tx.run(
            f"""
            CREATE CONSTRAINT {name} IF NOT EXISTS
            FOR (n:{label})
            REQUIRE n.{prop} IS UNIQUE
            """
        )


def create_indexes(tx) -> None:
    """Create search indexes from graph_schema.py."""
    for name, (label, prop) in SEARCH_INDEXES.items():
        tx.run(
            f"""
            CREATE INDEX {name} IF NOT EXISTS
            FOR (n:{label})
            ON (n.{prop})
            """
        )

def create_vector_index(tx) -> None:
    """Create the native vector index over KnowledgeUnit embeddings."""
    tx.run(
        f"""
        CREATE VECTOR INDEX {KNOWLEDGE_UNIT_VECTOR_INDEX} IF NOT EXISTS
        FOR (ku:KnowledgeUnit)
        ON (ku.embedding)
        OPTIONS {{ indexConfig: {{
            `vector.dimensions`: {EMBEDDING_DIMENSIONS},
            `vector.similarity_function`: '{EMBEDDING_SIMILARITY}'
        }} }}
        """
    )


def set_ku_embedding(tx, ku_id: str, embedding: list[float]) -> None:
    tx.run(
        "MATCH (ku:KnowledgeUnit {id: $id}) SET ku.embedding = $embedding",
        id=ku_id,
        embedding=embedding,
    )


def embed_and_store_knowledge_units(session, knowledge_units: list[dict[str, Any]]) -> None:
    """Embed each KnowledgeUnit document and store the vector on its node."""
    documents = [build_ku_document(ku) for ku in knowledge_units]
    vectors = embed_documents(documents)

    for ku, vector in zip(knowledge_units, vectors):
        ku_id = ku.get("id")
        if ku_id:
            session.execute_write(set_ku_embedding, ku_id, vector)

def create_source(tx, source: dict[str, Any]) -> None:
    tx.run(
        """
        MERGE (s:Source {id: $id})
        SET s.citation_key = $citation_key,
            s.authors = $authors,
            s.year = $year,
            s.title = $title,
            s.venue = $venue,
            s.volume = $volume,
            s.number = $number,
            s.pages = $pages,
            s.peer_reviewed = $peer_reviewed,
            s.doi = $doi,
            s.url = $url,
            s.notes = $notes
        """,
        **source,
    )


def create_category(tx, category: dict[str, Any]) -> None:
    tx.run(
        """
        MERGE (c:CyberHygieneCategory {id: $id})
        SET c.name = $name,
            c.definition = $definition,
            c.examples = $examples,
            c.source_ids = $source_ids

        WITH c
        UNWIND $source_ids AS source_id
        MATCH (s:Source {id: source_id})
        MERGE (s)-[:SUPPORTS_CATEGORY]->(c)
        """,
        id=category.get("id"),
        name=category.get("name"),
        definition=category.get("definition"),
        examples=as_list(category.get("examples")),
        source_ids=as_list(category.get("source_ids")),
    )


def create_threat(tx, threat: dict[str, Any]) -> None:
    tx.run(
        """
        MERGE (t:Threat {id: $id})
        SET t.name = $name,
            t.definition = $definition,
            t.related_categories = $related_categories,
            t.source_ids = $source_ids,
            t.support_status = $support_status,
            t.support_notes = $support_notes

        WITH t
        UNWIND $related_categories AS category_id
        MATCH (c:CyberHygieneCategory {id: category_id})
        MERGE (t)-[:RELATED_TO_CATEGORY]->(c)

        WITH t
        UNWIND $source_ids AS source_id
        MATCH (s:Source {id: source_id})
        MERGE (t)-[:SUPPORTED_BY_SOURCE]->(s)
        MERGE (s)-[:SUPPORTS_THREAT]->(t)
        """,
        id=threat.get("id"),
        name=threat.get("name"),
        definition=threat.get("definition"),
        related_categories=as_list(threat.get("related_categories")),
        source_ids=as_list(threat.get("source_ids")),
        support_status=threat.get("support_status"),
        support_notes=threat.get("support_notes"),
    )


def create_practice(tx, practice: dict[str, Any]) -> None:
    tx.run(
        """
        MERGE (p:Practice {id: $id})
        SET p.name = $name,
            p.description = $description,
            p.category_id = $category_id,
            p.mitigates = $mitigates,
            p.source_ids = $source_ids

        WITH p
        OPTIONAL MATCH (c:CyberHygieneCategory {id: $category_id})
        FOREACH (_ IN CASE WHEN c IS NULL THEN [] ELSE [1] END |
            MERGE (p)-[:BELONGS_TO_CATEGORY]->(c)
        )

        WITH p
        UNWIND $mitigates AS threat_id
        MATCH (t:Threat {id: threat_id})
        MERGE (p)-[:MITIGATES]->(t)

        WITH p
        UNWIND $source_ids AS source_id
        MATCH (s:Source {id: source_id})
        MERGE (p)-[:SUPPORTED_BY_SOURCE]->(s)
        MERGE (s)-[:SUPPORTS_PRACTICE]->(p)
        """,
        id=practice.get("id"),
        name=practice.get("name"),
        description=practice.get("description"),
        category_id=practice.get("category_id"),
        mitigates=as_list(practice.get("mitigates")),
        source_ids=as_list(practice.get("source_ids")),
    )


def create_knowledge_unit_base(tx, ku: dict[str, Any]) -> None:
    tx.run(
        """
        MERGE (ku:KnowledgeUnit {id: $id})
        SET ku.title = $title,
            ku.category_id = $category_id,
            ku.threat_ids = $threat_ids,
            ku.practice_ids = $practice_ids,
            ku.claim = $claim,
            ku.explanation = $explanation,
            ku.recommended_actions = $recommended_actions,
            ku.evidence_strength = $evidence_strength

        WITH ku
        OPTIONAL MATCH (c:CyberHygieneCategory {id: $category_id})
        FOREACH (_ IN CASE WHEN c IS NULL THEN [] ELSE [1] END |
            MERGE (ku)-[:IN_CATEGORY]->(c)
        )

        WITH ku
        UNWIND $threat_ids AS threat_id
        MATCH (t:Threat {id: threat_id})
        MERGE (ku)-[:ADDRESSES_THREAT]->(t)

        WITH ku
        UNWIND $practice_ids AS practice_id
        MATCH (p:Practice {id: practice_id})
        MERGE (ku)-[:RECOMMENDS_PRACTICE]->(p)
        """,
        id=ku.get("id"),
        title=ku.get("title"),
        category_id=ku.get("category_id"),
        threat_ids=as_list(ku.get("threat_ids")),
        practice_ids=as_list(ku.get("practice_ids")),
        claim=ku.get("claim"),
        explanation=ku.get("explanation"),
        recommended_actions=as_list(ku.get("recommended_actions")),
        evidence_strength=ku.get("evidence_strength"),
    )


def create_knowledge_unit_source_support(tx, ku: dict[str, Any]) -> None:
    """Connect KU to all sources used by its evidence."""
    ku_id = ku.get("id")
    source_ids = sorted(
        {
            evidence.get("source_id")
            for evidence in as_list(ku.get("evidence"))
            if evidence.get("source_id")
        }
    )

    tx.run(
        """
        MATCH (ku:KnowledgeUnit {id: $ku_id})
        UNWIND $source_ids AS source_id
        MATCH (s:Source {id: source_id})
        MERGE (s)-[:SUPPORTS_KNOWLEDGE_UNIT]->(ku)
        """,
        ku_id=ku_id,
        source_ids=source_ids,
    )


def create_evidence(tx, ku_id: str, evidence: dict[str, Any]) -> None:
    claim_location = evidence.get("claim_location") or {}

    tx.run(
        """
        MATCH (ku:KnowledgeUnit {id: $ku_id})
        MERGE (e:Evidence {evidence_id: $evidence_id})
        SET e.source_id = $source_id,
            e.citation_key = $citation_key,
            e.support_type = $support_type,
            e.exact_supporting_text = $exact_supporting_text,
            e.page = $page,
            e.section = $section,
            e.paragraph = $paragraph,
            e.claim_page = $claim_page,
            e.claim_section = $claim_section,
            e.claim_paragraph = $claim_paragraph

        MERGE (ku)-[:HAS_EVIDENCE]->(e)

        WITH e
        OPTIONAL MATCH (s:Source {id: $source_id})
        FOREACH (_ IN CASE WHEN s IS NULL THEN [] ELSE [1] END |
            MERGE (e)-[:FROM_SOURCE]->(s)
        )
        """,
        ku_id=ku_id,
        evidence_id=evidence.get("evidence_id"),
        source_id=evidence.get("source_id"),
        citation_key=evidence.get("citation_key"),
        support_type=evidence.get("support_type"),
        exact_supporting_text=evidence.get("exact_supporting_text"),
        page=evidence.get("page"),
        section=evidence.get("section"),
        paragraph=evidence.get("paragraph"),
        claim_page=claim_location.get("page"),
        claim_section=claim_location.get("section"),
        claim_paragraph=claim_location.get("paragraph"),
    )


def create_validity_fact(tx, ku_id: str, fact: dict[str, Any]) -> None:
    tx.run(
        """
        MATCH (ku:KnowledgeUnit {id: $ku_id})
        MERGE (vf:ValidityFact {fact_id: $fact_id})
        SET vf.fact = $fact,
            vf.source_id = $source_id,
            vf.evidence_id = $evidence_id

        MERGE (ku)-[:HAS_VALIDITY_FACT]->(vf)

        WITH vf
        OPTIONAL MATCH (e:Evidence {evidence_id: $evidence_id})
        FOREACH (_ IN CASE WHEN e IS NULL THEN [] ELSE [1] END |
            MERGE (vf)-[:SUPPORTED_BY_EVIDENCE]->(e)
        )

        WITH vf
        OPTIONAL MATCH (s:Source {id: $source_id})
        FOREACH (_ IN CASE WHEN s IS NULL THEN [] ELSE [1] END |
            MERGE (vf)-[:SUPPORTED_BY_SOURCE]->(s)
        )
        """,
        ku_id=ku_id,
        fact_id=fact.get("fact_id"),
        fact=fact.get("fact"),
        source_id=fact.get("source_id"),
        evidence_id=fact.get("evidence_id"),
    )


def create_traceability_requirement(tx, ku_id: str, traceability: dict[str, Any]) -> None:
    traceability_id = f"TR-{ku_id}"

    tx.run(
        """
        MATCH (ku:KnowledgeUnit {id: $ku_id})
        MERGE (tr:TraceabilityRequirement {id: $traceability_id})
        SET tr.requires_citation = $requires_citation,
            tr.acceptable_sources = $acceptable_sources,
            tr.citation_granularity = $citation_granularity,
            tr.minimum_traceability_requirement = $minimum_traceability_requirement

        MERGE (ku)-[:HAS_TRACEABILITY_REQUIREMENT]->(tr)
        """,
        ku_id=ku_id,
        traceability_id=traceability_id,
        requires_citation=traceability.get("requires_citation"),
        acceptable_sources=as_list(traceability.get("acceptable_sources")),
        citation_granularity=traceability.get("citation_granularity"),
        minimum_traceability_requirement=traceability.get(
            "minimum_traceability_requirement"
        ),
    )


def create_agent_answer_guidance(tx, ku_id: str, guidance: dict[str, Any]) -> None:
    guidance_id = f"AAG-{ku_id}"

    tx.run(
        """
        MATCH (ku:KnowledgeUnit {id: $ku_id})
        MERGE (g:AgentAnswerGuidance {id: $guidance_id})
        SET g.answer_style = $answer_style,
            g.must_include = $must_include,
            g.avoid_claims = $avoid_claims

        MERGE (ku)-[:HAS_ANSWER_GUIDANCE]->(g)
        """,
        ku_id=ku_id,
        guidance_id=guidance_id,
        answer_style=guidance.get("answer_style"),
        must_include=as_list(guidance.get("must_include")),
        avoid_claims=as_list(guidance.get("avoid_claims")),
    )


def create_question_templates(tx, ku_id: str, question_templates: list[str]) -> None:
    rows = [
        {
            "id": f"QT-{ku_id}-{index:03d}",
            "text": question,
        }
        for index, question in enumerate(question_templates, start=1)
    ]

    tx.run(
        """
        MATCH (ku:KnowledgeUnit {id: $ku_id})
        UNWIND $rows AS row
        MERGE (qt:QuestionTemplate {id: row.id})
        SET qt.text = row.text
        MERGE (ku)-[:HAS_QUESTION_TEMPLATE]->(qt)
        """,
        ku_id=ku_id,
        rows=rows,
    )


def create_knowledge_unit_details(tx, ku: dict[str, Any]) -> None:
    ku_id = ku.get("id")

    for evidence in as_list(ku.get("evidence")):
        create_evidence(tx, ku_id, evidence)

    for fact in as_list(ku.get("validity_facts")):
        create_validity_fact(tx, ku_id, fact)

    if ku.get("traceability"):
        create_traceability_requirement(tx, ku_id, ku["traceability"])

    if ku.get("agent_answer_guidance"):
        create_agent_answer_guidance(tx, ku_id, ku["agent_answer_guidance"])

    create_question_templates(tx, ku_id, as_list(ku.get("question_templates")))

    create_knowledge_unit_source_support(tx, ku)


# Main import

def main(clear_existing: bool = True) -> None:
    start_time = time.time()
    data = load_kb_data()

    sources = as_list(data.get("sources"))
    categories = as_list(data.get("cyber_hygiene_categories"))
    threats = as_list(data.get("threats"))
    practices = as_list(data.get("practices"))
    knowledge_units = as_list(data.get("knowledge_units"))

    print(f"\n{BOLD}Building Neo cyber hygiene knowledge graph...{RESET}")
    print(f"KB file: {KB_DATA_PATH}\n")

    driver = get_driver()

    try:
        with driver.session() as session:
            if clear_existing:
                print(f"{ORANGE}Clearing existing graph...{RESET}")
                session.execute_write(clear_graph)

            print("Creating constraints, indexes, and vector index...")
            session.execute_write(create_constraints)
            session.execute_write(create_indexes)
            session.execute_write(create_vector_index)

            print(f"Importing {len(sources)} sources...")
            for source in sources:
                session.execute_write(create_source, source)

            print(f"Importing {len(categories)} cyber hygiene categories...")
            for category in categories:
                session.execute_write(create_category, category)

            print(f"Importing {len(threats)} threats...")
            for threat in threats:
                session.execute_write(create_threat, threat)

            print(f"Importing {len(practices)} practices...")
            for practice in practices:
                session.execute_write(create_practice, practice)

            print(f"Importing {len(knowledge_units)} knowledge units...")
            for ku in knowledge_units:
                session.execute_write(create_knowledge_unit_base, ku)

            print("Importing evidence, validity facts, traceability, guidance, and question templates...")
            for ku in knowledge_units:
                session.execute_write(create_knowledge_unit_details, ku)

            print("Embedding knowledge units and storing vectors...")
            embed_and_store_knowledge_units(session, knowledge_units)
            
            counts = session.run(
                """
                MATCH (n)
                RETURN labels(n)[0] AS label, count(n) AS count
                ORDER BY label
                """
            ).data()

        elapsed = time.time() - start_time

        print(f"\n{GREEN}{BOLD}Import complete!{RESET}")
        for row in counts:
            print(f"  {row['label']:<28} {row['count']}")

        print(f"\n{BOLD}Duration:{RESET} {elapsed:.2f} seconds\n")

    except Neo4jError as error:
        print(f"{RED}Neo4j import failed:{RESET} {error}")
        raise
    finally:
        driver.close()


if __name__ == "__main__":
    main(clear_existing=True)