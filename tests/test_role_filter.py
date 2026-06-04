"""職稱過濾 is_target_role 測試 — 黑名單剔工程職、PM 白名單豁免。

fixtures 取自 2026-06-04 實際掃描結果的真實 104 title。
"""
import pytest

from job_ops.role_filter import is_target_role


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


# ---------- PM 鄰近職（專案經理/產品管理專員/Product Builder）：應保留 ----------

PM_ADJACENT_KEPT = [
    "專案經理/Project Manager",
    "AI Project Manager AI專案經理",
    "PG - 產品管理專員 Product Management Specialist (新莊)",
    "[HQ - Taipei] Forward-Deployed Product Builder",
    "AI 產品管理PM (新北)",
    "Sales PM (歐洲區)_5301",  # 含 sales 黑名單字，但 \bPM\b 白名單優先 → 保留
]


@pytest.mark.parametrize("title", PM_ADJACENT_KEPT)
def test_pm_adjacent_roles_kept(title):
    assert is_target_role(title) is True
