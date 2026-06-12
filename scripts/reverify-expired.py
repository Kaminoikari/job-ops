#!/usr/bin/env python3
"""一次性回填：複驗 scan-history.tsv 內所有 Expired 職缺是否真的下架。

背景：舊版把「今天搜尋沒撈到」直接標成 Expired，但 104 寬詞相關性排序 + max_pages
截斷會讓在架職缺掉出覆蓋窗，導致大量「假下架」。本腳本逐筆向 104 detail API 確認：

    detail 回 200 有資料 → 仍在架 → 改標 ListedNotScanned（漏掃，非下架）
    detail 回 404        → 真下架 → 維持 Expired
    驗證失敗（429/網路） → 無法確認 → 維持 Expired（可重跑）

用法：
    .venv/bin/python scripts/reverify-expired.py --dry-run      # 只統計、不寫檔
    .venv/bin/python scripts/reverify-expired.py --limit 50     # 只驗前 50 筆
    .venv/bin/python scripts/reverify-expired.py                # 全量複驗並寫回（先備份）
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from job_ops.history import (
    STATUS_EXPIRED,
    STATUS_LISTED_NOT_SCANNED,
    Record,
    load_history,
    save_history,
)
from job_ops.scraper_104 import verify_listings_alive

HISTORY_PATH = ROOT / "data" / "scan-history.tsv"

log = logging.getLogger("reverify-expired")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只統計，不寫回 TSV")
    ap.add_argument("--limit", type=int, default=0, help="只驗前 N 筆（0=全部）")
    ap.add_argument("--concurrency", type=int, default=3, help="detail 併發數")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s",
                        datefmt="%H:%M:%S", stream=sys.stdout)

    history = load_history(HISTORY_PATH)
    expired_urls = [url for url, rec in history.items() if rec.status == STATUS_EXPIRED]
    if args.limit:
        expired_urls = expired_urls[: args.limit]

    log.info("history 共 %d 筆，其中 Expired %d 筆待複驗", len(history), len(expired_urls))
    if not expired_urls:
        log.info("沒有 Expired 職缺，結束")
        return 0

    alive_map = asyncio.run(verify_listings_alive(expired_urls, concurrency=args.concurrency))

    alive = [u for u, v in alive_map.items() if v is True]
    really_down = [u for u, v in alive_map.items() if v is False]
    unknown = [u for u, v in alive_map.items() if v is None]
    log.info("複驗結果：仍在架（假下架）%d 筆、確認下架 %d 筆、無法確認 %d 筆",
             len(alive), len(really_down), len(unknown))

    if args.dry_run:
        log.info("[dry-run] 不寫檔。仍在架範例：")
        for u in alive[:10]:
            log.info("  在架 %s | %s", u, history[u].title)
        return 0

    if not alive:
        log.info("沒有需要改回的職缺，TSV 不變")
        return 0

    # 備份後寫回
    today = date.today().isoformat()
    backup = HISTORY_PATH.with_suffix(f".tsv.bak-reverify-{today.replace('-', '')}")
    backup.write_text(HISTORY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    log.info("已備份原 TSV 至 %s", backup)

    for url in alive:
        rec = history[url]
        history[url] = Record(
            **{**rec.__dict__, "status": STATUS_LISTED_NOT_SCANNED, "last_seen": today}
        )

    save_history(HISTORY_PATH, history)
    log.info("已將 %d 筆假下架改標為 %s 並寫回 %s", len(alive), STATUS_LISTED_NOT_SCANNED, HISTORY_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
