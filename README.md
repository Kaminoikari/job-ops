# job-ops

每日早上 7:00 自動爬 104 職缺，過濾出 AI PM 相關缺，寄一封 HTML 報告到 Gmail。
另附單一職缺的 8 維評分工具（`scripts/eval.py`）。架構比照 `house-ops`。

## 日報過濾管線

搜尋關鍵字只負責「廣度撈取」，真正決定一筆職缺進不進日報的是三道過濾：

1. **職稱過濾・title 階段**（`role_filter.is_target_role`，search 列表時跑）
   - PM 白名單（產品經理 / Product Manager / Product Builder / 產品負責人 / 獨立 PM 縮寫…）優先豁免
   - 黑名單剔除工程職（工程師 / Engineer / 架構師…）與非 PM 職能（行政 / 行銷 / 業務 / 設計師 / 特效 / 課程 / 講師 / 市場開發…）
   - 明確非 PM 的缺在抓 detail 前就剔掉，減少抓取量
   - 「產品管理」後接組織單位字（處/部/組/室/課/中心）視為部門名，不觸發白名單
2. **職稱過濾・JD 階段**（`role_filter.confirm_target_role`，detail 抓完後跑）
   - title 模糊（非白名單、也沒中黑名單，如 `Asset Manager`、`AI Server AM`）的缺改看 JD 內容
   - JD 須出現產品/專案管理職能訊號詞（產品規劃 / roadmap / PRD / 專案管理…）才保留
3. **AI 關鍵字硬門檻**（`ai_intent.has_ai`）
   - JD / title 必須出現至少一個 AI 關鍵字，否則整筆剔除
   - 另以加權 lexicon 計算 tier / score，把「角色本身做 AI」的缺排在「公司碰巧是 AI 公司」之前

調整過濾規則前先讀 `job_ops/role_filter.py` 與 `job_ops/ai_intent.py` 的 docstring——
黑白名單的取捨（哪些泛詞刻意不放、為何不收緊 AI 門檻）都記在註解裡。

## 設定

1. 建立 venv 並安裝依賴：
   ```sh
   cd /Users/charles/job-ops
   python3 -m venv .venv
   .venv/bin/pip install -e ".[dev]"
   ```

2. 複製範例設定：
   ```sh
   cp .env.example .env
   cp config/search.yml.example config/search.yml
   ```

3. 填入 `.env` 的 Gmail 帳號 + App Password（不是登入密碼，去 <https://myaccount.google.com/apppasswords> 申請）。

4. 編輯 `config/search.yml` 設定關鍵字、jobcat 職類、地區、過濾條件。

## 手動測跑

```sh
# 純抓 + 寫報告，不寄信
.venv/bin/python scripts/run-daily.py --no-email

# 用上次的快取資料重新渲染並寄信（不爬）
.venv/bin/python scripts/run-daily.py --email-only

# 完整跑：爬 → 寫報告 → 寄信
.venv/bin/python scripts/run-daily.py

# 跑測試
.venv/bin/pytest
```

## 單一職缺評估（eval）

```sh
# 對一筆 104 職缺跑 8 維評分 + 6 區塊報告（讀 cv.md 做匹配）
.venv/bin/python scripts/eval.py <104職缺URL>

# 印 tracker.tsv 統計
.venv/bin/python scripts/eval.py --stats
```

## 啟用每日 7:00 排程（launchd）

```sh
# 編輯 launchd/com.job-ops.daily.plist.example，填入 GMAIL_USER 等三個值
# 然後跑：
bash scripts/install-launchd.sh

# 立即測跑一次：
launchctl kickstart -k gui/$(id -u)/com.job-ops.daily

# 看 log：
tail -f data/logs/daily.out.log
```

## 檔案結構

### 日報 pipeline

- `scripts/run-daily.py` — 入口（被 launchd 觸發）
- `job_ops/scraper_104.py` — 104 search + detail API 爬蟲
- `job_ops/anti_detect.py` — RateLimiter + UA 輪替
- `job_ops/role_filter.py` — 兩階段職稱過濾（title 黑白名單 + JD 職能訊號）
- `job_ops/ai_intent.py` — AI 關鍵字硬門檻 + 加權 lexicon 排序
- `job_ops/history.py` — TSV 持久化 + lifecycle 計算（新上架/更新/下架）
- `job_ops/report.py` — markdown + inline-styled HTML 報告
- `job_ops/email_sender.py` — Gmail SMTP 寄信
- `job_ops/config.py` — YAML + .env 載入、`passes_filters` 過濾入口

### 單缺評估 pipeline

- `scripts/eval.py` — 入口（8 維評分 + 6 區塊報告）
- `job_ops/evaluator.py` — 8 維評分 + 報告組裝
- `job_ops/cv_reader.py` — 讀 `cv.md` 萃取結構化資料
- `job_ops/archetypes.py` — 4 個 PM archetypes 對 JD 做 keyword match
- `job_ops/forum_lookup.py` / `forum_cache.py` — 台灣論壇情報查詢 + 30 天 cache
- `job_ops/tracker.py` — 評估結果 TSV tracker

### 資料與產出（git ignore）

- `data/scan-history.tsv` — 主要狀態檔（持久化）
- `data/last-scan.json` — 上次掃描快取（`--dry-run` / `--email-only` 用）
- `reports/daily/YYYY-MM-DD.{md,html}` — 日報
- `reports/eval/` — 單缺評估報告
