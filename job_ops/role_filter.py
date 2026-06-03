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
_PM_WHITELIST = ("產品經理", "Product Manager", "Product Owner", "產品企劃")

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


def is_target_role(title: str) -> bool:
    """title 是否為目標 PM 缺；非字串或空字串時保守保留。"""
    if not title:
        return True
    if any(w in title for w in _PM_WHITELIST) or _PM_ABBR.search(title):
        return True
    lowered = title.lower()
    if any(b in lowered for b in _ROLE_BLACKLIST):
        return False
    return True
