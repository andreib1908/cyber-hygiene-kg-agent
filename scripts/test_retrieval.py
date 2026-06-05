"""Quick retrieval tests for Neo."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.retriever import retrieve_context


def show(question: str) -> None:
    print("\n" + "=" * 80)
    print(f"QUESTION: {question}")
    print("=" * 80)

    context = retrieve_context(question, limit=5)

    print(json.dumps(context, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    show("What is cyber hygiene?")
    show("How do I protect myself against phishing?")
    show("What is storage and device hygiene?")
    show("How can organizations improve employee cyber hygiene?")
