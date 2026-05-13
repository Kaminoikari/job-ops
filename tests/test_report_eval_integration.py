"""report.py 與 tracker.Evaluation 整合測試：score column + 摘要行。"""
from __future__ import annotations

from job_ops.history import ScanResult
from job_ops.report import build_markdown
from job_ops.tracker import Evaluation


def _job(url, **kw):
    base = {
        "url": url, "company": "Acme", "title": "PM",
        "salary_min": 100000, "salary_raw": "月薪 10萬",
        "industry": "科技業", "location": "台北市", "notes": {},
        "jd": "JD body", "104_update_date": "2026-05-13",
    }
    base.update(kw)
    return base


def _ev(url, score: float = 4.2) -> Evaluation:
    return Evaluation(
        report_num="001", url=url, evaluated_at="2026-05-13",
        company="Acme", title="PM", archetype="AI PM",
        global_score=score,
        d1_skills=5, d2_salary=4, d3_archetype_fit=5, d4_activeness=4,
        d5_stability=4, d6_culture=4, d7_growth=4, d8_red_flags=4,
        legitimacy="High Confidence",
        report_path="reports/eval/001-acme-2026-05-13.md",
    )


def test_build_markdown_no_evaluations_omits_summary():
    scan = ScanResult(today="2026-05-13", new_items=[_job("u1")],
                      refreshed=[], salary_changed=[], still_listed=[], expired=[])
    md = build_markdown(scan, "2026-05-13")  # evaluations=None
    assert "已評估" not in md
    # 表格仍然有評分欄但全部為 —
    assert "| 評分 |" in md


def test_build_markdown_with_evaluations_shows_summary_and_score():
    scan = ScanResult(today="2026-05-13", new_items=[_job("u1")],
                      refreshed=[], salary_changed=[], still_listed=[], expired=[])
    evs = {"u1": _ev("u1", 4.2)}
    md = build_markdown(scan, "2026-05-13", evaluations=evs)
    assert "🎯 已評估：**1 / 1**" in md
    assert "🟢 4.2" in md


def test_build_markdown_score_emoji_threshold():
    scan = ScanResult(
        today="2026-05-13",
        new_items=[_job("u1"), _job("u2"), _job("u3"), _job("u4")],
        refreshed=[], salary_changed=[], still_listed=[], expired=[],
    )
    evs = {
        "u1": _ev("u1", 4.5),
        "u2": _ev("u2", 3.7),
        "u3": _ev("u3", 3.2),
        "u4": _ev("u4", 2.5),
    }
    md = build_markdown(scan, "2026-05-13", evaluations=evs)
    assert "🟢 4.5" in md
    assert "🟡 3.7" in md
    assert "🟠 3.2" in md
    assert "🔴 2.5" in md


def test_build_markdown_unevaluated_job_shows_dash():
    scan = ScanResult(today="2026-05-13", new_items=[_job("u1"), _job("u2")],
                      refreshed=[], salary_changed=[], still_listed=[], expired=[])
    evs = {"u1": _ev("u1", 4.2)}
    md = build_markdown(scan, "2026-05-13", evaluations=evs)
    # u1 有分；u2 (未評估) 應該顯示 —
    assert "🟢 4.2" in md
    # 計算 — 的 occurrences 應該至少 1（u2 行）
    lines_for_u2 = [l for l in md.split("\n") if "u2" in l]
    assert any("| — |" in l for l in lines_for_u2)


def test_build_markdown_detail_block_shows_eval_link():
    scan = ScanResult(today="2026-05-13", new_items=[_job("u1")],
                      refreshed=[], salary_changed=[], still_listed=[], expired=[])
    evs = {"u1": _ev("u1", 4.2)}
    md = build_markdown(scan, "2026-05-13", evaluations=evs)
    # JD 詳細區塊應該有評估 line
    assert "**評估**" in md
    assert "reports/eval/001-acme-2026-05-13.md" in md
    assert "legitimacy" in md.lower() or "legitimacy" in md
