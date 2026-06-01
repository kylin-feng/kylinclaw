"""
Example 1: Basic Agent with Tools
----------------------------------
Single agent with tool use — ReAct loop.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kylinclaw import LLM, Agent, tool

# ── Define tools ──────────────────────────────────────────────────────────────

@tool
def calculator(expression: str) -> str:
    """Evaluate a math expression and return the result."""
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {e}"


@tool
def get_weather(city: str) -> str:
    """Get current weather for a city (mock data)."""
    weather_db = {
        "beijing": "Sunny, 25°C",
        "shanghai": "Cloudy, 22°C",
        "shenzhen": "Rainy, 28°C",
    }
    return weather_db.get(city.lower(), f"No data for {city}")


# ── Setup LLM & Agent ─────────────────────────────────────────────────────────

llm = LLM(
    api_key=os.environ.get("OPENAI_API_KEY", "sk-your-key"),
    model="deepseek-chat",
    base_url="https://api.deepseek.com/v1",
)

agent = Agent(
    name="Assistant",
    llm=llm,
    tools=[calculator, get_weather],
    system="You are a helpful assistant. Use tools when needed.",
    max_steps=5,
)

# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    questions = [
        "What is 2**10 + 3**5?",
        "What's the weather in Beijing and Shanghai?",
    ]
    for q in questions:
        print(f"\nQ: {q}")
        print(f"A: {agent.run(q)}")
