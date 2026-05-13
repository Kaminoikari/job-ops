"""archetypes.py 的關鍵字 + classify 邏輯測試。"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from job_ops.archetypes import (
    Archetype,
    archetype_score,
    classify,
    load_archetypes,
)


@pytest.fixture
def yaml_archetypes(tmp_path: Path) -> Path:
    p = tmp_path / "archetypes.yml"
    p.write_text(
        textwrap.dedent(
            """
            archetypes:
              - name: "AI PM"
                keywords: ["AI", "LLM", "RAG", "agent"]
                proof_points_priority: ["AI projects"]
                fit: "primary"
              - name: "Senior PM"
                keywords: ["Senior", "資深", "Lead"]
                proof_points_priority: ["cross-functional"]
                fit: "primary"
              - name: "TPM"
                keywords: ["TPM", "platform", "infra"]
                proof_points_priority: ["tech depth"]
                fit: "secondary"
            """
        ).strip(),
        encoding="utf-8",
    )
    return p


def test_load_archetypes_parses_yaml(yaml_archetypes: Path):
    arcs = load_archetypes(yaml_archetypes)
    assert len(arcs) == 3
    assert arcs[0].name == "AI PM"
    assert "LLM" in arcs[0].keywords


def test_classify_picks_primary_with_most_hits(yaml_archetypes: Path):
    arcs = load_archetypes(yaml_archetypes)
    jd = "We need an AI Product Manager familiar with LLM, RAG and agent workflows."
    match = classify(jd, arcs)
    assert match.primary.name == "AI PM"
    # secondary may be None if 2nd 0 hits
    assert match.is_hybrid is False


def test_classify_hybrid_when_two_strong(yaml_archetypes: Path):
    arcs = load_archetypes(yaml_archetypes)
    # AI + Senior 都很強
    jd = "Senior 資深 AI Product Manager — LLM agent. Lead cross-functional team."
    match = classify(jd, arcs)
    # 主應該是 AI PM 或 Senior PM 都行，但 hybrid=True
    assert match.is_hybrid is True
    assert match.secondary is not None
    assert match.primary.name != match.secondary.name


def test_classify_returns_first_when_no_hit(yaml_archetypes: Path):
    arcs = load_archetypes(yaml_archetypes)
    jd = "We bake bread."
    match = classify(jd, arcs)
    # 沒命中時 primary 必須有值（fallback 到第一個），且 hits 都 0
    assert match.primary is not None
    assert all(v == 0 for v in match.hits.values())


def test_archetype_score_primary_strong_hits():
    arc = Archetype(name="AI PM", keywords=["AI", "LLM"], proof_points_priority=[], fit="primary")
    from job_ops.archetypes import MatchResult
    m = MatchResult(primary=arc, secondary=None, is_hybrid=False, hits={"AI PM": 5})
    score = archetype_score(m)
    assert 1 <= score <= 5
    assert score >= 4  # primary + 強命中 → 高分


def test_archetype_score_zero_hits_falls_to_low():
    arc = Archetype(name="AI PM", keywords=["AI"], proof_points_priority=[], fit="adjacent")
    from job_ops.archetypes import MatchResult
    m = MatchResult(primary=arc, secondary=None, is_hybrid=False, hits={"AI PM": 0})
    score = archetype_score(m)
    assert score <= 2
