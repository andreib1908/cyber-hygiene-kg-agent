# SIA-Projects LangChain CLI

This README provides an overview of the application. For a dependency installation guide, check the file: 

**[DEPENDENCIES.md](DEPENDENCIES.md)**.

**You must install all dependencies before you can run the application.**

After installing dependencies, run the CLI entrypoint:

[sia_projects_langchain/sia_projects/cli.py](sia_projects_langchain/sia_projects/cli.py)

Ensure you run the `setup` command in the `cli.py` to setup your Neo4J Database within this application.

Additionally, to install the GitHub environment that utilizes pre-commit hooks (otherwise you will not be able to push changes to the Github Repo) check:

[Installation.md](Installation.md)

## Overview

This repository implements an LLM-driven CLI for exploring SIA-funded research projects stored in a (local) Neo4j graph database.

This CLI is a natural-language interface to a Neo4j graph database containing SIA-funded projects. Instead of writing Cypher queries, users can simply ask questions in English and the assistant automatically:

- Translates a user question into a Cypher query,
- Executes it on a local Neo4j database, and
- Returns a human-readable summary of the results.

## Conceptual View and Architecture

| Component                  | Description                                                                                                                     |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **Neo4j Graph**            | Stores project data (`data/sia-projects.json`) as nodes and relationships (Projects, Organizations, Participants, etc.).        |
| **LangChain Pipeline**     | Converts users' natural question into a Cypher query and runs it against Neo4j.                                                 |
| **Llama 3.1 (via Ollama)** | Generates and validates the query + summarizes the result. Two Llama models may be used: one for answering, one for validation. |

The design goal is to demonstrate a fully local, explainable graph-query pipeline that converts natural language -> database queries -> verified answers; with full logging and modular extensibility.

**Architecure Overview:**

```mathematica
           ┌──────────────────────────┐
           │        CLI Layer         │
           │  (User I/O + Commands)   │
           └────────────┬─────────────┘
                        │
                        ▼
           ┌──────────────────────────┐
           │      LangChain Graph     │
           │ (Llama 3.1 via Ollama)   │
           └────────────┬─────────────┘
                        │
                        ▼
           ┌──────────────────────────┐
           │        Neo4j DB          │
           │ (Projects, Orgs, Links)  │
           └────────────┬─────────────┘
                        │
                        ▼
           ┌──────────────────────────┐
           │    Validator LLM Layer    │
           │ (Optional consistency chk)│
           └──────────────────────────┘

```

## Directory Structure

```graphql
sia_projects_langchain/
│
├── sia_projects/
│   ├── cli.py                # Entry point for the command-line interface
│   ├── build_graph.py        # Converts JSON dataset → Neo4j graph schema
│   ├── graph_chain.py        # Builds the LangChain GraphQA pipeline
│   ├── validator.py          # Secondary LLM layer for result validation
│   ├── utils.py              # Logging, formatting, spinners, helpers
│   ├── data/
│   │   └── sia-projects.json # Source dataset
│   ├── logs/                 # Auto-generated query/answer logs
│   └── neo4j_db.env          # Local connection config (ignored by Git)
│
└── README.md

```

## Core Components

### 1. `graph_chain.py` - The LangChain Pipeline

Builds the Graph Cypher QA Chain, connecting the Ollama LLM (Llama 3.1), the Neo4j graph via the official LangChain-Neo4j connector,and a prompt template guiding Cypher generation and summarization.

You can modify this chain to:

- use a different LLM backend (for instance, OpenAI, Claude, however you will have to use your own API keys and tokens),
- change top_k retrieval behavior,
  - This may change how many records can be displayed at once. Current record limit is 50.

### 2. `build_graph.py` - Graph Construction

Parses the JSON dataset. It will then construct the project nodes with properties (title, funding, startYear etc.), the organization and Participant nodes, and relationships such as:

`(:Organization)-[:PARTICIPATES_IN]->(:Project).`

The build is idempotent: re-running overwrites existing nodes for consistency.

### 3. `cli.py` - Interactive Shell

The CLI manages:

- Initialization & setup (`setup_phase()`),
- Neo4j and Ollama connection checks,
- Command routing (such as `build`, `browser`, `skip-validation`, `exit`),
- Answer formatting, timing, and logging.

It’s structured as a continuous input loop with exception handling for:

- `ServiceUnavailable` (Neo4j offline, or when the database is not running),
- Validation toggling (`valid` and `novalid` in `cli.py`),
- Graceful exit.

To extend functionality, simply add more commands within the while True loop (`if-else` statements at the start of the loop).

### 4. `validator.py` - LLM-Based Answer Checks

A second Llama 3.1 model evaluates the accuracy and consistency of each answer using a dedicated prompt.

It receives:

```python
{
  "context": retrieved_data,
  "answer":  llm_summary
}
```

and returns a JSON verdict:

```python
{
  "verdict": "VALID",
  "justification": "Answer matches funding and title in database context."
}
```

This was the validation justification for an example question "What is the most expensive project?".

The validation layer can be turned off (`skip-validation` command in CLI) or extended to:

- cross-validate with a different model,
- use ensemble scoring,
- attach numeric confidence metrics
- add LLMs at different stages of the LangChain pipeline (Cypher, Answer).

### 5. `utils.py` - Shared Utilities

- Color-coded CLI printing (`GREEN, RED, ORANGE`, etc.)

- `spinner()` thread for progress animation

- `ask_question()` — wrapper for chain.invoke()

- `log_entry()` — persistent timestamped logging in `/logs/qa_log_YYYY-MM-DD.txt`

- `divider` and text indentation constants

## Running The System

Typical dev loop:

```bash
# 1. Ensure Neo4j Desktop or Aura instance is running
# 2. Ensure Ollama is serving locally
ollama serve
ollama pull llama3.1

# 3. Launch the CLI
python sia_projects_langchain/sia_projects/cli.py
```

Or simply navigate to `sia_projects_langchain/sia_projects` and run `cli.py`.

During startup:

- The CLI checks for neo4j_db.env and prompts creation if missing.
- Database connectivity is tested automatically.
- Optional graph build phase runs on first setup.

## Configuration

`neo4j_db.env` is created automatically via guided setup:

```ini
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
```

You can replace these values manually or rerun `setup` in the CLI.

## CLI Command Summary

| Command                                | Function                                                                              |
| -------------------------------------- | ------------------------------------------------------------------------------------- |
| **help**                               | Displays usage info and examples.                                                     |
| **setup**                              | Guides database connection setup.                                                     |
| **browser**                            | Opens Neo4j Browser ([http://localhost:7474/browser](http://localhost:7474/browser)). |
| **build / rebuild / refresh / update** | Rebuilds graph from dataset.                                                          |
| **skip-validation / novalid**          | Disables LLM validation for speed.                                                    |
| **enable-validation / valid**          | Re-enables validator.                                                                 |
| **exit / quit**                        | Terminates the session.                                                               |

## Logging and Debugging

Every interaction is logged to `/logs/`:

```pgsql
[2025-10-26 22:50:43]
Q: What is the most expensive project?
Cypher: MATCH (p:Project) RETURN p ORDER BY p.funding DESC LIMIT 1
A: Centre of Expertise Groen – 4,000,000€
Validator: VALID — Matches funding record.
Duration: 20.10s
```

## Key Dependencies

Check:
**[DEPENDENCIES.md](DEPENDENCIES.md)**.
