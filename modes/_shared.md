# job-ops 評估系統 — Shared Context

<!-- 給 Claude Code skill 用的共用 context。Python evaluator 端會把這份文件當系統 prompt 載入。 -->

## Sources of Truth

| File | Purpose |
|---|---|
| `cv.md` | 候選人 CV — Hard Skills / Domains / Proof Points |
| `config/profile.yml` | 個人偏好（薪資下限、地點、deal breakers、產業偏好） |
| `config/archetypes.yml` | 4 個 PM archetypes 定義（AI PM / Senior PM / Tech PM / Product Builder） |
| `data/tracker.tsv` | 已評估職缺主表（單一資料來源） |
| `data/forum-cache/{company-slug}.json` | 論壇情報快取（30 天 TTL） |

**RULE: 評估前必先讀 `cv.md` 與 `config/profile.yml`。**
**RULE: 不要編造 cv.md 或 JD 中沒有的事實。**

---

## 8 維加權評分系統

| # | 維度 | 權重 | 訊號來源 |
|---|---|---|---|
| 1 | 硬技能 + 領域經驗匹配 | 25% | `cv.md` Hard Skills/Domains × JD requirements |
| 2 | 薪資水準 | 15% | 104 `salary_min` vs `profile.yml` target × WebSearch 同職位中位數 |
| 3 | 職涯目標契合度 | 10% | 4 PM archetypes × JD keywords |
| 4 | 徵才活躍度 | 15% | 104 `hrBehaviorPR` + `lastProcessedResumeAtTime` + `lastCustReplyTimestamp` |
| 5 | 公司穩定性 | 15% | forum_cache + WebSearch（裁員/募資/負評密度） |
| 6 | 文化訊號 | 10% | forum_cache + JD 描述（加班強度、團隊風格） |
| 7 | 成長機會 | 5% | JD 中職級空間 + tech stack + 團隊規模 |
| 8 | Red Flags（扣分） | 5% | 鬼缺訊號 + JD 過度模糊 + deal_breakers 命中 |

**評分尺度**：每維度 1-5 整數
- 5 = 極佳 🟢
- 4 = 好 🟢
- 3 = 普通 🟡 / 🟠
- 2 = 差 🟠
- 1 = 極差 🔴

**Global Score** = Σ(維度分數 × 權重) ÷ Σ(權重)，1-5 浮點。

**Emoji 標籤對應**：
- 🟢 ≥ 4.0 → 強烈建議投
- 🟡 ≥ 3.5 → 值得投
- 🟠 ≥ 3.0 → 普通，看其他訊號
- 🔴 < 3.0 → 不建議投

---

## Archetype Detection

讀 `config/archetypes.yml`，對 JD title + description 跑 keyword match。回傳：
- `detected: [archetype1, archetype2]`（最相符的 1-2 個）
- `fit: primary | secondary | adjacent`（取最高匹配的 archetype 的 fit）

混合 archetype（例如 "AI Technical PM"）→ 取 2 個並標 `hybrid: true`。

---

## Global Rules

### NEVER
1. 編造 cv.md 中沒有的技能或經驗
2. 修改 cv.md 或 profile.yml
3. 在沒有實際資料的情況下給薪資估算 — 講「資料不足」
4. 把 forum_cache 中的負評當作確定事實 — 用「來自論壇的訊號」措辭

### ALWAYS
1. 評估前讀 `cv.md` + `config/profile.yml` + `config/archetypes.yml`
2. 引用具體 cv.md 行號或 JD quote
3. 用繁體中文輸出（保留技術術語英文）
4. 評估完成後寫入 `data/tracker.tsv`
5. 報告寫入 `reports/eval/{###}-{company-slug}-{YYYY-MM-DD}.md`

### Tools
- WebSearch — 薪資查詢、公司近期新聞、論壇情報
- WebFetch — 讀論壇文章內文
- Read — cv.md / profile.yml / archetypes.yml / tracker.tsv
- Write — 評估報告 + tracker 更新

---

## 6 區塊報告結構（A-G，跳過 PDF）

每筆評估產出 markdown 報告，順序：

1. **Header** — Company / Title / URL / Global Score / Legitimacy / 評估日期
2. **A. 角色摘要** — Archetype / Domain / Function / Seniority / Remote / TL;DR
3. **B. CV 匹配** — 逐項對照 cv.md 行號 + Gaps & Mitigation
4. **C. 等級策略** — JD 等級 vs 候選人等級 + 兩個雙計畫
5. **D. 薪酬研究** — 104 salary + WebSearch market + 建議談判數字
6. **E. 個人化計畫** — Top 5 履歷修改 + Top 5 LinkedIn 修改建議
7. **F. 面試準備** — 6-10 個 STAR+R 故事 mapping JD requirements
8. **G. 招募合法性** — High Confidence / Proceed with Caution / Suspicious + 訊號 table
9. **Scoring** — 8 維度評分表 + Global Score 計算

詳細格式見 `modes/{role-summary,cv-match,level-strategy,comp-research,personalization,interview-prep,legitimacy}.md`。
