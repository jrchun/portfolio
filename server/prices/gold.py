"""KRX 금현물(1g) 종가. 네이버 증권 '국내 금'(코드 M04020000), 키 불필요. 공식 문서가 없는 주소다.

응답: [{"localTradedAt": "2026-11-10T00:00:00+09:00", "closePrice": "177,290", ...}, ...] (최신순)
오늘 행은 장 시작 전에는 전일 값으로 미리 채워져 있고 장중에는 실시간 값이므로, 마감 뒤에만 받는다.
KRX 정보데이터시스템은 금 시세 화면에 로그인이 필요하고, 공공데이터포털 API는 키가 필요하며
기준일 다음 영업일 13시 이후에 갱신돼 아침 수집에 맞지 않아 쓰지 않는다(2단계 조사 결과).
"""
from __future__ import annotations

from datetime import date, datetime, time

from . import _common

CODE = "M04020000"
URL = "https://api.stock.naver.com/marketindex/metals/" + CODE + "/prices?page=1&pageSize=10"
CLOSE_AFTER = time(16, 0)  # 15:30 마감 + 여유


def parse(rows: list, now: datetime) -> tuple[str, float] | None:
    best = None
    for r in rows:
        try:
            d = date.fromisoformat(str(r["localTradedAt"])[:10])
            close = float(str(r["closePrice"]).replace(",", ""))
        except (KeyError, TypeError, ValueError):
            continue
        if close > 0 and _common.is_final(d, now, _common.KST, CLOSE_AFTER) and (best is None or d > best[0]):
            best = (d, close)
    return (best[0].isoformat(), best[1]) if best else None


def fetch(tickers: list[str], now: datetime | None = None) -> dict[str, tuple[str, float, str]]:
    now = now or _common.now_kst()
    wanted = [t for t in tickers if t.strip().upper() == CODE]
    if not wanted:
        return {}
    r = parse(_common.get_json(URL), now)
    return {t: (r[0], r[1], "naver") for t in wanted} if r else {}
