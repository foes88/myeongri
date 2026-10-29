# v6 ARGON 통합 감사 및 진행표

기준: 이 폴더 스냅샷(git 저장소 아님 → 커밋 `cb7be0a`와 대조 불가). 기존 L01~L12, X01~X08, 개인정보 검사기, 기존 37개 테스트는 그대로 통과.

| 영역 | 상태 | 비고 |
|---|---|---|
| 1 Astro-Core | **구현(V1 미부여)** | `backend/app/astro_core/`. 아래 상세 |
| 2 Mingli-Graph | 일부(십성·지장간 사실표 `chart_analysis.py`만) | 5단계 분석, 근거 그래프, 순서형 판단 미구현 |
| 3 Classical-RAG | 미구현 | 사례 DB/검색 없음 (`knowledge/14` 문서만) |
| 4 Consult-Agent | 미구현 | 사전 커밋·사후 끼워맞추기 방지 없음. 마스터 프롬프트 `knowledge/16`만 |
| 5 Multi-School | 미구현 | |
| 6 Eval-Harness | 일부(`report_checks`/`report_review` 텍스트 검사) | Track A/B 평가 미구현. 지시문 마지막 항목("필요한 경우 전통 전문가의…")이 잘려 있어 확인 필요 |

## Astro-Core 구현 범위
- 절기: Skyfield 1.55 `almanac_east_asia.solar_terms` + JPL DE421(1901~2050). AGPL 문제가 있는 Swiss Ephemeris는 쓰지 않음.
- 연주(입춘 순간)·월주(12절 순간)·일주(JDN)·시주(五鼠遁), 대운 순역·기산·10주기, 세운·월운.
- 시간: IANA(`zoneinfo`) 역사 시간대·서머타임(중복/건너뜀 시각 처리), CIVIL / 평균태양시 / 진태양시. 태양시는 UTC에서 한 번만 계산 → 이중 보정 불가(테스트로 검증). 균시차 = 시태양시 − 평균태양시, GAST−RA로 직접 산출 후 Meeus 식과 교차.
- 23시: 3개 프로필(`ZI_2300_DAY_CHANGE`, `MIDNIGHT_SAME_DAY_STEM`, `MIDNIGHT_NEXT_DAY_STEM`). 시간 보정 3종 × 23시 규칙 3종 × 서머타임 fold를 모두 계산해 서로 다른 명식은 `variants[]`로 반환. 기본 프로필은 편의상일 뿐 표준 확정이 아님.
- 대운: `DaeunProfile`(환산 일수, 반올림, 절입 기준) → `calculation_profile_id`. 만 나이/세는나이 둘 다 출력. 출생시간 미상이면 민감도 범위 표시.
- 음력: KARI 기반 `korean_lunar_calendar` + 중국 음력(`lunar-python`) 대조, 불일치 시 경고, 없는 윤달은 오류.
- API: `POST /api/v1/calendar/calculate`가 501 대신 `ChartCalculationResult`를 반환.

## 검증 상태 — 아직 V1이 아님
- 독립 교차검산은 `lunar-python` **1종**만 확보. 절기 시각은 최대 수십 초 차(근사 급수 쪽 오차로 추정) → 허용 1분.
- 외부 자료 2종 이상·100건 이상 골든 스위트가 없어 `GOLDEN_SUITE_COMPLETE=False`; 코드가 V1 부여를 막음(테스트 `test_v1_not_granted_until_golden_suite`).
- **문서 오류 발견**: `03_CALENDAR_VALIDATION.md`는 2000-01-01 19:25 서울 "진태양시는 戌시 후보"라고 적었으나 엔진 계산은 평균·진태양시 모두 18:4x → **酉시**(辛酉). 해당 문서는 정정 필요(손계산 값과 일치: 己卯 丙子 戊午 壬戌 / 변형 辛酉).
- 범위 밖: 1901 이전, 2050 이후, 해외 출생 좌표 자동 조회, 한국 외 지역의 서머타임 이력 검수.

## 다음 순서(제안)
1. 골든 스위트: 공신력 있는 만세력 2종 이상에서 100건 확보(한국천문연구원 월력요항 포함) → 조건 충족 시 V1 허용.
2. Mingli-Graph Layer1·2 + 근거 노드 스키마(순서형 판단) → 3. 다섯 학파 평가기 → 4. 사례 DB(검증 상태 필드) → 5. 상담 사전 커밋 → 6. 평가 하네스.

## v6.1 갱신 (Astro-Core 독립 검산 + Mingli-Graph 1·2층)
- 저장소는 git 이며 작업 시작 HEAD 는 `cb7be0a`; v6/v6.1 변경은 아직 커밋하지 않음.
- 검증 자료 레지스트리: `backend/golden/sources.json` (KASI=NOT_OBTAINED, sxtwl=NOT_RUN, lunar-python/HKO=OBTAINED).
- 골든 197건 `backend/golden/cases.json`, 결과 `report.json`, 불일치 판정 `judgements.json`, 절기 오차 분석 `term_analysis.json`.
- V1 게이트: `app/astro_core/verification_levels.py` (ASTRO/PILLARS/PROFILE/DAEUN + 내부 LUNAR). V1 차단 중.
- 절입 모호성: 절입 ±60초(1970 이전 ±420초)는 연·월주를 확정하지 않고 변형 반환, V3.
- Mingli-Graph: `backend/app/mingli/` — 근거 노드 스키마, 규칙 레지스트리(원전 대조 pending), Layer 1(월령·득령·통근·투간·강약 후보), Layer 2(천간합·합화 후보·육합·삼합·방합·충형파해·개고입묘·합충경합).
- API: `POST /api/v1/analysis/structure`.

## v6.1 후속 (KASI·sxtwl·Layer 3~5)
- **KASI**: OpenAPI 키 없이 공개 `달력자료`(2023~2028)를 취득(`tools/fetch_kasi.py`). KASI 스스로 "공식 발표 자료가 아니다"라고 명시 → 공식 월력요항으로 취급하지 않음. 월력요항은 2004년 이후만 제공되고 2012·2017 hwp 는 목록에 있으나 서버가 "파일을 찾을 수 없습니다"를 반환, 2001 은 범위 밖 → 5건 불일치는 `UNRESOLVED_OFFICIAL`.
- **한·중 음력 차이 원인**: `tools/lunar_astro.py`(삭·중기 천문 유도)가 UTC+8 에서 HKO, UTC+9 에서 korean_lunar_calendar 와 1963~2049 전 구간(2033 제외) 일치. 비공식 근거이며 공식 확인은 아님.
- **sxtwl 2.0.7**: Windows Py3.12 wheel 없음 → WSL Ubuntu virtualenv 에서 빌드(`tools/wsl/`). 절기 3300건 Skyfield 대비 최대 59초, 간지 194필드 lunar-python 과 불일치 0. 라이선스 BSD-3-Clause(upstream 원문). **lunar-python 과 동일 계열(寿星)로 추정 → 독립 1표**.
- 골든 491건(범주 11개), 일치 486, 설명된 불일치 5(통과 아님), 미설명 불일치 0.
- 레벨: ASTRO 부여(HKO·KASI·寿星 3계열). PILLARS/PROFILE/DAEUN/LUNAR 미부여. 필드별 독립 계열: 연·월·시 = 寿星 1, 일 = 寿星 + KASI. **V1 차단 유지**.
- Mingli Layer 3(생극제화)·4(격국·성패·조후 방향·용신 3종 분리)·5(대운 교체·입춘 구간, 특정/복수 연도). 궁통보감 개별 표·건록/양인 성패·월운·소운은 미구현.
- v6.3 상용화 설계: `docs/v6.3/`.
