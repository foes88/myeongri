# LLM 사용량 추적과 예상 원가

> **가격·토큰 수는 측정 전 가정값이다.** 실제 모델 단가는 계약/공시 시점의 값을 `PRICE_TABLE` 설정으로 넣고, 아래 산식에 대입해 계산한다. 이 문서의 숫자를 원가 확정치로 쓰지 않는다.

## 구조: LLM 은 마지막 단계에서만
| 단계 | 도구 | 비용 |
|---|---|---|
| 만세력·구조 분석(L1~L5) | 결정론적 코드 | LLM 0, 서버 CPU만 |
| 근거 검색(RAG) | 로컬 인덱스 | 미구현 |
| 설명 생성 | LLM(구조 JSON + claim_id 입력) | **여기가 유일한 변동원가** |
| 검수 | 규칙 검사기(L01~L12, X01~X08) | LLM 0 |

## 추적 (`llm_usage` 행/호출)
`report_id, stage, model_id, input_tokens, cached_input_tokens, output_tokens, latency_ms, status, retry_count, cost_micro_usd, prompt_version`.
집계 지표: 분석 유형별 평균·p95 원가, 성공률, 재시도율, 캐시 적중률, 보고서당 총원가, 무료 체험 총원가.

## 산식
```
call_cost = in_tok × P_in + cached_in × P_cached + out_tok × P_out
report_cost = Σ call_cost(설명 섹션) + 재시도 + 검수 재생성 + 저장·PDF 비용
```
토큰 가정(측정 후 교체): 구조 JSON 압축 입력 `I(depth)`, 출력 `O(depth, domains, years)`.
| depth | 입력 I (가정) | 출력 O (가정) |
|---|---|---|
| summary | 3k | 0.8k |
| detailed | 8k | 3k × (분야 수) |
| expert | 15k | 6k × (분야 수) |
기간이 늘면 `years` 만큼 구간 설명이 늘어나므로 O 에 `× ceil(years/2)` 가정을 두고 실측 보정한다.

## 원가 통제 장치
1. 구조 JSON 캐시 공유(동일 명식·기간·규칙 버전) → 계산 재사용, 깊이만 다른 상품의 설명만 생성.
2. 프롬프트 캐싱(공통 시스템 프롬프트·용어집), 섹션 병렬 아님 순차 + 조기 종료.
3. 무료 체험은 템플릿 + 최소 LLM, 일일 총액 한도(kill switch).
4. 검수 실패 재생성은 최대 2회, 그 이상은 템플릿 폴백.
5. 모델 라우팅: summary 는 소형 모델, expert 는 상위 모델(품질 평가 후 결정).

## 손익 점검 (가격 결정 전 필수)
`공헌이익 = 판매가 − PG 수수료 − 부가세 − report_cost − 환불예상 − CS 비용`. 환불률·재시도율은 베타 데이터 전에는 가정으로 민감도 분석(±50%)만 한다.

## 운영 대시보드
LLM 비용/일, 보고서 생성 성공률, 응답 시간 p50/p95, 오류율, 무료→유료 전환율, 구매 후 재열람·재구매율, 고객 문의·환불 사유 분류. (개인정보 없는 집계만)
