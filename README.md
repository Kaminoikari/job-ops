# job-ops

每日早上 7:00 自動爬 104 職缺，寄一封 HTML 報告到 Gmail。完全比照 `house-ops` 的架構。

## 設定

1. 建立 venv 並安裝依賴：
   ```sh
   cd /Users/charles/job-ops
   python3 -m venv .venv
   .venv/bin/pip install -e .
   ```

2. 複製範例設定：
   ```sh
   cp .env.example .env
   cp config/search.yml.example config/search.yml
   ```

3. 填入 `.env` 的 Gmail 帳號 + App Password（不是登入密碼，去 <https://myaccount.google.com/apppasswords> 申請）。

4. 編輯 `config/search.yml` 設定關鍵字、地區、過濾條件。

## 手動測跑

```sh
# 純抓 + 寫報告，不寄信
.venv/bin/python scripts/run-daily.py --no-email

# 用上次的快取資料重新渲染並寄信（不爬）
.venv/bin/python scripts/run-daily.py --email-only

# 完整跑：爬 → 寫報告 → 寄信
.venv/bin/python scripts/run-daily.py
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

- `job_ops/scraper_104.py` — 104 search + detail API 爬蟲
- `job_ops/anti_detect.py` — RateLimiter + UA 輪替
- `job_ops/history.py` — TSV 持久化 + lifecycle 計算
- `job_ops/report.py` — markdown + inline-styled HTML 報告
- `job_ops/email_sender.py` — Gmail SMTP 寄信
- `job_ops/config.py` — YAML + .env 載入
- `scripts/run-daily.py` — 入口（被 launchd 觸發）
- `data/scan-history.tsv` — 主要狀態檔（持久化）
- `reports/daily/YYYY-MM-DD.{md,html}` — 日報
