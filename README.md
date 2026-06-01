# KylinClaw

Lightweight Python framework for building LLM agents. Single file, zero heavy dependencies (stdlib only).

**[中文文档](#中文文档)**

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

---

# 中文文档

轻量级 Python LLM Agent 框架。单文件，零重依赖（仅用标准库）。

```
pip install kylinclaw
```

## 特性

- **零依赖** — 仅使用标准库 `urllib`，无需 `requests` 或 `httpx`
- **`@tool` 装饰器** — 从类型注解和 docstring 自动生成 OpenAI 兼容的 JSON Schema
- **ReAct 推理循环** — 多步骤思考 + 工具调用
- **可组合的原语** — `Chain`（串行）、`Crew`（协同）、`Workflow`（DAG 状态机）
- **RAG 支持** — `SimpleVectorStore` + `RAGAgent`，余弦相似度检索
- **生产工具** — `RateLimiter`（令牌桶限流）、`retry`（指数退避重试）

## 快速开始

```python
from kylinclaw import LLM, Agent, tool

@tool
def calculator(expression: str) -> str:
    """计算数学表达式并返回结果。"""
    return str(eval(expression, {"__builtins__": {}}, {}))

llm = LLM(api_key="sk-...", model="deepseek-chat",
          base_url="https://api.deepseek.com/v1")

agent = Agent("助手", llm=llm, tools=[calculator],
              system="你是一个有用的助手。")

print(agent.run("2**10 + 3**5 等于多少？"))
```

## 核心概念

### LLM

OpenAI 兼容客户端，支持 OpenAI、DeepSeek、通义千问、Moonshot 等。

```python
llm = LLM(
    api_key="sk-...",
    model="deepseek-chat",
    base_url="https://api.deepseek.com/v1",
    temperature=0.7,
    max_tokens=2048,
    timeout=30,
)

response = llm.chat([{"role": "user", "content": "你好"}])
```

### @tool 装饰器

将任意函数包装为带自动 JSON Schema 的 `Tool`：

```python
@tool
def search(query: str, max_results: int = 5) -> str:
    """搜索网页并返回结果。"""
    ...
```

类型注解 → JSON Schema 类型。docstring → 工具描述。返回值类型必须为 `str`。

### Agent（ReAct 推理循环）

```python
agent = Agent(
    name="研究助手",
    llm=llm,
    tools=[search, calculator],
    system="你是一个专业的研究助手。",
    max_steps=10,    # 最大工具调用轮次
    verbose=True,    # 打印每步推理过程
)

result = agent.run("调研量子计算的最新进展")
```

### Chain（串行管道）

每一步的输出作为下一步的输入：

```python
chain = agent_a | agent_b | agent_c
# 等价写法
chain = Chain([agent_a, agent_b, agent_c])

result = chain.run("初始输入")
```

### Crew（多智能体协同）

多个 Agent 共享上下文，协作完成同一任务：

```python
crew = Crew(agents=[researcher, critic, editor])
result = crew.run("写一份关于气候变化的报告")
```

### Workflow（DAG 状态机）

支持条件分支的有向无环图工作流：

```python
wf = Workflow()

@wf.node("start")
def classify(state):
    # state 是在节点间传递的字典
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

wf.edge("start", lambda s: s["category"])  # 动态路由
wf.edge("technical", "END")
wf.edge("general", "END")

result = wf.run({"query": "CUDA 是怎么工作的？"})
```

### Prompt（提示词模板）

支持 `{变量}` 插值的字符串模板：

```python
p = Prompt("请用{language}总结以下内容：{text}")
filled = p.format(language="中文", text="...")
```

### RAGAgent（检索增强生成）

```python
from kylinclaw import SimpleVectorStore, RAGAgent

store = SimpleVectorStore()
store.add("KylinClaw 使用 Python 标准库的 urllib")
store.add("@tool 装饰器会自动生成 JSON Schema")

agent = RAGAgent(
    name="文档助手",
    llm=llm,
    store=store,
    top_k=3,
    system="根据提供的上下文回答问题。",
)

print(agent.run("KylinClaw 如何处理 HTTP 请求？"))
```

### RateLimiter（限流器）

```python
from kylinclaw import RateLimiter

limiter = RateLimiter(rate=10, per=1.0)  # 每秒最多 10 次调用

# 作为上下文管理器
with limiter:
    result = llm.chat(...)

# 作为装饰器
@limiter
def call_api(text):
    return llm.chat(...)
```

### retry（重试）

```python
from kylinclaw import retry

@retry(max_attempts=3, delay=1.0, backoff=2.0)
def unreliable_function():
    ...
```

## 环境变量

| 变量名 | 说明 |
|--------|------|
| `OPENAI_API_KEY` | 默认 API Key |
| `OPENAI_BASE_URL` | 默认接口地址 |
| `OPENAI_MODEL` | 默认模型名称 |

## 示例

```
examples/
  basic_agent.py    # 单 Agent + 工具调用
  multi_agent.py    # Chain 和 Crew 模式
  rag_example.py    # RAG 检索增强生成
```

## 环境要求

- Python 3.9+
- 无需安装任何第三方包

## 许可证

MIT — 详见 [LICENSE](LICENSE)
