# 배포 안내 (Cloudflare Pages + D1 + GitHub Actions)

맥미니 없이 클라우드에만 둔다(사용자 결정 2026-11-11, 요청서 2·12장의 맥미니·launchd 계획을 대신한다).

```
아이폰·PC ──▶ Cloudflare Pages ── web/ (화면)
                     └─ functions/ (API) ──▶ D1 (포트폴리오·종가·환율)
GitHub Actions (매일 07:30 KST) ── server/ 가격 수집기 ──▶ D1 REST API
```

- 읽기는 누구나 할 수 있다. 저장은 편집 암호(`WRITE_TOKEN`)를 아는 기기만 할 수 있다.
- 비용: Pages, D1, 공개 저장소의 Actions 모두 무료 범위 안이다(사용량이 매우 작다).

## 처음 한 번 하는 설정

| # | 할 일 | 하는 곳 |
|---|---|---|
| 1 | `main` 브랜치 만들기, 저장소 기본 브랜치를 `main`으로 | GitHub |
| 2 | Cloudflare API 토큰 만들기 (권한: Account › D1 › Edit) | Cloudflare 대시보드 › 내 프로필 › API 토큰 |
| 3 | D1 데이터베이스 `rebalance-board` 만들기, 스키마·시드 넣기, `wrangler.toml`의 `database_id` 채우기 | API 토큰으로 처리 |
| 4 | Pages 프로젝트 만들기: Git 연결 › `jrchun/portfolio` › 프로덕션 브랜치 `main`, 빌드 명령 비움, 출력 폴더 `web` | Cloudflare 대시보드 › Workers 및 Pages |
| 5 | Pages › 설정 › 변수 및 비밀 › 비밀 `WRITE_TOKEN`(편집 암호) 추가 후 다시 배포 | Cloudflare 대시보드 |
| 6 | Actions 비밀 `CLOUDFLARE_API_TOKEN`(2의 토큰), 변수 `CF_ACCOUNT_ID`, `CF_D1_DATABASE_ID` | GitHub › Settings › Secrets and variables › Actions |
| 7 | Actions › fetch-prices › Run workflow로 한 번 실행해 로그 확인 | GitHub |

`wrangler.toml`이 Pages 설정의 기준이다. 출력 폴더와 D1 연결은 이 파일에서 바꾸고, 대시보드에서는 같은 항목을 고칠 수 없다. 편집 암호처럼 비밀인 값만 대시보드에 둔다.

## 확인할 것

- 사이트 주소에서 화면이 뜨고, 다른 기기에서도 같은 값이 보인다.
- 편집 암호 없이 고치면 화면 아래에 "저장하려면 편집 암호를 입력하세요"가 뜬다.
- 다음 날 아침 Actions 실행 기록에 `가격 수집: 성공 N`이 남고, 화면의 종가 날짜가 바뀐다.

## 운영

- 가격을 지금 다시 받기: GitHub › Actions › fetch-prices › Run workflow.
- 편집 암호 바꾸기: Pages 비밀 `WRITE_TOKEN`을 바꾸고 다시 배포. 각 기기에서 새 암호를 한 번 넣는다.
- 백업: `npx wrangler@4 d1 export rebalance-board --remote --output backup.sql`.
- 예약 실행은 GitHub 사정으로 몇 분~수십 분 늦을 수 있고, 저장소에 60일간 활동이 없으면 GitHub가 예약 실행을 멈춘다.
