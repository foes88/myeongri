"""계산 요소별 검증 상태표(VERIFIED / PARTIAL / UNVERIFIED / CONFLICT). 게이트(scope_status)의 승인 여부에서 도출하므로 게이트가 바뀌면 함께 바뀐다.

규칙
- VERIFIED: 해당 요소의 게이트가 승인(granted)되어 독립 계열 요건을 충족한 경우만.
- PARTIAL: 일부 근거(교차검증·독립 계열 1종·2차 자료)는 있으나 게이트 요건 미충족.
- UNVERIFIED: 독립 확인 수단이 아직 없음.
- CONFLICT: 독립 자료끼리 값이 다른 알려진 불일치가 남아 있음(해결 전에는 보증 대상 제외).
같은 원천을 공유하는 라이브러리 간 일치는 독립 검증으로 세지 않는다. 상태를 올리려고 기준을 낮추지 않는다.
"""
from __future__ import annotations

from . import verification_levels as vl

ORDER = {"VERIFIED": 0, "PARTIAL": 1, "UNVERIFIED": 2, "CONFLICT": 3}


def matrix(calendar: str = "solar") -> list[dict]:
    sc = vl.scope_status(calendar)
    core, prof, daeun = sc["CORE_VALIDATED"], sc["TIME_PROFILE_VALIDATED"], sc["DAEUN_PROFILE_VALIDATED"]
    lunar = sc["LUNAR_KR_PENDING"]
    rows = []

    def add(element, status, evidence, blockers=None, guarantee=None):
        rows.append({"element": element, "status": status, "evidence": evidence, "blockers": blockers or [],
                     "commercial_guarantee": status == "VERIFIED" if guarantee is None else guarantee})

    add("양력 입력의 연·월·일주(절기 경계 포함)", "VERIFIED" if core["granted"] else "PARTIAL", "절기 독립 3계열 + 일주 독립 2계열 + 골든 전건 일치 + sxtwl 불일치 0", core["blockers"])
    add("입춘·절입 경계(초 단위 판정, 경계 ±폭 이내 양쪽 명식 제시)", "VERIFIED" if core["granted"] else "PARTIAL", "절기 독립 3계열. 경계 ±폭 이내는 확정하지 않고 변형으로 반환", core["blockers"])
    if calendar == "lunar" or lunar["state"] not in ("NOT_APPLICABLE_SOLAR_INPUT",):
        st = "VERIFIED" if lunar["state"] == "OFFICIAL_MONTHS_VERIFIED" else ("CONFLICT" if "MISMATCH" in lunar["state"] else "PARTIAL")
        add("음력·윤달 → 양력 변환", st, f"입력 연도별 상태: {lunar['state']}", [lunar.get("detail", "")], st == "VERIFIED")
    else:
        add("음력·윤달 → 양력 변환", "PARTIAL", "양력 입력에서는 사용하지 않음. 음력 입력은 연도별로 KASI 월력요항 대조 상태가 다름(한·중 차이 연도 존재)", ["음력 입력 연도마다 공식 월 대조 필요"], False)
    add("시주(시지·오서둔)", "VERIFIED" if prof["granted"] else "PARTIAL", "시주 독립 계열 1종 + 내부 교차", prof["blockers"])
    add("평균태양시 경도 보정", "VERIFIED" if prof["granted"] else "PARTIAL", "경도×4분 공식. 출생지 좌표는 시청·군청 대표 위치 근사(전국 161곳)", prof["blockers"] + ["출생지 좌표는 근사값(실제 출생지와 차이 가능)"])
    add("진태양시·균시차", "VERIFIED" if prof["granted"] else "PARTIAL", "Meeus 근사식과 교차. 독립 천문 계열과의 대조는 아직 없음", prof["blockers"])
    add("한국 역사적 표준시·서머타임", "CONFLICT", "2차 공개 자료 28/30 일치. 1954-03-21 전환 시각이 자료(00:30)와 tzdata(00:00) 사이 30분 불일치", ["법령 1차 원문 미확인", "tzdata 는 엔진과 같은 원천(독립 아님)"], False)
    add("23시 경계·야자시 학파 차이", "PARTIAL", "3가지 규칙을 모두 계산해 명식이 갈리면 변형으로 제시(자동 선택하지 않음). 학파 간 정답 판정은 하지 않음", prof["blockers"], False)
    add("대운 방향·시작 시점", "VERIFIED" if daeun["granted"] else "PARTIAL", "독립 대운 계산원 1종(lunar-python Yun)과 대조", daeun["blockers"])
    add("세운·대운 교체 구간", "PARTIAL", "입춘(검증된 절입)과 대운 기산일로 구간 분할. 교체일은 대운 기산에 의존", daeun["blockers"], False)
    return rows


def summary(calendar: str = "solar") -> dict:
    rows = matrix(calendar)
    counts = {k: sum(1 for r in rows if r["status"] == k) for k in ORDER}
    ok, blockers = vl.v1_allowed()
    return {"calendar": calendar, "counts": counts, "elements": rows, "v1_granted": ok, "v1_blockers": blockers,
            "statement": "VERIFIED 로 표시된 요소만 정확성을 보증 대상으로 삼는다. 나머지는 참고용 계산이며 상용 정확성 보증에서 제외한다."}
