"""가격 수집기가 읽고 쓰는 저장소.

- D1Store: 운영. Cloudflare D1 REST API(POST /accounts/{account_id}/d1/database/{database_id}/query).
  GitHub Actions가 환경 변수 CF_ACCOUNT_ID, CF_D1_DATABASE_ID, CLOUDFLARE_API_TOKEN(D1 Write 권한)으로 연결한다.
- SqliteStore: 테스트·로컬 시험용. 같은 스키마(db/schema.sql)를 쓴다.
"""
from __future__ import annotations

import json
import os
import sqlite3
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
QUOTE_SQL = "INSERT OR REPLACE INTO quotes (ticker, date, close, currency, source) VALUES (?, ?, ?, ?, ?)"
FX_SQL = "INSERT OR REPLACE INTO fx (date, usdkrw, source) VALUES (?, ?, ?)"


def key_of(asset: dict) -> str:
    """화면(`rebalance.js`의 keyOf)과 같은 종목 키."""
    return str(asset.get("ticker") or "").strip().upper()


class SqliteStore:
    def __init__(self, path: str | Path):
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def query(self, sql: str, params=()) -> list[dict]:
        return [dict(r) for r in self.conn.execute(sql, params)]

    def get_doc(self) -> dict:
        row = self.conn.execute("SELECT doc FROM portfolio WHERE id = 1").fetchone()
        return json.loads(row["doc"]) if row else {"assets": []}

    def save(self, quotes: list[tuple], fx: tuple | None) -> None:
        with self.conn:
            self.conn.executemany(QUOTE_SQL, quotes)
            if fx:
                self.conn.execute(FX_SQL, fx)

    def close(self) -> None:
        self.conn.close()


class D1Store:
    API = "https://api.cloudflare.com/client/v4/accounts/{account}/d1/database/{db}/query"

    def __init__(self, account_id: str, database_id: str, token: str):
        self.url = self.API.format(account=account_id, db=database_id)
        self.token = token

    @classmethod
    def from_env(cls) -> "D1Store":
        missing = [k for k in ("CF_ACCOUNT_ID", "CF_D1_DATABASE_ID", "CLOUDFLARE_API_TOKEN") if not os.environ.get(k)]
        if missing:
            raise SystemExit("환경 변수가 없습니다: " + ", ".join(missing))
        return cls(os.environ["CF_ACCOUNT_ID"], os.environ["CF_D1_DATABASE_ID"], os.environ["CLOUDFLARE_API_TOKEN"])

    def _post(self, body: dict) -> list[dict]:
        req = urllib.request.Request(
            self.url, data=json.dumps(body).encode(), method="POST",
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            out = json.loads(r.read().decode())
        if not out.get("success"):
            raise RuntimeError(f"D1 오류: {out.get('errors')}")
        return out["result"]

    @staticmethod
    def _stmt(sql: str, params=()) -> dict:
        # REST API의 params는 문자열 목록이다. 숫자 열은 SQLite 자료형 규칙에 따라 숫자로 저장된다.
        return {"sql": sql, "params": [str(p) for p in params]}

    def query(self, sql: str, params=()) -> list[dict]:
        return self._post(self._stmt(sql, params))[0]["results"]

    def get_doc(self) -> dict:
        rows = self.query("SELECT doc FROM portfolio WHERE id = 1")
        return json.loads(rows[0]["doc"]) if rows else {"assets": []}

    def save(self, quotes: list[tuple], fx: tuple | None) -> None:
        batch = [self._stmt(QUOTE_SQL, q) for q in quotes] + ([self._stmt(FX_SQL, fx)] if fx else [])
        if batch:
            self._post({"batch": batch})

    def close(self) -> None:
        pass
