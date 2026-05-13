"""TSV-based job evaluation tracker.

Schema (tab-separated, header line 1):
    report_num \t url \t evaluated_at \t company \t title \t archetype \t
    global_score \t d1 \t d2 \t d3 \t d4 \t d5 \t d6 \t d7 \t d8 \t
    legitimacy \t status \t report_path

d1..d8 是 8 個維度的分數（1-5 int 或空字串）。
status: Evaluated / Applied / Responded / Interview / Offer / Rejected / Dropped / DO_NOT_APPLY
"""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

log = logging.getLogger(__name__)

TRACKER_PATH = Path("data/tracker.tsv")

HEADER = [
    "report_num",
    "url",
    "evaluated_at",
    "company",
    "title",
    "archetype",
    "global_score",
    "d1_skills",
    "d2_salary",
    "d3_archetype_fit",
    "d4_activeness",
    "d5_stability",
    "d6_culture",
    "d7_growth",
    "d8_red_flags",
    "legitimacy",
    "status",
    "report_path",
]

STATUS_EVALUATED = "Evaluated"
STATUS_APPLIED = "Applied"
STATUS_RESPONDED = "Responded"
STATUS_INTERVIEW = "Interview"
STATUS_OFFER = "Offer"
STATUS_REJECTED = "Rejected"
STATUS_DROPPED = "Dropped"
STATUS_DO_NOT_APPLY = "DO_NOT_APPLY"

ALL_STATUSES = {
    STATUS_EVALUATED, STATUS_APPLIED, STATUS_RESPONDED, STATUS_INTERVIEW,
    STATUS_OFFER, STATUS_REJECTED, STATUS_DROPPED, STATUS_DO_NOT_APPLY,
}


@dataclass
class Evaluation:
    report_num: str          # "001", "002", ...
    url: str
    evaluated_at: str        # ISO date
    company: str
    title: str
    archetype: str
    global_score: float
    d1_skills: int = 0
    d2_salary: int = 0
    d3_archetype_fit: int = 0
    d4_activeness: int = 0
    d5_stability: int = 0
    d6_culture: int = 0
    d7_growth: int = 0
    d8_red_flags: int = 0
    legitimacy: str = ""     # "High Confidence" / "Proceed with Caution" / "Suspicious"
    status: str = STATUS_EVALUATED
    report_path: str = ""

    def to_row(self) -> list[str]:
        return [
            self.report_num, self.url, self.evaluated_at, self.company, self.title,
            self.archetype, f"{self.global_score:.2f}",
            str(self.d1_skills), str(self.d2_salary), str(self.d3_archetype_fit),
            str(self.d4_activeness), str(self.d5_stability), str(self.d6_culture),
            str(self.d7_growth), str(self.d8_red_flags),
            self.legitimacy, self.status, self.report_path,
        ]

    @classmethod
    def from_row(cls, row: list[str]) -> "Evaluation":
        def _int(i: int) -> int:
            try:
                return int(row[i]) if i < len(row) and row[i] else 0
            except ValueError:
                return 0
        def _str(i: int) -> str:
            return row[i] if i < len(row) else ""
        return cls(
            report_num=_str(0), url=_str(1), evaluated_at=_str(2),
            company=_str(3), title=_str(4), archetype=_str(5),
            global_score=float(row[6]) if len(row) > 6 and row[6] else 0.0,
            d1_skills=_int(7), d2_salary=_int(8), d3_archetype_fit=_int(9),
            d4_activeness=_int(10), d5_stability=_int(11), d6_culture=_int(12),
            d7_growth=_int(13), d8_red_flags=_int(14),
            legitimacy=_str(15), status=_str(16) or STATUS_EVALUATED, report_path=_str(17),
        )


def _escape(v: str) -> str:
    return str(v).replace("\t", " ").replace("\n", " ").replace("\r", " ")


def load(path: str | Path = TRACKER_PATH) -> list[Evaluation]:
    p = Path(path)
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").splitlines()
    if not lines:
        return []
    out: list[Evaluation] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        out.append(Evaluation.from_row(line.split("\t")))
    return out


def save(evaluations: list[Evaluation], path: str | Path = TRACKER_PATH) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = ["\t".join(HEADER)]
    for e in evaluations:
        rows.append("\t".join(_escape(x) for x in e.to_row()))
    p.write_text("\n".join(rows) + "\n", encoding="utf-8")


def next_report_num(evaluations: list[Evaluation] | None = None, *, path: str | Path = TRACKER_PATH) -> str:
    """回傳下一個 3 位數的 report number (e.g. '042')。"""
    if evaluations is None:
        evaluations = load(path)
    if not evaluations:
        return "001"
    nums = []
    for e in evaluations:
        try:
            nums.append(int(e.report_num))
        except ValueError:
            pass
    next_n = (max(nums) + 1) if nums else 1
    return f"{next_n:03d}"


def add_evaluation(ev: Evaluation, path: str | Path = TRACKER_PATH) -> None:
    """新增一筆評估到 tracker。若 url 已存在 → 視為 update。"""
    all_ev = load(path)
    existing_idx = next((i for i, e in enumerate(all_ev) if e.url == ev.url), None)
    if existing_idx is not None:
        # 保留原 report_num 與 status
        existing = all_ev[existing_idx]
        ev.report_num = existing.report_num or ev.report_num
        if existing.status not in (STATUS_EVALUATED, ""):
            ev.status = existing.status
        all_ev[existing_idx] = ev
    else:
        if not ev.report_num:
            ev.report_num = next_report_num(all_ev)
        all_ev.append(ev)
    save(all_ev, path)


def update_status(url: str, new_status: str, path: str | Path = TRACKER_PATH) -> bool:
    """更新某筆評估的 status。回傳是否找到並更新。"""
    if new_status not in ALL_STATUSES:
        raise ValueError(f"Unknown status: {new_status}. Must be one of {ALL_STATUSES}")
    all_ev = load(path)
    for e in all_ev:
        if e.url == url:
            e.status = new_status
            save(all_ev, path)
            return True
    return False


def list_by_score(min_score: float = 0.0, status: str | None = None, path: str | Path = TRACKER_PATH) -> list[Evaluation]:
    """依分數降序列出，可選擇過濾 status。"""
    out = [e for e in load(path) if e.global_score >= min_score]
    if status:
        out = [e for e in out if e.status == status]
    out.sort(key=lambda e: e.global_score, reverse=True)
    return out


def stats(path: str | Path = TRACKER_PATH) -> dict:
    """tracker 統計總覽。"""
    all_ev = load(path)
    if not all_ev:
        return {"total": 0}
    status_counts = Counter(e.status for e in all_ev)
    scores = [e.global_score for e in all_ev if e.global_score > 0]
    return {
        "total": len(all_ev),
        "by_status": dict(status_counts),
        "avg_score": sum(scores) / len(scores) if scores else 0.0,
        "max_score": max(scores) if scores else 0.0,
        "green_count": sum(1 for s in scores if s >= 4.0),
        "yellow_count": sum(1 for s in scores if 3.5 <= s < 4.0),
        "orange_count": sum(1 for s in scores if 3.0 <= s < 3.5),
        "red_count": sum(1 for s in scores if s < 3.0),
    }


def find_by_url(url: str, path: str | Path = TRACKER_PATH) -> Evaluation | None:
    for e in load(path):
        if e.url == url:
            return e
    return None
