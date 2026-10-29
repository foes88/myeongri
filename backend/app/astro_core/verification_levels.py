"""V1 게이트 분리. golden/report.json(tools.run_golden), golden/sources.json, golden/sxtwl_report.json 에서 계산한다.

레벨은 '무엇을 어떤 자료로 검증했는가'의 범위를 분리한 것이다. 검증하지 못한 영역은 부여하지 않는다.
  ASTRO_VERIFIED   절기 시각 : 서로 다른 계열 3종 이상(HKO, KASI 달력자료, 寿星계열 lunar-python/sxtwl)과 허용 오차 내 일치
  PILLARS_VERIFIED 연·월·일·시 간지 : '네 필드 모두' 서로 다른 계열 2종 이상이 확인 (계열이 같은 lunar-python·sxtwl 은 1종으로 센다)
  PROFILE_VERIFIED 시간 보정/23시/서머타임 : 시주 필드 독립 계열 2종 이상 + 프로필 골든 전건 통과 + tzdata 독립 검증 아님 명시
  DAEUN_VERIFIED   대운 순역·기산 : 독립 대운 계산원 2종 이상
  LUNAR_VERIFIED   한국 음력 : KASI '공식' 자료(월력요항)와 일치. 비공식 달력자료·천문 유도는 근거로만 기록, 미해결 불일치가 없어야 함

V1/V2/V3 매핑 (기존 gate.classify_verification 결과 + 레벨)
  V1 : 레벨 4종(음력 입력이면 LUNAR 포함) + 필수 자료 4종(KASI 공식, sxtwl, lunar-python, HKO) OBTAINED + 라이선스 확인 완료
       + 골든 100건 이상 + 해당 입력이 경계/변형/모호 상태가 아님
  V2 : 계산은 되었으나 위 조건 일부 미충족 (기본값)
  V3 : 기존 gate 의 V3 사유, 절입 모호(AMBIGUOUS), 명식 변형, 음력 한·중 불일치
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "golden"
REQUIRED_SOURCES = ("KASI", "sxtwl", "lunar-python", "HKO")
MIN_GOLDEN = 100
PILLAR_FIELDS = ("year", "month", "day", "hour")


@lru_cache(maxsize=1)
def _load() -> tuple[dict, dict, dict]:
    def rd(name):
        try:
            return json.loads((GOLDEN_DIR / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    return rd("report.json"), rd("sources.json"), rd("sxtwl_report.json")


def reload() -> None:
    _load.cache_clear()


def _all_pass(rep: dict, *cats: str) -> bool:
    for c in cats:
        d = rep.get("by_category", {}).get(c)
        if not d or set(d) - {"PASS"}:
            return False
    return True


def pillar_coverage() -> dict[str, list[str]]:
    """필드별로 '독립 계열' 확인 목록. 계열은 sources.json 의 lineage 로 묶는다."""
    rep, src, sx = _load()
    cov = {f: [] for f in PILLAR_FIELDS}
    if not rep:
        return cov
    lin = lambda name: src.get(name, {}).get("lineage", name)
    pil_ok = _all_pass(rep, "GEN", "TERM", "ZI", "SOLAR")
    if pil_ok and src.get("lunar-python", {}).get("status") == "OBTAINED":
        for f in PILLAR_FIELDS:
            cov[f].append(lin("lunar-python"))
    if sx and sx.get("pillar_fields_disagree") == 0 and sx.get("pillar_fields_agree_with_lunar_python", 0) > 0:
        for f in PILLAR_FIELDS:
            cov[f].append(lin("sxtwl"))
    if _all_pass(rep, "KASIDAY"):
        cov["day"].append(lin("KASI"))
    return {f: sorted(set(v)) for f, v in cov.items()}


def levels() -> dict[str, dict]:
    rep, src, sx = _load()
    why: dict[str, list[str]] = {k: [] for k in ("ASTRO_VERIFIED", "PILLARS_VERIFIED", "PROFILE_VERIFIED", "DAEUN_VERIFIED", "LUNAR_VERIFIED")}
    ev: dict[str, list[str]] = {k: [] for k in why}
    if not rep:
        for k in why:
            why[k].append("golden/report.json 없음")
        return {k: {"granted": False, "blockers": v, "evidence": []} for k, v in why.items()}
    # ASTRO
    lineages = set()
    if _all_pass(rep, "TERMTIME"):
        lineages.add("HKO"); ev["ASTRO_VERIFIED"].append("HKO 분 단위 절기 2026~2028 전건")
    else:
        why["ASTRO_VERIFIED"].append("HKO 분 단위 절기 불일치/미실행")
    if _all_pass(rep, "KASITERM"):
        lineages.add("KASI"); ev["ASTRO_VERIFIED"].append("KASI 달력자료(비공식) 절기 2023~2028 전건")
    else:
        why["ASTRO_VERIFIED"].append("KASI 달력자료 절기 불일치/미실행")
    te = rep.get("term_error", {})
    if te.get("vs_lunar_python_max_abs_s_by_decade", {}).get("2020", 99) <= 60:
        lineages.add("shouxing"); ev["ASTRO_VERIFIED"].append("lunar-python 1901~2050 (1970 이후 5초, 1900년대 44초)")
    else:
        why["ASTRO_VERIFIED"].append("lunar-python 대비 오차 60초 초과")
    if sx and sx.get("terms_max_abs_s_vs_skyfield", 999) <= 60:
        ev["ASTRO_VERIFIED"].append(f"sxtwl 절기 {sx['terms_compared']}건 최대 {sx['terms_max_abs_s_vs_skyfield']:.0f}초 (lunar-python 과 동일 계열)")
    if len(lineages) < 3:
        why["ASTRO_VERIFIED"].append(f"독립 계열 {len(lineages)}종뿐 — 3종 필요")
    # PILLARS
    cov = pillar_coverage()
    for f, v in cov.items():
        ev["PILLARS_VERIFIED"].append(f"{f}: {','.join(v) or '없음'}")
        if len(v) < 2:
            why["PILLARS_VERIFIED"].append(f"{f}주 독립 계열 {len(v)}종뿐({','.join(v) or '-'}) — 2종 필요")
    if not _all_pass(rep, "GEN", "TERM", "ZI"):
        why["PILLARS_VERIFIED"].append("간지 골든 불일치/미실행")
    # PROFILE
    if not _all_pass(rep, "SOLAR", "ZI", "TZ"):
        why["PROFILE_VERIFIED"].append("프로필 골든 불일치/미실행")
    if len(cov["hour"]) < 2:
        why["PROFILE_VERIFIED"].append("시주 독립 계열 1종뿐이라 시간 보정/23시 프로필 결과를 독립 확인하지 못함(태양시 보정량은 Meeus 근사식과만 교차)")
    why["PROFILE_VERIFIED"].append("한국 표준시·서머타임 연혁의 독립 자료(법령/KASI)와 대조하지 않음 — tzdata 는 엔진과 동일 자료")
    # DAEUN
    if not _all_pass(rep, "DAEUN"):
        why["DAEUN_VERIFIED"].append("대운 골든 불일치/미실행")
    why["DAEUN_VERIFIED"].append("독립 대운 계산원 1종(lunar-python Yun)뿐 — sxtwl·KASI 는 대운을 제공하지 않음")
    # LUNAR
    if src.get("KASI", {}).get("status") != "OBTAINED":
        why["LUNAR_VERIFIED"].append("KASI 공식 월력요항 미확보(2012·2017 파일 다운로드 불가, 2001 범위 밖) — 달력자료 2023~2028 은 비공식")
    if not _all_pass(rep, "LUNAR"):
        why["LUNAR_VERIFIED"].append("음력 골든(HKO 기준)에 미해결 불일치 5건(2001·2012·2017: 한·중 음력 차이로 설명되나 공식 확인 없음)")
    if _all_pass(rep, "KASILUNAR"):
        ev["LUNAR_VERIFIED"].append("KASI 달력자료(비공식) 2023~2028 음력 75개월 전건 일치")
    ev["LUNAR_VERIFIED"].append("천문 유도(삭·중기) UTC+9 = korean_lunar_calendar 1963~2049 (2033 제외)")
    return {k: {"granted": not v, "blockers": v, "evidence": ev[k]} for k, v in why.items()}


def v1_allowed() -> tuple[bool, list[str]]:
    rep, src, _ = _load()
    lv = levels()
    blockers = [f"{k}: {b}" for k, v in lv.items() if k != "LUNAR_VERIFIED" and not v["granted"] for b in v["blockers"]]
    for s in REQUIRED_SOURCES:
        if src.get(s, {}).get("status") != "OBTAINED":
            blockers.append(f"필수 자료 {s} = {src.get(s, {}).get('status', '없음')}")
    for s in REQUIRED_SOURCES:
        if "UNVERIFIED" in str(src.get(s, {}).get("license", "UNVERIFIED")):
            blockers.append(f"{s} 라이선스 미확인")
    if rep.get("total", 0) < MIN_GOLDEN:
        blockers.append(f"골든 {rep.get('total', 0)}건 < {MIN_GOLDEN}")
    return not blockers, blockers


def summary() -> dict:
    ok, blockers = v1_allowed()
    return {"levels": levels(), "pillar_coverage": pillar_coverage(), "v1_allowed": ok, "v1_blockers": blockers}


# ---------------------------------------------------------------------------------------------
# v6.4 범위 표기: V1/V2/V3 는 그대로 두고, '무엇이 검증되었고 무엇이 미검증인가'를 결과마다 따로 표시한다.
# 각 상태는 실제 요건이 충족된 경우에만 granted=True. 미검증이라고 개발·테스트를 막지 않는다.
KR_CN_LUNAR_DIFF_YEARS = (2001, 2012, 2017)  # 한·중 음력 불일치가 확인된 해(골든) — 더 있을 수 있음
KASI_UNOFFICIAL_YEARS = range(2023, 2029)


def _classical_counts() -> dict:
    """고전 원문 대조 현황. 'pending' = 원문 내용 확인(text_confirmed)이 끝나지 않은 고전 근거 주장 규칙 수(구현 규약 제외)."""
    try:
        from ..mingli import classical
        c = classical.summary()
        bs = c.get("by_status", {})
        return {"total": c["total"], "pending": c.get("classical_rules_pending", c["total"]), "by_status": bs,
                "text_confirmed": bs.get("text_confirmed", 0), "location_confirmed": bs.get("location_confirmed", 0),
                "implementation_convention": bs.get("implementation_convention", 0)}
    except Exception:  # 모듈/검증 파일이 없으면 fail-closed: 전부 pending
        from ..mingli.rules import RULES
        return {"total": len(RULES), "pending": len(RULES), "by_status": {}, "text_confirmed": 0, "location_confirmed": 0, "implementation_convention": 0}


def scope_status(calendar: str = "solar", lunar_year: int | None = None) -> dict:
    rep, src, sx = _load()
    lv = levels()
    cov = pillar_coverage()
    core_blockers = []
    if not lv["ASTRO_VERIFIED"]["granted"]:
        core_blockers.append("절기 시각 독립 3계열 검증 미충족")
    if len(cov["day"]) < 2:
        core_blockers.append("일주 독립 2계열 미충족")
    if not _all_pass(rep, "GEN", "TERM"):
        core_blockers.append("연·월·일주 골든 불일치/미실행")
    if not sx or sx.get("pillar_fields_disagree", 1) != 0:
        core_blockers.append("sxtwl 교차검산 불일치/미실행")
    cc = _classical_counts()
    if calendar == "lunar":
        if lunar_year in KR_CN_LUNAR_DIFF_YEARS:
            lunar = {"state": "PENDING_KR_CN_DIFFERENCE", "detail": f"{lunar_year}년은 한·중 음력이 다른 해로 확인됨 — KASI 공식 월력요항 미확보"}
        elif lunar_year in KASI_UNOFFICIAL_YEARS:
            lunar = {"state": "PARTIAL_UNOFFICIAL_MATCH", "detail": "KASI 달력자료(비공식)와 일치, 공식 월력요항 확인은 아님"}
        else:
            lunar = {"state": "PENDING", "detail": "한국 음력 공식 자료 미대조(천문 유도 및 라이브러리 일치만 있음)"}
    else:
        lunar = {"state": "NOT_APPLICABLE_SOLAR_INPUT", "detail": "양력 입력은 음력 변환을 거치지 않음(간지는 절기 기준)"}
    out = {
        "CORE_VALIDATED": {"granted": not core_blockers, "blockers": core_blockers,
                           "scope": "양력 입력의 연·월·일주(절기 경계 포함). 시주·대운·음력 제외",
                           "requirement": "절기 독립 3계열 + 일주 독립 2계열 + 연·월·일주 골든 전건 + sxtwl 불일치 0"},
        "TIME_PROFILE_VALIDATED": {"granted": lv["PROFILE_VERIFIED"]["granted"], "blockers": lv["PROFILE_VERIFIED"]["blockers"]},
        "LUNAR_KR_PENDING": lunar,
        "DAEUN_PROFILE_VALIDATED": {"granted": lv["DAEUN_VERIFIED"]["granted"], "blockers": lv["DAEUN_VERIFIED"]["blockers"]},
        "CLASSICAL_RULES_PENDING": {"pending": cc["pending"], "total": cc["total"], "counts": cc,
                                    "detail": "고전 원문 대조가 끝나지 않은 규칙 수. 이 수가 0 이 아니면 해석을 고전의 결론이라고 표현하지 않는다"},
    }
    return out


def unverified_notice(scope: dict) -> list[str]:
    n = []
    if not scope["CORE_VALIDATED"]["granted"]:
        n.append("핵심 간지(연·월·일주) 독립 검증이 완료되지 않았습니다.")
    if not scope["TIME_PROFILE_VALIDATED"]["granted"]:
        n.append("시주와 시간 보정 프로필은 독립 검증이 완료되지 않았습니다.")
    if not scope["DAEUN_PROFILE_VALIDATED"]["granted"]:
        n.append("대운 기산은 단일 계산원과만 대조되었습니다.")
    st = scope["LUNAR_KR_PENDING"]["state"]
    if st.startswith("PENDING") or st.startswith("PARTIAL"):
        n.append("한국 음력 변환은 공식 자료와 대조되지 않았습니다: " + scope["LUNAR_KR_PENDING"]["detail"])
    if scope["CLASSICAL_RULES_PENDING"]["pending"]:
        n.append(f"해석 규칙 {scope['CLASSICAL_RULES_PENDING']['pending']}/{scope['CLASSICAL_RULES_PENDING']['total']}개가 고전 원문 대조 전입니다.")
    return n
