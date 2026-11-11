"""포트폴리오 종목의 종가와 환율을 모아 DB에 저장한다.

- 포트폴리오에 있는 종목만 수집한다. CASH는 수집하지 않는다.
- 시장별 수집기 하나가 통째로 실패해도 나머지 시장은 저장한다. 실패 종목은 직전 종가를 그대로 둔다.
- 주말·공휴일에는 새 종가가 없을 뿐이므로 오류로 보지 않는다(이미 가진 날짜를 다시 받으면 덮어쓴다).
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from typing import Callable

from .. import db
from . import _common, crypto, fx, gold, kr, us

FETCHERS: dict[str, Callable] = {"KR": kr.fetch, "US": us.fetch, "GOLD": gold.fetch, "CRYPTO": crypto.fetch}
CURRENCY = {"US": "USD"}
_lock = threading.Lock()


def run(conn: sqlite3.Connection, fetchers: dict | None = None, fx_fetch: Callable | None = None,
        now: datetime | None = None) -> dict:
    fetchers = FETCHERS if fetchers is None else fetchers
    fx_fetch = fx.fetch if fx_fetch is None else fx_fetch
    now = now or _common.now_kst()
    with _lock:
        doc, _ = db.get_portfolio(conn)
        by_market: dict[str, dict[str, str]] = {}
        for a in doc.get("assets", []):
            key, market = db.key_of(a), a.get("market")
            if key and market in fetchers:
                by_market.setdefault(market, {})[key] = a.get("name") or key

        updated, failed, errors = [], [], {}
        rows = []
        for market, names in by_market.items():
            try:
                got = fetchers[market](list(names), now)
            except Exception as e:  # 시장 하나가 통째로 실패
                got, errors[market] = {}, f"{type(e).__name__}: {e}"[:200]
            for key, name in names.items():
                r = got.get(key)
                if r:
                    d, close, source = r
                    rows.append((key, d, float(close), CURRENCY.get(market, "KRW"), source))
                    updated.append({"ticker": key, "name": name, "date": d, "close": float(close), "source": source})
                else:
                    failed.append({"ticker": key, "name": name, "market": market})

        try:
            rate = fx_fetch(now)
        except Exception as e:
            rate, errors["FX"] = None, f"{type(e).__name__}: {e}"[:200]

        with conn:
            conn.executemany(
                "INSERT OR REPLACE INTO quotes (ticker, date, close, currency, source) VALUES (?, ?, ?, ?, ?)", rows
            )
            if rate:
                conn.execute("INSERT OR REPLACE INTO fx (date, usdkrw, source) VALUES (?, ?, ?)", rate)

        return {
            "ranAt": now.isoformat(timespec="seconds"),
            "updated": updated,
            "failed": failed,
            "fx": {"date": rate[0], "usdkrw": rate[1]} if rate else None,
            "errors": errors,
        }
