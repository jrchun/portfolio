"""시드 파일(data/seed-portfolio.json, data/seed-prices.json)을 D1에 넣는 SQL로 바꾼다.

사용법: python3 scripts/seed_sql.py > seed.sql
        npx wrangler d1 execute rebalance-board --remote --file db/schema.sql
        npx wrangler d1 execute rebalance-board --remote --file seed.sql
포트폴리오가 이미 있으면 덮어쓰지 않는다(INSERT OR IGNORE). 가격은 시드 날짜로 넣고, 이후 수집값이 덮는다.
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def q(s) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def iso(mmdd: str, as_of: date) -> str:
    m = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})\s*", str(mmdd or ""))
    if not m:
        return as_of.isoformat()
    d = date(as_of.year, int(m.group(1)), int(m.group(2)))
    return (d.replace(year=d.year - 1) if d > as_of else d).isoformat()


def main() -> None:
    prefix = "seed" if (DATA / "seed-portfolio.json").exists() else "example"
    doc = json.loads((DATA / f"{prefix}-portfolio.json").read_text(encoding="utf-8"))
    prices = json.loads((DATA / f"{prefix}-prices.json").read_text(encoding="utf-8"))
    m = re.search(r"\d{4}-\d{2}-\d{2}", str(prices.get("asOf") or ""))
    as_of = date.fromisoformat(m.group(0)) if m else date.today()
    market = {str(a.get("ticker") or "").strip().upper(): a.get("market") for a in doc["assets"]}
    out = [
        "INSERT OR IGNORE INTO portfolio (id, doc, version, updated_at) VALUES (1, "
        + q(json.dumps(doc, ensure_ascii=False)) + ", 1, " + q(as_of.isoformat() + "T00:00:00Z") + ");"
    ]
    for t, v in (prices.get("quotes") or {}).items():
        k = t.strip().upper()
        out.append(
            f"INSERT OR IGNORE INTO quotes (ticker, date, close, currency, source) VALUES ({q(k)}, {q(iso(v.get('date'), as_of))}, "
            f"{float(v['close'])}, {q('USD' if market.get(k) == 'US' else 'KRW')}, {q(prefix)});"
        )
    if prices.get("fx"):
        out.append(f"INSERT OR IGNORE INTO fx (date, usdkrw, source) VALUES ({q(as_of.isoformat())}, {float(prices['fx'])}, {q(prefix)});")
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
