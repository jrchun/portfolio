// 가격 문서 만들기(순수 함수). /api/prices가 쓰고 tests/prices.test.js가 확인한다.

export const STALE_BUSINESS_DAYS = 3;

// 서울 기준 오늘 날짜(YYYY-MM-DD)
export function todayKST(nowMs = Date.now()) {
  return new Date(nowMs + 9 * 3600e3).toISOString().slice(0, 10);
}

// day 다음 날부터 today 전날까지의 평일 수. 공휴일은 따로 빼지 않는다.
export function businessDaysSince(day, today) {
  const d = new Date(day + 'T00:00:00Z'), end = new Date(today + 'T00:00:00Z');
  let n = 0;
  for (d.setUTCDate(d.getUTCDate() + 1); d < end; d.setUTCDate(d.getUTCDate() + 1)) {
    const w = d.getUTCDay();
    if (w !== 0 && w !== 6) n++;
  }
  return n;
}

export const keyOf = a => String(a?.ticker || '').trim().toUpperCase();

// rows: 종목별 최신 종가 [{ticker, date, close, source}], fxRow: {usdkrw} | null
// 결과: 요청서 4.2 형식 { asOf, fx, quotes: { TICKER: { close, date, stale? } }, example? }
export function buildPrices(doc, rows, fxRow, today) {
  const wanted = new Set((doc?.assets || []).map(keyOf).filter(Boolean));
  const quotes = {};
  const dates = [];
  let example = false;
  for (const r of rows) {
    if (!wanted.has(r.ticker)) continue;
    const q = { close: +r.close, date: r.date.slice(5, 7) + '/' + r.date.slice(8, 10) };
    if (businessDaysSince(r.date, today) > STALE_BUSINESS_DAYS) q.stale = true;
    quotes[r.ticker] = q;
    dates.push(r.date);
    example = example || r.source === 'example';
  }
  const out = { asOf: dates.length ? dates.sort().at(-1) : null, fx: fxRow ? +fxRow.usdkrw : null, quotes };
  if (example) out.example = true;
  return out;
}
