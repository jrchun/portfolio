"""가격 수집 테스트. 네트워크 없이 응답을 흉내 낸다."""
import json
from datetime import date, datetime

import pytest

from server import db
from server.prices import _common, collect, crypto, gold, kr, us

KST = _common.KST


def kst(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=KST)


NAVER = b"""
 [['\xb3\xaf\xc2\xa5', 'x'],
["20261106", 180000, 196500, 179200, 193500, 35516270, 45.94],
["20261109", 187200, 195400, 183800, 187000, 19855892, 45.93],
["20261110", 199400, 201500, 196400, 197300, 15289184, 45.93],
["20261111", 199000, 199500, 196000, 198000, 1000, 45.93]
]"""


def test_naver_skips_today_until_close():
    assert kr.parse_naver(NAVER, kst(2026, 11, 11, 7, 30)) == ("2026-11-10", 197300.0)
    assert kr.parse_naver(NAVER, kst(2026, 11, 11, 15, 0)) == ("2026-11-10", 197300.0)  # 장중 값은 버린다
    assert kr.parse_naver(NAVER, kst(2026, 11, 11, 16, 5)) == ("2026-11-11", 198000.0)
    assert kr.parse_naver(b"[['x']]", kst(2026, 11, 11, 7, 30)) is None  # 없는 종목


GOLD = [
    {"localTradedAt": "2026-11-11T00:00:00+09:00", "closePrice": "177,290"},  # 장 시작 전에 미리 채워진 행
    {"localTradedAt": "2026-11-10T00:00:00+09:00", "closePrice": "177,290"},
    {"localTradedAt": "2026-11-09T00:00:00+09:00", "closePrice": "178,770"},
]


def test_gold_skips_prefilled_today():
    assert gold.parse(GOLD, kst(2026, 11, 11, 7, 30)) == ("2026-11-10", 177290.0)
    assert gold.parse(GOLD, kst(2026, 11, 11, 17, 0)) == ("2026-11-11", 177290.0)


def test_crypto_close_date_follows_upbit_0900_boundary():
    assert crypto.close_date(kst(2026, 11, 11, 7, 30)) == "2026-11-10"
    assert crypto.close_date(kst(2026, 11, 11, 9, 0)) == "2026-11-11"


def test_crypto_retries_one_by_one_when_batch_rejected(monkeypatch):
    calls = []

    def fake(url):
        calls.append(url)
        if "," in url or "NOPE" in url:
            raise OSError("404 Code not found")
        return [{"market": "KRW-BTC", "prev_closing_price": 102254000.0}]

    monkeypatch.setattr(_common, "get_json", fake)
    r = crypto.fetch(["KRW-BTC", "KRW-NOPE"], kst(2026, 11, 11, 7, 30))
    assert r == {"KRW-BTC": ("2026-11-10", 102254000.0, "upbit")}
    assert len(calls) == 3


def test_us_symbol():
    assert us.yahoo_symbol("brk.b") == "BRK-B"


def test_kr_falls_back_to_yfinance_only_when_naver_has_nothing(monkeypatch):
    monkeypatch.setattr(kr, "SOURCES", (
        ("naver", lambda c, now: ("2026-11-10", 197300.0) if c == "005930" else None),
        ("yfinance", lambda c, now: ("2026-11-10", 1.0)),
    ))
    assert kr.fetch(["005930", "0080G0"], kst(2026, 11, 11, 7, 30)) == {
        "005930": ("2026-11-10", 197300.0, "naver"),
        "0080G0": ("2026-11-10", 1.0, "yfinance"),
    }


def test_business_days_since():
    # 금요일 종가를 화요일에 보면 그 사이 평일은 월요일 하루
    assert db.business_days_since(date(2026, 11, 6), date(2026, 11, 10)) == 1
    assert db.business_days_since(date(2026, 11, 10), date(2026, 11, 11)) == 0
    assert db.business_days_since(date(2026, 11, 4), date(2026, 11, 11)) == 4


DOC = {
    "monthly": 0, "band": 5, "groups": [],
    "assets": [
        {"name": "삼성전자", "ticker": "005930", "market": "KR", "qty": 1, "avg": 1, "unit": 1},
        {"name": "QQQM", "ticker": "QQQM", "market": "US", "qty": 1, "avg": 1, "unit": 1},
        {"name": "금", "ticker": "M04020000", "market": "GOLD", "qty": 1, "avg": 1, "unit": 1},
        {"name": "비트코인", "ticker": "KRW-BTC", "market": "CRYPTO", "qty": 1, "avg": 1, "unit": 0.0001},
        {"name": "현금", "ticker": "CASH-1", "market": "CASH", "qty": 1, "avg": 1, "unit": 1},
    ],
}


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.sqlite")
    c.executescript(db.SCHEMA)
    c.execute("INSERT INTO portfolio (id, doc, version, updated_at) VALUES (1, ?, 1, 'x')", (json.dumps(DOC),))
    # 미국 종목의 직전 종가
    c.execute("INSERT INTO quotes VALUES ('QQQM', '2026-11-06', 270.22, 'USD', 'yfinance')")
    c.commit()
    yield c
    c.close()


def ok(prices):
    return lambda tickers, now: {t: (d, c, "test") for t, (d, c) in prices.items() if t in tickers}


def boom(tickers, now):
    raise ConnectionError("blocked")


def test_one_market_blocked_others_still_saved(conn):
    """출처 하나를 일부러 막아도 나머지는 갱신되고, 막힌 종목은 직전 종가를 유지한다."""
    now = kst(2026, 11, 11, 7, 30)
    r = collect.run(conn, fetchers={
        "KR": ok({"005930": ("2026-11-10", 197300)}),
        "US": boom,
        "GOLD": ok({"M04020000": ("2026-11-10", 177290)}),
        "CRYPTO": ok({"KRW-BTC": ("2026-11-10", 102254000)}),
    }, fx_fetch=lambda now: ("2026-11-10", 1342.07, "test"), now=now)
    assert sorted(u["ticker"] for u in r["updated"]) == ["005930", "KRW-BTC", "M04020000"]
    assert [f["ticker"] for f in r["failed"]] == ["QQQM"]
    assert "US" in r["errors"]
    p = db.latest_prices(conn, DOC, today=date(2026, 11, 11))
    assert p["quotes"]["005930"] == {"close": 197300, "date": "11/10"}
    assert p["quotes"]["QQQM"] == {"close": 270.22, "date": "11/06"}  # 직전 종가 유지, 아직 3영업일 이내
    assert p["fx"] == 1342.07
    assert "CASH-1" not in p["quotes"]
    # 그대로 며칠 지나면 오래된 종가로 표시된다
    assert db.latest_prices(conn, DOC, today=date(2026, 11, 13))["quotes"]["QQQM"]["stale"] is True


def test_fx_failure_keeps_previous_rate_and_rerun_is_idempotent(conn):
    conn.execute("INSERT INTO fx VALUES ('2026-11-09', 1362.7, 'test')")
    conn.commit()
    fetchers = {m: ok({}) for m in ("KR", "US", "GOLD", "CRYPTO")}
    fetchers["KR"] = ok({"005930": ("2026-11-10", 197300)})

    def fx_boom(now):
        raise TimeoutError()

    for _ in range(2):  # 주말처럼 새 값이 없을 때 다시 돌려도 같은 행을 덮어쓸 뿐이다
        r = collect.run(conn, fetchers=fetchers, fx_fetch=fx_boom, now=kst(2026, 11, 11, 7, 30))
    assert r["fx"] is None and "FX" in r["errors"]
    assert conn.execute("SELECT COUNT(*) FROM quotes WHERE ticker='005930'").fetchone()[0] == 1
    assert db.latest_prices(conn, DOC, today=date(2026, 11, 11))["fx"] == 1362.7
