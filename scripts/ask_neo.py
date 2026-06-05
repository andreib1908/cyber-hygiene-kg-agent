"""Ask Neo a single question from the terminal.

Usage:
    python scripts/ask_neo.py "What is cyber hygiene?"
    python scripts/ask_neo.py "How do I protect myself against phishing?"
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.neo_answer import answer_from_context
from src.retrieval.retriever import retrieve_context


def main() -> None:
    if len(sys.argv) < 2:
        question = input("Ask Neo: ").strip()
    else:
        question = " ".join(sys.argv[1:]).strip()

    if not question:
        print("No question provided.")
        return

    print("\nRetrieving graph context...")
    context = retrieve_context(question, limit=5)

    print(f"Retrieved {len(context)} context record(s).")
    print("\nNeo is thinking...\n")

    answer = answer_from_context(question, context)

    print(answer)


if __name__ == "__main__":
    main()
