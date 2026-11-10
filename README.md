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
