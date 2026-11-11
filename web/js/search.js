// 종목 검색. web/symbols.json의 각 행은
// [코드, 이름, 상장구분, 시가총액(억원), 별칭('|' 구분), 보조순위, 자산군] 이다.

export const norm = t => String(t).toLowerCase().replace(/[\s\-_.()&]/g, '');
export const FILTER = { all: null, kr: ['KS', 'KE'], us: ['US', 'UE'], gd: ['GD'], cr: ['CR'] };

// 검색용 필드를 행에 붙이고, 코드로 찾는 Map을 돌려준다.
export function indexSymbols(rows) {
  const byCode = new Map();
  rows.forEach(r => {
    r.n = norm(r[1]); r.c = norm(r[0]); r.a = norm(r[4]);
    r.w = r[4] ? String(r[4]).split('|').map(norm) : null;
    byCode.set(String(r[0]).toUpperCase(), r);
  });
  return byCode;
}

// 1순위: 유사도 단계
export function similarity(r, nq) {
  if (r.c === nq) return 100;
  if (r.n === nq) return 95;
  if (r.w && r.w.includes(nq)) return 90;
  if (r.n.startsWith(nq)) return 80;
  if (r.c.startsWith(nq)) return 75;
  if (r.a && r.a.includes(nq)) return 60;
  if (r.n.includes(nq)) return 50;
  return 0;
}

// 2순위: 시가총액, 3순위: 보조순위(ETF 거래대금·인기순), 4순위: 이름순
function byRank(x, y) {
  return (y.s - x.s) || ((+y.r[3] || 0) - (+x.r[3] || 0)) || ((+y.r[5] || 0) - (+x.r[5] || 0)) || x.r[1].localeCompare(y.r[1], 'ko');
}

export function search(rows, q, filter = 'all') {
  const nq = norm(q), allow = FILTER[filter];
  const pool = allow ? rows.filter(r => allow.includes(r[2])) : rows;
  // 검색어가 없어도 금·코인은 목록이 짧아 전부 보여 준다.
  if (!nq) return (filter === 'gd' || filter === 'cr') ? pool.map(r => ({ r, s: 0 })).sort(byRank).map(x => x.r) : [];
  const out = [];
  for (const r of pool) { const sc = similarity(r, nq); if (sc) out.push({ r, s: sc }); }
  return out.sort(byRank).slice(0, 30).map(x => x.r);
}
