# G. 招募合法性（Posting Legitimacy — 鬼缺檢測）

辨識這個職缺是不是「鬼缺」（fake job posting）或公司沒有真的要招人。

## 產出格式

```markdown
## G) 招募合法性

**Assessment**: High Confidence / Proceed with Caution / Suspicious

### Signals Table

| Signal | Finding | Weight | Source |
|---|---|---|---|
| Posting 新鮮度 | {104 update_date 比今天 N 天前} | 🟢 / 🟡 / 🔴 | 104 |
| 候選人聯絡時間 | "{X 小時前聯絡應徵者}" | 🟢 / 🟡 / 🔴 | 104 interactionRecord |
| 雇主回覆時間 | "{X 小時前回覆求職者}" | 🟢 / 🟡 / 🔴 | 104 interactionRecord |
| hrBehaviorPR | {X.XX 分} | 🟢 / 🟡 / 🔴 | 104 |
| Reposting 偵測 | 同公司同類職缺出現 N 次 / Y 天 | 🟢 / 🟡 / 🔴 | tracker.tsv 歷史 |
| JD 品質 | {具體程度、是否提團隊規模、報告線、首 6 個月 scope} | 🟢 / 🟡 / 🔴 | JD 內文 |
| 公司近期動態 | {裁員 / 凍結 / 募資} | 🟢 / 🟡 / 🔴 | WebSearch |
| 論壇情報 | {forum_cache 中對招聘活動的 mentions} | 🟢 / 🟡 / 🔴 | forum_cache |

### Context Notes

{解釋有特殊 context 的 signals。如「JD 長達 5 個月未更新但公司是傳統製造業，這在該產業是常態」}

### 維度評分

**Red Flags（5% 扣分）：{1-5 分}** {emoji}

評分依據：{綜合上述訊號}
```

## Assessment Tier 判定

- **High Confidence**：≥6 個訊號是 🟢，0 個 🔴
- **Proceed with Caution**：1-2 個 🔴，其他 🟢/🟡
- **Suspicious**：≥3 個 🔴，特別是 reposting + 公司裁員同時出現

## 個別訊號評分標準

### Posting 新鮮度（104 update_date）

| 天數 | 🟢/🟡/🔴 |
|---|---|
| ≤ 7 天 | 🟢 |
| 8-30 天 | 🟡 |
| 31-60 天 | 🟠 |
| > 60 天 | 🔴（除非是政府/學術，可調整為 🟡） |

### 候選人聯絡時間（lastProcessedResumeAtTime）

| 時間 | 🟢/🟡/🔴 |
|---|---|
| < 24 小時 | 🟢 |
| 1-3 天 | 🟡 |
| 4-7 天 | 🟠 |
| > 7 天 | 🔴 |

### hrBehaviorPR

| 分數 | 🟢/🟡/🔴 |
|---|---|
| ≥ 0.8 | 🟢 積極徵才 |
| 0.6-0.79 | 🟡 普通 |
| 0.3-0.59 | 🟠 偏被動 |
| < 0.3 | 🔴 不積極（可能殭屍職缺）|

### Reposting 偵測

讀 `data/scan-history.tsv` 與 `data/tracker.tsv`，看同公司 + 同職位類型過去 90 天內出現幾次。

| 次數 | 🟢/🟡/🔴 |
|---|---|
| 1 次 | 🟢 |
| 2-3 次 | 🟡 |
| ≥ 4 次 | 🔴（職缺一直填不掉） |

### JD 品質

逐項打勾：
- [ ] 提到具體 tech stack 與 tools
- [ ] 提到團隊規模 / 報告線
- [ ] 提到首 6 個月 scope
- [ ] 薪資範圍透明
- [ ] requirements 合理（不是 entry-level 但要 5 years 的內部矛盾）

5 項全勾 🟢 / 3-4 項 🟡 / ≤2 項 🔴

### 公司近期動態（WebSearch）

Query：
- `"{company}" 裁員 OR 縮編 2026`
- `"{company}" hiring freeze`
- `"{company}" 募資 OR Series 2026`

若有近期裁員（< 6 個月）且裁的是同部門 → 🔴
若有近期募資 / 擴張 → 🟢

## Ethical Framing（必遵守）

- **觀察**，不 **指控**。每個 signal 都有合理解釋。
- User 決定怎麼解讀。
- 鬼缺 ≠ 詐騙。有些公司只是流程慢、評核久。

## NEVER

- 直接說 "this is a fake job"
- 把單一訊號當定論
- 在 forum_cache 為空時瞎猜「公司一定有問題」
