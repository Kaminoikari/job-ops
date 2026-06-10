"""職稱過濾測試 — is_target_role（title 階段）+ confirm_target_role（JD 階段）。

fixtures 取自 2026-06-04 / 2026-06-10 實際掃描結果的真實 104 title 與 JD 片段。
"""
import pytest

from job_ops.role_filter import confirm_target_role, is_target_role


# ---------- 純工程師 / RD 缺：應剔除 ----------

PURE_ENGINEER_TITLES = [
    "電腦視覺影像辨識工程師",
    "AI 電腦視覺工程師 (AI Computer Vision Engineer)",
    "機器學習與電腦視覺演算法工程師",
    "Senior Computer Vision Engineer",
    "Senior Software Engineer (Frontend)",
    "深度學習演算法工程師",
    "AI工程師",
    "軟體研發工程師 (嵌入式系統暨影像處理)",
    "Machine Learning and Signal Processing Engineer (機器學習與訊號處理工程師)",
]


@pytest.mark.parametrize("title", PURE_ENGINEER_TITLES)
def test_pure_engineer_titles_rejected(title):
    assert is_target_role(title) is False


# ---------- Product Engineer / 單獨 Architect / Data Scientist：應剔除 ----------

PRODUCT_ENGINEER_AND_ARCHITECT_TITLES = [
    "(Sr.) Product Engineer-Power Management IC",
    "Staff Product Applications Engineer (Advanced Consumer Power)",
    "Principal Product Application Engineer",
    "Senior Product Engineer – Silicon Validation",
    "Product Development Solution Architect (PDSA)",
    "資深資料科學家  Senior/Junior Data Scientist",
]


@pytest.mark.parametrize("title", PRODUCT_ENGINEER_AND_ARCHITECT_TITLES)
def test_product_engineer_and_architect_rejected(title):
    assert is_target_role(title) is False


# ---------- Engineering Manager / EPM：應剔除（且 PM 白名單不可誤救 EPM）----------

ENGINEERING_MANAGER_TITLES = [
    "Engineering Project Manager (EPM)",
    "RD22120 Engineering Manager - Autonomous Systems(AI應用)",
]


@pytest.mark.parametrize("title", ENGINEERING_MANAGER_TITLES)
def test_engineering_manager_and_epm_rejected(title):
    assert is_target_role(title) is False


# ---------- 真 PM：應保留 ----------

REAL_PM_TITLES = [
    "產品經理",
    "Product Manager 產品經理",
    "Sr. Product Manager 資深產品經理",
    "AI 產品經理 AI Product Manager",
    "硬體產品經理 / Hardware Product Manager (Drones)",
    "Product Manager - Embedded Single Board Computers",
]


@pytest.mark.parametrize("title", REAL_PM_TITLES)
def test_real_pm_titles_kept(title):
    assert is_target_role(title) is True


# ---------- 混合 title：含工程字但也含「產品經理/PM」→ 白名單救回，應保留 ----------

MIXED_PM_TITLES = [
    "演算法技術產品經理/ Algorithm Technical Product Manager",
    "資安產品研發產品經理",
    "資料產品經理｜數位研發中心",
    "產品經理/系統架構師",
    "Flash_Enterprise Storage 產品架構師/產品經理 PM (Product Manager)",
    "AI PM(AI產品研發與客戶專案管理)",
]


@pytest.mark.parametrize("title", MIXED_PM_TITLES)
def test_mixed_pm_titles_kept(title):
    assert is_target_role(title) is True


# ---------- 邊界：PM 縮寫須 word-boundary，不可被 EPM/PMP/PMO 誤命中 ----------

def test_pm_abbreviation_requires_word_boundary():
    # 「PM」獨立出現 → 視為 PM 白名單
    assert is_target_role("產品經理 (PM)") is True
    # 「EPM」內含 pm 子字串，但不是 PM → 不得被白名單救回
    assert is_target_role("Engineering Project Manager (EPM)") is False


# ---------- 非 PM 職能（行政/業務/行銷/設計/客服）：應剔除 ----------

NON_PM_TITLES = [
    "行政主管 Office Manager",
    "R&D 行政助理",
    "【海外市場專員】海外業務#國際貿易專業展覽#食品與保健食品產業#AI賦能工作流",
    "Product Marketing",
    "Product Marketing Manager",
    "AI 產品設計師 (AI Product Designer)",
    "資深介面設計師, Senior UI Designer, Education Solution BU",
    "Product Sales Manager_先進工業電腦視覺解決方案新事業發展部(台北)",
    "Marketing Manager",
    "醫療行銷與產品專員（Medical Marketing and Product Specialist）",
]


@pytest.mark.parametrize("title", NON_PM_TITLES)
def test_non_pm_roles_rejected(title):
    assert is_target_role(title) is False


# ---------- 非 PM 職能（美術特效/課程講師/BD/開發）：應剔除 ----------
# fixtures 取自 2026-06-10 實際掃描結果的漏網 title。

NON_PM_TITLES_2026_06_10 = [
    "資深動態特效",
    "【領導影響力學院】課程企劃經理",
    "桃竹區-AI講師(機器學習、深度學習、自然語意、影像辨識...)",
    "全球市場開發經理 Global Partnership",
    "Senior Business Development Manager – AI Call Agent Solutions",
    "軟體研發替代役 (嵌入式系統暨影像處理)",
    "智慧製造工程中心-產測程式開發 技術主任(外派越南)",
]


@pytest.mark.parametrize("title", NON_PM_TITLES_2026_06_10)
def test_non_pm_roles_2026_06_10_rejected(title):
    assert is_target_role(title) is False


# ---------- 白名單不得被「部門名」觸發：產品管理處/部 是單位不是職能 ----------

def test_whitelist_not_triggered_by_department_name():
    # 「產品管理處」是部門名，title 本體是行銷缺 → 不得豁免，應被「行銷」剔除
    assert is_target_role("商品行銷企劃人員(產品管理處)") is False


def test_pm_management_as_role_still_kept():
    # 「產品管理」後接職能字（師/專員/副理）仍是白名單
    assert is_target_role("產品管理師(台北/高雄)") is True
    assert is_target_role("PG - 產品管理專員 Product Management Specialist (新莊)") is True


def test_blacklisted_function_word_saved_by_pm_whitelist():
    # 含「課程/動畫」但 title 本體是產品經理 → 白名單救回
    assert is_target_role("線上課程產品經理") is True
    assert is_target_role("【在家上班】新創軟體公司  徵   2D原畫/ 產品經理") is True


# ---------- PM 鄰近職（專案經理/產品管理專員/Product Builder）：應保留 ----------

PM_ADJACENT_KEPT = [
    "專案經理/Project Manager",
    "AI Project Manager AI專案經理",
    "PG - 產品管理專員 Product Management Specialist (新莊)",
    "[HQ - Taipei] Forward-Deployed Product Builder",
    "AI 產品管理PM (新北)",
    "Sales PM (歐洲區)_5301",  # 含 sales 黑名單字，但 PM 縮寫白名單優先 → 保留
    "AI Product Builder【股感資訊】",
    "AI 落地產品負責人",
]


@pytest.mark.parametrize("title", PM_ADJACENT_KEPT)
def test_pm_adjacent_roles_kept(title):
    assert is_target_role(title) is True


# ---------- PM 縮寫邊界：中文字 / 底線旁的 PM 也要命中 ----------
# Python re 的 \b 把中文與底線都當 word char，「技術PM」「PM_新竹」會比對失敗，
# 這些是真 PM 缺，須用自訂邊界救回。

def test_pm_abbreviation_adjacent_to_cjk_and_underscore():
    assert is_target_role("【產品部】AI應用技術PM") is True
    assert is_target_role("【緯創資通】AI Server PM_新竹_6/27 (六) 台北面談會") is True
    # 英數相鄰仍不算獨立 PM：TPMO / EPM / PMO 不得誤中
    assert is_target_role("【TPMO0301】Operation Manager 行銷企劃") is False
    assert is_target_role("Engineering Project Manager (EPM)") is False


# ---------- JD 階段 confirm_target_role：title 模糊時看 JD 內容 ----------
# JD fixtures 節錄自 2026-06-10 實際掃描。

def test_title_whitelisted_skips_jd_check():
    # title 已明確是 PM → JD 完全不像 PM 也保留
    assert confirm_target_role("產品經理", "負責客戶投訴處理與銷售目標") is True


def test_ambiguous_title_kept_when_jd_shows_pm_work():
    assert confirm_target_role(
        "TPM (Technical Project Manager) 技術專案經理",
        "負責跨部門專案管理，統籌產品需求與時程",
    ) is True
    assert confirm_target_role(
        "PJM",
        "own the product roadmap, write prd and drive product planning",
    ) is True


def test_ambiguous_title_cut_when_jd_shows_non_pm_work():
    # 緯創 AI Server AM：客戶關係 + 報價 + 銷售目標 → account manager
    assert confirm_target_role(
        "【緯創資通】AI Server AM_新竹場",
        "建立和維護與客戶的長期合作關係，提供專業的客戶服務和支援。NPI報價及成本分析，在壓力下達成銷售目標",
    ) is False
    # Asset Manager：JD 無任何產品/專案管理訊號
    assert confirm_target_role(
        "Asset Manager",
        "負責不動產資產評估、租賃合約管理與投資報酬分析",
    ) is False
    # 群益 AI應用規劃師：LLM 微調 / RAG 實作 → 工程實作職
    assert confirm_target_role(
        "AI應用規劃師",
        "進行機器學習模型與大型語言模型（LLM）之微調、優化與應用落地，規劃與實作 RAG架構",
    ) is False


def test_ambiguous_title_with_empty_jd_kept_conservatively():
    assert confirm_target_role("綜合企劃處-整合及創新應用人員", "") is True


def test_blacklisted_title_still_cut_regardless_of_jd():
    # title 黑名單命中 → JD 再像 PM 也不豁免（第一階段已剔，此為防呆）
    assert confirm_target_role("資深動態特效", "負責產品規劃與 roadmap") is False
