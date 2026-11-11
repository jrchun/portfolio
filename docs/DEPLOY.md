# 배포 안내 (Cloudflare Workers + D1 + GitHub Actions)

맥미니 없이 클라우드에만 둔다(사용자 결정 2026-11-11, 요청서 2·12장의 맥미니·launchd 계획을 대신한다).

```
아이폰·PC ──▶ Cloudflare Worker "rebalance-board"
                 ├─ web/ (정적 화면, 파일이 있으면 바로 보냄)
                 └─ src/worker.js (/api/*) ──▶ D1 "rebalance-board" (포트폴리오·종가·환율)
GitHub Actions (매일 07:30 KST) ── server/ 가격 수집기 ──▶ D1 REST API
```

- 읽기는 누구나 할 수 있다. 저장은 편집 암호(`WRITE_TOKEN`)를 아는 기기만 할 수 있다.
- `main` 브랜치에 올리면 Cloudflare(Workers Builds)가 `npx wrangler deploy`로 자동 배포한다.
- 비용: Workers, D1, 공개 저장소의 Actions 모두 무료 범위 안이다(사용량이 매우 작다).

## 처음 한 번 하는 설정

| # | 할 일 | 상태 |
|---|---|---|
| 1 | `main` 브랜치 만들기, 저장소 기본 브랜치를 `main`으로 | 완료 |
| 2 | Cloudflare API 토큰 `rebalance-d1` (권한: D1 Write) | 완료 |
| 3 | D1 `rebalance-board`(아시아·태평양) 만들기, 스키마·시드 넣기, `wrangler.toml`에 ID 기입 | 완료 |
| 4 | Actions 비밀 `CLOUDFLARE_API_TOKEN`(2의 토큰). 계정 ID·DB ID는 워크플로 파일에 적혀 있다 | 완료, 수동 실행 성공 |
| 5 | Cloudflare › Workers 및 Pages › 만들기 › Git 연결 › `jrchun/portfolio`, 브랜치 `main`, 빌드 명령 없음, 배포 명령 `npx wrangler deploy`. Worker 이름은 `wrangler.toml`의 `name`(`rebalance-board`)과 같아야 한다 | 프로젝트 생성됨 |
| 6 | Worker › 설정 › 변수 및 비밀 › 추가 › 형식 **Secret**, 이름 `WRITE_TOKEN`(편집 암호) | |

`wrangler.toml`이 Worker 설정의 기준이다. 정적 파일 폴더와 D1 연결은 이 파일에서 바꾼다. 편집 암호처럼 비밀인 값만 대시보드에 둔다(배포해도 비밀값은 지워지지 않는다).

## 확인할 것

- 사이트 주소(`https://rebalance-board.<계정 하위 도메인>.workers.dev`)에서 화면이 뜨고, 다른 기기에서도 같은 값이 보인다.
- 편집 암호 없이 고치면 화면 아래에 "저장하려면 편집 암호를 입력하세요"가 뜬다.
- 다음 날 아침 Actions 실행 기록에 `가격 수집: 성공 N`이 남고, 화면의 종가 날짜가 바뀐다.

## 운영

- 가격을 지금 다시 받기: GitHub › Actions › fetch-prices › Run workflow.
- 편집 암호 바꾸기: Worker 비밀 `WRITE_TOKEN`을 바꾼다. 각 기기에서 새 암호를 한 번 넣는다.
- 백업: `npx wrangler@4 d1 export rebalance-board --remote --output backup.sql`.
- 예약 실행은 GitHub 사정으로 몇 분~수십 분 늦을 수 있고, 저장소에 60일간 활동이 없으면 GitHub가 예약 실행을 멈춘다.
