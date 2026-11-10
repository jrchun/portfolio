// 숫자·통화 표시. 규칙은 docs/DESIGN.md 6장.
import { isUSD } from './rebalance.js';

export const won = n => Math.round(n).toLocaleString('ko-KR') + '원';
export const wonShort = n => {
  const a = Math.abs(n), s = n < 0 ? '−' : '';
  if (a >= 1e8) return s + (a / 1e8).toFixed(2).replace(/\.?0+$/, '') + '억원';
  if (a >= 1e4) return s + Math.round(a / 1e4).toLocaleString('ko-KR') + '만원';
  return s + Math.round(a).toLocaleString('ko-KR') + '원';
};
export const signedWon = n => (n > 0 ? '+' : n < 0 ? '−' : '') + Math.round(Math.abs(n)).toLocaleString('ko-KR') + '원';
export const pct = n => n.toFixed(1) + '%';
export const spct = n => (n > 0 ? '+' : n < 0 ? '−' : '') + Math.abs(n).toFixed(2) + '%';
export const pp = n => (n > 0 ? '+' : n < 0 ? '−' : '±') + Math.abs(n).toFixed(1) + '%p';
export const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
export const fmtQty = (q, unit) => unit >= 1 ? Math.round(q).toLocaleString('ko-KR') : (+(+q).toFixed(8)).toString();
export const fmtLocal = (v, a) => isUSD(a) ? '$' + (+v).toLocaleString('en-US', { maximumFractionDigits: 2 }) : Math.round(v).toLocaleString('ko-KR') + '원';
export const unitWord = a => a.market === 'GOLD' ? 'g' : a.market === 'CRYPTO' ? '개' : a.market === 'CASH' ? '원' : '주';
// 시가총액(억원) → "1.2조" / "3,456억"
export const capText = eok => eok >= 10000 ? (eok / 10000).toFixed(eok >= 100000 ? 0 : 1) + '조' : Math.round(eok).toLocaleString('ko-KR') + '억';
