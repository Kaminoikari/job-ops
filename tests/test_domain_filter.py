"""domain_filter 測試：納入門檻從「必須有 AI 訊號」放寬成「AI 或 軟體/SaaS 產品」。

背景：舊門檻只認 AI 訊號，把「標準的 SaaS 產品經理」這種 JD 完全沒提 AI 的缺
整筆剔除（例：永悅健康 8rm17）。放寬後這類缺會進日報，但因為報表按
ai_intent.priority 排序，無 AI 訊號的缺自然排在最後，不會蓋掉 AI PM 缺。
"""
from __future__ import annotations

from job_ops.domain_filter import has_software_signal, passes_domain_gate

# 真實案例：永悅健康 8rm17 的 JD 節錄（JD 全文無任何 AI 字眼）
SAAS_PM_JD = (
    "負責主導軟體產品的開發與優化。此職位將與跨部門團隊緊密合作，評估商業價值、"
    "規劃開發範疇。具備 3～5 年軟體產品管理或產品開發經驗，熟悉 SaaS 或系統整合"
    "相關產品尤佳。製作線框圖或原型設計，協助系統設計確認與團隊共識建立。"
)

# 硬體／製造業產品線 PM：同樣沒有 AI 訊號，但也不是軟體產品缺
HARDWARE_PM_JD = (
    "負責筆記型電腦產品線之規劃與管理，與 ODM 客戶洽談機構設計與料號成本，"
    "追蹤模具開發進度、量產良率與供應鏈交期，並管理產品生命週期與庫存水位。"
)


def _job(title: str, jd: str) -> dict:
    return {"title": title, "jd": jd}


def test_saas_pm_without_any_ai_signal_passes():
    job = _job("產品管理師/產品經理Product Development Manager", SAAS_PM_JD)
    assert has_software_signal(job) is True
    assert passes_domain_gate(job) is True


def test_hardware_product_line_pm_without_ai_is_rejected():
    job = _job("產品經理", HARDWARE_PM_JD)
    assert has_software_signal(job) is False
    assert passes_domain_gate(job) is False


def test_ai_job_without_software_wording_still_passes():
    """原本的 AI 通道必須保留：JD 有 AI 訊號但沒有軟體字眼時仍要通過。"""
    job = _job("AI 產品經理", "負責大型語言模型應用的產品規劃與落地。")
    assert has_software_signal(job) is False
    assert passes_domain_gate(job) is True


def test_gate_reads_cached_ai_intent_when_present():
    """annotate_ai_intent 標記過的缺要吃快取欄位，不重算。"""
    job = _job("產品經理", HARDWARE_PM_JD)
    job["ai_intent"] = {"has_ai": True}
    assert passes_domain_gate(job) is True


def test_short_ascii_terms_respect_word_boundaries():
    """ui / app / api 這類短詞不可以命中 building、application 內部的子字串。"""
    job = _job("產品經理", "負責 building guidelines 與 happenings 的追蹤管理。")
    assert has_software_signal(job) is False


def test_production_line_wording_is_not_mistaken_for_online():
    """中文無詞邊界：「產線上 / 生產線上」內含「線上」二字。若詞庫收「線上」，
    製造業產線 PM 會拿到一張完全沒有軟體內容的通行證。"""
    for jd in ("負責產線上的良率追蹤與模具開發", "生產線上異常處理", "產線上線時程管理"):
        assert has_software_signal(_job("產品經理", jd)) is False, jd


def test_representative_domain_terms_each_pass():
    """詞庫是資料不是邏輯，抽樣釘住代表詞，避免整批被刪掉還全綠。"""
    for jd in (
        "負責 SaaS 訂閱制產品的定價與包裝",
        "規劃開放 API 與 SDK 的開發者體驗",
        "負責電商網站前端改版與轉換率優化",
        "主導雲端服務的資料庫遷移與後端重構",
        "負責 App 的 UX 流程設計與 iOS 改版",
    ):
        assert has_software_signal(_job("產品經理", jd)) is True, jd


def test_ambiguous_platform_wording_alone_does_not_pass():
    """「平台」「系統整合」單獨出現不算軟體訊號——硬體平台缺會誤入（實測邊際效益僅 3.7%）。"""
    job = _job("產品經理", "負責硬體平台與系統整合專案之進度追蹤與成本管理。")
    assert has_software_signal(job) is False
