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

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANSWER_PROMPT_PATH = PROJECT_ROOT / "src" / "prompts" / "answer_prompt.txt"
CONVERSATION_PROMPT_PATH = PROJECT_ROOT / "src" / "prompts" / "conversation_prompt.txt"
DEBUG_DIR = PROJECT_ROOT / "debug"

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

    common_kwargs = {
        "model": model,
        "base_url": base_url,
        "temperature": 0,
        "keep_alive": "30m",
    }

    # Only some models support reasoning/thinking output.
    # Qwen3 supports it; Llama 3.1 does not.
    if model.startswith("qwen3"):
        common_kwargs["reasoning"] = True

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


def answer_from_context(question: str, context: list[dict[str, Any]]) -> str:
    """Generate a source-grounded answer from retrieved context."""
    if not context:
        return "The knowledge base does not contain enough evidence to answer this."

    prompt_template = load_answer_prompt()
    formatted_context = format_context_for_llm(context)

    prompt = prompt_template.format(
        question=question,
        context=formatted_context,
    )

    debug_llm_prompt(prompt, mode="graph_answer")

    llm = get_llm()
    response = llm.invoke(prompt)

    raw_output = extract_model_output(response)
    return finalize_model_output(raw_output)


def answer_conversationally(question: str) -> str:
    """Generate a short conversational response without graph context."""
    prompt_template = load_conversation_prompt()
    prompt = prompt_template.format(question=question)

    debug_llm_prompt(prompt, mode="conversation")

    llm = get_llm()
    response = llm.invoke(prompt)

    raw_output = extract_model_output(response)
    return finalize_model_output(raw_output)