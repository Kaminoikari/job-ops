"""report.py 測試：新版日報（無評分欄、無已下架區塊、refreshed 比照新上架欄位）。"""
from __future__ import annotations

from job_ops.history import Record, ScanResult
from job_ops.report import build_markdown, build_subject


def _job(url, **kw):
    base = {
        "url": url, "company": "Acme", "title": "AI PM",
        "salary_min": 100000, "salary_raw": "月薪 10萬",
        "industry": "科技業", "location": "台北市", "notes": {},
        "jd": "負責規劃並打造 LLM agent 產品", "104_update_date": "2026-05-13",
        "ai_intent": {
            "is_ai_pm": True, "has_ai": True, "score": 8.0,
            "tier": "strong", "matched": ["llm", "ai agent"],
        },
    }
    base.update(kw)
    return base


def _expired_rec(url="ex1"):
    return Record(
        url=url, first_seen="2026-04-01", last_seen="2026-05-01",
        last_104_update="2026-05-01", company="OldCo", title="Old PM",
        salary_raw="面議", salary_min="", location="台北市", address="",
        status="Expired", salary_history="", notes="{}",
    )


# ---------- 評分欄已移除 ----------


def test_no_score_column_anywhere():
    scan = ScanResult(today="2026-05-13", new_items=[_job("u1")],
                      refreshed=[], salary_changed=[], still_listed=[], expired=[])
    md = build_markdown(scan, "2026-05-13")
    assert "評分" not in md
    assert "已評估" not in md
    assert "**評估**" not in md


# ---------- 已下架區塊不顯示 ----------


def test_expired_block_not_shown():
    scan = ScanResult(today="2026-05-13", new_items=[_job("u1")],
                      refreshed=[], salary_changed=[], still_listed=[],
                      expired=[_expired_rec()])
    md = build_markdown(scan, "2026-05-13")
    assert "已下架" not in md
    assert "OldCo" not in md


def test_subject_omits_expired():
    scan = ScanResult(today="2026-05-13", new_items=[_job("u1")],
                      refreshed=[], salary_changed=[], still_listed=[],
                      expired=[_expired_rec(), _expired_rec("ex2")])
    subj = build_subject(scan, "2026-05-13")
    assert "下架" not in subj
    assert "1 筆新上架" in subj


# ---------- refreshed 欄位完全比照今日新上架 ----------


def test_refreshed_uses_same_columns_as_new():
    scan = ScanResult(today="2026-05-13", new_items=[_job("u1")],
                      refreshed=[_job("u2")], salary_changed=[],
                      still_listed=[], expired=[])
    md = build_markdown(scan, "2026-05-13")
    # 兩個區塊都用同一個表頭
    header = "| AI | 月薪下限 | 公司 | 產業 | 職位 | 地區 | 連結 | 徵才積極度 | 回覆求職者 | 聯絡應徵者 |"
    assert md.count(header) == 2


# ---------- AI 欄位存在 ----------


def test_ai_tier_cell_present():
    scan = ScanResult(today="2026-05-13", new_items=[_job("u1")],
                      refreshed=[], salary_changed=[], still_listed=[], expired=[])
    md = build_markdown(scan, "2026-05-13")
    assert "🤖 強" in md


# ---------- 詳細 JD 區塊不再顯示 ----------


def test_detail_block_removed():
    scan = ScanResult(today="2026-05-13", new_items=[_job("u1")],
                      refreshed=[], salary_changed=[], still_listed=[], expired=[])
    md = build_markdown(scan, "2026-05-13")
    assert "詳細資訊" not in md
    assert "Job Description" not in md
    assert "命中訊號" not in md


# ---------- 排序：AI 供應鏈 priority 高者排前 ----------


def test_priority_orders_new_listings():
    low = _job("low", salary_min=200000,
               ai_intent={"is_ai_pm": True, "has_ai": True, "score": 5.0,
                          "priority": 5.0, "tier": "moderate", "matched": ["ai"]})
    high = _job("high", salary_min=80000,
                ai_intent={"is_ai_pm": True, "has_ai": True, "score": 5.0,
                           "priority": 9.0, "tier": "moderate", "matched": ["ai"]})
    scan = ScanResult(today="2026-05-13", new_items=[low, high],
                      refreshed=[], salary_changed=[], still_listed=[], expired=[])
    md = build_markdown(scan, "2026-05-13")
    # priority 高（9.0）的 high 應排在 priority 低（5.0）的 low 之前，即使薪資較低
    assert md.index("[104](high)") < md.index("[104](low)")
