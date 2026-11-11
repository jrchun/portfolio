#!/bin/bash
# 가격 수집 launchd 작업을 설치(또는 다시 설치)한다. 저장소 폴더에서 실행: bash ops/install-launchd.sh
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
UV="$(command -v uv || true)"
[ -n "$UV" ] || { echo "uv를 찾지 못했습니다. uv를 설치한 뒤 다시 실행하세요." >&2; exit 1; }
LABEL=com.user.rebalance.fetch-prices
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"

mkdir -p "$REPO/logs" "$HOME/Library/LaunchAgents"
sed -e "s#__REPO__#$REPO#g" -e "s#__UV__#$UV#g" "$REPO/ops/$LABEL.plist" > "$DEST"
plutil -lint "$DEST"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$DEST"
echo "설치했습니다: $DEST"
echo "시스템 시간대: $(systemsetup -gettimezone 2>/dev/null || readlink /etc/localtime)"
echo "지금 한 번 실행해 보려면: launchctl kickstart -k gui/$(id -u)/$LABEL && tail -f $REPO/logs/fetch-prices.log"
