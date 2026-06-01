"""scraper_104.search() 測試：jobcat / keyword 參數組裝與互斥保護。

用 httpx.MockTransport 攔截 104 search API，斷言送出的 query params 正確；
limiter.wait 被 no-op 掉避免測試 sleep。
"""
from __future__ import annotations

import httpx
import pytest

from job_ops.scraper_104 import OneZeroFourScraper


def _make_scraper(handler):
    """建一個用 MockTransport 攔截請求、且 limiter 不 sleep 的 scraper。"""
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    scraper = OneZeroFourScraper(client=client)

    async def _no_wait() -> None:
        return None

    scraper._limiter.wait = _no_wait  # type: ignore[method-assign]
    return scraper


def _one_job_then_empty(captured: list[dict]):
    """回傳 handler：第 1 頁給一筆職缺，第 2 頁起回空（讓翻頁迴圈停止）。"""

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        captured.append(params)
        if params.get("page") == "1":
            data = [{"link": {"job": "//www.104.com.tw/job/abc12"},
                     "custName": "X 公司", "jobName": "PM", "appearDate": "20260601"}]
        else:
            data = []
        return httpx.Response(200, json={"data": data})

    return handler


@pytest.mark.asyncio
async def test_search_jobcat_mode_sets_jobcat_not_keyword():
    captured: list[dict] = []
    scraper = _make_scraper(_one_job_then_empty(captured))
    try:
        results = await scraper.search(areas=["台北市"], max_pages=1, jobcat="2004003009")
    finally:
        await scraper.close()

    assert len(results) == 1
    assert results[0]["url"] == "https://www.104.com.tw/job/abc12"
    params = captured[0]
    assert params["jobcat"] == "2004003009"
    assert "keyword" not in params       # jobcat-only 模式不帶 keyword
    assert params["area"]                # 地區有解析


@pytest.mark.asyncio
async def test_search_keyword_mode_sets_keyword_not_jobcat():
    captured: list[dict] = []
    scraper = _make_scraper(_one_job_then_empty(captured))
    try:
        await scraper.search("產品經理", areas=["台北市"], max_pages=1)
    finally:
        await scraper.close()

    params = captured[0]
    assert params["keyword"] == "產品經理"
    assert "jobcat" not in params


@pytest.mark.asyncio
async def test_search_requires_keyword_or_jobcat():
    scraper = _make_scraper(_one_job_then_empty([]))
    try:
        with pytest.raises(ValueError):
            await scraper.search(areas=["台北市"], max_pages=1)
    finally:
        await scraper.close()
