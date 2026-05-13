"""8 維評分 + 6 區塊報告組裝。

LLM 推理由 Claude Code skill（主對話）跑；
本模組只負責「資料準備」、「機械式計算」（薪資、活躍度評分）與「報告 markdown 組裝」。

evaluator 暴露的兩個主要 API：
1. prepare_context(url, search_data, detail_data) → EvalContext
    回傳「Claude Code skill 評估需要的所有原始資料」字典，給 skill 主對話讀
2. assemble_report(eval_input) → str
    把 skill 主對話產生的 8 個分數 + 6 區塊文字組裝成 markdown 報告
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .archetypes import Archetype, MatchResult, archetype_score, classify, load_archetypes
from .cv_reader import CVData, read_cv, summarize
from .forum_cache import ForumReport
from .tracker import Evaluation, next_report_num

log = logging.getLogger(__name__)


# 8 維度權重（必須與 _shared.md 一致）
WEIGHTS = {
    "d1_skills": 0.25,
    "d2_salary": 0.15,
    "d3_archetype_fit": 0.10,
    "d4_activeness": 0.15,
    "d5_stability": 0.15,
    "d6_culture": 0.10,
    "d7_growth": 0.05,
    "d8_red_flags": 0.05,
}


def global_score(scores: dict) -> float:
    """8 維加權平均 (1-5 浮點)。

    scores: {"d1_skills": 1-5 int, ...} 8 個 dimension 分數
    """
    total = sum(scores.get(k, 0) * w for k, w in WEIGHTS.items())
    return round(total, 2)


def score_emoji(score: float) -> str:
    if score >= 4.0:
        return "🟢"
    if score >= 3.5:
        return "🟡"
    if score >= 3.0:
        return "🟠"
    return "🔴"


def recommendation(score: float) -> str:
    if score >= 4.0:
        return "強烈建議投"
    if score >= 3.5:
        return "值得投"
    if score >= 3.0:
        return "普通，看其他訊號決定"
    return "不建議投"


# ---------- 機械式維度評分（不需 LLM）----------


def score_salary(salary_min: int | None, profile_min: int, profile_target: int) -> int:
    """第 2 維度：薪資水準。

    salary_min: 104 解析後的月薪下限（面議 = None）
    """
    if salary_min is None:
        # 面議 → 中性分數，由 LLM 進一步從論壇情報調整
        return 3
    if salary_min >= profile_target * 1.2:
        return 5
    if salary_min >= profile_target:
        return 4
    if salary_min >= profile_min:
        return 3
    if salary_min >= profile_min * 0.85:
        return 2
    return 1


def score_activeness(notes: dict) -> int:
    """第 4 維度：徵才活躍度。直接從 104 訊號計算。

    notes: scraper_104.detail() 回傳的 notes dict，含
        - activeness_score: float (0~1)，hrBehaviorPR
        - reply_info: str（"X 小時前回覆求職者"）
        - resume_info: str（"X 小時前聯絡應徵者"）
    """
    score = 3   # 中性起點
    activeness = notes.get("activeness_score")
    if isinstance(activeness, (int, float)):
        if activeness >= 0.8:
            score = 5
        elif activeness >= 0.6:
            score = 4
        elif activeness >= 0.3:
            score = 2
        else:
            score = 1

    # 補強：若有近期聯絡應徵者 < 24h → +1
    resume_info = notes.get("resume_info") or ""
    if "小時前" in resume_info:
        score = min(5, score + 1)
    elif "天前聯絡" in resume_info and "1 週" in resume_info:
        score = max(1, score - 1)

    return score


# ---------- EvalContext: 把資料準備好給 Skill 主對話 ----------


@dataclass
class EvalContext:
    """評估前需要的所有原始資料。給 Claude Code skill 主對話用。"""
    url: str
    job: dict                     # scraper_104.detail() 回傳的完整 dict
    cv: CVData
    cv_summary: str
    archetype_match: MatchResult
    archetype_score: int          # 已計算好的第 3 維度
    salary_score: int             # 已計算好的第 2 維度
    activeness_score: int         # 已計算好的第 4 維度
    profile: dict                 # config/profile.yml content
    forum_report: ForumReport | None
    today: str                    # YYYY-MM-DD


def prepare_context(
    url: str,
    job: dict,
    *,
    cv_path: str | Path = "cv.md",
    profile: dict | None = None,
    forum_report: ForumReport | None = None,
) -> EvalContext:
    """收集所有評估需要的資料。"""
    cv = read_cv(cv_path)
    archetypes = load_archetypes()
    jd_text = (job.get("title", "") + "\n" + job.get("jd", "")).strip()
    match = classify(jd_text, archetypes)

    salary_min = job.get("salary_min")
    pm = (profile or {}).get("target_compensation") or {}
    sal_score = score_salary(
        salary_min,
        profile_min=int(pm.get("monthly_min", 80000)),
        profile_target=int(pm.get("monthly_target", 120000)),
    )

    act_score = score_activeness(job.get("notes") or {})
    arc_score = archetype_score(match)

    return EvalContext(
        url=url,
        job=job,
        cv=cv,
        cv_summary=summarize(cv),
        archetype_match=match,
        archetype_score=arc_score,
        salary_score=sal_score,
        activeness_score=act_score,
        profile=profile or {},
        forum_report=forum_report,
        today=date.today().isoformat(),
    )


# ---------- 報告 markdown 組裝 ----------


@dataclass
class EvalInput:
    """Claude Code skill 主對話跑完評估後產生的完整輸入。

    把所有 8 個分數 + 6 區塊 text 集中，用來組裝 markdown 報告。
    """
    # Identity
    url: str
    company: str
    title: str
    archetype: str
    today: str

    # 6 區塊 markdown text（每個區塊內含 LLM 評估的 narrative）
    block_a_summary: str           # A. 角色摘要
    block_b_cv_match: str          # B. CV 匹配
    block_c_level: str             # C. 等級策略
    block_d_comp: str              # D. 薪酬研究
    block_e_personalization: str   # E. 個人化計畫
    block_f_interview: str         # F. 面試準備
    block_g_legitimacy: str        # G. 招募合法性

    # 8 維度分數
    d1_skills: int
    d2_salary: int
    d3_archetype_fit: int
    d4_activeness: int
    d5_stability: int
    d6_culture: int
    d7_growth: int
    d8_red_flags: int

    legitimacy: str = "Proceed with Caution"
    report_path: str = ""

    def scores_dict(self) -> dict:
        return {
            "d1_skills": self.d1_skills,
            "d2_salary": self.d2_salary,
            "d3_archetype_fit": self.d3_archetype_fit,
            "d4_activeness": self.d4_activeness,
            "d5_stability": self.d5_stability,
            "d6_culture": self.d6_culture,
            "d7_growth": self.d7_growth,
            "d8_red_flags": self.d8_red_flags,
        }


def assemble_report(ev: EvalInput) -> str:
    """組 markdown 報告。"""
    gscore = global_score(ev.scores_dict())
    emoji = score_emoji(gscore)
    rec = recommendation(gscore)

    parts: list[str] = []
    parts.append(f"# 評估報告：{ev.company} — {ev.title}")
    parts.append("")
    parts.append(f"**URL:** {ev.url}")
    parts.append(f"**評估日期:** {ev.today}")
    parts.append(f"**Archetype:** {ev.archetype}")
    parts.append(f"**Global Score:** {gscore:.2f} / 5 {emoji} — {rec}")
    parts.append(f"**Legitimacy:** {ev.legitimacy}")
    parts.append("")
    parts.append("---")
    parts.append("")
    parts.append(ev.block_a_summary)
    parts.append("")
    parts.append("---")
    parts.append("")
    parts.append(ev.block_b_cv_match)
    parts.append("")
    parts.append("---")
    parts.append("")
    parts.append(ev.block_c_level)
    parts.append("")
    parts.append("---")
    parts.append("")
    parts.append(ev.block_d_comp)
    parts.append("")
    parts.append("---")
    parts.append("")
    parts.append(ev.block_e_personalization)
    parts.append("")
    parts.append("---")
    parts.append("")
    parts.append(ev.block_f_interview)
    parts.append("")
    parts.append("---")
    parts.append("")
    parts.append(ev.block_g_legitimacy)
    parts.append("")
    parts.append("---")
    parts.append("")
    parts.append("## 8 維評分總覽")
    parts.append("")
    parts.append("| 維度 | 權重 | 分數 | Emoji |")
    parts.append("|---|---|---|---|")
    parts.append(f"| D1 硬技能+領域匹配 | 25% | {ev.d1_skills} | {score_emoji(ev.d1_skills)} |")
    parts.append(f"| D2 薪資水準 | 15% | {ev.d2_salary} | {score_emoji(ev.d2_salary)} |")
    parts.append(f"| D3 職涯目標契合度 | 10% | {ev.d3_archetype_fit} | {score_emoji(ev.d3_archetype_fit)} |")
    parts.append(f"| D4 徵才活躍度 | 15% | {ev.d4_activeness} | {score_emoji(ev.d4_activeness)} |")
    parts.append(f"| D5 公司穩定性 | 15% | {ev.d5_stability} | {score_emoji(ev.d5_stability)} |")
    parts.append(f"| D6 文化訊號 | 10% | {ev.d6_culture} | {score_emoji(ev.d6_culture)} |")
    parts.append(f"| D7 成長機會 | 5% | {ev.d7_growth} | {score_emoji(ev.d7_growth)} |")
    parts.append(f"| D8 Red Flags | 5% | {ev.d8_red_flags} | {score_emoji(ev.d8_red_flags)} |")
    parts.append(f"| **Global Score** | — | **{gscore:.2f}** | **{emoji}** |")
    parts.append("")
    parts.append(f"_Generated by job-ops evaluator at {ev.today}_")
    parts.append("")
    return "\n".join(parts)


def to_evaluation(ev: EvalInput) -> Evaluation:
    """把 EvalInput 轉成 tracker.Evaluation 寫入 tracker.tsv。"""
    return Evaluation(
        report_num=next_report_num(),
        url=ev.url,
        evaluated_at=ev.today,
        company=ev.company,
        title=ev.title,
        archetype=ev.archetype,
        global_score=global_score(ev.scores_dict()),
        d1_skills=ev.d1_skills,
        d2_salary=ev.d2_salary,
        d3_archetype_fit=ev.d3_archetype_fit,
        d4_activeness=ev.d4_activeness,
        d5_stability=ev.d5_stability,
        d6_culture=ev.d6_culture,
        d7_growth=ev.d7_growth,
        d8_red_flags=ev.d8_red_flags,
        legitimacy=ev.legitimacy,
        report_path=ev.report_path,
    )


def company_slug_for_report(company: str) -> str:
    """報告檔名用的 slug (lowercase, hyphenated)。"""
    if not company:
        return "unknown"
    s = company.strip()
    for suffix in ("股份有限公司", "有限公司", "Co., Ltd.", "Ltd.", "Inc.", "Corp.", "Corporation"):
        s = s.replace(suffix, "")
    s = re.sub(r"[\s_,./\\()（）\[\]【】「」]+", "-", s.strip())
    s = re.sub(r"-+", "-", s).strip("-")
    return s.lower()[:50] or "unknown"


def report_path(company: str, today: str, report_num: str, base_dir: str | Path = "reports/eval") -> Path:
    return Path(base_dir) / f"{report_num}-{company_slug_for_report(company)}-{today}.md"
