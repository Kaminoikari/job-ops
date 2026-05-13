#!/usr/bin/env python3
"""URL paste evaluation pipeline.

Modes:
    python scripts/eval.py {104 URL}           # 直接評估一份 104 職缺
    python scripts/eval.py --prepare {URL}     # 只準備資料（不呼叫 LLM）；給 Claude Code skill 用
    python scripts/eval.py --pipeline          # 批次跑 data/pipeline.md 中所有 pending URL
    python scripts/eval.py --stats             # 印 tracker.tsv 統計

評估的 LLM 推理由 Claude Code skill 主對話進行（讀 modes/*.md），
本腳本只負責資料準備 + 報告組裝 + tracker 寫入。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from job_ops.evaluator import (
    EvalContext,
    prepare_context,
    company_slug_for_report,
    report_path,
)
from job_ops.forum_lookup import lookup_cached
from job_ops.scraper_104 import OneZeroFourScraper
from job_ops.tracker import stats as tracker_stats

PROFILE_PATH = ROOT / "config" / "profile.yml"
PIPELINE_MD = ROOT / "data" / "pipeline.md"


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _load_profile() -> dict:
    if not PROFILE_PATH.exists():
        return {}
    return yaml.safe_load(PROFILE_PATH.read_text(encoding="utf-8")) or {}


def _is_104_url(url: str) -> bool:
    return bool(re.match(r"^https?://(www\.)?104\.com\.tw/job/", url))


async def _fetch_104(url: str) -> dict | None:
    scraper = OneZeroFourScraper()
    try:
        return await scraper.detail(url)
    finally:
        await scraper.close()


def _eval_context_to_dict(ctx: EvalContext) -> dict:
    """把 EvalContext 序列化成 dict（給 --prepare 模式 dump 給 Claude Code skill）。"""
    forum = None
    if ctx.forum_report:
        forum = ctx.forum_report.to_dict()
    return {
        "url": ctx.url,
        "today": ctx.today,
        "job": ctx.job,
        "cv_summary": ctx.cv_summary,
        "cv": {
            "headline": ctx.cv.headline,
            "summary": ctx.cv.summary,
            "hard_skills": ctx.cv.hard_skills,
            "domains": ctx.cv.domains,
            "years_of_experience": ctx.cv.years_of_experience,
            "current_role": ctx.cv.current_role,
            "proof_points": ctx.cv.proof_points,
            "work_experience": ctx.cv.work_experience,
            "is_template": ctx.cv.is_template,
        },
        "archetype": {
            "primary": ctx.archetype_match.primary.name,
            "secondary": ctx.archetype_match.secondary.name if ctx.archetype_match.secondary else None,
            "is_hybrid": ctx.archetype_match.is_hybrid,
            "fit": ctx.archetype_match.primary.fit,
            "hits": ctx.archetype_match.hits,
        },
        "machine_scores": {
            "d2_salary": ctx.salary_score,
            "d3_archetype_fit": ctx.archetype_score,
            "d4_activeness": ctx.activeness_score,
        },
        "profile": ctx.profile,
        "forum_report": forum,
    }


async def cmd_prepare(url: str) -> int:
    """準備評估資料並 dump 成 JSON（給 Claude Code skill 讀）。"""
    if not _is_104_url(url):
        print(f"ERROR: 目前只支援 104 URL（您提供：{url}）", file=sys.stderr)
        return 1

    log = logging.getLogger("eval.prepare")
    log.info("Fetching 104 detail: %s", url)
    job = await _fetch_104(url)
    if not job:
        print(f"ERROR: 無法抓取 104 detail：{url}", file=sys.stderr)
        return 2

    log.info("Loading CV, archetypes, profile, forum cache...")
    profile = _load_profile()
    forum_report = lookup_cached(job.get("company", ""))

    ctx = prepare_context(url=url, job=job, profile=profile, forum_report=forum_report)
    out = _eval_context_to_dict(ctx)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_stats() -> int:
    s = tracker_stats()
    print(json.dumps(s, ensure_ascii=False, indent=2))
    return 0


def cmd_pipeline_list() -> int:
    """列出 pipeline.md 中所有 pending URL。"""
    if not PIPELINE_MD.exists():
        print(f"⚠ pipeline.md 不存在 ({PIPELINE_MD})。要建立可：echo '## Pendientes' > {PIPELINE_MD}")
        return 1
    text = PIPELINE_MD.read_text(encoding="utf-8")
    pendings = re.findall(r"^-\s+\[\s*\]\s+(.+)$", text, flags=re.MULTILINE)
    if not pendings:
        print("(no pending URLs)")
        return 0
    for u in pendings:
        print(u.strip())
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="URL paste evaluation pipeline")
    ap.add_argument("url", nargs="?", help="104 職缺 URL")
    ap.add_argument("--prepare", metavar="URL", help="只準備資料 dump JSON（給 Claude Code skill 用）")
    ap.add_argument("--pipeline", action="store_true", help="列出 pipeline.md pending URLs")
    ap.add_argument("--stats", action="store_true", help="印 tracker.tsv 統計")
    args = ap.parse_args()

    _setup_logging()

    if args.stats:
        return cmd_stats()
    if args.pipeline:
        return cmd_pipeline_list()
    if args.prepare:
        return asyncio.run(cmd_prepare(args.prepare))
    if args.url:
        # 預設模式：等同 --prepare
        return asyncio.run(cmd_prepare(args.url))

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
