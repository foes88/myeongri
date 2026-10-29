# 브라우저 통합·접근성 테스트 보고 (v6.6 §5)

실행: `cd backend; python -m pytest -m browser tests/browser -q` 또는 `python -m tools.run_browser_tests`
(필요: `pip install playwright`, `python -m playwright install chromium`. 기본 `python -m pytest -q` 에서는 이 테스트가 skip 된다.)
환경: Windows, Playwright + Chromium, uvicorn(127.0.0.1 임시 포트) + `http.server`(web/). 입력은 모두 가상 값. 서버는 fixture 종료 시 종료.
산출물(커밋 안 함): `backend/data_private/browser/browser_results.json`, `consult_360.png`.

## 결과 (16개 모두 통과)
| # | 점검 | 결과 |
|---|---|---|
| 1 | 양력/음력·윤달 입력, 시간 보정 선택, 검증 상태 패널(판정·프로필·해시·미검증 안내·범위 배지) | 통과 |
| 2 | 특정 연도 / 5년 / 10년 / 두 연도 비교 — 표시와 서버 전송 `years` 값 일치 | 통과 |
| 3 | 11개 분야 복수 선택, 깊이 요약·상세·전문가별 표시 차이(전문가 패널 유무), 건강 전통 해석의 의료 고지 | 통과 |
| 4 | 자유 질문, 후속 질문, 현실 사건 분류, 재분석(원본 해시 유지), 이력 표시 | 통과 |
| 5 | 명식 변형이 갈리는 입력 → 변형 선택 UI(자동 선택 안 함) → 진행 | 통과 |
| 6 | 잘못된 토큰 재열람 실패 메시지, 올바른 번호+토큰 재열람 성공 | 통과 |
| 7 | 서버 연결 불가 / 범위 밖 날짜(422) 메시지 | 통과 (409 변형·403 은 5·6 에서 확인) |
| 8 | 출생정보가 URL·콘솔·localStorage 에 없음 | 통과 |
| 9 | 360px: 가로 스크롤 없음, 컨트롤 높이 ≥ 36px | 통과 |
| 9b | 키보드만으로 작성·제출, 포커스 윤곽 표시, details 펼치기(Enter) | 통과 |
| 9c | 모든 입력에 label, 결과 영역 aria-live | 수정 후 통과 |
| 9d | 색 대비 AA 4.5:1 | 수정 후 통과 |

## 발견·수정한 결함 (web/consult.html)
1. 결과·상태·오류 영역에 `aria-live`/역할이 없어 스크린리더가 갱신을 알리지 못함 → `#out`, `#status`, `#variants`, `#evr`, `#rer`, `#histout` 에 `aria-live="polite"` 와 영역 레이블 추가, 분야 체크박스 묶음에 `role="group"` + `aria-label`.
2. 포커스 표시가 브라우저 기본값에만 의존 → `:focus-visible` 윤곽(3px) 명시.
3. claim id 글자(`.cid`, #778 on 흰색) 대비 4.39:1 로 AA 미달 → #566070 (6.36:1).

## 색 대비 측정값 (수정 후, WCAG 상대휘도 계산)
| 조합 | 비율 |
|---|---|
| 본문 ink on ivory | 12.73 |
| 작은 설명(.small) | 7.01 |
| 버튼 흰 글씨 on teal | 6.63 |
| 보조 버튼 / h2 teal | 6.63 (흰 배경 기준) |
| claim id | 6.36 |
| 배지 teal on 연한 배경 | 5.91 |
| 경고 배지 | 7.12 |
| 오류 문구 | 8.42 |
gold(#BE9864)는 글자색으로 쓰지 않고 포커스 윤곽·좌측 테두리 장식에만 사용(텍스트 대비 대상 아님; 흰 배경 대비는 AA 미달이므로 글자에 쓰지 말 것).

## 토큰 저장 방식 (정직한 기록)
- 접근 토큰은 **페이지의 JS 변수(메모리)에만** 있다. localStorage·sessionStorage·URL·콘솔·화면 텍스트에 없고, 요청에서는 `X-Consult-Token` 헤더로만 전송된다. localStorage 에는 `api`(API 주소) 키 하나만 저장된다.
- 한계: 새로고침하면 토큰이 사라지므로 사용자가 번호+토큰을 직접 보관해야 한다. 재열람 입력칸은 `type=password`.
- 상업 서비스에는 계정 인증·서버 세션(HttpOnly 쿠키)이 필요하다(docs/10).

## 남은 결함·한계
- 스크린리더 실기기(NVDA 등) 청취 점검은 하지 못했다(자동 규칙 점검만). `#out` 의 aria-live 는 결과가 길어 장황할 수 있다.
- 409/403 화면은 흐름 안에서만 확인했고 별도 표시 문구 개선은 하지 않았다.
- Firefox/Safari 미검증(Chromium 만). 터치 실기기 미검증.
- 상담 저장은 개발용 파일 기반이다(암호화·접근 감사 없음).
