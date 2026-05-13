# C. 等級策略（Level Strategy）

判斷 JD 描述的 seniority vs 候選人的等級，給「賣 senior 不撒謊」與「被 downlevel」兩個雙計畫。

## 產出格式

```markdown
## C) 等級策略

### Detection

| 欄位 | 值 |
|---|---|
| JD 描述等級 | {Junior / Mid / Senior / Lead / Principal / Director} |
| 候選人自然等級（依 cv.md） | {同上} |
| 落差 | {none / -1 / +1 / +2} |

### 賣 senior 不撒謊（適用於候選人等級 ≥ JD 要求）

- **可強調的點**：cv.md 中 2-3 個對齊 senior 等級的 proof points（如「主導跨團隊」、「0→1 從零打造」、「mentor X 個 PM」）
- **可說的 framing 句**：
  - "I've led {跨部門 X 個團隊} on {專案}, which is exactly the scope this role requires"
  - 引用 cv.md 中具體量化成就（不要 "I'm experienced"）

### 被 downlevel（適用於候選人等級 < JD 要求）

| 情境 | 策略 |
|---|---|
| 薪資 fair | 接受 + 談 6 個月 review 機會 |
| 薪資 unfair | 用 cv.md 證據談判：「我已經做過 X、Y、Z，這些都是 senior level scope」 |
| 仍想嘗試 | 在 cover letter / 面試 explicitly 提：「我等級剛跨到 senior，但這 3 個 proof points 顯示能力對齊」 |

### 維度說明

此區塊**不直接產生 1-5 分**，但會影響：
- **第 3 維度（職涯目標契合度）**：若 JD 要求遠超候選人等級 → 降到 archetype `adjacent`
- **第 8 維度（Red Flags）**：若 JD 寫 "Senior" 但 requirements 是 staff 等級 → +1 紅旗扣分
```

## 等級判定 keyword

| 等級 | JD keyword |
|---|---|
| Junior | "junior", "1-2 years", "新鮮人", "Associate" |
| Mid | "2-5 years", "mid-level", "PM"（無前綴） |
| Senior | "Senior", "Sr.", "5+ years", "資深" |
| Lead | "Lead", "Group", "Manager"（管 PM）, "Principal" |
| Principal | "Principal", "Staff", "Distinguished" |
| Director | "Director", "Head of", "VP" |

候選人等級從 `cv.md` 的 `## Current Role` 與 `## Years of Experience` 推斷。
