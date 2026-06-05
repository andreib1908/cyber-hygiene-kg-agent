"""Embedding utilities for Neo (local, via Ollama).

Retrieval is vector-first and graph-grounded:
  1. each KnowledgeUnit is embedded once at ingestion,
  2. the user's question is embedded at query time,
  3. the nearest KUs are found through the Neo4j native vector index, after
     which the knowledge graph supplies all grounding (evidence, sources,
     citations).

This keeps the whole pipeline local while combining vector search with the
knowledge graph.

nomic-embed-text is trained with task prefixes:
  - 'search_document:' for stored documents
  - 'search_query:'    for queries
Applying them improves asymmetric (query <-> document) retrieval quality, so we
add them here rather than leaving it to chance.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
from langchain_ollama import OllamaEmbeddings

DOC_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "

DOCUMENT_FIELDS = ("title", "claim", "explanation")


@lru_cache(maxsize=1)
def get_embedder() -> OllamaEmbeddings:
    """Create (once) the local Ollama embedding client."""
    load_dotenv()

    model = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    return OllamaEmbeddings(model=model, base_url=base_url)


def build_ku_document(ku: dict[str, Any]) -> str:
    """Build the text that represents a KnowledgeUnit for embedding.

    Combines the title, claim, explanation, and all question templates so the
    embedding captures both what the KU asserts and the questions it answers.
    """
    parts: list[str] = []

    for field in DOCUMENT_FIELDS:
        value = ku.get(field)
        if value:
            parts.append(str(value).strip())

    for template in ku.get("question_templates") or []:
        if template:
            parts.append(str(template).strip())

    return "\n".join(parts)


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed KnowledgeUnit documents (applies the document prefix)."""
    embedder = get_embedder()
    prefixed = [f"{DOC_PREFIX}{text}" for text in texts]
    return embedder.embed_documents(prefixed)


def embed_query(text: str) -> list[float]:
    """Embed a user question (applies the query prefix)."""
    embedder = get_embedder()
    return embedder.embed_query(f"{QUERY_PREFIX}{text}")