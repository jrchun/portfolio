// GET /api/prices → 포트폴리오 종목의 최신 종가와 환율(요청서 4.2 형식)
import { json } from '../lib/http.js';
import { buildPrices, todayKST } from '../lib/prices.js';

export async function GET({ env }) {
  const [pf, latest, fx] = await env.DB.batch([
    env.DB.prepare('SELECT doc FROM portfolio WHERE id = 1'),
    env.DB.prepare(`SELECT q.ticker, q.date, q.close, q.source FROM quotes q
      JOIN (SELECT ticker, MAX(date) AS d FROM quotes GROUP BY ticker) m ON q.ticker = m.ticker AND q.date = m.d`),
    env.DB.prepare('SELECT usdkrw FROM fx ORDER BY date DESC LIMIT 1'),
  ]);
  const doc = pf.results[0] ? JSON.parse(pf.results[0].doc) : { assets: [] };
  return json(buildPrices(doc, latest.results, fx.results[0] || null, todayKST()));
}
