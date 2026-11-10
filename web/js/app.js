// 화면 렌더링과 이벤트. 계산은 rebalance.js의 결과만 그린다.
import { keyOf, isUSD, makePricer, ensureGroups, computeBoard } from './rebalance.js';
import { won, wonShort, signedWon, pct, spct, pp, esc, fmtQty, fmtLocal, unitWord, capText } from './format.js';
import { indexSymbols, search } from './search.js';
import * as api from './api.js';

const $ = id => document.getElementById(id);
const CACHE = 'rebalance-board-cache-v1'; // 직전에 서버에서 받은 값(첫 화면용). 기준은 항상 서버다.

let state = null;            // 포트폴리오 문서
let version = 0;             // 서버가 붙인 문서 버전
let prices = { quotes: {} }; // { asOf, fx, quotes: { TICKER: { close, date } } }
let px = makePricer(prices);
let SYM = [], SYM_BY_CODE = new Map();

const MARKETS = { KR: '국내상장', US: '해외상장', GOLD: '금현물', CRYPTO: '코인', CASH: '현금·예금 (원화 금액)' };
const TYPE_MARKET = { KS: 'KR', KE: 'KR', US: 'US', UE: 'US', GD: 'GOLD', CR: 'CRYPTO' };
const CLASSES = { KS: ['국내주식', 'var(--k1)'], GS: ['해외주식', 'var(--k2)'], BD: ['채권', 'var(--k3)'], CM: ['금·원자재', 'var(--k4)'], RE: ['리츠·부동산', 'var(--k5)'], CA: ['현금성', 'var(--k6)'], CR: ['가상자산', 'var(--k7)'] };
const LISTING = { KS: '국내상장 주식', KE: '국내상장 ETF', US: '미국상장 주식', UE: '미국상장 ETF', GD: 'KRX 현물', CR: '업비트', CS: '현금·예금' };
const ACCOUNTS = ['일반', 'ISA', '연금저축', 'IRP', '업비트', '기타'];
const GCOLORS = ['var(--k1)', 'var(--k2)', 'var(--k3)', 'var(--k4)', 'var(--k5)', 'var(--k7)', 'var(--k6)'];

function autoClass(a) { const r = SYM_BY_CODE.get(keyOf(a)); return r && r[6] ? r[6] : ({ KR: 'KS', US: 'GS', GOLD: 'CM', CRYPTO: 'CR', CASH: 'CA' })[a.market] || 'KS'; }
function clsOf(a) { return CLASSES[a.cls] ? a.cls : autoClass(a); }
const clsChip = c => `<span class="type k" style="--c:${CLASSES[c][1]}">${CLASSES[c][0]}</span>`;
const acct = a => a.account && a.account !== '일반' ? ' · ' + esc(a.account) : '';
function typeOf(a) { const r = SYM_BY_CODE.get(keyOf(a)); return r ? r[2] : ({ KR: 'KS', US: 'US', GOLD: 'GD', CRYPTO: 'CR', CASH: 'CS' })[a.market] || 'KS'; }
const setSaveState = t => { $('saveState').textContent = t; };

/* ---------- 대시보드 ---------- */
function renderBoard() {
  if (!state) return;
  const b = computeBoard(state, prices);
  const { A, EXA, exVal, vals, cost, T, TC, C, band, units, live, byG, tSum, loose, uv, uw, cur, uDrift, md, mdIdx, pl } = b;
  const { quote, fx, krwPrice } = b.px;
  $('exampleTag').hidden = !state.example;

  // 가격 상태
  $('priceLine').innerHTML = prices.asOf
    ? `<span>가격 기준 <b>${esc(prices.asOf)}</b></span>${fx() ? `<span>환율 <b>${fx().toLocaleString('ko-KR')}</b>원</span>` : ''}${prices.example ? '<span class="example">예시 가격</span>' : ''}`
    : '<span>가격 정보가 아직 없습니다</span>';
  const warns = [];
  if (b.missing.length) warns.push(`가격을 찾지 못한 자산은 평균단가로 계산했습니다: ${b.missing.map(a => esc(a.name || a.ticker || '이름 없음')).join(', ')}.`);
  if (b.needFx) warns.push('환율 정보가 없어 미국 자산 평가액을 계산할 수 없습니다.');
  if (loose.length) warns.push(`그룹에 넣지 않은 종목은 목표 비중 0%로 계산됩니다: ${loose.map(u => esc(u.label)).join(', ')}. 포트폴리오 탭에서 그룹을 지정해 주세요.`);
  $('priceWarn').hidden = !warns.length; $('priceWarn').innerHTML = warns.join('<br>');

  // 요약
  $('sTotal').textContent = wonShort(T);
  $('sPL').innerHTML = (TC ? `<span class="${pl >= 0 ? 'up' : 'down'}">${signedWon(pl)} (${spct(pl / TC * 100)})</span>` : '') + (exVal ? `<br>제외 자산 포함 ${wonShort(T + exVal)}` : '');
  $('sDrift').textContent = md.toFixed(1) + '%p';
  $('sDriftSub').textContent = units.length ? (units[mdIdx].label + ' ' + pp(uDrift[mdIdx])) : '';
  const stLabel = { ok: '양호', warn: '주의', bad: '리밸런싱 필요' }[b.status];
  $('sStatus').innerHTML = `<span class="pill ${b.status}">${stLabel}</span>`;
  $('sStatusSub').textContent = '허용 밴드 ±' + band + '%p 기준';
  $('sMonths').textContent = b.months != null ? (b.months >= 120 ? '10년+' : b.months + '개월') : md <= band ? '해당 없음' : '적립금 없음';

  // 비중 막대
  function barRows(items) {
    const maxScale = Math.max(10, ...items.map(x => Math.max(x.cur, (x.tgt ?? 0) + band))) * 1.08;
    const sc = x => Math.min(100, Math.max(0, x / maxScale * 100));
    return items.map(it => {
      if (it.tgt == null) return `<div class="bar-row">
        <div class="bar-name" title="${esc(it.name)}">${esc(it.name)}</div>
        <div class="track" role="img" aria-label="${esc(it.name)} 현재 ${pct(it.cur)}"><div class="fill" style="width:${sc(it.cur)}%;opacity:.55"></div></div>
        <div class="bar-meta">${pct(it.cur)}<span class="d">${esc(it.note || '')}</span></div></div>`;
      const d = it.cur - it.tgt, ad = Math.abs(d);
      const cls = ad > band ? 'far' : ad > band / 2 ? 'over' : '';
      const dcls = ad > band ? 'big' : d > 0 ? 'pos' : 'neg';
      return `<div class="bar-row">
        <div class="bar-name" title="${esc(it.name)}">${esc(it.name)}</div>
        <div class="track" role="img" aria-label="${esc(it.name)} 현재 ${pct(it.cur)}, 목표 ${pct(it.tgt)}">
          <div class="band" style="left:${sc(it.tgt - band)}%;width:${sc(it.tgt + band) - sc(it.tgt - band)}%"></div>
          <div class="fill ${cls}" style="width:${sc(it.cur)}%"></div>
          <div class="tick" style="left:calc(${sc(it.tgt)}% - 1px)"></div>
        </div>
        <div class="bar-meta">${pct(it.cur)} / ${pct(it.tgt)}<span class="d ${dcls}">${pp(d)}</span></div>
      </div>`;
    }).join('');
  }
  const gItems = live.map(g => ({ name: g.name, cur: byG.get(g.id).reduce((x, i) => x + cur[i], 0), tgt: tSum ? (+g.target || 0) / tSum * 100 : 0 }));
  if (loose.length) gItems.push({ name: '미분류', cur: loose.reduce((x, u) => x + (T ? u.val / T * 100 : 0), 0), tgt: 0 });
  $('classBars').innerHTML = barRows(gItems) || '<p class="hint">포트폴리오 탭에서 그룹을 만들면 그룹별 비중이 표시됩니다.</p>';
  const unitOf = i => units.find(u => u.idx.includes(i));
  $('bars').innerHTML = barRows(A.map((a, i) => { const u = unitOf(i); return u.lead ? { name: a.name, cur: cur[i], tgt: null, note: u.label + ' 합산' } : { name: a.name, cur: cur[i], tgt: u.w * 100 }; })) || '<p class="hint">보유 자산 탭에서 종목을 추가하면 비중이 표시됩니다.</p>';

  // 보유 현황
  $('tblHold').innerHTML = `<thead><tr><th>자산</th><th>현재가</th><th>평균단가</th><th>평가액</th><th>평가손익</th><th>수익률</th></tr></thead><tbody>` +
    A.map((a, i) => {
      const p = cost[i] ? (vals[i] - cost[i]) : 0, r = cost[i] ? p / cost[i] * 100 : 0, cl = p >= 0 ? 'up' : 'down', cash = a.market === 'CASH';
      return `<tr><td>${esc(a.name)}<small>${cash ? '현금·예금' : fmtQty(+a.qty || 0, +a.unit || 1) + unitWord(a)}${acct(a)}</small></td>
        <td>${cash ? '–' : quote(a) ? fmtLocal(quote(a).close, a) : '<span class="d pos">없음</span>'}</td><td>${cash ? '–' : fmtLocal(+a.avg || 0, a)}</td>
        <td>${wonShort(vals[i])}</td><td class="${cl}">${signedWon(p)}</td><td class="${cl}">${spct(r)}</td></tr>`;
    }).join('') +
    EXA.map(a => `<tr><td>${esc(a.name)}<small>리밸런싱 제외</small></td><td>–</td><td>–</td><td>${wonShort((+a.qty || 0) * krwPrice(a))}</td><td>–</td><td>–</td></tr>`).join('') +
    `</tbody><tfoot><tr><td>투자자산 합계</td><td></td><td></td><td>${wonShort(T)}</td><td class="${pl >= 0 ? 'up' : 'down'}">${signedWon(pl)}</td><td class="${pl >= 0 ? 'up' : 'down'}">${TC ? spct(pl / TC * 100) : '–'}</td></tr></tfoot>`;

  // 이번 달 적립 배분(정액식)
  const { carry, budget, UA, plan, after, T2, md2 } = b;
  $('monthlyHint').textContent = `예산 ${wonShort(budget)}` + (carry ? ` (적립 ${wonShort(C)} + 이월 ${wonShort(carry)})` : '') + ' · 매도 없이 부족한 쪽부터 채웁니다';
  const side = (a, s) => a.market === 'CASH' ? (s > 0 ? '입금' : '출금') : (s > 0 ? '매수' : '매도');
  const sub = (u, a) => `${u.g ? esc(u.g.name) : '미분류'}${acct(a)}`;
  $('tblMonthly').innerHTML = `<thead><tr><th>살 종목</th><th>배정액</th><th>매수 수량</th><th>실제 매수액</th><th>매수 후 비중</th><th>목표</th></tr></thead><tbody>` +
    units.map((u, i) => {
      const a = UA[i]; return `<tr><td>${esc(a.name)}<small>${sub(u, a)}${a.market === 'CASH' ? '' : ' · 1' + unitWord(a) + ' ' + won(krwPrice(a))}</small></td><td>${plan.raw[i] >= 1 ? won(plan.raw[i]) : '–'}</td>
      <td>${plan.q[i] > 0 ? `<span class="act buy">${side(a, 1)}</span> ${fmtQty(plan.q[i], +a.unit || 1)}` : plan.blocked[i] ? '<span class="act hold">이번 달 보류</span>' : '<span class="act hold">유지</span>'}</td>
      <td>${plan.amt[i] > 0 ? won(plan.amt[i]) : '–'}</td><td>${T2 ? pct(after[i] / T2 * 100) : '–'}</td><td>${pct(uw[i] * 100)}</td></tr>`;
    }).join('') +
    `</tbody><tfoot><tr><td>합계</td><td>${won(budget)}</td><td></td><td>${won(plan.spent)}</td><td></td><td></td></tr></tfoot>`;
  const blockedNames = units.filter((u, i) => plan.blocked[i]).map(u => esc(A[u.buy].name));
  $('monthlyNote').innerHTML = budget > 0
    ? `매수 후 최대 이탈은 <b>${md.toFixed(1)}%p → ${md2.toFixed(1)}%p</b>입니다. 남는 현금 <b>${won(budget - plan.spent)}</b>은 다음 달 이월 현금으로 넣어 주세요.` +
      (blockedNames.length ? `<br>${blockedNames.join(', ')}은(는) 배정액이 매매 단위 가격보다 작아 이번 달은 사지 않습니다. 부족분이 쌓이면 다음 달에 우선 배정됩니다.` : '')
    : '포트폴리오 탭에서 월 적립금을 입력하면 이번 달 매수안을 계산합니다.';

  // 1월 정기 리밸런싱
  const { act, sells, buys, usGain } = b.annual;
  $('tblAnnual').innerHTML = `<thead><tr><th>자산</th><th>현재</th><th>매매</th><th>금액</th></tr></thead><tbody>` +
    A.map((a, i) => {
      const x = act[i], u = unitOf(i);
      const tag = !x ? '<span class="act hold">유지</span>' : `<span class="act ${x.s < 0 ? 'sell' : 'buy'}">${side(a, x.s)}</span> ${fmtQty(x.q, +a.unit || 1)}`;
      return `<tr><td>${esc(a.name)}<small>${sub(u, a)}</small></td><td>${wonShort(vals[i])}</td><td>${tag}</td><td>${x ? (x.s < 0 ? '−' : '+') + won(x.amt) : '–'}</td></tr>`;
    }).join('') + `</tbody>`;
  const taxLine = usGain > 0
    ? ` 미국 상장 자산 매도로 생기는 양도차익은 약 <b>${won(usGain)}</b>입니다(현재 환율로 단순 환산). 연 250만 원 공제를 넘는 부분은 22% 과세 대상입니다.`
    : '';
  $('annualNote').innerHTML = `매도 <b>${won(sells)}</b> · 매수 <b>${won(buys)}</b> · 적립금·이월 현금 <b>${won(budget)}</b> 반영 후 남는 현금 <b>${won(budget + sells - buys)}</b>. 매도 대금이 들어온 뒤 매수하세요.${taxLine}`;
}

/* ---------- 보유 자산 편집 ---------- */
function priceCell(a) {
  if (a.market === 'CASH') return `<div class="price-ro"><span>현금·예금</span><b>금액을 수량에 입력</b></div>`;
  const q = px.quote(a);
  if (q) return `<div class="price-ro"><span>전일 종가${q.date ? ' · ' + esc(q.date) : ''}</span><b>${fmtLocal(q.close, a)}</b></div>`;
  return `<div class="price-ro missing"><span>전일 종가</span><b>${a.ticker ? '찾지 못함' : '종목코드 필요'}</b></div>`;
}
function totalLine(a) {
  const v = (+a.qty || 0) * px.krwPrice(a), c = (+a.qty || 0) * (+a.avg || 0) * (isUSD(a) ? (px.fx() || 0) : 1), p = v - c;
  return `<span>평가액 <span class="num">${won(v)}</span></span><span class="${p >= 0 ? 'up' : 'down'} num">${signedWon(p)}${c ? ' (' + spct(p / c * 100) + ')' : ''}</span>`;
}
function renderAssets() {
  const A = state.assets || [];
  $('assets').innerHTML = A.map((a, i) => `
    <div class="asset" data-i="${i}">
      <div class="field f-name"><label for="n${i}">자산명</label><input id="n${i}" data-k="name" value="${esc(a.name)}"></div>
      ${a.manual ? `<div class="field f-tk"><label for="k${i}">종목코드</label><input id="k${i}" data-k="ticker" value="${esc(a.ticker)}" autocapitalize="characters" spellcheck="false"></div>
      <div class="field f-mk"><label for="m${i}">시장</label><select id="m${i}" data-k="market">${Object.entries(MARKETS).map(([k, v]) => `<option value="${k}" ${a.market === k ? 'selected' : ''}>${v}</option>`).join('')}</select></div>`
      : `<div class="code-ro f-tk">${LISTING[typeOf(a)] || '종목코드'}<span class="c">${esc(a.ticker)}</span></div><div class="code-ro f-mk">자산군<span>${clsChip(clsOf(a))}</span></div>`}
      <div class="field f-ac"><label for="ac${i}">계좌</label><select id="ac${i}" data-k="account">${ACCOUNTS.map(v => `<option ${(a.account || '일반') === v ? 'selected' : ''}>${v}</option>`).join('')}</select></div>
      <div class="field f-unit"><label for="u${i}">매매 단위</label><select id="u${i}" data-k="unit">
        <option value="1" ${+a.unit === 1 ? 'selected' : ''}>1${unitWord(a)}</option><option value="0.01" ${+a.unit === 0.01 ? 'selected' : ''}>0.01</option><option value="0.0001" ${+a.unit === 0.0001 ? 'selected' : ''}>0.0001</option></select></div>
      <div class="field f-qty"><label for="q${i}">보유 수량 (${unitWord(a)})</label><input id="q${i}" class="num" data-k="qty" type="number" step="any" inputmode="decimal" value="${esc(a.qty)}"></div>
      <div class="field f-avg"><label for="a${i}">평균단가 (${isUSD(a) ? '$' : '원'})</label><input id="a${i}" class="num" data-k="avg" type="number" step="any" inputmode="decimal" value="${esc(a.avg)}"></div>
      ${priceCell(a)}
      <button class="del" type="button" data-del="${i}" aria-label="${esc(a.name)} 삭제">✕</button>
      <div class="asset-total">${totalLine(a)}</div>
      <label class="excl"><input type="checkbox" data-k="exclude" ${a.exclude ? 'checked' : ''}> 리밸런싱에서 제외 (전세보증금처럼 사고팔 수 없는 자산)</label>
    </div>`).join('') || '<p class="hint">아직 자산이 없습니다. 위에서 종목을 검색해 추가하세요.</p>';
}
function refreshAssetMeta() {
  document.querySelectorAll('.asset').forEach(el => {
    const a = state.assets[+el.dataset.i]; if (!a) return;
    el.querySelector('.price-ro').outerHTML = priceCell(a);
    el.querySelector('.asset-total').innerHTML = totalLine(a);
  });
}

/* ---------- 포트폴리오(그룹과 목표) ---------- */
function members(g) { return state.assets.map((a, i) => [a, i]).filter(([a]) => !a.exclude && a.group === g.id); }
function groupOptions(sel) { return `<option value="">미분류</option>` + state.groups.map(g => `<option value="${esc(g.id)}" ${g.id === sel ? 'selected' : ''}>${esc(g.name)}</option>`).join(''); }
function memRow(a, i, showInner) {
  return `<div class="mem">
    <div class="tgt-name"><b>${esc(a.name)}</b><span class="meta"><select class="cls-sel" data-move="${i}" aria-label="${esc(a.name)} 그룹 이동">${groupOptions(a.group)}</select><span class="sub-code">${esc(a.account || '일반')} · ${LISTING[typeOf(a)] || ''}</span></span></div>
    <div class="tgt-cur" data-cur="${i}"></div>
    ${showInner ? `<div class="tgt-in ratio"><input id="in${i}" class="num" data-inner="${i}" type="number" step="1" min="0" inputmode="decimal" value="${esc(a.inner ?? 1)}" aria-label="${esc(a.name)} 그룹 내 비율"></div>` : '<div></div>'}
  </div>`;
}
function renderTargets() {
  ensureGroups(state);
  const G = state.groups;
  const html = G.map((g, gi) => {
    const M = members(g), multi = M.length > 1, lead = g.mode === 'lead' && multi;
    const opts = sel => M.map(([a]) => `<option value="${esc(keyOf(a))}" ${keyOf(a) === String(sel || '').toUpperCase() ? 'selected' : ''}>${esc(a.name)} (${esc(a.account || '일반')})</option>`).join('');
    return `<div class="grp" data-g="${esc(g.id)}">
      <div class="grp-head">
        <i class="sw" style="background:${GCOLORS[gi % GCOLORS.length]}"></i>
        <input id="gn-${esc(g.id)}" class="gname" data-gk="name" value="${esc(g.name)}" aria-label="그룹 이름">
        <span class="tgt-cur" data-gcur="${esc(g.id)}"></span>
        <div class="tgt-in"><input id="gt-${esc(g.id)}" class="num" data-gk="target" type="number" step="0.5" min="0" max="100" inputmode="decimal" value="${esc(g.target ?? 0)}" aria-label="${esc(g.name)} 목표 비중"></div>
        <button class="del" type="button" data-gdel="${esc(g.id)}" aria-label="${esc(g.name)} 그룹 삭제">✕</button>
      </div>
      ${multi ? `<div class="grp-rule"><label>규칙 <select data-gk="mode"><option value="ratio" ${!lead ? 'selected' : ''}>비율대로 나눠 사기</option><option value="lead" ${lead ? 'selected' : ''}>대표 종목만 사기</option></select></label>
        ${lead ? `<label>매수 <select data-gk="lead">${opts(g.lead || keyOf(M[0][0]))}</select></label><label>먼저 매도 <select data-gk="sell">${opts(g.sell || g.lead || keyOf(M[0][0]))}</select></label>` : '<span>아래 비율에 못 미치는 종목부터 사고, 넘치는 종목부터 팝니다</span>'}</div>` : ''}
      ${M.map(([a, i]) => memRow(a, i, multi && !lead)).join('') || '<p class="hint">아직 종목이 없습니다. 다른 그룹이나 미분류의 종목을 이 그룹으로 옮기세요.</p>'}
    </div>`;
  }).join('');
  const loose = state.assets.map((a, i) => [a, i]).filter(([a]) => !a.exclude && !G.some(g => g.id === a.group));
  const ex = state.assets.filter(a => a.exclude);
  $('targets').innerHTML = (html
    + (loose.length ? `<div class="grp"><div class="grp-rule"><b>미분류</b><span>그룹에 넣어야 목표 비중이 적용됩니다</span></div>${loose.map(([a, i]) => memRow(a, i, false)).join('')}</div>` : '')
    + (ex.length ? `<p class="hint">리밸런싱 제외: ${ex.map(a => esc(a.name)).join(', ')}</p>` : ''))
    || '<p class="hint">그룹 추가를 눌러 첫 그룹을 만드세요.</p>';
  renderTargetMeta();
}
function renderTargetMeta() {
  const A = state.assets || [], G = state.groups || [];
  const vals = A.map(a => a.exclude ? 0 : (+a.qty || 0) * px.krwPrice(a)), T = vals.reduce((s, v) => s + v, 0);
  document.querySelectorAll('[data-cur]').forEach(el => { const i = +el.dataset.cur; el.textContent = T ? pct(vals[i] / T * 100) : '–'; });
  document.querySelectorAll('[data-gcur]').forEach(el => { const g = G.find(x => x.id === el.dataset.gcur); el.textContent = g && T ? pct(members(g).reduce((x, [, i]) => x + vals[i], 0) / T * 100) : '–'; });
  const parts = G.map((g, gi) => [g.name, members(g).length ? (+g.target || 0) : 0, GCOLORS[gi % GCOLORS.length]]);
  $('gaugeTrack').innerHTML = parts.map(([l, v, c]) => v > 0 ? `<i style="width:${Math.min(100, v)}%;background:${c}" title="${esc(l)} ${v}%"></i>` : '').join('');
  $('groups').innerHTML = parts.filter(p => p[1] > 0).map(([l, v, c]) => `<span><i class="sw" style="background:${c}"></i>${esc(l)} <b>${+v.toFixed(1)}%</b></span>`).join('');
  renderTgtSum();
}
function renderTgtSum() {
  const s = (state.groups || []).filter(g => members(g).length).reduce((x, g) => x + (+g.target || 0), 0);
  $('tgtSum').innerHTML = Math.abs(s - 100) > 0.01
    ? `<span class="warnline">목표 비중 합계 ${s.toFixed(1)}% · 100%로 맞춰 주세요 (지금은 비율로 환산 중)</span>` : '목표 비중 합계 100%';
}
function fillSettings() { $('monthly').value = state.monthly ?? ''; $('carry').value = state.carry ?? 0; $('bandIn').value = state.band ?? ''; }

/* ---------- 저장 ---------- */
// 입력 후 0.7초 뒤 자동 저장. 서버 version과 다르면(다른 기기에서 먼저 수정) 최신 문서를 다시 불러온다.
let saveTimer = null, saving = false, dirtyAgain = false, pendingLocal = false;
function writeCache() {
  try { localStorage.setItem(CACHE, JSON.stringify({ doc: state, version, prices })); } catch (e) { /* 저장 공간이 없어도 동작에는 지장 없다 */ }
}
function scheduleSave() {
  state.example = false; pendingLocal = true;
  setSaveState('저장 대기 중…');
  clearTimeout(saveTimer); saveTimer = setTimeout(flush, 700);
}
async function flush() {
  if (saving) { dirtyAgain = true; return; }
  saving = true;
  const body = JSON.parse(JSON.stringify(state));
  try {
    const r = await api.putPortfolio(body, version);
    if (r.ok) { version = r.version; setSaveState('저장됨'); writeCache(); }
    else {
      // 충돌: 내 수정은 버리고 최신 문서로 바꾼다.
      clearTimeout(saveTimer); dirtyAgain = false; pendingLocal = false; saving = false;
      version = r.version; applyPortfolio(r.doc, true); writeCache();
      setSaveState('다른 기기에서 수정돼 새로 불러왔습니다');
      loadPrices();
      return;
    }
  } catch (e) {
    setSaveState('저장하지 못했습니다. 잠시 후 다시 수정해 보세요.');
  }
  saving = false;
  if (dirtyAgain) { dirtyAgain = false; flush(); } else pendingLocal = false;
}
function changed(structural) {
  if (structural) renderAssets(); else refreshAssetMeta();
  if (structural) renderTargets(); else renderTargetMeta();
  renderBoard(); scheduleSave();
}
$('assets').addEventListener('input', e => {
  const row = e.target.closest('.asset'); const k = e.target.dataset.k; if (!row || !k) return;
  const a = state.assets[+row.dataset.i];
  a[k] = k === 'exclude' ? e.target.checked : (k === 'name' || k === 'ticker' || k === 'market' || k === 'account') ? e.target.value : +e.target.value;
  if (k === 'ticker') a.ticker = e.target.value.trim();
  changed(k === 'market' || k === 'exclude' || k === 'account');
});
$('assets').addEventListener('click', e => {
  const i = e.target.dataset.del; if (i === undefined) return;
  state.assets.splice(+i, 1); changed(true);
});
$('monthly').addEventListener('input', e => { if (!state) return; state.monthly = +e.target.value; renderBoard(); scheduleSave(); });
$('bandIn').addEventListener('input', e => { if (!state) return; state.band = +e.target.value; renderBoard(); scheduleSave(); });
$('carry').addEventListener('input', e => { if (!state) return; state.carry = +e.target.value; renderBoard(); scheduleSave(); });
$('targets').addEventListener('input', e => {
  const t = e.target, grp = t.closest('.grp');
  if (t.dataset.inner !== undefined) state.assets[+t.dataset.inner].inner = Math.max(0, +t.value || 0);
  else if (grp && (t.dataset.gk === 'name' || t.dataset.gk === 'target')) {
    const g = state.groups.find(x => x.id === grp.dataset.g); if (!g) return;
    if (t.dataset.gk === 'name') { g.name = t.value; document.querySelectorAll('#targets select[data-move] option').forEach(o => { if (o.value === g.id) o.textContent = g.name; }); }
    else g.target = Math.max(0, +t.value || 0);
  } else return;
  renderTargetMeta(); renderBoard(); scheduleSave();
});
$('targets').addEventListener('change', e => {
  const t = e.target, grp = t.closest('.grp');
  if (t.dataset.move !== undefined) { const a = state.assets[+t.dataset.move]; if (t.value) a.group = t.value; else delete a.group; }
  else if (grp && ['mode', 'lead', 'sell'].includes(t.dataset.gk)) {
    const g = state.groups.find(x => x.id === grp.dataset.g); if (!g) return;
    g[t.dataset.gk] = t.value;
    if (g.mode === 'lead' && !g.lead) { const M = members(g); if (M.length) g.lead = g.sell = keyOf(M[0][0]); }
  } else return;
  renderTargets(); renderBoard(); scheduleSave();
});
$('targets').addEventListener('click', e => {
  const id = e.target.dataset.gdel; if (id === undefined) return;
  state.groups = state.groups.filter(g => g.id !== id);
  state.assets.forEach(a => { if (a.group === id) delete a.group; });
  renderTargets(); renderBoard(); scheduleSave();
});
$('addGroup').addEventListener('click', () => {
  if (!state) return;
  const id = 'g' + Date.now().toString(36);
  state.groups.push({ id, name: '새 그룹', target: 0, mode: 'ratio' });
  renderTargets(); renderBoard(); scheduleSave();
  const el = $('gn-' + id); if (el) { el.focus(); el.select(); }
});

/* ---------- 종목 검색 ---------- */
let filter = 'all';
function renderResults() {
  const q = $('q').value, list = search(SYM, q, filter), ul = $('results');
  if (!q.trim() && !list.length) { ul.hidden = true; ul.innerHTML = ''; return; }
  ul.hidden = false;
  if (!list.length) { ul.innerHTML = `<li><p class="hint" style="padding:10px 12px">'${esc(q)}'에 맞는 종목이 없습니다. 이름을 줄여 보거나 직접 입력을 이용하세요.</p></li>`; return; }
  const held = new Set((state?.assets || []).map(keyOf));
  ul.innerHTML = list.map(r => `<li><button type="button" data-code="${esc(r[0])}">
    <span class="rn">${esc(r[1])}</span>
    <span class="rc">${LISTING[r[2]]} · ${esc(r[0])}${+r[3] ? ' · 시총 ' + capText(+r[3]) : ''}${r[4] && (r[2] === 'US' || r[2] === 'UE') ? ' · ' + esc(r[4].replace(/\|/g, ', ')) : ''}</span>
    <span class="rt">${held.has(String(r[0]).toUpperCase()) ? '<span class="have">보유 중</span> ' : ''}${clsChip(r[6] || 'KS')}</span>
  </button></li>`).join('');
}
let qTimer = null;
$('q').addEventListener('input', () => { clearTimeout(qTimer); qTimer = setTimeout(renderResults, 120); });
document.querySelectorAll('.chip').forEach(c => c.addEventListener('click', () => {
  filter = c.dataset.f;
  document.querySelectorAll('.chip').forEach(x => x.setAttribute('aria-pressed', x === c));
  renderResults();
}));
function focusAsset(i, field) {
  const row = document.querySelector(`.asset[data-i="${i}"]`); if (!row) return;
  row.scrollIntoView({ block: 'center', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  row.classList.add('flash'); setTimeout(() => row.classList.remove('flash'), 1400);
  const el = $(field + i); if (el) { el.focus({ preventScroll: true }); el.select?.(); }
}
$('results').addEventListener('click', e => {
  const b = e.target.closest('button[data-code]'); if (!b || !state) return;
  const r = SYM_BY_CODE.get(b.dataset.code.toUpperCase()); if (!r) return;
  const existing = state.assets.findIndex(a => keyOf(a) === String(r[0]).toUpperCase());
  $('q').value = ''; renderResults();
  if (existing >= 0) { focusAsset(existing, 'q'); return; }
  const market = TYPE_MARKET[r[2]];
  state.assets.push({ name: r[1].replace(' (1g)', ''), ticker: r[0], market, qty: 0, avg: 0, target: 0, unit: market === 'CRYPTO' ? 0.0001 : 1 });
  changed(true);
  focusAsset(state.assets.length - 1, 'q');
});
$('manualBtn').addEventListener('click', () => {
  if (!state) return;
  state.assets.push({ name: $('q').value.trim() || '새 자산', ticker: '', market: 'KR', qty: 0, avg: 0, target: 0, unit: 1, manual: true });
  $('q').value = ''; renderResults(); changed(true);
  focusAsset(state.assets.length - 1, 'k');
});

/* ---------- 탭 ---------- */
const TABS = ['board', 'portfolio', 'holdings'];
function showTab(name) {
  const t = TABS.includes(name) ? name : 'board';
  TABS.forEach(k => { $(k).hidden = k !== t; $('tab-' + k).setAttribute('aria-selected', k === t); });
}
TABS.forEach(k => $('tab-' + k).addEventListener('click', () => { location.hash = k; showTab(k); }));
window.addEventListener('hashchange', () => showTab(location.hash.slice(1)));
showTab(location.hash.slice(1));

/* ---------- 시작 ---------- */
function setPrices(p) {
  prices = p && typeof p === 'object' ? p : { quotes: {} };
  if (!prices.quotes) prices.quotes = {};
  px = makePricer(prices);
}
// force: 입력 중이어도 편집 화면을 다시 그린다(충돌로 문서를 통째로 바꿀 때)
function applyPortfolio(data, force) {
  state = data;
  if (!Array.isArray(state.assets)) state.assets = [];
  ensureGroups(state);
  const editing = !force && document.activeElement && $('holdings').contains(document.activeElement);
  const editingP = !force && document.activeElement && $('portfolio').contains(document.activeElement);
  if (!editing) renderAssets();
  if (!editingP) { renderTargets(); fillSettings(); } else renderTargetMeta();
  renderBoard();
}
function bootCache() {
  let c = null; try { c = JSON.parse(localStorage.getItem(CACHE) || 'null'); } catch (e) { /* 깨진 캐시는 무시 */ }
  if (c && c.doc && Array.isArray(c.doc.assets)) { version = +c.version || 0; setPrices(c.prices); applyPortfolio(c.doc); return true; }
  $('priceLine').innerHTML = '<span>불러오는 중</span>';
  return false;
}
async function loadPrices() {
  try {
    setPrices(await api.getPrices());
    if (state) { renderBoard(); refreshAssetMeta(); renderTargetMeta(); writeCache(); }
  } catch (e) { /* 직전 가격을 그대로 쓴다 */ }
}
async function loadSymbols() {
  try { SYM = await api.getSymbols(); } catch (e) { SYM = []; }
  SYM_BY_CODE = indexSymbols(SYM);
  // 상장구분·자산군 표시는 종목 목록에서 오므로 다시 그린다(입력 중이면 건드리지 않는다).
  if (state && !$('holdings').contains(document.activeElement)) renderAssets();
  if (state && !$('portfolio').contains(document.activeElement)) renderTargets();
}

const hadCache = bootCache(); // 첫 화면: 직전에 받은 값
(async () => {
  loadSymbols();
  try {
    const [p, pr] = await Promise.all([api.getPortfolio(), api.getPrices().catch(() => null)]);
    if (pr) setPrices(pr);
    if (!pendingLocal) { version = p.version; applyPortfolio(p.doc); writeCache(); }
    else if (pr) { renderBoard(); refreshAssetMeta(); renderTargetMeta(); }
  } catch (e) {
    setSaveState(hadCache ? '서버에 연결하지 못해 직전에 받은 값을 보여 줍니다' : '서버에 연결하지 못했습니다. 잠시 후 새로고침해 주세요.');
    if (!hadCache) $('priceLine').innerHTML = '<span>불러오지 못했습니다</span>';
  }
})();
