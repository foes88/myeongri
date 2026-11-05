# v11.4 인수인계 (`/clear` 이후 재개용)

> 이 문서는 **현재 상태와 남은 일**을 적는다. 영구 작업 원칙은 `CLAUDE.md`(저장소 루트)가 맡고, 디자인·수치 상세는 `docs/43_V114_MODERN_MYEONGRI.md`, 직전 감사 수정은 `docs/42_V113B_AUDIT_FIXES.md` 에 있다. 이 문서 작성 시점(2026-11-06)에 확인한 사실만 적었고, 확인하지 못한 것은 "미확인"으로 표시했다.
> `CLAUDE.md` 의 "현재 상태" 줄은 아직 v11.0 기준이다(이 인수인계 커밋에서는 고치지 않음 → 아래 P2-10).

## A. 프로젝트 현황
- **명리 AI / 명리 明理.** FastAPI `backend/` + 정적 웹 `web/`(번들러 없음). 개인용 서버 `http://127.0.0.1:8765/consult.html`, 운영(Vercel) `https://myeongri-tau.vercel.app`.
- **엔진 계층:** Astro-Core V2 계산 → Mingli L1–L6(`layer6_monthly`) → `app/consult/*`(`agent`, `verdict`(judge-2.0.0), `facts`, `explain`, `months`, `synthesis`, `qa` …). 공개 verdict 필드: `story`(하위 호환 유지), 추가 선택 필드 `story_parts`·`signals`·`segments`·`months`·`think`.
- **화면(`web/assets/`):** `dashboard.js`(결과 대시보드), `mingli.css`(맨 아래 v11.4 블록이 디자인 토큰), `verdict_ui.js`, `member.js`, `motion-ui.js`, `demo_consult.js`(정적 데모, `python -m tools.build_static_demo` 로 재생성).
- **종합운 구조(v11.4):** 컨트롤 바(1·5·10년, 이전/다음 해) → A 핵심 결론(헤드라인·쉬운 요약·좋은 흐름/조심할 점) → B 올해 주요 변화(≤3, 구간 날짜 표시) → C 분야별 해석(탭, 중요 주제 우선, 나머지 접힘, 전체 해석과 근거 접힘) → 시기별 흐름·월별 흐름 → 해석의 근거(접힘) → 후속 질문 → 리포트 저장 → 계산 상태(접힘).
- **브랜치·커밋:** 작업 브랜치 `feature/v11-report-redesign` @ `996834c`(로컬 전용, main 보다 8커밋 앞섬). `main` = `origin/main` = `57742bd`(v11.0 후속). 원격 브랜치는 `main` 하나뿐.
- **운영 vs 로컬:** 운영은 `main`(≤ 57742bd) 기준으로 알고 있으나 **Vercel 현재 배포 커밋은 이번에 확인하지 못했다(미확인)**. v11.1~v11.4(`ad0410a`…`996834c`)는 push·배포하지 않았다. 로컬 서버는 Postgres(Docker `myeongri-pg`, 포트 55498)를 쓰고 가입은 닫혀 있다.

## B. 개발 환경
- 저장소 `C:\dev\myeongri`. 서버 실행 `scripts\run-local.bat`(최초 1회 `scripts\create-owner.bat`). 종료는 해당 콘솔에서 Ctrl+C 후 다시 실행. 정적 파일은 no-cache 로 서빙되어 화면 수정은 새로고침(Ctrl+F5)이면 반영되지만, **Python 코드 수정은 서버 재시작이 필요**하다(`--reload` 없음).
- 테스트(`backend` 에서):
  - 백엔드 `python -m pytest -q -k "not browser"` (최근: 1128 통과 · 12 건너뜀 · 실패 0)
  - 브라우저 `python -m pytest -m browser tests/browser` (최근: 141 통과 · 실패 0; 약 5.5분, Playwright)
  - Postgres 테스트는 별도 임시 DB 스크립트 필요(`DATABASE_URL` 은 `scripts\_personal_env.bat`; 비밀번호를 출력·기록하지 말 것).
- 화면 검증: 합성 입력만으로 임시 서버(`SERVE_WEB` 사본 + uvicorn 임의 포트)에 Playwright 로 접속(`tests/browser/test_oneshot_ui.py` 의 `one`·`open_page` 패턴). 개인용 8765 서버에는 로컬 기본값(실제 정보 가능성)이 채워지므로 캡처 검증에 쓰지 않는다.
- 문서: `docs/33`~`43`(모션·연도/월·v11.0 기준·문장 비교·v11.1~v11.4), `docs/40`(10초 이해도 평가 계획), `docs/35`(v11.0 개인용 릴리스 기준).
- 스크린샷(Git 제외, 합성 명식): `backend/data_private/ux/{v11…v113b, v114/before, v114/after}/`.
- 도구: `backend/tools/text_probe.py`(문장 측정), `bias_probe.charts(n, seed)`(합성 명식), `C.pre_for`.
- 셸 주의: Windows 콘솔 한글 깨짐 → `PYTHONIOENCODING=utf-8`; 긴 스크립트는 파일로 작성; CRLF 파일은 `newline=""` 로 읽고 쓴다.

## C. 변경 불가 원칙
1. 만세력 계산·명리 판정·점수·톤은 UI/문장 작업에서 바꾸지 않는다(300개 판정·헤드라인 항목 동일을 확인하는 감사 스크립트로 검증).
2. `story` API 하위 호환 유지, 새 필드는 추가형 선택 필드만. 구버전 저장 결과가 표시돼야 한다.
3. 실제 출생정보를 테스트·로그·스크린샷·Git 에 쓰지 않는다. `APP_DATA_KEY`·비밀번호 기록 금지.
4. 유료 LLM 호출 금지. 사용자(다른) Docker 컨테이너 건드리지 않기(55498 의 `myeongri-pg` 만).
5. **사용자 승인 없이 push·배포·main 병합·원격 브랜치 삭제·이력 재작성 금지.**
6. 품질 표기: 사람 평가 0건 → "미평가", 실제 사례 0건 → "미검증". "10초 이해도"·"사용성 검증 완료"는 사람 평가 전에 쓰지 않는다. 검증용 사례를 본 뒤 규칙을 고치지 않는다.
7. 관상 기능은 명리 브랜치에 섞지 않는다.

## D. 현재 남은 문제 (추적 목록)
| # | 우선 | 항목 | 영향 | 확인 방법 | 수정 위치 |
|---|---|---|---|---|---|
| 1 | **P0** | **실행 중인 8765 서버가 옛 백엔드 코드**(서버 시작 14:41, `explain.py`·`months.py` 수정 16:37 이후 재시작 안 함). 화면은 새 CSS/JS 인데 `period_reasons`·월별 입춘 안내는 반영 전 | 개인용 화면의 기간 설명·월 안내가 커밋과 불일치 | `run-local.bat` 재시작 후 2026 군겁쟁재 등 여러 구간 사례에서 구간별 문장·월별 "입춘 시각은" 안내 확인 | 코드 수정 없음(재시작) |
| 2 | P1 | Hover·선택 상태 실제 시각 검수(옛 적갈색 제거는 CSS 치환 + 테스트 통과까지만, 오버 상태 스크린샷은 못 찍음) | 버튼·탭·타임라인·접힘 머리글 | 6개 폭에서 마우스 오버/포커스/선택 상태 캡처(Playwright `hover()`) | `web/assets/mingli.css` 맨 아래 v11.4 블록 |
| 3 | P1 | 월별 입춘 경계 안내 정확성 검증(합성 24건 모두 안내가 붙는 것만 확인, 문구·표시 위치의 사용자 이해는 미확인) | 월별 흐름 | `verdict["months"][연도]["items"][i]["notes"]` 와 `segments` 비교, 화면에서 노트가 보이는지 | `backend/app/consult/months.py`, `web/assets/dashboard.js`(월 노트 렌더) |
| 4 | P1 | 합성 명식 8개 이상 확장 회귀(6개 폭 캡처는 명식 2개, 수치 감사는 12개×5년, UI 측정은 4개×5년뿐) | 전 화면 | `tests/browser` 에 8+ 명식 파라미터화(`bias_probe.charts`) 후 잘림·넘침·중복·접힘 | `backend/tests/browser/` 신규 테스트 |
| 5 | P1 | 실제 사용자 10초 이해도 평가 **미평가**(평가 계획 `docs/40`) | 상담 품질 표기 전체 | 사람 평가자 1명 이상, 응답 기록 | 코드 아님 |
| 6 | P1 | 현재 기능 운영 미배포(v11.1~v11.4) · Vercel 현재 배포 커밋 미확인 | 운영 사용자 | 사용자 승인 후 병합/푸시/배포 절차, 배포 전 이 문서 D·E 확인 | 해당 없음 |
| 7 | P2 | 접힘 머리글 스타일 불일치("나머지 주제 보기"는 상자 없음, "전체 해석과 근거 보기"는 상자 있음) | 분야 패널 | 360/1440 캡처 | `mingli.css`(`.dp-fold>summary`, `.dp-more>summary`), `dashboard.js` |
| 8 | P2 | 도식 ▲ 아이콘에 짙은 초록 잔존(`.heat .sym` 등) | 분야×연도 표·범례 | 캡처, `.heat`·`.chip` 색 확인 | `mingli.css` |
| 9 | P2 | 모바일 연도 카드 말줄임(`…`) 적절성(카드 요약 의도이나 핵심이 잘릴 수 있음) | 시기별 흐름 카드 | 360px 캡처에서 카드마다 핵심 의미 유지 여부 | `mingli.css`(`.tl-node` 요약), `dashboard.js` |
| 10 | P2 | 월별 흐름 UI 구조 개선(이번엔 색·간격만) / `CLAUDE.md` 현재 상태 줄 갱신 / `why` 170자+ 9건(입춘 전 괄호) / 문장 어휘 반복("흐름/기운") | 월별·문서·문장 | `audit1.py` 류 측정, 화면 | `dashboard.js`(월 UI), `CLAUDE.md`, `facts.py` `PRE_NOTE` |

**테스트 기준을 바꾼 7개 사례의 타당성(검토 결과):** (1) 콘텐츠 폭 ≥72% → 960~1080px, (2) 바탕·글자색 기대값, (3) '민트/블루 없음' → 의도한 옥색 토큰만 허용, (4) 섹션 제목 최소 24→21px, (5) 종합운 패널 헤드라인 생략 허용(핵심 결론에 같은 문장이 있을 때만), (6) 주요 변화 요약에 구간 날짜 문장 허용(날짜가 엔진 구간 `from` 과 일치해야 함), (7) 한 문장 안 기운 중복 검사를 기간별 문장 단위로. 모두 새 설계 요구에서 나온 의도적 변경이며 판정·계산 검증 테스트는 약화하지 않았다. 다만 (3)은 허용 색 집합이 넓어질수록 검사가 느슨해질 수 있으므로 토큰 목록을 늘릴 때 주의.

## E. 다음 개발 계획
1. **(먼저) 서버 재시작 후 D-1 확인**, 이어서 D-2~D-4 를 코드 수정 단위로 처리.
2. v11.4 잔여 UX(D-7~9)와 월별 흐름 UI 개선, 이후 `docs/40` 계획대로 사람 평가.
3. **개인용 릴리스 승인 조건:** 위 P0/P1 해소 + 백엔드·브라우저 전체 통과 + 사용자의 실제 화면 확인 + (병합·배포는) 사용자의 명시적 승인. 사람 평가 전까지 해석 품질은 "미검증/미평가"로 표시.
4. **관상학 Phase 0 (별도 연구):** 브랜치 `research/physiognomy-phase0` 는 안정 `main`(`57742bd`)에서 만들어 두었다(체크아웃·커밋 없음, 로컬 전용). 범위는 고전 원전·해석 체계·기술 구현 가능성 **조사만**. 명리 계산과 독립적으로 설계하고, 사진만으로 성격·운명이 드러난다고 단정하지 않는다. 얼굴 사진은 출생정보보다 민감한 생체 정보 → 로컬 처리·저장 금지·외부 전송 금지를 설계 첫 원칙으로. 필요하면 `git worktree add ..\myeongri-physio research/physiognomy-phase0` 로 분리 작업.

## F. Claude Code 복구 안내
`/clear` 후 순서:
1. `CLAUDE.md` → 이 문서 → `docs/43_V114_MODERN_MYEONGRI.md` 읽기.
2. 확인: `git -C C:\dev\myeongri branch --show-current` (기대 `feature/v11-report-redesign`), `git rev-parse --short HEAD`(이 문서 커밋 이후 기준은 아래 최종 보고의 해시; 직전 기능 커밋 `996834c`), `git status --short`(깨끗해야 함), `git branch -vv`.
3. 서버 코드 일치 확인: 8765 프로세스 시작 시각 vs `backend\app` 수정 시각(`Get-Process -Id <PID>`). 불일치면 재시작.
4. 지금까지의 한 줄 요약: *v11.4 옥색 디자인·종합운 A/B/C·구간별 기간 설명·월별 입춘 안내 구현 및 자동 테스트 통과(백엔드 1128, 브라우저 141). 남은 일은 서버 재시작 확인 → hover/월 안내 시각 검수 → 8+ 명식 회귀 → 사람 평가. 배포·push·병합은 승인 대기.*
