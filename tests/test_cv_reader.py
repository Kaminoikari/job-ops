"""cv_reader.py 解析測試。"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from job_ops.cv_reader import read_cv, summarize


SAMPLE_CV = textwrap.dedent(
    """
    # Charles

    ## Headline
    Senior AI Product Manager — 8 yrs FinTech & B2B SaaS

    ## Professional Summary
    Drive 0→1 products with hard data, fast iteration.

    ## Hard Skills
    - 工具：Figma、Jira、Linear
    - 語言：Python (pandas, ETL)、SQL
    - AI/ML：LLM、RAG、agent

    ## Domains
    - FinTech
    - B2B SaaS
    - AI/LLM

    ## Years of Experience
    8 年

    ## Current Role
    Senior PM @ Foo Corp

    ## Work Experience
    ### Foo Corp (2024-now)
    - shipped PR
    - led migration

    ### Bar Inc (2020-2024)
    - led 5 PMs

    ## Proof Points
    - Shipped X to 1M users
    - 0→1 launch of Y
    """
).strip()


@pytest.fixture
def cv_file(tmp_path: Path) -> Path:
    p = tmp_path / "cv.md"
    p.write_text(SAMPLE_CV, encoding="utf-8")
    return p


def test_read_cv_basic_fields(cv_file: Path):
    cv = read_cv(cv_file)
    assert "Senior AI Product Manager" in cv.headline
    assert cv.years_of_experience == 8
    assert "Senior PM" in cv.current_role


def test_read_cv_skills_flattened(cv_file: Path):
    cv = read_cv(cv_file)
    # 攤平的結果應該包含這些 keyword
    assert "Figma" in cv.hard_skills
    assert "Python" in cv.hard_skills
    assert "LLM" in cv.hard_skills


def test_read_cv_domains(cv_file: Path):
    cv = read_cv(cv_file)
    assert "FinTech" in cv.domains
    assert "AI/LLM" in cv.domains


def test_read_cv_work_experience_split(cv_file: Path):
    cv = read_cv(cv_file)
    assert len(cv.work_experience) == 2
    assert any("Foo Corp" in w for w in cv.work_experience)


def test_read_cv_proof_points(cv_file: Path):
    cv = read_cv(cv_file)
    assert any("1M users" in p for p in cv.proof_points)


def test_read_cv_template_detection(tmp_path: Path):
    template = textwrap.dedent(
        """
        ## Headline
        {your-headline}

        ## Hard Skills
        - 工具：{tool-1}、{tool-2}
        - 語言：{lang-1}、{lang-2}
        - AI/ML：{ai-1}
        """
    ).strip()
    p = tmp_path / "cv.md"
    p.write_text(template, encoding="utf-8")
    cv = read_cv(p)
    assert cv.is_template is True


def test_read_cv_filled_not_template(cv_file: Path):
    cv = read_cv(cv_file)
    assert cv.is_template is False


def test_read_cv_missing_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        read_cv(tmp_path / "missing.md")


def test_summarize_includes_key_data(cv_file: Path):
    cv = read_cv(cv_file)
    s = summarize(cv)
    assert "Senior AI Product Manager" in s
    assert "Years: 8" in s
