"""Answer package construction for Neo.

This module converts raw retrieved graph context into a compact answer package.

The goal is to avoid sending the full graph context to the LLM. Instead, Python
selects the useful answer fields, while citation/traceability formatting is
handled deterministically outside the model.
"""

from __future__ import annotations

import os
from typing import Any


MAX_EVIDENCE_PER_KU = 3


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

def _sanitize_answer_style(style: str | None) -> str:
    """Strip the '...with_traceability_note' suffix from answer styles.

    That style reads to the model as an instruction to add a traceability note,
    which leaks internal ids / author-year citations into the answer body.
    """
    return (style or "concise_answer").replace("_with_traceability_note", "")

def _split_sentences(text: str) -> list[str]:
    """Split an answer into sentences and bullet lines for matching."""
    import re
    out: list[str] = []
    for chunk in re.split(r"(?<=[.!?])\s+", text.strip()):
        for line in chunk.split("\n"):
            line = line.strip(" -*•\t")
            if line:
                out.append(line)
    return out


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0

def _score_sources_against_answer(
    sources: list[dict[str, Any]], answer: str
) -> list[tuple[dict[str, Any], float]] | None:
    """Best cosine of each source to any answer sentence/bullet. None if embedder down."""
    if not sources:
        return []
    try:
        from src.retrieval.embeddings import embed_documents, embed_query
        sentences = _split_sentences(answer) or [answer]
        sentence_vectors = [embed_query(s) for s in sentences]
        passage_vectors = embed_documents([s.get("text") or "" for s in sources])
    except Exception:
        return None
    return [
        (src, max((_cosine(pv, sv) for sv in sentence_vectors), default=0.0))
        for src, pv in zip(sources, passage_vectors)
    ]


def _normalize_text(text: str | None) -> str:
    return " ".join((text or "").lower().split())


def _dedupe_sources_by_text(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse evidence items that quote identical source text (keeps the first)."""
    seen, out = set(), []
    for source in sources:
        key = _normalize_text(source.get("text"))
        if key and key in seen:
            continue
        seen.add(key)
        out.append(source)
    return out

def filter_sources_by_answer(sources, answer, floor, debug=False):
    """Drop declared evidence whose statement does not appear in the answer."""
    if not sources or not answer:
        return sources
    scored = _score_sources_against_answer(sources, answer)
    if scored is None:
        return sources
    kept = []
    for source, best in scored:
        keep = floor <= 0 or best >= floor
        if debug:
            print(f"[citation-filter] {source.get('evidence_id')} best={best:.3f} {'KEEP' if keep else 'DROP'}")
        if keep:
            kept.append(source)
    return kept or sources


def select_sources_by_relevance(context, answer, floor, debug=False, max_total=int(os.getenv("CITATION_MAX", "10"))):
    """Cite retrieved evidence whose content matches the answer — no model tag needed."""
    candidates, seen = [], set()
    for record in context:
        for evidence in _as_list(record.get("evidence")):
            eid = evidence.get("evidence_id")
            if eid and eid not in seen:
                seen.add(eid)
                candidates.append(evidence)
    scored = _score_sources_against_answer(candidates, answer)
    if scored is None:
        return select_sources_used(context)
    ranked = sorted(scored, key=lambda x: x[1], reverse=True)
    kept = []
    for source, best in ranked:
        keep = floor <= 0 or best >= floor
        if debug:
            print(f"[citation-relevance] {source.get('evidence_id')} best={best:.3f} {'KEEP' if keep else 'DROP'}")
        if keep:
            kept.append(source)

    kept = _dedupe_sources_by_text(kept)
    return kept[:max_total] if kept else select_sources_used(context)



def _build_ku_package(record: dict[str, Any]) -> dict[str, Any]:
    """Build a compact package for one retrieved KnowledgeUnit."""
    ku = _first_item(record.get("knowledge_units"))
    guidance = _first_item(record.get("answer_guidance"))

    recommended_actions = _as_list(ku.get("recommended_actions"))
    must_include = _as_list(guidance.get("must_include"))
    avoid_claims = _as_list(guidance.get("avoid_claims"))
    question_templates = _as_list(record.get("question_templates"))

    evidence_passages = []
    for e in _as_list(record.get("evidence")):
        evidence_id = e.get("evidence_id")
        text = e.get("text")
        if evidence_id and text:
            evidence_passages.append({"evidence_id": evidence_id, "text": text})

    return {
        "id": ku.get("id"),
        "title": ku.get("title"),
        "answer_style": _sanitize_answer_style(guidance.get("answer_style")),
        "main_claim": ku.get("claim") or "",
        "brief_explanation": ku.get("explanation") or "",
        "allowed_recommendations": _dedupe_preserve_order(recommended_actions),
        "must_include": _dedupe_preserve_order(must_include),
        "avoid_claims": _dedupe_preserve_order(avoid_claims),
        "question_templates": _dedupe_preserve_order(question_templates),
        "evidence": evidence_passages,
    }

def _record_ku_id(record: dict[str, Any]) -> str | None:
    """Return the KU id for a retrieved context record."""
    ku_id = record.get("ku_id")
    if ku_id:
        return ku_id
    kus = record.get("knowledge_units") or []
    return kus[0].get("id") if kus else None


def ku_ids_in_context(context: list[dict[str, Any]]) -> list[str]:
    """List the KU ids present in retrieved context, in order, de-duplicated."""
    ids: list[str] = []
    for record in context:
        ku_id = _record_ku_id(record)
        if ku_id and ku_id not in ids:
            ids.append(ku_id)
    return ids

def evidence_ids_in_context(context: list[dict[str, Any]]) -> list[str]:
    """Every evidence_id present in retrieved context, in order, de-duplicated."""
    ids: list[str] = []
    for record in context:
        for evidence in _as_list(record.get("evidence")):
            eid = evidence.get("evidence_id")
            if eid and eid not in ids:
                ids.append(eid)
    return ids


def select_sources_by_evidence_ids(
    context: list[dict[str, Any]],
    used_evidence_ids: list[str] | None,
) -> list[dict[str, Any]]:
    """Cite exactly the evidence passages the model declared it used.

    Returned in natural context order (retrieval rank, then KU evidence order),
    de-duplicated by evidence_id. No per-KU cap — the model's declaration bounds it.
    """
    if not context or not used_evidence_ids:
        return []
    wanted = set(used_evidence_ids)
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in context:
        for evidence in _as_list(record.get("evidence")):
            eid = evidence.get("evidence_id")
            if eid and eid in wanted and eid not in seen:
                seen.add(eid)
                selected.append(evidence)
    return _dedupe_sources_by_text(selected)

def build_answer_package(
    question: str,
    context: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a compact multi-KU answer package from retrieved graph context."""
    if not context:
        return {
            "question": question,
            "selected_knowledge_units": []
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

def _format_authors(authors: list[str] | None, year: Any) -> str | None:
    """Build a readable academic citation from the source's author list.

    Uses the first author's surname for the 'et al.' form. Replaces the old
    hardcoded author map, so it works for any source in the graph.
    """
    surnames = []
    for author in authors or []:
        author = str(author).strip()
        if author:
            surnames.append(author.split()[-1])

    if not surnames:
        return None

    lead = surnames[0] if len(surnames) == 1 else f"{surnames[0]} et al."
    return f"{lead} ({year})" if year else lead


def _format_source_line(evidence: dict[str, Any]) -> str | None:
    """Format one evidence item into Neo's required source format."""
    evidence_id = evidence.get("evidence_id")
    if not evidence_id:
        return None

    parts = [
        _format_authors(evidence.get("authors"), evidence.get("year")),
        evidence.get("citation_key"),
        evidence.get("source_id"),
    ]

    page = evidence.get("page")
    section = evidence.get("section")
    paragraph = evidence.get("paragraph")

    if page not in (None, ""):
        parts.append(f"page {page}")
    if section:
        parts.append(f'section "{section}"')
    if not _is_empty_or_todo(paragraph):
        parts.append(f'paragraph "{paragraph}"')

    safe_parts = [str(part) for part in parts if part not in (None, "")]
    return f"- {evidence_id} - ({', '.join(safe_parts)})"


def select_sources_used(context, used_ku_ids=None, max_per_ku=MAX_EVIDENCE_PER_KU):
    """The evidence items that would be cited — same logic, returned as data."""
    if not context:
        return []
    records = context
    if used_ku_ids:
        used = set(used_ku_ids)
        records = [r for r in context if _record_ku_id(r) in used] or context

    selected, seen = [], set()
    for record in records:
        evidence_items = sorted(
            _as_list(record.get("evidence")),
            key=lambda e: 0 if e.get("support_type") == "direct" else 1,
        )
        count = 0
        for evidence in evidence_items:
            eid = evidence.get("evidence_id")
            if not eid or eid in seen:
                continue
            seen.add(eid)
            selected.append(evidence)
            count += 1
            if count >= max_per_ku:
                break
    return selected


def format_sources_block(evidence_items: list[dict[str, Any]]) -> str:
    """Plain-text 'Sources used' from already-selected evidence (logs, non-TTY)."""
    lines = [_format_source_line(e) for e in evidence_items]
    lines = [line for line in lines if line]
    return ("Sources used:\n" + "\n".join(lines)) if lines else ""


def format_sources_used(context, used_ku_ids=None, max_per_ku=MAX_EVIDENCE_PER_KU):
    return format_sources_block(select_sources_used(context, used_ku_ids, max_per_ku))

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

