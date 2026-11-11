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
| `data/symbols.json` | 종목 검색용 목록(약 12,000개) |
| `scripts/build_symbols.py` | 종목 목록 재생성 스크립트 |

## 실행

```
uv run uvicorn server.main:app --host 127.0.0.1 --port 8765   # http://127.0.0.1:8765
uv run pytest                                                  # 서버 테스트
node --test tests/*.test.js                                    # 계산·검색 테스트
```

- 첫 실행 때 `data/seed-portfolio.json`과 `data/seed-prices.json`을 `data/rebalance.sqlite`에 넣는다. 두 파일은 저장소에 없으므로 기기에 직접 복사한다. 없으면 `data/example-*.json`(예시 데이터)으로 시작한다.
- 시드는 DB가 비어 있을 때 한 번만 들어간다. 다시 넣으려면 `data/rebalance.sqlite*`를 지우고 서버를 다시 띄운다.
- 요청서 6장의 테스트 벡터 "경우 2"는 `data/seed-*.json`과 기대값 파일 `data/seed-expected.json`이 있는 기기에서만 실행된다(없으면 건너뛴다).
- 앱에는 인증이 없다. 반드시 `127.0.0.1`에만 바인딩한다.

## 가격 수집

```
uv run python -m server.jobs.fetch_prices     # 지금 한 번 수집 (화면의 [가격 새로고침]과 같다)
bash ops/install-launchd.sh                   # 맥미니에서 매일 07:30 자동 수집 등록 (로그: logs/fetch-prices.log)
```

| 시장 | 출처 | 비고 |
|---|---|---|
| 국내 주식·ETF | 네이버 금융 일봉 → 없으면 yfinance(`.KS`→`.KQ`) | 2026-11-10 대조에서 증권사 앱과 일치한 쪽이 네이버였다 |
| 미국 주식·ETF | yfinance | `BRK.B` → `BRK-B` |
| 환율 | yfinance `KRW=X` | 수집 시점 값 |
| 코인 | 업비트 `prev_closing_price` | 날짜는 그 종가가 정해진 09:00의 날짜 |
| KRX 금현물 | 네이버 증권 "국내 금" | KRX 정보데이터시스템은 로그인 필요, 공공데이터포털은 키 필요·갱신이 늦어 쓰지 않는다 |

- 키가 필요한 출처는 없다. 네이버 주소 두 곳은 공식 문서가 없어 바뀌면 그 시장만 실패한다.
- 마감 전에 수집하면 오늘 행은 버리고 전일 종가를 쓴다(국내 16:00, 미국 뉴욕 16:30 기준).
- 받지 못한 종목은 직전 종가를 유지한다. 3영업일 넘게 갱신되지 않으면 대시보드 맨 위에 경고가 뜬다. 공휴일은 따로 빼지 않으므로 긴 연휴 뒤에는 경고가 잠깐 뜰 수 있다.
- launchd 시각은 맥미니 시스템 시간대를 따른다. 서울로 맞춰 둔다.
