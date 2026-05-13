# A. 角色摘要（Role Summary）

職缺評估的第一步：把 JD 結構化、判定 archetype、產生 1 行 TL;DR。

## 產出格式

```markdown
## A) 角色摘要

| 欄位 | 內容 |
|---|---|
| Archetype | {主要 archetype}{若 hybrid 加標 `(hybrid: A+B)`} |
| Domain | platform / agentic / LLMOps / ML / enterprise / B2B SaaS / consumer / FinTech |
| Function | build（從 0 打造）/ scale（擴大現有）/ consult（顧問型）/ deploy（落地導入）/ manage（人員管理為主） |
| Seniority | Junior / Mid / Senior / Lead / Principal / Director |
| Remote | full-remote / hybrid（每週 X 天）/ onsite |
| Team Size | {JD 提到的團隊規模；沒提到寫「未知」} |
| 公司產業 | {從 104 industry 欄位} |
| 104 更新日 | {104_update_date} |

**TL;DR：** {一句話描述這份工作核心職責與最重要 1-2 個 requirement}
```

## Archetype 判定邏輯

1. 讀 `config/archetypes.yml`
2. 對 JD title + description 計算每個 archetype 的 keyword 命中數
3. **主要 archetype** = 命中最多的那個
4. 若第 2 名命中數 ≥ 主要的 60% → 標 `hybrid`
5. 若所有 archetype 命中數都 < 2 → 標 `archetype: 無明顯匹配`，後續維度評估會降低 archetype 維度權重

## TL;DR 寫作規則

- 1 句話、≤ 40 字
- 句型：「{seniority} {archetype}，負責 {核心 1-2 件事}，最重要的 1-2 個 requirement 是 {...}」
- 範例：「Senior PM，負責 RAG 產品線從 0→1，最重要的 requirement 是 LLM evals 與快速 iteration 經驗。」
- **不要使用** corporate speak（"empowering"、"innovative"、"cutting-edge"）

## 範例輸出

```markdown
## A) 角色摘要

| 欄位 | 內容 |
|---|---|
| Archetype | AI Product Manager（hybrid: + Technical PM） |
| Domain | LLMOps / B2B SaaS |
| Function | build |
| Seniority | Senior |
| Remote | hybrid（每週 2 天 onsite） |
| Team Size | 8 人產品團隊 |
| 公司產業 | 電腦軟體服務業 |
| 104 更新日 | 2026/05/12 |

**TL;DR：** Senior AI PM，負責企業端 RAG 產品從 0→1，最重要的是 LLM evals 框架與工程協作能力。
```
