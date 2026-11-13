"""重點領域標記：Physical AI／LLM／FDE 三類 PM 缺在日報裡另外 highlight。

與 ai_intent 的分工：
    ai_intent    — AI 訊號強弱，決定排序（tier／priority）
    focus_domain — 這個缺落在哪個使用者指定的重點領域，只決定 highlight，
                   不影響納入門檻與排序

判準依 2026-11-13 對 414 筆在架職缺的實測：
  - JD 只出現一次 LLM 詞的 34 筆幾乎都是順帶提到（「熟悉生成式 AI 工具者佳」），
    所以 LLM 需要職稱命中，或 JD 出現至少兩個不同的核心詞。
  - 「機器人」常出現在公司簡介或應用舉例，單次出現不算；Physical AI 需要職稱命中、
    JD 出現強詞（具身／VLA／sim-to-real…），或機器人類詞累計出現 3 次以上。
  - 「聊天機器人」「機器人流程自動化（RPA）」不是實體機器人，比對前先拿掉。
  - ChatGPT／Claude／Gemini 這類工具名不算 LLM 訊號：它們多半寫在「熟悉工具」
    的條件裡，代表使用者自己要會用，跟產品領域無關。
  - 比對前先移除福利文案（同 domain_filter.has_software_signal 的理由）。
"""
from __future__ import annotations

from job_ops.ai_intent import phrase_count, phrase_present

FOCUS_ORDER: tuple[str, ...] = ("physical_ai", "llm", "fde")

FOCUS_ICONS: dict[str, str] = {
    "physical_ai": "🦾",
    "llm": "🧠",
    "fde": "🚀",
}

FOCUS_LABELS: dict[str, str] = {
    "physical_ai": "🦾 Physical AI",
    "llm": "🧠 LLM",
    "fde": "🚀 FDE",
}

# 比對前從文字中拿掉的片語：字面含「機器人／robot」但不是實體機器人。
_NOT_PHYSICAL = (
    "聊天機器人",
    "對話機器人",
    "客服機器人",
    "機器人流程自動化",
    "robotic process automation",
)

# Physical AI：職稱命中即標。
PHYSICAL_TITLE_TERMS: tuple[str, ...] = (
    "physical ai", "embodied", "具身", "robot", "robots", "robotics", "機器人",
    "humanoid", "人形", "無人機", "drone", "drones", "uav", "自駕",
    "autonomous driving", "amr", "自主移動", "機械手臂", "robotic arm", "vla",
)

# Physical AI：JD 出現一次即標（幾乎只會出現在真正做實體 AI 的 JD）。
PHYSICAL_JD_STRONG: tuple[str, ...] = (
    "physical ai", "embodied ai", "embodied intelligence", "具身智能", "具身智慧",
    "vision-language-action", "vla", "humanoid", "人形機器人", "sim-to-real",
    "sim2real", "sim to real", "isaac sim", "isaac lab", "gr00t",
    "robot foundation model",
)

# Physical AI：JD 累計出現次數達門檻才標（單次常是公司簡介）。
PHYSICAL_JD_REPEATED: tuple[str, ...] = (
    "機器人", "robot", "robots", "robotics", "無人機", "drone", "drones", "uav",
    "自駕", "amr", "自主移動", "機械手臂", "robotic arm",
)
PHYSICAL_REPEAT_THRESHOLD = 3

# LLM：職稱命中即標。
LLM_TITLE_TERMS: tuple[str, ...] = (
    "llm", "genai", "generative ai", "生成式", "大型語言模型", "語言模型",
    "ai agent", "agentic", "智能體", "rag", "copilot", "chatbot", "聊天機器人",
)

# LLM：JD 需出現至少 LLM_MIN_DISTINCT 個不同核心詞（互為子字串者算一個）。
LLM_JD_CORE: tuple[str, ...] = (
    "llm", "large language model", "大型語言模型", "語言模型",
    "生成式 ai", "生成式人工智慧", "generative ai", "genai",
    "rag", "retrieval augmented", "prompt engineering", "prompt",
    "agentic", "ai agent", "智能體", "fine-tune", "fine-tuning", "fine tuning",
    "微調", "foundation model", "基礎模型", "langchain", "向量資料庫",
    "vector database", "embedding", "mcp", "chatbot", "聊天機器人", "copilot",
)
LLM_MIN_DISTINCT = 2

# FDE：title 或 JD 出現即標。
FDE_TERMS: tuple[str, ...] = (
    "forward deployed", "forward-deployed", "fde", "deployment strategist",
    "前線部署",
)

# 「駐點」單獨出現常只是派駐地點（「專案管理師-承攬合作(大直駐點)」），
# 前後 FDE_ONSITE_WINDOW 字內同時出現「客戶」才代表進駐客戶端做導入。
_ONSITE = "駐點"
_ONSITE_CONTEXT = "客戶"
FDE_ONSITE_WINDOW = 20


def _texts(job: dict) -> tuple[str, str]:
    """回傳（小寫 title、小寫 JD），JD 已移除福利文案。"""
    jd = job.get("jd") or ""
    benefits = job.get("benefits") or ""
    if benefits:
        jd = jd.replace(benefits, " ")
    return (job.get("title") or "").lower(), jd.lower()


def _strip_not_physical(text: str) -> str:
    for p in _NOT_PHYSICAL:
        text = text.replace(p, " ")
    return text


def _any(text: str, terms: tuple[str, ...]) -> bool:
    return any(phrase_present(text, t) for t in terms)


def _is_physical(title: str, jd: str) -> bool:
    title = _strip_not_physical(title)
    jd = _strip_not_physical(jd)
    if _any(title, PHYSICAL_TITLE_TERMS) or _any(jd, PHYSICAL_JD_STRONG):
        return True
    hits = sum(phrase_count(jd, t) for t in PHYSICAL_JD_REPEATED)
    return hits >= PHYSICAL_REPEAT_THRESHOLD


def _is_llm(title: str, jd: str) -> bool:
    if _any(title, LLM_TITLE_TERMS):
        return True
    found = {t for t in LLM_JD_CORE if phrase_present(jd, t)}
    distinct = {t for t in found if not any(t != o and t in o for o in found)}
    return len(distinct) >= LLM_MIN_DISTINCT


def _onsite_at_customer(text: str) -> bool:
    start = 0
    while (idx := text.find(_ONSITE, start)) != -1:
        lo = max(0, idx - FDE_ONSITE_WINDOW)
        hi = idx + len(_ONSITE) + FDE_ONSITE_WINDOW
        if _ONSITE_CONTEXT in text[lo:hi]:
            return True
        start = idx + 1
    return False


def _is_fde(title: str, jd: str) -> bool:
    text = title + "\n" + jd
    return _any(text, FDE_TERMS) or _onsite_at_customer(text)


def classify_focus_domains(job: dict) -> list[str]:
    """回傳這筆職缺命中的重點領域 key，依 FOCUS_ORDER 排序；沒命中回空 list。"""
    title, jd = _texts(job)
    checks = {
        "physical_ai": _is_physical,
        "llm": _is_llm,
        "fde": _is_fde,
    }
    return [k for k in FOCUS_ORDER if checks[k](title, jd)]
