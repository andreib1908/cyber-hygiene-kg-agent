"""Interactive CLI for Neo.

Neo is a source-grounded cyber hygiene assistant.

Current MVP flow:
    user question
    -> retrieve graph context through safe retrieval templates
    -> generate answer with local Ollama model
    -> render answer nicely in terminal

Run from project root:
    python -m src.agent.cli
"""

from __future__ import annotations

import os
import re
import socket
import sys
import textwrap
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.neo_answer import answer_from_context
from src.ingestion.build_graph import main as rebuild_graph
from src.retrieval.retriever import retrieve_context
from src.agent.neo_answer import answer_conversationally, answer_from_context

# ---------------------------------------------------------------------------
# Terminal formatting
# ---------------------------------------------------------------------------

BOLD = "\033[1m"
RESET = "\033[0m"
GREEN = "\033[92m"
RED = "\033[91m"
ORANGE = "\033[38;5;214m"
BLUE = "\033[94m"
CYAN = "\033[96m"
DIM = "\033[2m"
INDENT = "  "

DIVIDER = f"{DIM}{'─' * 78}{RESET}"

LOGS_DIR = PROJECT_ROOT / "logs"
ENV_PATH = PROJECT_ROOT / ".env"


# ---------------------------------------------------------------------------
# Markdown-ish terminal rendering
# ---------------------------------------------------------------------------

def render_markdown_terminal(text: str) -> str:
    """Render a small subset of Markdown as ANSI terminal formatting.

    This handles the common output style used by LLMs:
    - **bold**
    - ### headings
    - bullet lists
    """
    if not text:
        return text

    # Convert headings.
    text = re.sub(
        r"^###\s+(.*)$",
        lambda m: f"{BOLD}{CYAN}{m.group(1).strip()}{RESET}",
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(
        r"^##\s+(.*)$",
        lambda m: f"{BOLD}{CYAN}{m.group(1).strip()}{RESET}",
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(
        r"^#\s+(.*)$",
        lambda m: f"{BOLD}{CYAN}{m.group(1).strip()}{RESET}",
        text,
        flags=re.MULTILINE,
    )
	
    # Convert bold markdown to ANSI bold.
    text = re.sub(r"\*\*(.*?)\*\*", rf"{BOLD}\1{RESET}", text)

	# Make "Sources used:" stand out.
    text = re.sub(
        r"(?im)^sources used:\s*$",
        f"{BOLD}Sources used:{RESET}",
        text,
    )

    # Turn raw evidence lines into bullet points.
    text = re.sub(
        r"(?m)^(EVID-[A-Z0-9-]+)\s*-\s*\(",
        r"- \1 - (",
        text,
    )

    # Clean occasional trailing spaces before line breaks.
    text = re.sub(r"[ \t]+\n", "\n", text)

    return text


def indent_block(text: str, indent: str = INDENT) -> str:
    return textwrap.indent(text.strip(), indent)


def split_qwen_thinking(text: str) -> tuple[str | None, str]:
    marker = "...done thinking."
    if "Thinking..." in text and marker in text:
        before, after = text.split(marker, 1)
        thinking = before.replace("Thinking...", "").strip()
        final = after.strip()
        return thinking, final

    return None, text

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def get_log_path() -> Path:
    LOGS_DIR.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    return LOGS_DIR / f"neo_cli_{today}.txt"


def log_entry(
    question: str,
    answer: str,
    elapsed: float,
    context_count: int,
) -> None:
    log_path = get_log_path()
    is_new_file = not log_path.exists()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(log_path, "a", encoding="utf-8") as log:
        if is_new_file:
            log.write("=" * 78 + "\n")
            log.write(f"Neo CLI session started: {timestamp}\n")
            log.write("=" * 78 + "\n\n")

        log.write(f"[{timestamp}]\n")
        log.write(f"Q: {question.strip()}\n")
        log.write(f"Context records: {context_count}\n")
        log.write(f"A: {answer.strip()}\n")
        log.write(f"Duration: {elapsed:.2f}s\n")
        log.write("-" * 78 + "\n\n")


# ---------------------------------------------------------------------------
# Spinner
# ---------------------------------------------------------------------------

def spinner(stop_event: threading.Event, message: str = "Neo is consulting the scrolls") -> None:
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    for frame in iter(lambda: frames[int(time.time() * 10) % len(frames)], None):
        if stop_event.is_set():
            break
        sys.stdout.write(f"\r{GREEN}{message} {frame}{RESET}")
        sys.stdout.flush()
        time.sleep(0.1)

    sys.stdout.write("\r" + " " * 80 + "\r")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Environment / status helpers
# ---------------------------------------------------------------------------

def load_environment() -> None:
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH)


def get_model_name() -> str:
    load_environment()
    return os.getenv("OLLAMA_MODEL", "qwen3:8b")


def get_neo4j_uri() -> str:
    load_environment()
    return os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")


def print_header() -> None:
    model = get_model_name()
    uri = get_neo4j_uri()

    print()
    print(f"{GREEN}{BOLD}Neo — Cyber Hygiene KG Assistant{RESET}")
    print(DIVIDER)
    print(f"{INDENT}{BOLD}Neo4j:{RESET} {uri}")
    print(f"{INDENT}{BOLD}Model:{RESET} {model}")
    print(f"{INDENT}{BOLD}Mode:{RESET} source-grounded graph retrieval")
    print()
    print(
        textwrap.indent(
            "Ask cyber hygiene questions in natural language. Neo retrieves relevant "
            "knowledge units, practices, evidence, and source metadata from the local "
            "Neo4j knowledge graph, then answers using only that context.",
            INDENT,
        )
    )
    print()
    print(f"{DIM}Type 'help' for commands, 'browser' to open Neo4j, or 'exit' to quit.{RESET}")


def print_help() -> None:
    print()
    print(f"{CYAN}{BOLD}Help — Neo CLI{RESET}")
    print(DIVIDER)

    print(f"{BOLD}Commands:{RESET}")
    print(
        textwrap.indent(
            "help                 Show this help menu\n"
            "browser              Open Neo4j Browser\n"
            "build / rebuild      Rebuild the Neo4j graph from the KB JSON\n"
            "model                Show the active Ollama model\n"
            "clear                Clear the terminal screen\n"
            "exit / quit          Quit Neo\n",
            INDENT,
        )
    )

    print(f"{BOLD}Example questions:{RESET}")
    print(
        textwrap.indent(
            "What is cyber hygiene?\n"
            "What are the five dimensions of cyber hygiene?\n"
            "How do I protect myself against phishing?\n"
            "How can I check whether a website connection is secure?\n"
            "How can organizations improve employee cyber hygiene?\n"
            "Why does awareness matter for cyber hygiene?\n",
            INDENT,
        )
    )

    print(f"{BOLD}Current design:{RESET}")
    print(
        textwrap.indent(
            "Neo does not freely generate Cypher in this MVP. It uses safe retrieval "
            "templates and graph context, then generates a source-grounded answer "
            "with citations in the Sources used section.",
            INDENT,
        )
    )
    print(DIVIDER)


def open_browser() -> None:
    host, port = "127.0.0.1", 7474

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect_ex((host, port)) == 0:
            print(f"{GREEN}Opening Neo4j Browser...{RESET}")
            webbrowser.open("http://localhost:7474/browser/")
        else:
            print(f"{RED}Neo4j Browser does not seem to be running at localhost:7474.{RESET}")
            print(f"{ORANGE}Start Neo4j first, then try again.{RESET}")


def rebuild_graph_interactive() -> None:
    confirm = input(
        f"{ORANGE}This will clear and rebuild the current Neo4j graph. Continue? (y/N): {RESET}"
    ).strip().lower()

    if confirm != "y":
        print(f"{ORANGE}Rebuild cancelled.{RESET}")
        return

    print(f"\n{GREEN}{BOLD}Rebuilding Neo knowledge graph...{RESET}")
    start = time.perf_counter()

    try:
        rebuild_graph(clear_existing=True)
    except Exception as exc:
        print(f"{RED}Graph rebuild failed:{RESET} {exc}")
        return

    elapsed = time.perf_counter() - start
    print(f"{GREEN}{BOLD}Graph rebuild complete.{RESET} Duration: {elapsed:.2f}s")


# ---------------------------------------------------------------------------
# Context memory
# ---------------------------------------------------------------------------

def empty_memory() -> dict[str, Any]:
    return {
        "last_question": None,
        "last_answer": None,
        "last_context_count": 0,
    }


def update_memory(
    memory: dict[str, Any],
    question: str,
    answer: str,
    context: list[dict[str, Any]],
) -> None:
    memory["last_question"] = question
    memory["last_answer"] = answer
    memory["last_context_count"] = len(context)


def summarize_context(context: list[dict[str, Any]]) -> str:
    summaries = []

    for record in context:
        ku_ids = []
        answer_styles = []

        for ku in record.get("knowledge_units", []):
            ku_id = ku.get("id")
            if ku_id and ku_id not in ku_ids:
                ku_ids.append(ku_id)

        for guidance in record.get("answer_guidance", []):
            style = guidance.get("answer_style")
            if style and style not in answer_styles:
                answer_styles.append(style)

        if ku_ids:
            summary = ", ".join(ku_ids)
            if answer_styles:
                summary += f" [{', '.join(answer_styles)}]"
            summaries.append(summary)

    if not summaries:
        return "No KUs retrieved."

    return "Retrieved KUs: " + " | ".join(summaries)

# ---------------------------------------------------------------------------
# Main asking flow
# ---------------------------------------------------------------------------

def is_conversational_question(question: str) -> bool:
    """Detect non-technical conversational inputs."""
    q = question.lower().strip()

    conversational_markers = [
        "hello",
        "hi",
        "hey",
        "how are you",
        "how are you doing",
        "who are you",
        "what are you",
        "what can you do",
        "how can you help",
        "thanks",
        "thank you",
    ]

    cyber_markers = [
        "cyber",
        "hygiene",
        "phishing",
        "password",
        "credential",
        "mfa",
        "2fa",
        "email",
        "domain",
        "website",
        "ssl",
        "certificate",
        "browser",
        "malware",
        "ransomware",
        "security",
        "secure",
        "privacy",
        "social media",
        "training",
        "policy",
    ]

    if any(marker in q for marker in cyber_markers):
        return False

    return any(marker in q for marker in conversational_markers)

def answer_question(question: str, memory: dict[str, Any]) -> None:
    start = time.perf_counter()

    stop_event = threading.Event()
    spin_thread = threading.Thread(target=spinner, args=(stop_event,))
    spin_thread.start()

    context: list[dict[str, Any]] = []
    answer = ""

    try:
        if is_conversational_question(question):
            context = []
            answer = answer_conversationally(question)
        else:
            context = retrieve_context(question, limit=2)

            # Debug: show which KUs were retrieved.
            # Later we can hide this behind a debug toggle.
            stop_event.set()
            spin_thread.join()
            print(f"{DIM}{summarize_context(context)}{RESET}")

            # Restart spinner while the model answers.
            stop_event = threading.Event()
            spin_thread = threading.Thread(target=spinner, args=(stop_event,))
            spin_thread.start()

            answer = answer_from_context(question, context)

    except KeyboardInterrupt:
        stop_event.set()
        spin_thread.join()
        print(f"\n{ORANGE}Cancelled.{RESET}")
        return
    except Exception as exc:
        stop_event.set()
        spin_thread.join()
        print(f"\n{RED}Neo failed:{RESET} {exc}")
        return
    finally:
        stop_event.set()
        spin_thread.join()

    elapsed = time.perf_counter() - start

    thinking, final_answer = split_qwen_thinking(answer)
    if thinking:
        print(f"\n{ORANGE}{BOLD}Model deliberation{RESET}")
        print(DIVIDER)
        print(indent_block(render_markdown_terminal(thinking)))
        print(DIVIDER)

    print(f"\n{GREEN}{BOLD}Answer{RESET}")
    print(DIVIDER)
    print(indent_block(render_markdown_terminal(final_answer)))
    print(DIVIDER)
    print(
        f"{DIM}{INDENT}Context records: {len(context)} | "
        f"Duration: {elapsed:.2f}s | Time: {datetime.now().strftime('%H:%M:%S')}{RESET}"
    )

    log_entry(
        question=question,
        answer=answer,
        elapsed=elapsed,
        context_count=len(context),
    )

    update_memory(memory, question, answer, context)

def main() -> None:
    load_environment()
    print_header()

    memory = empty_memory()

    while True:
        try:
            question = input(f"\n{GREEN}{BOLD}Ask Neo:{RESET}\n{INDENT}").strip()
        except KeyboardInterrupt:
            print(f"\n{BOLD}Exiting... Goodbye!{RESET}")
            break

        if not question:
            continue

        command = question.lower()

        if command in {"exit", "quit"}:
            print(f"{BOLD}Exiting... Goodbye!{RESET}")
            break

        if command in {"help", "h", "?"}:
            print_help()
            continue

        if command in {"browser", "open-browser"}:
            open_browser()
            continue

        if command in {"build", "rebuild", "refresh", "update"}:
            rebuild_graph_interactive()
            continue

        if command == "model":
            print(f"{BOLD}Active model:{RESET} {get_model_name()}")
            continue

        if command == "clear":
            os.system("clear")
            print_header()
            continue

        answer_question(question, memory)


if __name__ == "__main__":
    main()