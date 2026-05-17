# graph_chain.py
from langchain_neo4j import Neo4jGraph
from langchain_neo4j.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_ollama import OllamaLLM
from prompts import cypher_prompt_temp, qa_prompt

BOLD = "\033[1m"
RESET = "\033[0m"


def create_chain():
	graph = Neo4jGraph(
		url="neo4j://127.0.0.1:7687", username="neo4j", password="password"
	)
	llm = OllamaLLM(model="llama3.1:8b", temperature=0)

	graph.refresh_schema()
	print(f"\n{BOLD}Schema loaded successfully.{RESET}")

	chain = GraphCypherQAChain.from_llm(
		llm,
		graph=graph,
		allow_dangerous_requests=True,
		verbose=False,
		qa_prompt=qa_prompt,
		cypher_prompt=cypher_prompt_temp,
	)
	chain.top_k = 50

	# Refresh the schema so LLM knows the graph structure
	# print(f"\n{GREEN}{BOLD}--- Refreshing Schema --- {RESET}")
	graph.refresh_schema()
	# print(graph.schema)

	return chain
