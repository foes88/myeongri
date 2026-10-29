# v6.8 — 깨끗한 브랜치 기반 정적 디자인 Preview 준비

> **상태: 로컬 준비 완료, 원격 push 안 함.** Vercel Preview 접근 보호가 확인되지 않아 push 조건을 충족하지 못했다.

## 브랜치
- 기반: `clean/v6.6-history-prep` (`b12bbe7`, 부모 `cb7be0a`). 노출 이력(`943ea23` 이후 개발 커밋)을 조상에 포함하지 않는다.
- Preview 브랜치: `preview/v6.7-editorial` — 기반 위에 v6.7 디자인 + v6.8 정적 모드 파일만 `git checkout <개발 브랜치> -- <파일>`로 가져와 단일 커밋.
- 병합한 커밋 없음(파일 단위 복사). 개발 브랜치 `feature/v6.1-verification-mingli-l345`는 그대로 보존.

## 포함/제외
| 구분 | 내용 |
|---|---|
| 포함(디자인) | `web/index.html`(+`web/src/template.html`), `web/consult.html`, `web/assets/mingli.css`, `web/assets/demo_consult.js`(합성 데모) |
| 포함(보조) | 답변 필드 추가(`pillars`, `classical_basis`), 브라우저 테스트·캡처 도구, 이력 검사 도구, `docs/15`, 이 문서 |
| 제외 | HKO·KASI 원자료, 외부 파생 케이스, `data_private/`, 천문 데이터(`*.bsp`), 스크린샷 |
| Preview 전용 | `consult.html` 메타 `mingli-mode=static-preview`, `vercel.json` 보안 헤더(CSP 등), `backend/vercel.json`(backend 프로젝트 빌드 건너뜀) |

## 정적 모드가 보장하는 것
- 입력란(`#f` 전체)이 비활성화되어 출생 정보를 입력할 수 없다. API 주소·재열람 입력은 숨김.
- `call()` 이 서버 호출 대신 거절하며, 페이지에 `fetch`/XHR 가 실행되지 않는다(브라우저 테스트로 0건 확인). 쿠키·localStorage·sessionStorage 사용 0.
- 시연은 합성 명식(간지 4쌍)으로 엔진이 생성한 답변(`demo_consult.js`)만 사용. 화면 곳곳에 “합성 데모 — 실제 분석 결과가 아닙니다” 표시. 합성 명식은 `CORE_VALIDATED` 를 받지 않는다.
- 배포 헤더(`vercel.json`): `Content-Security-Policy: connect-src 'none'; form-action 'none'; frame-ancestors 'none'; object-src 'none'` 등. 같은 헤더를 붙인 로컬 서버에서 데모는 동작하고 fetch(동일 출처·외부)와 폼 제출이 차단됨을 확인(`test_csp_headers_allow_demo_but_block_any_network_send`).

## 검사 결과 (preview 브랜치)
| 항목 | 결과 |
|---|---|
| 조상에 `943ea23`·`c2f55f0`·`664f830`·`e3165f5`·`e150887`·`ecd8c69` | 없음 |
| `python -m tools.scan_history HEAD --forbidden-commit 943ea23` (도달 가능한 모든 커밋·파일) | clean |
| `python -m tools.check_distribution` | clean (금지 경로 미추적, 데이터 파일 분류, 의존성 라이선스) |
| `python -m app.privacy_scan` | clean |
| pytest | 804 통과, 33 건너뜀(브라우저 마커) |
| Playwright `-m browser` | 13 통과, 20 건너뜀 — 라이브 API 상담 테스트(정적 모드에서 의미 없음)는 건너뜀. 라이브 모드 23개는 개발 브랜치에서 통과 |

## Vercel 설정 확인 (이번에 확인한 것 / 못 한 것)
- 확인: 저장소는 Vercel 프로젝트 2개(`myeongri`, `backend`)와 Git 연동되어 있고, 브랜치 push 마다 두 프로젝트에서 배포가 생성된다(GitHub 커밋 상태). `Vercel Preview Comments` 체크도 붙는다.
- **확인하지 못함**(이 환경에 Vercel/GitHub 로그인 없음 — `gh auth` 없음, `VERCEL_TOKEN` 없음, CLI 미설치): ① 두 프로젝트의 Git 자동 배포 조건 ② Preview Deployment Protection(Vercel Authentication / Password) ③ 브랜치별 빌드 제외 설정 ④ backend 프로젝트의 Root Directory ⑤ 기존 backend 배포에서 JSON·민감 파일 접근 가능 여부.
- 대비책(저장소 쪽, 효과 미검증): `backend/vercel.json` 의 `ignoreCommand: "exit 0"` — backend 프로젝트 Root Directory 가 `backend` 일 때 이 브랜치의 backend 빌드를 건너뛴다.

## push 하기 전에 사람이 확인할 것 (대시보드)
1. `myeongri` 프로젝트 → Settings → Deployment Protection: Preview 에 **Vercel Authentication**(또는 Password) 켜짐.
2. `backend` 프로젝트 → Settings → Git: 이 저장소 연결 해제 또는 Ignored Build Step 설정, Root Directory 확인. 과거 배포 URL 에서 `golden/sources/*.json` 이 열리는지 점검(열리면 프로젝트/배포 삭제).
3. 두 프로젝트의 Preview 도메인이 팀 계정 보호 하에 있는지 확인.
위가 확인되면 `git push origin preview/v6.7-editorial` — 승인 전에는 실행하지 않는다.
