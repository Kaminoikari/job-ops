"""AI 意圖偵測 — 判斷 PM 職缺的 JD 是否真的涉及 AI / agentic / automation 工作。

不是純關鍵字比對。設計重點在分辨兩種情況：
  1. 「角色本身做 AI」 — JD 描述規劃 / 打造 / 導入 AI、agent、自動化流程
  2. 「公司碰巧是 AI 公司」 — 只在公司介紹出現 AI 字樣，職務內容與 AI 無關

做法：
  - 加權 lexicon：強 / 中 / 弱訊號各有不同權重，"ai" 這種泛用詞權重最低
  - 動詞鄰近度：訊號詞靠近「規劃 / 打造 / build / lead」等動詞時加成，因為那
    代表這份工作要「做」AI，而不只是提到
  - 否定偵測：JD 明說「不需 AI 經驗」之類時扣分
  - 子字串去重：避免 "agentic" 與 "agentic workflow" 重複計分
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# 訊號 lexicon：phrase（小寫）→ 權重。權重代表「此詞出現代表角色涉及 AI」的強度。

# STRONG：幾乎只會出現在真正做 AI 產品 / agentic 工作的 JD
STRONG_SIGNALS: dict[str, float] = {
    "agentic workflow": 5.0,
    "agentic": 5.0,
    "claude code": 5.0,
    "ai agent": 5.0,
    "llm": 5.0,
    "large language model": 5.0,
    "大型語言模型": 5.0,
    "語言模型": 4.0,
    "rag": 5.0,
    "retrieval augmented": 5.0,
    "prompt engineering": 5.0,
    "prompt 工程": 5.0,
    "mcp server": 5.0,
    "vibe coding": 5.0,
    "生成式 ai": 5.0,
    "生成式人工智慧": 5.0,
    "generative ai": 5.0,
    "genai": 5.0,
    "langchain": 5.0,
    "copilot": 4.0,
    "fine-tune": 5.0,
    "fine tuning": 5.0,
    "向量資料庫": 5.0,
    "vector database": 5.0,
    "ai pm": 5.0,
    "ai product manager": 5.0,
    "ai 產品": 4.0,
    "agent 開發": 5.0,
    "workflow ai": 4.5,
}

# MEDIUM：與 AI 高度相關但用詞較泛
MEDIUM_SIGNALS: dict[str, float] = {
    "人工智慧": 3.0,
    "machine learning": 3.0,
    "機器學習": 3.0,
    "deep learning": 3.0,
    "深度學習": 3.0,
    "automation": 3.0,
    "automate": 2.5,
    "自動化": 2.5,
    "ai-driven": 3.0,
    "ai driven": 3.0,
    "ai-powered": 3.0,
    "ai tool": 3.0,
    "ai 工具": 3.0,
    "ai 應用": 3.0,
    "ai 導入": 3.5,
    "ai enablement": 3.5,
    "ai 落地": 3.5,
    "nlp": 3.0,
    "自然語言": 3.0,
    "computer vision": 3.0,
    "電腦視覺": 3.0,
    "multimodal": 3.0,
    "多模態": 3.0,
    "rpa": 2.5,
    "agent": 3.0,
}

# WEAK：可能只是公司形象包裝，本身不足以判定角色涉及 AI
WEAK_SIGNALS: dict[str, float] = {
    "ai": 1.0,
    "智能": 0.8,
    "智慧化": 1.0,
    "演算法": 1.0,
    "algorithm": 1.0,
    "data-driven": 0.8,
    "數據驅動": 0.8,
}

# 動詞：訊號詞鄰近這些動詞時加成（代表角色要「做」AI，而不只是提到）
ACTION_VERBS: tuple[str, ...] = (
    "規劃", "設計", "導入", "打造", "開發", "負責", "主導", "建構", "建立",
    "運用", "利用", "整合", "落地", "驅動", "推動", "應用", "評估",
    "build", "develop", "design", "lead", "drive", "own", "integrate",
    "leverage", "implement", "deploy", "create", "automate", "explore",
)

# 否定片語：JD 明說不涉及 AI 時扣分
ANTI_SIGNALS: tuple[str, ...] = (
    "不需 ai", "不須 ai", "無需 ai", "不需要 ai", "非 ai 相關",
    "與 ai 無關", "non-ai", "no ai experience",
)

VERB_BOOST = 1.5          # 訊號詞靠近動詞時的權重倍數
VERB_WINDOW = 16          # 動詞鄰近度的字元視窗（前後各 N 字元）
ANTI_PENALTY = 4.0        # 每個否定片語的扣分

# 分數門檻 → tier。tier 為 strong / moderate 時視為 AI PM 職缺。
STRONG_THRESHOLD = 7.0
MODERATE_THRESHOLD = 3.5
WEAK_THRESHOLD = 1.0

_CJK = re.compile(r"[一-鿿]")


@dataclass
class AIIntentResult:
    """單筆職缺的 AI 意圖判定結果。"""
    is_ai_pm: bool
    score: float
    tier: str                          # strong / moderate / weak / none
    matched: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        """轉成可 JSON 序列化的 dict，供 job dict 攜帶。"""
        return {
            "is_ai_pm": self.is_ai_pm,
            "score": self.score,
            "tier": self.tier,
            "matched": list(self.matched),
        }


def _iter_positions(text: str, phrase: str):
    """yield phrase 在 text 中每個出現的起始 index。

    純 ASCII 詞用「非英數邊界」比對，避免 "ai" 誤中 email / detail；
    含中文的詞直接子字串比對（中文無詞邊界問題）。
    """
    if _CJK.search(phrase):
        start = 0
        while True:
            idx = text.find(phrase, start)
            if idx == -1:
                return
            yield idx
            start = idx + 1
    else:
        pattern = r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])"
        for m in re.finditer(pattern, text):
            yield m.start()


def _phrase_present(text: str, phrase: str) -> bool:
    for _ in _iter_positions(text, phrase):
        return True
    return False


def _has_verb_nearby(text: str, phrase: str) -> bool:
    """phrase 的任一出現位置，前後 VERB_WINDOW 字元內是否有 action verb。"""
    for idx in _iter_positions(text, phrase):
        lo = max(0, idx - VERB_WINDOW)
        hi = min(len(text), idx + len(phrase) + VERB_WINDOW)
        ctx = text[lo:hi]
        if any(v in ctx for v in ACTION_VERBS):
            return True
    return False


def classify_ai_intent(job: dict) -> AIIntentResult:
    """判定一筆 job dict 的 AI 意圖。

    job 需有 'jd'（職缺描述）；'title' 可選。
    """
    text = ((job.get("title") or "") + "\n" + (job.get("jd") or "")).lower()
    if not text.strip():
        return AIIntentResult(is_ai_pm=False, score=0.0, tier="none")

    # 收集所有命中的 (phrase, weight, has_verb)
    candidates: list[tuple[str, float, bool]] = []
    for lexicon in (STRONG_SIGNALS, MEDIUM_SIGNALS, WEAK_SIGNALS):
        for phrase, weight in lexicon.items():
            if _phrase_present(text, phrase):
                candidates.append((phrase, weight, _has_verb_nearby(text, phrase)))

    # 子字串去重：若某 phrase 是另一個命中 phrase 的子字串，丟掉較短的
    # （例："agentic" 被 "agentic workflow" 涵蓋；"ai" 被 "ai agent" 涵蓋）
    all_phrases = {c[0] for c in candidates}
    kept = [
        c for c in candidates
        if not any(c[0] != other and c[0] in other for other in all_phrases)
    ]

    score = 0.0
    matched: list[str] = []
    for phrase, weight, has_verb in kept:
        score += weight * (VERB_BOOST if has_verb else 1.0)
        matched.append(phrase)

    for anti in ANTI_SIGNALS:
        if _phrase_present(text, anti):
            score -= ANTI_PENALTY

    score = max(0.0, round(score, 1))
    tier, is_ai_pm = _score_to_tier(score)
    # matched 依權重高→低排序，方便閱讀證據
    matched.sort(key=lambda p: -_phrase_weight(p))
    return AIIntentResult(is_ai_pm=is_ai_pm, score=score, tier=tier, matched=matched)


def _phrase_weight(phrase: str) -> float:
    for lexicon in (STRONG_SIGNALS, MEDIUM_SIGNALS, WEAK_SIGNALS):
        if phrase in lexicon:
            return lexicon[phrase]
    return 0.0


def _score_to_tier(score: float) -> tuple[str, bool]:
    if score >= STRONG_THRESHOLD:
        return "strong", True
    if score >= MODERATE_THRESHOLD:
        return "moderate", True
    if score >= WEAK_THRESHOLD:
        return "weak", False
    return "none", False


def annotate_ai_intent(jobs: list[dict]) -> None:
    """就地為每筆 job dict 加上 'ai_intent' 欄位（dict 形式，可 JSON 序列化）。

    idempotent：重複呼叫只會重算覆寫，不會出錯。
    """
    for job in jobs:
        job["ai_intent"] = classify_ai_intent(job).as_dict()
