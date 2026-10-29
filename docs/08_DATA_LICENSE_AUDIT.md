# 외부 데이터·라이선스 감사 (v6.4)

감사 대상: 브랜치 `feature/v6.1-verification-mingli-l345` (원격 `foes88/myeongri`, **공개 저장소**로 확인됨 — GitHub API `private:false`, 포크 0개).

## 원칙
- 개별 날짜·시각 **사실**(예: 어떤 해의 입춘 시각)과 **자료집·데이터베이스**(연도별 표 전체)는 구분한다. 사실 자체의 저작권 여부와 별개로, 자료집 형태의 대량 복제·재배포는 제공처 이용 조건을 확인하기 전에는 공개하지 않는다.
- 라이선스가 불확실한 자료를 상업적 사용 가능하다고 간주하지 않는다.

## 파일별 판정
| 파일(경로) | 출처 | 성격 | 이용 조건 | 판정 |
|---|---|---|---|---|
| `golden/sources/hko_lunar_terms.json` (이전 위치) | HKO 음양력 표 1901~2050 + 절기 시각 | 자료집 수준 대량 추출(150년) | **미확인** | **공개 저장소에서 제거** → `backend/data_private/external/` (gitignored). 재생성: `python -m tools.fetch_hko` |
| `golden/sources/kasi_calendar.json` (이전 위치) | KASI 달력자료 2023~2028(월·대소·월건·일진·절기) | 자료집 수준 | **미확인** (KASI 는 "공식 발표 자료가 아님" 명시) | **제거** → `data_private/external/`. 재생성: `python -m tools.fetch_kasi` |
| `golden/cases.json` (이전 버전) | 위 두 자료에서 파생한 기대값 366건 포함 | 대량 파생 | 미확인 | **분리**: 공개 `cases.json` 은 lunar-python·Meeus·공개 연혁 기준 125건만. 외부 파생 366건은 `data_private/cases_external.json` |
| `golden/term_analysis.json` (이전 버전) | HKO 분 단위 72행·날짜 불일치 행 포함 | 행 단위 파생 | 미확인 | **요약 수치만 공개**, 행 단위는 `data_private/term_analysis_full.json` |
| `golden/report.json` | 집계 | 집계 수치 | 사실 집계 | 공개 유지(집계만, 케이스별 결과는 공개 케이스만). 외부 파생 범주는 "로컬 재현 필요" 명시 |
| `golden/lunar_check.json` | 천문 유도(자체 계산) 대 라이브러리·외부 자료 일치 여부 | 불리언/연도 목록 + 3개 해 윤달 날짜 | 개별 사실 | 공개 유지 |
| `golden/judgements.json`, `sources.json` | 자체 작성 판정/레지스트리 | 자체 | — | 공개 |
| `golden/sxtwl_report.json` | sxtwl 대 Skyfield 비교 요약 | 요약 | sxtwl BSD-3-Clause(상위 저장소 원문) | 공개 |
| `backend/data/de421.bsp` | JPL DE421 (NASA/JPL 공개 천체력) | 바이너리 16MB | 공개 도메인에 준하는 공개 자료로 알려져 있으나 **본 감사에서 이용 조건 원문은 확인하지 않음** | 저장소에 넣지 않음(`.gitignore`), 실행 시 Skyfield 가 내려받음 |

## 라이브러리
| 라이브러리 | 용도 | 라이선스 확인 |
|---|---|---|
| skyfield 1.55, jplephem | 서비스 런타임(천문 계산) | MIT (패키지 메타데이터) |
| lunar-python 1.4.8 | 서비스 런타임 교차 검산 + 골든 기대값 | MIT (메타데이터; 저장소 원문 재확인 필요) |
| korean-lunar-calendar 0.4.0 | 서비스 런타임(음양력 변환) | MIT (상위 GitHub 저장소 `usingsky/korean_lunar_calendar_py` LICENSE 확인). PyPI 메타데이터에는 라이선스 필드 없음 |
| tzdata / zoneinfo | 서비스 런타임 | Apache-2.0(메타데이터) / IANA 데이터는 공개 |
| sxtwl 2.0.7 | **검증 전용**(WSL), 서비스 의존성 아님 | BSD-3-Clause (상위 GitHub LICENSE 원문 확인; PyPI sdist 에 라이선스 파일 없음) |

## 공개 Git 이력 노출 (중요)
- 커밋 `943ea23` 이 원격 브랜치 `feature/v6.1-verification-mingli-l345` 로 이미 push 되어 있고, 이 커밋에는 위 `hko_lunar_terms.json`, `kasi_calendar.json` 과 외부 파생 케이스 366건을 포함한 `cases.json`, 행 단위 `term_analysis.json` 이 들어 있다.
- 저장소가 공개이므로 이 브랜치와 커밋 SHA 로 해당 파일이 열람·복제될 수 있다. `main` 에는 반영되지 않았다(포크 0).
- **이번 커밋은 파일을 트리에서 제거할 뿐 이력은 지우지 못한다.** 이력에서 없애려면 브랜치 삭제 후 이력 재작성 push(force) 또는 브랜치 재생성이 필요하며, GitHub 은 삭제 후에도 SHA 직접 접근/캐시를 한동안 유지할 수 있다. 원격 이력 변경은 파괴적이므로 **사용자 승인 후에만** 수행한다(미수행).
- 키/토큰·개인 출생정보는 포함되지 않았다(개인정보 검사 clean, 골든 입력은 가상).

## 사용자 확인 필요
1. HKO·KASI 이용 약관 확인(재배포·상업적 이용 여부). 확인 전까지 두 자료는 비공개 로컬 전용.
2. 원격 브랜치 이력 정리 여부(삭제·force push 승인).
3. KASI 공식 월력요항 2012·2017 확보 경로.
