// Cloudflare Worker 진입점.
// 정적 파일(web/)은 Cloudflare가 먼저 찾아 보내고, 맞는 파일이 없을 때만 이 코드가 실행된다.
// 여기서는 /api/* 만 처리하고 나머지는 정적 파일 처리(404 포함)에 넘긴다.
import * as portfolio from './api/portfolio.js';
import * as prices from './api/prices.js';
import { json } from './lib/http.js';

const ROUTES = { '/api/portfolio': portfolio, '/api/prices': prices };

export default {
  async fetch(request, env, ctx) {
    const path = new URL(request.url).pathname.replace(/\/+$/, '');
    const route = ROUTES[path];
    if (!route) return env.ASSETS.fetch(request);
    const handler = route[request.method];
    if (!handler) return json({ detail: '허용하지 않는 요청 방식입니다.' }, 405);
    try {
      return await handler({ request, env, ctx });
    } catch (e) {
      return json({ detail: '서버 오류: ' + (e && e.message || e) }, 500);
    }
  },
};
