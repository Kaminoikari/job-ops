"""TSV-based job history with lifecycle tracking.

Schema (tab-separated, header on line 1):
    url, first_seen, last_seen, last_104_update,
    company, title, salary_raw, salary_min,
    location, address, status, salary_history, notes
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)


HEADER = [
    "url",
    "first_seen",
    "last_seen",
    "last_104_update",
    "company",
    "title",
    "salary_raw",
    "salary_min",
    "location",
    "address",
    "status",
    "salary_history",
    "notes",
]


STATUS_NEW = "New"
STATUS_REFRESHED = "Refreshed"
STATUS_EXPIRED = "Expired"


@dataclass
class Record:
    url: str
    first_seen: str
    last_seen: str
    last_104_update: str
    company: str
    title: str
    salary_raw: str
    salary_min: str  # str（空字串表示 None）
    location: str
    address: str
    status: str
    salary_history: str
    notes: str

    def to_row(self) -> list[str]:
        return [getattr(self, h) for h in HEADER]

    @classmethod
    def from_row(cls, row: list[str]) -> "Record":
        kwargs = {h: (row[i] if i < len(row) else "") for i, h in enumerate(HEADER)}
        return cls(**kwargs)

    @property
    def salary_min_int(self) -> int | None:
        if not self.salary_min:
            return None
        try:
            return int(self.salary_min)
        except ValueError:
            return None


@dataclass
class ScanResult:
    today: str
    new_items: list[dict] = field(default_factory=list)
    refreshed: list[dict] = field(default_factory=list)            # 104 update_date 變動
    salary_changed: list[dict] = field(default_factory=list)        # 月薪下限變動
    still_listed: list[dict] = field(default_factory=list)          # 仍在架且無變動
    expired: list[Record] = field(default_factory=list)             # 今天沒看到

    def total_today(self) -> int:
        return len(self.new_items) + len(self.refreshed) + len(self.still_listed)


def _escape(v) -> str:
    if v is None:
        return ""
    s = str(v)
    return s.replace("\t", " ").replace("\n", " ").replace("\r", " ")


def load_history(path: str | Path) -> dict[str, Record]:
    p = Path(path)
    if not p.exists():
        return {}
    lines = p.read_text(encoding="utf-8").splitlines()
    if not lines:
        return {}
    # 跳過 header
    out: dict[str, Record] = {}
    for line in lines[1:]:
        if not line.strip():
            continue
        cols = line.split("\t")
        r = Record.from_row(cols)
        if r.url:
            out[r.url] = r
    return out


def save_history(path: str | Path, records: dict[str, Record]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = ["\t".join(HEADER)]
    for r in records.values():
        rows.append("\t".join(_escape(x) for x in r.to_row()))
    p.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _job_salary_str(job: dict) -> str:
    v = job.get("salary_min")
    return "" if v is None else str(int(v))


def _append_salary_history(prev: str, today: str, salary_min: int | None) -> str:
    entry = f"{today}:{salary_min if salary_min is not None else 'negotiable'}"
    if not prev:
        return entry
    return prev + ";" + entry


def compare(today_jobs: list[dict], history: dict[str, Record], today: str | None = None) -> ScanResult:
    """比對今天抓到的 jobs 與 history，計算 lifecycle。"""
    today = today or date.today().isoformat()
    result = ScanResult(today=today)

    today_urls: set[str] = set()
    for job in today_jobs:
        url = job["url"]
        today_urls.add(url)
        salary_min = job.get("salary_min")
        update_date = job.get("104_update_date", "") or ""

        if url not in history or history[url].status == STATUS_EXPIRED:
            result.new_items.append(job)
            continue

        prev = history[url]
        prev_salary = prev.salary_min_int

        is_104_updated = update_date and update_date != prev.last_104_update
        is_salary_changed = salary_min != prev_salary

        if is_salary_changed:
            job_with_prev = dict(job)
            job_with_prev["prev_salary_min"] = prev_salary
            job_with_prev["prev_salary_raw"] = prev.salary_raw
            result.salary_changed.append(job_with_prev)
            if is_104_updated:
                # 同時也是 104 更新（不重複加進 refreshed）
                pass
        elif is_104_updated:
            result.refreshed.append(job)
        else:
            result.still_listed.append(job)

    # expired：在 history 但今天沒看到，且原本不是 Expired
    for url, rec in history.items():
        if url in today_urls:
            continue
        if rec.status == STATUS_EXPIRED:
            continue
        result.expired.append(rec)

    return result


def merge_into_history(
    today_jobs: list[dict],
    history: dict[str, Record],
    scan: ScanResult,
    today: str | None = None,
) -> dict[str, Record]:
    """把 scan 結果寫回 history dict（return 新的 dict，不修改 input）。"""
    today = today or date.today().isoformat()
    out = dict(history)

    today_urls: set[str] = set()
    salary_changed_urls = {j["url"] for j in scan.salary_changed}

    for job in today_jobs:
        url = job["url"]
        today_urls.add(url)
        salary_min = job.get("salary_min")
        salary_str = _job_salary_str(job)
        update_date = job.get("104_update_date", "") or ""
        notes_str = json.dumps(job.get("notes") or {}, ensure_ascii=False)

        existing = out.get(url)
        if existing is None or existing.status == STATUS_EXPIRED:
            # 新（或重新上架）
            out[url] = Record(
                url=url,
                first_seen=today,
                last_seen=today,
                last_104_update=update_date,
                company=job.get("company", ""),
                title=job.get("title", ""),
                salary_raw=job.get("salary_raw", ""),
                salary_min=salary_str,
                location=job.get("location", ""),
                address=job.get("address", ""),
                status=STATUS_NEW,
                salary_history=_append_salary_history("", today, salary_min),
                notes=notes_str,
            )
        else:
            # 既有更新
            new_salary_history = existing.salary_history
            if url in salary_changed_urls:
                new_salary_history = _append_salary_history(existing.salary_history, today, salary_min)
            out[url] = Record(
                url=url,
                first_seen=existing.first_seen,
                last_seen=today,
                last_104_update=update_date or existing.last_104_update,
                company=job.get("company", "") or existing.company,
                title=job.get("title", "") or existing.title,
                salary_raw=job.get("salary_raw", "") or existing.salary_raw,
                salary_min=salary_str,
                location=job.get("location", "") or existing.location,
                address=job.get("address", "") or existing.address,
                status=STATUS_REFRESHED,
                salary_history=new_salary_history,
                notes=notes_str or existing.notes,
            )

    # 處理 expired
    for rec in scan.expired:
        out[rec.url] = Record(
            **{**rec.__dict__, "status": STATUS_EXPIRED},
        )

    return out
