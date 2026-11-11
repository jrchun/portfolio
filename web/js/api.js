// 서버 통신. 같은 출처의 /api 만 호출한다.
// 읽기는 누구나, 저장은 편집 암호가 있어야 한다. 암호는 이 기기 브라우저에만 저장한다.

const TOKEN_KEY = 'rebalance-board-write-token';
export function getToken() { try { return localStorage.getItem(TOKEN_KEY) || ''; } catch (e) { return ''; } }
export function setToken(t) { try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); } catch (e) { /* 저장 공간이 없으면 이번 화면에서만 쓴다 */ } }
const auth = () => { const t = getToken(); return t ? { Authorization: 'Bearer ' + t } : {}; };

async function json(res) {
  if (!res.ok) throw Object.assign(new Error('HTTP ' + res.status), { status: res.status });
  return res.json();
}

export const getPortfolio = () => fetch('/api/portfolio', { cache: 'no-store', headers: auth() }).then(json);
export const getPrices = () => fetch('/api/prices', { cache: 'no-store' }).then(json);
export const getSymbols = () => fetch('/symbols.json').then(json);

// 저장. 성공 { ok: true, version } / 다른 기기에서 먼저 수정 { ok: false, conflict: true, doc, version }
// / 편집 암호 없음·틀림 { ok: false, unauthorized: true }
export async function putPortfolio(doc, version) {
  const res = await fetch('/api/portfolio', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...auth() },
    body: JSON.stringify({ doc, version }),
  });
  if (res.status === 409) return { ok: false, conflict: true, ...(await res.json()) };
  if (res.status === 401) return { ok: false, unauthorized: true };
  return { ok: true, ...(await json(res)) };
}
