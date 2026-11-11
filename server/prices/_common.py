"""수집기 공용 도구: HTTP 요청과 '이미 확정된 종가인가' 판정."""
from __future__ import annotations

import json
import urllib.request
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
NEW_YORK = ZoneInfo("America/New_York")
UA = "rebalance-board/0.1 (personal portfolio tool)"
TIMEOUT = 15


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def get_json(url: str):
    return json.loads(get(url).decode("utf-8"))


def now_kst() -> datetime:
    return datetime.now(KST)


def is_final(day: date, now: datetime, tz: ZoneInfo, close_after: time) -> bool:
    """그 날짜의 종가가 확정됐는가.

    오늘 날짜 행은 장중에는 실시간 값이고, 국내 금은 장 시작 전에도 전일 값으로 미리 채워져 있다.
    그래서 오늘 행은 그 시장의 마감 시각(여유 포함)이 지난 뒤에만 받는다.
    """
    local = now.astimezone(tz)
    if day < local.date():
        return True
    return day == local.date() and local.time() >= close_after
