"""YAML config + .env loader."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv


@dataclass
class FilterConfig:
    min_salary_monthly: int = 0
    include_negotiable_salary: bool = True
    exclude_keywords: list[str] = field(default_factory=list)
    exclude_companies: list[str] = field(default_factory=list)


@dataclass
class SearchConfig:
    keywords: list[str]
    areas: list[str]
    jobcats: list[str] = field(default_factory=list)  # 104 職務類別代碼，職類精準涵蓋
    max_pages_per_keyword: int = 5
    from_date: str | None = None         # YYYY-MM-DD；只保留 appearDate >= 此日期
    filters: FilterConfig = field(default_factory=FilterConfig)


@dataclass
class EmailEnv:
    sender: str | None
    app_password: str | None
    recipient: str | None

    @property
    def ready(self) -> bool:
        return bool(self.sender and self.app_password and self.recipient)

    def missing(self) -> list[str]:
        return [
            name for name, val in [
                ("GMAIL_USER", self.sender),
                ("GMAIL_APP_PASSWORD", self.app_password),
                ("NOTIFY_EMAIL_TO", self.recipient),
            ] if not val
        ]


def load_search_config(path: str | Path) -> SearchConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    filt = raw.get("filters") or {}
    return SearchConfig(
        keywords=list(raw.get("keywords") or []),
        areas=list(raw.get("areas") or []),
        jobcats=[str(c) for c in (raw.get("jobcats") or [])],
        max_pages_per_keyword=int(raw.get("max_pages_per_keyword", 5)),
        from_date=(raw.get("from_date") or None),
        filters=FilterConfig(
            min_salary_monthly=int(filt.get("min_salary_monthly", 0) or 0),
            include_negotiable_salary=bool(filt.get("include_negotiable_salary", True)),
            exclude_keywords=list(filt.get("exclude_keywords") or []),
            exclude_companies=list(filt.get("exclude_companies") or []),
        ),
    )


def load_email_env(env_path: str | Path | None = None) -> EmailEnv:
    if env_path is not None and Path(env_path).exists():
        load_dotenv(env_path, override=False)
    else:
        load_dotenv(override=False)  # 預設讀 cwd 的 .env
    # 移除 app password 中的空白（Google 顯示時會有空格）
    pw = os.getenv("GMAIL_APP_PASSWORD") or None
    if pw:
        pw = pw.replace(" ", "")
    return EmailEnv(
        sender=os.getenv("GMAIL_USER") or None,
        app_password=pw,
        recipient=os.getenv("NOTIFY_EMAIL_TO") or None,
    )


def passes_filters(job: dict, cfg: FilterConfig) -> bool:
    """判斷一筆 job dict 是否通過 filter 條件。"""
    title = job.get("title", "")
    company = job.get("company", "")
    salary_min = job.get("salary_min")

    if any(kw in title for kw in cfg.exclude_keywords):
        return False
    if any(c in company for c in cfg.exclude_companies):
        return False

    if salary_min is None:
        return cfg.include_negotiable_salary
    return salary_min >= cfg.min_salary_monthly
