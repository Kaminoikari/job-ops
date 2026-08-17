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
    """pipeline 的納入門檻若退回「只看 has_ai」，通篇沒提 AI 的 SaaS PM 缺會被
    整筆剔除，而 domain_filter 自己的單元測試仍然全綠——這條綁住那段接線。"""
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
