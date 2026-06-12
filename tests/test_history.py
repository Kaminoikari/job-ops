"""history.py 的 lifecycle 邏輯測試。"""
from __future__ import annotations

from pathlib import Path

from job_ops.history import (
    Record,
    STATUS_EXPIRED,
    STATUS_LISTED_NOT_SCANNED,
    STATUS_NEW,
    STATUS_REFRESHED,
    classify_missing,
    compare,
    load_history,
    merge_into_history,
    save_history,
)


def _record(url="u1", status=STATUS_NEW, last_seen="2026-05-11"):
    return Record(
        url=url, first_seen="2026-05-10", last_seen=last_seen,
        last_104_update="2026-05-11",
        company="Acme", title="PM", salary_raw="", salary_min="80000",
        location="", address="", status=status, salary_history="", notes="",
    )


def _job(url, salary_min=80000, update_date="2026-05-12"):
    return {
        "url": url,
        "company": "Acme",
        "title": "Product Manager",
        "salary_raw": "月薪 80,000元",
        "salary_min": salary_min,
        "location": "台北市",
        "address": "台北市內湖區",
        "104_update_date": update_date,
        "notes": {},
    }


def test_compare_new_item():
    today = [_job("u1")]
    scan = compare(today, history={}, today="2026-05-12")
    assert len(scan.new_items) == 1
    assert scan.new_items[0]["url"] == "u1"
    assert not scan.refreshed and not scan.salary_changed and not scan.expired


def test_compare_refreshed_when_104_update_changes():
    prev = Record(
        url="u1", first_seen="2026-05-10", last_seen="2026-05-11",
        last_104_update="2026-05-10",
        company="Acme", title="PM", salary_raw="", salary_min="80000",
        location="台北市", address="", status="New", salary_history="", notes="",
    )
    today = [_job("u1", update_date="2026-05-12")]
    scan = compare(today, history={"u1": prev}, today="2026-05-12")
    assert len(scan.refreshed) == 1
    assert not scan.new_items


def test_compare_salary_changed_takes_precedence():
    prev = Record(
        url="u1", first_seen="2026-05-10", last_seen="2026-05-11",
        last_104_update="2026-05-10",
        company="Acme", title="PM", salary_raw="", salary_min="70000",
        location="", address="", status="New", salary_history="", notes="",
    )
    today = [_job("u1", salary_min=90000, update_date="2026-05-12")]
    scan = compare(today, history={"u1": prev}, today="2026-05-12")
    assert len(scan.salary_changed) == 1
    assert scan.salary_changed[0]["prev_salary_min"] == 70000
    assert scan.salary_changed[0]["salary_min"] == 90000


def test_compare_still_listed():
    prev = Record(
        url="u1", first_seen="2026-05-10", last_seen="2026-05-11",
        last_104_update="2026-05-11",
        company="Acme", title="PM", salary_raw="", salary_min="80000",
        location="", address="", status="New", salary_history="", notes="",
    )
    today = [_job("u1", update_date="2026-05-11")]  # 同 update_date
    scan = compare(today, history={"u1": prev}, today="2026-05-12")
    assert len(scan.still_listed) == 1
    assert not scan.new_items and not scan.refreshed


def test_compare_missing_collects_newly_dropped():
    # 今天沒看到、原本還在架 → 進 missing 待驗證（不直接判 expired）
    prev = _record("u1", status=STATUS_NEW)
    scan = compare(today_jobs=[], history={"u1": prev}, today="2026-05-12")
    assert [r.url for r in scan.missing] == ["u1"]
    assert scan.expired == []  # 未驗證前不標真下架


def test_compare_skips_already_terminal_statuses():
    # 已是 Expired / ListedNotScanned 的不再重複驗證
    history = {
        "u1": _record("u1", status=STATUS_EXPIRED),
        "u2": _record("u2", status=STATUS_LISTED_NOT_SCANNED),
        "u3": _record("u3", status=STATUS_REFRESHED),
    }
    scan = compare(today_jobs=[], history=history, today="2026-05-12")
    assert [r.url for r in scan.missing] == ["u3"]


def test_classify_missing_splits_by_verifier():
    missing = [_record("dead"), _record("alive"), _record("unknown")]

    def verifier(url):
        return {"dead": False, "alive": True, "unknown": None}[url]

    expired, listed = classify_missing(missing, verifier)
    assert [r.url for r in expired] == ["dead"]
    # True（仍在架）與 None（驗證失敗）都不誤殺，歸為「在架未掃到」
    assert {r.url for r in listed} == {"alive", "unknown"}


def test_compare_negotiable_salary_handled():
    today = [_job("u1", salary_min=None)]
    scan = compare(today, history={}, today="2026-05-12")
    assert scan.new_items[0]["salary_min"] is None


def test_merge_into_history_new_item():
    today = [_job("u1")]
    scan = compare(today, history={}, today="2026-05-12")
    out = merge_into_history(today, history={}, scan=scan, today="2026-05-12")
    rec = out["u1"]
    assert rec.status == STATUS_NEW
    assert rec.first_seen == "2026-05-12"
    assert rec.salary_min == "80000"
    assert "2026-05-12:80000" in rec.salary_history


def test_merge_into_history_refreshed():
    prev = Record(
        url="u1", first_seen="2026-05-10", last_seen="2026-05-11",
        last_104_update="2026-05-10",
        company="Acme", title="PM", salary_raw="", salary_min="80000",
        location="", address="", status="New", salary_history="2026-05-10:80000", notes="",
    )
    today = [_job("u1", update_date="2026-05-12")]
    scan = compare(today, history={"u1": prev}, today="2026-05-12")
    out = merge_into_history(today, {"u1": prev}, scan, today="2026-05-12")
    rec = out["u1"]
    assert rec.status == STATUS_REFRESHED
    assert rec.first_seen == "2026-05-10"
    assert rec.last_seen == "2026-05-12"
    # salary 沒變，不應該 append salary_history
    assert rec.salary_history == "2026-05-10:80000"


def test_merge_into_history_salary_changed_appends():
    prev = Record(
        url="u1", first_seen="2026-05-10", last_seen="2026-05-11",
        last_104_update="2026-05-10",
        company="Acme", title="PM", salary_raw="", salary_min="70000",
        location="", address="", status="New", salary_history="2026-05-10:70000", notes="",
    )
    today = [_job("u1", salary_min=90000, update_date="2026-05-12")]
    scan = compare(today, {"u1": prev}, today="2026-05-12")
    out = merge_into_history(today, {"u1": prev}, scan, today="2026-05-12")
    assert "2026-05-10:70000;2026-05-12:90000" == out["u1"].salary_history


def test_merge_expired_marks_status():
    prev = _record("u1", status=STATUS_NEW)
    scan = compare(today_jobs=[], history={"u1": prev}, today="2026-05-12")
    scan.expired = list(scan.missing)  # 模擬驗證後判定真下架
    scan.missing = []
    out = merge_into_history([], {"u1": prev}, scan, today="2026-05-12")
    assert out["u1"].status == STATUS_EXPIRED


def test_merge_listed_not_scanned_marks_status_and_confirms_alive():
    prev = _record("u1", status=STATUS_REFRESHED, last_seen="2026-05-11")
    scan = compare(today_jobs=[], history={"u1": prev}, today="2026-05-12")
    scan.listed_not_scanned = list(scan.missing)  # 驗證後仍在架
    scan.missing = []
    out = merge_into_history([], {"u1": prev}, scan, today="2026-05-12")
    assert out["u1"].status == STATUS_LISTED_NOT_SCANNED
    # 已透過 detail 確認今天仍在架 → last_seen 更新為今天
    assert out["u1"].last_seen == "2026-05-12"


def test_save_and_load_roundtrip(tmp_path: Path):
    today = [_job("u1"), _job("u2", salary_min=None)]
    scan = compare(today, history={}, today="2026-05-12")
    out = merge_into_history(today, {}, scan, today="2026-05-12")
    tsv = tmp_path / "history.tsv"
    save_history(tsv, out)

    loaded = load_history(tsv)
    assert set(loaded.keys()) == {"u1", "u2"}
    assert loaded["u1"].salary_min == "80000"
    assert loaded["u2"].salary_min == ""  # 面議
