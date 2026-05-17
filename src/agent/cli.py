import os
import socket
import textwrap
import threading
import time
import webbrowser
from datetime import datetime
from getpass import getpass

from build_graph import main as rebuild_graph
from dotenv import load_dotenv, set_key
from graph_chain import create_chain
from neo4j.exceptions import Neo4jError, ServiceUnavailable
from utils import (
	BOLD,
	ENV_FILE,
	GREEN,
	INDENT,
	ORANGE,
	RED,
	RESET,
	ask_question,
	divider,
	log_entry,
	spinner,
)
from validator import validate_answer_with_llm

# Run Second LLM (Llama 3.1) Validator - True to run validation, False to skip validation
# This is the base value, we always show validation by default.
# It can toggled in the CLI with the commands: 'valid' and 'novalid'
VALIDATION_ENABLED = True


# Verbose enabled to see full context or not
VERBOSE_ENABLED = False


def setup_phase():
	print(
		f"\n{GREEN}{BOLD}Initial setup:{RESET} Let's connect to your Neo4j database. "
		f"Press the 'ENTER' key to accept default values."
	)

	# Warn if config file already exists
	if os.path.exists(ENV_FILE):
		print(f"\n{ORANGE}A configuration file already exists at {ENV_FILE}.{RESET}")
		choice = input("Do you want to overwrite it? (y/N): ").strip().lower() or "n"
		if choice != "y":
			print(f"{BOLD}Setup cancelled. Keeping existing configuration.{RESET}\n")
			return

	while True:
		try:
			# Prompt for connection details (with sensible defaults)
			print()
			uri = (
				input(
					f"{BOLD}Neo4j URI{RESET} (default bolt://127.0.0.1:7687): "
				).strip()
				or "bolt://127.0.0.1:7687"
			)
			username = (
				input(f"{BOLD}Neo4j username{RESET} (default neo4j): ").strip()
				or "neo4j"
			)
			password = (
				getpass(f"{BOLD}Neo4j password{RESET} (default: 'password'): ").strip()
				or "password"
			)

			print("\nTesting connection...")

			from neo4j import GraphDatabase

			driver = GraphDatabase.driver(uri, auth=(username, password))
			with driver.session() as session:
				session.run("RETURN 1")

			print(f"{GREEN}Successfully connected to Neo4j!{RESET}\n")

			# Save configuration once successful
			if not os.path.exists(ENV_FILE):
				open(ENV_FILE, "w").close()

			set_key(ENV_FILE, "NEO4J_URI", uri)
			set_key(ENV_FILE, "NEO4J_USERNAME", username)
			set_key(ENV_FILE, "NEO4J_PASSWORD", password)

			print(f"{BOLD}Saved configuration to {ENV_FILE}{RESET}")
			print(f"{BOLD}→ URI:{RESET} {uri}")
			print(f"{BOLD}→ Username:{RESET} {username}")
			print(f"→{BOLD} Password:{RESET} (hidden)\n")

			# Rebuild after success
			choice = (
				input(
					f"\n{BOLD}{GREEN}Would you like to build the knowledge graph?{RESET} (y/N): "
				)
				.strip()
				.lower()
				or "n"
			)
			if choice != "y":
				print(
					f"{ORANGE}Graph rebuild aborted. Run the 'rebuild' or 'setup' commands to attempt this process again.{RESET}\n"
				)
				break
			else:
				print(
					f"{GREEN}{BOLD}Now building your Neo4j graph from local data...{RESET}"
				)
				start_time = time.perf_counter()
				try:
					rebuild_graph()
					print(
						f"{GREEN}Graph successfully built from data/sia-projects.json{RESET}"
					)
				except Exception as e:
					print(f"{RED}Graph rebuild failed:{RESET} {e}")
				finally:
					elapsed = time.perf_counter() - start_time
					print(f"{GREEN}{BOLD}Duration:{RESET} {elapsed:.2f} seconds\n")

				break  # Exit setup loop on success

		except KeyboardInterrupt:
			print(f"\n{RED}Setup cancelled by user.{RESET}\n")
			exit(0)

		except Exception as e:
			print(f"\n{RED}Connection failed: {e}{RESET}")
			print(
				f"{ORANGE}Please verify your credentials or ensure Neo4j is running.{RESET}"
			)
			retry = input("Try again? (Y/n): ").strip().lower() or "y"
			if retry != "y":
				print(f"\n{BOLD}Setup aborted.{RESET}\n")
				exit(1)


# Build the chain
chain = create_chain()

chain.top_k = (
	50  # or 25, or 100. Include your limit of how many entries you want to display
)

print(f"\n{GREEN}{BOLD}Welcome to the SIA-Projects LangChain CLI{RESET}")
print(f"{INDENT}Connected to Neo4j → {BOLD}bolt://127.0.0.1:7687{RESET}")
print(f"{INDENT}Using model → {BOLD}Llama 3.1 (via Ollama){RESET}\n")

print(
	textwrap.indent(
		"This interactive assistant lets you explore and query the SIA research projects database "
		"through natural language — no Cypher required. You can ask about project titles, participants, "
		"funding amounts, years, or organizations. It automatically converts your questions into Cypher "
		"and summarizes the results in plain English.\n\n"
		"Before first use, run 'setup' to connect your local Neo4j database.\n"
		"To view the database visually in Neo4j Browser, type 'browser'.",
		INDENT,
	)
)

print(
	textwrap.indent(
		"\nAvailable commands:\n"
		"• {BOLD}help{RESET} — show usage instructions and examples\n"
		"• {BOLD}setup{RESET} — configure Neo4j connection credentials\n"
		"• {BOLD}browser / open-browser{RESET} — open Neo4j Browser at http://localhost:7474/browser/\n"
		"• {BOLD}build / rebuild / refresh / update{RESET} — (re)build the Neo4j graph from JSON data\n"
		"• {BOLD}novalid / skip-validation{RESET} — disable LLM validation for faster responses\n"
		"• {BOLD}valid / enable-validation{RESET} — enable validation — disable LLM validation for faster responses\n"
		"• {BOLD}noverbose / skip-verbose{RESET} — disable verbose (detailed output of Langchain and LLM Cypher Generation).\n"
		"• {BOLD}verbose / enable-verbose{RESET} — enable verbose\n"
		"• {BOLD}exit{RESET} — quit the program\n",
		INDENT,
	).format(BOLD=BOLD, RESET=RESET)
)


while True:
	if not os.path.exists("neo4j_db.env"):
		setup_phase()
	else:
		load_dotenv("neo4j_db.env")

	question = input(f"\n{GREEN}{BOLD}Ask a question:{RESET}\n{INDENT}").strip()

	if question.lower() in {"exit", "quit"}:
		print(f"{BOLD}Exiting... Goodbye!{RESET}")
		break
	elif question.lower() in {"help", "h", "?"}:
		print(f"\n{divider}")
		print(f"{GREEN}{BOLD}HELP MENU — Using the SIA-Projects LangChain CLI{RESET}\n")

		print(f"{BOLD}Overview:{RESET}")
		print(
			textwrap.indent(
				"This assistant allows you to query a Neo4j graph database containing SIA-funded research "
				"and collaboration projects. Each project includes details such as title, funding amount, "
				"participating organizations, network members, and key dates. The Llama 3.1 model (via Ollama) "
				"translates your natural-language questions into Cypher queries and summarizes the results.\n",
				INDENT,
			)
		)

		print(f"{BOLD}Main Commands:{RESET}")
		print(
			print(
				print(
					textwrap.indent(
						"\nAvailable commands:\n"
						"• {BOLD}help{RESET} — show usage instructions and examples\n"
						"• {BOLD}setup{RESET} — configure Neo4j connection credentials\n"
						"• {BOLD}browser / open-browser{RESET} — open Neo4j Browser at http://localhost:7474/browser/\n"
						"• {BOLD}build / rebuild / refresh / update{RESET} — (re)build the Neo4j graph from JSON data\n"
						"• {BOLD}novalid / skip-validation{RESET} — disable LLM validation for faster responses\n"
						"• {BOLD}valid / enable-validation{RESET} — enable validation — disable LLM validation for faster responses\n"
						"• {BOLD}noverbose / skip-verbose{RESET} — disable verbose (detailed output of Langchain and LLM Cypher Generation).\n"
						"• {BOLD}verbose / enable-verbose{RESET} — enable verbose\n"
						"• {BOLD}exit{RESET} — quit the program\n",
						INDENT,
					).format(BOLD=BOLD, RESET=RESET)
				)
			)
		)

		print(f"{BOLD}You can ask about:{RESET}")
		print(
			textwrap.indent(
				"- Projects by title, keywords, or year\n"
				"- Projects involving specific organizations or participants\n"
				"- Funding details (e.g., top N projects by payment amount)\n"
				"- Start and end dates of projects\n"
				"- Coordinating and participating organizations\n"
				"- Any property available in the Neo4j schema\n",
				INDENT,
			)
		)

		print(f"{BOLD}Example questions:{RESET}")
		print(
			textwrap.indent(
				"1) What are the top 10 most expensive projects?\n"
				'2) Which organizations participated in "SAVE in woord en daad"?\n'
				"3) Which projects were funded under the KIEM scheme?\n"
				"4) Which projects started in 2023?\n"
				"5) What projects involve Avans Hogeschool as a participant?\n"
				"6) How many total projects exist in the database?\n",
				INDENT,
			)
		)

		print(f"{BOLD}Notes & Tips:{RESET}")
		print(
			textwrap.indent(
				"- You can type questions in plain English — the model handles the Cypher translation.\n"
				"- All answers are formatted clearly with bullet lists or summaries.\n"
				"- Each Q/A pair (with query and duration) is saved in /logs/ for review.\n"
				"- Use {BOLD}browser{RESET} anytime to view your graph visually in Neo4j Browser.\n"
				"- If connection fails, rerun {BOLD}setup{RESET} to reconfigure credentials.\n",
				INDENT,
			).format(BOLD=BOLD, RESET=RESET)
		)

		print(f"{divider}\n")
		continue

	elif question.lower() in {"build", "rebuild", "refresh", "update"}:
		confirm = (
			input(f"{INDENT}This will overwrite the current graph. Continue? (y/N): ")
			.strip()
			.lower()
		)
		if confirm != "y":
			print(f"{INDENT}Cancelled rebuild.\n")
			continue

		print(f"\n{GREEN}{BOLD}Rebuilding Neo4j graph from JSON...{RESET}")
		start_time = time.perf_counter()
		try:
			rebuild_graph()
			print(
				f"{GREEN}Graph successfully rebuilt from data/sia-projects.json{RESET}"
			)
		except Exception as e:
			print(f"\n{RED} Graph rebuild failed:{RESET}{e}")
		finally:
			elapsed = time.perf_counter() - start_time
			print(f"{GREEN}{BOLD}Duration:{RESET} {elapsed:.2f} seconds\n")
		continue
	elif question.lower() in {"browser", "open-browser"}:
		host, port = "127.0.0.1", 7474
		with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
			if s.connect_ex((host, port)) == 0:
				print(f"{GREEN}Opening Neo4j Browser...{RESET}")
				webbrowser.open("http://localhost:7474/browser/")
			else:
				print(
					f"{RED}Neo4j Browser does not seem to be running at localhost:7474{RESET}"
				)
				print(f"{ORANGE}Please start your Neo4j Desktop app first.{RESET}")
		continue
	elif question.lower() in {"skip-validation", "novalid"}:
		VALIDATION_ENABLED = False
		print(f"{ORANGE}Validation disabled for this session.{RESET}")
		continue
	elif question.lower() in {"enable-validation", "valid"}:
		VALIDATION_ENABLED = True
		print(f"{GREEN}Validation enabled for this session.{RESET}")
		continue
	elif question.lower() in {"enable-verbose", "verbose"}:
		chain.verbose = True
		print(f"{GREEN}Verbose enabled for this session.{RESET}")
		continue
	elif question.lower() in {"skip-verbose", "noverbose"}:
		chain.verbose = False
		print(f"{ORANGE}Verbose disabled for this session.{RESET}")
		continue

	elif question.lower() == "setup":
		setup_phase()
		continue

	stop_event = threading.Event()
	t = threading.Thread(target=spinner, args=(stop_event,))
	t.start()

	start_time = time.perf_counter()

	try:
		answer = ask_question(chain, question)
		context_data = answer.get("context", "")
		final_answer = answer.get("result", "")

		# Validator phase
		if VALIDATION_ENABLED:
			print(f"\n{ORANGE}Running validator check...{RESET}")
			validation_result = validate_answer_with_llm(context_data, final_answer)
		else:
			validation_result = {
				"verdict": "SKIPPED",
				"justification": "Validation disabled.",
			}

		verdict = validation_result.get("verdict", "UNKNOWN")
		justification = validation_result.get("justification", "")
		if verdict not in {"VALID", "INVALID", "SKIPPED"}:
			verdict = "UNKNOWN"
			justification = justification or "Could not parse validator output."
	except (ServiceUnavailable, Neo4jError) as e:
		print(f"\n{RED}Connection to Neo4j failed:{RESET} {e}")
		retry = (
			input(f"{ORANGE}Do you want to re-attempt connection? (y/N): {RESET}")
			.strip()
			.lower()
			or "n"
		)
		if retry == "y":
			print(f"{GREEN}Retrying connection...{RESET}")
			continue
		else:
			print(
				f"{RED}Aborting query. Please ensure Neo4j is running and try again later.{RESET}\n"
			)
			break
	finally:
		stop_event.set()
		t.join()

	end_time = time.perf_counter()
	elapsed = end_time - start_time

	result_text = answer.get("result", "(no answer returned)")
	cypher_query = answer.get("cypher", None)

	timestamp = datetime.now().strftime("%H:%M:%S")

	print(
		f"{GREEN}{BOLD}Answer:{RESET}\n{textwrap.indent(result_text.strip(), INDENT)}"
	)

	if verdict == "VALID":
		print(f"{GREEN}{BOLD}Validator Verdict:{RESET} {verdict} — {justification}")
	elif verdict == "INVALID":
		print(f"{RED}{BOLD}Validator Verdict:{RESET} {verdict} — {justification}")
	elif verdict == "SKIPPED":
		print(f"{ORANGE}{BOLD}Validator Verdict:{RESET} {verdict} — {justification}")
	else:
		print(f"{ORANGE}{BOLD}Validator Verdict:{RESET} UNKNOWN — {justification}")

	print(f"{GREEN}{BOLD}Duration:{RESET} {elapsed:.2f} seconds")
	print(f"{GREEN}{BOLD}Time:{RESET} {timestamp}")

	log_entry(
		question=question,
		cypher_query=cypher_query,
		answer=result_text,
		elapsed=elapsed,
		verdict=verdict,
		justification=justification,
	)
