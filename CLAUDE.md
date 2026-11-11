# 내 리밸런싱 보드

개인용 포트폴리오 리밸런싱 도구. 사용자 1명. Cloudflare Workers(정적 화면 + API) + D1(SQLite)에 배포하고, 가격은 GitHub Actions가 매일 수집한다.

## 먼저 읽을 것
- `docs/requests/` — 번호순 개발 요청서. 가장 최근 번호가 현재 작업이다.
- `docs/DESIGN.md` — 색, 글꼴, 컴포넌트, 숫자 표기 규칙.
- `reference/rebalance-board.html` — 동작하는 시안. 화면과 계산 로직의 기준이다. 수정하지 않는다.

## 지켜야 할 것
- 계산 로직은 `web/js/rebalance.js`의 순수 함수에만 둔다. 바꾸면 `tests/`의 테스트 벡터를 함께 확인한다.
- 화면은 빌드 없는 정적 파일이다. React, 번들러, CSS 프레임워크를 들이지 않는다.
- 색은 CSS 변수만 쓴다. 라이트·다크와 폰 폭 400px을 매번 확인한다.
- 포트폴리오 데이터는 공개해도 된다(사용자 결정 2026-11-11). 읽기는 누구나, 수정은 편집 암호(Worker 비밀값 `WRITE_TOKEN`)가 있어야 한다. 외부 분석·오류 수집 서비스는 붙이지 않는다.
- 비밀값(API 토큰, 편집 암호)은 저장소에 올리지 않는다. 공개 저장소다.
- 증권사 API는 쓰지 않는다. 가격은 키가 필요 없는 출처의 전일 종가만 쓴다. 모르는 API 사양은 추측하지 말고 문서를 확인한 뒤 보고한다.
- 주문 기능은 만들지 않는다. 계산과 기록만 한다.
- 요청서의 단계가 끝나면 멈추고 결과를 보고한다.

## 구성
- `web/`: 정적 화면(Worker 정적 자산으로 그대로 배포). `web/js/rebalance.js`가 계산.
- `src/`: Worker API(`src/worker.js`가 `/api/portfolio`, `/api/prices`를 처리). D1 바인딩 이름 `DB`.
- `server/`: 가격 수집기(Python). GitHub Actions(`.github/workflows/fetch-prices.yml`)가 매일 07:30 KST에 실행해 D1 REST API로 저장한다.
- `db/schema.sql`: D1 스키마. `wrangler.toml`: Worker 설정의 기준. `main`에 올리면 Cloudflare가 자동 배포한다.
- 배포 절차: `docs/DEPLOY.md`

## 실행
- 로컬: `npx wrangler@4 d1 execute rebalance-board --local --file db/schema.sql` 후 `npx wrangler@4 dev` (편집 암호는 `.dev.vars`의 `WRITE_TOKEN`)
- 테스트: `uv run pytest` / `node --test tests/*.test.js`
- 가격 수집 시험: `uv run python -m server.jobs.fetch_prices --sqlite <파일>`
