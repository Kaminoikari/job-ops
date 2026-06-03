#!/usr/bin/env python3
"""Daily pipeline entry point — invoked by launchd at 7:00 AM.

Flow:
    1. Load config + .env
    2. Scrape 104 (all keyword × area combos)
    3. Compare against TSV history → compute lifecycle
    4. Save TSV history + cache last scan
    5. Render markdown + HTML report
    6. Send Gmail email

CLI flags:
    --dry-run     : use cached last-scan.json, skip scraping AND TSV write, skip email
    --no-email    : full pipeline but skip email send
    --email-only  : use cached last-scan.json, re-render report, send email
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

# 確保可以 import job_ops（即使從 launchd 啟動）
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from job_ops.ai_intent import annotate_ai_intent
from job_ops.config import load_email_env, load_search_config, passes_filters
from job_ops.email_sender import send_daily_email
from job_ops.history import (
    Record,
    ScanResult,
    compare,
    load_history,
    merge_into_history,
    save_history,
)
from job_ops.report import build_markdown, build_subject, render_html
from job_ops.scraper_104 import scrape_all


CONFIG_PATH = ROOT / "config" / "search.yml"
ENV_PATH = ROOT / ".env"
HISTORY_PATH = ROOT / "data" / "scan-history.tsv"
LAST_SCAN_PATH = ROOT / "data" / "last-scan.json"
SAMPLE_DUMP_PATH = ROOT / "data" / "logs" / "sample-detail.json"
LOG_DIR = ROOT / "data" / "logs"
REPORT_DIR = ROOT / "reports" / "daily"


def _setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def _cache_last_scan(today_jobs: list[dict], scan: ScanResult) -> None:
    payload = {
        "today": scan.today,
        "today_jobs": today_jobs,
        "scan": {
            "new_items": scan.new_items,
            "refreshed": scan.refreshed,
            "salary_changed": scan.salary_changed,
            "still_listed": scan.still_listed,
            "expired": [asdict(r) for r in scan.expired],
        },
    }
    LAST_SCAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    LAST_SCAN_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_cached_scan() -> tuple[list[dict], ScanResult]:
    if not LAST_SCAN_PATH.exists():
        print(f"ERROR: no cached scan at {LAST_SCAN_PATH}", file=sys.stderr)
        print("執行 --dry-run / --email-only 之前需要先正常跑過一次 pipeline。", file=sys.stderr)
        sys.exit(1)
    data = json.loads(LAST_SCAN_PATH.read_text(encoding="utf-8"))
    scan = ScanResult(
        today=data["today"],
        new_items=data["scan"]["new_items"],
        refreshed=data["scan"]["refreshed"],
        salary_changed=data["scan"]["salary_changed"],
        still_listed=data["scan"]["still_listed"],
        expired=[Record(**r) for r in data["scan"]["expired"]],
    )
    return data["today_jobs"], scan


async def _do_scrape(cfg) -> list[dict]:
    return await scrape_all(
        keywords=cfg.keywords,
        areas=cfg.areas,
        max_pages=cfg.max_pages_per_keyword,
        detail_concurrency=3,
        sample_dump_path=SAMPLE_DUMP_PATH,
        from_date=cfg.from_date,
        jobcats=cfg.jobcats,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="用 cache 重跑，不爬 / 不寫 TSV / 不寄信")
    ap.add_argument("--no-email", action="store_true", help="完整爬完但不寄信")
    ap.add_argument("--email-only", action="store_true", help="用 cache 重新渲染並寄信")
    ap.add_argument("--full", action="store_true", help="包含全部活躍職缺多排序視角（預設只顯示變化）")
    args = ap.parse_args()

    _setup_logging()
    log = logging.getLogger("run-daily")

    if not CONFIG_PATH.exists():
        log.error("找不到設定檔 %s（請從 config/search.yml.example 複製）", CONFIG_PATH)
        return 1

    cfg = load_search_config(CONFIG_PATH)
    today = date.today().isoformat()
    if cfg.from_date:
        log.info("from_date 設定為 %s — 只保留此日期之後上架/更新的職缺", cfg.from_date)

    skip_scrape = args.dry_run or args.email_only

    if skip_scrape:
        today_jobs, scan = _load_cached_scan()
        log.info("[%s mode] loaded cached scan: %d total jobs, %d new",
                 "email-only" if args.email_only else "dry-run",
                 len(today_jobs), len(scan.new_items))
    else:
        log.info("=== Phase 1: 爬 104 ===")
        log.info("keywords=%s jobcats=%s areas=%s max_pages=%d",
                 cfg.keywords, cfg.jobcats, cfg.areas, cfg.max_pages_per_keyword)
        raw_jobs = asyncio.run(_do_scrape(cfg))
        log.info("scrape complete: %d jobs (before filter)", len(raw_jobs))

        today_jobs = [j for j in raw_jobs if passes_filters(j, cfg.filters)]
        log.info("after filter: %d jobs", len(today_jobs))

        # AI 意圖標記：在 compare 前標好，scan 各 list 沿用同批 dict 即帶有 ai_intent
        annotate_ai_intent(today_jobs)

        # AI 關鍵字硬門檻：JD / title 沒有任何 AI 訊號的職缺一律剔除，連抓都不抓進來
        before_ai = len(today_jobs)
        today_jobs = [j for j in today_jobs if (j.get("ai_intent") or {}).get("has_ai")]
        log.info("AI 關鍵字篩選：%d → %d 筆（剔除無 AI 訊號 %d 筆）",
                 before_ai, len(today_jobs), before_ai - len(today_jobs))

        log.info("=== Phase 2: 比對 history ===")
        history = load_history(HISTORY_PATH)
        log.info("history records: %d", len(history))
        scan = compare(today_jobs, history, today=today)
        log.info(
            "scan result: new=%d refreshed=%d salary_changed=%d still_listed=%d expired=%d",
            len(scan.new_items), len(scan.refreshed), len(scan.salary_changed),
            len(scan.still_listed), len(scan.expired),
        )

        log.info("=== Phase 3: 寫回 history ===")
        new_history = merge_into_history(today_jobs, history, scan, today=today)
        save_history(HISTORY_PATH, new_history)
        _cache_last_scan(today_jobs, scan)

    # 確保 scan 各 list 都帶 ai_intent（cached 模式的 dict 與 today_jobs 是分開反序列化的）
    annotate_ai_intent(
        scan.new_items + scan.refreshed + scan.salary_changed + scan.still_listed
    )
    n_ai = sum(1 for j in scan.new_items if (j.get("ai_intent") or {}).get("is_ai_pm"))
    log.info("AI 意圖標記：今日新上架 %d / %d 筆判定為 AI PM", n_ai, len(scan.new_items))

    log.info("=== Phase 4: 產出報告 ===")
    md = build_markdown(scan, today, full=args.full)
    html = render_html(md, today)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    md_path = REPORT_DIR / f"{today}.md"
    html_path = REPORT_DIR / f"{today}.html"
    md_path.write_text(md, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    log.info("報告寫入：%s / %s", md_path, html_path)

    if args.dry_run or args.no_email:
        log.info("⊘ Email 已跳過（%s）", "--dry-run" if args.dry_run else "--no-email")
        return 0

    log.info("=== Phase 5: 寄送 Email ===")
    env = load_email_env(ENV_PATH)
    result = send_daily_email(
        subject=build_subject(scan, today),
        text=md,
        html=html,
        sender=env.sender,
        app_password=env.app_password,
        recipient=env.recipient,
    )
    if result.ok:
        log.info("✓ Email 已寄出至 %s", env.recipient)
        return 0
    else:
        log.error("⚠ Email 寄送失敗：%s", result.reason)
        return 2


if __name__ == "__main__":
    sys.exit(main())
