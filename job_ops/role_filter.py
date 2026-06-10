"""職稱過濾：判斷一筆 104 職缺是否為目標 PM 缺。

掃描用了 `Product Builder`/`電腦視覺`/`AI Product Manager` 等寬詞與 jobcat 職類，
會連帶撈進大量工程師/RD 缺（電腦視覺工程師、機器學習工程師、Data Scientist…）。
本模組以「PM 白名單優先、工程職黑名單剔除」的規則把這些非目標職缺濾掉。

兩階段過濾：
    1. is_target_role(title) — search 列表階段，只看 title。
       白名單優先 → 黑名單剔除 → 其餘保留。明確非 PM 的 title 在抓 detail
       前就剔掉，減少抓取量。
    2. confirm_target_role(title, jd) — detail 抓完後。title 白名單命中直接
       保留；title 模糊（非白名單、也沒中黑名單）時改看 JD 內容，JD 須出現
       產品/專案管理職能訊號才保留。「Asset Manager」「AI Server AM」這類
       title 看不出職能的缺由此剔除。
"""
import re

# PM 白名單：含其一即視為目標 PM 缺，即使同時命中黑名單也豁免。
# 用「Product Manager」全詞（而非 Product），所以 Product Engineer 不會被誤救。
# 「Product Builder」「產品負責人」是 PM 等價角色（ai_intent ROLE_SIGNALS 同列）。
_PM_WHITELIST = (
    "產品經理",
    "Product Manager",
    "Product Owner",
    "Product Management",
    "Product Builder",
    "產品負責人",
)

# 「產品管理/產品企劃」救回「產品管理專員」這類入門 PM，但後接組織單位字
# （處/部/組/室/課/中心）時是部門名而非職能，不得觸發豁免，
# 否則「商品行銷企劃人員(產品管理處)」會被部門名救回。
_PM_FUNCTION = re.compile(r"產品(管理|企劃)(?![處部組室課中])")

# 「PM」縮寫須獨立出現，否則 EPM / PMP / PMO / PMM 會被誤判成 PM。
# 不用 \b：Python re 把中文與底線都當 word char，「技術PM」「PM_新竹」
# 這類真 PM 缺會比對失敗 — 邊界改為「前後不是英數」。
_PM_ABBR = re.compile(r"(?<![A-Za-z0-9])PM(?![A-Za-z0-9])")

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

# JD 職能訊號：title 模糊時，JD（或 title）出現其一即視為實際在做產品/專案
# 管理工作。全小寫比對。專案管理訊號比照 title 規則一併保留（專案經理是
# 刻意保留的鄰近職）。
_JD_ROLE_SIGNALS = (
    # 產品管理
    "產品經理",
    "產品負責人",
    "產品規劃",
    "產品策略",
    "產品藍圖",
    "產品路線",
    "產品生命週期",
    "產品需求",
    "產品管理",
    "產品企劃",
    "產品開發",
    "產品上市",
    "產品營運",
    "product manager",
    "product owner",
    "product management",
    "product planning",
    "product strategy",
    "product lifecycle",
    "roadmap",
    "prd",
    "go-to-market",
    "gtm",
    "user story",
    "backlog",
    "mvp",
    "使用者研究",
    "user research",
    # 專案管理
    "專案經理",
    "專案管理",
    "project manager",
    "project management",
)


def _is_title_whitelisted(title: str) -> bool:
    return (
        any(w in title for w in _PM_WHITELIST)
        or _PM_FUNCTION.search(title) is not None
        or _PM_ABBR.search(title) is not None
    )


def is_target_role(title: str) -> bool:
    """title 是否為目標 PM 缺；非字串或空字串時保守保留。"""
    if not title:
        return True
    if _is_title_whitelisted(title):
        return True
    lowered = title.lower()
    if any(b in lowered for b in _ROLE_BLACKLIST):
        return False
    if any(b in lowered for b in _NON_PM_BLACKLIST):
        return False
    return True


def confirm_target_role(title: str, jd: str) -> bool:
    """detail 抓完後的第二階段判定：title 模糊時改看 JD 內容。

    - title 黑名單命中 → 剔除（第一階段已剔，此為防呆）
    - title 白名單命中 → 保留，不看 JD
    - title 模糊 → JD 須出現產品/專案管理職能訊號；JD 缺漏時保守保留
    """
    if not is_target_role(title):
        return False
    if title and _is_title_whitelisted(title):
        return True
    if not jd:
        return True
    text = ((title or "") + "\n" + jd).lower()
    return any(s in text for s in _JD_ROLE_SIGNALS)
