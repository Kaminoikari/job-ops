"""4 個 PM archetypes 載入 + 對 JD 做 keyword match。"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

log = logging.getLogger(__name__)


@dataclass
class Archetype:
    name: str
    keywords: list[str]
    proof_points_priority: list[str]
    fit: str = "primary"   # primary / secondary / adjacent


@dataclass
class MatchResult:
    primary: Archetype
    secondary: Archetype | None = None
    is_hybrid: bool = False
    hits: dict[str, int] = field(default_factory=dict)   # archetype name → 命中數


def load_archetypes(path: str | Path = "config/archetypes.yml") -> list[Archetype]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return [
        Archetype(
            name=a["name"],
            keywords=list(a.get("keywords") or []),
            proof_points_priority=list(a.get("proof_points_priority") or []),
            fit=a.get("fit", "primary"),
        )
        for a in (raw.get("archetypes") or [])
    ]


def _count_hits(text: str, keywords: list[str]) -> int:
    """大小寫不敏感地計算 keywords 在 text 中出現的次數（每 keyword 最多算 1）。"""
    text_lower = text.lower()
    hit = 0
    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower and kw_lower in text_lower:
            hit += 1
    return hit


def classify(jd_text: str, archetypes: list[Archetype] | None = None) -> MatchResult:
    """對 JD 文字判定最相符的 archetype。

    Algorithm:
        1. 對每個 archetype 計算 keyword 命中數
        2. primary = 命中最多的
        3. 若第 2 名命中數 >= primary × 0.6 → hybrid
    """
    archetypes = archetypes or load_archetypes()
    if not archetypes:
        raise ValueError("沒有定義 archetypes，請確認 config/archetypes.yml")

    hits = {a.name: _count_hits(jd_text, a.keywords) for a in archetypes}
    sorted_by_hit = sorted(archetypes, key=lambda a: hits[a.name], reverse=True)
    primary = sorted_by_hit[0]

    secondary = None
    is_hybrid = False
    if len(sorted_by_hit) >= 2:
        second = sorted_by_hit[1]
        if hits[primary.name] > 0 and hits[second.name] >= hits[primary.name] * 0.6:
            secondary = second
            is_hybrid = True

    return MatchResult(primary=primary, secondary=secondary, is_hybrid=is_hybrid, hits=hits)


def archetype_score(match: MatchResult) -> int:
    """根據 archetype fit 與命中強度回 1-5 分（用於第 3 維度「職涯目標契合度」）。"""
    primary_hits = match.hits.get(match.primary.name, 0)
    fit = match.primary.fit

    if primary_hits == 0:
        return 1  # 完全沒匹配到

    if fit == "primary":
        if primary_hits >= 4:
            return 5
        if primary_hits >= 2:
            return 4
        return 3
    elif fit == "secondary":
        if primary_hits >= 4:
            return 4
        if primary_hits >= 2:
            return 3
        return 2
    else:  # adjacent
        if primary_hits >= 4:
            return 3
        return 2
