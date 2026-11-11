"""코인 전일 종가(업비트 공개 시세, 키 불필요).

GET https://api.upbit.com/v1/ticker?markets=KRW-BTC,... 의 `prev_closing_price`.
업비트 일봉은 KST 09:00에 바뀐다. 그래서 종가 날짜는 그 종가가 정해진 시각(직전 09:00)의 날짜로 적는다.
예: 11/11 07:30에 받으면 11/10 09:00에 정해진 값 → 11/10.
목록 중 하나라도 없는 마켓이면 업비트가 요청 전체를 404로 거절하므로, 그때는 하나씩 다시 받는다.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta

from . import _common

URL = "https://api.upbit.com/v1/ticker?markets="


def close_date(now: datetime) -> str:
    local = now.astimezone(_common.KST)
    d = local.date() if local.time() >= time(9, 0) else local.date() - timedelta(days=1)
    return d.isoformat()


def fetch(tickers: list[str], now: datetime | None = None) -> dict[str, tuple[str, float, str]]:
    now = now or _common.now_kst()
    markets = [t.strip().upper() for t in tickers]
    try:
        rows = _common.get_json(URL + ",".join(markets))
    except Exception:
        rows = []
        for m in markets:
            try:
                rows += _common.get_json(URL + m)
            except Exception:
                pass
    d = close_date(now)
    out = {}
    for r in rows:
        try:
            close = float(r["prev_closing_price"])
        except (KeyError, TypeError, ValueError):
            continue
        if close > 0:
            out[r["market"]] = (d, close, "upbit")
    return out
