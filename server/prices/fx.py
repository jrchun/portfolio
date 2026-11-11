"""USD/KRW 환율(yfinance `KRW=X`). 요청서대로 수집 시점 값을 쓴다(오늘 행이 있으면 그 값)."""
from __future__ import annotations

from datetime import datetime


def fetch(now: datetime | None = None) -> tuple[str, float, str] | None:
    import yfinance as yf

    h = yf.Ticker("KRW=X").history(period="5d", interval="1d", auto_adjust=False)
    if h is None or h.empty:
        return None
    idx = h.index[-1]
    rate = float(h["Close"].iloc[-1])
    return (idx.date().isoformat(), round(rate, 4), "yfinance") if rate > 0 else None
