# 연도·기간·분야별 분석 요청 API (계약 초안)

현재 구현된 엔드포인트(검증용, 인증·과금 없음): `POST /api/v1/calendar/calculate`, `/analysis/structure`, `/analysis/periods`.
아래 `/reports` 계열은 **설계만** 있다.

## 요청
`POST /api/v1/reports` (Idempotency-Key 헤더 필수)
```json
{
  "profile_id": "uuid",
  "variant_id": "v1",
  "product_code": "PERIOD_DETAILED",
  "depth": "summary | detailed | expert",
  "period": {
    "kind": "year | range5 | range10 | month | compare_years",
    "years": [2030],
    "month": "2030-03",
    "compare": [2030, 2031]
  },
  "domains": ["overall", "wealth_business", "career", "documents_realestate", "love_marriage", "family", "health_traditional"],
  "questions": ["선택 질문 최대 3개"],
  "reality_context": {"job": "선택", "note": "선택(상담 층 전용)"},
  "accept": {"traditional_interpretation": true, "variant_notice": true}
}
```
규칙
- `kind` 별 검증: `year` 1개 연도, `range5/10` 시작 연도 1개(5·10년 전개), `month` 연월 1개(월운은 아직 미구현 → 지원 전까지 422), `compare_years` 정확히 2개.
- 대운 교체 연도는 응답에서 자동으로 **구간 분리**(`segments[]`): 대운 교체일·입춘. 사용자가 연도 단위만 선택해도 구간 정보를 반환.
- `reality_context` 는 구조 분석에 전달되지 않는다. 상담 설명 생성에만 쓰이며 응답에 `used_for: "advice_only"` 로 표기.
- 명식 `verification.status` 가 V1 이 아니면 `release_gate` 판단: **유료 상품은 `422 CHART_NOT_VERIFIED`**, 무료 체험은 "조건부 참고" 라벨로만 허용(정책 결정 필요).
- 변형 명식(`variants>1`) 또는 절입 모호: `variant_id` 를 명시하지 않으면 `409 VARIANT_REQUIRED` + 변형 목록 반환(자동 선택 금지).

## 응답 (비동기)
`202 { "report_id": "...", "status": "queued", "estimated_seconds": 40 }` → `GET /api/v1/reports/{id}`
```json
{
  "report_id": "...", "status": "succeeded",
  "chart_snapshot_id": "...", "calculation_profile_id": "...", "ruleset_version": "mingli-l12-0.1.0", "model_version": "...",
  "verification": {"status": "V2", "levels": {"ASTRO_VERIFIED": true, "PILLARS_VERIFIED": false}},
  "structure": {"layers": "1-5", "claims": ["L1-DEUK-001"], "validation": {"ok": true}},
  "sections": [{"domain": "career", "depth": "detailed", "text_ref": "...", "claim_ids": ["L3-004"], "disagreements": [...]}],
  "segments": [...], "disclaimer": "전통 명리학의 해석이며 예측력은 검증되지 않았습니다",
  "revision": 1
}
```
오류 코드: `400` 형식, `401/403` 인증·소유권, `402 INSUFFICIENT_CREDIT`, `409 VARIANT_REQUIRED | DUPLICATE_REQUEST`, `422 CHART_NOT_VERIFIED | UNSUPPORTED_PERIOD`, `429` 한도, `503 ENGINE_UNAVAILABLE`(**해석 엔진 없으면 보고서 생성 금지**).

## 보조 API
`GET /reports` 목록 · `GET /reports/{id}/revisions` · `POST /reports/{id}/followups`(추가 질문, 구조 JSON 변경 불가) · `POST /reports/{id}/pdf` · `POST /reports/{id}/corrections`(오류 신고) · `DELETE /reports/{id}`.

## 동일 명식·기간 계산 공유
`(chart_snapshot_id, period, ruleset_version)` 로 **구조 분석 캐시**. depth 가 달라도 구조 JSON 은 공유하고, 설명 생성 단계만 depth 별로 다르게 실행 → 원가 절감과 일관성(06 문서).
