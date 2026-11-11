"""미국 주식·ETF 종가(yfinance, 비공식 라이브러리). `BRK.B`는 `BRK-B`로 바꿔 조회한다."""
from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from . import _common

CLOSE_AFTER = time(16, 30)  # 뉴욕 16:00 마감 + 여유


def yahoo_symbol(ticker: str) -> str:
    return ticker.strip().upper().replace(".", "-").replace("/", "-")


def history_close(symbol: str, now: datetime, tz: ZoneInfo, close_after: time) -> tuple[str, float] | None:
    """yfinance 일봉에서 확정된 마지막 종가."""
    import yfinance as yf  # 가져오는 데 시간이 걸려 필요할 때만 읽는다

    h = yf.Ticker(symbol).history(period="1mo", interval="1d", auto_adjust=False)
    if h is None or h.empty or "Close" not in h:
        return None
    best = None
    for idx, close in h["Close"].items():
        d = idx.date()
        c = float(close)
        if c > 0 and _common.is_final(d, now, tz, close_after) and (best is None or d > best[0]):
            best = (d, c)
    return (best[0].isoformat(), round(best[1], 4)) if best else None


def fetch(tickers: list[str], now: datetime | None = None) -> dict[str, tuple[str, float, str]]:
    now = now or _common.now_kst()
    out = {}
    for t in tickers:
        try:
            r = history_close(yahoo_symbol(t), now, _common.NEW_YORK, CLOSE_AFTER)
        except Exception:
            r = None
        if r:
            out[t] = (r[0], r[1], "yfinance")
    return out
