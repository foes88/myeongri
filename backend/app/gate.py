"""명식 검증 상태 판정 (knowledge/16 §B 의 V1/V2/V3). 달력 계산은 하지 않는다."""
from __future__ import annotations

from datetime import time

TERM_NEAR_MINUTES = 24 * 60  # 절입 ±1일 이내는 연·월주 분기 후보를 병렬 검토 (02, 14 S06)


def classify_verification(
    *,
    pillars_given: dict[str, str] | None,
    verifications: list[dict] | None = None,
    birth_time: time | None = None,
    hour_known: bool = True,
    calendar: str = "solar",
    is_leap_month: bool | None = False,
    term_distance_minutes: int | None = None,
) -> dict:
    """verifications: [{'tool':str,'version':str,'pillars':{...}}] — 서로 독립인 만세력 결과."""
    reasons: list[str] = []
    if not hour_known or birth_time is None and pillars_given is not None and "hour" not in pillars_given:
        reasons.append("hour_unknown")
    if birth_time is not None and (birth_time >= time(23, 0) or birth_time < time(1, 0)):
        reasons.append("yaja_si_profile_split")
    if calendar == "lunar" and is_leap_month is None:
        reasons.append("leap_month_unspecified")
    if term_distance_minutes is not None and abs(term_distance_minutes) <= TERM_NEAR_MINUTES:
        reasons.append("solar_term_boundary")
    if reasons:
        return {"status": "V3", "reasons": reasons, "may_claim_verified": False}

    ok = [v for v in (verifications or []) if v.get("tool") and v.get("version") and v.get("pillars")]
    tools = {v["tool"] for v in ok}
    if len(tools) >= 2 and all(v["pillars"] == ok[0]["pillars"] for v in ok):
        return {"status": "V1", "reasons": [], "may_claim_verified": True}
    if len(tools) >= 2:
        return {"status": "V3", "reasons": ["verifier_disagreement"], "may_claim_verified": False}
    if pillars_given:
        return {"status": "V2", "reasons": ["user_provided_unverified"], "may_claim_verified": False}
    return {"status": "V3", "reasons": ["no_pillars"], "may_claim_verified": False}
