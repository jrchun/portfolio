"""국내 주식·ETF 종가.

1순위: 네이버 금융 일봉(fchart.stock.naver.com). 키 불필요. 공식 문서가 없는 주소다.
       2026-11-10 대조에서 증권사 앱 종가와 일치했다(삼성전자 197,300원).
2순위: yfinance(.KS → .KQ). 같은 날 개별 주식 종가가 증권사 앱과 달랐으므로(삼성전자 198,900원)
       네이버에서 받지 못한 종목에만 쓴다. 저장할 때 출처로 구분된다.
"""
from __future__ import annotations

import re
from datetime import datetime, time, timedelta

from . import _common, us

CLOSE_AFTER = time(16, 0)  # 15:30 마감 + 여유
ROW = re.compile(rb'\["(\d{8})",\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)')


def naver(code: str, now: datetime) -> tuple[str, float] | None:
    today = now.astimezone(_common.KST).date()
    url = (
        "https://fchart.stock.naver.com/siseJson.nhn?symbol=" + code
        + "&requestType=1&timeframe=day"
        + "&startTime=" + (today - timedelta(days=21)).strftime("%Y%m%d")
        + "&endTime=" + today.strftime("%Y%m%d")
    )
    return parse_naver(_common.get(url), now)


def parse_naver(body: bytes, now: datetime) -> tuple[str, float] | None:
    """행 형식: ["20261110", 시가, 고가, 저가, 종가, 거래량, 외국인소진율]. 확정된 마지막 종가."""
    best = None
    for m in ROW.finditer(body):
        d = datetime.strptime(m.group(1).decode(), "%Y%m%d").date()
        close = float(m.group(5))
        if close > 0 and _common.is_final(d, now, _common.KST, CLOSE_AFTER) and (best is None or d > best[0]):
            best = (d, close)
    return (best[0].isoformat(), best[1]) if best else None


def yahoo(code: str, now: datetime) -> tuple[str, float] | None:
    for suffix in (".KS", ".KQ"):
        r = us.history_close(code + suffix, now, _common.KST, CLOSE_AFTER)
        if r:
            return r
    return None


SOURCES = (("naver", naver), ("yfinance", yahoo))


def fetch(tickers: list[str], now: datetime | None = None) -> dict[str, tuple[str, float, str]]:
    """{종목코드: (날짜, 종가, 출처)}. 받지 못한 종목은 결과에 없다."""
    now = now or _common.now_kst()
    out = {}
    for code in tickers:
        for source, fn in SOURCES:
            try:
                r = fn(code, now)
            except Exception:
                r = None
            if r:
                out[code] = (r[0], r[1], source)
                break
    return out
