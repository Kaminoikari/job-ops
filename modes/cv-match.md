# B. CV 匹配（CV Match）

逐項對照 JD requirements vs cv.md，找出 hit / gap，給每個 gap 寫具體 mitigation。

這是**第 1 維度（硬技能 + 領域經驗匹配，25% 權重）**的主要輸入。

## 產出格式

```markdown
## B) CV 匹配

### Hits — 候選人已有的能力（cited from cv.md）

| # | JD Requirement | CV 證據 | 強度 |
|---|---|---|---|
| 1 | {JD 原文 quote} | cv.md L{行號}: "{原文 snippet}" | 🟢 強 / 🟡 中 / 🟠 弱 |
| 2 | ... | ... | ... |

### Gaps — 候選人缺的能力

| # | JD Requirement | 是否 hard blocker | Mitigation |
|---|---|---|---|
| 1 | {JD 原文 quote} | Yes / No | {具體做法：寫進 cover letter / proof point 中提一個鄰近經驗 / 建立 portfolio 專案} |

### 維度評分

**硬技能 + 領域經驗匹配（25%）：{1-5 分}** {emoji}

評分依據：{1-2 句話解釋為什麼這個分數，cite hit/gap 數量與權重}
```

## 評分尺度

| 分數 | 條件 |
|---|---|
| 5 🟢 | 90%+ requirements hit，0 hard blockers，且領域經驗 100% 對得上 |
| 4 🟢 | 70%+ hit，最多 1 個 hard blocker，領域 80% 對得上 |
| 3 🟡 | 50% hit，1-2 個 hard blockers，領域稍微跨界 |
| 2 🟠 | 30% hit，多個 hard blockers，領域不太對 |
| 1 🔴 | < 30% hit，完全不同領域 |

## Hard Blocker vs Nice-to-have 判定

**Hard blocker**：
- JD 明確說 "must have"、"required"、"必須"
- 完全的硬技能（如 "5+ years Python" 你只有 1 年）
- 工作許可（visa）
- Location（onsite 但你在另一個城市）

**Nice-to-have**（不算 blocker）：
- "preferred"、"a plus"、"加分"
- 軟技能（"team player"）
- 可學習的工具（學會 Figma、Jira 等不是 blocker）

## Mitigation 寫作要點

每個 gap 給**具體做法**，不要寫「會持續學習」這種空話：

❌ 不好：「我會持續學習 AWS」
✅ 好：「Cover letter 中提一段：去年用 GCP（cv.md L42）做了類似 RAG 部署，可在 1-2 週內上手 AWS Bedrock」

❌ 不好：「我熟悉 React」
✅ 好：「JD 要 React Native，我有 React Web（cv.md L67），可在 cover letter 提：1 個月內可上手 React Native，並引用 mobile-first 設計經驗」

## 範例輸出

```markdown
## B) CV 匹配

### Hits

| # | JD Requirement | CV 證據 | 強度 |
|---|---|---|---|
| 1 | "5+ years product management" | cv.md L8: "8+ 年產品經驗" | 🟢 強 |
| 2 | "B2B SaaS 經驗" | cv.md L46: "Senior PM @ B2B SaaS 公司" | 🟢 強 |
| 3 | "LLM / RAG 產品經驗" | cv.md L52: "主導 AI 助手 product line" | 🟢 強 |
| 4 | "SQL 與資料分析" | cv.md L24: "SQL（PostgreSQL/BigQuery）" | 🟢 強 |
| 5 | "evals 框架" | cv.md L54: "定義 evals 框架" | 🟡 中（提及但細節需展開） |

### Gaps

| # | JD Requirement | Hard blocker | Mitigation |
|---|---|---|---|
| 1 | "Python 進階開發" | No | cv.md L25 提到 "Python（pandas、簡易 ETL）"。可在 cover letter 提：實作過 RAG pipeline 雛形與評估腳本，再深入是 commitment |
| 2 | "海外經驗" | No | 沒有，但 cv.md L48 顯示我在跨時區團隊（美國工程師）協作。在面試時用此例 |

### 維度評分

**硬技能 + 領域經驗匹配（25%）：4 🟢**

評分依據：5 個關鍵 requirements 全部 hit，2 個 gaps 都不是 hard blockers 且有可信 mitigation 路徑。Python 深度與 evals 細節是中度展開空間。
```
