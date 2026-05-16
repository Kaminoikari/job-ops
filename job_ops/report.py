"""Daily report: markdown + Gmail-safe inline-styled HTML."""
from __future__ import annotations

import re
from collections import defaultdict

import markdown as md_lib

from .history import Record, ScanResult
from .tracker import Evaluation


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
    "none": "—",
}


def _ai_cell(j: dict) -> str:
    """日報表格的 AI 意圖欄位。"""
    intent = j.get("ai_intent") or {}
    return _AI_TIER_LABEL.get(intent.get("tier", ""), "—")


def _is_ai_pm(j: dict) -> bool:
    return bool((j.get("ai_intent") or {}).get("is_ai_pm"))


def _score_emoji(score: float) -> str:
    if score >= 4.0:
        return "🟢"
    if score >= 3.5:
        return "🟡"
    if score >= 3.0:
        return "🟠"
    return "🔴"


def _fmt_score(url: str, evaluations: dict[str, Evaluation] | None) -> str:
    """回傳評估分數欄位（含 emoji + 分數），未評估顯示 —。"""
    if not evaluations:
        return "—"
    ev = evaluations.get(url)
    if ev is None or ev.global_score <= 0:
        return "—"
    return f"{_score_emoji(ev.global_score)} {ev.global_score:.1f}"


def _job_row(j: dict, evaluations: dict[str, Evaluation] | None = None) -> str:
    salary = _fmt_salary(j.get("salary_min"))
    company = _trim(j.get("company", "—"), 30)
    title = _trim(j.get("title", "—"), 50)
    industry = _trim(j.get("industry", "") or "—", 20)
    loc = _trim(j.get("location", "") or "—", 20)
    url = j.get("url", "")
    link = f"[104]({url})" if url else "—"
    score = _fmt_score(url, evaluations)
    ai = _ai_cell(j)
    notes = j.get("notes") or {}
    activeness = _trim(str(notes.get("activeness", "") or "—"), 20)
    reply = _trim(str(notes.get("reply_info", "") or "—"), 18)
    resume = _trim(str(notes.get("resume_info", "") or "—"), 18)
    return (
        f"| {score} | {ai} | {salary} | {company} | {industry} | {title} | {loc} | {link} | "
        f"{activeness} | {reply} | {resume} |"
    )


def _job_row_header() -> list[str]:
    return [
        "| 評分 | AI | 月薪下限 | 公司 | 產業 | 職位 | 地區 | 連結 | 徵才積極度 | 回覆求職者 | 聯絡應徵者 |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]


def build_markdown(
    scan: ScanResult,
    today: str,
    *,
    full: bool = False,
    evaluations: dict[str, Evaluation] | None = None,
) -> str:
    """生成日報 markdown。

    full=False (預設、日常模式): 只顯示變化（新上架／更新／薪資變動／下架）
    full=True: 加上「全部活躍職缺 — 多排序視角」與「詳細資訊（今日新上架）」附錄
    evaluations: { url → Evaluation } map（從 tracker.tsv 載入）；非 None 時表格會加入「評分」欄
    """
    lines: list[str] = []
    new_paid = [j for j in scan.new_items if j.get("salary_min") is not None]
    new_negotiable = [j for j in scan.new_items if j.get("salary_min") is None]
    # 排序：AI PM 職缺優先，其次月薪降序
    new_paid.sort(key=lambda j: (not _is_ai_pm(j), -(j.get("salary_min") or 0)))
    new_negotiable.sort(key=lambda j: not _is_ai_pm(j))
    new_ai_count = sum(1 for j in scan.new_items if _is_ai_pm(j))

    active_jobs = scan.new_items + scan.refreshed + scan.still_listed
    evaluated_active = (
        sum(1 for j in active_jobs if evaluations and j.get("url") in evaluations)
        if evaluations else 0
    )

    # 1. 摘要
    lines.append(f"# 📋 104 職缺日報 — {today}")
    lines.append("")
    lines.append("## 📊 摘要")
    lines.append("")
    lines.append(f"- 今日總抓取：**{scan.total_today()}** 筆")
    lines.append(f"- 🆕 今日新上架：**{len(scan.new_items)}** 筆（含面議 {len(new_negotiable)} 筆）")
    lines.append(f"- 🤖 其中 AI PM 職缺：**{new_ai_count}** 筆（JD 意圖偵測判定，已排前）")
    lines.append(f"- 🔄 104 更新日期變動：**{len(scan.refreshed)}** 筆")
    lines.append(f"- 💰 薪資變動：**{len(scan.salary_changed)}** 筆")
    lines.append(f"- 📌 仍在架（無變動）：{len(scan.still_listed)} 筆")
    lines.append(f"- 💀 已下架：{len(scan.expired)} 筆")
    if evaluations is not None:
        lines.append(
            f"- 🎯 已評估：**{evaluated_active} / {len(active_jobs)}** 筆"
            f"（用 `/eval {{URL}}` 對未評估職缺觸發評估）"
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
            lines.append(_job_row(j, evaluations))
        if new_negotiable:
            lines.append("| **— 以下為面議 —** | | | | | | | | | | |")
            for j in new_negotiable:
                lines.append(_job_row(j, evaluations))
        lines.append("")

    # 3. 104 更新日期變動
    if scan.refreshed:
        lines.append(f"## 🔄 104 更新日期變動（公司主動推，{len(scan.refreshed)} 筆）")
        lines.append("")
        lines.append("> 這些職缺已上架一段時間，但公司今天更新了 104 上的職缺日期")
        lines.append("")
        refreshed_sorted = sorted(scan.refreshed, key=lambda j: j.get("104_update_date", ""), reverse=True)
        lines.append("| 評分 | 更新日 | 月薪下限 | 公司 | 產業 | 職位 | 地區 | 連結 |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for j in refreshed_sorted:
            lines.append(
                f"| {_fmt_score(j.get('url', ''), evaluations)} | "
                f"{j.get('104_update_date', '—')} | {_fmt_salary(j.get('salary_min'))} | "
                f"{_trim(j.get('company', '—'), 30)} | {_trim(j.get('industry', '') or '—', 20)} | "
                f"{_trim(j.get('title', '—'), 50)} | "
                f"{_trim(j.get('location', '') or '—', 20)} | [104]({j.get('url', '')}) |"
            )
        lines.append("")

    # 4. 薪資變動
    if scan.salary_changed:
        lines.append(f"## 💰 薪資變動警示（{len(scan.salary_changed)} 筆）")
        lines.append("")
        lines.append("| 評分 | 變化 | 原薪資 | 新薪資 | 公司 | 職位 | 連結 |")
        lines.append("|---|---|---|---|---|---|---|")
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
                f"| {_fmt_score(j.get('url', ''), evaluations)} | "
                f"{arrow} | {_fmt_salary(prev)} | {_fmt_salary(cur)} | "
                f"{_trim(j.get('company', '—'), 30)} | {_trim(j.get('title', '—'), 50)} | "
                f"[104]({j.get('url', '')}) |"
            )
        lines.append("")

    # 5. 已下架
    if scan.expired:
        lines.append(f"## 💀 已下架（{len(scan.expired)} 筆）")
        lines.append("")
        for rec in scan.expired[:30]:
            lines.append(f"- {rec.company} — {rec.title}（上次見 {rec.last_seen}）[104]({rec.url})")
        if len(scan.expired) > 30:
            lines.append(f"- … 另有 {len(scan.expired) - 30} 筆未列出")
        lines.append("")

    # 6. 多排序視角（僅 --full 模式）
    if full and active_jobs:
        lines.append("---")
        lines.append("")
        lines.append(f"## 📋 全部活躍職缺 — 多排序視角（共 {len(active_jobs)} 筆）")
        lines.append("")

        # 6a. 依公司分組（表格）
        by_company: dict[str, list[dict]] = defaultdict(list)
        for j in active_jobs:
            by_company[j.get("company", "—")].append(j)
        lines.append(f"### 🏢 依公司分組（{len(by_company)} 家）")
        lines.append("")
        lines.append("| 公司 | 筆數 | 評分 | 產業 | 月薪下限 | 職位 | 地區 | 104 更新日 | 連結 | 徵才積極度 |")
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
                    f"{_fmt_score(j.get('url', ''), evaluations)} | "
                    f"{_trim(j.get('industry', '') or '—', 20)} | "
                    f"{_fmt_salary(j.get('salary_min'))} | "
                    f"{_trim(j.get('title', '—'), 50)} | "
                    f"{_trim(j.get('location', '') or '—', 20)} | "
                    f"{j.get('104_update_date', '—')} | "
                    f"[104]({j.get('url', '')}) | "
                    f"{_trim(str(notes.get('activeness', '') or '—'), 18)} |"
                )
        lines.append("")

        # 6b. 依地區分組（表格）
        by_loc: dict[str, list[dict]] = defaultdict(list)
        for j in active_jobs:
            loc = (j.get("location") or "未標示").strip() or "未標示"
            m = re.match(r"(.{0,3}[市縣])", loc)
            key = m.group(1) if m else loc
            by_loc[key].append(j)
        lines.append(f"### 🗺 依地區分組（{len(by_loc)} 區）")
        lines.append("")
        lines.append("| 地區 | 筆數 | 評分 | 月薪下限 | 公司 | 產業 | 職位 | 104 更新日 | 連結 | 徵才積極度 |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for loc, jobs in sorted(by_loc.items(), key=lambda x: -len(x[1])):
            jobs_sorted = sorted(jobs, key=lambda j: j.get("salary_min") or 0, reverse=True)
            for i, j in enumerate(jobs_sorted):
                notes = j.get("notes") or {}
                lines.append(
                    f"| {loc if i == 0 else ''} | "
                    f"{len(jobs) if i == 0 else ''} | "
                    f"{_fmt_score(j.get('url', ''), evaluations)} | "
                    f"{_fmt_salary(j.get('salary_min'))} | "
                    f"{_trim(j.get('company', '—'), 30)} | "
                    f"{_trim(j.get('industry', '') or '—', 20)} | "
                    f"{_trim(j.get('title', '—'), 50)} | "
                    f"{j.get('104_update_date', '—')} | "
                    f"[104]({j.get('url', '')}) | "
                    f"{_trim(str(notes.get('activeness', '') or '—'), 18)} |"
                )
        lines.append("")

        # 6c. 依 104 更新日降序（最近活躍）
        lines.append("### 🕒 依 104 更新日降序（最近活躍）")
        lines.append("")
        by_update = sorted(active_jobs, key=lambda j: j.get("104_update_date", ""), reverse=True)
        lines.append("| 評分 | 104 更新日 | 月薪下限 | 公司 | 產業 | 職位 | 地區 | 連結 | 徵才積極度 |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for j in by_update:
            notes = j.get("notes") or {}
            lines.append(
                f"| {_fmt_score(j.get('url', ''), evaluations)} | "
                f"{j.get('104_update_date', '—')} | {_fmt_salary(j.get('salary_min'))} | "
                f"{_trim(j.get('company', '—'), 30)} | "
                f"{_trim(j.get('industry', '') or '—', 20)} | "
                f"{_trim(j.get('title', '—'), 50)} | "
                f"{_trim(j.get('location', '') or '—', 20)} | "
                f"[104]({j.get('url', '')}) | "
                f"{_trim(str(notes.get('activeness', '') or '—'), 18)} |"
            )
        lines.append("")

        # 6d. 依薪資降序（不分組）
        lines.append("### 💵 依月薪降序（不分組）")
        lines.append("")
        with_salary = [j for j in active_jobs if j.get("salary_min") is not None]
        neg_salary = [j for j in active_jobs if j.get("salary_min") is None]
        by_salary = sorted(with_salary, key=lambda j: j.get("salary_min") or 0, reverse=True) + neg_salary
        lines.append("| 評分 | 月薪下限 | 公司 | 產業 | 職位 | 地區 | 連結 | 徵才積極度 |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for j in by_salary:
            notes = j.get("notes") or {}
            lines.append(
                f"| {_fmt_score(j.get('url', ''), evaluations)} | "
                f"{_fmt_salary(j.get('salary_min'))} | "
                f"{_trim(j.get('company', '—'), 30)} | "
                f"{_trim(j.get('industry', '') or '—', 20)} | "
                f"{_trim(j.get('title', '—'), 50)} | "
                f"{_trim(j.get('location', '') or '—', 20)} | "
                f"[104]({j.get('url', '')}) | "
                f"{_trim(str(notes.get('activeness', '') or '—'), 18)} |"
            )
        lines.append("")

    # 7. 詳細 JD 附錄 — 只列「今日新上架」，無論 full 與否都顯示
    #    （新上架通常 < 10 筆，附錄不至於太肥；refreshed / still_listed 不附 JD）
    if scan.new_items:
        lines.append("---")
        lines.append("")
        lines.append("## 📂 詳細資訊（今日新上架）")
        lines.append("")
        for j in new_paid + new_negotiable:
            lines.append(f"### {j.get('company', '—')} — {j.get('title', '—')}")
            lines.append("")
            url = j.get("url", "")
            ev = evaluations.get(url) if evaluations else None
            if ev and ev.global_score > 0:
                lines.append(
                    f"- **評估**：{_score_emoji(ev.global_score)} **{ev.global_score:.2f}** / 5"
                    f" — [{ev.report_num or '報告'}]({ev.report_path or '#'})"
                    f" ｜ legitimacy: {ev.legitimacy or '—'}"
                )
            else:
                lines.append("- **評估**：未評估（用 `/eval` 觸發）")
            intent = j.get("ai_intent") or {}
            if intent:
                ai_label = _AI_TIER_LABEL.get(intent.get("tier", ""), "—")
                matched = intent.get("matched") or []
                if matched:
                    lines.append(
                        f"- **AI 意圖**：{ai_label}（score {intent.get('score', 0)}）"
                        f" — 命中訊號：{', '.join(matched[:8])}"
                    )
                else:
                    lines.append(f"- **AI 意圖**：{ai_label}")
            lines.append(f"- **薪資**：{j.get('salary_raw', '—') or '—'}")
            lines.append(f"- **地區**：{j.get('location', '—') or '—'}")
            if j.get("address"):
                lines.append(f"- **地址**：{j.get('address')}")
            if j.get("industry"):
                lines.append(f"- **產業**：{j.get('industry')}")
            notes = j.get("notes") or {}
            if notes.get("activeness"):
                lines.append(f"- **徵才積極度**：{notes['activeness']}")
            if notes.get("reply_info"):
                lines.append(f"- **回覆資訊**：{notes['reply_info']}")
            lines.append(f"- **連結**：{j.get('url', '')}")
            if j.get("benefits"):
                lines.append("")
                lines.append("**公司福利**：")
                lines.append("")
                lines.append("> " + j["benefits"].replace("\n", "\n> "))
            jd = j.get("jd", "")
            if jd:
                lines.append("")
                lines.append("**Job Description**：")
                lines.append("")
                # 限制 JD 長度
                jd_trim = jd if len(jd) < 1500 else jd[:1500] + "…（截斷）"
                lines.append("> " + jd_trim.replace("\n", "\n> "))
            lines.append("")
            lines.append("---")
            lines.append("")

    lines.append(f"_Generated at {today} by job-ops_")
    return "\n".join(lines) + "\n"


# ---------- HTML 渲染（inline styles，相容 Gmail）----------


def render_html(md_text: str, today: str) -> str:
    body = md_lib.markdown(md_text, extensions=["tables", "fenced_code"])
    styled = (
        body
        .replace("<table>", '<table style="border-collapse:collapse;width:100%;font-size:13px;margin:8px 0">')
        .replace("<th>", '<th style="border:1px solid #ddd;padding:6px 10px;background:#f5f5f5;text-align:left;font-weight:600">')
        .replace("<td>", '<td style="border:1px solid #ddd;padding:6px 10px;vertical-align:top">')
        .replace("<a ", '<a style="color:#2563eb;text-decoration:underline" ')
        .replace("<h1>", '<h1 style="font-size:24px;margin:16px 0 8px">')
        .replace("<h2>", '<h2 style="font-size:20px;margin:24px 0 10px;padding-bottom:4px;border-bottom:1px solid #eee">')
        .replace("<h3>", '<h3 style="font-size:16px;margin:20px 0 8px;color:#0f172a">')
        .replace("<h4>", '<h4 style="font-size:14px;margin:14px 0 6px;color:#374151">')
        .replace("<li>", '<li style="margin:2px 0">')
        .replace("<blockquote>", '<blockquote style="margin:8px 0;padding:8px 12px;border-left:3px solid #cbd5e1;background:#f8fafc;color:#475569">')
        .replace("<hr>", '<hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0">')
        .replace("<code>", '<code style="background:#f1f5f9;padding:1px 4px;border-radius:3px;font-size:13px">')
    )
    return (
        '<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="UTF-8">'
        f'<title>104 職缺日報 · {today}</title></head>'
        '<body style="font-family:-apple-system,BlinkMacSystemFont,\'PingFang TC\','
        '\'Noto Sans TC\',\'Helvetica Neue\',sans-serif;font-size:15px;line-height:1.6;'
        'color:#1a1a1a;background:#fff;max-width:900px;margin:0 auto;padding:24px">'
        f'{styled}'
        '</body></html>'
    )


def build_subject(scan: ScanResult, today: str) -> str:
    parts = [f"{len(scan.new_items)} 筆新上架"]
    if scan.refreshed:
        parts.append(f"{len(scan.refreshed)} 筆 104 更新")
    if scan.salary_changed:
        parts.append(f"{len(scan.salary_changed)} 筆薪資變動")
    if scan.expired:
        parts.append(f"{len(scan.expired)} 筆下架")
    return f"[job-ops] {today} 日報：" + "，".join(parts)
