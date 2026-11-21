"""术语表：既作 initial_prompt（喂给解码器），也作事后正则校正（不改变原意，只修拼写）。"""
import re

GLOSSARY = (
    "以下是一段关于人工智能行业的中文口播，涉及的英文术语：Scaling Law, OpenAI, DeepMind, "
    "Chinchilla, Gopher, Ilya Sutskever, emergence, ChatGPT, LLaMA, Qwen, RAG, MoE, "
    "DeepSeek V3, DeepSeek R1, o1, test-time compute, Salesforce Agentforce, Skill, "
    "CLI-Anything, REA, Agent, MCP, API。"
)

TERM_FIXES = [
    (r"scal+ing\s*lo[wg]", "Scaling Law"),
    (r"scal+ing\s*la+w", "Scaling Law"),
    (r"open\s*[ia]+\b", "OpenAI"),
    (r"giler\b|gopher\b", "Gopher"),
    (r"chinch?ella|chinchilla", "Chinchilla"),
    (r"alice\s*suckever|ilya\s*s(ut|uck)ever", "Ilya Sutskever"),
    (r"de[e]?p\s*sea\s*(v3|v-3)", "DeepSeek V3"),
    (r"deep\s*seq\s*r1", "DeepSeek R1"),
    (r"chat\s*gbt|chaigbt", "ChatGPT"),
    (r"agent\s*force", "Agentforce"),
    (r"clean\s*anything", "CLI-Anything"),
    (r"\brack\b", "RAG"),
]


def fix(text: str) -> str:
    for pat, rep in TERM_FIXES:
        text = re.sub(pat, rep, text, flags=re.IGNORECASE)
    return text


KEY_TERMS = ["Scaling Law", "OpenAI", "Gopher", "Chinchilla", "DeepMind", "RAG", "MoE",
             "ChatGPT", "Qwen", "LLaMA", "Agentforce", "DeepSeek", "Skill", "CLI-Anything"]


def keyhits(text: str):
    return {k: text.count(k) for k in KEY_TERMS if text.count(k)}