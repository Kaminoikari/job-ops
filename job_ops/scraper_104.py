"""104 search + detail API scraper.

回傳 dict 結構（對齊 TSV schema）：
    url, company, title, jd, salary_raw, salary_min,
    location, address, benefits, 104_update_date, 104_post_date, notes(dict)
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from urllib.parse import quote

import httpx

from .anti_detect import RateLimiter, SessionUA

log = logging.getLogger(__name__)

SEARCH_URL = "https://www.104.com.tw/jobs/search/api/jobs"
DETAIL_URL = "https://www.104.com.tw/job/ajax/content/{job_id}"

# 完整地區代碼（取自 https://static.104.com.tw/category-tool/json/Area.json）
AREA_CODES: dict[str, str] = {
    # 台灣縣市
    "台北市": "6001001000",
    "新北市": "6001002000",
    "宜蘭縣": "6001003000",
    "基隆市": "6001004000",
    "桃園市": "6001005000",
    "新竹市": "6001006000",       # 104 實為「新竹縣市」合併
    "新竹縣市": "6001006000",
    "新竹縣": "6001006000",
    "苗栗縣": "6001007000",
    "台中市": "6001008000",
    "彰化縣": "6001010000",
    "南投縣": "6001011000",
    "雲林縣": "6001012000",
    "嘉義縣市": "6001013000",
    "嘉義市": "6001013000",
    "嘉義縣": "6001013000",
    "台南市": "6001014000",
    "高雄市": "6001016000",
    "屏東縣": "6001018000",
    "台東縣": "6001019000",
    "花蓮縣": "6001020000",
    "澎湖縣": "6001021000",
    "金門縣": "6001022000",
    "連江縣": "6001023000",
    # 海外大區
    "大陸地區": "6002000000",
    "其他亞洲": "6003000000",
    "東北亞": "6003001000",
    "東南亞": "6003002000",
    "大洋洲": "6004000000",
    "美加地區": "6005000000",
    "中南美洲": "6006000000",
    "歐洲": "6007000000",
    "非洲": "6008000000",
}

# 「海外地區」= 全部海外大區合併
OVERSEAS_CODES = ",".join(
    [
        "6002000000",
        "6003000000",
        "6004000000",
        "6005000000",
        "6006000000",
        "6007000000",
        "6008000000",
    ]
)


def resolve_area_codes(areas: list[str]) -> str:
    """把 YAML 中的地區名稱清單轉成 104 API 的 comma-separated 代碼。"""
    parts: list[str] = []
    for a in areas:
        if a == "海外地區":
            parts.append(OVERSEAS_CODES)
        elif a in AREA_CODES:
            parts.append(AREA_CODES[a])
        else:
            raise ValueError(f"未知地區名稱：{a}（請參考 job_ops/scraper_104.py 的 AREA_CODES）")
    return ",".join(parts)


# ---------- 薪資解析 ----------

_NEGOTIABLE_PATTERNS = ("面議", "待遇面議", "依公司規定", "面談", "電議")


def parse_salary(raw: str) -> int | None:
    """解析 104 薪資字串成「月薪下限」整數；面議或無法解析回 None。

    支援格式：
      月薪 60,000~80,000元 / 月薪 80000元
      年薪 100萬 / 年薪 1,200,000元
      時薪 200元 / 日薪 1500元
      面議 / 待遇面議 / 依公司規定 → None
    """
    if not raw:
        return None
    s = raw.strip()
    if any(p in s for p in _NEGOTIABLE_PATTERNS):
        return None

    # 把 "100萬" → "1000000"，"50K" → "50000"
    def _expand_unit(text: str) -> str:
        text = re.sub(r"([\d,]+)\s*萬", lambda m: str(int(m.group(1).replace(",", "")) * 10000), text)
        text = re.sub(r"([\d,]+)\s*[Kk]", lambda m: str(int(m.group(1).replace(",", "")) * 1000), text)
        return text

    expanded = _expand_unit(s)
    nums = [int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", expanded)]
    if not nums:
        return None
    low = min(nums)

    if "年薪" in s:
        return round(low / 12)
    if "時薪" in s:
        return low * 8 * 22  # 估算月薪
    if "日薪" in s:
        return low * 22
    # 月薪 / 預設視為月薪
    return low


# ---------- 抓徵才積極度 best-effort ----------

_DUMPED_SAMPLE = False


def _dump_sample_once(data: dict, dest: Path) -> None:
    global _DUMPED_SAMPLE
    if _DUMPED_SAMPLE:
        return
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        _DUMPED_SAMPLE = True
        log.info("dumped sample detail JSON to %s", dest)
    except Exception as e:
        log.warning("failed to dump sample: %s", e)


def _extract_activeness(detail: dict) -> dict:
    """從 104 detail JSON 抓徵才積極度與最近聯絡時間。

    Confirmed 欄位（觀察自實際 API）：
        header.hrBehaviorPR              — 0~1 浮點數，HR 行為積極度（越接近 1 越積極）
        interactionRecord.lastCustReplyTimestamp     — 最後雇主回覆 unix 秒
        interactionRecord.lastProcessedResumeAtTime  — 最後處理應徵者 unix 秒
        interactionRecord.nowTimestamp               — 當前 unix 秒（用來算「幾小時前」）
    """
    import time as _time
    notes: dict = {}
    header = detail.get("header") or {}
    ir = detail.get("interactionRecord") or {}

    pr = header.get("hrBehaviorPR")
    if isinstance(pr, (int, float)):
        # 把 0~1 分數轉成中文標籤
        if pr >= 0.8:
            notes["activeness"] = f"🟢 積極徵才 ({pr:.2f})"
        elif pr >= 0.6:
            notes["activeness"] = f"🟡 普通 ({pr:.2f})"
        elif pr >= 0.3:
            notes["activeness"] = f"🟠 偏被動 ({pr:.2f})"
        else:
            notes["activeness"] = f"🔴 不積極 ({pr:.2f})"
        notes["activeness_score"] = pr

    now_ts = ir.get("nowTimestamp") or int(_time.time())
    last_reply = ir.get("lastCustReplyTimestamp")
    last_resume = ir.get("lastProcessedResumeAtTime")
    if last_reply:
        hours = int((now_ts - last_reply) / 3600)
        if hours < 24:
            notes["reply_info"] = f"{hours} 小時前回覆求職者"
        elif hours < 24 * 7:
            notes["reply_info"] = f"{hours // 24} 天前回覆求職者"
        else:
            notes["reply_info"] = f"{hours // 24} 天前回覆（超過 1 週）"
    if last_resume:
        hours = int((now_ts - last_resume) / 3600)
        if hours < 24:
            notes["resume_info"] = f"{hours} 小時前聯絡應徵者"
        elif hours < 24 * 7:
            notes["resume_info"] = f"{hours // 24} 天前聯絡應徵者"
        else:
            notes["resume_info"] = f"{hours // 24} 天前聯絡（超過 1 週）"

    return notes


# ---------- 爬蟲主體 ----------


class OneZeroFourScraper:
    def __init__(self, client: httpx.AsyncClient | None = None, sample_dump_path: Path | None = None):
        self._ua = SessionUA()
        self._limiter = RateLimiter("104")
        self._client = client or httpx.AsyncClient(timeout=30)
        self._owns_client = client is None
        self._sample_dump_path = sample_dump_path

    def _headers(self, referer: str) -> dict[str, str]:
        return {
            "User-Agent": self._ua.get(),
            "Referer": referer,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    async def search(
        self,
        keyword: str,
        areas: list[str],
        max_pages: int = 5,
        from_date: str | None = None,
    ) -> list[dict]:
        """搜尋職缺，回傳 [{url, company, title, appear_date}, ...]。

        from_date 格式 YYYY-MM-DD；翻頁時若整頁 appearDate 都早於此日期就停止
        （104 預設 order=12 是按更新日期降序排列）。
        """
        from_date_compact = from_date.replace("-", "") if from_date else None
        params: dict = {"keyword": keyword, "order": 12, "asc": 0, "mode": "s"}
        if areas:
            params["area"] = resolve_area_codes(areas)

        results: list[dict] = []
        seen_urls: set[str] = set()
        for page in range(1, max_pages + 1):
            await self._limiter.wait()
            params["page"] = page
            try:
                resp = await self._client.get(
                    SEARCH_URL,
                    params=params,
                    headers=self._headers(
                        f"https://www.104.com.tw/jobs/search/?keyword={quote(keyword)}"
                    ),
                )
                if resp.status_code == 429:
                    self._limiter.record_error(429)
                    break
                resp.raise_for_status()
                self._limiter.record_success()
                jobs = resp.json().get("data", []) or []
                if not jobs:
                    break

                page_min_date = None
                added_this_page = 0
                for j in jobs:
                    url = (j.get("link") or {}).get("job", "")
                    if not url:
                        continue
                    if url.startswith("//"):
                        url = "https:" + url
                    elif not url.startswith("http"):
                        url = "https://www.104.com.tw" + url

                    appear = (j.get("appearDate") or "").strip()  # YYYYMMDD
                    if page_min_date is None or appear < page_min_date:
                        page_min_date = appear

                    # 過濾早於 from_date 的職缺
                    if from_date_compact and appear and appear < from_date_compact:
                        continue
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    results.append(
                        {
                            "url": url,
                            "company": j.get("custName", ""),
                            "title": j.get("jobName", ""),
                            "appear_date": appear,
                        }
                    )
                    added_this_page += 1

                log.info(
                    "104 search page=%d keyword=%s count=%d kept=%d min_appear=%s",
                    page, keyword, len(jobs), added_this_page, page_min_date,
                )

                # Early-stop：若整頁最早的 appearDate 已經 < from_date，後續頁更舊不用翻
                if from_date_compact and page_min_date and page_min_date < from_date_compact:
                    log.info("104 search early-stop at page=%d (page_min=%s < from=%s)",
                             page, page_min_date, from_date_compact)
                    break
            except httpx.HTTPStatusError as e:
                self._limiter.record_error(e.response.status_code)
                log.warning("104 search error: %s", e)
                break
            except Exception as e:
                self._limiter.record_error(None)
                log.warning("104 search exception: %s", e)
                break
        return results

    async def detail(self, url: str) -> dict | None:
        """抓單筆職缺詳細資料；失敗回 None。"""
        job_id = _extract_job_id(url)
        await self._limiter.wait()
        try:
            resp = await self._client.get(
                DETAIL_URL.format(job_id=job_id),
                headers=self._headers(f"https://www.104.com.tw/job/{job_id}"),
            )
            if resp.status_code == 429:
                self._limiter.record_error(429)
                return None
            resp.raise_for_status()
            self._limiter.record_success()
            body = resp.json()
            data = body.get("data", {}) or {}

            if self._sample_dump_path is not None:
                _dump_sample_once(body, self._sample_dump_path)

            header = data.get("header") or {}
            jd = data.get("jobDetail") or {}
            cond = data.get("condition") or {}
            welfare = data.get("welfare") or {}
            industry_raw = data.get("industry") or ""  # 注意：104 回傳是 str（產業名稱），不是 dict

            # 組合 JD 文字
            jd_parts: list[str] = []
            if jd.get("jobDescription"):
                jd_parts.append(jd["jobDescription"])
            if cond.get("other"):
                jd_parts.append(f"其他條件：{cond['other']}")
            if welfare.get("welfare"):
                jd_parts.append(f"福利：{welfare['welfare']}")

            salary_raw = jd.get("salary") or header.get("salaryDesc") or ""
            # 104 salaryType 對照（觀察自實際 API）：
            #   10 = 面議  20 = 論件  30 = 時薪  40 = 日薪  50 = 月薪  60 = 年薪
            salary_type = jd.get("salaryType")
            salary_min_raw = jd.get("salaryMin")
            if isinstance(salary_min_raw, int) and salary_min_raw > 0:
                if salary_type == 60:      # 年薪 → 月薪
                    salary_min = round(salary_min_raw / 12)
                elif salary_type == 30:    # 時薪
                    salary_min = salary_min_raw * 8 * 22
                elif salary_type == 40:    # 日薪
                    salary_min = salary_min_raw * 22
                else:                       # 月薪 / 其他 → 視為月薪
                    salary_min = salary_min_raw
            else:
                # salaryMin = 0（面議 / 論件）→ fallback 到字串解析（會回 None）
                salary_min = parse_salary(salary_raw)

            # 地址：detail 的 addressRegion + addressDetail
            region = jd.get("addressRegion") or ""
            addr_detail = jd.get("addressDetail") or ""
            # 完整地址 = 行政區 + 街道
            address = (region + addr_detail) if addr_detail else region
            location = region  # 縣市+區

            notes = _extract_activeness(data)

            return {
                "url": url,
                "company": header.get("custName", ""),
                "title": header.get("jobName", ""),
                "jd": "\n\n".join(jd_parts),
                "salary_raw": salary_raw,
                "salary_min": salary_min,
                "location": location,
                "address": address,
                "benefits": welfare.get("welfare", "") or "",
                # 104 對 active 職缺會持續更新 appearDate（這就是 UI 上的「更新日期」）
                "104_update_date": header.get("appearDate", "") or "",
                "104_post_date": header.get("appearDate", "") or "",
                "industry": industry_raw if isinstance(industry_raw, str) else "",
                "notes": notes,
            }
        except httpx.HTTPStatusError as e:
            self._limiter.record_error(e.response.status_code)
            log.warning("104 detail HTTP %s for %s", e.response.status_code, url)
            return None
        except Exception as e:
            self._limiter.record_error(None)
            log.warning("104 detail exception for %s: %s", url, e)
            return None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def _extract_job_id(url: str) -> str:
    m = re.search(r"/job/([a-zA-Z0-9]+)", url)
    if m:
        return m.group(1)
    return url.rstrip("/").split("/")[-1].split("?")[0]


# ---------- 高層 API ----------


async def scrape_all(
    keywords: list[str],
    areas: list[str],
    max_pages: int = 5,
    detail_concurrency: int = 3,
    sample_dump_path: Path | None = None,
    from_date: str | None = None,
) -> list[dict]:
    """對每個 keyword 跑 search + detail，回傳合併去重後的完整 dict list。

    from_date: YYYY-MM-DD；只保留 appearDate >= from_date 的職缺
    （104 search 預設按更新日降序，會做翻頁 early-stop 加速）。
    """
    scraper = OneZeroFourScraper(sample_dump_path=sample_dump_path)
    try:
        all_search: list[dict] = []
        seen: set[str] = set()
        for kw in keywords:
            results = await scraper.search(kw, areas, max_pages=max_pages, from_date=from_date)
            for r in results:
                if r["url"] in seen:
                    continue
                seen.add(r["url"])
                all_search.append(r)
            log.info("keyword=%s collected %d unique URLs so far", kw, len(all_search))

        log.info("Total unique URLs across keywords: %d, fetching details...", len(all_search))

        sem = asyncio.Semaphore(detail_concurrency)

        async def _fetch(item: dict) -> dict | None:
            async with sem:
                return await scraper.detail(item["url"])

        detail_results = await asyncio.gather(*(_fetch(it) for it in all_search))
        return [d for d in detail_results if d is not None]
    finally:
        await scraper.close()
