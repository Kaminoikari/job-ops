"""讀 cv.md，萃取結構化資料給 evaluator 用。

簡單版本：用 heading 切割 + 條列點抓取。後續可換 LLM extraction。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class CVData:
    headline: str = ""
    summary: str = ""
    hard_skills: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    years_of_experience: int = 0
    current_role: str = ""
    work_experience: list[str] = field(default_factory=list)   # 每筆是一段 markdown
    proof_points: list[str] = field(default_factory=list)
    raw_text: str = ""

    @property
    def is_template(self) -> bool:
        """偵測是否還是未填的模板（包含 {...} placeholder）"""
        # 計算 placeholder 比例：raw_text 中有多少 {...}
        placeholders = re.findall(r"\{[^}]+\}", self.raw_text)
        return len(placeholders) >= 5


def _split_sections(text: str) -> dict[str, str]:
    """把 markdown 切成 {heading: body} dict。Heading 用 H2 (## )。"""
    sections: dict[str, str] = {}
    current_h = "_preamble"
    buf: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            sections[current_h] = "\n".join(buf).strip()
            current_h = m.group(1).strip().lower()
            buf = []
        else:
            buf.append(line)
    sections[current_h] = "\n".join(buf).strip()
    return sections


def _extract_list_items(body: str) -> list[str]:
    """從 markdown body 抓所有 `- xxx` 或 `* xxx` 條列項。"""
    items: list[str] = []
    for line in body.splitlines():
        m = re.match(r"^\s*[-*]\s+(.+?)\s*$", line)
        if m:
            items.append(m.group(1).strip())
    return items


def _extract_skills_keywords(items: list[str]) -> list[str]:
    """把條列項中『標籤: keyword1, keyword2』格式的右側 keywords 攤平。

    Examples:
        "工具：Figma、Jira、Linear" → ["Figma", "Jira", "Linear"]
        "Python (pandas, ETL)"     → ["Python", "pandas", "ETL"]
    """
    out: list[str] = []
    for item in items:
        # 移除括號內補述
        cleaned = re.sub(r"[（(][^）)]*[）)]", "", item)
        # 取「標籤」後面的部份
        if "：" in cleaned:
            cleaned = cleaned.split("：", 1)[1]
        elif ":" in cleaned:
            cleaned = cleaned.split(":", 1)[1]
        # 用常見分隔切
        parts = re.split(r"[,、，/]\s*", cleaned)
        for p in parts:
            p = p.strip()
            if p and len(p) <= 40 and not p.startswith("{"):
                out.append(p)
    return out


def read_cv(path: str | Path = "cv.md") -> CVData:
    """讀 cv.md，回傳結構化資料。檔案不存在 raise FileNotFoundError。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"cv.md not found at {p.resolve()}")

    text = p.read_text(encoding="utf-8")
    sections = _split_sections(text)
    cv = CVData(raw_text=text)

    # Headline
    cv.headline = sections.get("headline", "").splitlines()[0].strip() if sections.get("headline") else ""

    # Professional Summary
    cv.summary = sections.get("professional summary", "").strip()

    # Hard Skills — 條列項 → 攤平
    hs_items = _extract_list_items(sections.get("hard skills", ""))
    cv.hard_skills = _extract_skills_keywords(hs_items)

    # Domains
    cv.domains = _extract_list_items(sections.get("domains", ""))

    # Years of Experience
    yoe_body = sections.get("years of experience", "")
    m = re.search(r"\d+", yoe_body)
    if m:
        cv.years_of_experience = int(m.group(0))

    # Current Role
    cv.current_role = sections.get("current role", "").splitlines()[0].strip() if sections.get("current role") else ""

    # Work Experience — 用 H3 切，每段一筆
    we_body = sections.get("work experience", "")
    if we_body:
        chunks = re.split(r"^###\s+", we_body, flags=re.MULTILINE)
        cv.work_experience = [c.strip() for c in chunks if c.strip()]

    # Proof Points — 條列項
    cv.proof_points = _extract_list_items(sections.get("proof points", ""))

    return cv


def summarize(cv: CVData) -> str:
    """產生 1 段簡短摘要給 evaluator 用 (≤ 200 字)。"""
    return (
        f"Headline: {cv.headline}\n"
        f"Years: {cv.years_of_experience}\n"
        f"Current: {cv.current_role}\n"
        f"Hard Skills ({len(cv.hard_skills)}): {', '.join(cv.hard_skills[:15])}\n"
        f"Domains: {', '.join(cv.domains)}\n"
        f"Proof points ({len(cv.proof_points)}): {'; '.join(cv.proof_points[:3])}"
    )
