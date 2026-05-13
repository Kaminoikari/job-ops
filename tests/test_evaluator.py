"""evaluator.py 的機械評分 + global_score + report 組裝測試。"""
from __future__ import annotations

import pytest

from job_ops.evaluator import (
    EvalInput,
    assemble_report,
    company_slug_for_report,
    global_score,
    recommendation,
    report_path,
    score_activeness,
    score_emoji,
    score_salary,
    to_evaluation,
)


# ---------- score_salary ----------


def test_score_salary_negotiable_neutral():
    assert score_salary(None, 80000, 120000) == 3


def test_score_salary_above_target_plus_20pct_perfect():
    assert score_salary(150000, 80000, 120000) == 5  # 150k >= 120k*1.2=144k


def test_score_salary_at_target_high():
    assert score_salary(125000, 80000, 120000) == 4


def test_score_salary_at_min_passing():
    assert score_salary(80000, 80000, 120000) == 3


def test_score_salary_slightly_below_min():
    # 80% of profile_min → 落在 0.85*min 以上 = 2
    assert score_salary(70000, 80000, 120000) == 2


def test_score_salary_way_below_min():
    assert score_salary(40000, 80000, 120000) == 1


# ---------- score_activeness ----------


def test_score_activeness_high_signal():
    notes = {"activeness_score": 0.85, "resume_info": "—"}
    assert score_activeness(notes) == 5


def test_score_activeness_with_recent_resume_bonus():
    # 0.65 → 4，加上「小時前」應拉到 5（capped）
    notes = {"activeness_score": 0.65, "resume_info": "3 小時前聯絡應徵者"}
    assert score_activeness(notes) == 5


def test_score_activeness_low_signal():
    notes = {"activeness_score": 0.2, "resume_info": ""}
    assert score_activeness(notes) == 1


def test_score_activeness_neutral_when_no_data():
    assert score_activeness({}) == 3


# ---------- global_score / emoji / recommendation ----------


def test_global_score_weighted_average():
    scores = dict(
        d1_skills=5, d2_salary=4, d3_archetype_fit=5, d4_activeness=4,
        d5_stability=4, d6_culture=5, d7_growth=4, d8_red_flags=4,
    )
    # 25%*5 + 15%*4 + 10%*5 + 15%*4 + 15%*4 + 10%*5 + 5%*4 + 5%*4
    # = 1.25 + 0.6 + 0.5 + 0.6 + 0.6 + 0.5 + 0.2 + 0.2 = 4.45
    assert global_score(scores) == pytest.approx(4.45, abs=0.01)


def test_global_score_weights_sum_to_one():
    from job_ops.evaluator import WEIGHTS
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_score_emoji_thresholds():
    assert score_emoji(4.5) == "🟢"
    assert score_emoji(4.0) == "🟢"
    assert score_emoji(3.7) == "🟡"
    assert score_emoji(3.2) == "🟠"
    assert score_emoji(2.5) == "🔴"


def test_recommendation_levels():
    assert "強烈" in recommendation(4.5)
    assert recommendation(3.7) == "值得投"
    assert recommendation(3.0) == "普通，看其他訊號決定"
    assert recommendation(2.0) == "不建議投"


# ---------- company_slug_for_report ----------


def test_company_slug_for_report_strips_suffix():
    a = company_slug_for_report("Acme 股份有限公司")
    b = company_slug_for_report("Acme")
    assert a == b


def test_company_slug_for_report_replaces_punctuation():
    assert "/" not in company_slug_for_report("Foo / Bar, Inc.")
    assert "(" not in company_slug_for_report("Foo (Asia)")


def test_company_slug_for_report_max_length():
    long_name = "Foo" * 100
    assert len(company_slug_for_report(long_name)) <= 50


def test_company_slug_for_report_empty():
    assert company_slug_for_report("") == "unknown"


def test_report_path_format(tmp_path):
    p = report_path("Acme Inc.", "2026-05-13", "042", base_dir=tmp_path)
    assert p.name.startswith("042-")
    assert p.name.endswith("-2026-05-13.md")


# ---------- assemble_report ----------


def _full_eval() -> EvalInput:
    return EvalInput(
        url="https://www.104.com.tw/job/abc",
        company="Acme Inc.",
        title="Senior AI PM",
        archetype="AI Product Manager",
        today="2026-05-13",
        block_a_summary="## A. 角色摘要\n- AI PM",
        block_b_cv_match="## B. CV 匹配\n- skills match",
        block_c_level="## C. 等級策略\n- Senior",
        block_d_comp="## D. 薪酬研究\n- 120k median",
        block_e_personalization="## E. 個人化計畫\n- todo",
        block_f_interview="## F. 面試準備\n- STAR",
        block_g_legitimacy="## G. 合法性\n- legit",
        d1_skills=5, d2_salary=4, d3_archetype_fit=5, d4_activeness=4,
        d5_stability=4, d6_culture=4, d7_growth=4, d8_red_flags=4,
        legitimacy="High Confidence",
    )


def test_assemble_report_contains_all_blocks():
    md = assemble_report(_full_eval())
    for needle in [
        "Acme Inc.", "Senior AI PM", "AI Product Manager",
        "A. 角色摘要", "B. CV 匹配", "C. 等級策略",
        "D. 薪酬研究", "E. 個人化計畫", "F. 面試準備", "G. 合法性",
        "8 維評分總覽",
    ]:
        assert needle in md, f"missing: {needle}"


def test_assemble_report_global_score_in_header():
    md = assemble_report(_full_eval())
    # global score 應該在 header
    assert "Global Score:" in md
    assert "🟢" in md  # 4.4+ → green


def test_to_evaluation_carries_scores():
    ev = _full_eval()
    ev.report_path = "reports/eval/001-acme-2026-05-13.md"
    out = to_evaluation(ev)
    assert out.url == ev.url
    assert out.d1_skills == 5
    assert out.legitimacy == "High Confidence"
    assert out.global_score > 0


# ---------- prepare_context (minimal smoke) ----------


def test_prepare_context_smoke(tmp_path, monkeypatch):
    import textwrap

    cv = tmp_path / "cv.md"
    cv.write_text("## Headline\nSenior PM", encoding="utf-8")

    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "archetypes.yml").write_text(
        textwrap.dedent(
            """
            archetypes:
              - name: "AI PM"
                keywords: ["AI", "LLM"]
                proof_points_priority: []
                fit: "primary"
            """
        ).strip(),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    from job_ops.evaluator import prepare_context

    job = {
        "title": "AI Product Manager",
        "jd": "We need an AI/LLM PM",
        "company": "Acme",
        "salary_min": 100000,
        "notes": {"activeness_score": 0.85, "resume_info": "1 小時前聯絡應徵者"},
    }
    ctx = prepare_context(
        url="https://www.104.com.tw/job/xxx",
        job=job,
        cv_path="cv.md",
        profile={"target_compensation": {"monthly_min": 80000, "monthly_target": 120000}},
        forum_report=None,
    )
    assert ctx.salary_score in {3, 4}   # 100k vs target=120k → 3
    assert ctx.activeness_score == 5
    assert ctx.archetype_match.primary.name == "AI PM"
    assert ctx.archetype_score >= 3
