#!/usr/bin/env bash
# 安裝 / 重新安裝 com.job-ops.daily launchd job。
#
# 用法：bash scripts/install-launchd.sh
#
# 前置：
#   1. 編輯 launchd/com.job-ops.daily.plist.example，填入 GMAIL_USER 等 env vars
#   2. .venv 已建立、依賴已安裝
#   3. config/search.yml 已從 .example 複製並編輯

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/launchd/com.job-ops.daily.plist.example"
DST="$HOME/Library/LaunchAgents/com.job-ops.daily.plist"
LABEL="com.job-ops.daily"

if [ ! -f "$SRC" ]; then
  echo "ERROR: $SRC 不存在" >&2
  exit 1
fi

if grep -q "YOUR_GMAIL@gmail.com" "$SRC"; then
  echo "⚠️  請先編輯 $SRC，把 YOUR_GMAIL / YOUR_RECIPIENT / YOUR_16_CHAR_APP_PASSWORD 換成真實值" >&2
  exit 1
fi

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "⚠️  $ROOT/.venv/bin/python 不存在，請先 python3 -m venv .venv && .venv/bin/pip install -e ." >&2
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents"
cp "$SRC" "$DST"
echo "✓ plist 已複製到 $DST"

# unload 既有 job（如果存在）
if launchctl list | grep -q "$LABEL"; then
  launchctl unload "$DST" 2>/dev/null || true
  echo "✓ 已 unload 既有 $LABEL"
fi

launchctl load "$DST"
echo "✓ 已 load $LABEL"

if launchctl list | grep -q "$LABEL"; then
  echo "✓ 啟用成功，每日 07:00 觸發"
  echo ""
  echo "立即測跑一次："
  echo "  launchctl kickstart -k gui/\$(id -u)/$LABEL"
  echo ""
  echo "看 log："
  echo "  tail -f $ROOT/data/logs/daily.out.log"
  echo "  tail -f $ROOT/data/logs/daily.err.log"
else
  echo "⚠️  load 後找不到 $LABEL，請檢查 $ROOT/data/logs/daily.err.log" >&2
  exit 1
fi
