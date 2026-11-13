"""Daily report: markdown + Gmail-safe inline-styled HTML."""
from __future__ import annotations

import html as html_lib
import re
from collections import defaultdict
from datetime import date

from .focus_domain import FOCUS_ICONS, FOCUS_LABELS, classify_focus_domains
from .history import ScanResult


# ---------- Markdown 產生 ----------


def _fmt_salary(salary_min: int | None, salary_raw: str = "") -> str:
    if salary_min is None:
        return "面議"
    return f"{salary_min:,}+"


def _trim(s: str, n: int = 80) -> str:
    s = s.replace("|", "/").replace("\n", " ").strip()
    if len(s) > n:
        return s[:n] + "…"
    return s


_AI_TIER_LABEL = {
    "strong": "🤖 強",
    "moderate": "🤖 中",
    "weak": "· 弱",
    "none": "無",
}


def _ai_cell(j: dict) -> str:
    """日報表格的 AI 意圖欄位。"""
    intent = j.get("ai_intent") or {}
    return _AI_TIER_LABEL.get(intent.get("tier", ""), "無")


def _is_ai_pm(j: dict) -> bool:
    return bool((j.get("ai_intent") or {}).get("is_ai_pm"))


def _ai_score(j: dict) -> float:
    """排序鍵：優先用 priority（含 AI native / 供應鏈 產業公司加分），fallback 到 score。"""
    intent = j.get("ai_intent") or {}
    val = intent.get("priority")
    if val is None:
        val = intent.get("score")
    try:
        return float(val or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _focus_icons(j: dict) -> str:
    """職稱前綴的重點領域圖示（例：「🦾🧠 」）；不屬於重點領域回空字串。"""
    icons = "".join(FOCUS_ICONS[k] for k in classify_focus_domains(j))
    return icons + " " if icons else ""


def _job_row(j: dict) -> str:
    salary = _fmt_salary(j.get("salary_min"))
    company = _trim(j.get("company", "—"), 30)
    title = _trim(_focus_icons(j) + j.get("title", "—"), 50)
    industry = _trim(j.get("industry", "") or "—", 20)
    loc = _trim(j.get("location", "") or "—", 20)
    url = j.get("url", "")
    link = f"[104]({url})" if url else "—"
    ai = _ai_cell(j)
    notes = j.get("notes") or {}
    activeness = _trim(str(notes.get("activeness", "") or "—"), 20)
    reply = _trim(str(notes.get("reply_info", "") or "—"), 18)
    resume = _trim(str(notes.get("resume_info", "") or "—"), 18)
    return (
        f"| {ai} | {salary} | {company} | {industry} | {title} | {loc} | {link} | "
        f"{activeness} | {reply} | {resume} |"
    )


def _job_row_header() -> list[str]:
    return [
        "| AI | 月薪下限 | 公司 | 產業 | 職位 | 地區 | 連結 | 徵才積極度 | 回覆求職者 | 聯絡應徵者 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]


_FOCUS_STATUS = (("new_items", "🆕 新上架"), ("refreshed", "🔄 104 更新"), ("still_listed", "📌 仍在架"))


def _focus_rows(scan: ScanResult) -> list[tuple[str, list[str], dict]]:
    """在架職缺中屬於重點領域者：（狀態、領域 keys、job），新上架→更新→仍在架，同狀態依 priority。"""
    rows: list[tuple[str, list[str], dict]] = []
    for attr, status in _FOCUS_STATUS:
        group = [(status, classify_focus_domains(j), j) for j in getattr(scan, attr)]
        group = [r for r in group if r[1]]
        group.sort(key=lambda r: -_ai_score(r[2]))
        rows.extend(group)
    return rows


def _count_new_focus(scan: ScanResult) -> int:
    return sum(1 for j in scan.new_items if classify_focus_domains(j))


def build_markdown(
    scan: ScanResult,
    today: str,
    *,
    full: bool = False,
) -> str:
    """生成日報 markdown。

    full=False (預設、日常模式): 只顯示變化（新上架／更新／薪資變動）
    full=True: 加上「全部活躍職缺 — 多排序視角」附錄

    所有職缺都已通過領域門檻（AI 訊號或軟體/SaaS 訊號，見 domain_filter）；
    已下架區塊與詳細 JD 區塊都不再顯示（職缺常被
    下架再上架刷更新日期，已下架資訊無參考價值；詳細資訊過於冗長）。
    排序：AI native / AI 供應鏈 產業或公司優先（ai_intent.priority），其次月薪。
    """
    lines: list[str] = []
    new_paid = [j for j in scan.new_items if j.get("salary_min") is not None]
    new_negotiable = [j for j in scan.new_items if j.get("salary_min") is None]
    # 排序：AI 意圖分數高者優先，其次月薪降序
    new_paid.sort(key=lambda j: (-_ai_score(j), -(j.get("salary_min") or 0)))
    new_negotiable.sort(key=lambda j: -_ai_score(j))
    new_ai_count = sum(1 for j in scan.new_items if _is_ai_pm(j))

    active_jobs = scan.new_items + scan.refreshed + scan.still_listed
    focus_rows = _focus_rows(scan)

    # 1. 摘要
    lines.append(f"# 📋 104 AI 職缺日報 — {today}")
    lines.append("")
    lines.append("## 📊 摘要")
    lines.append("")
    lines.append(f"- 今日總抓取：**{scan.total_today()}** 筆（全數通過領域門檻：AI 或 軟體/SaaS）")
    lines.append(f"- 🆕 今日新上架：**{len(scan.new_items)}** 筆（含面議 {len(new_negotiable)} 筆）")
    lines.append(f"- 🤖 其中強訊號 AI PM：**{new_ai_count}** 筆（JD 意圖偵測判定，已排前）")
    lines.append(
        f"- 🎯 重點領域（Physical AI／LLM／FDE）：在架 **{len(focus_rows)}** 筆，"
        f"其中今日新上架 **{_count_new_focus(scan)}** 筆"
    )
    lines.append(f"- 🔄 104 更新日期變動：**{len(scan.refreshed)}** 筆")
    lines.append(f"- 💰 薪資變動：**{len(scan.salary_changed)}** 筆")
    lines.append(f"- 📌 仍在架（無變動）：{len(scan.still_listed)} 筆")
    if scan.listed_not_scanned:
        lines.append(f"- 📡 在架未掃到（漏掃補回）：**{len(scan.listed_not_scanned)}** 筆")
    lines.append("")

    # 1b. 重點領域：每天列出全部在架者（不只變化），方便一眼看完這三個領域
    if focus_rows:
        lines.append(f"## 🎯 重點領域職缺（{len(focus_rows)} 筆）")
        lines.append("")
        lines.append("> " + "、".join(FOCUS_LABELS.values())
                     + "；下方各表的職稱前也會標同樣的圖示")
        lines.append("")
        lines.append("| 領域 | 狀態 | AI | 月薪下限 | 公司 | 職位 | 地區 | 連結 | 徵才積極度 |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for status, keys, j in focus_rows:
            notes = j.get("notes") or {}
            url = j.get("url", "")
            lines.append(
                f"| {'／'.join(FOCUS_LABELS[k] for k in keys)} | {status} | {_ai_cell(j)} | "
                f"{_fmt_salary(j.get('salary_min'))} | "
                f"{_trim(j.get('company', '—'), 30)} | "
                f"{_trim(j.get('title', '—'), 50)} | "
                f"{_trim(j.get('location', '') or '—', 20)} | "
                f"{f'[104]({url})' if url else '—'} | "
                f"{_trim(str(notes.get('activeness', '') or '—'), 20)} |"
            )
        lines.append("")

    # 2. 今日新上架
    lines.append("## 🆕 今日新上架")
    lines.append("")
    if not scan.new_items:
        lines.append("_今日無新上架職缺_")
        lines.append("")
    else:
        lines.extend(_job_row_header())
        for j in new_paid:
            lines.append(_job_row(j))
        if new_negotiable:
            lines.append("| **— 以下為面議 —** | | | | | | | | | |")
            for j in new_negotiable:
                lines.append(_job_row(j))
        lines.append("")

    # 3. 104 更新日期變動（欄位完全比照「今日新上架」）
    if scan.refreshed:
        lines.append(f"## 🔄 104 更新日期變動（公司主動推，{len(scan.refreshed)} 筆）")
        lines.append("")
        lines.append("> 這些職缺已上架一段時間，但公司今天更新了 104 上的職缺日期")
        lines.append("")
        # 排序：AI 意圖分數高者優先，其次 104 更新日降序
        refreshed_sorted = sorted(
            scan.refreshed,
            key=lambda j: (_ai_score(j), j.get("104_update_date", "")),
            reverse=True,
        )
        lines.extend(_job_row_header())
        for j in refreshed_sorted:
            lines.append(_job_row(j))
        lines.append("")

    # 4. 薪資變動
    if scan.salary_changed:
        lines.append(f"## 💰 薪資變動警示（{len(scan.salary_changed)} 筆）")
        lines.append("")
        lines.append("| 變化 | 原薪資 | 新薪資 | 公司 | 職位 | 連結 |")
        lines.append("|---|---|---|---|---|---|")
        for j in scan.salary_changed:
            prev = j.get("prev_salary_min")
            cur = j.get("salary_min")
            if prev is None or cur is None:
                arrow = "↔️ 面議↔具體"
            elif cur > prev:
                arrow = f"⬆️ +{cur - prev:,}"
            else:
                arrow = f"⬇️ {cur - prev:,}"
            lines.append(
                f"| {arrow} | {_fmt_salary(prev)} | {_fmt_salary(cur)} | "
                f"{_trim(j.get('company', '—'), 30)} | {_trim(j.get('title', '—'), 50)} | "
                f"[104]({j.get('url', '')}) |"
            )
        lines.append("")

    # 4b. 在架未掃到（今天搜尋沒撈到，但 detail 確認 104 上仍在架的漏掃職缺）
    if scan.listed_not_scanned:
        lines.append(f"## 📡 在架未掃到（{len(scan.listed_not_scanned)} 筆）")
        lines.append("")
        lines.append("> 今天搜尋關鍵字沒撈到，但逐筆向 104 確認後仍在架——屬掃描覆蓋率漏接，非下架")
        lines.append("")
        lines.append("| 公司 | 職位 | 地區 | 104 更新日 | 連結 |")
        lines.append("|---|---|---|---|---|")
        for rec in scan.listed_not_scanned:
            lines.append(
                f"| {_trim(rec.company or '—', 30)} | {_trim(rec.title or '—', 50)} | "
                f"{_trim(rec.location or '—', 20)} | {rec.last_104_update or '—'} | "
                f"[104]({rec.url}) |"
            )
        lines.append("")

    # 5. 多排序視角（僅 --full 模式）
    if full and active_jobs:
        lines.append("---")
        lines.append("")
        lines.append(f"## 📋 全部活躍職缺 — 多排序視角（共 {len(active_jobs)} 筆）")
        lines.append("")

        # 5a. 依公司分組（表格）
        by_company: dict[str, list[dict]] = defaultdict(list)
        for j in active_jobs:
            by_company[j.get("company", "—")].append(j)
        lines.append(f"### 🏢 依公司分組（{len(by_company)} 家）")
        lines.append("")
        lines.append("| 公司 | 筆數 | AI | 產業 | 月薪下限 | 職位 | 地區 | 104 更新日 | 連結 | 徵才積極度 |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        # 公司排序：依該公司職缺數降序，同筆數則按字母
        sorted_companies = sorted(by_company.items(), key=lambda x: (-len(x[1]), x[0]))
        for company, jobs in sorted_companies:
            jobs_sorted = sorted(jobs, key=lambda j: j.get("salary_min") or 0, reverse=True)
            for i, j in enumerate(jobs_sorted):
                notes = j.get("notes") or {}
                lines.append(
                    f"| {_trim(company, 30) if i == 0 else ''} | "
                    f"{len(jobs) if i == 0 else ''} | "
                    f"{_ai_cell(j)} | "
                    f"{_trim(j.get('industry', '') or '—', 20)} | "
                    f"{_fmt_salary(j.get('salary_min'))} | "
                    f"{_trim(j.get('title', '—'), 50)} | "
                    f"{_trim(j.get('location', '') or '—', 20)} | "
                    f"{j.get('104_update_date', '—')} | "
                    f"[104]({j.get('url', '')}) | "
                    f"{_trim(str(notes.get('activeness', '') or '—'), 18)} |"
                )
        lines.append("")

        # 5b. 依地區分組（表格）
        by_loc: dict[str, list[dict]] = defaultdict(list)
        for j in active_jobs:
            loc = (j.get("location") or "未標示").strip() or "未標示"
            m = re.match(r"(.{0,3}[市縣])", loc)
            key = m.group(1) if m else loc
            by_loc[key].append(j)
        lines.append(f"### 🗺 依地區分組（{len(by_loc)} 區）")
        lines.append("")
        lines.append("| 地區 | 筆數 | AI | 月薪下限 | 公司 | 產業 | 職位 | 104 更新日 | 連結 | 徵才積極度 |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for loc, jobs in sorted(by_loc.items(), key=lambda x: -len(x[1])):
            jobs_sorted = sorted(jobs, key=lambda j: j.get("salary_min") or 0, reverse=True)
            for i, j in enumerate(jobs_sorted):
                notes = j.get("notes") or {}
                lines.append(
                    f"| {loc if i == 0 else ''} | "
                    f"{len(jobs) if i == 0 else ''} | "
                    f"{_ai_cell(j)} | "
                    f"{_fmt_salary(j.get('salary_min'))} | "
                    f"{_trim(j.get('company', '—'), 30)} | "
                    f"{_trim(j.get('industry', '') or '—', 20)} | "
                    f"{_trim(j.get('title', '—'), 50)} | "
                    f"{j.get('104_update_date', '—')} | "
                    f"[104]({j.get('url', '')}) | "
                    f"{_trim(str(notes.get('activeness', '') or '—'), 18)} |"
                )
        lines.append("")

        # 5c. 依 104 更新日降序（最近活躍）
        lines.append("### 🕒 依 104 更新日降序（最近活躍）")
        lines.append("")
        by_update = sorted(active_jobs, key=lambda j: j.get("104_update_date", ""), reverse=True)
        lines.append("| AI | 104 更新日 | 月薪下限 | 公司 | 產業 | 職位 | 地區 | 連結 | 徵才積極度 |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for j in by_update:
            notes = j.get("notes") or {}
            lines.append(
                f"| {_ai_cell(j)} | "
                f"{j.get('104_update_date', '—')} | {_fmt_salary(j.get('salary_min'))} | "
                f"{_trim(j.get('company', '—'), 30)} | "
                f"{_trim(j.get('industry', '') or '—', 20)} | "
                f"{_trim(j.get('title', '—'), 50)} | "
                f"{_trim(j.get('location', '') or '—', 20)} | "
                f"[104]({j.get('url', '')}) | "
                f"{_trim(str(notes.get('activeness', '') or '—'), 18)} |"
            )
        lines.append("")

        # 5d. 依薪資降序（不分組）
        lines.append("### 💵 依月薪降序（不分組）")
        lines.append("")
        with_salary = [j for j in active_jobs if j.get("salary_min") is not None]
        neg_salary = [j for j in active_jobs if j.get("salary_min") is None]
        by_salary = sorted(with_salary, key=lambda j: j.get("salary_min") or 0, reverse=True) + neg_salary
        lines.append("| AI | 月薪下限 | 公司 | 產業 | 職位 | 地區 | 連結 | 徵才積極度 |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for j in by_salary:
            notes = j.get("notes") or {}
            lines.append(
                f"| {_ai_cell(j)} | "
                f"{_fmt_salary(j.get('salary_min'))} | "
                f"{_trim(j.get('company', '—'), 30)} | "
                f"{_trim(j.get('industry', '') or '—', 20)} | "
                f"{_trim(j.get('title', '—'), 50)} | "
                f"{_trim(j.get('location', '') or '—', 20)} | "
                f"[104]({j.get('url', '')}) | "
                f"{_trim(str(notes.get('activeness', '') or '—'), 18)} |"
            )
        lines.append("")

    lines.append(f"_Generated at {today} by job-ops_")
    return "\n".join(lines) + "\n"


# ---------- HTML 渲染：Wallet 版 email（table + inline style，相容 Gmail）----------
#
# 只靠字級、字重、色彩與留白建立層次，不放任何圖示或表情符號；來源資料裡的
# emoji 與符號（104 的「🟢 徵才行為活躍」、職稱裡的「★」）一律在輸出前拿掉。
# 深色模式由 <style> 的 prefers-color-scheme 覆寫（Apple Mail 支援；Gmail 會忽略，
# 維持淺色）。

_PICTO_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍]")

_C = {
    "page": "#f2f2f7", "card": "#ffffff", "well": "#f5f5f7",
    "ink": "#1d1d1f", "ink2": "#6e6e73", "ink3": "#86868b", "ink4": "#aeaeb2",
    "hair": "#e5e5ea", "blue": "#0071e3", "live": "#248a3d",
}
_DOMAIN_NAME = {"physical_ai": "Physical AI", "llm": "LLM", "fde": "FDE"}
_DOMAIN_COLOR = {"physical_ai": "#bf5a00", "llm": "#0071e3", "fde": "#8944ab"}
_TIER_TEXT = {"strong": "AI 訊號強", "moderate": "AI 訊號中", "weak": "AI 訊號弱"}
_WEEKDAY = "一二三四五六日"
_FONT = ("-apple-system,BlinkMacSystemFont,'SF Pro Text','PingFang TC',"
         "'Helvetica Neue','Noto Sans TC',sans-serif")

_DARK_CSS = (
    "@media (prefers-color-scheme: dark){"
    ".jo-page{background:#000000!important}"
    ".jo-card{background:#1c1c1e!important}"
    ".jo-well{background:#2c2c2e!important}"
    ".jo-ink{color:#f5f5f7!important}"
    ".jo-ink2{color:#a1a1a6!important}"
    ".jo-hair{border-color:#38383a!important}"
    ".jo-list td{color:#a1a1a6!important;border-color:#38383a!important}"
    ".jo-list a,.jo-list b{color:#f5f5f7!important}"
    ".jo-list div{color:#a1a1a6!important}"
    "}"
)


def _plain(value: object) -> str:
    """拿掉 emoji／符號並收斂空白；回傳未跳脫的純文字。"""
    return re.sub(r"\s{2,}", " ", _PICTO_RE.sub("", str(value or ""))).strip()


def strip_pictographs(text: str) -> str:
    """拿掉 emoji 與符號，給 email 的 text/plain 段落用（markdown 日報檔本身不動）。"""
    return _PICTO_RE.sub("", text)


def _e(value: object) -> str:
    return html_lib.escape(_plain(value))


_CO_SUFFIX_RE = re.compile(r"股份有限公司|有限公司|[(（]股[)）]公司")
_CO_ORIGIN_RE = re.compile(r"^(?:[日美德英法韓港星荷瑞加澳陸台]商|外商)$")
# 黏在名字前面的外商註冊地（「英屬開曼群島商○○」）。不含「台商」：台商資訊這類是公司名本身
_CO_ATTACHED_ORIGIN_RE = re.compile(
    r"^(?:英屬開曼群島|英屬維京群島|開曼群島|英屬|薩摩亞|塞席爾|香港|新加坡|美|日|德|英|法|韓|荷|瑞士|加拿大|澳|陸)商(?=.)"
)
_CO_BRANCH_RE = re.compile(r"台灣分公司$")


def _display_company(name: str) -> str:
    """104 公司名的顯示形：取「品牌_法人名」的品牌，去掉公司型態字樣、外商註冊地前綴
    與「台灣分公司」。公司型態字樣常夾在中間（「富邦媒體科技股份有限公司(富邦momo)」），
    所以不只看字尾。

    拆不出東西時（只剩後綴、只有前綴）原樣回傳：顯示錯位的名字比冗長的原名更誤導。
    """
    raw = _plain(name)
    if not raw:
        return "—"
    parts = [p.strip() for p in raw.split("_") if p.strip()]
    if parts and _CO_ORIGIN_RE.match(parts[0]):
        parts = parts[1:]
    if not parts:
        return raw
    brand = _CO_ATTACHED_ORIGIN_RE.sub("", parts[0])
    brand = _CO_BRANCH_RE.sub("", brand)
    brand = _CO_SUFFIX_RE.sub("", brand).strip()
    return brand or raw


_RECENCY_RE = re.compile(r"^(\d+)\s*(分鐘前|小時前|天內)")
_RECENCY_HOURS = {"分鐘前": 1 / 60, "小時前": 1.0, "天內": 24.0}


def _recency_hours(text: str) -> float | None:
    """「8 小時前處理過履歷」→ 8；讀不出時間回 None（不猜）。"""
    m = _RECENCY_RE.match(text)
    if not m:
        return None
    return int(m.group(1)) * _RECENCY_HOURS[m.group(2)]


def _activity(j: dict) -> str:
    """招募動態：處理履歷與聯絡求職者取最近的一筆，同樣新時處理履歷優先；
    讀不出時間的排在讀得出的後面。兩者都沒有才用徵才積極度。"""
    notes = j.get("notes") or {}
    texts = [t for t in (_plain(notes.get("resume_info")), _plain(notes.get("reply_info")))
             if t and t != "—"]
    if texts:
        # sorted 是穩定排序：同分時維持 resume 在前
        return sorted(texts, key=lambda t: (_recency_hours(t) is None, _recency_hours(t) or 0))[0]
    activeness = _plain(notes.get("activeness"))
    return activeness if activeness and activeness != "—" else ""


def _salary_text(salary_min: int | None) -> str:
    return "面議" if salary_min is None else f"{salary_min:,} 起"


def _tier_text(j: dict) -> str:
    return _TIER_TEXT.get((j.get("ai_intent") or {}).get("tier", ""), "")


def _domain_html(keys: list[str], size: int = 12) -> str:
    return "　".join(
        f'<span style="color:{_DOMAIN_COLOR[k]};font-size:{size}px;font-weight:600">'
        f'{_DOMAIN_NAME[k]}</span>'
        for k in keys
    )


def _title_html(j: dict, style: str) -> str:
    title = _e(j.get("title")) or "—"
    url = j.get("url") or ""
    if not url:
        return f'<div class="jo-ink" style="{style}">{title}</div>'
    return (f'<a class="jo-ink" href="{html_lib.escape(url)}" '
            f'style="{style};text-decoration:none;display:block">{title}</a>')


def _table(inner: str, style: str = "", cls: str = "") -> str:
    cls_attr = f' class="{cls}"' if cls else ""
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'border="0"{cls_attr} style="border-collapse:separate;{style}">{inner}</table>')


def _card(inner: str, padding: str = "18px 20px") -> str:
    return (
        '<tr><td style="padding:0 0 10px">'
        + _table(f'<tr><td style="padding:{padding}">{inner}</td></tr>',
                 f"background:{_C['card']};border-radius:18px", "jo-card")
        + "</td></tr>"
    )


def _section_head(title: str, count: int | None = None) -> str:
    right = (f'<td align="right" style="font-size:14px;color:{_C["ink3"]}">{count} 個</td>'
             if count is not None else "")
    return (
        f'<tr data-section="{title}"><td style="padding:30px 6px 12px">'
        + _table(f'<tr><td class="jo-ink" style="font-size:22px;font-weight:700;'
                 f'letter-spacing:-.4px;color:{_C["ink"]}">{title}</td>{right}</tr>')
        + "</td></tr>"
    )


def _job_card(j: dict) -> str:
    keys = classify_focus_domains(j)
    left = (_domain_html(keys) if keys else
            f'<span style="font-size:12px;color:{_C["ink3"]}">{_e(j.get("industry"))}</span>')
    activity = _activity(j)
    act_color = _C["live"] if activity else _C["ink4"]
    salary = _salary_text(j.get("salary_min"))
    salary = salary if salary == "面議" else f"月薪 {salary}"
    inner = (
        _table(f'<tr><td>{left}</td><td align="right" style="font-size:12px;'
               f'color:{_C["ink3"]}">{_tier_text(j)}</td></tr>')
        + _title_html(j, f"margin-top:8px;font-size:17px;font-weight:600;line-height:1.35;"
                         f"color:{_C['ink']}")
        + f'<div class="jo-ink2" style="margin-top:3px;font-size:14px;color:{_C["ink2"]}">'
          f'{html_lib.escape(_display_company(j.get("company", "")))}</div>'
        + _table(
            f'<tr><td class="jo-ink2" style="padding:12px 0 0;font-size:13px;color:{_C["ink2"]}">'
            f'{_e(j.get("location")) or "—"}　{salary}</td>'
            f'<td align="right" style="padding:12px 0 0;font-size:13px;color:{act_color}">'
            f'{html_lib.escape(activity or "近期無招募動態")}</td></tr>',
            f"margin-top:16px;border-top:1px solid {_C['hair']}", "jo-hair")
    )
    return _card(inner, "18px 20px 14px")


def _list_card(rows: list[tuple[str, str, str, str]]) -> str:
    """分組清單：(上方小標 html, 職稱 html, 副標 html, 右欄 html)。

    清單列是 email 體積的大宗（真實資料一天約 160 列），inline style 只留必要的；
    深色模式改由 .jo-list 的後代選擇器覆寫，不在每個元素上掛 class。Gmail 超過
    102KB 會剪掉信尾。
    """
    body = ""
    for i, (label, title, sub, right) in enumerate(rows):
        border = "" if i == 0 else f"border-top:1px solid {_C['hair']};"
        label_html = f"{label}<br>" if label else ""
        body += (
            f'<tr><td style="{border}padding:13px 0 13px 16px">{label_html}{title}'
            f'<div style="font-size:13px;color:{_C["ink2"]}">{sub}</div></td>'
            f'<td align="right" valign="top" style="{border}padding:13px 16px;'
            f'font-size:14px;color:{_C["ink2"]}">{right}</td></tr>'
        )
    return ('<tr><td style="padding:0 0 10px">'
            + _table(body, f"background:{_C['card']};border-radius:18px", "jo-card jo-list")
            + "</td></tr>")


def _list_row(j: dict, right: str, with_domain: bool = False) -> tuple[str, str, str, str]:
    keys = classify_focus_domains(j) if with_domain else []
    title = _e(j.get("title")) or "—"
    url = j.get("url") or ""
    style = f"font-size:15px;font-weight:500;color:{_C['ink']}"
    title_html = (f'<a href="{html_lib.escape(url)}" style="{style};text-decoration:none">{title}</a>'
                  if url else f'<span style="{style}">{title}</span>')
    sub = f'{html_lib.escape(_display_company(j.get("company", "")))}　{_e(j.get("location"))}'
    return (_domain_html(keys, 11) if keys else "", title_html, sub, right)


def _salary_right(j: dict) -> str:
    sal = j.get("salary_min")
    if sal is None:
        return "面議"
    return f'<b style="color:{_C["ink"]}">{sal:,} 起</b>'


def _featured(scan: ScanResult) -> dict | None:
    """今日焦點：今天新上架、屬於重點領域者之中 priority 最高的一筆。"""
    cands = [j for j in scan.new_items if classify_focus_domains(j)]
    if not cands:
        return None
    return max(cands, key=_ai_score)


def _featured_card(j: dict) -> str:
    keys = classify_focus_domains(j)
    names = "／".join(_DOMAIN_NAME[k] for k in keys)
    activity = _activity(j)
    reason = f"今天新上架的 {names} 職缺。" + (f"招募動態：{activity}。" if activity else "")
    facts = [
        (_e(j.get("location")) or "—", "地區"),
        (_salary_text(j.get("salary_min")), "月薪"),
        (_domain_html(keys, 15), "領域"),
        (_tier_text(j).replace("AI 訊號", "") or "—", "AI 訊號"),
    ]
    # 2×2：手機寬度下四欄並排會把「台北市信義區」「60,000 起」折成兩行
    cells = [
        f'<td width="50%" valign="top" style="padding:14px 16px">'
        f'<div class="jo-ink" style="font-size:15px;font-weight:600;color:{_C["ink"]}">{v}</div>'
        f'<div style="margin-top:2px;font-size:12px;color:{_C["ink3"]}">{k}</div></td>'
        for v, k in facts
    ]
    fact_cells = f"{cells[0]}{cells[1]}</tr><tr>{cells[2]}{cells[3]}"
    url = j.get("url") or ""
    button = (
        f'<a href="{html_lib.escape(url)}" style="display:inline-block;background:{_C["blue"]};'
        f'color:#ffffff;font-size:15px;font-weight:500;padding:11px 24px;border-radius:980px;'
        f'text-decoration:none">在 104 查看</a>' if url else ""
    )
    inner = (
        f'<div style="font-size:12px;font-weight:600;letter-spacing:1px;color:{_C["ink3"]}">今日焦點</div>'
        + _title_html(j, f"margin-top:12px;font-size:24px;font-weight:700;line-height:1.25;"
                         f"letter-spacing:-.4px;color:{_C['ink']}")
        + f'<div class="jo-ink2" style="margin-top:6px;font-size:15px;color:{_C["ink2"]}">'
          f'{html_lib.escape(_display_company(j.get("company", "")))}</div>'
        + f'<div class="jo-ink" style="margin:16px 0 18px;font-size:15px;line-height:1.55;'
          f'color:{_C["ink"]}">{html_lib.escape(reason)}</div>'
        + _table(f"<tr>{fact_cells}</tr>",
                 f"background:{_C['well']};border-radius:14px;margin-bottom:20px", "jo-well")
        + button
    )
    return (f'<tr data-section="今日焦點"><td style="padding:0">'
            + _table(_card(inner, "24px 22px 24px")) + "</td></tr>")


def _summary(scan: ScanResult) -> str:
    focus = _focus_rows(scan)
    n_ai = sum(1 for j in scan.new_items if _is_ai_pm(j))

    def stat(key: str, value: int) -> str:
        return f'<span data-stat="{key}">{value}</span>'

    side = "<br>".join(
        f'{label}　<b class="jo-ink" style="color:{_C["ink"]}">{stat(key, value)}</b>'
        for label, key, value in (
            ("強訊號 AI PM", "ai_pm", n_ai),
            ("104 更新", "refreshed", len(scan.refreshed)),
            ("今日掃描", "total", scan.total_today()),
        )
    )
    dom_cells = "".join(
        f'<td width="33%" valign="top" class="jo-hair" style="padding:16px 0 0;'
        f'border-top:1px solid {_C["hair"]}">'
        f'<div style="font-size:26px;font-weight:600;letter-spacing:-.5px;color:{_DOMAIN_COLOR[k]}">'
        f'{stat(k, sum(1 for _, keys, _j in focus if k in keys))}</div>'
        f'<div style="font-size:12px;color:{_C["ink3"]}">{_DOMAIN_NAME[k]} 在架</div></td>'
        for k in ("llm", "physical_ai", "fde")
    )
    inner = (
        _table(
            f'<tr><td valign="bottom" style="padding-bottom:20px">'
            f'<div class="jo-ink" style="font-size:64px;font-weight:700;line-height:1;'
            f'letter-spacing:-2.5px;color:{_C["ink"]}">{stat("new", len(scan.new_items))}</div>'
            f'<div class="jo-ink2" style="margin-top:8px;font-size:15px;color:{_C["ink2"]}">個新上架職缺</div></td>'
            f'<td align="right" valign="bottom" class="jo-ink2" style="padding-bottom:20px;font-size:14px;'
            f'line-height:1.9;color:{_C["ink2"]}">{side}</td></tr>')
        + _table(f"<tr>{dom_cells}</tr>")
    )
    return (f'<tr data-section="摘要"><td style="padding:0">'
            + _table(_card(inner, "24px 22px 20px")) + "</td></tr>")


def render_html(scan: ScanResult, today: str, *, full: bool = False) -> str:
    """Wallet 版日報 email。區塊：摘要 → 今日焦點 → 新上架 → 重點領域今日更新 →
    重點領域仍在架 → 薪資變動 → 104 更新（非重點領域）→ 在架未掃到 →（full）全部在架。

    非重點領域的仍在架職缺不逐筆列出（數量大且無變化），full 模式才列。
    """
    d = date.fromisoformat(today)
    date_text = f"{d.month} 月 {d.day} 日 星期{_WEEKDAY[d.weekday()]}"
    featured = _featured(scan)
    rows: list[str] = []

    rows.append(
        f'<tr><td style="padding:0 6px 22px">'
        f'<div style="font-size:13px;font-weight:600;color:{_C["ink3"]}">{date_text}</div>'
        f'<div class="jo-ink" style="margin-top:2px;font-size:32px;font-weight:700;letter-spacing:-.8px;'
        f'color:{_C["ink"]}">今日職缺</div></td></tr>'
    )
    rows.append(_summary(scan))
    if featured is not None:
        rows.append('<tr><td style="height:20px;line-height:20px;font-size:0">&nbsp;</td></tr>')
        rows.append(_featured_card(featured))

    # 新上架：排序同 markdown 日報（有薪資者依 priority、月薪；面議者依 priority）
    paid = sorted((j for j in scan.new_items if j.get("salary_min") is not None),
                  key=lambda j: (-_ai_score(j), -(j.get("salary_min") or 0)))
    negotiable = sorted((j for j in scan.new_items if j.get("salary_min") is None),
                        key=lambda j: -_ai_score(j))
    new_jobs = [j for j in paid + negotiable if j is not featured]
    rows.append(_section_head("新上架", len(new_jobs)))
    if new_jobs:
        rows.extend(_job_card(j) for j in new_jobs)
    else:
        rows.append(_card(f'<div style="font-size:15px;color:{_C["ink3"]}">'
                          + ("今日無其他新上架職缺" if featured is not None else "今日無新上架職缺")
                          + "</div>"))

    by_priority = lambda js: sorted(js, key=lambda j: -_ai_score(j))  # noqa: E731
    focus_refreshed = by_priority(j for j in scan.refreshed if classify_focus_domains(j))
    if focus_refreshed:
        rows.append(_section_head("重點領域今日更新", len(focus_refreshed)))
        rows.append(_list_card([_list_row(j, _salary_right(j), True) for j in focus_refreshed]))

    focus_still = by_priority(j for j in scan.still_listed if classify_focus_domains(j))
    if focus_still:
        rows.append(_section_head("重點領域仍在架", len(focus_still)))
        rows.append(_list_card([_list_row(j, _salary_right(j), True) for j in focus_still]))

    if scan.salary_changed:
        rows.append(_section_head("薪資變動", len(scan.salary_changed)))
        rows.append(_list_card([
            _list_row(j, f"{_salary_text(j.get('prev_salary_min'))} 改為 "
                         f"{_salary_text(j.get('salary_min'))}")
            for j in scan.salary_changed
        ]))

    plain_refreshed = sorted(
        (j for j in scan.refreshed if not classify_focus_domains(j)),
        key=lambda j: (_ai_score(j), j.get("104_update_date", "")), reverse=True,
    )
    if plain_refreshed:
        rows.append(_section_head("104 更新", len(plain_refreshed)))
        rows.append(_list_card([_list_row(j, _salary_right(j)) for j in plain_refreshed]))

    if scan.listed_not_scanned:
        rows.append(_section_head("在架未掃到", len(scan.listed_not_scanned)))
        rows.append(_list_card([
            _list_row({"url": r.url, "title": r.title, "company": r.company,
                       "location": r.location}, _e(r.last_104_update) or "—")
            for r in scan.listed_not_scanned
        ]))

    if full:
        active = sorted(scan.new_items + scan.refreshed + scan.still_listed,
                        key=lambda j: j.get("104_update_date", ""), reverse=True)
        if active:
            rows.append(_section_head("全部在架", len(active)))
            rows.append(_list_card([_list_row(j, _e(j.get("104_update_date")) or "—", True)
                                    for j in active]))

    rows.append(
        f'<tr><td style="padding:24px 6px 8px;font-size:12px;line-height:1.6;color:{_C["ink3"]}">'
        "job-ops 每日寄送。所有職缺皆通過 AI 或軟體／SaaS 領域門檻，月薪為 104 標示的下限。"
        "</td></tr>"
    )

    n_new = len(scan.new_items)
    preheader = f"{n_new} 個新上架職缺，重點領域在架 {len(_focus_rows(scan))} 個"
    return (
        '<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        '<meta name="supported-color-schemes" content="light dark">'
        f"<title>職缺日報 {today}</title><style>{_DARK_CSS}</style></head>"
        f'<body class="jo-page" style="margin:0;padding:0;background:{_C["page"]};'
        f'font-family:{_FONT};-webkit-font-smoothing:antialiased">'
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0">{html_lib.escape(preheader)}</div>'
        + _table(
            '<tr><td align="center" style="padding:32px 12px 40px">'
            + _table("".join(rows), "max-width:600px;margin:0 auto")
            + "</td></tr>",
            f"background:{_C['page']}", "jo-page")
        + "</body></html>"
    )


def build_subject(scan: ScanResult, today: str) -> str:
    parts = [f"{len(scan.new_items)} 筆新上架"]
    new_focus = _count_new_focus(scan)
    if new_focus:
        parts.append(f"重點領域 {new_focus} 筆")
    if scan.refreshed:
        parts.append(f"{len(scan.refreshed)} 筆 104 更新")
    if scan.salary_changed:
        parts.append(f"{len(scan.salary_changed)} 筆薪資變動")
    return f"[job-ops] {today} AI 職缺日報：" + "，".join(parts)
