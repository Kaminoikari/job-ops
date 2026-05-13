"""論壇情報 JSON cache (30 天 TTL)。"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

CACHE_DIR = Path("data/forum-cache")
DEFAULT_TTL_DAYS = 30


@dataclass
class ForumReport:
    """單一公司的論壇情報結構。"""
    company: str
    slug: str
    queried_at: str          # ISO datetime
    positive_signals: list[str] = field(default_factory=list)
    negative_signals: list[str] = field(default_factory=list)
    quotes: list[dict] = field(default_factory=list)   # {"text": "...", "source_url": "..."}
    source_urls: list[str] = field(default_factory=list)
    notes: str = ""          # 自由文字摘要

    def to_dict(self) -> dict:
        return asdict(self)


def company_slug(company: str) -> str:
    """把公司名稱轉成 cache key 安全的 slug。

    保留中文，但移除空白、標點與股份有限公司等常見後綴的差異。
    """
    if not company:
        return "_unknown_"
    # 移除常見後綴
    s = company.strip()
    for suffix in (
        "股份有限公司",
        "有限公司",
        "Co., Ltd.",
        "Ltd.",
        "Inc.",
        "Corp.",
        "Corporation",
    ):
        s = s.replace(suffix, "")
    # 移除空白與標點，但保留中文與英數
    s = re.sub(r"[\s\-_,.()（）\[\]【】「」]+", "", s)
    if not s:
        # 完全變空 → hash 原字串
        return hashlib.md5(company.encode("utf-8")).hexdigest()[:12]
    return s.lower()


def _cache_path(slug: str, cache_dir: Path = CACHE_DIR) -> Path:
    return cache_dir / f"{slug}.json"


def get(company: str, ttl_days: int = DEFAULT_TTL_DAYS, cache_dir: Path = CACHE_DIR) -> ForumReport | None:
    """讀 cache，回傳 ForumReport；不存在或過期回 None。"""
    slug = company_slug(company)
    path = _cache_path(slug, cache_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        queried_at = datetime.fromisoformat(data["queried_at"])
        if datetime.now() - queried_at > timedelta(days=ttl_days):
            log.info("forum cache expired for %s (slug=%s)", company, slug)
            return None
        return ForumReport(**data)
    except Exception as e:
        log.warning("forum cache read error for %s: %s", company, e)
        return None


def put(report: ForumReport, cache_dir: Path = CACHE_DIR) -> Path:
    """寫 cache。"""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(report.slug, cache_dir)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("forum cache written: %s", path)
    return path


def purge_stale(ttl_days: int = DEFAULT_TTL_DAYS, cache_dir: Path = CACHE_DIR) -> int:
    """刪除過期 cache，回傳刪除筆數。"""
    if not cache_dir.exists():
        return 0
    removed = 0
    cutoff = datetime.now() - timedelta(days=ttl_days)
    for p in cache_dir.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            queried_at = datetime.fromisoformat(data["queried_at"])
            if queried_at < cutoff:
                p.unlink()
                removed += 1
        except Exception:
            # 壞檔直接刪
            p.unlink()
            removed += 1
    return removed
