"""config.load_search_config 測試：jobcats 解析與預設。"""
from __future__ import annotations

from pathlib import Path

import pytest

from job_ops.config import FilterConfig, load_search_config, passes_filters


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "search.yml"
    p.write_text(body, encoding="utf-8")
    return p


def test_jobcats_parsed_as_str_list(tmp_path: Path):
    cfg = load_search_config(_write(tmp_path, """
keywords: [產品經理]
areas: [台北市]
jobcats:
  - "2004003009"
  - 2004003004
"""))
    # 數字與字串混寫都正規化成 str（104 API 需要字串代碼）
    assert cfg.jobcats == ["2004003009", "2004003004"]


def test_jobcats_defaults_to_empty_when_absent(tmp_path: Path):
    cfg = load_search_config(_write(tmp_path, """
keywords: [產品經理]
areas: [台北市]
"""))
    assert cfg.jobcats == []


def test_jobcat_recency_days_parsed(tmp_path: Path):
    cfg = load_search_config(_write(tmp_path, """
keywords: [產品經理]
areas: [台北市]
jobcats: ["2004003009"]
jobcat_recency_days: 3
"""))
    assert cfg.jobcat_recency_days == 3


def test_jobcat_recency_days_zero_is_kept_not_coerced_to_none(tmp_path: Path):
    """0 = 僅今日，是合法值；用真值判斷會把它靜默變成「不限時間」。"""
    cfg = load_search_config(_write(tmp_path, """
keywords: [產品經理]
areas: [台北市]
jobcat_recency_days: 0
"""))
    assert cfg.jobcat_recency_days == 0


def test_jobcat_recency_days_rejects_value_104_does_not_accept(tmp_path: Path):
    """不合法的值若拖到第一個 jobcat 查詢才爆，前面數分鐘的 keyword 結果會全丟。
    載入設定時就要擋下來。"""
    with pytest.raises(ValueError):
        load_search_config(_write(tmp_path, """
keywords: [產品經理]
areas: [台北市]
jobcat_recency_days: 5
"""))


def test_jobcat_recency_days_defaults_to_none_when_absent(tmp_path: Path):
    cfg = load_search_config(_write(tmp_path, """
keywords: [產品經理]
areas: [台北市]
"""))
    assert cfg.jobcat_recency_days is None


# ---------- passes_filters × 職稱過濾（雙層保險）----------


def test_passes_filters_rejects_engineer_title_even_if_salary_ok():
    cfg = FilterConfig(min_salary_monthly=0, include_negotiable_salary=True)
    job = {"title": "電腦視覺工程師", "company": "某公司", "salary_min": 80000}
    assert passes_filters(job, cfg) is False


def test_passes_filters_keeps_product_manager_title():
    cfg = FilterConfig(min_salary_monthly=0, include_negotiable_salary=True)
    job = {"title": "資深產品經理 Senior Product Manager", "company": "某公司", "salary_min": 80000}
    assert passes_filters(job, cfg) is True
