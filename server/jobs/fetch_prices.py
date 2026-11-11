"""매일 아침 launchd가 실행하는 가격 수집 진입점.

실행: uv run python -m server.jobs.fetch_prices
출력은 launchd가 logs/fetch-prices.log에 남긴다. 받지 못한 종목이 있어도 종료 코드는 0이다
(직전 종가를 유지하고 화면에서 오래된 날짜로 드러난다). 한 종목도 받지 못했으면 1을 돌려준다.
"""
from __future__ import annotations

import sys

from .. import db
from ..prices import collect


def main() -> int:
    conn = db.connect()
    try:
        db.init(conn)
        r = collect.run(conn)
    finally:
        conn.close()
    print(f"[{r['ranAt']}] 가격 수집: 성공 {len(r['updated'])} · 실패 {len(r['failed'])}"
          + (f" · 환율 {r['fx']['usdkrw']} ({r['fx']['date']})" if r["fx"] else " · 환율 실패"), flush=True)
    for u in r["updated"]:
        print(f"  ok   {u['ticker']:<10} {u['date']} {u['close']:>14,.2f}  {u['source']:<8} {u['name']}")
    for f in r["failed"]:
        print(f"  FAIL {f['ticker']:<10} {f['market']:<6} {f['name']}")
    for k, v in r["errors"].items():
        print(f"  ERROR {k}: {v}")
    return 1 if r["failed"] and not r["updated"] else 0


if __name__ == "__main__":
    sys.exit(main())
