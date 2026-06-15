"""Answer generation for Neo.

This module takes retrieved graph context and asks the local Ollama model
to produce a source-grounded natural language answer.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from datetime import datetime

from src.agent.answer_package import (
    build_answer_package,
    evidence_ids_in_context,
    select_sources_by_evidence_ids,
    select_sources_used,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANSWER_PROMPT_PATH = PROJECT_ROOT / "src" / "prompts" / "answer_prompt.txt"
CONVERSATION_PROMPT_PATH = PROJECT_ROOT / "src" / "prompts" / "conversation_prompt.txt"
DEBUG_DIR = PROJECT_ROOT / "debug"

USED_KUS_PATTERN = re.compile(r"<used_kus>(.*?)</used_kus>", re.IGNORECASE | re.DOTALL)
USED_EVIDENCE_PATTERN = re.compile(r"<used_evidence>(.*?)</used_evidence>", re.IGNORECASE | re.DOTALL)


def extract_used_evidence_ids(text: str, available_evidence_ids: list[str]) -> list[str] | None:
    """Parse <used_evidence>, keeping only ids that were actually retrieved.

    Returns None when nothing usable is declared, signalling the caller to fall
    back to the bounded KU-level selection.
    """
    matches = USED_EVIDENCE_PATTERN.findall(text)
    if not matches:
        return None
    declared = [token.strip() for token in re.split(r"[,\s]+", matches[-1]) if token.strip()]
    available = set(available_evidence_ids)
    used = [eid for eid in declared if eid in available]
    return used or None


def strip_citation_tags(text: str) -> str:
    """Remove citation-tracking tag(s) so the user never sees internal ids."""
    text = USED_EVIDENCE_PATTERN.sub("", text)
    text = USED_KUS_PATTERN.sub("", text)  # defensive: strip the old tag if it appears
    return text.strip()

def extract_used_ku_ids(text: str, available_ku_ids: list[str]) -> list[str] | None:
    """Parse the <used_kus> tag, keeping only ids that were actually retrieved.

    Returns None when the model declares nothing usable, signalling the caller
    to fall back to citing all retrieved KUs.
    """
    matches = USED_KUS_PATTERN.findall(text)
    if not matches:
        return None

    declared = [token.strip() for token in re.split(r"[,\s]+", matches[-1]) if token.strip()]
    available = set(available_ku_ids)
    used = [ku_id for ku_id in declared if ku_id in available]
    return used or None


def strip_used_kus_tag(text: str) -> str:
    """Remove the <used_kus> tag(s) so the user never sees internal ids."""
    return USED_KUS_PATTERN.sub("", text).strip()

def load_answer_prompt() -> str:
    """Load the answer prompt template from disk."""
    if not ANSWER_PROMPT_PATH.exists():
        raise FileNotFoundError(f"Missing answer prompt: {ANSWER_PROMPT_PATH}")

    return ANSWER_PROMPT_PATH.read_text(encoding="utf-8")


def load_conversation_prompt() -> str:
    """Load the conversational prompt template from disk."""
    if not CONVERSATION_PROMPT_PATH.exists():
        raise FileNotFoundError(f"Missing conversation prompt: {CONVERSATION_PROMPT_PATH}")

    return CONVERSATION_PROMPT_PATH.read_text(encoding="utf-8")


def get_llm() -> ChatOllama:
    """Create the configured Ollama chat model."""
    load_dotenv(PROJECT_ROOT / ".env")

    model = os.getenv("OLLAMA_MODEL", "qwen3:8b")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # Reasoning is OFF by default. Neo's job is faithful extraction from the
    # answer package, not open-ended reasoning. Left on, a small model can spend
    # the whole context window thinking and emit no final answer.
    enable_reasoning = os.getenv("ENABLE_MODEL_REASONING", "false").lower() == "true"

    # Generous context so prompt + (optional) reasoning + answer all fit.
    num_ctx = int(os.getenv("OLLAMA_NUM_CTX", "8192"))

    common_kwargs: dict[str, Any] = {
        "model": model,
        "base_url": base_url,
        "temperature": 0,
        "keep_alive": "30m",
        "num_ctx": num_ctx,
    }

    # Qwen3 thinks by default, so we must pass reasoning EXPLICITLY to turn it
    # off. Omitting it (the old code) left Ollama on its default — thinking ON —
    # which silently fills the context window and truncates the real answer.
    if model.startswith("qwen3") or model.startswith("qwen3.5"):
        common_kwargs["reasoning"] = enable_reasoning

    return ChatOllama(**common_kwargs)


def strip_qwen_thinking(text: str) -> str:
    """Remove Qwen thinking blocks if the model prints them."""
    if not text:
        return text

    marker = "...done thinking."
    if marker in text:
        return text.split(marker, 1)[1].strip()

    # Fallback for possible <think>...</think> formats.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # Fallback if output starts with Thinking... but lacks the exact marker.
    if text.startswith("Thinking..."):
        parts = text.split("\n\n")
        if len(parts) > 1:
            return parts[-1].strip()

    return text.strip()


def extract_model_output(response: Any) -> str:
    """Extract reasoning + final answer from a LangChain/Ollama response.

    Depending on the model and langchain_ollama version, Qwen thinking may appear:
    1. directly inside response.content as "Thinking... ...done thinking."
    2. inside response.content as <think>...</think>
    3. separately in response.additional_kwargs["reasoning_content"]

    This function normalizes case 3 into the same text shape expected by
    split_qwen_thinking() in the CLI.
    """
    content = getattr(response, "content", str(response)) or ""

    additional_kwargs = getattr(response, "additional_kwargs", {}) or {}

    reasoning = (
        additional_kwargs.get("reasoning_content")
        or additional_kwargs.get("thinking")
        or additional_kwargs.get("reasoning")
    )

    if reasoning:
        return (
            "Thinking...\n"
            f"{str(reasoning).strip()}\n"
            "...done thinking.\n\n"
            f"{str(content).strip()}"
        ).strip()

    return str(content).strip()


def should_show_thinking() -> bool:
    """Return whether model thinking should be shown in the CLI."""
    load_dotenv(PROJECT_ROOT / ".env")
    return os.getenv("SHOW_MODEL_THINKING", "false").lower() == "true"


def format_context_for_llm(context: list[dict[str, Any]]) -> str:
    """Format graph context as readable JSON for the LLM.

    Keeping JSON-like structure is useful because it preserves evidence IDs,
    source IDs, citation keys, page numbers, sections, and avoid_claims.
    """
    if not context:
        return "[]"

    return json.dumps(context, indent=2, ensure_ascii=False)


def finalize_model_output(raw_output: str) -> str:
    """Return raw or thinking-stripped output depending on .env setting."""
    if should_show_thinking():
        return raw_output.strip()

    return strip_qwen_thinking(raw_output)

def debug_llm_prompt(prompt: str, mode: str) -> None:
    """Optionally print/save the exact prompt sent to the LLM."""
    load_dotenv(PROJECT_ROOT / ".env")

    debug_console = os.getenv("DEBUG_LLM_PROMPT", "false").lower() == "true"
    debug_file = os.getenv("DEBUG_LLM_PROMPT_TO_FILE", "false").lower() == "true"

    if not debug_console and not debug_file:
        return

    header = (
        "\n"
        + "=" * 100
        + f"\nEXACT LLM PROMPT SENT TO MODEL — MODE: {mode}\n"
        + "=" * 100
        + "\n"
    )

    footer = "\n" + "=" * 100 + "\nEND LLM PROMPT\n" + "=" * 100 + "\n"

    if debug_console:
        print(header)
        print(prompt)
        print(footer)

    if debug_file:
        DEBUG_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = DEBUG_DIR / f"llm_prompt_{mode}_{timestamp}.txt"
        path.write_text(header + prompt + footer, encoding="utf-8")
        print(f"\nSaved exact LLM prompt to: {path}")


def answer_from_context(question: str, context: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Generate a grounded answer plus the evidence the CLI should cite."""
    if not context:
        return "The knowledge base does not contain enough evidence to answer this.", []

    prompt_template = load_answer_prompt()
    answer_package = build_answer_package(question, context)
    formatted_answer_package = json.dumps(answer_package, indent=2, ensure_ascii=False)

    prompt = prompt_template.format(
        question=question,
        answer_package=formatted_answer_package,
    )
    debug_llm_prompt(prompt, mode="graph_answer")

    llm = get_llm()
    response = llm.invoke(prompt)

    raw_output = extract_model_output(response)
    model_answer = finalize_model_output(raw_output)

    used_evidence_ids = extract_used_evidence_ids(
        model_answer, evidence_ids_in_context(context)
    )
    model_answer = strip_citation_tags(model_answer)

    if used_evidence_ids:
        sources = select_sources_by_evidence_ids(context, used_evidence_ids)
    else:
        sources = select_sources_used(context)  # fallback: bounded KU-level

    return model_answer, sources


def answer_conversationally(question: str) -> str:
    """Generate a short conversational response without graph context."""
    prompt_template = load_conversation_prompt()
    prompt = prompt_template.format(question=question)

    debug_llm_prompt(prompt, mode="conversation")

    llm = get_llm()
    response = llm.invoke(prompt)

    raw_output = extract_model_output(response)
    return finalize_model_output(raw_output)