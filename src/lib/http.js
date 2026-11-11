// Worker API 공용 도구.

export const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' },
});

// 편집 암호 확인. 읽기는 누구나, 쓰기는 WRITE_TOKEN(Worker 비밀값)을 아는 사람만.
// 비밀값이 설정되지 않았으면 쓰기를 모두 막는다.
export function canWrite(request, env) {
  const expected = env.WRITE_TOKEN || '';
  const got = (request.headers.get('Authorization') || '').replace(/^Bearer\s+/i, '');
  if (!expected || got.length !== expected.length) return false;
  let diff = 0;
  for (let i = 0; i < got.length; i++) diff |= got.charCodeAt(i) ^ expected.charCodeAt(i);
  return diff === 0;
}

export const nowIso = () => new Date().toISOString().replace(/\.\d+Z$/, 'Z');

export async function logUsage(env, event) {
  await env.DB.prepare('INSERT INTO usage_log (ts, event) VALUES (?, ?)').bind(nowIso(), event).run();
}
