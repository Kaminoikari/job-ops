---
name: job-ops-eval
description: Use when the user pastes a 104 job URL or asks to evaluate a Taiwan job. Runs 8-dimension weighted scoring with cv.md matching, Taiwan forum lookup (PTT/Dcard/面試趣), and generates a 6-block A-G report at reports/eval/.
---

# job-ops Evaluation Skill

## When to use

User pastes a 104 URL (`https://www.104.com.tw/job/...`) and explicitly or implicitly asks to evaluate it.

Phrases that should trigger this skill:
- "評估這份職缺 {URL}"
- "這份工作值得投嗎 {URL}"
- "幫我看一下 {URL}"
- "{URL}" (single URL, no other context)

## Workflow

### Step 1 — Prepare data

Run the prepare command to fetch the 104 JD via existing httpx scraper + load cv.md + archetypes + forum cache:

```bash
cd /Users/charles/job-ops
.venv/bin/python scripts/eval.py --prepare {URL}
```

This outputs a JSON with:
- `job` — full 104 detail dict (jd, company, salary, location, benefits, 104 update_date, hrBehaviorPR, lastProcessedResumeAtTime, lastCustReplyTimestamp)
- `cv` — parsed cv.md (hard_skills, domains, proof_points, work_experience)
- `archetype` — keyword-matched archetype + fit (primary/secondary/adjacent)
- `machine_scores` — pre-computed d2_salary, d3_archetype_fit, d4_activeness (use these as starting point, override if needed)
- `profile` — user's target compensation, location, deal_breakers
- `forum_report` — cached forum signals OR null (if null, run forum lookup in Step 2)

### Step 2 — Forum lookup (if forum_report is null)

If `forum_report` is null in the prepared data, fetch fresh signals via WebSearch. Run these queries in **parallel** (single message, multiple tool calls):

```
WebSearch: site:ptt.cc Tech_Job "{company}"
WebSearch: site:dcard.tw "{company}" 職場
WebSearch: site:interview.tw {company}
WebSearch: "{company}" 評價 OR 心得 OR 面試 OR 離職
WebSearch: "{company}" 裁員 OR 凍結 OR 募資 2026
```

For each query take top 3 results. WebFetch into the most relevant 5-8 URLs (skip social shares / spam). Extract:
- **positive_signals**: e.g. "員工 retention 高", "薪資 透明", "技術成長機會多"
- **negative_signals**: e.g. "加班嚴重", "近期裁員 30%", "管理層流動率高"
- **quotes**: 3-5 representative quotes with source URL
- **notes**: 1-2 sentence summary

Then save to forum cache via a small Python snippet using `forum_lookup.save_report()` (so 30 days later we don't re-fetch). Use the `python -c` Bash invocation to call it.

### Step 3 — Run 6-block evaluation

Read these files for evaluation methodology:
- `modes/_shared.md` — scoring rubric + 8-dimension weights + global rules
- `modes/role-summary.md` — Block A format
- `modes/cv-match.md` — Block B format
- `modes/level-strategy.md` — Block C format
- `modes/comp-research.md` — Block D format
- `modes/personalization.md` — Block E format
- `modes/interview-prep.md` — Block F format
- `modes/legitimacy.md` — Block G format

Produce each block as markdown. Score each of the 8 dimensions (1-5 integer).

**For dimensions 2 (salary), 3 (archetype), 4 (activeness)** — start with the pre-computed `machine_scores` and only override if forum/WebSearch reveals something the machine score missed.

**For dimension 5 (公司穩定性) and 6 (文化訊號)** — these are the dimensions most enriched by forum signals; cite specific quotes from forum_report.

**For dimension 8 (Red Flags)** — read `modes/legitimacy.md` Block G criteria carefully. Check tracker.tsv for reposting patterns.

### Step 4 — Assemble report + write tracker

Use a Python snippet to call `evaluator.assemble_report()` and write tracker entry:

```python
from job_ops.evaluator import EvalInput, assemble_report, to_evaluation, report_path
from job_ops.tracker import add_evaluation, next_report_num
ev = EvalInput(
    url="...", company="...", title="...", archetype="...", today="...",
    block_a_summary="...", block_b_cv_match="...", block_c_level="...",
    block_d_comp="...", block_e_personalization="...", block_f_interview="...",
    block_g_legitimacy="...",
    d1_skills=..., d2_salary=..., d3_archetype_fit=..., d4_activeness=...,
    d5_stability=..., d6_culture=..., d7_growth=..., d8_red_flags=...,
    legitimacy="High Confidence|Proceed with Caution|Suspicious",
)
rn = next_report_num()
ev.report_path = str(report_path(ev.company, ev.today, rn))
md = assemble_report(ev)
Path(ev.report_path).parent.mkdir(parents=True, exist_ok=True)
Path(ev.report_path).write_text(md, encoding="utf-8")
evaluation = to_evaluation(ev)
evaluation.report_num = rn
add_evaluation(evaluation)
```

### Step 5 — Report back to user

Show the user:
- Global Score with emoji
- Top 3 reasons for the score (highest-weight dimensions that drove it)
- 1 actionable next step ("建議投" / "再想想" / "Skip")
- Report file path

Keep the summary under 200 字. The full 6-block detail is in the report file.

## Rules

- **NEVER** edit cv.md or profile.yml
- **NEVER** invent skills/experience not in cv.md
- **ALWAYS** cite cv.md line numbers when matching
- **ALWAYS** save forum lookup to cache (30 days TTL)
- **ALWAYS** write tracker.tsv after evaluation
- Output in **繁體中文** (technical terms keep English)

## Anti-patterns

- Don't run forum WebSearch if `forum_report` is already cached (check the prepare JSON output first)
- Don't override `machine_scores` without a clear forum/web signal that justifies it
- Don't write the report markdown manually — use `assemble_report()` so the format stays consistent
