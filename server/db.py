"""SQLite 스키마와 접근 함수.

파일 하나(`data/rebalance.sqlite`)에 모든 것을 둔다. 경로는 환경 변수 REBALANCE_DB로 바꿀 수 있다.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
KST = ZoneInfo("Asia/Seoul")

SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolio (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  doc TEXT NOT NULL,
  version INTEGER NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quotes (
  ticker TEXT NOT NULL,
  date TEXT NOT NULL,
  close REAL NOT NULL,
  currency TEXT NOT NULL,
  source TEXT NOT NULL,
  PRIMARY KEY (ticker, date)
);
CREATE TABLE IF NOT EXISTS fx (
  date TEXT PRIMARY KEY,
  usdkrw REAL NOT NULL,
  source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL,
  ticker TEXT NOT NULL,
  side TEXT NOT NULL,
  qty REAL NOT NULL,
  price REAL NOT NULL,
  currency TEXT NOT NULL,
  fx REAL,
  kind TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshots (
  date TEXT PRIMARY KEY,
  total REAL NOT NULL,
  doc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS usage_log (
  ts TEXT NOT NULL,
  event TEXT NOT NULL
);
"""


def db_path() -> Path:
    return Path(os.environ.get("REBALANCE_DB") or DATA_DIR / "rebalance.sqlite")


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    # 요청마다 연결을 새로 열고 닫는다. FastAPI가 의존성과 엔드포인트를 서로 다른 작업 스레드에서
    # 돌릴 수 있어 스레드 검사는 끈다(한 연결을 동시에 두 곳에서 쓰지는 않는다).
    conn = sqlite3.connect(str(path or db_path()), timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def key_of(asset: dict) -> str:
    """화면(`rebalance.js`의 keyOf)과 같은 종목 키."""
    return str(asset.get("ticker") or "").strip().upper()


# ---------- 초기화와 시드 ----------

def init(conn: sqlite3.Connection, data_dir: Path | None = None) -> None:
    """테이블을 만들고, 포트폴리오가 비어 있으면 시드 파일을 넣는다.

    `seed-*.json`(개인 데이터, 저장소에 없음)이 있으면 그것을, 없으면 `example-*.json`을 쓴다.
    """
    conn.executescript(SCHEMA)
    if conn.execute("SELECT 1 FROM portfolio WHERE id = 1").fetchone():
        return
    data_dir = data_dir or DATA_DIR
    for prefix in ("seed", "example"):
        pf, pr = data_dir / f"{prefix}-portfolio.json", data_dir / f"{prefix}-prices.json"
        if not pf.exists():
            continue
        doc = json.loads(pf.read_text(encoding="utf-8"))
        prices = json.loads(pr.read_text(encoding="utf-8")) if pr.exists() else {}
        with conn:
            conn.execute(
                "INSERT INTO portfolio (id, doc, version, updated_at) VALUES (1, ?, 1, ?)",
                (json.dumps(doc, ensure_ascii=False), now_iso()),
            )
            _seed_prices(conn, doc, prices, source=prefix)
        return
    with conn:
        conn.execute(
            "INSERT INTO portfolio (id, doc, version, updated_at) VALUES (1, ?, 1, ?)",
            (json.dumps({"monthly": 0, "carry": 0, "band": 5, "groups": [], "assets": []}), now_iso()),
        )


def _seed_prices(conn: sqlite3.Connection, doc: dict, prices: dict, source: str) -> None:
    m = re.search(r"\d{4}-\d{2}-\d{2}", str(prices.get("asOf") or ""))
    as_of = date.fromisoformat(m.group(0)) if m else date.today()
    market = {key_of(a): a.get("market") for a in doc.get("assets", [])}
    for ticker, q in (prices.get("quotes") or {}).items():
        try:
            close = float(q.get("close"))
        except (TypeError, ValueError):
            continue
        if not close > 0:
            continue
        key = str(ticker).strip().upper()
        conn.execute(
            "INSERT OR REPLACE INTO quotes (ticker, date, close, currency, source) VALUES (?, ?, ?, ?, ?)",
            (key, _seed_date(q.get("date"), as_of), close, "USD" if market.get(key) == "US" else "KRW", source),
        )
    try:
        fx = float(prices.get("fx") or 0)
    except (TypeError, ValueError):
        fx = 0
    if fx > 0:
        conn.execute(
            "INSERT OR REPLACE INTO fx (date, usdkrw, source) VALUES (?, ?, ?)",
            (as_of.isoformat(), fx, source),
        )


def _seed_date(text, as_of: date) -> str:
    """시드 파일의 'MM/DD'를 ISO 날짜로 바꾼다. 연도는 기준일에서 가져온다."""
    m = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})\s*", str(text or ""))
    if not m:
        return as_of.isoformat()
    try:
        d = date(as_of.year, int(m.group(1)), int(m.group(2)))
    except ValueError:
        return as_of.isoformat()
    if d > as_of:  # 기준일보다 뒤면 지난해 날짜다(1월 초에 12월 종가)
        d = d.replace(year=d.year - 1)
    return d.isoformat()


# ---------- 포트폴리오 ----------

def get_portfolio(conn: sqlite3.Connection) -> tuple[dict, int]:
    row = conn.execute("SELECT doc, version FROM portfolio WHERE id = 1").fetchone()
    return json.loads(row["doc"]), row["version"]


def put_portfolio(conn: sqlite3.Connection, doc: dict, version: int) -> int | None:
    """version이 서버와 같을 때만 저장하고 새 version을 돌려준다. 다르면 None."""
    with conn:
        cur = conn.execute(
            "UPDATE portfolio SET doc = ?, version = version + 1, updated_at = ? WHERE id = 1 AND version = ?",
            (json.dumps(doc, ensure_ascii=False), now_iso(), version),
        )
    return version + 1 if cur.rowcount == 1 else None


# ---------- 가격 ----------

STALE_BUSINESS_DAYS = 3


def business_days_since(day: date, today: date) -> int:
    """day 다음 날부터 어제까지의 평일 수. 공휴일은 따로 빼지 않는다."""
    n, d = 0, day
    while True:
        d = date.fromordinal(d.toordinal() + 1)
        if d >= today:
            return n
        if d.weekday() < 5:
            n += 1


def latest_prices(conn: sqlite3.Connection, doc: dict, today: date | None = None) -> dict:
    """포트폴리오 종목의 최신 종가와 환율(요청서 4.2 형식).

    종가가 3영업일 넘게 갱신되지 않은 종목에는 `"stale": true`를 붙인다.
    """
    today = today or datetime.now(KST).date()
    quotes: dict[str, dict] = {}
    dates: list[str] = []
    example = False
    for key in dict.fromkeys(key_of(a) for a in doc.get("assets", [])):
        if not key:
            continue
        row = conn.execute(
            "SELECT date, close, source FROM quotes WHERE ticker = ? ORDER BY date DESC LIMIT 1", (key,)
        ).fetchone()
        if not row:
            continue
        quotes[key] = {"close": row["close"], "date": f"{row['date'][5:7]}/{row['date'][8:10]}"}
        if business_days_since(date.fromisoformat(row["date"]), today) > STALE_BUSINESS_DAYS:
            quotes[key]["stale"] = True
        dates.append(row["date"])
        example = example or row["source"] == "example"
    out: dict = {"asOf": max(dates) if dates else None, "fx": None, "quotes": quotes}
    fx = conn.execute("SELECT usdkrw FROM fx ORDER BY date DESC LIMIT 1").fetchone()
    if fx:
        out["fx"] = fx["usdkrw"]
    if example:
        out["example"] = True
    return out


# ---------- 사용 기록 ----------

def log_usage(conn: sqlite3.Connection, event: str) -> None:
    with conn:
        conn.execute("INSERT INTO usage_log (ts, event) VALUES (?, ?)", (now_iso(), event))
