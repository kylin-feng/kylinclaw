"""
Example 2: Multi-Agent with Chain and Crew
-------------------------------------------
Chain = sequential pipeline (output of step N is input to step N+1)
Crew  = multiple agents collaborate, sharing accumulated context
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kylinclaw import LLM, Agent, Prompt, Chain, Crew

llm = LLM(
    api_key=os.environ.get("OPENAI_API_KEY", "sk-your-key"),
    model="deepseek-chat",
    base_url="https://api.deepseek.com/v1",
)

# ── Example A: Chain ──────────────────────────────────────────────────────────
# Step 1: Extract key points
# Step 2: Translate to English
# Step 3: Write a tweet

extractor = Agent("Extractor", llm=llm,
    system="Extract 3 key points from the text. Be concise.")

translator = Agent("Translator", llm=llm,
    system="Translate the given Chinese text to English.")

tweeter = Agent("Tweeter", llm=llm,
    system="Turn the given points into a single engaging tweet under 280 chars.")

chain = extractor | translator | tweeter
# Equivalent: chain = Chain([extractor, translator, tweeter])

article = """
人工智能正在改变各行各业。医疗领域，AI可以辅助诊断疾病；教育领域，
AI可以个性化教学内容；制造业，AI驱动的机器人正在提升生产效率。
未来十年，AI将重塑全球经济格局。
"""

print("=== Chain example ===")
print(chain.run(article))


# ── Example B: Crew ───────────────────────────────────────────────────────────
# Researcher → Critic → Editor working on the same task

researcher = Agent("Researcher", llm=llm,
    system="You are a thorough researcher. Investigate the topic and provide facts.")

critic = Agent("Critic", llm=llm,
    system="You are a critical reviewer. Point out weaknesses in the research.")

editor = Agent("Editor", llm=llm,
    system="You are a professional editor. Produce a polished final report.")

crew = Crew(agents=[researcher, critic, editor])

print("\n=== Crew example ===")
result = crew.run("The impact of large language models on software development")
print(result)
