# 내 리밸런싱 보드 · 개발 시작 묶음

Claude Code에서 이 폴더를 열고 다음과 같이 요청하면 된다.

> docs/requests/001-rebalance-board-mvp.md 를 읽고 1단계부터 진행해 줘. 단계가 끝나면 멈추고 보고해.

| 파일 | 내용 |
|---|---|
| `CLAUDE.md` | Claude Code가 매번 읽는 프로젝트 규칙 |
| `docs/requests/001-rebalance-board-mvp.md` | 작업지시서 |
| `docs/DESIGN.md` | 디자인 가이드라인 |
| `reference/rebalance-board.html` | 동작하는 시안(화면·계산 기준) |
| `data/seed-portfolio.json` | 현재 포트폴리오(2026-11-11 기준). 개인 금융 정보이므로 공개 저장소에 올리지 않는다 |
| `data/seed-prices.json` | 위 포트폴리오의 가격·환율 |
| `web/symbols.json` | 종목 검색용 목록(약 12,000개) |
| `scripts/build_symbols.py` | 종목 목록 재생성 스크립트 |

## 구성

| 역할 | 위치 | 실행 곳 |
|---|---|---|
| 화면 | `web/` | Cloudflare Pages |
| API (`/api/portfolio`, `/api/prices`) | `functions/` | Cloudflare Pages Functions |
| 저장 | `db/schema.sql` | Cloudflare D1 |
| 매일 가격 수집 | `server/`, `.github/workflows/fetch-prices.yml` | GitHub Actions (07:30 KST) |

- 읽기는 누구나 할 수 있다. 저장은 편집 암호(Pages 비밀값 `WRITE_TOKEN`)가 있어야 하고, 기기마다 처음 한 번 화면 아래 칸에 넣는다.
- 배포 절차는 [`docs/DEPLOY.md`](docs/DEPLOY.md).

## 로컬에서 실행

```
npx wrangler@4 d1 execute rebalance-board --local --file db/schema.sql
python3 scripts/seed_sql.py > /tmp/seed.sql && npx wrangler@4 d1 execute rebalance-board --local --file /tmp/seed.sql
echo 'WRITE_TOKEN=local-test-token' > .dev.vars
npx wrangler@4 pages dev            # http://localhost:8788
```

- 테스트: `uv run pytest` (가격 수집기) / `node --test tests/*.test.js` (계산·검색·가격 문서)
- 요청서 6장의 테스트 벡터 "경우 2"는 `data/seed-*.json`과 `data/seed-expected.json`이 있을 때만 실행된다.

## 가격 수집

```
uv run python -m server.jobs.fetch_prices --sqlite <파일>   # 로컬 SQLite에 시험 수집
uv run python -m server.jobs.fetch_prices                   # D1에 수집 (CF_ACCOUNT_ID, CF_D1_DATABASE_ID, CLOUDFLARE_API_TOKEN 필요)
```

| 시장 | 출처 | 비고 |
|---|---|---|
| 국내 주식·ETF | 네이버 금융 일봉 → 없으면 yfinance(`.KS`→`.KQ`) | 2026-11-10 대조에서 증권사 앱과 일치한 쪽이 네이버였다 |
| 미국 주식·ETF | yfinance | `BRK.B` → `BRK-B` |
| 환율 | yfinance `KRW=X` | 수집 시점 값 |
| 코인 | 업비트 `prev_closing_price` | 날짜는 그 종가가 정해진 09:00의 날짜 |
| KRX 금현물 | 네이버 증권 "국내 금" | KRX 정보데이터시스템은 로그인 필요, 공공데이터포털은 키 필요·갱신이 늦어 쓰지 않는다 |

- 키가 필요한 가격 출처는 없다. 네이버 주소 두 곳은 공식 문서가 없어 바뀌면 그 시장만 실패한다.
- 마감 전에 수집하면 오늘 행은 버리고 전일 종가를 쓴다(국내 16:00, 미국 뉴욕 16:30 기준). 야후가 값을 비워 주면 직전 종가를 유지한다.
- 받지 못한 종목은 직전 종가를 유지한다. 3영업일 넘게 갱신되지 않으면 대시보드 맨 위에 경고가 뜬다. 공휴일은 따로 빼지 않는다.
