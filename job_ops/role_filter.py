"""職稱過濾：判斷一筆 104 職缺的 title 是否為目標 PM 缺。

掃描用了 `Product Builder`/`電腦視覺`/`AI Product Manager` 等寬詞與 jobcat 職類，
會連帶撈進大量工程師/RD 缺（電腦視覺工程師、機器學習工程師、Data Scientist…）。
本模組以「PM 白名單優先、工程職黑名單剔除」的規則把這些非目標職缺濾掉。

規則順序：
    1. 白名單優先 — title 含 PM 指標 → 一律保留（救回「演算法技術產品經理」這類混合 title）
    2. 黑名單     — 含工程職指標 → 剔除（Product Engineer / 架構師 / Engineering Manager / Data Scientist）
    3. 其餘        → 保留
"""
import re

# PM 白名單：含其一即視為目標 PM 缺，即使同時命中黑名單也豁免。
# 用「Product Manager」全詞（而非 Product），所以 Product Engineer 不會被誤救。
_PM_WHITELIST = (
    "產品經理",
    "Product Manager",
    "Product Owner",
    "Product Management",
)

# 「產品管理/產品企劃」救回「產品管理專員」這類入門 PM，但後接組織單位字
# （處/部/組/室/課/中心）時是部門名而非職能，不得觸發豁免，
# 否則「商品行銷企劃人員(產品管理處)」會被部門名救回。
_PM_FUNCTION = re.compile(r"產品(管理|企劃)(?![處部組室課中])")

# 「PM」縮寫須 word-boundary，否則 EPM / PMP / PMO / PMM 會被誤判成 PM。
_PM_ABBR = re.compile(r"\bPM\b")

# 工程職黑名單：title 含其一（且未被白名單豁免）→ 剔除。
# 「Engineer」為子字串，連帶涵蓋 Engineering Manager / Engineering Project Manager。
_ROLE_BLACKLIST = (
    "工程師",
    "engineer",
    "developer",
    "架構師",
    "architect",
    "資料科學",
    "data scientist",
)

# 非 PM 職能黑名單：行政/業務/行銷/設計/客服等。
# 刻意「不」放泛詞，否則會誤殺要保留的職類：
#   - 不放「專員 / Specialist」→ 保留「產品管理專員」
#   - 不放「Manager / Project / 專案」→ 保留「專案經理 Project Manager」
#   - 不放英文「HR」→ 避免 hr 子字串誤傷，只用中文「人資」
_NON_PM_BLACKLIST = (
    "行政",
    "總務",
    "秘書",
    "secretary",
    "客服",
    "客戶服務",
    "業務",
    "銷售",
    "sales",
    "行銷",
    "marketing",
    "設計師",
    "designer",
    "會計",
    "財務",
    "人資",
    "採購",
    "辦事員",
    "差旅",
    # 美術 / 內容製作（「資深動態特效」這類遊戲美術缺）
    "特效",
    "動畫",
    "美術",
    "原畫",
    # 教育訓練（「課程企劃經理」「AI講師」）
    "課程",
    "講師",
    # BD / 市場開發（與既有 sales 同類）
    "市場開發",
    "business development",
    # 其他混入過的非 PM 職
    "替代役",
    "程式開發",
)


def is_target_role(title: str) -> bool:
    """title 是否為目標 PM 缺；非字串或空字串時保守保留。"""
    if not title:
        return True
    if (
        any(w in title for w in _PM_WHITELIST)
        or _PM_FUNCTION.search(title)
        or _PM_ABBR.search(title)
    ):
        return True
    lowered = title.lower()
    if any(b in lowered for b in _ROLE_BLACKLIST):
        return False
    if any(b in lowered for b in _NON_PM_BLACKLIST):
        return False
    return True
