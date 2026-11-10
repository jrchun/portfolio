// 종목 검색 정렬 규칙(요청서 7.4)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { indexSymbols, search, norm } from '../web/js/search.js';

const rows = [
  ['005930', '삼성전자', 'KS', 100, '', 0, 'KS'],
  ['005935', '삼성전자우', 'KS', 10, '', 0, 'KS'],
  ['000001', '신삼성전자', 'KS', 999, '', 0, 'KS'],
  ['AAPL', 'Apple Inc.', 'US', 500, '애플', 0, 'GS'],
  ['QQQ', 'Invesco QQQ (Nasdaq-100)', 'UE', 0, '나스닥100', 5, 'GS'],
  ['QQQM', 'Invesco Nasdaq 100', 'UE', 0, '나스닥100', 9, 'GS'],
  ['KRW-BTC', '비트코인', 'CR', 0, 'BTC|bitcoin', 10, 'CR'],
];
indexSymbols(rows);
const codes = (q, f) => search(rows, q, f).map(r => r[0]);

test('공백·기호를 지우고 소문자로 비교한다', () => {
  assert.equal(norm('S&P (500)-a_b.c'), 'sp500abc');
});
test('이름 일치 > 이름이 검색어로 시작 > 이름에 포함(시총이 커도 뒤)', () => {
  assert.deepEqual(codes('삼성전자'), ['005930', '005935', '000001']);
});
test('별칭 일치로 찾고, 같은 단계에서는 보조순위가 높은 쪽이 먼저', () => {
  assert.deepEqual(codes('애플'), ['AAPL']);
  assert.deepEqual(codes('나스닥100'), ['QQQM', 'QQQ']);
});
test('코드 일치가 가장 먼저', () => {
  assert.deepEqual(codes('qqq'), ['QQQ', 'QQQM']);
});
test('필터: 검색어 없이도 코인 목록은 보여 주고, 전체는 비운다', () => {
  assert.deepEqual(codes('', 'cr'), ['KRW-BTC']);
  assert.deepEqual(codes('', 'all'), []);
  assert.deepEqual(codes('삼성', 'us'), []);
});
