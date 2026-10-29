# 명리 아틀리에 — 실행형 프로토타입 + 완성 개발 설계

가족·지인 공유를 목표로 하는 고전 명리학 기반 웹서비스 프로젝트. **현재 실행되는 것은 UI 프로토타입**이며 완전한 만세력/AI 엔진이 아닙니다. 기존 연구용 Markdown 17개를 `knowledge/`에 포함합니다.

## 1분 실행 (Windows + VS Code)
1. ZIP을 모두 압축 풀기. VS Code의 `File > Open Folder`에서 이 폴더 선택.
2. `web/index.html` 파일을 Chrome으로 열면 **의존성 설치 없이 즉시 시안 확인** 가능.
3. 개발서버로 실행하려면 Python 3 설치 후 터미널에서 `python -m http.server 5173 --directory web` 실행하고 `http://localhost:5173` 접속. 또는 `scripts/run-web.bat` 더블클릭.
4. VS Code의 Live Server 확장이 있다면 `web/index.html` 우클릭 후 `Open with Live Server` 사용 가능.
5. Claude Code에서 `prompts/CLAUDE_CODE_전체개발_프롬프트.md`를 열고 내용을 붙여넣어 실제 제품 코드 구현을 진행.

## 구성
- `web/index.html`: 동작하는 반응형 시안(한 명의 **검증 대기 예제**만 명식 표시, 다른 입력은 계산 불가 안내)
- `knowledge/`: 17개 연구용 Markdown(고전 출처와 논쟁 목록 포함)
- `docs/`: 화면/기능/아키텍처/계산 검증/보안/검수 설계
- `backend/`: API 골격. 진짜 계산기가 없는 상태에선 501을 반환하며 계산을 꾸며내지 않음
- `prompts/`: Claude Code에 붙여넣는 구현 지시문

## 백엔드 테스트 (선택)
`cd backend` → `python -m venv .venv` → Windows: `.venv\Scripts\activate` → `pip install -r requirements.txt` → `uvicorn app.main:app --reload --port 8000`
접속: `http://127.0.0.1:8000/docs`. API에서 계산 요청 시 명시적으로 501 반환.

## 구현 완료의 정의
만세력 교차검증, 한국 DST, 절기 경계, 시간 보정, 대운, 주석별 해석 출처, 보안, 접근제어, 테스트가 통과해야만 출시. 현재 자료만으로 완성됐다고 주장하지 말 것.

**문화적·역사적 해석 서비스이며 질병/재정/승진의 과학적 예측이나 판정을 제공하지 않습니다.**
