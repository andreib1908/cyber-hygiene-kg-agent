import itertools
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# CLI Constants


BOLD = "\033[1m"
RESET = "\033[0m"
GREEN = "\033[92m"
RED = "\033[91m"
ORANGE = "\033[38;5;214m"
INDENT = "  "
divider = f"{BOLD}{'-' * 70 * 3}{RESET}"

# ENV Connection (neo4j database credentials)
ENV_FILE = "neo4j_db.env"


# Cypher and Question Sanitizers/QOL


def sanitize_cypher(chain, query: str) -> str:
	if not query:
		return query
	# Replace SQL-style OFFSET
	query = query.replace("OFFSET", "SKIP")
	# Fix invalid Neo4j functions
	query = query.replace("toNumber", "toInteger")
	# Replace LIMIT ALL or dynamic variables
	query = query.replace("LIMIT ALL", f"LIMIT {chain.top_k}")
	# Prevent accidental 'LIMIT $var' or similar
	query = re.sub(r"LIMIT\s+\$\w+", f"LIMIT {chain.top_k}", query)
	# Replace money misuses
	if "fs.name" in query and "€" in query:
		query = query.replace("fs.name", "p.paymentAmount")
	return query


def ask_question(chain, question: str):
	result = chain.invoke({"query": question})

	# sanitize after invoke
	if "cypher" in result:
		result["cypher"] = sanitize_cypher(chain, result["cypher"])

	return result


# CLI Utils


def spinner(stop_event):
	"""Display a clean green spinner while the LLM is working."""
	GREEN = "\033[92m"
	RESET = "\033[0m"

	for c in itertools.cycle(["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]):
		if stop_event.is_set():
			break
		sys.stdout.write(f"\r{GREEN}Thinking {c}{RESET}")
		sys.stdout.flush()
		time.sleep(0.1)
	# Clear the line when done
	sys.stdout.write("\r" + " " * 50 + "\r")
	sys.stdout.flush()


def get_log_path():
	"""Return today's log file path inside the package's /logs folder."""
	base_dir = Path(__file__).resolve().parent  # -> sia_projects_langchain/sia_projects
	logs_dir = base_dir / "logs"
	logs_dir.mkdir(exist_ok=True)  # create if missing

	today = datetime.now().strftime("%Y-%m-%d")
	return logs_dir / f"qa_log_{today}.txt"


def log_entry(
	question, cypher_query, answer, elapsed, verdict=None, justification=None
):
	"""Append a detailed, timestamped log entry to today's log file."""
	log_path = get_log_path()
	is_new_file = not os.path.exists(log_path)

	timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

	with open(log_path, "a", encoding="utf-8") as log:
		# Add header if new
		if is_new_file:
			log.write("=" * 70 + "\n")
			log.write(f"LangChain QA Session started: {timestamp}\n")
			log.write("=" * 70 + "\n\n")

		# --- Core Log Structure ---
		log.write(f"[{timestamp}]\n")
		log.write(f"Q: {question.strip()}\n")

		# print(f"{ORANGE} The cypher query is: {cypher_query}{RESET}")
		if cypher_query:
			log.write(f"Cypher: {cypher_query.strip()}\n")

		if answer:
			log.write(f"A: {answer.strip()}\n")

		if verdict:
			verdict_line = f"Validator: {verdict}"
			if justification:
				verdict_line += f" — {justification.strip()}"
			log.write(f"{verdict_line}\n")

		log.write(f"Duration: {elapsed:.2f}s\n")
		log.write("-" * 70 + "\n\n")
