# KylinClaw

Lightweight Python framework for building LLM agents. Single file, zero heavy dependencies (stdlib only).

```
pip install kylinclaw
```

## Features

- **Zero dependencies** — uses `urllib` from stdlib, no `requests` or `httpx` required
- **`@tool` decorator** — auto-generates OpenAI-compatible JSON schema from type hints + docstrings
- **ReAct agent loop** — multi-step reasoning with tool execution
- **Composable primitives** — `Chain`, `Crew`, `Workflow` DAG
- **RAG support** — `SimpleVectorStore` + `RAGAgent` with cosine similarity retrieval
- **Production utilities** — `RateLimiter` (token bucket), `retry` (exponential backoff)

## Quick Start

```python
from kylinclaw import LLM, Agent, tool

@tool
def calculator(expression: str) -> str:
    """Evaluate a math expression."""
    return str(eval(expression, {"__builtins__": {}}, {}))

llm = LLM(api_key="sk-...", model="deepseek-chat",
          base_url="https://api.deepseek.com/v1")

agent = Agent("Assistant", llm=llm, tools=[calculator],
              system="You are a helpful assistant.")

print(agent.run("What is 2**10 + 3**5?"))
```

## Core Concepts

### LLM

OpenAI-compatible client. Works with OpenAI, DeepSeek, Qwen, Moonshot, etc.

```python
llm = LLM(
    api_key="sk-...",
    model="gpt-4o",
    base_url="https://api.openai.com/v1",  # default
    temperature=0.7,
    max_tokens=2048,
    timeout=30,
)

response = llm.chat([{"role": "user", "content": "Hello"}])
```

### @tool decorator

Wraps any function into a `Tool` with auto-generated JSON schema:

```python
@tool
def search(query: str, max_results: int = 5) -> str:
    """Search the web and return results."""
    ...
```

Type hints → JSON schema types. Docstring → tool description. Return type must be `str`.

### Agent (ReAct loop)

```python
agent = Agent(
    name="MyAgent",
    llm=llm,
    tools=[search, calculator],
    system="You are a research assistant.",
    max_steps=10,       # max tool-call iterations
    verbose=True,       # print step-by-step reasoning
)

result = agent.run("Research the latest news on quantum computing")
```

### Chain

Sequential pipeline — output of each step is the input to the next:

```python
chain = agent_a | agent_b | agent_c
# or
chain = Chain([agent_a, agent_b, agent_c])

result = chain.run("initial input")
```

### Crew

Multiple agents collaborate on the same task with accumulated context:

```python
crew = Crew(agents=[researcher, critic, editor])
result = crew.run("Write a report on climate change")
```

### Workflow (DAG)

State machine with conditional branching:

```python
wf = Workflow()

@wf.node("start")
def classify(state):
    # state is a dict passed between nodes
    state["category"] = "technical"
    return state

@wf.node("technical")
def handle_tech(state):
    state["response"] = agent.run(state["query"])
    return state

@wf.node("general")
def handle_general(state):
    state["response"] = llm.chat([{"role": "user", "content": state["query"]}])
    return state

wf.edge("start", lambda s: s["category"])  # dynamic routing
wf.edge("technical", "END")
wf.edge("general", "END")

result = wf.run({"query": "How does CUDA work?"})
```

### Prompt

String templates with `{variable}` interpolation:

```python
p = Prompt("Summarize the following in {language}: {text}")
filled = p.format(language="English", text="...")
```

### RAGAgent

Retrieval-augmented generation:

```python
from kylinclaw import SimpleVectorStore, RAGAgent

store = SimpleVectorStore()
store.add("KylinClaw uses urllib from Python stdlib")
store.add("The @tool decorator generates JSON schema automatically")

agent = RAGAgent(
    name="DocBot",
    llm=llm,
    store=store,
    top_k=3,
    system="Answer based on the provided context.",
)

print(agent.run("How does KylinClaw handle HTTP?"))
```

### RateLimiter

```python
from kylinclaw import RateLimiter

limiter = RateLimiter(rate=10, per=1.0)  # 10 calls/second

# Use as context manager
with limiter:
    result = llm.chat(...)

# Use as decorator
@limiter
def call_api(text):
    return llm.chat(...)
```

### retry

```python
from kylinclaw import retry

@retry(max_attempts=3, delay=1.0, backoff=2.0)
def unreliable_function():
    ...
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Default API key |
| `OPENAI_BASE_URL` | Default base URL |
| `OPENAI_MODEL` | Default model name |

## Examples

```
examples/
  basic_agent.py    # Single agent with tool use
  multi_agent.py    # Chain and Crew patterns
  rag_example.py    # RAG with SimpleVectorStore
```

## Requirements

- Python 3.9+
- No external packages required

## License

MIT — see [LICENSE](LICENSE)
