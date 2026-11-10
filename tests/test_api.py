"""API 테스트. 임시 DB와 임시 데이터 폴더를 쓰므로 실제 데이터는 건드리지 않는다."""
import json

import pytest
from fastapi.testclient import TestClient

from server import db

DOC = {
    "monthly": 100000,
    "carry": 0,
    "band": 5,
    "groups": [{"id": "g1", "name": "A", "target": 100, "mode": "ratio"}],
    "assets": [
        {"name": "가", "ticker": "111111", "market": "KR", "qty": 10, "avg": 1000, "unit": 1, "group": "g1"},
        {"name": "나", "ticker": "abc", "market": "US", "qty": 1, "avg": 10, "unit": 1, "group": "g1"},
        {"name": "현금", "ticker": "CASH-1", "market": "CASH", "qty": 5000, "avg": 1, "unit": 1},
    ],
}
PRICES = {
    "asOf": "2026-01-02 (잔고 화면 기준)",
    "fx": 1400.5,
    "quotes": {
        "111111": {"close": 1200, "date": "01/02"},
        "ABC": {"close": 12.5, "date": "12/31"},
        "ZZZ": {"close": 1, "date": "01/02"},
    },
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    (tmp_path / "seed-portfolio.json").write_text(json.dumps(DOC), encoding="utf-8")
    (tmp_path / "seed-prices.json").write_text(json.dumps(PRICES), encoding="utf-8")
    monkeypatch.setenv("REBALANCE_DB", str(tmp_path / "test.sqlite"))
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    from server.main import app

    with TestClient(app) as c:
        yield c


def test_seed_and_get_portfolio(client):
    r = client.get("/api/portfolio")
    assert r.status_code == 200
    assert r.json() == {"doc": DOC, "version": 1}


def test_put_bumps_version_and_persists(client):
    doc = {**DOC, "monthly": 200000}
    r = client.put("/api/portfolio", json={"doc": doc, "version": 1})
    assert r.status_code == 200 and r.json() == {"version": 2}
    assert client.get("/api/portfolio").json() == {"doc": doc, "version": 2}


def test_put_with_stale_version_returns_409_and_latest(client):
    first = {**DOC, "monthly": 1}
    assert client.put("/api/portfolio", json={"doc": first, "version": 1}).status_code == 200
    r = client.put("/api/portfolio", json={"doc": {**DOC, "monthly": 2}, "version": 1})
    assert r.status_code == 409
    assert r.json() == {"doc": first, "version": 2}
    assert client.get("/api/portfolio").json()["doc"]["monthly"] == 1


def test_put_rejects_doc_without_assets(client):
    assert client.put("/api/portfolio", json={"doc": {"monthly": 1}, "version": 1}).status_code == 422
    assert client.get("/api/portfolio").json()["version"] == 1


def test_prices_only_for_portfolio_tickers(client):
    r = client.get("/api/prices").json()
    assert r == {
        "asOf": "2026-01-02",
        "fx": 1400.5,
        # 종목 키는 대문자. 12/31은 기준일(1/2)보다 뒤일 수 없으므로 지난해 날짜로 저장된다.
        "quotes": {"111111": {"close": 1200, "date": "01/02"}, "ABC": {"close": 12.5, "date": "12/31"}},
    }
    conn = db.connect()
    rows = {r["ticker"]: (r["date"], r["currency"]) for r in conn.execute("SELECT * FROM quotes")}
    conn.close()
    assert rows["ABC"] == ("2025-12-31", "USD")
    assert rows["111111"] == ("2026-01-02", "KRW")


def test_seed_runs_only_once(client, tmp_path):
    client.put("/api/portfolio", json={"doc": {**DOC, "monthly": 7}, "version": 1})
    conn = db.connect()
    db.init(conn, tmp_path)
    assert db.get_portfolio(conn) == ({**DOC, "monthly": 7}, 2)
    conn.close()


def test_usage_log_records_open_and_save(client):
    client.get("/api/portfolio")
    client.put("/api/portfolio", json={"doc": DOC, "version": 1})
    conn = db.connect()
    events = [r["event"] for r in conn.execute("SELECT event FROM usage_log ORDER BY rowid")]
    conn.close()
    assert events == ["open", "save"]


def test_symbols_and_static(client):
    r = client.get("/api/symbols")
    assert r.status_code == 200 and "max-age" in r.headers["cache-control"]
    assert isinstance(r.json()[0], list)
    page = client.get("/")
    assert page.status_code == 200 and "내 리밸런싱 보드" in page.text
    assert client.get("/js/rebalance.js").status_code == 200


def test_falls_back_to_example_when_no_seed(tmp_path, monkeypatch):
    monkeypatch.setenv("REBALANCE_DB", str(tmp_path / "ex.sqlite"))
    conn = db.connect()
    db.init(conn)  # 실제 data/ 폴더: 테스트 환경에 seed가 있으면 seed, 없으면 example
    doc, version = db.get_portfolio(conn)
    conn.close()
    assert version == 1 and doc["assets"]
