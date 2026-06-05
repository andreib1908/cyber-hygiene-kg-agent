"""Answer package construction for Neo.

This module converts raw retrieved graph context into a compact answer package.

The goal is to avoid sending the full graph context to the LLM. Instead, Python
selects the useful answer fields, while citation/traceability formatting is
handled deterministically outside the model.
"""

from __future__ import annotations

from typing import Any


MAX_SOURCE_ITEMS = 4


def _first_item(items: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Return the first dict from a list, or an empty dict."""
    if not items:
        return {}
    return items[0] or {}


def _as_list(value: Any) -> list[Any]:
    """Normalize optional/list-like values."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _is_empty_or_todo(value: Any) -> bool:
    """Return True if a paragraph/location value should be omitted."""
    if value is None:
        return True

    text = str(value).strip()
    if not text:
        return True

    return text.upper().startswith("TODO")


def _dedupe_preserve_order(values: list[Any]) -> list[Any]:
    """Remove duplicates while preserving order."""
    seen = set()
    result = []

    for value in values:
        marker = str(value)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(value)

    return result


def _build_ku_package(record: dict[str, Any]) -> dict[str, Any]:
    """Build a compact package for one retrieved KnowledgeUnit."""
    ku = _first_item(record.get("knowledge_units"))
    guidance = _first_item(record.get("answer_guidance"))

    recommended_actions = _as_list(ku.get("recommended_actions"))
    must_include = _as_list(guidance.get("must_include"))
    avoid_claims = _as_list(guidance.get("avoid_claims"))
    question_templates = _as_list(record.get("question_templates"))

    return {
        "id": ku.get("id"),
        "title": ku.get("title"),
        "answer_style": guidance.get("answer_style") or "concise_answer",
        "main_claim": ku.get("claim") or "",
        "brief_explanation": ku.get("explanation") or "",
        "allowed_recommendations": _dedupe_preserve_order(recommended_actions),
        "must_include": _dedupe_preserve_order(must_include),
        "avoid_claims": _dedupe_preserve_order(avoid_claims),
        "question_templates": _dedupe_preserve_order(question_templates),
    }


def build_answer_package(
    question: str,
    context: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a compact multi-KU answer package from retrieved graph context."""
    if not context:
        return {
            "question": question,
            "selected_knowledge_units": [],
            "global_limitations": [
                "The knowledge base does not contain enough evidence to answer this."
            ],
        }

    selected_kus = []
    seen_ku_ids = set()

    for record in context:
        ku_package = _build_ku_package(record)
        ku_id = ku_package.get("id")

        if not ku_id or ku_id in seen_ku_ids:
            continue

        seen_ku_ids.add(ku_id)
        selected_kus.append(ku_package)

    return {
        "question": question,
        "selected_knowledge_units": selected_kus
    }

# def _format_source_line(evidence: dict[str, Any]) -> str | None:
#     """Format one evidence item into Neo's required source format."""
#     evidence_id = evidence.get("evidence_id")
#     citation_key = evidence.get("citation_key")
#     source_id = evidence.get("source_id")
#     page = evidence.get("page")
#     section = evidence.get("section")
#     paragraph = evidence.get("paragraph")
#     year = evidence.get("year")

#     if not evidence_id:
#         return None

#     # We do not always have a clean academic citation string in the retrieved
#     # context yet, so use source_id/citation_key as fallback.
#     source_title = evidence.get("source_title") or ""

#     academic_citation = _infer_academic_citation(
#         citation_key=citation_key,
#         source_id=source_id,
#         year=year,
#         source_title=source_title,
#     )

#     parts = [
#         academic_citation,
#         citation_key,
#         source_id,
#     ]

#     if page not in (None, ""):
#         parts.append(f"page {page}")

#     if section:
#         parts.append(f'section "{section}"')

#     if not _is_empty_or_todo(paragraph):
#         parts.append(f'paragraph "{paragraph}"')

#     safe_parts = [str(part) for part in parts if part not in (None, "")]

#     return f"- {evidence_id} - ({', '.join(safe_parts)})"


def format_sources_used(
    context: list[dict[str, Any]],
    max_items: int = MAX_SOURCE_ITEMS,
) -> str:
    """Format the deterministic Sources used section from retrieved evidence."""
    if not context:
        return ""

    source_lines: list[str] = []
    seen_evidence_ids: set[str] = set()

    for record in context:
        evidence_items = _as_list(record.get("evidence"))

        # Prefer direct evidence first.
        evidence_items = sorted(
            evidence_items,
            key=lambda item: 0 if item.get("support_type") == "direct" else 1,
        )

        for evidence in evidence_items:
            evidence_id = evidence.get("evidence_id")
            if not evidence_id or evidence_id in seen_evidence_ids:
                continue

            line = _format_source_line(evidence)
            if not line:
                continue

            seen_evidence_ids.add(evidence_id)
            source_lines.append(line)

            if len(source_lines) >= max_items:
                break

        if len(source_lines) >= max_items:
            break

    if not source_lines:
        return ""

    return "Sources used:\n" + "\n".join(source_lines)


def append_sources_used(answer: str, sources_text: str) -> str:
    """Append deterministic sources to the model-generated answer."""
    clean_answer = answer.strip()

    # Remove model-generated source sections if it disobeys the prompt.
    forbidden_headings = [
        "Sources used:",
        "Sources:",
        "Citations:",
        "References:",
        "Traceability:",
    ]

    for heading in forbidden_headings:
        index = clean_answer.lower().find(heading.lower())
        if index != -1:
            clean_answer = clean_answer[:index].strip()

    if not sources_text:
        return clean_answer

    return f"{clean_answer}\n\n{sources_text}"

