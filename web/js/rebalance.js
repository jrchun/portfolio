// 리밸런싱 계산. 순수 함수만 둔다(DOM·네트워크 접근 금지).
// reference/rebalance-board.html의 계산 로직을 그대로 옮긴 것이다. 바꾸면 tests/rebalance.test.js를 함께 확인한다.

export const keyOf = a => String(a.ticker || '').trim().toUpperCase();
export const isUSD = a => a.market === 'US';
export const floorTo = (q, unit) => unit > 0 ? Math.floor(q / unit + 1e-9) * unit : q;

/* ---------- 가격 ---------- */
// prices: { asOf, fx, quotes: { TICKER: { close, date } } }
export function makePricer(prices) {
  const quotes = prices?.quotes || {};
  const fxv = +prices?.fx > 0 ? +prices.fx : null;
  const quote = a => { const q = quotes[keyOf(a)]; return q && +q.close > 0 ? q : null; };
  const fx = () => fxv;
  // 종목 통화 기준 1단위 가격. 종가가 없으면 평균단가로 대신한다.
  const localPrice = a => { if (a.market === 'CASH') return 1; const q = quote(a); return q ? +q.close : (+a.avg || 0); };
  const krwPrice = a => { const p = localPrice(a); return isUSD(a) ? p * (fx() || 0) : p; };
  return { quote, fx, localPrice, krwPrice };
}

/* ---------- 배분 ---------- */
export function allocateContribution(values, weights, C) {
  const T2 = values.reduce((s, v) => s + v, 0) + C;
  const deficit = values.map((v, i) => Math.max(0, weights[i] * T2 - v));
  const D = deficit.reduce((s, d) => s + d, 0);
  if (D <= 0) return weights.map(w => w * C);
  if (D <= C) return deficit.map((d, i) => d + weights[i] * (C - D));
  return deficit.map(d => d / D * C);
}

export function maxDrift(values, weights) {
  const T = values.reduce((s, v) => s + v, 0); if (!T) return 0;
  return Math.max(0, ...values.map((v, i) => Math.abs(v / T * 100 - weights[i] * 100)));
}

// 정액식: 부족분에 배분 → 매매 단위로 내림 → 남은 돈으로 가장 부족한 단위부터 1단위씩 추가
export function planMonthly(A, vals, w, budget, krwPrice) {
  const n = A.length, price = A.map(krwPrice), unit = A.map(a => +a.unit || 1);
  const raw = allocateContribution(vals, w, budget);
  const q = raw.map((x, i) => price[i] > 0 ? floorTo(x / price[i], unit[i]) : 0);
  const T2 = vals.reduce((s, v) => s + v, 0) + budget;
  let spent = q.reduce((s, x, i) => s + x * price[i], 0);
  for (let guard = 0; guard < 500; guard++) {
    let best = -1, bestGap = 0;
    for (let i = 0; i < n; i++) {
      const step = unit[i] * price[i];
      if (!(price[i] > 0) || !(w[i] > 0) || step > budget - spent + 1e-6) continue;
      const gap = w[i] * T2 - (vals[i] + q[i] * price[i]);
      if (gap > bestGap) { bestGap = gap; best = i; }
    }
    if (best < 0) break;
    q[best] = +(q[best] + unit[best]).toFixed(8); spent += unit[best] * price[best];
  }
  const amt = q.map((x, i) => x * price[i]);
  const blocked = raw.map((x, i) => x >= 1 && q[i] <= 0);
  return { raw, q, amt, spent, blocked };
}

/* ---------- 그룹과 리밸런싱 단위 ---------- */
// 그룹이 없는 예전 문서: 종목마다 그룹 하나를 만들어 종목별 목표를 그대로 옮긴다.
export function ensureGroups(state) {
  if (!Array.isArray(state.groups)) {
    state.groups = [];
    state.assets.forEach((a, i) => { if (a.exclude) return; const id = 'g' + (i + 1); state.groups.push({ id, name: a.name, target: +a.target || 0, mode: 'ratio' }); a.group = id; });
  }
  return state;
}

// 리밸런싱 단위: 비율형 그룹은 종목마다 1단위, 대표형 그룹은 그룹 전체가 1단위
export function buildUnits(A, vals, groups) {
  groups = groups || [];
  const units = [], loose = [];
  const byG = new Map(groups.map(g => [g.id, []]));
  A.forEach((a, i) => { if (byG.has(a.group)) byG.get(a.group).push(i); else loose.push({ g: null, idx: [i], buy: i, sellOrder: [i], w: 0, val: vals[i], label: a.name }); });
  const live = groups.filter(g => byG.get(g.id).length);
  const tSum = live.reduce((x, g) => x + (+g.target || 0), 0);
  live.forEach(g => {
    const M = byG.get(g.id), gw = tSum ? (+g.target || 0) / tSum : 0;
    if (g.mode === 'lead' && M.length > 1) {
      const buy = M.find(i => keyOf(A[i]) === String(g.lead || '').toUpperCase()) ?? M[0];
      const sf = M.find(i => keyOf(A[i]) === String(g.sell || '').toUpperCase()) ?? buy;
      units.push({ g, idx: M, buy, sellOrder: [sf, ...M.filter(i => i !== sf)], w: gw, val: M.reduce((x, i) => x + vals[i], 0), label: g.name, lead: true });
    } else {
      const inn = M.map(i => Math.max(0, +(A[i].inner ?? 1) || 0)), sum = inn.reduce((x, y) => x + y, 0);
      M.forEach((i, k) => units.push({ g, idx: [i], buy: i, sellOrder: [i], w: gw * (sum ? inn[k] / sum : 1 / M.length), val: vals[i], label: A[i].name }));
    }
  });
  return { units: units.concat(loose), live, byG, tSum, loose };
}

/* ---------- 1월 정기 리밸런싱 ---------- */
// 단위별 목표 금액과의 차이만큼 매수(대표·해당 종목) 또는 매도(먼저 매도 종목부터)
// act[i]: null(유지) 또는 { q, amt, s }  (s: 1 매수, -1 매도)
export function planAnnual(A, units, T, budget, pricer) {
  const { krwPrice, localPrice, fx } = pricer;
  const TT = T + budget;
  let sells = 0, buys = 0, usGain = 0;
  const act = A.map(() => null);
  units.forEach(u => {
    const diff = u.w * TT - u.val;
    if (diff > 0) {
      const i = u.buy, up = krwPrice(A[i]), un = +A[i].unit || 1, q = up > 0 ? floorTo(diff / up, un) : 0;
      if (q > 0) { act[i] = { q, amt: q * up, s: 1 }; buys += q * up; }
    } else if (diff < 0) {
      let rem = -diff;
      for (const i of u.sellOrder) {
        const a = A[i], up = krwPrice(a), un = +a.unit || 1; if (!(up > 0)) continue;
        const q = Math.min(floorTo(rem / up, un), floorTo(+a.qty || 0, un));
        if (q > 0) { act[i] = { q, amt: q * up, s: -1 }; sells += q * up; rem -= q * up; if (isUSD(a)) usGain += q * (localPrice(a) - (+a.avg || 0)) * (fx() || 0); }
        if (rem < 1) break;
      }
    }
  });
  return { act, sells, buys, usGain };
}

/* ---------- 상태 판정 ---------- */
export function statusOf(md, band) {
  return md <= band / 2 ? 'ok' : md <= band ? 'warn' : 'bad';
}

// 적립만으로 밴드 안에 들어올 때까지 걸리는 개월 수(가격 변동 없다고 가정, 최대 120)
export function monthsToResolve(uv, uw, C, band) {
  let months = 0, v = uv.slice();
  while (maxDrift(v, uw) > band && months < 120) { const add = allocateContribution(v, uw, C); v = v.map((x, i) => x + add[i]); months++; }
  return months;
}

/* ---------- 대시보드에 필요한 계산 전체 ---------- */
export function computeBoard(state, prices) {
  const px = makePricer(prices);
  const { quote, fx, krwPrice } = px;
  const ALL = state.assets || [], A = ALL.filter(a => !a.exclude), EXA = ALL.filter(a => a.exclude);
  const exVal = EXA.reduce((x, a) => x + (+a.qty || 0) * krwPrice(a), 0);
  const vals = A.map(a => (+a.qty || 0) * krwPrice(a));
  const cost = A.map(a => (+a.qty || 0) * (+a.avg || 0) * (isUSD(a) ? (fx() || 0) : 1));
  const T = vals.reduce((s, v) => s + v, 0), TC = cost.reduce((s, v) => s + v, 0);
  const C = Math.max(0, +state.monthly || 0);
  const band = Math.max(0.1, +state.band || 5);
  const { units, live, byG, tSum, loose } = buildUnits(A, vals, state.groups);
  const uv = units.map(u => u.val), uw = units.map(u => u.w);

  const missing = A.filter(a => a.market !== 'CASH' && !quote(a));
  const needFx = A.some(isUSD) && !fx();

  const cur = vals.map(v => T ? v / T * 100 : 0);
  const uDrift = uv.map((v, k) => (T ? v / T * 100 : 0) - uw[k] * 100);
  const md = maxDrift(uv, uw);
  const mdIdx = uDrift.reduce((bi, d, i) => Math.abs(d) > Math.abs(uDrift[bi]) ? i : bi, 0);
  const pl = T - TC;
  const status = statusOf(md, band);
  const months = md > band && C > 0 ? monthsToResolve(uv, uw, C, band) : null;

  const carry = Math.max(0, +state.carry || 0), budget = C + carry;
  const UA = units.map(u => A[u.buy]);
  const plan = planMonthly(UA, uv, uw, budget, krwPrice);
  const after = uv.map((x, i) => x + plan.amt[i]);
  const T2 = after.reduce((s, x) => s + x, 0);
  const md2 = maxDrift(after, uw);

  const annual = planAnnual(A, units, T, budget, px);

  return {
    px, A, EXA, exVal, vals, cost, T, TC, C, band, carry, budget,
    units, live, byG, tSum, loose, uv, uw,
    missing, needFx, cur, uDrift, md, mdIdx, pl, status, months,
    UA, plan, after, T2, md2, annual,
  };
}
