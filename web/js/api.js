// 서버 통신. 같은 출처의 /api 만 호출한다.

async function json(res) {
  if (!res.ok) throw Object.assign(new Error('HTTP ' + res.status), { status: res.status });
  return res.json();
}

export const getPortfolio = () => fetch('/api/portfolio', { cache: 'no-store' }).then(json);
export const getPrices = () => fetch('/api/prices', { cache: 'no-store' }).then(json);
export const getSymbols = () => fetch('/api/symbols').then(json);
// 가격 수집을 지금 실행한다. { updated, failed, fx, errors, prices }
export const refreshPrices = () => fetch('/api/prices/refresh', { method: 'POST' }).then(json);

// 저장. 성공하면 { ok: true, version }, 다른 기기에서 먼저 바뀌었으면 { ok: false, doc, version }.
export async function putPortfolio(doc, version) {
  const res = await fetch('/api/portfolio', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ doc, version }),
  });
  if (res.status === 409) return { ok: false, ...(await res.json()) };
  return { ok: true, ...(await json(res)) };
}
