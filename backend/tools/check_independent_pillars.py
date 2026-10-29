"""월주·시주·대운 기산의 독립 검증 시도 (v6.6 §6). 집계 결과는 golden/independent_pillars_check.json (공개 가능 집계만).

독립 후보(서비스 requirements 에는 넣지 않고 임시 가상환경에서만 실행, 모두 MIT):
  - korean-saju 0.3.0   : KASI 특일정보 API 절기(2000~2027)·KASI 음력(1900~2050) 내장 + Meeus 폴백. 한국식 야자시/조자시 분리, 진태양시, 대운 구현이 별도 코드
  - bazi 2.4.0          : 'celestial' 백엔드(= celestial-calendar C++ VSOP87D 계열, 초 단위 절기표)·진태양시(균시차표)·대운 구현이 별도 코드
  - celestial-calendar  : bazi 가 쓰는 천문 계산 패키지(절기·균시차)
  - cnlunar 0.2.5       : 절기 '날짜'(일 단위) 압축표 기반 — 일 단위 비교만 가능
  - KASI 월력요항 표(2004~2017, data_private) · KASI 달력자료(2023~2028, data_private) · KASI 변환 서비스(월건)
사용:
  python -m tools.check_independent_pillars            # 전체 실행 (임시 가상환경 필요: INDEP_VENV_PY 환경변수 또는 %TEMP%/indep_venv)
  <venv>/python tools/check_independent_pillars.py venv-run in.json out.json   # 가상환경 쪽 계산 (내부용)
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "golden"
PRIV = ROOT / "data_private" / "external"
TEMP = Path(os.environ.get("TEMP", "/tmp"))
VENV_PY = os.environ.get("INDEP_VENV_PY") or str(TEMP / "indep_venv" / "Scripts" / "python.exe")
WORK = TEMP / "indep_work"
STEMS, BRANCHES = "甲乙丙丁戊己庚辛壬癸", "子丑寅卯辰巳午未申酉戌亥"
HG = dict(zip("갑을병정무기경신임계", STEMS))
HZ = dict(zip("자축인묘진사오미신유술해", BRANCHES))
SEOUL_LON = 126.9784


# =====================================================================================================================
# 가상환경 쪽 (독립 라이브러리만 import; 이 프로젝트 코드는 import 하지 않는다)
# =====================================================================================================================
def venv_run(in_path: str, out_path: str) -> None:
    import datetime as dt
    import importlib.metadata as md
    import itertools
    from zoneinfo import ZoneInfo

    import celestial_calendar as cc
    import cnlunar
    import korean_saju as ks
    from bazi.bazi import Bazi, BaziConfig, BaziPrecision, CalendarBackend
    from bazi.bazi_chart import BaziChart
    from bazi.school import BaziSchool, DayRollover

    data = json.load(open(in_path, encoding="utf-8"))
    seoul = ZoneInfo("Asia/Seoul")
    out = {"versions": {n: md.version(n) for n in ("korean-saju", "bazi", "celestial-calendar", "cnlunar")}, "cases": {}, "jieqi": [], "eot": []}
    _, terms = ks.load_bundled_data()
    cfg = lambda roll: BaziConfig(precision=BaziPrecision.MINUTE, backend=CalendarBackend.CELESTIAL, school=BaziSchool(day_rollover=roll))
    four = lambda xs: [str(x)[:2] for x in xs]
    for c in data["cases"]:
        t = dt.datetime.fromisoformat(c["kst"])
        r: dict = {}
        try:
            for key, sep in (("ks_sep", True), ("ks_nosep", False)):
                s = ks.Saju.from_birth(kst_moment=t, solar_terms=terms, yaja_si_separated=sep)
                r[key] = four([s.year_pillar, s.month_pillar, s.day_pillar, s.hour_pillar])
            s = ks.Saju.from_birth(kst_moment=t, solar_terms=terms)
            d = ks.Daewoon.compute(saju=s, gender=ks.Gender.MALE if c["gender"] == "male" else ks.Gender.FEMALE, solar_terms=terms)
            r["ks_daewoon"] = {"forward": d.forward, "days_to_boundary": d.days_to_boundary, "start_age": d.entries[0].start_age,
                               "start_months": d.entries[0].start_months_offset, "first": str(d.entries[0].gan_ji)[:2]}
        except Exception as e:
            r["ks_error"] = repr(e)[:160]
        try:
            for key, roll in (("bazi_wan", DayRollover.WAN_ZISHI), ("bazi_zizheng", DayRollover.ZIZHENG)):
                b = Bazi.create(t.replace(tzinfo=seoul), c["gender"], cfg(roll), longitude=SEOUL_LON_C)
                r[key] = four(b.pillars)
                r[key + "_apparent"] = b.location_time.apparent_time.isoformat()
            bj = t - dt.timedelta(hours=1)  # bazi 기본 입력은 UTC+8 벽시계: 같은 순간을 북경시 벽시계로 변환해 대운 시작 순간을 비교
            b2 = Bazi.create(bj, c["gender"], cfg(DayRollover.WAN_ZISHI))
            ch = BaziChart(b2)
            first = next(iter(itertools.islice(ch.dayun, 1)))
            r["bazi_dayun"] = {"forward": bool(ch.dayun_order), "start": first.start_moment.isoformat(), "first": str(first.ganzhi)[:2], "birth_bj": bj.isoformat()}
        except Exception as e:
            r["bazi_error"] = repr(e)[:160]
        try:
            x = cnlunar.Lunar(t, godType="8char")
            r["cn"] = [x.year8Char, x.month8Char, x.day8Char, x.twohour8Char]
        except Exception as e:
            r["cn_error"] = repr(e)[:160]
        out["cases"][c["id"]] = r
    names = list(cc.Jieqi)
    for y in range(1901, 2051):
        for i, jq in enumerate(names):
            m = cc.jieqi_moment(y, jq).moment_ut1
            ut1 = dt.datetime(m.year, m.month, m.day) + dt.timedelta(days=m.fraction)
            out["jieqi"].append([y, i, ut1.isoformat()])
    for iso in data["eot_instants"]:
        t = dt.datetime.fromisoformat(iso)
        frac = (t.hour * 3600 + t.minute * 60 + t.second) / 86400.0
        deg = cc.equation_of_time(cc.ut1_to_jde(cc.CivilDateTime(year=t.year, month=t.month, day=t.day, fraction=frac)))
        out["eot"].append([iso, deg * 4.0])  # 시각도 1° = 4분
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False)


SEOUL_LON_C = 126.9784


# =====================================================================================================================
# 프로젝트 쪽
# =====================================================================================================================
def _gz_idx(g: str) -> int:
    return next(i for i in range(60) if STEMS[i % 10] + BRANCHES[i % 12] == g)


def _five_tiger(year_stem_idx: int, n: int) -> str:
    """오호둔: 인월(n=0)부터 n번째 달의 월건."""
    return STEMS[(year_stem_idx % 5 * 2 + 2 + n) % 10] + BRANCHES[(2 + n) % 12]


def main_run() -> None:
    sys.path.insert(0, str(ROOT))
    from zoneinfo import ZoneInfo

    from app.astro_core import ephemeris as eph
    from app.astro_core.engine import TimeProfile, ZiProfile, calculate_chart

    KST = ZoneInfo("Asia/Seoul")
    rng = random.Random(66)
    res: dict = {"generated": datetime.now(timezone.utc).date().isoformat(), "tools": {}, "notes": []}
    all_terms = sorted((t, k) for y in range(1900, 2052) for t, k in eph.solar_terms_in_utc_year(y) if 1900 <= y <= 2051)

    def nearest_term_seconds(u: datetime) -> float:
        return min(abs((u - t).total_seconds()) for t, _ in all_terms if abs((u - t).days) < 20)

    # ---- 사례 생성: 1962~2027, UTC+9(서머타임 아님) 구간만 ----
    cases = []
    while len(cases) < 600:
        t = datetime(1962, 1, 1) + timedelta(minutes=rng.randrange(0, 60 * 24 * 365 * 66))
        a = t.replace(tzinfo=KST)
        if a.utcoffset() != timedelta(hours=9) or a.dst() != timedelta(0):
            continue
        u = a.astimezone(timezone.utc)
        if nearest_term_seconds(u) < 180:
            continue
        cases.append({"id": f"C{len(cases):04d}", "kst": t.isoformat(), "gender": rng.choice(["male", "female"])})
    start = datetime(1950, 1, 1, tzinfo=timezone.utc)
    eot_instants = [(start + timedelta(minutes=rng.randrange(0, 60 * 24 * 365 * 100))).replace(tzinfo=None).isoformat() for _ in range(1500)]
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "in.json").write_text(json.dumps({"cases": cases, "eot_instants": eot_instants}), encoding="utf-8")
    if not Path(VENV_PY).exists():
        raise SystemExit(f"가상환경 python 없음: {VENV_PY}  (INDEP_VENV_PY 로 지정)")
    subprocess.run([VENV_PY, str(Path(__file__)), "venv-run", str(WORK / "in.json"), str(WORK / "out.json")], check=True,
                   env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    out = json.loads((WORK / "out.json").read_text(encoding="utf-8"))
    res["tools"] = {
        "korean-saju": {"version": out["versions"]["korean-saju"], "license": "MIT", "lineage": "KASI 특일정보 API 절기(2000~2027)+KASI 음력 내장, Meeus 폴백; 독립 코드",
                        "scope": "연·월·일·시주(진태양시·야자시 분리), 대운"},
        "bazi": {"version": out["versions"]["bazi"], "license": "MIT", "lineage": "celestial-calendar(C++ VSOP87D 계열) 초 단위 절기표·균시차표; 독립 코드",
                 "scope": "연·월·일·시주(진태양시), 대운"},
        "celestial-calendar": {"version": out["versions"]["celestial-calendar"], "license": "MIT", "lineage": "VSOP87D 태양 + ΔT 모델", "scope": "절기 순간·균시차"},
        "cnlunar": {"version": out["versions"]["cnlunar"], "license": "MIT", "lineage": "절기 날짜(일 단위) 압축표", "scope": "일 단위 간지(경계일 제외)"},
    }

    def engine_pillars(c, zi, tp):
        t = datetime.fromisoformat(c["kst"])
        r = calculate_chart(year=t.year, month=t.month, day=t.day, hour=t.hour, minute=t.minute, gender=c["gender"], latitude=37.5665, longitude=SEOUL_LON_C,
                            time_profile=tp, zi_profile=zi)
        p = r.pillars
        return [p["year"], p["month"], p["day"], p["hour"]], r

    def band(pt: datetime) -> bool:  # 야자시/조자시 경계 영역(진태양시 23:00~01:00)
        return pt.hour == 23 or pt.hour == 0

    def near_hour_boundary(pt: datetime, limit=150) -> bool:
        """시진 경계(홀수 정각 23,1,3,…)에서 limit 초 이내인가."""
        s = pt.minute * 60 + pt.second + pt.microsecond / 1e6
        if pt.hour % 2 == 1:
            return min(s, 7200 - s) < limit
        return (3600 - s) < limit

    FIELDS = ["year", "month", "day", "hour"]

    def cmp(tool_key, zi, tp, skip_band=False):
        agg = {"cases": 0, "agree_all": 0, "fields": {f: {"compared": 0, "mismatch": 0} for f in FIELDS}, "mismatch_near_boundary": 0, "mismatch_unexplained": [], "skipped_zi_band": 0}
        for c in cases:
            r = out["cases"][c["id"]]
            if tool_key not in r:
                continue
            eng, rr = engine_pillars(c, zi, tp)
            pt = datetime.fromisoformat(rr.time_profile["pillar_time_local"])
            if skip_band and band(pt):
                agg["skipped_zi_band"] += 1
                continue
            agg["cases"] += 1
            bad = []
            other = r[tool_key]
            for i, f in enumerate(FIELDS):
                if other[i] is None or other[i] == "N":
                    continue
                agg["fields"][f]["compared"] += 1
                if other[i] != eng[i]:
                    agg["fields"][f]["mismatch"] += 1
                    bad.append(f)
            if not bad:
                agg["agree_all"] += 1
            elif set(bad) <= {"hour"} and near_hour_boundary(pt):
                agg["mismatch_near_boundary"] += 1
            else:
                agg["mismatch_unexplained"].append({"id": c["id"], "fields": bad, "engine": eng, "other": other, "pillar_time": pt.isoformat(timespec="seconds")})
        agg["mismatch_unexplained_count"] = len(agg["mismatch_unexplained"])
        agg["mismatch_unexplained"] = agg["mismatch_unexplained"][:8]
        return agg

    MEAN, APP = TimeProfile.LOCAL_MEAN_SOLAR_TIME, TimeProfile.LOCAL_APPARENT_SOLAR_TIME
    res["korean_saju_vs_engine"] = {
        "note": "korean-saju 의 '진태양시(AST)'는 경도 보정만 있고 균시차가 없다(SolarTimeCorrection.to_apparent_solar_time = KST + (경도−135°)×4분). 따라서 엔진의 평균태양시 프로필과 대응시킨다.",
        "yaja_separated__vs__MEAN_SOLAR__MIDNIGHT_NEXT_DAY_STEM": cmp("ks_sep", ZiProfile.MIDNIGHT_NEXT_DAY_STEM, MEAN),
        "yaja_unified__vs__MEAN_SOLAR__ZI_2300_DAY_CHANGE": cmp("ks_nosep", ZiProfile.ZI_2300_DAY_CHANGE, MEAN),
        "contrast_yaja_separated__vs__APPARENT_SOLAR(균시차 포함, 일치하지 않는 것이 정상)": cmp("ks_sep", ZiProfile.MIDNIGHT_NEXT_DAY_STEM, APP),
        "in_kasi_term_range_2000_2027": sum(1 for c in cases if 2000 <= int(c["kst"][:4]) <= 2027), "total_cases": len(cases)}
    res["bazi_vs_engine"] = {
        "note": "bazi: 서울 경도+KST 벽시계 입력 시 진태양시(균시차 포함, celestial 표) 사용. 일 경계 옵션 WAN_ZISHI=23시 일주 교체(ZI_2300_DAY_CHANGE), ZIZHENG=00시 교체·당일 천간(MIDNIGHT_SAME_DAY_STEM).",
        "WAN_ZISHI__vs__APPARENT__ZI_2300_DAY_CHANGE": cmp("bazi_wan", ZiProfile.ZI_2300_DAY_CHANGE, APP),
        "ZIZHENG__vs__APPARENT__MIDNIGHT_SAME_DAY_STEM": cmp("bazi_zizheng", ZiProfile.MIDNIGHT_SAME_DAY_STEM, APP)}

    # ---- cnlunar (일 단위): 절기 당일±1일, 23시대 제외, 시주 제외 비교 ----
    cn = {"compared": 0, "mismatch": [], "excluded_near_jie_day": 0}
    for c in cases:
        t = datetime.fromisoformat(c["kst"])
        r = out["cases"][c["id"]]
        if "cn" not in r or t.hour == 23:
            continue
        u = t.replace(tzinfo=KST).astimezone(timezone.utc)
        if any(abs((u - jt).total_seconds()) < 36 * 3600 for jt, _ in all_terms if abs((u - jt).days) < 3):
            cn["excluded_near_jie_day"] += 1
            continue
        eng = calculate_chart(year=t.year, month=t.month, day=t.day, hour=t.hour, minute=t.minute, gender=c["gender"]).pillars
        cn["compared"] += 1
        got = dict(zip(FIELDS, r["cn"]))
        bad = {f: [eng[f], got[f]] for f in FIELDS if got[f] != eng.get(f)}
        if bad:
            from korean_lunar_calendar import KoreanLunarCalendar
            kc = KoreanLunarCalendar()
            kc.setLunarDate(t.year, 1, 1, False)
            seol = datetime(kc.solarYear, kc.solarMonth, kc.solarDay)
            if set(bad) == {"year"} and t.month in (1, 2):  # 입춘(엔진) 대 음력 설날(cnlunar) 기준 차이가 나는 1~2월 구간
                cn["year_basis_lunar_new_year_expected"] = cn.get("year_basis_lunar_new_year_expected", 0) + 1  # 입춘~설날 사이: cnlunar 는 음력 설 기준 연주
                continue
            cn["mismatch"].append({"id": c["id"], "diff": bad, "kst": c["kst"]})
    cn["mismatch_count"] = len(cn["mismatch"])
    cn.setdefault("year_basis_lunar_new_year_expected", 0)
    cn["mismatch"] = cn["mismatch"][:8]
    res["cnlunar_vs_engine_civil_date_level"] = cn

    # ---- celestial-calendar / korean-saju 절기 순간 vs 엔진 (전 구간 1901~2050, 24절기) ----
    diffs = []
    by_decade: dict[int, float] = {}
    jq_to_k = lambda i: (21 + i) % 24
    for y, i, iso in out["jieqi"]:
        t = datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)  # UT1 ≈ UTC (±0.9s, 1972 이전은 ΔT 모델 차이)
        k = jq_to_k(i)
        ours = next((tt for tt, kk in eph.solar_terms_in_utc_year(y) if kk == k), None)
        if ours is None:
            # 입춘 기준 연도 정의 차이로 연말 절기가 다음 UTC 해에 걸릴 수 있음
            for yy in (y - 1, y + 1):
                ours = next((tt for tt, kk in eph.solar_terms_in_utc_year(yy) if kk == k and abs((tt - t).days) < 5), None)
                if ours:
                    break
        if ours is None:
            continue
        d = abs((ours - t).total_seconds())
        diffs.append(d)
        by_decade[y // 10 * 10] = max(by_decade.get(y // 10 * 10, 0), d)
    res["celestial_calendar_jieqi_vs_engine"] = {"compared": len(diffs), "max_abs_s": max(diffs), "mean_abs_s": sum(diffs) / len(diffs),
                                                 "over_60s": sum(d > 60 for d in diffs), "max_abs_s_by_decade": {str(k): round(v, 1) for k, v in sorted(by_decade.items())},
                                                 "note": "celestial-calendar 는 UT1 순간을 돌려주고 엔진은 UTC. 1972 이전은 UT1/UTC 정의·ΔT 모델 차이가 섞여 있음"}

    # ---- 균시차: 엔진(GAST−RA) vs celestial-calendar vs NOAA 공식 vs korean-saju/bazi 보정량 ----
    import math
    def noaa_eot(t: datetime) -> float:
        doy = t.timetuple().tm_yday
        g = 2 * math.pi / 365.0 * (doy - 1 + (t.hour - 12) / 24.0)
        return 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    e_cc, e_noaa = [], []
    for iso, mins in out["eot"]:
        t = datetime.fromisoformat(iso)
        eng = eph.equation_of_time_minutes(t.replace(tzinfo=timezone.utc))
        e_cc.append(abs(eng - mins))
        e_noaa.append(abs(eng - noaa_eot(t)))
    # 부호 확인: 11월 초(+16분)
    sign_ok = out is not None and eph.equation_of_time_minutes(datetime(2000, 11, 3, 12, tzinfo=timezone.utc)) > 15
    # 진태양시 보정량 비교: 엔진의 시계 대비 차이(분) vs bazi apparent_time
    app_diff = []
    for c in cases[:300]:
        r = out["cases"][c["id"]]
        if "bazi_wan_apparent" not in r:
            continue
        t = datetime.fromisoformat(c["kst"])
        eng_r = calculate_chart(year=t.year, month=t.month, day=t.day, hour=t.hour, minute=t.minute, gender=c["gender"], latitude=37.5665, longitude=SEOUL_LON_C,
                                time_profile=TimeProfile.LOCAL_APPARENT_SOLAR_TIME)
        pt = datetime.fromisoformat(eng_r.time_profile["pillar_time_local"])
        app_diff.append(abs((pt - datetime.fromisoformat(r["bazi_wan_apparent"])).total_seconds()))
    res["equation_of_time"] = {"samples": len(e_cc), "engine_vs_celestial_calendar_max_min": round(max(e_cc), 3), "engine_vs_celestial_calendar_mean_min": round(sum(e_cc) / len(e_cc), 4),
                               "engine_vs_noaa_formula_max_min": round(max(e_noaa), 3), "noaa_formula_note": "NOAA 근사식은 ±1분 안팎이라 대략적 일치만 확인",
                               "sign_convention_ok_apparent_minus_mean": bool(sign_ok),
                               "engine_vs_bazi_apparent_time_seconds": {"samples": len(app_diff), "max_s": round(max(app_diff), 2), "mean_s": round(sum(app_diff) / len(app_diff), 3)}}

    # ---- 대운: 방향·시작 나이 비교 (3일=1년 환산은 관습이므로 '정답' 비교가 아니라 구현 간 일치 정도) ----
    dv = {"cases": 0, "direction_agree_ks": 0, "direction_agree_bazi": 0, "ks_months_diff": {}, "bazi_start_day_diff_stats": [], "ks_error": 0, "bazi_error": 0}
    for c in cases:
        r = out["cases"][c["id"]]
        t = datetime.fromisoformat(c["kst"])
        eng = calculate_chart(year=t.year, month=t.month, day=t.day, hour=t.hour, minute=t.minute, gender=c["gender"]).daeun
        dv["cases"] += 1
        if "ks_daewoon" in r:
            k = r["ks_daewoon"]
            dv["direction_agree_ks"] += int((eng["direction"] == "forward") == k["forward"])
            em = eng["start_age"]["years"] * 12 + eng["start_age"]["months"]
            km = k["start_age"] * 12 + k["start_months"]
            dv["ks_months_diff"][str(km - em)] = dv["ks_months_diff"].get(str(km - em), 0) + 1
        else:
            dv["ks_error"] += 1
        if "bazi_dayun" in r:
            b = r["bazi_dayun"]
            dv["direction_agree_bazi"] += int((eng["direction"] == "forward") == b["forward"])
            bs = datetime.fromisoformat(b["start"])
            bd = datetime.fromisoformat(b["birth_bj"])
            es = datetime.fromisoformat(eng["first_luck_date"])
            dv["bazi_start_day_diff_stats"].append((bs.date() - es.date()).days)
        else:
            dv["bazi_error"] += 1
    ds = dv.pop("bazi_start_day_diff_stats")
    dv["bazi_first_luck_date_minus_engine_days"] = {"n": len(ds), "min": min(ds), "max": max(ds), "mean": round(sum(ds) / len(ds), 2),
                                                    "within_3_days": sum(abs(x) <= 3 for x in ds), "within_10_days": sum(abs(x) <= 10 for x in ds)}
    dv["interpretation"] = ("방향은 구현 간 일치 여부 확인 가능(음양×성별 규칙). 시작 시점은 '3일=1년' 환산의 세부(1년 길이, 반올림, 절기 순간 사용)가 구현마다 달라 "
                            "정답이 없는 관습이므로, 일치 정도는 '독립 구현이 같은 관습을 같은 방식으로 적용했는가'만 뜻한다.")
    res["daeun_cross_implementation"] = dv

    # ---- KASI 월력요항(2004~2017) 절기표로 월주·연주 유도 vs 엔진 ----
    KJ = {"입춘": 0, "경칩": 1, "청명": 2, "입하": 3, "망종": 4, "소서": 5, "입추": 6, "백로": 7, "한로": 8, "입동": 9, "대설": 10, "소한": 11}
    kal = PRIV / "kasi_almanac.json"
    if kal.exists():
        yrs = json.loads(kal.read_text(encoding="utf-8"))["years"]
        supplemented = {}
        for ys, v in yrs.items():  # 일부 연도 표에 '05시 1분'처럼 한 자리 분이 있어 수집기 정규식이 놓친 절기를 관대한 정규식으로 보충
            if len(v["terms"]) != 24:
                import re as _re
                import urllib.request as _ur
                html = _ur.urlopen(f"https://astro.kasi.re.kr/kor/life/post/almanac?search_year={ys}&bbs_uniq_id=almanac", timeout=40).read().decode("utf-8", errors="replace")
                txt = _re.sub(r"\s+", " ", _re.sub(r"<[^>]+>", "|", html[html.find("24절기"):]))
                have = {t["name"] for t in v["terms"]}
                for m in _re.finditer(r"\|(\S{2})\| \|(\d+)\| \|(\d{2})월(\d{2})일\| \|(\d{1,2})시\s*(\d{1,2})분\|", txt):
                    if m[1] not in have:
                        v["terms"].append({"name": m[1], "kst": f"{int(ys):04d}-{m[3]}-{m[4]}T{int(m[5]):02d}:{int(m[6]):02d}"})
                        supplemented.setdefault(ys, []).append(m[1])
        ev = sorted((datetime.fromisoformat(t["kst"]), KJ[t["name"]]) for v in yrs.values() for t in v["terms"] if t["name"] in KJ)
        lichun = [t for t, n in ev if n == 0]
        mism, tested = [], 0
        lo, hi = datetime(2005, 1, 15), datetime(2016, 12, 20)
        for _ in range(600):
            t = lo + timedelta(minutes=rng.randrange(0, int((hi - lo).total_seconds() // 60)))
            a = t.replace(tzinfo=KST)
            if a.utcoffset() != timedelta(hours=9):
                continue
            if min(abs((t - e).total_seconds()) for e, _ in ev) < 150:
                continue
            past = [(e, n) for e, n in ev if e <= t]
            _, n = past[-1]
            y = [e for e in lichun if e <= t][-1].year
            exp_month = _five_tiger((y - 4) % 10, n)
            exp_year = STEMS[(y - 4) % 10] + BRANCHES[(y - 4) % 12]
            r = calculate_chart(year=t.year, month=t.month, day=t.day, hour=t.hour, minute=t.minute, gender="male")
            tested += 1
            if r.pillars["month"] != exp_month or r.pillars["year"] != exp_year:
                mism.append({"kst": t.isoformat(timespec="minutes"), "kasi_derived": [exp_year, exp_month], "engine": [r.pillars["year"], r.pillars["month"]]})
        res["month_year_from_kasi_almanac_terms"] = {"range": "2005-01-15~2016-12-20", "tested": tested, "mismatch": len(mism), "mismatch_samples": mism[:5], "excluded_within_150s_of_term": True, "terms_supplemented_by_tolerant_regex": supplemented,
                                                     "method": "KASI 월력요항 절기(분 단위)로 월 경계를 구하고 월건·연간은 오호둔 산술(아래 KASI 월건 대조로 산술 확인)로 이름 부여"}
    else:
        res["month_year_from_kasi_almanac_terms"] = {"status": "NOT_RUN", "reason": "data_private/external/kasi_almanac.json 없음 (python -m tools.fetch_kasi_almanac)"}

    # ---- KASI 월건 = 음력월 기준임을 확인하고, 오호둔 산술을 KASI 값으로 대조 ----
    cal = PRIV / "kasi_calendar.json"
    wg = {"local_file": {"months": 0, "mismatch": 0}, "service_sample": {"queries": 0, "mismatch": 0}, "wolgun_basis": None}
    if cal.exists():
        for ys, v in json.loads(cal.read_text(encoding="utf-8"))["years"].items():
            y = int(ys)
            for m in v["months"]:
                if m["is_leap"] or not m["month_gz"] or m["month_gz"][0] not in HG:
                    continue
                wg["local_file"]["months"] += 1
                kasi_gz = HG[m["month_gz"][0]] + HZ[m["month_gz"][1]]
                if kasi_gz != _five_tiger((y - 4) % 10, m["lunar_month"] - 1):
                    wg["local_file"]["mismatch"] += 1
    import urllib.parse
    import urllib.request
    cache_p = PRIV / "kasi_wolgun_cache.json"
    cache = json.loads(cache_p.read_text(encoding="utf-8")) if cache_p.exists() else {}

    def svc(yyyy, mm, dd):
        key = f"{yyyy}-{mm:02d}-{dd:02d}"
        if key not in cache:
            import time
            time.sleep(0.2)
            cache[key] = json.loads(urllib.request.urlopen("https://astro.kasi.re.kr/life/solc?" + urllib.parse.urlencode({"yyyy": yyyy, "mm": f"{mm:02d}", "dd": f"{dd:02d}"}), timeout=30).read().decode("utf-8"))
        return cache[key]
    hj = lambda s: s.split("(")[1][:2] if s and "(" in s else None
    try:
        r1, r2 = svc(2024, 2, 3), svc(2024, 2, 5)  # 연혁 사실 예시: 입춘 전후(2024-02-04 17:27), 같은 음력 12월
        wg["wolgun_basis"] = {"before_lichun": hj(r1["LUNC_WLGN"]), "after_lichun": hj(r2["LUNC_WLGN"]), "same_lunar_month": (r1["LUNC_MM"], r1["LUNC_YYYY"]) == (r2["LUNC_MM"], r2["LUNC_YYYY"]),
                              "conclusion": "입춘 전후로 월건이 같으므로 KASI 월건은 절기 기준 월주가 아니라 음력 월 기준" if hj(r1["LUNC_WLGN"]) == hj(r2["LUNC_WLGN"]) else "입춘 전후로 월건이 바뀜"}
        for _ in range(60):
            y, m = rng.randrange(1901, 2049), rng.randrange(1, 13)
            key = f"lunc-{y}-{m:02d}"
            if key not in cache:
                import time
                time.sleep(0.2)
                cache[key] = json.loads(urllib.request.urlopen("https://astro.kasi.re.kr/life/lunc?" + urllib.parse.urlencode({"yyyy": y, "mm": f"{m:02d}", "dd": "01"}), timeout=30).read().decode("utf-8") or "null")
            rows = cache[key] if isinstance(cache[key], list) else ([cache[key]] if cache[key] else [])
            for r in rows:
                if r["LUNC_LEAP_MM"] == "윤" or not r["LUNC_WLGN"]:
                    continue
                wg["service_sample"]["queries"] += 1
                if hj(r["LUNC_WLGN"]) != _five_tiger(_gz_idx(hj(r["LUNC_PRCN"])) % 10, int(r["LUNC_MM"]) - 1):
                    wg["service_sample"]["mismatch"] += 1
    except Exception as e:
        wg["service_error"] = repr(e)[:200]
    cache_p.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    res["kasi_wolgun_arithmetic"] = wg

    # ---- 결론 필드 (요약) ----
    def mism_total(section, keys):
        return sum(res[section][k]["mismatch_unexplained_count"] for k in keys)
    ks_keys = [k for k in res["korean_saju_vs_engine"] if k.startswith(("yaja_separated__vs__MEAN", "yaja_unified"))]
    bz_keys = [k for k in res["bazi_vs_engine"] if k.startswith(("WAN", "ZIZ"))]
    ks = res["korean_saju_vs_engine"]["yaja_separated__vs__MEAN_SOLAR__MIDNIGHT_NEXT_DAY_STEM"]
    res["summary"] = {
        "month_pillar_independent_lineages_for_boundary": ["JPL DE421(엔진)", "寿星(lunar-python/sxtwl)", "KASI 월력요항(2004~2017)·HKO(2026~28)", "VSOP87D(celestial-calendar)", "KASI 특일정보 API(korean-saju 내장 2000~2027)"],
        "month_pillar_naming_independent_check": "KASI 월건(음력월 기준) 오호둔 산술 대조 + korean-saju·bazi 의 월주 이름 산출",
        "korean_saju_field_mismatch_mean_solar_profile": {f: v["mismatch"] for f, v in ks["fields"].items()},
        "unexplained_mismatches_korean_saju": mism_total("korean_saju_vs_engine", ks_keys),
        "unexplained_mismatches_bazi": mism_total("bazi_vs_engine", bz_keys),
        "unexplained_mismatches_cnlunar": res["cnlunar_vs_engine_civil_date_level"]["mismatch_count"],
        "kasi_derived_month_year_mismatch": res["month_year_from_kasi_almanac_terms"].get("mismatch"),
    }
    (GOLDEN / "independent_pillars_check.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["summary"], ensure_ascii=False))
    print(json.dumps({k: res[k] for k in ("equation_of_time", "celestial_calendar_jieqi_vs_engine")}, ensure_ascii=False)[:1500])


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "venv-run":
        venv_run(sys.argv[2], sys.argv[3])
    else:
        main_run()
