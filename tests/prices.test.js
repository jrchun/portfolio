// /api/prices가 쓰는 가격 문서 만들기(src/lib/prices.js)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildPrices, businessDaysSince, todayKST } from '../src/lib/prices.js';

test('평일 수: 금요일 종가를 화요일에 보면 월요일 하루', () => {
  assert.equal(businessDaysSince('2026-11-06', '2026-11-10'), 1);
  assert.equal(businessDaysSince('2026-11-10', '2026-11-11'), 0);
  assert.equal(businessDaysSince('2026-11-04', '2026-11-11'), 4);
});

test('서울 날짜: UTC 15시는 서울 다음 날 0시', () => {
  assert.equal(todayKST(Date.parse('2026-11-10T14:59:00Z')), '2026-11-10');
  assert.equal(todayKST(Date.parse('2026-11-10T15:00:00Z')), '2026-11-11');
});

test('포트폴리오 종목만, 3영업일 넘게 지난 종가에는 stale', () => {
  const doc = { assets: [{ ticker: '005930' }, { ticker: 'qqqm' }, { ticker: 'CASH-1' }] };
  const rows = [
    { ticker: '005930', date: '2026-11-10', close: 197300, source: 'naver' },
    { ticker: 'QQQM', date: '2026-11-03', close: 265.1, source: 'yfinance' },
    { ticker: 'ZZZ', date: '2026-11-10', close: 1, source: 'naver' },
  ];
  assert.deepEqual(buildPrices(doc, rows, { usdkrw: 1342.07 }, '2026-11-11'), {
    asOf: '2026-11-10',
    fx: 1342.07,
    quotes: { '005930': { close: 197300, date: '11/10' }, QQQM: { close: 265.1, date: '11/03', stale: true } },
  });
  assert.deepEqual(buildPrices({ assets: [] }, [], null, '2026-11-11'), { asOf: null, fx: null, quotes: {} });
});
