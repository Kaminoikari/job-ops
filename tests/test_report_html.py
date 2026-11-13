"""render_html 測試：Wallet 版日報 email（不含任何圖示與表情符號）。"""
from __future__ import annotations

import re

import pytest

from job_ops.history import Record, ScanResult
from job_ops.report import _display_company, build_subject, render_html

_TODAY = "2026-11-13"

# 涵蓋 emoji、雜項符號（★ ✓）與變體選擇子；這些都算使用者不要的圖示
_PICTO = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️]")


def _job(url, **kw):
    base = {
        "url": url, "company": "宇見智能科技股份有限公司", "title": "Technical Product Manager",
        "salary_min": None, "industry": "電腦軟體服務業", "location": "台北市南港區",
        "notes": {}, "jd": "負責 SaaS 平台產品規劃", "104_update_date": "2026/11/13",
        "ai_intent": {"is_ai_pm": True, "tier": "strong", "score": 8.0, "priority": 8.0},
    }
    base.update(kw)
    return base


def _llm(url, priority=8.0, **kw):
    """職稱命中 LLM → 重點領域 llm。"""
    kw.setdefault("title", "LLM 產品經理")
    return _job(url, ai_intent={"is_ai_pm": True, "tier": "strong", "score": priority,
                                "priority": priority}, **kw)


def _rec(url, company="宇見智能科技", title="舊 PM 職缺"):
    return Record(url=url, first_seen="2026-10-01", last_seen="2026-11-12",
                  last_104_update="2026/11/10", company=company, title=title,
                  salary_raw="面議", salary_min="", location="台北市", address="",
                  status="New", salary_history="", notes="{}")


def _scan(**kw):
    base = dict(today=_TODAY, new_items=[], refreshed=[], salary_changed=[],
                still_listed=[], expired=[], listed_not_scanned=[])
    base.update(kw)
    return ScanResult(**base)


def _section(html: str, title: str) -> str:
    """取出某個區塊標題之後、下一個區塊標題之前的 HTML。"""
    start = html.index(f'data-section="{title}"')
    nxt = html.find('data-section="', start + 1)
    return html[start: nxt if nxt != -1 else len(html)]


# ---------- 不含圖示與表情符號 ----------


def test_no_emoji_or_symbols_even_when_source_data_has_them():
    scan = _scan(
        new_items=[_llm("https://x/n1", title="AI 產品經理 ★搬遷★",
                        notes={"activeness": "🟢 徵才行為活躍"})],
        refreshed=[_job("https://x/r1", notes={"activeness": "🟢 徵才行為活躍"})],
        salary_changed=[_job("https://x/s1", salary_min=70000, prev_salary_min=60000)],
        still_listed=[_llm("https://x/st1")],
        listed_not_scanned=[_rec("https://x/l1")],
    )
    html = render_html(scan, _TODAY, full=True)
    found = sorted(set(_PICTO.findall(html)))
    assert found == [], found
    assert "徵才行為活躍" in html  # 去掉圖示，文字保留


def test_subject_has_no_emoji():
    scan = _scan(new_items=[_llm("https://x/n1")], refreshed=[_job("https://x/r1")])
    subject = build_subject(scan, _TODAY)
    assert _PICTO.findall(subject) == []
    assert "重點領域 1 筆" in subject


# ---------- 今日焦點 ----------


def test_featured_is_highest_priority_new_focus_job_and_not_repeated():
    low = _llm("https://x/low", priority=5.0, title="LLM 產品經理 低")
    high = _llm("https://x/high", priority=9.0, title="LLM 產品經理 高")
    plain = _job("https://x/plain")
    html = render_html(_scan(new_items=[low, plain, high]), _TODAY)
    featured = _section(html, "今日焦點")
    assert "https://x/high" in featured and "https://x/low" not in featured
    new = _section(html, "新上架")
    assert "https://x/high" not in new
    assert "https://x/low" in new and "https://x/plain" in new


def test_featured_reason_states_domain_and_activity():
    job = _llm("https://x/f", notes={"resume_info": "16 小時前處理過履歷"})
    featured = _section(render_html(_scan(new_items=[job]), _TODAY), "今日焦點")
    assert "今天新上架的 LLM 職缺" in featured
    assert "16 小時前處理過履歷" in featured


def test_no_featured_when_no_new_focus_job():
    # 重點領域職缺只在仍在架：不是今天新上架，不當焦點
    html = render_html(_scan(new_items=[_job("https://x/plain")],
                             still_listed=[_llm("https://x/st")]), _TODAY)
    assert 'data-section="今日焦點"' not in html


# ---------- 各區塊的歸屬 ----------


def test_refreshed_split_between_focus_and_plain_sections():
    scan = _scan(refreshed=[_llm("https://x/rf"), _job("https://x/rp")],
                 still_listed=[_llm("https://x/sf"), _job("https://x/sp")])
    html = render_html(scan, _TODAY)
    focus_upd = _section(html, "重點領域今日更新")
    assert "https://x/rf" in focus_upd and "https://x/rp" not in focus_upd
    plain_upd = _section(html, "104 更新")
    assert "https://x/rp" in plain_upd and "https://x/rf" not in plain_upd
    still = _section(html, "重點領域仍在架")
    assert "https://x/sf" in still and "https://x/sp" not in still
    # 非重點領域的仍在架職缺不在 email 裡逐筆列出
    assert "https://x/sp" not in html


def test_new_items_ordered_by_priority():
    a = _job("https://x/a", ai_intent={"tier": "weak", "score": 2.0, "priority": 2.0})
    b = _job("https://x/b", ai_intent={"tier": "strong", "score": 9.0, "priority": 9.0})
    c = _job("https://x/c", ai_intent={"tier": "moderate", "score": 5.0, "priority": 5.0})
    new = _section(render_html(_scan(new_items=[a, b, c]), _TODAY), "新上架")
    assert new.index("https://x/b") < new.index("https://x/c") < new.index("https://x/a")


def test_empty_new_items_says_so():
    new = _section(render_html(_scan(), _TODAY), "新上架")
    assert "今日無新上架職缺" in new


def test_salary_change_shows_before_and_after():
    j = _job("https://x/s", salary_min=70000, prev_salary_min=60000)
    sec = _section(render_html(_scan(salary_changed=[j]), _TODAY), "薪資變動")
    assert "60,000 起 改為 70,000 起" in sec


def test_salary_change_to_negotiable():
    j = _job("https://x/s", salary_min=None, prev_salary_min=60000)
    sec = _section(render_html(_scan(salary_changed=[j]), _TODAY), "薪資變動")
    assert "60,000 起 改為 面議" in sec


def test_listed_not_scanned_section():
    html = render_html(_scan(listed_not_scanned=[_rec("https://x/l1")]), _TODAY)
    assert "https://x/l1" in _section(html, "在架未掃到")


def test_optional_sections_absent_when_empty():
    html = render_html(_scan(new_items=[_job("https://x/n")]), _TODAY)
    for title in ("重點領域今日更新", "重點領域仍在架", "薪資變動", "104 更新", "在架未掃到", "全部在架"):
        assert f'data-section="{title}"' not in html, title


def test_full_mode_lists_every_active_job_by_update_date():
    old = _job("https://x/old", **{"104_update_date": "2026/11/01"})
    new = _job("https://x/new", **{"104_update_date": "2026/11/12"})
    html = render_html(_scan(still_listed=[old, new]), _TODAY, full=True)
    sec = _section(html, "全部在架")
    assert sec.index("https://x/new") < sec.index("https://x/old")


# ---------- 摘要卡 ----------


def test_summary_counts():
    scan = _scan(
        new_items=[_llm("https://x/n1"), _job("https://x/n2"),
                   _job("https://x/n3", ai_intent={"is_ai_pm": False, "tier": "weak"})],
        refreshed=[_job("https://x/r1")],
        still_listed=[_llm("https://x/s1"), _job("https://x/s2", title="Physical AI 產品經理")],
    )
    html = render_html(scan, _TODAY)
    summary = _section(html, "摘要")
    assert 'data-stat="new">3<' in summary
    assert 'data-stat="ai_pm">2<' in summary
    assert 'data-stat="refreshed">1<' in summary
    assert 'data-stat="total">6<' in summary
    assert 'data-stat="llm">2<' in summary
    assert 'data-stat="physical_ai">1<' in summary
    assert 'data-stat="fde">0<' in summary


def test_header_shows_chinese_weekday():
    assert "11 月 13 日 星期五" in render_html(_scan(), _TODAY)


# ---------- 單筆職缺的欄位 ----------


def test_card_fields():
    j = _job("https://x/c", salary_min=60000, location="台北市信義區",
             notes={"reply_info": "2 天內聯絡過求職者"})
    card = _section(render_html(_scan(new_items=[j]), _TODAY), "新上架")
    assert "Technical Product Manager" in card
    assert "宇見智能科技" in card and "股份有限公司" not in card
    assert "月薪 60,000 起" in card
    assert "台北市信義區" in card
    assert "AI 訊號強" in card
    assert "2 天內聯絡過求職者" in card


@pytest.mark.parametrize("notes,expected", [
    ({"resume_info": "16 小時前處理過履歷", "reply_info": "1 天內聯絡過求職者",
      "activeness": "🟢 徵才行為活躍"}, "16 小時前處理過履歷"),
    ({"resume_info": "", "reply_info": "1 天內聯絡過求職者",
      "activeness": "🟢 徵才行為活躍"}, "1 天內聯絡過求職者"),
    ({"resume_info": "—", "reply_info": "", "activeness": "🟢 徵才行為活躍"}, "徵才行為活躍"),
    ({}, "近期無招募動態"),
], ids=["resume-first", "reply-second", "activeness-last", "none"])
def test_activity_precedence(notes, expected):
    card = _section(render_html(_scan(new_items=[_job("https://x/a", notes=notes)]), _TODAY), "新上架")
    assert expected in card
    for other in ("16 小時前處理過履歷", "1 天內聯絡過求職者", "徵才行為活躍", "近期無招募動態"):
        if other != expected:
            assert other not in card, other


@pytest.mark.parametrize("tier,label", [
    ("strong", "AI 訊號強"), ("moderate", "AI 訊號中"), ("weak", "AI 訊號弱"),
])
def test_ai_tier_label(tier, label):
    j = _job("https://x/t", ai_intent={"tier": tier, "score": 1.0})
    assert label in _section(render_html(_scan(new_items=[j]), _TODAY), "新上架")


def test_no_ai_tier_label_when_none():
    j = _job("https://x/t", ai_intent={"tier": "none", "score": 0.0})
    assert "AI 訊號" not in _section(render_html(_scan(new_items=[j]), _TODAY), "新上架")


def test_external_text_is_escaped():
    j = _job("https://x/e?a=1&b=2", title="<script>alert(1)</script>", company="A&B 公司")
    html = render_html(_scan(new_items=[j]), _TODAY)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "https://x/e?a=1&amp;b=2" in html


def test_job_without_url_is_not_linked():
    j = _job("", title="無連結職缺")
    new = _section(render_html(_scan(new_items=[j]), _TODAY), "新上架")
    assert "無連結職缺" in new
    assert 'href=""' not in new


# ---------- 公司名顯示 ----------


@pytest.mark.parametrize("raw,expected", [
    ("宇見智能科技股份有限公司", "宇見智能科技"),
    ("宇見智能科技有限公司", "宇見智能科技"),
    ("PChome Online_網路家庭國際資訊(股)公司", "PChome Online"),
    ("Cooler Master_訊凱國際股份有限公司", "Cooler Master"),
    ("日商_建興儲存科技股份有限公司", "建興儲存科技"),
    ("台達電子工業股份有限公司 _DELTA ELECTRONICS, INC.", "台達電子工業"),
    ("SHOPLINE Technology Corp., Ltd.", "SHOPLINE Technology Corp., Ltd."),
    # 拆不出來就原樣保留
    ("股份有限公司", "股份有限公司"),
    ("日商_", "日商_"),
    ("", "—"),
    ("_宇見智能科技股份有限公司", "宇見智能科技"),
    ("___", "___"),
], ids=["suffix", "suffix-ltd", "brand-paren-suffix", "brand-first", "origin-prefix",
        "space-before-underscore", "untouched", "only-suffix", "only-origin", "empty",
        "leading-underscore", "only-underscores"])
def test_display_company(raw, expected):
    assert _display_company(raw) == expected


# ---------- 補強：卡片細節與排序 ----------


def test_new_card_label_is_domain_for_focus_and_industry_otherwise():
    first = _llm("https://x/f1", priority=9.0)  # 進焦點區
    second = _llm("https://x/f2", priority=5.0, industry="網際網路相關業")
    plain = _job("https://x/p", industry="電腦軟體服務業")
    new = _section(render_html(_scan(new_items=[first, second, plain]), _TODAY), "新上架")
    second_card = new[new.index("https://x/f2") - 600: new.index("https://x/f2")]
    assert ">LLM<" in second_card and "網際網路相關業" not in second_card
    assert "電腦軟體服務業" in new


def test_activity_color_live_or_idle():
    busy = _job("https://x/b", notes={"reply_info": "2 天內聯絡過求職者"})
    idle = _job("https://x/i", ai_intent={"tier": "weak", "score": 1.0, "priority": 1.0})
    new = _section(render_html(_scan(new_items=[busy, idle]), _TODAY), "新上架")
    assert 'color:#248a3d">2 天內聯絡過求職者' in new
    assert 'color:#aeaeb2">近期無招募動態' in new


def test_negotiable_card_does_not_say_monthly():
    new = _section(render_html(_scan(new_items=[_job("https://x/n")]), _TODAY), "新上架")
    assert "面議" in new and "月薪 面議" not in new


def test_list_row_without_url_is_not_linked():
    html = render_html(_scan(refreshed=[_job("", title="無連結更新職缺")]), _TODAY)
    sec = _section(html, "104 更新")
    assert "無連結更新職缺" in sec and 'href=""' not in sec


def test_featured_without_activity_or_url():
    job = _llm("", notes={})
    featured = _section(render_html(_scan(new_items=[job]), _TODAY), "今日焦點")
    assert "今天新上架的 LLM 職缺。" in featured
    assert "招募動態" not in featured
    assert 'href=""' not in featured and "在 104 查看" not in featured


def test_only_featured_new_job_says_no_other():
    new = _section(render_html(_scan(new_items=[_llm("https://x/f")]), _TODAY), "新上架")
    assert "今日無其他新上架職缺" in new


def test_paid_listed_before_negotiable_then_priority_then_salary():
    neg = _job("https://x/neg", salary_min=None,
               ai_intent={"tier": "strong", "score": 9.0, "priority": 9.5})
    a = _job("https://x/a", salary_min=50000, ai_intent={"tier": "strong", "priority": 9.0})
    b = _job("https://x/b", salary_min=90000, ai_intent={"tier": "weak", "priority": 1.0})
    c = _job("https://x/c", salary_min=70000, ai_intent={"tier": "strong", "priority": 9.0})
    new = _section(render_html(_scan(new_items=[neg, a, b, c]), _TODAY), "新上架")
    order = sorted(["neg", "a", "b", "c"], key=lambda k: new.index(f"https://x/{k}"))
    assert order == ["c", "a", "b", "neg"]


def test_full_mode_without_active_jobs_has_no_all_section():
    html = render_html(_scan(listed_not_scanned=[_rec("https://x/l")]), _TODAY, full=True)
    assert 'data-section="全部在架"' not in html
