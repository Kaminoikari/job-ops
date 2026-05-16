"""ai_intent 加權啟發式分類器測試。"""
import json

from job_ops.ai_intent import annotate_ai_intent, classify_ai_intent


def _jd(text: str, title: str = "Product Manager") -> dict:
    return {"title": title, "jd": text}


# ---------- tier 判定 ----------


def test_strong_ai_jd_is_ai_pm():
    r = classify_ai_intent(_jd(
        "規劃 agentic workflow，導入 LLM 與 RAG，用 Claude Code 打造 AI agent"
    ))
    assert r.tier == "strong"
    assert r.is_ai_pm is True


def test_moderate_single_medium_signal_with_verb():
    # 一個中強度訊號 + 動詞加成 → moderate
    r = classify_ai_intent(_jd("負責導入 machine learning 模型到業務流程"))
    assert r.tier == "moderate"
    assert r.is_ai_pm is True


def test_pure_non_ai_pm_jd_is_none():
    r = classify_ai_intent(_jd("負責供應鏈管理與物流流程優化，撰寫 PRD 與規格文件"))
    assert r.tier == "none"
    assert r.is_ai_pm is False
    assert r.matched == []


def test_empty_jd_is_none():
    r = classify_ai_intent(_jd("", title=""))
    assert r.tier == "none"
    assert r.score == 0.0


# ---------- 意圖偵測核心：分辨「公司是 AI」vs「角色做 AI」 ----------


def test_company_boilerplate_ai_is_not_ai_pm():
    """JD 只在公司介紹提到 AI、職務本身與 AI 無關 → 不應判為 AI PM。

    這是「意圖偵測 vs 關鍵字比對」的關鍵差異：純關鍵字會誤判。
    """
    r = classify_ai_intent(_jd(
        "我們是一家 AI 新創公司。徵求產品經理，負責電商網站的使用者體驗優化與 A/B test"
    ))
    assert r.is_ai_pm is False
    assert r.tier in ("weak", "none")


def test_role_level_ai_signal_outweighs_boilerplate():
    role_ai = classify_ai_intent(_jd("負責規劃並打造 LLM agent 產品，導入 RAG pipeline"))
    company_ai = classify_ai_intent(_jd("AI 公司徵 PM，負責一般網站產品"))
    assert role_ai.score > company_ai.score
    assert role_ai.is_ai_pm and not company_ai.is_ai_pm


# ---------- 否定偵測 ----------


def test_negation_cancels_signal():
    r = classify_ai_intent(_jd("本職務不需 AI 相關經驗，負責傳統 ERP 系統導入"))
    assert r.is_ai_pm is False


# ---------- 動詞鄰近度加成 ----------


def test_verb_proximity_boosts_score():
    with_verb = classify_ai_intent(_jd("負責打造 automation 流程"))
    without_verb = classify_ai_intent(_jd(
        "公司福利優。automation。團隊聚餐補助每季一千元，零食津貼每月兩百元"
    ))
    assert with_verb.score > without_verb.score


# ---------- 子字串去重 ----------


def test_substring_dedup_no_double_count():
    """'agentic workflow' 不應同時把 'agentic' 也計分。"""
    r = classify_ai_intent(_jd("agentic workflow"))
    assert "agentic workflow" in r.matched
    assert "agentic" not in r.matched


def test_ai_substring_deduped_when_longer_phrase_matches():
    r = classify_ai_intent(_jd("打造 ai agent 平台"))
    assert "ai agent" in r.matched
    assert "ai" not in r.matched


# ---------- 詞邊界：避免 "ai" 誤中英文單字 ----------


def test_ai_does_not_false_match_inside_english_words():
    # email / detail / training / available 都含 "ai" 子字串
    r = classify_ai_intent(_jd(
        "Send detailed email about training. Remote available. Manage product backlog."
    ))
    assert r.matched == []
    assert r.tier == "none"


# ---------- annotate_ai_intent ----------


def test_annotate_mutates_jobs_in_place():
    jobs = [
        _jd("導入 LLM 與 agentic workflow"),
        _jd("負責供應鏈物流"),
    ]
    annotate_ai_intent(jobs)
    assert jobs[0]["ai_intent"]["is_ai_pm"] is True
    assert jobs[1]["ai_intent"]["is_ai_pm"] is False


def test_annotate_is_idempotent():
    jobs = [_jd("導入 LLM 與 RAG")]
    annotate_ai_intent(jobs)
    first = dict(jobs[0]["ai_intent"])
    annotate_ai_intent(jobs)
    assert jobs[0]["ai_intent"] == first


def test_ai_intent_dict_is_json_serializable():
    jobs = [_jd("Claude Code agentic workflow")]
    annotate_ai_intent(jobs)
    round_trip = json.loads(json.dumps(jobs[0]["ai_intent"]))
    assert round_trip["tier"] == "strong"
    assert set(round_trip.keys()) == {"is_ai_pm", "score", "tier", "matched"}


def test_matched_sorted_by_weight_descending():
    r = classify_ai_intent(_jd("使用 ai 工具，導入 agentic workflow，數據驅動決策"))
    # agentic workflow（強）應排在 data-driven（弱）之前
    assert r.matched[0] == "agentic workflow"
