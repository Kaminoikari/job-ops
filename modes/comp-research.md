# D. 薪酬研究（Compensation Research）

這是**第 2 維度（薪資水準，15% 權重）**的主要輸入。

## 產出格式

```markdown
## D) 薪酬研究

### 104 顯示薪資

| 欄位 | 值 |
|---|---|
| 原始字串 | {104 `salary_raw`} |
| 解析月薪下限 | {`salary_min` TWD} |
| 是否面議 | Yes / No |

### 市場行情（WebSearch）

| 來源 | 月薪範圍 | 連結 |
|---|---|---|
| Glassdoor TW {role} | NT$ {X}-{Y} | {URL} |
| 104 相似職位中位數 | NT$ {X}-{Y} | {WebSearch 結果} |
| LinkedIn Salary（如有）| NT$ {X}-{Y} | {URL} |

### 比較

- 候選人 `profile.yml` target：月薪 {target}（min {min}）
- 此職缺 vs target：{above target / at target / below target / below minimum}

### 談判建議

- 預估 base 範圍：NT$ {X}-{Y}
- 預估總包（含 bonus / equity）：NT$ {X}-{Y}
- 開價建議：NT$ {Y * 1.1}（上限 +10%）
- 走人線：低於 NT$ {profile.minimum} 直接拒

### 維度評分

**薪資水準（15%）：{1-5 分}** {emoji}

評分依據：{解釋}
```

## 評分尺度

| 分數 | 條件 |
|---|---|
| 5 🟢 | salary_min ≥ target × 1.2 |
| 4 🟢 | target ≤ salary_min < target × 1.2 |
| 3 🟡 | minimum ≤ salary_min < target |
| 2 🟠 | salary_min < minimum 但差距 < 15% |
| 1 🔴 | salary_min < minimum × 0.85 |

**面議特殊處理**：
- 若公司在論壇上有薪資 disclosure（PTT、Glassdoor）→ 用論壇資料評分
- 若完全找不到 → 評 3 🟡 並標 `salary_data: insufficient`，不要瞎猜

## WebSearch query 範本

對每筆評估打這幾個 query（從成本最低 → 最高）：

1. `"{company}" salary {role} Taiwan TWD`（最直接）
2. `Glassdoor "{company}" salaries Taipei`
3. `104 "{role}" 薪資 中位數`
4. `levels.fyi {company}`（如果是知名科技公司）

每個 query 取 top 3 結果用 WebFetch 進去讀；萃取數字 + 來源 URL。

## NEVER

- 用 PPP（購買力平價）換算 — 直接給 TWD 數字
- 用 US 數字推估 TW（科技業差異 ~3-4x）
- 在沒有資料時瞎掰 — 講「資料不足，建議直接問 HR」
