"""Retrieval layer for Neo.

Retrieval is vector-first and graph-grounded:
  1. embed the user question with the local Ollama model,
  2. find the nearest KnowledgeUnits via the Neo4j native vector index,
  3. hydrate each KU's full graph context (evidence, sources, practices,
     threats, guidance, traceability) with a safe predefined Cypher template.

It does not ask the LLM to generate Cypher.
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase

from src.retrieval.embeddings import embed_query
from src.retrieval.templates import (
    RETRIEVE_BY_KU_IDS,
    VECTOR_SEARCH_KNOWLEDGE_UNITS,
)
from src.schema.graph_schema import KNOWLEDGE_UNIT_VECTOR_INDEX

DEFAULT_TOP_K = 5
DEFAULT_SIMILARITY_FLOOR = 0.0


def get_driver():
    load_dotenv()

    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    if not uri or not username or not password:
        raise RuntimeError(
            "Missing Neo4j environment variables: "
            "NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD"
        )

    return GraphDatabase.driver(uri, auth=(username, password))


def run_query(query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    parameters = parameters or {}

    driver = get_driver()
    try:
        with driver.session() as session:
            result = session.run(query, parameters)
            return [record.data() for record in result]
    finally:
        driver.close()


def retrieve_by_ku_ids(ku_ids: list[str], limit: int = DEFAULT_TOP_K) -> list[dict[str, Any]]:
    """Hydrate full graph context for the given KU ids, preserving their order."""
    return run_query(RETRIEVE_BY_KU_IDS, {"ku_ids": ku_ids, "limit": limit})


def vector_search_ku_ids(question: str, top_k: int, floor: float) -> list[str]:
    """Return KU ids whose embeddings are nearest the question, above the floor.

    Results stay in similarity order (closest first).
    """
    query_vector = embed_query(question)

    hits = run_query(
        VECTOR_SEARCH_KNOWLEDGE_UNITS,
        {
            "index_name": KNOWLEDGE_UNIT_VECTOR_INDEX,
            "top_k": top_k,
            "query_vector": query_vector,
        },
    )

    ku_ids: list[str] = []
    for hit in hits:
        ku_id = hit.get("ku_id")
        score = hit.get("score") or 0.0

        if ku_id and score >= floor:
            ku_ids.append(ku_id)

    return ku_ids


def retrieve_context(question: str, limit: int = DEFAULT_TOP_K) -> list[dict[str, Any]]:
    """Retrieve graph context for a user question via vector search.

    Embeds the question, finds the nearest KnowledgeUnits through the vector
    index, then hydrates their full graph context. Returns an empty list when
    nothing clears the similarity floor, which lets Neo decline gracefully.
    """
    load_dotenv()

    top_k = int(os.getenv("RETRIEVAL_TOP_K", limit))
    floor = float(os.getenv("RETRIEVAL_SIMILARITY_FLOOR", DEFAULT_SIMILARITY_FLOOR))

    ku_ids = vector_search_ku_ids(question, top_k=top_k, floor=floor)

    if not ku_ids:
        return []

    return retrieve_by_ku_ids(ku_ids, limit=top_k)