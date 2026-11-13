"""focus_domain 測試：Physical AI／LLM／FDE 三個重點領域的判定邊界。

每一類「該原樣退回（不標）」的輸入各一條，再加上各條命中通道各一條。
"""
from __future__ import annotations

import pytest

from job_ops.focus_domain import classify_focus_domains


def _job(title="產品經理", jd="", benefits=""):
    return {"title": title, "jd": jd, "benefits": benefits}


# ---------- Physical AI ----------


def test_physical_title_hit():
    assert classify_focus_domains(_job("SA12282 Physical AI 產品經理")) == ["physical_ai"]


def test_physical_title_drone_hit():
    assert classify_focus_domains(_job("產品經理（無人機 SDK / 平台）")) == ["physical_ai"]


def test_physical_title_robotics_hit():
    # robot 用英數邊界比對，robotics 必須另列，否則職稱 (AI Robotics) 會漏
    assert classify_focus_domains(_job("資深產品經理(AI Robotics)")) == ["physical_ai"]


def test_physical_jd_strong_term_single_hit():
    job = _job(jd="負責具身智能平台的產品規劃與上市")
    assert classify_focus_domains(job) == ["physical_ai"]


def test_physical_jd_single_robot_mention_not_hit():
    # 公司簡介順帶一句「機器人」不代表這個 PM 缺在做機器人
    job = _job(jd="本公司產品涵蓋工業電腦與機器人應用。負責 SaaS 後台規劃。")
    assert classify_focus_domains(job) == []


def test_physical_jd_repeated_robot_terms_hit():
    # 剛好 3 次（機器人 ×2＋AMR ×1）：門檻是「>= 3」
    job = _job(jd="規劃機器人產品線，定義 AMR 規格，追蹤機器人上市")
    assert classify_focus_domains(job) == ["physical_ai"]


def test_physical_jd_two_robot_mentions_not_hit():
    # 門檻是 3 次：2 次仍可能是公司簡介＋一句應用舉例
    job = _job(jd="集團事業含機器人。產品可應用於機器人。負責 SaaS 規劃。")
    assert classify_focus_domains(job) == []


def test_chatbot_title_is_not_physical():
    assert "physical_ai" not in classify_focus_domains(_job("AI 聊天機器人產品經理"))


@pytest.mark.parametrize("word", ["聊天機器人", "對話機器人", "客服機器人", "機器人流程自動化"],
                         ids=["chatbot", "dialog", "service", "rpa"])
def test_software_robot_words_in_jd_are_not_physical(word):
    # 每個詞各出現 3 次：沒拿掉的話「機器人」累計 3 次就會達門檻
    job = _job(jd="、".join([word] * 3))
    assert "physical_ai" not in classify_focus_domains(job)


def test_physical_in_benefits_only_not_hit():
    benefits = "福利：員工可參加 Physical AI 與具身智能講座"
    job = _job(jd="負責 SaaS 後台規劃。\n" + benefits, benefits=benefits)
    assert classify_focus_domains(job) == []


# ---------- LLM ----------


def test_llm_title_hit():
    assert classify_focus_domains(_job("產品經理 — AI Agent 平台")) == ["llm"]


def test_llm_title_genai_hit():
    assert classify_focus_domains(_job("GenAI Product Manager")) == ["llm"]


def test_llm_jd_two_core_terms_hit():
    job = _job(jd="規劃 LLM 應用，設計 RAG 檢索流程")
    assert classify_focus_domains(job) == ["llm"]


def test_llm_jd_single_core_term_not_hit():
    # 只有「生成式 ai」一個核心詞；工具名不算
    job = _job(jd="熟悉生成式 AI 工具者佳，例如 ChatGPT、Claude、Gemini")
    assert classify_focus_domains(job) == []


def test_llm_subsumed_terms_count_once():
    # 「大型語言模型」內含「語言模型」，兩個詞表項目同時命中，但只算一個詞
    job = _job(jd="熟悉大型語言模型者佳")
    assert classify_focus_domains(job) == []


def test_bare_agent_is_not_llm():
    job = _job("代理商 Agent 產品經理", jd="管理海外 agent 與經銷 agent")
    assert classify_focus_domains(job) == []


def test_llm_in_benefits_only_not_hit():
    benefits = "福利：提供 LLM 與 RAG 課程補助"
    job = _job(jd="負責電商規劃。\n" + benefits, benefits=benefits)
    assert classify_focus_domains(job) == []


# ---------- FDE ----------


def test_fde_title_hit():
    assert classify_focus_domains(_job("Forward Deployed Product Manager")) == ["fde"]


def test_fde_hyphen_hit():
    assert classify_focus_domains(_job(jd="以 forward-deployed 模式與客戶共創")) == ["fde"]


def test_fde_abbr_hit():
    assert classify_focus_domains(_job(jd="以 FDE 模式進駐客戶端")) == ["fde"]


def test_fde_onsite_hit():
    assert classify_focus_domains(_job(jd="需駐點客戶端，主導導入")) == ["fde"]


def test_fde_onsite_second_occurrence_hit():
    # 第一個「駐點」只是地點，第二個才在客戶旁；要檢查到每一個出現位置
    job = _job(jd="工作地點：大直駐點。" + "。" * 30 + "專案期間需駐點客戶端")
    assert classify_focus_domains(job) == ["fde"]


def test_fde_onsite_customer_before_hit():
    # 「客戶」在「駐點」前面也算（真實 JD：「常態於新竹客戶現場及辦公室駐點協同」）
    job = _job(jd="需能常態於新竹客戶現場及辦公室駐點協同")
    assert classify_focus_domains(job) == ["fde"]


def test_onsite_location_only_not_fde():
    job = _job("專案管理師-承攬合作(大直駐點)", jd="負責專案時程追蹤與文件管理")
    assert classify_focus_domains(job) == []


def test_onsite_customer_far_away_not_fde():
    # 「客戶」離「駐點」超過 20 字：只是同一段 JD 各自提到，不是駐點客戶端
    job = _job(jd="服務客戶。" + "。" * 30 + "工作地點：大直駐點")
    assert classify_focus_domains(job) == []


def test_forward_alone_not_fde():
    job = _job(jd="forward-looking 思維，look forward to working with you")
    assert classify_focus_domains(job) == []


def test_fde_abbr_needs_word_boundary():
    job = _job(jd="系統代號 FDEX 與 xfde 模組")
    assert classify_focus_domains(job) == []


# ---------- 多領域 ----------


def test_multiple_domains_in_fixed_order():
    job = _job("Forward Deployed PM", jd="具身智能機器人導入，LLM 與 RAG 整合")
    assert classify_focus_domains(job) == ["physical_ai", "llm", "fde"]


def test_empty_job():
    assert classify_focus_domains({}) == []
