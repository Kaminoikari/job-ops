"""tracker.py TSV 讀寫 + add/update/stats 測試。"""
from __future__ import annotations

from pathlib import Path

import pytest

from job_ops.tracker import (
    STATUS_APPLIED,
    STATUS_EVALUATED,
    Evaluation,
    add_evaluation,
    find_by_url,
    list_by_score,
    load,
    next_report_num,
    save,
    stats,
    update_status,
)


def _ev(num: str, url: str, score: float = 4.0, **kw) -> Evaluation:
    base = dict(
        report_num=num,
        url=url,
        evaluated_at="2026-05-13",
        company="Acme",
        title="PM",
        archetype="AI PM",
        global_score=score,
        d1_skills=4, d2_salary=4, d3_archetype_fit=5, d4_activeness=4,
        d5_stability=4, d6_culture=4, d7_growth=3, d8_red_flags=4,
        legitimacy="High Confidence",
        status=STATUS_EVALUATED,
        report_path=f"reports/eval/{num}-acme-2026-05-13.md",
    )
    base.update(kw)
    return Evaluation(**base)


def test_save_and_load_roundtrip(tmp_path: Path):
    path = tmp_path / "tracker.tsv"
    evs = [_ev("001", "u1"), _ev("002", "u2", score=3.5)]
    save(evs, path)
    loaded = load(path)
    assert len(loaded) == 2
    assert loaded[0].url == "u1"
    assert loaded[1].global_score == 3.5
    assert loaded[1].legitimacy == "High Confidence"


def test_load_empty_returns_empty(tmp_path: Path):
    assert load(tmp_path / "nonexistent.tsv") == []


def test_next_report_num_increments(tmp_path: Path):
    path = tmp_path / "tracker.tsv"
    save([_ev("001", "u1"), _ev("003", "u3")], path)
    assert next_report_num(path=path) == "004"


def test_next_report_num_starts_at_001_empty(tmp_path: Path):
    assert next_report_num(path=tmp_path / "empty.tsv") == "001"


def test_add_evaluation_appends(tmp_path: Path):
    path = tmp_path / "tracker.tsv"
    add_evaluation(_ev("001", "u1"), path)
    add_evaluation(_ev("", "u2"), path)
    rows = load(path)
    assert len(rows) == 2
    assert rows[1].report_num == "002"  # auto-assigned


def test_add_evaluation_dedupe_by_url(tmp_path: Path):
    path = tmp_path / "tracker.tsv"
    add_evaluation(_ev("001", "u1", score=4.0), path)
    add_evaluation(_ev("999", "u1", score=4.5), path)   # 同 URL → update
    rows = load(path)
    assert len(rows) == 1
    assert rows[0].global_score == 4.5
    assert rows[0].report_num == "001"  # 沿用原號


def test_add_preserves_status_after_applied(tmp_path: Path):
    path = tmp_path / "tracker.tsv"
    add_evaluation(_ev("001", "u1", status=STATUS_APPLIED), path)
    add_evaluation(_ev("001", "u1", status=STATUS_EVALUATED), path)
    rows = load(path)
    # 既有 status 是 Applied → 重新評估不應該降回 Evaluated
    assert rows[0].status == STATUS_APPLIED


def test_update_status_changes_status(tmp_path: Path):
    path = tmp_path / "tracker.tsv"
    add_evaluation(_ev("001", "u1"), path)
    ok = update_status("u1", STATUS_APPLIED, path)
    assert ok is True
    assert load(path)[0].status == STATUS_APPLIED


def test_update_status_invalid_raises(tmp_path: Path):
    path = tmp_path / "tracker.tsv"
    add_evaluation(_ev("001", "u1"), path)
    with pytest.raises(ValueError):
        update_status("u1", "Banana", path)


def test_update_status_missing_returns_false(tmp_path: Path):
    path = tmp_path / "tracker.tsv"
    assert update_status("nope", STATUS_APPLIED, path) is False


def test_list_by_score_filters_and_sorts(tmp_path: Path):
    path = tmp_path / "tracker.tsv"
    save([
        _ev("001", "u1", score=3.0),
        _ev("002", "u2", score=4.5),
        _ev("003", "u3", score=3.8),
    ], path)
    high = list_by_score(min_score=3.5, path=path)
    assert [e.url for e in high] == ["u2", "u3"]   # 降序


def test_find_by_url(tmp_path: Path):
    path = tmp_path / "tracker.tsv"
    add_evaluation(_ev("001", "u1"), path)
    assert find_by_url("u1", path).report_num == "001"
    assert find_by_url("nope", path) is None


def test_stats_empty(tmp_path: Path):
    assert stats(tmp_path / "x.tsv") == {"total": 0}


def test_stats_counts_correctly(tmp_path: Path):
    path = tmp_path / "tracker.tsv"
    save([
        _ev("001", "u1", score=4.2),
        _ev("002", "u2", score=3.7),
        _ev("003", "u3", score=3.2, status=STATUS_APPLIED),
        _ev("004", "u4", score=2.5),
    ], path)
    s = stats(path)
    assert s["total"] == 4
    assert s["green_count"] == 1
    assert s["yellow_count"] == 1
    assert s["orange_count"] == 1
    assert s["red_count"] == 1
    assert s["by_status"][STATUS_EVALUATED] == 3
    assert s["by_status"][STATUS_APPLIED] == 1


def test_save_escapes_tab_and_newline(tmp_path: Path):
    path = tmp_path / "tracker.tsv"
    nasty = _ev("001", "u1", title="Has\ttab\nand\nnewlines")
    save([nasty], path)
    loaded = load(path)
    # 不應該因為 title 內含 \t/\n 而崩
    assert loaded[0].url == "u1"
    assert "\t" not in loaded[0].title
    assert "\n" not in loaded[0].title
