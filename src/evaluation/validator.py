from langchain_core.prompts import PromptTemplate
from langchain_ollama import OllamaLLM


def get_validator_llm(model_name="llama3.1:8b"):
	llm = OllamaLLM(model=model_name, temperature=0)
	return llm


def get_validation_prompt():
	return PromptTemplate(
		# TODO: Add the initial question here as well to check if the final answer also reflected the user's question properly.
		input_variables=["context", "answer"],
		template=(
			"You are a strict factual verifier. Your task is to check whether the provided answer "
			"accurately reflects the factual information in the database context below.\n\n"
			"---\n"
			"Database Output:\n{context}\n"
			"---\n"
			"Answer:\n{answer}\n"
			"---\n\n"
			"Rules:\n"
			"1. Consider the database output as the sole source of truth.\n"
			"2. Check that all facts, quantities, and names in the answer appear correctly in the database.\n"
			"3. If the answer includes data not found in the database, mark it INVALID.\n"
			"4. If the answer omits relevant data or misinterprets relationships, mark it INVALID.\n"
			"5. Otherwise, mark it VALID.\n\n"
			"Respond strictly in JSON with the following structure:\n"
			'{{"verdict": "VALID" or "INVALID", "justification": "Short reason (one sentence)."}}'
		),
	)


def validate_answer_with_llm(context, answer, model_name="llama3.1:8b"):
	"""
	Runs a factual consistency check using a validator LLM.
	Returns a dict: {"verdict": "VALID"|"INVALID", "justification": "..."}
	"""
	llm = get_validator_llm(model_name)
	prompt = get_validation_prompt()
	formatted = prompt.format(context=context, answer=answer)

	try:
		result = llm.invoke(formatted)
		# Basic parsing fallback
		if isinstance(result, str) and "VALID" in result.upper():
			if "INVALID" in result.upper():
				return {"verdict": "INVALID", "justification": result.strip()}
			return {"verdict": "VALID", "justification": result.strip()}
		return {"verdict": "UNKNOWN", "justification": str(result).strip()}
	except Exception as e:
		return {"verdict": "ERROR", "justification": f"Validator failed: {e}"}
