"""가격 수집 테스트. 네트워크 없이 응답을 흉내 낸다."""
import json
from datetime import date, datetime

import pytest

from server.prices import _common, collect, crypto, gold, kr, us
from server.store import SqliteStore

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
def store(tmp_path):
    st = SqliteStore(tmp_path / "t.sqlite")
    st.conn.execute("INSERT INTO portfolio (id, doc, version, updated_at) VALUES (1, ?, 1, 'x')", (json.dumps(DOC),))
    # 미국 종목의 직전 종가
    st.conn.execute("INSERT INTO quotes VALUES ('QQQM', '2026-11-06', 270.22, 'USD', 'yfinance')")
    st.conn.commit()
    yield st
    st.close()


def latest(st, ticker):
    return st.query("SELECT date, close FROM quotes WHERE ticker = ? ORDER BY date DESC LIMIT 1", (ticker,))[0]


def ok(prices):
    return lambda tickers, now: {t: (d, c, "test") for t, (d, c) in prices.items() if t in tickers}


def boom(tickers, now):
    raise ConnectionError("blocked")


def test_one_market_blocked_others_still_saved(store):
    """출처 하나를 일부러 막아도 나머지는 갱신되고, 막힌 종목은 직전 종가를 유지한다."""
    now = kst(2026, 11, 11, 7, 30)
    r = collect.run(store, fetchers={
        "KR": ok({"005930": ("2026-11-10", 197300)}),
        "US": boom,
        "GOLD": ok({"M04020000": ("2026-11-10", 177290)}),
        "CRYPTO": ok({"KRW-BTC": ("2026-11-10", 102254000)}),
    }, fx_fetch=lambda now: ("2026-11-10", 1342.07, "test"), now=now)
    assert sorted(u["ticker"] for u in r["updated"]) == ["005930", "KRW-BTC", "M04020000"]
    assert [f["ticker"] for f in r["failed"]] == ["QQQM"]
    assert "US" in r["errors"]
    assert latest(store, "005930") == {"date": "2026-11-10", "close": 197300}
    assert latest(store, "QQQM") == {"date": "2026-11-06", "close": 270.22}  # 직전 종가 유지
    assert store.query("SELECT usdkrw FROM fx") == [{"usdkrw": 1342.07}]
    assert store.query("SELECT COUNT(*) AS n FROM quotes WHERE ticker = 'CASH-1'") == [{"n": 0}]


def test_fx_failure_keeps_previous_rate_and_rerun_is_idempotent(store):
    store.conn.execute("INSERT INTO fx VALUES ('2026-11-09', 1362.7, 'test')")
    store.conn.commit()
    fetchers = {m: ok({}) for m in ("KR", "US", "GOLD", "CRYPTO")}
    fetchers["KR"] = ok({"005930": ("2026-11-10", 197300)})

    def fx_boom(now):
        raise TimeoutError()

    for _ in range(2):  # 주말처럼 새 값이 없을 때 다시 돌려도 같은 행을 덮어쓸 뿐이다
        r = collect.run(store, fetchers=fetchers, fx_fetch=fx_boom, now=kst(2026, 11, 11, 7, 30))
    assert r["fx"] is None and "FX" in r["errors"]
    assert store.query("SELECT COUNT(*) AS n FROM quotes WHERE ticker = '005930'") == [{"n": 1}]
    assert store.query("SELECT usdkrw FROM fx") == [{"usdkrw": 1362.7}]


def test_d1_store_sends_documented_query_shapes(monkeypatch):
    """D1 REST: 단일 {sql, params}, 여러 문장 {batch: [...]}. params는 문자열."""
    from server import store as store_mod

    sent = []

    class Resp:
        def __init__(self, body): self.body = body
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return json.dumps(self.body).encode()

    def fake_urlopen(req, timeout):
        sent.append((req.full_url, req.get_header("Authorization"), json.loads(req.data)))
        return Resp({"success": True, "result": [{"results": [{"doc": json.dumps(DOC)}], "success": True}]})

    monkeypatch.setattr(store_mod.urllib.request, "urlopen", fake_urlopen)
    st = store_mod.D1Store("acc", "dbid", "tok")
    assert st.get_doc() == DOC
    st.save([("005930", "2026-11-10", 197300.0, "KRW", "naver")], ("2026-11-10", 1342.07, "yfinance"))
    url, auth, body = sent[0]
    assert url == "https://api.cloudflare.com/client/v4/accounts/acc/d1/database/dbid/query"
    assert auth == "Bearer tok" and body == {"sql": "SELECT doc FROM portfolio WHERE id = 1", "params": []}
    batch = sent[1][2]["batch"]
    assert batch[0]["params"] == ["005930", "2026-11-10", "197300.0", "KRW", "naver"]
    assert batch[1]["sql"].startswith("INSERT OR REPLACE INTO fx")


def test_d1_store_retries_on_rate_limit(monkeypatch):
    import urllib.error
    from server import store as store_mod

    calls = []

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return json.dumps({"success": True, "result": [{"results": [], "success": True}]}).encode()

    def flaky(req, timeout):
        calls.append(1)
        if len(calls) < 3:
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {"Retry-After": "1"}, None)
        return Resp()

    monkeypatch.setattr(store_mod.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(store_mod.time, "sleep", lambda s: None)
    assert store_mod.D1Store("a", "b", "t").query("SELECT 1") == []
    assert len(calls) == 3
