"""
KylinClaw — A lightweight Python framework for building LLM agents.

Core philosophy: minimal API, zero magic, composable.
Single file, no heavy dependencies (only stdlib + optional requests).

Usage:
    from kylinclaw import LLM, Agent, tool, Chain, Crew, Prompt

    @tool
    def search(query: str) -> str:
        \"\"\"Search the web\"\"\"
        return f"Results for: {query}"

    llm = LLM(api_key="sk-...", model="deepseek-chat")
    agent = Agent("Assistant", llm=llm, tools=[search], system="You help users.")
    print(agent.run("Find info about Python"))
"""

from __future__ import annotations

import json
import inspect
import logging
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Union

__version__ = "0.1.0"
__all__ = [
    "LLM", "Tool", "tool", "Message", "Memory",
    "Agent", "Prompt", "Chain", "Crew", "Workflow",
    "RAGAgent", "SimpleVectorStore", "RateLimiter", "retry",
    "KylinError", "LLMError", "ToolError", "AgentError",
]

logger = logging.getLogger("kylinclaw")


# ════════════════════════════════════════════════════════════════════
# Exceptions
# ════════════════════════════════════════════════════════════════════

class KylinError(Exception):  pass
class LLMError(KylinError):   pass
class ToolError(KylinError):  pass
class AgentError(KylinError): pass


# ════════════════════════════════════════════════════════════════════
# Tool — decorator-based function calling
# ════════════════════════════════════════════════════════════════════

@dataclass
class Tool:
    name:        str
    func:        Callable
    description: str
    parameters:  Dict[str, Any]

    def __call__(self, **kwargs) -> Any:
        return self.func(**kwargs)

    def to_schema(self) -> Dict:
        """OpenAI-compatible function schema."""
        return {
            "type": "function",
            "function": {
                "name":        self.name,
                "description": self.description,
                "parameters":  self.parameters,
            },
        }


_TYPE_MAP = {str: "string", int: "integer", float: "number",
             bool: "boolean", list: "array", dict: "object"}


def tool(func: Optional[Callable] = None, *, name: str = None, description: str = None):
    """
    Decorator to register a Python function as an LLM-callable tool.

    @tool
    def my_func(x: str, y: int) -> str:
        \"\"\"Does something\"\"\"
        ...

    # Or with explicit metadata:
    @tool(name="my_tool", description="Custom description")
    def my_func(...):
        ...
    """
    def _build(f: Callable) -> Callable:
        _name = name or f.__name__
        _desc = description or (inspect.getdoc(f) or "").strip()

        sig   = inspect.signature(f)
        hints = f.__annotations__

        props, required = {}, []
        for pname, param in sig.parameters.items():
            if pname in ("return", "self"):
                continue
            hint = hints.get(pname, str)
            prop = {"type": _TYPE_MAP.get(hint, "string")}
            # Try to pull param description from docstring (Google style)
            props[pname] = prop
            if param.default is inspect.Parameter.empty:
                required.append(pname)

        parameters = {"type": "object", "properties": props, "required": required}
        t = Tool(name=_name, func=f, description=_desc, parameters=parameters)

        @wraps(f)
        def wrapper(*args, **kwargs):
            return f(*args, **kwargs)

        wrapper._kc_tool = t  # type: ignore[attr-defined]
        return wrapper

    return _build(func) if func is not None else _build


def _get_tool(f: Callable) -> Optional[Tool]:
    return getattr(f, "_kc_tool", None)


# ════════════════════════════════════════════════════════════════════
# Message & Memory — conversation history
# ════════════════════════════════════════════════════════════════════

@dataclass
class Message:
    role:         str   # "system" | "user" | "assistant" | "tool"
    content:      str
    tool_calls:   Optional[List[Dict]] = None
    tool_call_id: Optional[str]        = None
    name:         Optional[str]        = None

    def to_dict(self) -> Dict:
        d: Dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:   d["tool_calls"]   = self.tool_calls
        if self.tool_call_id: d["tool_call_id"] = self.tool_call_id
        if self.name:         d["name"]          = self.name
        return d

    @staticmethod
    def system(text: str)    -> "Message": return Message("system",    text)
    @staticmethod
    def user(text: str)      -> "Message": return Message("user",      text)
    @staticmethod
    def assistant(text: str) -> "Message": return Message("assistant", text)


class Memory:
    """
    Sliding-window conversation memory.
    Keeps the system prompt pinned, trims oldest exchanges when full.
    """
    def __init__(self, max_turns: int = 20):
        self.max_turns = max_turns
        self.messages:  List[Message] = []

    def add(self, msg: Message):
        self.messages.append(msg)
        self._trim()

    def _trim(self):
        sys   = [m for m in self.messages if m.role == "system"]
        other = [m for m in self.messages if m.role != "system"]
        limit = self.max_turns * 2
        if len(other) > limit:
            other = other[-limit:]
        self.messages = sys + other

    def to_list(self) -> List[Dict]:
        return [m.to_dict() for m in self.messages]

    def clear(self):
        """Reset conversation but keep system prompt."""
        self.messages = [m for m in self.messages if m.role == "system"]

    def __len__(self) -> int:
        return len(self.messages)


# ════════════════════════════════════════════════════════════════════
# LLM — OpenAI-compatible client (stdlib only)
# ════════════════════════════════════════════════════════════════════

class LLM:
    """
    Thin wrapper around any OpenAI-compatible REST API.
    Works with DeepSeek, OpenAI, Moonshot, Qwen, local Ollama, etc.

    Examples::

        llm = LLM(api_key="sk-...", model="deepseek-chat",
                  base_url="https://api.deepseek.com")

        llm = LLM(api_key="ollama", model="llama3",
                  base_url="http://localhost:11434/openai")
    """
    def __init__(
        self,
        api_key:     str   = "",
        model:       str   = "deepseek-chat",
        base_url:    str   = "https://api.deepseek.com",
        temperature: float = 0.7,
        max_tokens:  int   = 4096,
        timeout:     int   = 60,
    ):
        self.api_key     = api_key
        self.model       = model
        self.base_url    = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens  = max_tokens
        self.timeout     = timeout

    def _post(self, endpoint: str, payload: Dict) -> Dict:
        data = json.dumps(payload).encode()
        req  = urllib.request.Request(
            f"{self.base_url}{endpoint}",
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type":  "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise LLMError(f"HTTP {e.code}: {e.read().decode()}")
        except Exception as e:
            raise LLMError(str(e))

    def chat(
        self,
        messages: List[Dict],
        tools:    Optional[List[Dict]] = None,
    ) -> Dict:
        """Raw chat completions call."""
        payload: Dict[str, Any] = {
            "model":       self.model,
            "messages":    messages,
            "temperature": self.temperature,
            "max_tokens":  self.max_tokens,
        }
        if tools:
            payload["tools"]       = tools
            payload["tool_choice"] = "auto"
        return self._post("/v1/chat/completions", payload)

    def complete(self, prompt: str, system: str = "") -> str:
        """One-shot completion, no history."""
        messages: List[Dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = self.chat(messages)
        return resp["choices"][0]["message"]["content"]

    def embed(self, text: str, model: str = "text-embedding-ada-002") -> List[float]:
        """Get embedding vector for text."""
        resp = self._post("/v1/embeddings", {"model": model, "input": text})
        return resp["data"][0]["embedding"]


# ════════════════════════════════════════════════════════════════════
# Agent — ReAct-style (Reason + Act)
# ════════════════════════════════════════════════════════════════════

class Agent:
    """
    An LLM-powered agent that can reason and use tools in a loop.

    Loop::

        user_input → LLM → tool_call? → execute tool → LLM → ... → final answer

    Examples::

        agent = Agent("Coder", llm=llm, tools=[run_code], system="You write Python.")
        answer = agent.run("Write a bubble sort")
    """
    def __init__(
        self,
        name:      str,
        llm:       LLM,
        tools:     Optional[List[Callable]] = None,
        system:    str                       = "",
        memory:    Optional[Memory]          = None,
        max_steps: int                       = 10,
        verbose:   bool                      = False,
    ):
        self.name      = name
        self.llm       = llm
        self.system    = system
        self.max_steps = max_steps
        self.verbose   = verbose
        self.memory    = memory or Memory()

        # Register tools
        self._tools: Dict[str, Tool] = {}
        for f in (tools or []):
            t = _get_tool(f)
            if t:
                self._tools[t.name] = t
            elif callable(f):
                self._tools[f.__name__] = Tool(
                    name=f.__name__, func=f,
                    description=inspect.getdoc(f) or "",
                    parameters={"type": "object", "properties": {}},
                )

        if system:
            pinned = Message.system(system)
            if not any(m.role == "system" for m in self.memory.messages):
                self.memory.messages.insert(0, pinned)

    # ── internals ─────────────────────────────────────────────────

    def _log(self, msg: str):
        if self.verbose:
            print(f"\033[36m[{self.name}]\033[0m {msg}")

    def _call_tool(self, name: str, args: Dict) -> str:
        t = self._tools.get(name)
        if not t:
            return f"[Error] Tool '{name}' not found."
        try:
            result = t(**args)
            return str(result) if result is not None else "(no output)"
        except Exception as e:
            return f"[Error] {type(e).__name__}: {e}"

    # ── public API ────────────────────────────────────────────────

    def run(self, user_input: str) -> str:
        """Run the agent and return its final text response."""
        self.memory.add(Message.user(user_input))
        self._log(f"↳ {user_input[:80]}")

        schemas = [t.to_schema() for t in self._tools.values()]

        for step in range(self.max_steps):
            resp    = self.llm.chat(self.memory.to_list(), tools=schemas or None)
            choice  = resp["choices"][0]
            msg     = choice["message"]
            reason  = choice["finish_reason"]

            # Record assistant turn
            self.memory.add(Message(
                role="assistant",
                content=msg.get("content") or "",
                tool_calls=msg.get("tool_calls"),
            ))

            if reason == "stop":
                answer = msg.get("content", "")
                self._log(f"✓ {answer[:80]}")
                return answer

            # Handle tool calls
            for tc in msg.get("tool_calls") or []:
                fn_name = tc["function"]["name"]
                fn_args = json.loads(tc["function"]["arguments"])
                self._log(f"  tool → {fn_name}({fn_args})")
                result = self._call_tool(fn_name, fn_args)
                self._log(f"  tool ← {result[:120]}")
                self.memory.add(Message(
                    role="tool", content=result,
                    tool_call_id=tc["id"], name=fn_name,
                ))

            if not msg.get("tool_calls") and reason != "stop":
                return msg.get("content") or ""

        return "[AgentError] Max steps reached."

    def chat(self, message: str) -> str:
        """Alias for run(); keeps conversational history between calls."""
        return self.run(message)

    def reset(self):
        """Clear conversation memory, keep system prompt."""
        self.memory.clear()

    def add_tool(self, func: Callable):
        """Dynamically add a tool to this agent."""
        t = _get_tool(func)
        if t:
            self._tools[t.name] = t
        return self


# ════════════════════════════════════════════════════════════════════
# Prompt — template with {variable} interpolation
# ════════════════════════════════════════════════════════════════════

class Prompt:
    """
    Simple string template.

    Examples::

        p = Prompt("Translate to {lang}: {text}")
        p(lang="French", text="Hello")
    """
    def __init__(self, template: str):
        self.template = template

    def format(self, **kwargs) -> str:
        return self.template.format(**kwargs)

    def __call__(self, **kwargs) -> str:
        return self.format(**kwargs)

    def __repr__(self) -> str:
        return f"Prompt({self.template[:40]!r})"


# ════════════════════════════════════════════════════════════════════
# Chain — sequential pipeline
# ════════════════════════════════════════════════════════════════════

class Chain:
    """
    Linear pipeline where each step receives the previous output.
    Steps can be: Agent | Prompt | callable | str (passthrough).

    Examples::

        chain = Chain([
            Prompt("Summarize: {input}"),
            summarizer_agent,
            translator_agent,
        ])
        result = chain.run("Long article text...")
    """
    def __init__(self, steps: List[Any], verbose: bool = False):
        self.steps   = steps
        self.verbose = verbose

    def run(self, input_data: str) -> str:
        result = input_data
        for i, step in enumerate(self.steps):
            if self.verbose:
                print(f"[Chain] step {i+1}/{len(self.steps)}: {type(step).__name__}")

            if isinstance(step, Agent):
                result = step.run(result)
            elif isinstance(step, Prompt):
                result = step.format(input=result)
            elif callable(step):
                result = step(result)
            else:
                raise AgentError(f"Invalid step type at index {i}: {type(step)}")

        return result

    def __or__(self, other: Any) -> "Chain":
        """Allow `chain | step` syntax."""
        return Chain(self.steps + [other], verbose=self.verbose)


# ════════════════════════════════════════════════════════════════════
# Crew — multi-agent collaboration
# ════════════════════════════════════════════════════════════════════

class Crew:
    """
    Coordinates multiple agents on a shared task.
    Agents run sequentially; each receives the accumulated context.

    Examples::

        crew = Crew([researcher, analyst, writer])
        report = crew.run("Analyze the EV market in China")
    """
    def __init__(self, agents: List[Agent], verbose: bool = False):
        self.agents  = agents
        self.verbose = verbose

    def run(self, task: str) -> str:
        context = ""
        outputs: List[str] = []

        for agent in self.agents:
            if self.verbose:
                print(f"\n[Crew] → {agent.name}")

            if outputs:
                prior = "\n".join(
                    f"[{self.agents[i].name}]: {o}"
                    for i, o in enumerate(outputs)
                )
                prompt = (
                    f"Task: {task}\n\n"
                    f"Prior work:\n{prior}\n\n"
                    f"Now contribute as {agent.name}:"
                )
            else:
                prompt = f"Task: {task}"

            out = agent.run(prompt)
            outputs.append(out)

            if self.verbose:
                print(f"[{agent.name}] ✓ {out[:100]}…")

        return outputs[-1] if outputs else ""

    def __repr__(self) -> str:
        names = [a.name for a in self.agents]
        return f"Crew({' → '.join(names)})"


# ════════════════════════════════════════════════════════════════════
# Workflow — DAG-based state machine
# ════════════════════════════════════════════════════════════════════

class Workflow:
    """
    DAG workflow. Nodes are callables that receive/return a shared state dict.

    Examples::

        wf = Workflow()

        @wf.node("fetch")
        def fetch(state):
            return {"data": fetch_data(state["url"])}

        @wf.node("analyze")
        def analyze(state):
            return {"result": analyze(state["data"])}

        wf.edge("fetch", "analyze")
        final = wf.run({"url": "https://example.com"})
    """
    def __init__(self):
        self.nodes:  Dict[str, Callable] = {}
        self.edges:  Dict[str, List[str]] = {}
        self._entry: Optional[str] = None

    def node(self, name: str):
        def decorator(func: Callable) -> Callable:
            self.nodes[name] = func
            if self._entry is None:
                self._entry = name
            return func
        return decorator

    def edge(self, src: str, dst: str):
        self.edges.setdefault(src, []).append(dst)

    def set_entry(self, name: str):
        self._entry = name

    def run(self, initial_state: Dict) -> Dict:
        if not self._entry:
            raise AgentError("No entry node. Use @wf.node() or wf.set_entry().")

        state   = dict(initial_state)
        queue   = [self._entry]
        visited: set = set()

        while queue:
            name = queue.pop(0)
            if name in visited:
                continue
            visited.add(name)

            fn = self.nodes.get(name)
            if not fn:
                raise AgentError(f"Node '{name}' not found.")

            result = fn(state)
            if isinstance(result, dict):
                state.update(result)

            queue.extend(self.edges.get(name, []))

        return state


# ════════════════════════════════════════════════════════════════════
# SimpleVectorStore — in-memory RAG (no external deps)
# ════════════════════════════════════════════════════════════════════

class SimpleVectorStore:
    """
    Minimal in-memory vector store using cosine similarity.
    Uses the LLM's embedding endpoint; falls back to TF-IDF-like hashing
    if embeddings aren't available.

    Examples::

        store = SimpleVectorStore(llm)
        store.add("Python is a programming language.")
        store.add("The sky is blue.")
        docs = store.search("coding language", top_k=1)
    """
    def __init__(self, llm: LLM):
        self.llm   = llm
        self._docs: List[str]         = []
        self._vecs: List[List[float]] = []

    def _embed(self, text: str) -> List[float]:
        try:
            return self.llm.embed(text)
        except Exception:
            # Fallback: simple hash-based pseudo-embedding
            v = [0.0] * 64
            for i, ch in enumerate(text):
                v[i % 64] += ord(ch) / 10000
            norm = (sum(x**2 for x in v) ** 0.5) or 1
            return [x / norm for x in v]

    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na  = sum(x**2 for x in a) ** 0.5
        nb  = sum(x**2 for x in b) ** 0.5
        return dot / (na * nb) if na and nb else 0.0

    def add(self, document: str):
        self._docs.append(document)
        self._vecs.append(self._embed(document))

    def add_many(self, documents: List[str]):
        for doc in documents:
            self.add(doc)

    def search(self, query: str, top_k: int = 3) -> List[str]:
        if not self._docs:
            return []
        qv     = self._embed(query)
        scored = sorted(
            zip(self._vecs, self._docs),
            key=lambda pair: self._cosine(qv, pair[0]),
            reverse=True,
        )
        return [doc for _, doc in scored[:top_k]]

    def __len__(self) -> int:
        return len(self._docs)


# ════════════════════════════════════════════════════════════════════
# RAGAgent — Agent with retrieval-augmented generation
# ════════════════════════════════════════════════════════════════════

class RAGAgent(Agent):
    """
    Agent that automatically retrieves relevant documents before answering.

    Examples::

        store = SimpleVectorStore(llm)
        store.add_many(my_documents)
        agent = RAGAgent("Expert", llm=llm, vector_store=store, top_k=3)
        agent.run("What does the doc say about refunds?")
    """
    def __init__(self, *args, vector_store: SimpleVectorStore, top_k: int = 3, **kwargs):
        super().__init__(*args, **kwargs)
        self.vector_store = vector_store
        self.top_k        = top_k

    def run(self, user_input: str) -> str:
        docs = self.vector_store.search(user_input, top_k=self.top_k)
        if docs:
            ctx     = "\n\n".join(f"[{i+1}] {d}" for i, d in enumerate(docs))
            augment = f"Relevant context:\n{ctx}\n\nUser question: {user_input}"
        else:
            augment = user_input
        return super().run(augment)


# ════════════════════════════════════════════════════════════════════
# Utilities
# ════════════════════════════════════════════════════════════════════

class RateLimiter:
    """Token-bucket rate limiter."""
    def __init__(self, calls_per_minute: int = 60):
        self.interval  = 60.0 / max(calls_per_minute, 1)
        self._last: float = 0.0

    def wait(self):
        elapsed = time.time() - self._last
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self._last = time.time()

    def __call__(self, func: Callable) -> Callable:
        """Use as decorator: @rate_limiter"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            self.wait()
            return func(*args, **kwargs)
        return wrapper


def retry(
    max_attempts: int   = 3,
    delay:        float = 1.0,
    backoff:      float = 2.0,
    exceptions:   tuple = (Exception,),
):
    """
    Retry decorator with exponential backoff.

    Examples::

        @retry(max_attempts=3, delay=1.0, backoff=2.0)
        def call_api():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            wait = delay
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt + 1 >= max_attempts:
                        raise
                    logger.warning(f"[retry] attempt {attempt+1} failed: {e}. Retrying in {wait:.1f}s")
                    time.sleep(wait)
                    wait *= backoff
        return wrapper
    return decorator


# ════════════════════════════════════════════════════════════════════
# Factory helpers
# ════════════════════════════════════════════════════════════════════

def create_agent(
    name:      str,
    api_key:   str,
    system:    str                       = "",
    tools:     Optional[List[Callable]] = None,
    model:     str                       = "deepseek-chat",
    base_url:  str                       = "https://api.deepseek.com",
    **kwargs,
) -> Agent:
    """One-liner agent factory."""
    return Agent(name, llm=LLM(api_key=api_key, model=model, base_url=base_url),
                 system=system, tools=tools, **kwargs)


def create_chain(*steps: Any, verbose: bool = False) -> Chain:
    """One-liner chain factory."""
    return Chain(list(steps), verbose=verbose)
