"""104 interactionRecord／hrBehaviorPR 解析測試。

2026-09-05 起 104 detail API 把數值欄位全部歸零（hrBehaviorPR、
lastCustReplyTimestamp、lastProcessedResumeAtTime、nowTimestamp 都是 0），
改回傳預先組好的描述文字（lastCustReplyDesc／lastProcessedResumeDesc）。
下面的 payload 形狀取自 2026-09-17 對 250 筆真實職缺的抽樣。
"""
from __future__ import annotations

import logging

import httpx
import pytest

from job_ops.evaluator import score_activeness
from job_ops.report import _job_row
from job_ops.scraper_104 import OneZeroFourScraper, _extract_activeness


def _masked_detail(
    *,
    reply_desc: object = "",
    resume_desc: object = "",
    has_hr_behavior: bool = False,
) -> dict:
    """2026-09 之後 104 回傳的形狀：數值全歸零，只剩描述文字。"""
    return {
        "header": {"hrBehaviorPR": 0, "hasHrBehavior": has_hr_behavior},
        "interactionRecord": {
            "lastProcessedResumeAtTime": 0,
            "lastCustReplyTimestamp": 0,
            "nowTimestamp": 0,
            "lastProcessedResumeDesc": resume_desc,
            "lastCustReplyDesc": reply_desc,
        },
    }


NOW = 1_780_000_000


def _legacy_detail(*, pr: float, resume_hours_ago: float | None = None) -> dict:
    """2026-09 之前 104 回傳的形狀：數值欄位有值。"""
    ir: dict = {"nowTimestamp": NOW, "lastCustReplyTimestamp": 0, "lastProcessedResumeAtTime": 0}
    if resume_hours_ago is not None:
        ir["lastProcessedResumeAtTime"] = int(NOW - resume_hours_ago * 3600)
    return {"header": {"hrBehaviorPR": pr}, "interactionRecord": ir}


# ---------- 描述文字（2026-09 之後的形狀） ----------


def test_reply_desc_is_shown_verbatim():
    notes = _extract_activeness(_masked_detail(reply_desc="2 分鐘前聯絡過求職者"))
    assert notes["reply_info"] == "2 分鐘前聯絡過求職者"


def test_resume_desc_is_shown_verbatim():
    notes = _extract_activeness(_masked_detail(resume_desc="15 小時前處理過履歷"))
    assert notes["resume_info"] == "15 小時前處理過履歷"


def test_empty_descs_leave_no_info():
    notes = _extract_activeness(_masked_detail())
    assert "reply_info" not in notes
    assert "resume_info" not in notes
    assert "resume_recency" not in notes


@pytest.mark.parametrize(
    ("desc", "expected"),
    [
        ("46 分鐘前處理過履歷", "within_day"),
        ("23 小時前處理過履歷", "within_day"),
        ("1 天內處理過履歷", "within_week"),
        ("6 天內處理過履歷", "within_week"),
        ("7 天內處理過履歷", "over_week"),
        ("30 天內處理過履歷", "over_week"),
    ],
)
def test_resume_desc_recency_bucket(desc, expected):
    notes = _extract_activeness(_masked_detail(resume_desc=desc))
    assert notes["resume_recency"] == expected


@pytest.mark.parametrize(
    "desc",
    [
        "2 週內處理過履歷",         # 沒見過的單位
        "超過 30 天內處理過履歷",   # 前面多了字
        "3 小時前處理過履歷（HR）", # 後面多了字
        "3 小時前聯絡過求職者",     # 動詞屬於另一個欄位
        "3小時前處理過履歷",        # 格式漂移：少了空格
    ],
)
def test_unparseable_resume_desc_kept_raw_without_recency(desc):
    notes = _extract_activeness(_masked_detail(resume_desc=desc))
    assert notes["resume_info"] == desc
    assert "resume_recency" not in notes


def test_non_string_desc_ignored():
    notes = _extract_activeness(_masked_detail(reply_desc=123, resume_desc={"x": 1}))
    assert "reply_info" not in notes
    assert "resume_info" not in notes


def test_unparseable_resume_desc_logs_field_name(caplog):
    with caplog.at_level(logging.WARNING, logger="job_ops.scraper_104"):
        _extract_activeness(_masked_detail(resume_desc="2 週內處理過履歷"))
    assert "lastProcessedResumeDesc" in caplog.text


# ---------- hrBehaviorPR 被遮蔽 ----------


def test_masked_pr_is_not_reported_as_score():
    notes = _extract_activeness(_masked_detail(has_hr_behavior=False))
    assert "activeness_score" not in notes
    assert "activeness" not in notes


def test_has_hr_behavior_shows_104_badge():
    notes = _extract_activeness(_masked_detail(has_hr_behavior=True))
    assert notes["activeness"] == "🟢 徵才行為活躍"
    assert "activeness_score" not in notes


# ---------- 舊形狀（數值有值）仍照舊解析 ----------


def test_legacy_pr_is_used_when_not_masked():
    notes = _extract_activeness(_legacy_detail(pr=0.85))
    assert notes["activeness_score"] == 0.85


def test_legacy_zero_pr_is_a_real_score():
    # 2026-09 之前每天也有 1～4 筆真的 0.00；遮蔽判定不能只看 PR 是不是 0
    notes = _extract_activeness(_legacy_detail(pr=0))
    assert notes["activeness_score"] == 0


def test_pr_kept_when_interaction_record_missing():
    notes = _extract_activeness({"header": {"hrBehaviorPR": 0.7}})
    assert notes["activeness_score"] == 0.7


@pytest.mark.parametrize(
    ("hours", "expected"),
    [(23, "within_day"), (24, "within_week"), (167, "within_week"), (168, "over_week")],
)
def test_legacy_resume_timestamp_recency_bucket(hours, expected):
    notes = _extract_activeness(_legacy_detail(pr=0.5, resume_hours_ago=hours))
    assert notes["resume_recency"] == expected


# ---------- 端到端：detail() → notes → 評分與日報 ----------


async def test_detail_masked_payload_flows_to_score_and_report():
    payload = {
        "data": {
            **_masked_detail(
                reply_desc="2 分鐘前聯絡過求職者",
                resume_desc="15 小時前處理過履歷",
                has_hr_behavior=True,
            ),
            "jobDetail": {"jobDescription": "AI PM", "salaryMin": 0},
            "industry": "電腦軟體服務業",
        }
    }
    payload["data"]["header"].update({"custName": "Acme", "jobName": "AI PM", "appearDate": "2026/09/17"})

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    scraper = OneZeroFourScraper(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    async def _no_wait() -> None:
        return None

    scraper._limiter.wait = _no_wait  # type: ignore[method-assign]

    job = await scraper.detail("https://www.104.com.tw/job/8oyk3")
    assert job is not None

    # 中性 3 分 + 24 小時內處理過履歷 +1；遮蔽的 PR=0 不能把基準壓成 1
    assert score_activeness(job["notes"]) == 4

    row = _job_row(job)
    assert "2 分鐘前聯絡過求職者" in row
    assert "15 小時前處理過履歷" in row
    assert "不積極" not in row
