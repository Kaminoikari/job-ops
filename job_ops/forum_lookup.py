"""論壇情報查詢介面。

實際的 WebSearch + WebFetch + LLM 萃取由 Claude Code skill 主對話跑（modes/_shared.md 提供 context）。
本模組只負責：
1. 列出該查的 queries
2. 包裝 cache 讀寫
3. 提供「給定 raw search snippets，回傳 ForumReport」的 builder（供 skill 寫回 cache 用）
"""
from __future__ import annotations

import logging
from datetime import datetime

from .forum_cache import ForumReport, company_slug, get as cache_get, put as cache_put

log = logging.getLogger(__name__)


def build_queries(company: str) -> list[str]:
    """產出該查的 WebSearch queries（給 Claude Code skill 主對話用）。"""
    return [
        f'site:ptt.cc Tech_Job "{company}"',
        f'site:dcard.tw "{company}" 職場',
        f'site:interview.tw {company}',
        f'site:threads.com "{company}"',
        f'"{company}" 評價 OR 心得 OR 面試 OR 離職',
        f'"{company}" 裁員 OR 凍結 OR 募資 2026',
    ]


def lookup_cached(company: str) -> ForumReport | None:
    """讀 cache，不存在或過期回 None。"""
    return cache_get(company)


def save_report(
    company: str,
    *,
    positive_signals: list[str],
    negative_signals: list[str],
    quotes: list[dict],
    source_urls: list[str],
    notes: str = "",
) -> ForumReport:
    """把 Claude Code skill 萃取的論壇情報寫進 cache。"""
    report = ForumReport(
        company=company,
        slug=company_slug(company),
        queried_at=datetime.now().isoformat(timespec="seconds"),
        positive_signals=positive_signals,
        negative_signals=negative_signals,
        quotes=quotes,
        source_urls=source_urls,
        notes=notes,
    )
    cache_put(report)
    return report


def empty_report(company: str, reason: str = "no signals found") -> ForumReport:
    """產生一個「無資料」的 ForumReport，標記在 notes，仍然寫進 cache 避免 30 天內重查。"""
    return save_report(
        company=company,
        positive_signals=[],
        negative_signals=[],
        quotes=[],
        source_urls=[],
        notes=reason,
    )
