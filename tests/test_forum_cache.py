"""forum_cache.py 測試：slug 規則、TTL、get/put roundtrip、purge。"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from job_ops.forum_cache import (
    ForumReport,
    company_slug,
    get,
    purge_stale,
    put,
)


def test_company_slug_strips_suffix():
    assert company_slug("Acme 股份有限公司") == company_slug("Acme")


def test_company_slug_strips_punctuation():
    a = company_slug("Acme, Inc.")
    b = company_slug("Acme Inc.")
    assert a == b


def test_company_slug_handles_chinese():
    s = company_slug("104 人力銀行")
    # 中文應保留，數字 + 中文 → "104人力銀行"
    assert "104" in s
    assert "人力銀行" in s


def test_company_slug_empty_falls_to_underscore():
    assert company_slug("") == "_unknown_"


def test_company_slug_pure_punctuation_hashes():
    s = company_slug("（）「」")
    # 純標點 → hash fallback
    assert s != "_unknown_"
    assert len(s) == 12


def _make_report(company="Acme") -> ForumReport:
    return ForumReport(
        company=company,
        slug=company_slug(company),
        queried_at=datetime.now().isoformat(timespec="seconds"),
        positive_signals=["薪資透明"],
        negative_signals=["加班嚴重"],
        quotes=[{"text": "好公司", "source_url": "https://ptt.cc/x"}],
        source_urls=["https://ptt.cc/x"],
        notes="summary here",
    )


def test_put_and_get_roundtrip(tmp_path: Path):
    rep = _make_report()
    put(rep, cache_dir=tmp_path)
    loaded = get("Acme", cache_dir=tmp_path)
    assert loaded is not None
    assert loaded.company == "Acme"
    assert loaded.positive_signals == ["薪資透明"]
    assert loaded.quotes[0]["source_url"] == "https://ptt.cc/x"


def test_get_returns_none_when_missing(tmp_path: Path):
    assert get("NoSuchCo", cache_dir=tmp_path) is None


def test_ttl_expired(tmp_path: Path):
    rep = _make_report()
    put(rep, cache_dir=tmp_path)
    # 直接改寫 queried_at 為 60 天前
    f = tmp_path / f"{rep.slug}.json"
    data = json.loads(f.read_text(encoding="utf-8"))
    data["queried_at"] = (datetime.now() - timedelta(days=60)).isoformat(timespec="seconds")
    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    assert get("Acme", ttl_days=30, cache_dir=tmp_path) is None
    # 但提高 TTL 就拿得到
    assert get("Acme", ttl_days=90, cache_dir=tmp_path) is not None


def test_purge_stale_removes_old(tmp_path: Path):
    # 新 cache 1 筆
    put(_make_report("Fresh"), cache_dir=tmp_path)
    # 舊 cache 1 筆
    old = _make_report("Old")
    put(old, cache_dir=tmp_path)
    f = tmp_path / f"{old.slug}.json"
    data = json.loads(f.read_text(encoding="utf-8"))
    data["queried_at"] = (datetime.now() - timedelta(days=60)).isoformat(timespec="seconds")
    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    removed = purge_stale(ttl_days=30, cache_dir=tmp_path)
    assert removed == 1
    assert get("Fresh", cache_dir=tmp_path) is not None
    assert get("Old", cache_dir=tmp_path) is None


def test_corrupt_cache_returns_none(tmp_path: Path):
    bad = tmp_path / "broken.json"
    bad.write_text("not json", encoding="utf-8")
    # 用同 slug 的公司去讀
    assert get("broken", cache_dir=tmp_path) is None
