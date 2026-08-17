"""scraper_104.search() 測試：jobcat / keyword 參數組裝與互斥保護。

用 httpx.MockTransport 攔截 104 search API，斷言送出的 query params 正確；
limiter.wait 被 no-op 掉避免測試 sleep。
"""
from __future__ import annotations

import httpx
import pytest

from job_ops import scraper_104 as scraper_module
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


@pytest.mark.asyncio
async def test_search_recency_days_sets_isnew_param():
    """recency_days 會轉成 104 的 isnew 參數（伺服器端只回近 N 天更新的職缺）。"""
    captured: list[dict] = []
    scraper = _make_scraper(_one_job_then_empty(captured))
    try:
        await scraper.search(areas=["台北市"], max_pages=1, jobcat="2004003009", recency_days=3)
    finally:
        await scraper.close()

    assert captured[0]["isnew"] == "3"


@pytest.mark.asyncio
async def test_search_recency_days_zero_still_sends_isnew():
    """0 是合法值（僅今日）但為 falsy；用真值判斷會讓它靜默失去時間窗。"""
    captured: list[dict] = []
    scraper = _make_scraper(_one_job_then_empty(captured))
    try:
        await scraper.search(areas=["台北市"], max_pages=1, jobcat="2004003009", recency_days=0)
    finally:
        await scraper.close()

    assert captured[0]["isnew"] == "0"


@pytest.mark.asyncio
async def test_scrape_all_applies_recency_to_jobcat_queries_only(monkeypatch):
    """時間窗只套在 jobcat 查詢；keyword 查詢必須維持不受限的廣度掃描。"""
    calls: list[dict] = []

    class _RecordingScraper:
        def __init__(self, *args, **kwargs):
            pass

        async def search(self, keyword="", areas=None, max_pages=5,
                         from_date=None, jobcat=None, recency_days=None):
            calls.append({"keyword": keyword, "jobcat": jobcat, "recency_days": recency_days})
            return []

        async def detail(self, url):
            return None

        async def close(self):
            return None

    monkeypatch.setattr(scraper_module, "OneZeroFourScraper", _RecordingScraper)
    await scraper_module.scrape_all(
        keywords=["產品經理"], areas=["台北市"],
        jobcats=["2004003009"], jobcat_recency_days=3,
    )

    keyword_calls = [c for c in calls if c["keyword"]]
    jobcat_calls = [c for c in calls if c["jobcat"]]
    assert keyword_calls
    assert all(c["recency_days"] is None for c in keyword_calls)

    # 每個 jobcat 掃兩趟：一趟不設時間窗（保留原本「久未更新但仍在架」的覆蓋），
    # 一趟套時間窗（把近期更新的缺從相關性後段拉進前幾頁）。少任何一趟都是覆蓋損失。
    windows = [c["recency_days"] for c in jobcat_calls if c["jobcat"] == "2004003009"]
    assert len(windows) == 2
    assert None in windows and 3 in windows


@pytest.mark.asyncio
async def test_scrape_all_jobcat_single_sweep_when_no_recency_configured(monkeypatch):
    """沒設定時間窗時不該平白多掃一趟。"""
    calls: list[dict] = []

    class _RecordingScraper:
        def __init__(self, *args, **kwargs):
            pass

        async def search(self, keyword="", areas=None, max_pages=5,
                         from_date=None, jobcat=None, recency_days=None):
            calls.append({"jobcat": jobcat, "recency_days": recency_days})
            return []

        async def detail(self, url):
            return None

        async def close(self):
            return None

    monkeypatch.setattr(scraper_module, "OneZeroFourScraper", _RecordingScraper)
    await scraper_module.scrape_all(
        keywords=[], areas=["台北市"], jobcats=["2004003009"], jobcat_recency_days=None,
    )

    assert [c["recency_days"] for c in calls if c["jobcat"]] == [None]


@pytest.mark.asyncio
async def test_search_omits_isnew_when_recency_days_none():
    captured: list[dict] = []
    scraper = _make_scraper(_one_job_then_empty(captured))
    try:
        await scraper.search("產品經理", areas=["台北市"], max_pages=1)
    finally:
        await scraper.close()

    assert "isnew" not in captured[0]


@pytest.mark.asyncio
async def test_search_rejects_recency_days_104_does_not_accept():
    """104 只吃 isnew ∈ {0,3,7,14,30}；其餘值回 400，會被 except 吞掉導致整個
    jobcat 掃描靜默變成 0 筆。這裡要求提前 fail-loud。"""
    scraper = _make_scraper(_one_job_then_empty([]))
    try:
        with pytest.raises(ValueError):
            await scraper.search(areas=["台北市"], max_pages=1, jobcat="2004003009", recency_days=5)
    finally:
        await scraper.close()


def _stale_first_page_then_fresh(captured: list[dict]):
    """page 1 全是舊職缺、page 2 才有新職缺的 handler。

    104 的排序不是更新日降序（實測 order 1~16 都不是），所以「整頁都舊就停止翻頁」
    會把後面頁數裡的新職缺整批丟掉。
    """

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        captured.append(params)
        page = params.get("page")
        if page == "1":
            data = [{"link": {"job": "//www.104.com.tw/job/old01"},
                     "custName": "舊公司", "jobName": "PM", "appearDate": "20260101"}]
        elif page == "2":
            data = [{"link": {"job": "//www.104.com.tw/job/new02"},
                     "custName": "新公司", "jobName": "PM", "appearDate": "20260815"}]
        else:
            data = []
        return httpx.Response(200, json={"data": data})

    return handler


@pytest.mark.asyncio
async def test_search_does_not_early_stop_on_a_stale_page():
    captured: list[dict] = []
    scraper = _make_scraper(_stale_first_page_then_fresh(captured))
    try:
        results = await scraper.search(
            "產品經理", areas=["台北市"], max_pages=3, from_date="2026-08-01"
        )
    finally:
        await scraper.close()

    urls = [r["url"] for r in results]
    assert "https://www.104.com.tw/job/new02" in urls, "第 2 頁的新職缺被 early-stop 丟掉了"
    assert "https://www.104.com.tw/job/old01" not in urls  # from_date 過濾仍生效


def _alive_scraper(status: int, body: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body if body is not None else {})
    return _make_scraper(handler)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,body,expected",
    [
        (200, {"data": {"header": {"jobName": "PM"}}}, True),   # 在架
        (200, {"data": {}}, False),                             # 空 data = 下架
        (404, {"error": {"code": 11201}}, False),               # 職務不存在 = 真下架
        (429, {}, None),                                        # 被限流 = 無法確認
        (403, {}, None),                                        # 封鎖 = 無法確認
        (500, {}, None),                                        # 伺服器錯誤 = 無法確認
    ],
)
async def test_is_listing_alive(status, body, expected):
    scraper = _alive_scraper(status, body)
    try:
        result = await scraper.is_listing_alive("https://www.104.com.tw/job/abc12")
    finally:
        await scraper.close()
    assert result is expected
