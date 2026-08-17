"""領域過濾：判斷職缺是否落在目標產品領域（AI 或 軟體/SaaS）。

與 role_filter 的分工：
    role_filter  — 這是不是「產品經理」這個**職能**
    domain_filter — 這個 PM 缺是不是在**目標領域**

為什麼不是只看 AI：原本的納入門檻要求 JD/title 必須出現 AI 關鍵字，否則整筆
剔除。這會把「標準的 SaaS 產品經理」這種 JD 通篇沒提 AI 的缺一起砍掉，而那
正是目標職缺之一。改成「AI 訊號 **或** 軟體/SaaS 產品訊號」兩條通道擇一。
放寬不會淹沒 AI PM 缺：日報按 `ai_intent.priority` 排序，無 AI 訊號的缺
tier 為「無」、分數 0，自然沉在最後。

為什麼不用 104 的 industry 欄位當白名單：該欄位是公司自填且常與實際業務不符。
實測永悅健康（H2U，健康科技 SaaS）報的是「工商顧問服務業」，而該產業別在歷史
日報中「無 AI 訊號」比例最高（69.6%）。用產業白名單會直接排除掉真正的 SaaS 缺。

詞庫取捨（依 2026-08-17 對 272 筆已知目標 PM 缺的實測）：
  - 只收「領域詞」，不收 PM 流程詞（roadmap / prd / user story / sprint / 敏捷）。
    流程詞每個 PM 缺都會寫，硬體 PM 也有 roadmap，放進來等於門檻失效。
  - 刻意排除「平台 / platform / 系統整合」。這三個詞硬體缺也大量使用，而實測
    它們只多帶進 10 筆（+3.7%），邊際效益不足以換取誤放硬體產品線 PM 的代價。
  - 中文詞走純子字串比對（無詞邊界），所以短中文詞要檢查有沒有被包在其他詞裡。
    「線上」因為會命中「產線上／生產線上」而被排除。
  - 詞庫對那 272 筆的覆蓋率為 78.3%；未覆蓋的部分本來就走 AI 通道通過，
    不構成損失（實測新門檻是舊門檻的嚴格超集，272 筆全數仍通過）。
"""
from __future__ import annotations

from job_ops.ai_intent import has_ai_signal, phrase_present

# 軟體 / SaaS 產品領域訊號（全小寫比對）。皆為「領域詞」——出現即代表這個產品
# 本身是軟體或線上服務，而不是機構件、料號、模具那類實體產品。
SOFTWARE_SIGNALS: tuple[str, ...] = (
    # 交付形態
    "saas",
    "paas",
    "iaas",
    "軟體",
    "software",
    "雲端",
    "cloud",
    "數位產品",
    "digital product",
    "訂閱制",
    "subscription",
    # 刻意不收「線上」：中文無詞邊界，「產線上／生產線上」內含這兩字，
    # 會給製造業產線 PM 一張完全沒有軟體內容的通行證。
    # 技術構件
    "api",
    "sdk",
    "應用程式",
    "app",
    "網站",
    "web",
    "前端",
    "後端",
    "前後端",
    "frontend",
    "backend",
    "微服務",
    "microservice",
    "資料庫",
    "database",
    "資訊系統",
    "開源",
    "open source",
    "devops",
    # 使用者介面 / 體驗（軟體產品才會有的職責）
    "使用者體驗",
    "user experience",
    "ux",
    "ui",
    "mobile",
    "ios",
    "android",
    # 常見軟體產品領域
    "電商",
    "e-commerce",
    "fintech",
    "crm",
    "erp",
    "數位轉型",
)


def has_software_signal(job: dict) -> bool:
    """job 的 title / JD 是否出現任一軟體/SaaS 領域訊號。

    會先把福利文案從 JD 裡拿掉再比對：scraper_104.detail 把「福利：…」接在 jd
    後面，而福利段落常提到員工用的 app（例：永悅健康寫「專屬的職場健康服務 app」）。
    那是公司給員工的福利，不是這個職缺要做的產品，拿它當領域訊號會讓製造業
    產品線 PM 靠福利文案矇混通過。
    """
    jd = job.get("jd") or ""
    benefits = job.get("benefits") or ""
    if benefits:
        jd = jd.replace(benefits, " ")
    text = ((job.get("title") or "") + "\n" + jd).lower()
    if not text.strip():
        return False
    return any(phrase_present(text, p) for p in SOFTWARE_SIGNALS)


def passes_domain_gate(job: dict) -> bool:
    """納入日報的領域門檻：AI 訊號或軟體/SaaS 訊號，兩條通道擇一即可。"""
    return has_ai_signal(job) or has_software_signal(job)
