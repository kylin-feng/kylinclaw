"""
Example 3: RAG Agent
---------------------
RAGAgent retrieves relevant documents from a vector store
before answering, grounding responses in your knowledge base.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kylinclaw import LLM, RAGAgent, SimpleVectorStore

llm = LLM(
    api_key=os.environ.get("OPENAI_API_KEY", "sk-your-key"),
    model="deepseek-chat",
    base_url="https://api.deepseek.com/v1",
)

# ── Build knowledge base ──────────────────────────────────────────────────────

store = SimpleVectorStore()

docs = [
    "KylinClaw is a lightweight Python framework for building LLM agents.",
    "The @tool decorator automatically generates JSON schema from type hints.",
    "Chain connects agents sequentially; output of each step feeds the next.",
    "Crew runs multiple agents on the same task with accumulated context.",
    "Workflow is a DAG-based state machine using @wf.node() and wf.edge().",
    "SimpleVectorStore uses cosine similarity for nearest-neighbor retrieval.",
    "RAGAgent retrieves top-k documents before calling the LLM.",
    "RateLimiter implements token bucket algorithm and can be used as a decorator.",
    "The retry() decorator adds exponential backoff to any function.",
    "Memory class implements sliding-window conversation history.",
]

for doc in docs:
    store.add(doc)

print(f"Knowledge base: {len(docs)} documents indexed\n")

# ── Create RAGAgent ───────────────────────────────────────────────────────────

agent = RAGAgent(
    name="KylinDocs",
    llm=llm,
    store=store,
    top_k=3,
    system="You are a KylinClaw documentation assistant. Answer based on the provided context.",
)

# ── Query ─────────────────────────────────────────────────────────────────────

questions = [
    "How does the @tool decorator work?",
    "What is the difference between Chain and Crew?",
    "How do I add rate limiting to my agent?",
]

for q in questions:
    print(f"Q: {q}")
    print(f"A: {agent.run(q)}\n")
