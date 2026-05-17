import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase
from utils import BOLD, GREEN, RED, RESET

# NOTE: To view the knowledge graph visit:
# http://localhost:7474/browser/

# NOTE: To drop all existing datbase entries run (in the neo4j broswer):
# MATCH (n) DETACH DELETE n;

# Load environment variables
DATA_PATH = Path(__file__).parent / "data" / "sia-projects.json"


def get_driver():
	"""Safely initialize Neo4j driver from env file."""
	load_dotenv("neo4j_db.env")

	uri = os.getenv("NEO4J_URI")
	username = os.getenv("NEO4J_USERNAME")
	password = os.getenv("NEO4J_PASSWORD")

	if not uri or not username or not password:
		raise RuntimeError(
			"Missing Neo4j credentials. Please run 'setup' in the CLI first."
		)

	return GraphDatabase.driver(uri, auth=(username, password))


def parse_amount(raw):
	if not raw:
		return None
	if isinstance(raw, (int, float)):
		return raw
	cleaned = raw.replace("€", "").replace(".", "").replace(",", ".").strip()
	try:
		return float(cleaned)
	except ValueError:
		return None


def create_project(tx, project):
	# extract safely with defaults
	contact = project.get("contact", {})
	participants = project.get("participants", [])
	participants_only = [p for p in participants if p.get("role") == "participant"]
	network_members_only = [
		p for p in participants if p.get("role") == "network-member"
	]

	payment_amount = parse_amount(project.get("paymentAmount"))

	tx.run(
		"""
        MERGE (p:Project {id: $id})
          SET p.title = $title,
              p.status = $status,
              p.paymentAmount = $paymentAmount,
              p.startDate = $startDate,
              p.endDate = $endDate,
              p.description = $description,
              p.url = $url

        MERGE (f:FundingScheme {name: $funding})
        MERGE (p)-[:FUNDED_BY]->(f)


        MERGE (o:Organization {name: $org})
          SET o.url = $org_url
        MERGE (p)-[:COORDINATED_BY]->(o)

        // only if contact info exists
        FOREACH (_ IN CASE WHEN $contact_email IS NOT NULL THEN [1] ELSE [] END |
          MERGE (c:Contact {email: $contact_email})
            SET c.name = $contact_name
          MERGE (p)-[:HAS_CONTACT]->(c)
          MERGE (c)-[:BELONGS_TO]->(o)
        )

        FOREACH (participant IN $participants |
          MERGE (part:Participant {name: participant.name})
            SET part.role = participant.role,
                part.url = participant.url
          MERGE (p)-[:HAS_PARTICIPANT]->(part)
        )

        FOREACH (member IN $network_members |
          MERGE (net:NetworkMember {name: member.name})
            SET net.url = member.url
          MERGE (p)-[:HAS_NETWORK_MEMBER]->(net)
        )
        """,
		id=project.get("projectID"),
		title=project.get("title"),
		status=project.get("status"),
		paymentAmount=payment_amount,
		startDate=project.get("startDate"),
		endDate=project.get("endDate"),
		description=project.get("description"),
		url=project.get("url"),
		funding=project.get("fundingScheme"),
		org=contact.get("org"),
		org_url=contact.get("org_url"),
		contact_name=contact.get("name"),
		contact_email=contact.get("email"),
		participants=participants_only,
		network_members=network_members_only,
	)


def main():
	start_time = time.time()

	if not DATA_PATH.exists():
		print(f"{RED}ERROR: Could not find data file at: {DATA_PATH}{RESET}")
		return

	driver = get_driver()  # 🔹 Only connect here, not on import

	with open(DATA_PATH, encoding="utf-8") as f:
		data = json.load(f)

	total = len(data)
	success, failed = 0, 0

	print(f"{BOLD}Loading {total} projects into Neo4j...{RESET}\n")

	with driver.session() as session:
		for i, project in enumerate(data, start=1):
			try:
				session.execute_write(create_project, project)
				success += 1
			except Exception as e:
				failed += 1
				print(
					f"{RED}Error on record {i} ({project.get('title', '<no title>')}): {e}{RESET}"
				)

			if i % 50 == 0 or i == total:
				print(f"  → Processed {i}/{total} ({(i / total) * 100:.1f}%)")

	driver.close()

	elapsed = time.time() - start_time
	print(f"\n{GREEN}Import complete!{RESET}")
	print(f"   {BOLD}Successfully inserted:{RESET}{success}")
	print(f"   {BOLD}Failed records:{RESET}       {failed}")
	print(f"   {BOLD}Duration:{RESET}             {elapsed:.2f} seconds")


if __name__ == "__main__":
	main()
