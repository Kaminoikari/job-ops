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
