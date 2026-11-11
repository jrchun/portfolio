-- 내 리밸런싱 보드 D1(SQLite) 스키마. 여러 번 실행해도 안전하다.
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
