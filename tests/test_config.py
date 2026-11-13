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


# ---------- 排除雇主（公司名或 JD 指出隸屬）----------

from job_ops.config import drop_excluded, is_excluded_employer  # noqa: E402
from job_ops.history import Record, ScanResult  # noqa: E402

_SANLIH = FilterConfig(exclude_companies=["三立", "創造智能"], exclude_jd_keywords=["三立集團"])


def test_exclude_jd_keywords_parsed(tmp_path: Path):
    p = tmp_path / "search.yml"
    p.write_text(
        "keywords: [x]\nareas: [y]\nfilters:\n  exclude_jd_keywords: [三立集團]\n",
        encoding="utf-8",
    )
    assert load_search_config(p).filters.exclude_jd_keywords == ["三立集團"]


def test_excluded_by_company_name():
    assert is_excluded_employer("創造智能科技股份有限公司", "", _SANLIH) is True
    assert is_excluded_employer("三立電視台_三立電視股份有限公司", "", _SANLIH) is True


def test_excluded_by_jd_affiliation_when_company_name_unrelated():
    # 只有 JD 擋得住：公司名不含任何排除詞
    jd = "本公司為三立集團 100% 轉投資之 AI 科技公司"
    assert is_excluded_employer("某某新創股份有限公司", jd, _SANLIH) is True


def test_not_excluded_when_neither_matches():
    assert is_excluded_employer("宇見智能科技股份有限公司", "LLM 平台", _SANLIH) is False


def test_blank_entries_do_not_exclude_everyone():
    # YAML 寫出空字串時（`- ""`），"" in 任何字串都成立，會把所有職缺排掉
    cfg = FilterConfig(exclude_companies=[""], exclude_jd_keywords=[""])
    assert is_excluded_employer("宇見智能科技", "LLM 平台", cfg) is False


def test_passes_filters_drops_excluded_employer():
    job = {"title": "產品經理", "company": "某某新創", "salary_min": 90000,
           "jd": "我們是三立集團旗下公司，負責產品規劃"}
    assert passes_filters(job, _SANLIH) is False


def _rec(url, company):
    return Record(url=url, first_seen="2026-11-01", last_seen="2026-11-10",
                  last_104_update="2026/11/10", company=company, title="PM",
                  salary_raw="面議", salary_min="", location="台北市", address="",
                  status="New", salary_history="", notes="{}")


def test_drop_excluded_covers_every_scan_list():
    bad = {"url": "b", "company": "創造智能科技股份有限公司", "jd": ""}
    bad_jd = {"url": "bj", "company": "某某新創", "jd": "三立集團旗下"}
    good = {"url": "g", "company": "宇見智能科技", "jd": "LLM"}
    scan = ScanResult(
        today="2026-11-13",
        new_items=[bad, good], refreshed=[bad_jd, good], salary_changed=[bad, good],
        still_listed=[bad_jd, good],
        missing=[_rec("m1", "三立電視台_三立電視股份有限公司"), _rec("m2", "宇見智能科技")],
        expired=[_rec("e1", "創造智能科技"), _rec("e2", "宇見智能科技")],
        listed_not_scanned=[_rec("l1", "創造智能科技"), _rec("l2", "宇見智能科技")],
    )
    out = drop_excluded(scan, _SANLIH)
    for attr in ("new_items", "refreshed", "salary_changed", "still_listed"):
        assert [j["url"] for j in getattr(out, attr)] == ["g"], attr
    assert [r.url for r in out.missing] == ["m2"]
    assert [r.url for r in out.expired] == ["e2"]
    assert [r.url for r in out.listed_not_scanned] == ["l2"]
