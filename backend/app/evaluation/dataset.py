"""합성 명식 평가 데이터셋(Track A). 실제 출생정보와 연계하지 않는다 — 간지 4쌍과 가상 대운 순서만 사용.

각 쌍은 '한 가지 요인만' 바꾼 두 입력이며, 어떤 해석 측면(facet)이 달라져야 하는지(expected_facets)를 사전에 적어 둔다.
달력상 실현 가능 여부(calendar_realizable)는 1901~2049 사이에 네 기둥이 모두 맞는 날이 존재하는지 불리언으로만 기록하고 날짜는 저장하지 않는다.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from ..astro_core import engine as astro
from ..astro_core import verification_levels as vl
from ..consult import agent

STEMS, BR = "甲乙丙丁戊己庚辛壬癸", "子丑寅卯辰巳午未申酉戌亥"
BASE = {"year": "癸卯", "month": "庚申", "day": "甲子", "hour": "丙寅"}


def valid_gz(gz: str) -> bool:
    return len(gz) == 2 and gz[0] in STEMS and gz[1] in BR and STEMS.index(gz[0]) % 2 == BR.index(gz[1]) % 2


def calendar_realizable(p: dict[str, str]) -> bool:
    """네 기둥이 모두 일치하는 실제 날짜·시각이 1901~2049 에 존재하는가(날짜는 반환하지 않음)."""
    if not all(valid_gz(v) for v in p.values()):
        return False
    di = astro.idx60(*p["day"])
    d = date(1901, 1, 1)
    while astro.day_pillar_index(d) != di:
        d += timedelta(days=1)
    hb = BR.index(p["hour"][1])
    if STEMS.index(p["hour"][0]) != (STEMS.index(p["day"][0]) % 5 * 2 + hb) % 10:
        return False  # 시주 천간이 일간(五鼠遁)과 맞지 않음
    while d.year <= 2049:
        u = datetime(d.year, d.month, d.day, 12, tzinfo=timezone(timedelta(hours=9))).astimezone(timezone.utc)
        yp, mp, _ = astro.year_month_pillars(u)
        if yp == p["year"] and mp == p["month"]:
            return True
        d += timedelta(days=60)
    return False


def synthetic_cycles(pillars: dict[str, str], gender: str, first_year: int = 2004, first_month_day: str = "06-15") -> dict:
    base = astro.idx60(*pillars["month"])
    yang = STEMS.index(pillars["year"][0]) % 2 == 0
    forward = yang == (gender == "male")
    step = 1 if forward else -1
    cycles = [{"order": i + 1, "pillar": astro.gz(base + step * (i + 1)), "start_age_man": 10 * i + 4, "start_age_korean": 10 * i + 5,
               "start_date": f"{first_year + 10 * i}-{first_month_day}"} for i in range(10)]
    return {"calculation_profile_id": "synthetic/eval", "direction": "forward" if forward else "backward", "first_luck_date": f"{first_year}-{first_month_day}", "cycles": cycles}


def synthetic_precommit(pillars: dict[str, str], *, gender: str = "male", years=(2030,), domains=("wealth", "career"), depth="expert",
                        cycles: dict | None = None, ruleset_tag: str = "eval") -> dict:
    scope = vl.scope_status("solar")
    scope["CORE_VALIDATED"] = dict(scope["CORE_VALIDATED"], granted=False, blockers=["합성 명식 — 실제 출생 정보로 계산한 결과가 아니며 검증 대상이 아님"])
    chart = {"variants": [{"variant_id": "v1", "pillars": dict(pillars), "is_primary": True, "produced_by": []}],
             "verification": {"status": "V2", "reasons": ["synthetic_eval"], "may_claim_verified": False, "scope": scope, "unverified_notice": ["합성 명식 — 평가 전용(실제 출생정보와 무관)"] + vl.unverified_notice(scope)},
             "calculation_profile_id": "synthetic/eval", "zi_profile": "n/a", "pillars": dict(pillars), "libraries": {}, "warnings": [],
             "daeun": cycles or synthetic_cycles(pillars, gender)}
    pre = agent.build_precommit(chart, variant_id="v1", years=list(years), domains=list(domains), depth=depth, input_fingerprint={"synthetic": ruleset_tag, "p": pillars}, gender=gender)
    pre["content_hash"] = agent.store.sha256({k: v for k, v in pre.items() if k != "content_hash"})
    return pre


@dataclass
class Spec:
    pillars: dict
    gender: str = "male"
    years: tuple = (2030,)
    domains: tuple = ("wealth", "career")
    cycles_first_year: int = 2004
    cycles_md: str = "06-15"
    cycle_override: list[str] | None = None   # 대운 간지 목록 직접 지정


@dataclass
class Pair:
    pair_id: str
    factor: str
    a: Spec
    b: Spec
    expected_facets: set[str] = field(default_factory=set)   # b 에서 달라져야 하는 해석 측면
    note: str = ""


def _swap(base: dict, **kw) -> dict:
    d = dict(base)
    d.update(kw)
    return d


def build_pairs() -> list[Pair]:
    P = []
    P.append(Pair("D01", "일간만 다름", Spec(BASE), Spec(_swap(BASE, day="丙子")), {"deukryeong", "strength", "gyeokguk", "structure", "tonggeun"}, "일지 子 고정, 일간 甲→丙"))
    P.append(Pair("D02", "월령(월지)만 다름", Spec(BASE), Spec(_swap(BASE, month="壬子")), {"month", "deukryeong", "gyeokguk"}, "월지 申→子"))
    P.append(Pair("D03", "통근 구조만 다름", Spec(BASE), Spec(_swap(BASE, hour="丙午")), {"tonggeun", "relations"}, "시지 寅→午 (丙의 뿌리 변화)"))
    P.append(Pair("D04", "격국 후보만 다름", Spec(BASE), Spec(_swap(BASE, month="辛酉")), {"gyeokguk", "month", "deukryeong"}, "월주 庚申→辛酉: 칠살격 계열→정관격 계열"))
    P.append(Pair("D05", "조후(계절)만 다름", Spec(_swap(BASE, month="壬子")), Spec(_swap(BASE, month="壬午")), {"month", "gyeokguk", "schools"}, "월지 子(겨울)→午(여름)"))
    P.append(Pair("D06", "합충 관계만 다름", Spec(_swap(BASE, hour="丁未")), Spec(_swap(BASE, hour="丁酉")), {"relations"}, "시지 未→酉 (연지 卯와 卯酉 충)"))
    P.append(Pair("D07", "대운만 다름", Spec(BASE), Spec(BASE, cycle_override=["乙酉", "丙戌", "丁亥", "戊子", "己丑", "庚寅", "辛卯", "壬辰", "癸巳", "甲午"]), {"period"}, "원국 동일, 대운 배열만 다름"))
    P.append(Pair("D08", "세운(연도)만 다름", Spec(BASE, years=(2030,)), Spec(BASE, years=(2031,)), {"period"}, "원국·대운 동일, 분석 연도만 다름"))
    P.append(Pair("D09", "운세 분야만 다름", Spec(BASE, domains=("wealth",)), Spec(BASE, domains=("career",)), {"domain"}, "같은 명식·같은 연도, 재물 vs 직업"))
    P.append(Pair("D10", "분야 다름(연애 vs 가족)", Spec(BASE, domains=("love_marriage",)), Spec(BASE, domains=("family",)), {"domain"}, "궁위 신호가 다른 분야"))
    P.append(Pair("D11", "대운 교체 연도", Spec(BASE, years=(2030,), cycles_first_year=2000, cycles_md="06-15"), Spec(BASE, years=(2030,), cycles_first_year=2004, cycles_md="06-15"), {"period"},
                  "분석 연도 중반(6월)에 대운이 교체되는 배열 vs 교체되지 않는 배열"))
    P.append(Pair("D12", "성별만 다름(연애 분야)", Spec(BASE, domains=("love_marriage",), gender="male"), Spec(BASE, domains=("love_marriage",), gender="female"), {"domain", "period"},
                  "배우자성이 재성↔관성으로 바뀜(대운 방향도 달라짐)"))
    return P


def conflict_chart_spec() -> Spec | None:
    """학파(용신 후보)가 서로 겹치지 않는 합성 명식 하나를 찾는다(시드 고정)."""
    from ..mingli import analyze_structure
    rng = random.Random(66)
    for _ in range(400):
        p = {k: STEMS[i % 10] + BR[i % 12] for k in ("year", "month", "day", "hour") for i in [rng.randrange(60)]}
        r = analyze_structure(p)
        if any(x["relation"] == "충돌" for x in r["schools"]["pairs"]):
            return Spec(p)
    return None


def barnum_set(n: int = 12, seed: int = 6601) -> list[Spec]:
    rng = random.Random(seed)
    out = []
    while len(out) < n:
        p = {k: STEMS[i % 10] + BR[i % 12] for k in ("year", "month", "day", "hour") for i in [rng.randrange(60)]}
        if p not in [s.pillars for s in out]:
            out.append(Spec(p, gender=rng.choice(["male", "female"])))
    return out


def pre_of(spec: Spec) -> dict:
    cyc = synthetic_cycles(spec.pillars, spec.gender, spec.cycles_first_year, spec.cycles_md)
    if spec.cycle_override:
        for c, g in zip(cyc["cycles"], spec.cycle_override):
            c["pillar"] = g
    return synthetic_precommit(spec.pillars, gender=spec.gender, years=spec.years, domains=spec.domains, cycles=cyc)
