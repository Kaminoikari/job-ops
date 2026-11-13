"""run-daily.py 的設定傳遞測試：確認 config 的值真的送進 scrape_all。

為什麼需要這層：search() 內部的參數組裝已有測試，config 解析也有測試，但
「cfg.jobcat_recency_days → scrape_all(jobcat_recency_days=...)」這段接線
若被刪掉，兩邊的測試都還是綠的，jobcat 查詢會靜默退回沒有時間窗的行為。
這裡驅動真實的 _do_scrape 入口，把寫入端（YAML）與讀取端（scrape_all 收到
的 kwargs）綁在同一條測試上。
"""
from __future__ import annotations

import asyncio
import importlib.util
import logging
from pathlib import Path

import pytest

from job_ops.config import load_search_config

ROOT = Path(__file__).resolve().parent.parent


def _load_run_daily():
    """run-daily.py 檔名有連字號，不能直接 import，用 importlib 從路徑載入。"""
    spec = importlib.util.spec_from_file_location(
        "run_daily_under_test", ROOT / "scripts" / "run-daily.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "search.yml"
    p.write_text(body, encoding="utf-8")
    return p


def test_domain_gate_keeps_saas_pm_without_ai_signal():
    """綁住 apply_domain_gate 的篩選行為：若它退回「只看 has_ai」，通篇沒提 AI 的
    SaaS PM 缺會被整筆剔除。

    範圍限制：這條只驅動 apply_domain_gate 本身，沒有驅動 main() 的呼叫點
    （main() 需要真實爬蟲與 email，測試不跑它）。
    """
    run_daily = _load_run_daily()
    saas_pm = {
        "url": "https://www.104.com.tw/job/saas1",
        "title": "產品經理",
        "jd": "負責主導軟體產品的開發與優化，熟悉 SaaS 產品管理。",
    }
    ai_pm = {
        "url": "https://www.104.com.tw/job/aipm1",
        "title": "AI 產品經理",
        "jd": "負責大型語言模型應用的產品規劃。",
    }
    hardware_pm = {
        "url": "https://www.104.com.tw/job/hw1",
        "title": "產品經理",
        "jd": "負責機構件模具開發進度、料號成本與量產良率追蹤。",
    }

    kept = run_daily.apply_domain_gate(
        [saas_pm, ai_pm, hardware_pm], logging.getLogger("test")
    )
    kept_urls = [j["url"] for j in kept]

    assert "https://www.104.com.tw/job/saas1" in kept_urls
    assert "https://www.104.com.tw/job/aipm1" in kept_urls
    assert "https://www.104.com.tw/job/hw1" not in kept_urls


def test_domain_gate_bucket_counts_are_reported(caplog):
    """三桶統計是之後調詞庫的唯一依據（重跑掃描會被 104 限流），數字錯了就白記。
    僅 AI + 僅軟體 + 兩者皆有 必須等於保留數。"""
    run_daily = _load_run_daily()
    jobs = [
        {"title": "AI 產品經理", "jd": "負責大型語言模型應用的產品規劃。"},        # 僅 AI
        {"title": "產品經理", "jd": "負責 SaaS 軟體產品的規劃。"},                # 僅軟體
        {"title": "AI 產品經理", "jd": "負責 SaaS 軟體產品的大型語言模型應用。"},  # 兩者
        {"title": "產品經理", "jd": "負責模具開發進度與料號成本管理。"},          # 皆無
    ]
    with caplog.at_level(logging.INFO):
        kept = run_daily.apply_domain_gate(jobs, logging.getLogger("gate-test"))

    assert len(kept) == 3
    msg = caplog.text
    assert "僅 AI 訊號 1" in msg, msg
    assert "僅軟體訊號 1" in msg, msg
    assert "兩者皆有 1" in msg, msg


@pytest.mark.parametrize("yaml_value,expected", [("3", 3), ("0", 0), ("null", None)])
def test_do_scrape_forwards_jobcat_recency_days(tmp_path: Path, monkeypatch, yaml_value, expected):
    run_daily = _load_run_daily()
    captured: dict = {}

    async def _fake_scrape_all(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(run_daily, "scrape_all", _fake_scrape_all)

    cfg = load_search_config(_config(tmp_path, f"""
keywords: [產品經理]
areas: [台北市]
jobcats: ["2004003009"]
jobcat_recency_days: {yaml_value}
"""))
    asyncio.run(run_daily._do_scrape(cfg))

    assert captured["jobcat_recency_days"] == expected
    # 同時確認其餘既有設定沒有在這條路徑上掉件
    assert captured["jobcats"] == ["2004003009"]
    assert captured["keywords"] == ["產品經理"]


# ---------- 排除雇主：main() 兩條路徑都不能漏 ----------

import json  # noqa: E402
import sys  # noqa: E402

_EXCLUDE_YAML = """
keywords: [產品經理]
areas: [台北市]
filters:
  exclude_companies: [創造智能]
  exclude_jd_keywords: [三立集團]
"""

_HISTORY_HEADER = ("url\tfirst_seen\tlast_seen\tlast_104_update\tcompany\ttitle\tsalary_raw\t"
                   "salary_min\tlocation\taddress\tstatus\tsalary_history\tnotes\n")


def _point_paths(run_daily, monkeypatch, tmp_path):
    cfg = tmp_path / "search.yml"
    cfg.write_text(_EXCLUDE_YAML, encoding="utf-8")
    monkeypatch.setattr(run_daily, "CONFIG_PATH", cfg)
    monkeypatch.setattr(run_daily, "HISTORY_PATH", tmp_path / "history.tsv")
    monkeypatch.setattr(run_daily, "LAST_SCAN_PATH", tmp_path / "last-scan.json")
    monkeypatch.setattr(run_daily, "REPORT_DIR", tmp_path / "reports")
    monkeypatch.setattr(run_daily, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(run_daily, "SAMPLE_DUMP_PATH", tmp_path / "logs" / "s.json")


def _report_html(tmp_path):
    return next((tmp_path / "reports").glob("*.html")).read_text(encoding="utf-8")


def test_main_live_path_excludes_employer_from_report_and_verification(tmp_path, monkeypatch):
    """歷史裡已有被排除公司的職缺：今天掃描濾掉後它會變成 missing，若不在驗證前
    排除，就會被 detail 確認在架而出現在「在架未掃到」。"""
    run_daily = _load_run_daily()
    _point_paths(run_daily, monkeypatch, tmp_path)
    (tmp_path / "history.tsv").write_text(
        _HISTORY_HEADER
        + "https://www.104.com.tw/job/old\t2026-10-30\t2026-11-12\t2026/11/10\t"
          "創造智能科技股份有限公司\tAI應用規劃師\t面議\t\t台北市\t\tNew\t\t{}\n"
        + "https://www.104.com.tw/job/keep\t2026-10-30\t2026-11-12\t2026/11/10\t"
          "宇見智能科技\t舊 PM 職缺\t面議\t\t台北市\t\tNew\t\t{}\n",
        encoding="utf-8",
    )
    scraped = [
        {"url": "https://www.104.com.tw/job/bad", "title": "AI 產品經理",
         "company": "創造智能科技股份有限公司", "jd": "負責大型語言模型 LLM 產品規劃",
         "salary_min": None, "104_update_date": "2026/11/13"},
        {"url": "https://www.104.com.tw/job/badjd", "title": "AI 產品經理",
         "company": "某某新創", "jd": "三立集團旗下，負責大型語言模型 LLM 產品規劃",
         "salary_min": None, "104_update_date": "2026/11/13"},
        {"url": "https://www.104.com.tw/job/good", "title": "AI 產品經理",
         "company": "宇見智能科技", "jd": "負責大型語言模型 LLM 產品規劃",
         "salary_min": None, "104_update_date": "2026/11/13"},
    ]
    verified: list[str] = []

    async def _fake_scrape_all(**kwargs):
        return [dict(j) for j in scraped]

    async def _fake_verify(urls):
        verified.extend(urls)
        return {u: True for u in urls}

    monkeypatch.setattr(run_daily, "scrape_all", _fake_scrape_all)
    monkeypatch.setattr(run_daily, "verify_listings_alive", _fake_verify)
    monkeypatch.setattr(sys, "argv", ["run-daily.py", "--no-email"])

    assert run_daily.main() == 0
    assert verified == ["https://www.104.com.tw/job/keep"]
    html = _report_html(tmp_path)
    assert "job/good" in html and "job/keep" in html
    for bad in ("job/bad\"", "job/badjd", "job/old", "創造智能"):
        assert bad not in html, bad


def test_main_cached_path_excludes_employer(tmp_path, monkeypatch):
    """--email-only／--dry-run 讀的是排除名單加入前寫下的快取，必須在讀回時再濾一次。"""
    run_daily = _load_run_daily()
    _point_paths(run_daily, monkeypatch, tmp_path)
    bad = {"url": "https://www.104.com.tw/job/bad", "title": "AI 產品經理",
           "company": "創造智能科技股份有限公司", "jd": "LLM", "salary_min": None}
    good = {"url": "https://www.104.com.tw/job/good", "title": "AI 產品經理",
            "company": "宇見智能科技", "jd": "LLM", "salary_min": None}
    rec = {"url": "https://www.104.com.tw/job/lns", "first_seen": "2026-10-30",
           "last_seen": "2026-11-12", "last_104_update": "2026/11/10",
           "company": "創造智能科技股份有限公司", "title": "AI應用規劃師",
           "salary_raw": "面議", "salary_min": "", "location": "台北市", "address": "",
           "status": "ListedNotScanned", "salary_history": "", "notes": "{}"}
    (tmp_path / "last-scan.json").write_text(json.dumps({
        "today": "2026-11-13", "today_jobs": [bad, good],
        "scan": {"new_items": [bad, good], "refreshed": [], "salary_changed": [],
                 "still_listed": [], "expired": [], "listed_not_scanned": [rec]},
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["run-daily.py", "--dry-run"])

    assert run_daily.main() == 0
    html = _report_html(tmp_path)
    assert "job/good" in html
    assert "job/bad" not in html and "job/lns" not in html and "創造智能" not in html
