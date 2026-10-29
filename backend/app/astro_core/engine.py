"""사주 네 기둥·대운·세운·월운의 결정론적 계산. LLM 미사용.

설계 원칙
- 연주·월주는 '절대 시각(UTC)'과 절입 시각을 비교한다. 시간대/경도 보정은 일주·시주 경계에만 쓴다.
  따라서 UTC에서 한 번만 보정하며 시간대 보정과 경도 보정이 이중 적용될 수 없다.
- 학파별로 갈리는 선택(시간 보정, 23시 처리)은 프로필이다. 프로필에 따라 명식이 달라지면
  변형(ChartVariant)으로 모두 반환하고 하나를 천문학적 정답으로 확정하지 않는다.
"""
from __future__ import annotations

import calendar as _cal
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from zoneinfo import ZoneInfo

from . import ephemeris as eph
from . import lunar as lunar_mod
from . import verification_levels as vlevels
from ..gate import classify_verification

CALC_VERSION = "astro-core-0.1.0"
STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
TERM_NAMES = ["春分", "清明", "穀雨", "立夏", "小滿", "芒種", "夏至", "小暑", "大暑", "立秋", "處暑", "白露",
              "秋分", "寒露", "霜降", "立冬", "小雪", "大雪", "冬至", "小寒", "大寒", "立春", "雨水", "驚蟄"]
LICHUN = 21

# V1 은 verification_levels.v1_allowed() (골든 100건+, 필수 자료 4종, 라이선스 점검, 4개 레벨)가 모두 충족될 때만.
GOLDEN_SUITE_COMPLETE = vlevels.v1_allowed()[0]

# 절입 모호 판정 폭(초). 독립 구현·시간척도(ΔT) 차이로 절입 순간이 이만큼 흔들릴 수 있다고 보고 이 안의 입력은 확정하지 않는다.
# 근거: golden/term_analysis.json — lunar-python 대비 1970년 이후 최대 5초, 1900년대 최대 44초;
#       HKO 날짜 단위 대조에서 1928년 등 6분 어긋난 사례. 폭은 보수적으로 잡았다.
AMBIGUITY_SECONDS_MODERN = 60
AMBIGUITY_SECONDS_EARLY = 420  # 1970년 이전

# 출생지 좌표: app/places.py (시청 소재지 근사). 사용자 입력 좌표가 우선한다.
from ..places import PLACES  # noqa: E402


class TimeProfile(str, Enum):
    CIVIL_TIME = "CIVIL_TIME"
    LOCAL_MEAN_SOLAR_TIME = "LOCAL_MEAN_SOLAR_TIME"
    LOCAL_APPARENT_SOLAR_TIME = "LOCAL_APPARENT_SOLAR_TIME"


class ZiProfile(str, Enum):
    ZI_2300_DAY_CHANGE = "ZI_2300_DAY_CHANGE"  # 23:00 에 일주 교체, 23시 이후 시주 천간은 다음 날 기준
    MIDNIGHT_SAME_DAY_STEM = "MIDNIGHT_SAME_DAY_STEM"  # 00:00 일주 교체, 23시대 子시 천간은 당일 기준
    MIDNIGHT_NEXT_DAY_STEM = "MIDNIGHT_NEXT_DAY_STEM"  # 00:00 일주 교체, 23시대 子시 천간은 다음 날 기준


@dataclass(frozen=True)
class DaeunProfile:
    """3일=1년 환산법의 세부 선택. 값이 하나라도 다르면 profile_id 가 달라진다."""
    year_days: int = 360          # 1년을 며칠로 보는가 (1일=4개월 → 120일, 2시간=10일)
    rounding: str = "floor"       # 'floor' | 'round' (환산한 일수를 정수일로 만드는 방식)
    term_boundary: str = "exact_instant"  # 절입 '순간'(초 단위)과 출생 순간의 차

    @property
    def profile_id(self) -> str:
        return f"daeun/3d1y/{self.year_days}d/{self.rounding}/{self.term_boundary}/v1"


@dataclass
class ChartCalculationResult:
    input: dict
    normalized: dict
    timezone: str
    coordinates: dict
    solar_term_boundaries: dict
    time_profile: dict
    zi_profile: str
    pillars: dict
    daeun: dict | None
    variants: list
    verification: dict
    libraries: dict
    lunar_conversion: dict | None
    calendar_range: str
    calculation_profile_id: str
    warnings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------- 간지 기초 ----------
def idx60(stem: str, branch: str) -> int:
    s, b = STEMS.index(stem), BRANCHES.index(branch)
    if s % 2 != b % 2:
        raise ValueError(f"존재하지 않는 간지 조합: {stem}{branch}")
    return next(i for i in range(60) if i % 10 == s and i % 12 == b)


def gz(i: int) -> str:
    return STEMS[i % 10] + BRANCHES[i % 12]


def _jdn(d: date) -> int:
    return d.toordinal() + 1721425


def day_pillar_index(d: date) -> int:
    return (_jdn(d) + 49) % 60  # JDN 2451545(2000-01-01) → 戊午


def _jie_events(utc: datetime) -> list[tuple[datetime, int]]:
    return [(t, k) for t, k in eph.solar_terms_around(utc) if k % 2 == 1]


def year_month_pillars(utc: datetime) -> tuple[str, str, dict]:
    ev = _jie_events(utc)
    past = [(t, k) for t, k in ev if t <= utc]
    future = [(t, k) for t, k in ev if t > utc]
    lichun_t = max(t for t, k in past if k == LICHUN)
    year_idx = (lichun_t.year - 4) % 60
    cur_t, cur_k = past[-1]
    n = ((cur_k - LICHUN) // 2) % 12  # 0=寅월 … 11=丑월
    month_branch = (2 + n) % 12
    month_stem = (STEMS.index(gz(year_idx)[0]) % 5 * 2 + 2 + n) % 10  # 五虎遁
    month = STEMS[month_stem] + BRANCHES[month_branch]
    nxt_t, nxt_k = future[0]
    return gz(year_idx), month, {
        "previous_jie": _term(cur_t, cur_k), "next_jie": _term(nxt_t, nxt_k), "lichun_of_saju_year": _term(lichun_t, LICHUN),
    }


def _term(t: datetime, k: int) -> dict:
    return {"name": TERM_NAMES[k], "index": k, "ecliptic_longitude_deg": 15 * k, "utc": t.isoformat()}


def day_hour_pillars(pt: datetime, zi: ZiProfile, hour_known: bool) -> tuple[str, str | None]:
    d = pt.date()
    late = pt.hour >= 23
    eff = d + timedelta(days=1) if (late and zi == ZiProfile.ZI_2300_DAY_CHANGE) else d
    day_i = day_pillar_index(eff)
    if not hour_known:
        return gz(day_i), None
    stem_day_i = day_pillar_index(d + timedelta(days=1)) if (late and zi != ZiProfile.MIDNIGHT_SAME_DAY_STEM) else day_i
    branch = ((pt.hour + 1) // 2) % 12
    hour_stem = (stem_day_i % 10 % 5 * 2 + branch) % 10  # 五鼠遁
    return gz(day_i), STEMS[hour_stem] + BRANCHES[branch]


# ---------- 시간 보정 ----------
def _pillar_time(profile: TimeProfile, aware_local: datetime, utc: datetime, lon: float, dst_policy: str) -> tuple[datetime, dict]:
    info = {"profile": profile.value, "longitude_offset_from_utc_minutes": None, "equation_of_time_minutes": None,
            "dst_removed_minutes": 0.0, "difference_vs_civil_minutes": 0.0}
    if profile == TimeProfile.CIVIL_TIME:
        pt = aware_local.replace(tzinfo=None)
        if dst_policy == "standard_time":
            dst = aware_local.dst() or timedelta(0)
            pt -= dst
            info["dst_removed_minutes"] = dst.total_seconds() / 60
        return pt, info
    # 태양시 프로필은 UTC 에서 곧바로 구한다 → 법정 시간대 오프셋(역사적 +8:30 등)과 경도 보정이 겹치지 않는다.
    lon_min = lon * 4.0
    info["longitude_offset_from_utc_minutes"] = lon_min  # 경도×4분: UTC 에 대한 오프셋(시계 시각 대비 보정량이 아님)
    t = utc + timedelta(minutes=lon_min)
    if profile == TimeProfile.LOCAL_APPARENT_SOLAR_TIME:
        e = eph.equation_of_time_minutes(utc)
        info["equation_of_time_minutes"] = e
        t += timedelta(minutes=e)
    info["difference_vs_civil_minutes"] = (t.replace(tzinfo=None) - aware_local.replace(tzinfo=None)).total_seconds() / 60
    return t.replace(tzinfo=None), info


def _resolve_instants(naive: datetime, tz: ZoneInfo) -> list[tuple[int, datetime, datetime]]:
    """로컬 벽시계 → [(fold, aware_local, utc)]. 서머타임 중복 시각이면 2개, 존재하지 않는 시각이면 오류."""
    out = []
    for fold in (0, 1):
        a = naive.replace(tzinfo=tz, fold=fold)
        u = a.astimezone(timezone.utc)
        if u.astimezone(tz).replace(tzinfo=None) != naive:
            raise ValueError(f"해당 지역시간에 존재하지 않는 시각입니다(서머타임 건너뜀 구간): {naive.isoformat()} {tz.key}")
        out.append((fold, a, u))
    return [out[0]] if out[0][2] == out[1][2] else out


def _add_ymd(d: date, years: int, months: int, days: int) -> date:
    m0 = d.month - 1 + months + years * 12
    y, m = d.year + m0 // 12, m0 % 12 + 1
    day = min(d.day, _cal.monthrange(y, m)[1])
    return date(y, m, day) + timedelta(days=days)


# ---------- 대운 ----------
def compute_daeun(utc: datetime, birth_local: datetime, year_pillar: str, month_pillar: str, gender: str,
                  profile: DaeunProfile, count: int = 10) -> dict:
    yang = STEMS.index(year_pillar[0]) % 2 == 0
    forward = yang == (gender == "male")
    ev = _jie_events(utc)
    if forward:
        t, k = next((t, k) for t, k in ev if t > utc)
    else:
        t, k = [(t, k) for t, k in ev if t <= utc][-1]
    diff_s = abs((t - utc).total_seconds())
    total = diff_s / 86400.0 * (profile.year_days / 3.0)  # 1일 = year_days/3 일 (360일 모델이면 120일)
    total_days = int(total + 0.5) if profile.rounding == "round" else int(total)
    y, m, d = total_days // profile.year_days, (total_days % profile.year_days) // 30, total_days % 30
    first = _add_ymd(birth_local.date(), y, m, d)
    base = idx60(month_pillar[0], month_pillar[1])
    step = 1 if forward else -1
    cycles = []
    for n in range(count):
        start = _add_ymd(first, 10 * n, 0, 0)
        cycles.append({"order": n + 1, "pillar": gz(base + step * (n + 1)), "start_age_man": y + 10 * n,
                       "start_age_korean": start.year - birth_local.year + 1, "start_date": start.isoformat()})
    return {
        "calculation_profile_id": profile.profile_id,
        "direction": "forward" if forward else "backward",
        "direction_basis": f"연간 {'양' if yang else '음'} × {'남' if gender == 'male' else '여'}",
        "reference_jie": _term(t, k),
        "distance_to_jie_seconds": diff_s,
        "equivalent_days": total, "equivalent_days_used": total_days,
        "start_age": {"years": y, "months": m, "days": d},
        "start_age_man": y,
        "start_age_korean": first.year - birth_local.year + 1,
        "first_luck_date": first.isoformat(),
        "cycles": cycles,
    }


def sewun(year: int) -> dict:
    """세운: 해당 양력 연도의 연주. 교체 시각은 그해 입춘(절대 시각)이다."""
    lichun = next(t for t, k in eph.solar_terms_in_utc_year(year) if k == LICHUN)
    return {"year": year, "pillar": gz(year - 4), "starts_utc": lichun.isoformat(), "boundary": "立春"}


def wolun(year: int) -> list[dict]:
    """월운: 입춘 년도 기준 12개월 (寅월 ~ 丑월). 각 월은 해당 절입 순간에 시작한다."""
    ys = STEMS.index(gz(year - 4)[0])
    evs = sorted((t, k) for y in (year, year + 1) for t, k in eph.solar_terms_in_utc_year(y) if k % 2 == 1)
    start = next(i for i, (t, k) in enumerate(evs) if k == LICHUN and t.year == year)
    out = []
    for n in range(12):
        t, k = evs[start + n]
        out.append({"month_order": n + 1, "pillar": STEMS[(ys % 5 * 2 + 2 + n) % 10] + BRANCHES[(2 + n) % 12],
                    "term": TERM_NAMES[k], "starts_utc": t.isoformat()})
    return out


# ---------- 독립 교차검산 (lunar-python) ----------
def _crosscheck(utc: datetime, pt: datetime, zi: ZiProfile, pillars: dict) -> dict:
    from lunar_python import Solar
    bj = utc.astimezone(timezone(timedelta(hours=8)))
    ym = Solar.fromYmdHms(bj.year, bj.month, bj.day, bj.hour, bj.minute, bj.second).getLunar()
    dh = Solar.fromYmdHms(pt.year, pt.month, pt.day, pt.hour, pt.minute, pt.second).getLunar()
    other = {"year": ym.getYearInGanZhiExact(), "month": ym.getMonthInGanZhiExact(),
             "day": dh.getDayInGanZhiExact() if zi == ZiProfile.ZI_2300_DAY_CHANGE else dh.getDayInGanZhi()}
    if "hour" in pillars:
        other["hour"] = dh.getTimeInGanZhi()
    compared = {p: v for p, v in other.items() if p in pillars and not (p == "hour" and pt.hour >= 23)}
    diffs = {p: {"engine": pillars[p], "other": v} for p, v in compared.items() if pillars[p] != v}
    return {"tool": "lunar-python", "version": "1.4.8", "compared": sorted(compared), "agree": not diffs, "diffs": diffs,
            "pillars": {p: pillars[p] for p in compared} if not diffs else other}


# ---------- 메인 ----------
def calculate_chart(
    *, year: int, month: int, day: int, gender: str, hour: int | None = None, minute: int = 0, second: int = 0,
    calendar: str = "solar", is_leap_month: bool = False, place: str = "서울특별시",
    latitude: float | None = None, longitude: float | None = None, timezone_name: str = "Asia/Seoul",
    time_profile: TimeProfile = TimeProfile.CIVIL_TIME, zi_profile: ZiProfile = ZiProfile.ZI_2300_DAY_CHANGE,
    dst_policy: str = "wall_clock", daeun_profile: DaeunProfile = DaeunProfile(),
) -> ChartCalculationResult:
    if gender not in ("male", "female"):
        raise ValueError("gender 는 male/female")
    warnings: list[str] = []
    lunar_info = None
    if calendar == "lunar":
        solar, w = lunar_mod.lunar_to_solar(year, month, day, is_leap_month)
        warnings += w
        lunar_info = {"input": {"year": year, "month": month, "day": day, "is_leap": is_leap_month},
                      "solar_date": solar.isoformat(), "library": lunar_mod.LIBRARY}
    else:
        solar = date(year, month, day)  # 잘못된 날짜는 ValueError
    hour_known = hour is not None
    if not hour_known:
        warnings.append("hour_unknown: 시주 미확정. 연·월·일주만 산출하며 일주도 경계 시각에선 달라질 수 있음")
    naive = datetime(solar.year, solar.month, solar.day, hour if hour_known else 12, minute, second)

    if latitude is None or longitude is None:
        if place not in PLACES:
            raise ValueError(f"알 수 없는 출생지 '{place}': latitude/longitude 를 직접 입력하세요")
        latitude, longitude = PLACES[place]
        coord_source = f"table:{place}(도시 중심 근사)"
    else:
        coord_source = "user"
    tz = ZoneInfo(timezone_name)
    instants = _resolve_instants(naive, tz)
    if len(instants) > 1:
        warnings.append("ambiguous_local_time: 서머타임 종료로 같은 벽시계 시각이 두 번 있음 → fold 별 변형 반환")

    def build(fold_aw_utc, tp: TimeProfile, zi: ZiProfile):
        fold, aw, utc = fold_aw_utc
        pt, tinfo = _pillar_time(tp, aw, utc, longitude, dst_policy)
        ypil, mpil, bounds = year_month_pillars(utc)
        dpil, hpil = day_hour_pillars(pt, zi, hour_known)
        pillars = {"year": ypil, "month": mpil, "day": dpil}
        if hpil:
            pillars["hour"] = hpil
        return pillars, pt, tinfo, bounds

    tz_unresolved = tz.key == "Asia/Seoul" and datetime(1954, 3, 20, 23, 30) <= naive <= datetime(1954, 3, 21, 0, 30)  # 연혁 상수(예시 아님: 표준시 전환 구간, 출생정보 아님)
    if tz_unresolved:
        warnings.append("tz_transition_unresolved: 1954-03-21 한국 표준시 전환(연혁 사실 예시, +9→+8:30) 시각이 2차 자료(00:30)와 tzdata(00:00)에서 30분 다르고 법령 원문은 미확인 — 이 구간 출생은 시각 보정이 확정되지 않음")
    primary_inst = instants[0]
    pillars, pt, tinfo, bounds = build(primary_inst, time_profile, zi_profile)
    fold, aw, utc = primary_inst

    # 변형: 시간 보정 3종 × 23시 규칙 3종 × (서머타임 fold)
    groups: dict[tuple, list] = {}
    for inst in instants:
        for tp in TimeProfile:
            for zi in ZiProfile:
                p, *_ = build(inst, tp, zi)
                groups.setdefault(tuple(p.items()), []).append(
                    {"time_profile": tp.value, "zi_profile": zi.value, "dst_fold": inst[0]})
    variants = []
    for i, (key, produced) in enumerate(groups.items()):
        is_primary = any(x["time_profile"] == time_profile.value and x["zi_profile"] == zi_profile.value and x["dst_fold"] == fold
                         for x in produced)
        variants.append({"variant_id": f"v{i + 1}", "pillars": dict(key), "is_primary": is_primary, "produced_by": produced})
    variants.sort(key=lambda v: not v["is_primary"])
    for i, v in enumerate(variants):
        v["variant_id"] = f"v{i + 1}"
    if len(variants) > 1:
        warnings.append(f"chart_variants: 프로필에 따라 명식이 {len(variants)}종으로 갈림 (확정 금지, variants 참조)")

    # 절입 모호성: 절입 순간 ±폭 이내면 연·월주를 확정하지 않고 양쪽 명식을 변형으로 반환
    nearest_s = min(abs((utc - t).total_seconds()) for t, _ in _jie_events(utc))
    amb_s = AMBIGUITY_SECONDS_MODERN if utc.year >= 1970 else AMBIGUITY_SECONDS_EARLY
    ambiguous = nearest_s <= amb_s
    if ambiguous:
        seen = {tuple(v["pillars"].items()) for v in variants}
        for sign in (-1, 1):
            yp, mp, _ = year_month_pillars(utc + timedelta(seconds=sign * (amb_s + 1)))
            alt = dict(pillars, year=yp, month=mp)
            if tuple(alt.items()) not in seen:
                seen.add(tuple(alt.items()))
                variants.append({"variant_id": "", "pillars": alt, "is_primary": False,
                                 "produced_by": [{"boundary_shift_seconds": sign * (amb_s + 1)}]})
        for i, v in enumerate(variants):
            v["variant_id"] = f"v{i + 1}"
        warnings.append(f"solar_term_ambiguous: 절입 {nearest_s:.0f}초 거리(판정 폭 ±{amb_s}초) → 연·월주 확정 금지")

    # 대운
    if hour_known:
        daeun = compute_daeun(utc, aw.replace(tzinfo=None), pillars["year"], pillars["month"], gender, daeun_profile)
    else:
        # 출생시각 미상: 대운 시점 민감도 범위 (현지 하루의 양 끝)
        local_day0 = naive.replace(hour=0, minute=0).replace(tzinfo=tz).astimezone(timezone.utc)
        local_day1 = local_day0 + timedelta(hours=23, minutes=59)
        ends = [compute_daeun(u, naive.replace(hour=h, minute=m), pillars["year"], pillars["month"], gender, daeun_profile, 1)
                for u, h, m in ((local_day0, 0, 0), (local_day1, 23, 59))]
        daeun = compute_daeun(utc, naive, pillars["year"], pillars["month"], gender, daeun_profile)
        daeun["nominal_time_used"] = "12:00"
        daeun["sensitivity_start_age"] = [e["start_age"] for e in ends]
        warnings.append("daeun_time_sensitivity: 출생시간 미상 → 대운 기산이 시각에 따라 달라짐")

    # 검산·게이트
    cc = _crosscheck(utc, pt, zi_profile, pillars)
    term_min = min(abs((utc - t).total_seconds()) for t, _ in _jie_events(utc)) / 60
    gate = classify_verification(
        pillars_given=pillars,
        verifications=[{"tool": "astro-core/skyfield", "version": CALC_VERSION,
                        "pillars": {p: pillars[p] for p in cc["compared"]}},
                       {"tool": cc["tool"], "version": cc["version"], "pillars": cc["pillars"]}],
        birth_time=pt.time() if hour_known else None, hour_known=hour_known, calendar=calendar,
        is_leap_month=is_leap_month if calendar == "lunar" else False, term_distance_minutes=int(term_min),
    )
    status, reasons = gate["status"], list(gate["reasons"])
    if ambiguous:
        status, reasons = "V3", reasons + ["solar_term_ambiguous"]
    if tz_unresolved:
        status, reasons = "V3", reasons + ["tz_transition_unresolved"]
    if any("lunar_calendar_kr_cn_mismatch" in w for w in warnings):
        if vlevels.official_lunar_state(year)["state"] == "OFFICIAL_MONTHS_VERIFIED":
            reasons = reasons + ["lunar_kr_cn_differ_kr_official_confirmed"]  # 한국 기준을 KASI 월력요항과 대조해 확인한 해: V3 로 내리지 않고 사유만 표시
        else:
            status, reasons = "V3", reasons + ["lunar_kr_cn_mismatch"]
    v1_ok, v1_blockers = vlevels.v1_allowed()
    if status == "V1" and calendar == "lunar" and vlevels.official_lunar_state(year)["state"] != "OFFICIAL_MONTHS_VERIFIED":
        status, reasons = "V2", reasons + ["lunar_conversion_unverified"]
    if status == "V1" and not v1_ok:
        status, reasons = "V2", reasons + ["golden_suite_incomplete"]
    if len(variants) > 1 and status == "V1":
        status, reasons = "V3", reasons + ["chart_variants"]
    _scope = vlevels.scope_status(calendar, year if calendar == "lunar" else None)
    verification = {"status": status, "reasons": reasons, "may_claim_verified": status == "V1" and GOLDEN_SUITE_COMPLETE,
                    "independent_crosscheck": cc, "golden_suite_complete": GOLDEN_SUITE_COMPLETE,
                    "nearest_jie_minutes": term_min, "ambiguity": {"ambiguous": ambiguous, "nearest_jie_seconds": nearest_s,
                                                                    "window_seconds": amb_s},
                    "levels": {k: v["granted"] for k, v in vlevels.levels().items()}, "v1_blockers": v1_blockers,
                    "scope": _scope, "unverified_notice": vlevels.unverified_notice(_scope)}

    tinfo = dict(tinfo, pillar_time_local=pt.isoformat())
    profile_id = f"{CALC_VERSION}/{time_profile.value}/{zi_profile.value}/dst:{dst_policy}/{daeun_profile.profile_id}"
    return ChartCalculationResult(
        input={"calendar": calendar, "year": year, "month": month, "day": day, "hour": hour, "minute": minute,
               "is_leap_month": is_leap_month, "gender": gender, "place": place},
        normalized={"local_civil": aw.replace(tzinfo=None).isoformat(), "utc": utc.isoformat(),
                    "utc_offset_minutes": aw.utcoffset().total_seconds() / 60,
                    "dst_active": bool(aw.dst()), "dst_fold": fold, "solar_date": solar.isoformat()},
        timezone=timezone_name, coordinates={"latitude": latitude, "longitude": longitude, "source": coord_source},
        solar_term_boundaries=bounds, time_profile=tinfo, zi_profile=zi_profile.value, pillars=pillars, daeun=daeun,
        variants=variants, verification=verification,
        libraries={**eph.library_versions(), "solar_term_source": eph.SOLAR_TERM_SOURCE, "lunar": lunar_mod.LIBRARY,
                   "tzdata": "IANA via python zoneinfo", "calc": CALC_VERSION},
        lunar_conversion=lunar_info, calendar_range="1901-01-01..2050-12-31 (DE421)",
        calculation_profile_id=profile_id, warnings=warnings,
    )
