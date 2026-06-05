"""Retrieval layer for Neo.

This module runs safe predefined Cypher templates against Neo4j.
It does not ask the LLM to generate Cypher.
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase

from src.retrieval.templates import (
    FULLTEXT_SEARCH_KNOWLEDGE_UNITS,
    FULLTEXT_SEARCH_PRACTICES,
    FULLTEXT_SEARCH_QUESTION_TEMPLATES,
    FULLTEXT_SEARCH_THREATS,
    RETRIEVE_BY_CATEGORY,
    RETRIEVE_BY_KU_IDS,
    RETRIEVE_BY_PRACTICE,
    RETRIEVE_BY_QUESTION_TEMPLATE,
    RETRIEVE_BY_THREAT,
    RETRIEVE_GENERAL_DEFINITION,
)

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


def retrieve_by_ku_ids(ku_ids: list[str], limit: int = 5) -> list[dict[str, Any]]:
    return run_query(RETRIEVE_BY_KU_IDS, {"ku_ids": ku_ids, "limit": limit})

def retrieve_context(question: str, limit: int = 5) -> list[dict[str, Any]]:
    """Retrieve context for a user question.

    Supports simple compound questions by retrieving context per subquestion.
    """
    subquestions = split_into_subquestions(question)

    all_context: list[dict[str, Any]] = []
    seen_ku_ids: set[str] = set()

    for subquestion in subquestions:
        sub_context = retrieve_context_for_single_question(subquestion, limit=1)

        for record in sub_context:
            ku_id = record.get("ku_id")

            if not ku_id:
                knowledge_units = record.get("knowledge_units", [])
                if knowledge_units:
                    ku_id = knowledge_units[0].get("id")

            if not ku_id or ku_id in seen_ku_ids:
                continue

            seen_ku_ids.add(ku_id)
            all_context.append(record)

            if len(all_context) >= limit:
                break

        if len(all_context) >= limit:
            break

    return all_context
