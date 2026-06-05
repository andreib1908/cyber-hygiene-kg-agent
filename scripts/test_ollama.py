import os

from dotenv import load_dotenv
from langchain_ollama import ChatOllama

load_dotenv()

model = os.getenv("OLLAMA_MODEL", "qwen3:8b")

llm = ChatOllama(model=model, temperature=0)
response = llm.invoke("Reply with exactly: Ollama online for Neo.")

print(response.content)
