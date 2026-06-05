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


def retrieve_by_threat(keyword: str, limit: int = 5) -> list[dict[str, Any]]:
    return run_query(RETRIEVE_BY_THREAT, {"keyword": keyword, "limit": limit})


def retrieve_by_category(keyword: str, limit: int = 5) -> list[dict[str, Any]]:
    return run_query(RETRIEVE_BY_CATEGORY, {"keyword": keyword, "limit": limit})


def retrieve_by_practice(keyword: str, limit: int = 5) -> list[dict[str, Any]]:
    return run_query(RETRIEVE_BY_PRACTICE, {"keyword": keyword, "limit": limit})


def retrieve_by_question_template(keyword: str, limit: int = 5) -> list[dict[str, Any]]:
    return run_query(RETRIEVE_BY_QUESTION_TEMPLATE, {"keyword": keyword, "limit": limit})


def retrieve_general_definition(limit: int = 5) -> list[dict[str, Any]]:
    return run_query(RETRIEVE_GENERAL_DEFINITION, {"limit": limit})

def retrieve_by_ku_ids(ku_ids: list[str], limit: int = 5) -> list[dict[str, Any]]:
    return run_query(RETRIEVE_BY_KU_IDS, {"ku_ids": ku_ids, "limit": limit})

def escape_lucene_query(text: str) -> str:
    """Basic escaping for Neo4j/Lucene full-text search.

    Keeps the query simple and avoids special-character weirdness.
    """
    special_chars = ['\\', '+', '-', '!', '(', ')', ':', '^', '[', ']', '"', '{', '}', '~', '*', '?', '|', '&', '/']
    cleaned = text
    for char in special_chars:
        cleaned = cleaned.replace(char, " ")

    return " ".join(cleaned.split())


def fulltext_search_ku_candidates(question: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search full-text indexes and return candidate KU IDs.

    Search priority:
    1. Question templates: strongest signal, because they are curated expected questions.
    2. Practices: strong signal for practical user questions.
    3. Threats: strong signal for risk/protection questions.
    4. Knowledge units: useful but broader.

    Category full-text search is intentionally excluded from this first pass
    because categories are broad and tend to retrieve too many conceptual KUs.
    """
    query = escape_lucene_query(question)

    if not query:
        return []

    weighted_searches = [
        (FULLTEXT_SEARCH_QUESTION_TEMPLATES, 4.0),
        (FULLTEXT_SEARCH_PRACTICES, 3.0),
        (FULLTEXT_SEARCH_THREATS, 2.5),
        (FULLTEXT_SEARCH_KNOWLEDGE_UNITS, 1.5),
    ]

    candidates: dict[str, dict[str, Any]] = {}

    for search_query, weight in weighted_searches:
        rows = run_query(search_query, {"query": query, "limit": limit})
        for row in rows:
            ku_id = row.get("ku_id")
            if not ku_id:
                continue

            raw_score = float(row.get("score", 0) or 0)
            weighted_score = raw_score * weight

            candidate = {
                **row,
                "raw_score": raw_score,
                "weighted_score": weighted_score,
                "weight": weight,
            }

            existing = candidates.get(ku_id)
            if existing is None or weighted_score > existing.get("weighted_score", 0):
                candidates[ku_id] = candidate

    return sorted(
        candidates.values(),
        key=lambda item: item.get("weighted_score", 0),
        reverse=True,
    )[:limit]

def is_practical_question(question: str) -> bool:
    """Detect whether the user is asking for practical advice or action."""
    q = question.lower()

    practical_markers = [
        "how do i",
        "how can i",
        "how should i",
        "what should i do",
        "what can i do",
        "how can users",
        "how should users",
        "protect myself",
        "protect against",
        "guard myself",
        "prevent",
        "check whether",
        "check if",
        "what should users look for",
        "received this",
        "weird email",
        "strange email",
        "asking me to",
        "send him",
        "hack my computer",
    ]

    return any(marker in q for marker in practical_markers)


def has_practical_guidance(record: dict[str, Any]) -> bool:
    """Return True if a retrieved context record contains practical answer guidance."""
    for guidance in record.get("answer_guidance", []):
        style = guidance.get("answer_style", "")
        if "practical" in style:
            return True

    return False


def filter_practical_context(
    question: str,
    context: list[dict[str, Any]],
    limit: int = 2,
) -> list[dict[str, Any]]:
    """Prefer category-relevant and practical KUs for user questions."""
    if not context:
        return context

    # First, remove context records from irrelevant categories if possible.
    context = filter_by_detected_category(question, context)

    # Then, for practical questions, prefer practical advice KUs.
    if is_practical_question(question):
        practical_context = [
            record for record in context if has_practical_guidance(record)
        ]

        if practical_context:
            return practical_context[:limit]

    return context[:limit]

def detect_relevant_categories(question: str) -> list[str]:
    """Detect broad cyber hygiene categories from the user question.

    This is not static answer mapping. It only identifies likely category focus.
    """
    q = question.lower()

    category_markers = {
        "CAT-EMAIL-MESSAGING": [
            "email",
            "sender",
            "domain",
            "header",
            "subject",
            "attachment",
            "hyperlink",
            "link",
            "message",
            "phishing",
            "e-fraud",
            "scam",
            "strange email",
            "weird email",
        ],
        "CAT-TRANSMISSION": [
            "website",
            "connection",
            "ssl",
            "certificate",
            "browser lock",
            "lock icon",
            "public wifi",
            "public wi-fi",
            "secure website",
        ],
        "CAT-AUTH-CREDENTIAL": [
            "password",
            "credential",
            "login",
            "mfa",
            "2fa",
            "two-factor",
            "multifactor",
            "default password",
        ],
        "CAT-STORAGE-DEVICE": [
            "device",
            "computer",
            "antivirus",
            "virus scan",
            "backup",
            "firewall",
            "software update",
            "operating system",
            "malware",
            "storage",
        ],
        "CAT-SOCIAL-MEDIA": [
            "social media",
            "friend request",
            "privacy setting",
            "location leak",
            "post",
            "profile",
        ],
    }

    detected = []

    for category_id, markers in category_markers.items():
        if any(marker in q for marker in markers):
            detected.append(category_id)

    # Email/messaging should dominate when the user describes a suspicious email,
    # even if the message also mentions hacking or computer compromise.
    if "CAT-EMAIL-MESSAGING" in detected:
        return ["CAT-EMAIL-MESSAGING"]

    return detected


def record_has_category(record: dict[str, Any], category_ids: list[str]) -> bool:
    """Return True if a context record belongs to one of the detected categories."""
    for category in record.get("categories", []):
        if category.get("id") in category_ids:
            return True

    return False


def filter_by_detected_category(
    question: str,
    context: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Prefer context records whose categories match the user's apparent focus."""
    category_ids = detect_relevant_categories(question)

    if not category_ids:
        return context

    matching = [record for record in context if record_has_category(record, category_ids)]

    if matching:
        return matching

    return context

def retrieve_by_fulltext(question: str, limit: int = 5) -> list[dict[str, Any]]:
    """Retrieve graph context using full-text search and practical filtering.

    If a curated QuestionTemplate matches, trust the best matching template first.
    This prevents broad KUs from polluting specific benchmark-style questions.
    """
    candidates = fulltext_search_ku_candidates(question, limit=limit)

    if not candidates:
        return []

    # If a curated question template matched, prefer the single best template match.
    question_template_candidates = [
        candidate
        for candidate in candidates
        if candidate.get("match_type") == "QuestionTemplate"
    ]

    if question_template_candidates:
        best = question_template_candidates[0]
        return retrieve_by_ku_ids([best["ku_id"]], limit=1)

    # Otherwise use top candidates, then filter.
    ku_ids = [candidate["ku_id"] for candidate in candidates if candidate.get("ku_id")]

    if not ku_ids:
        return []

    context = retrieve_by_ku_ids(ku_ids, limit=limit)
    return filter_practical_context(question, context, limit=min(limit, 2))



def retrieve_context(question: str, limit: int = 5) -> list[dict[str, Any]]:
    q = question.lower()

    # 1. Very high-confidence direct routes.
    if "what is cyber hygiene" in q or "define cyber hygiene" in q:
        return retrieve_general_definition(limit=limit)

    if (
        "five dimensions" in q
        or "5 dimensions" in q
        or "safety acronym" in q
        or "cyber hygiene inventory" in q
    ):
        return retrieve_by_ku_ids(["KU-CHI-FIVE-DIMENSIONS-001"], limit=limit)

    if (
        "organization" in q
        or "organisational" in q
        or "organizational" in q
        or "employee" in q
        or "employees" in q
        or "training" in q
        or "policies" in q
        or "policy" in q
        or "company" in q
        or "companies" in q
    ):
        return retrieve_by_ku_ids(
            [
                "KU-ORG-TRAINING-POLICIES-001",
                "KU-ORG-MEASURES-INFLUENCE-001",
            ],
            limit=limit,
        )

    # 2. Dynamic full-text search.
    fulltext_context = retrieve_by_fulltext(question, limit=limit)
    if fulltext_context:
        return fulltext_context

    # 3. Nothing found.
    return []

