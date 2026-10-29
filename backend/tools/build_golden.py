"""골든 케이스 생성. 기대값은 반드시 '외부 기준'에서 얻는다(엔진 출력으로 채우지 않는다).
  - 간지: lunar-python 1.4.8 (년·월: 북경시 절입 순간, 일·시: 보정된 시계 시각)
  - 절기/음력: HKO (2026~28 분 단위 시각, 1901~2050 날짜)
  - 시간 보정: 경도(°×4분) + 균시차 Meeus 근사식(엔진의 GAST−RA 방식과 독립)
  - 대운: lunar-python Yun sect=2 (분 단위 3일=1년 환산; 기본 sect=1 은 시진 단위로 거칠다)
실행: python -m tools.build_golden → golden/cases.json
"""
import json
import random
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from lunar_python import Solar

from app.astro_core import ephemeris as eph

G = Path(__file__).resolve().parents[1] / "golden"
from tools.paths import EXT_CASES, HKO_FILE, KASI_FILE
# 이용 조건이 불명확한 HKO/KASI 자료는 data_private/ (gitignored)에만 둔다. 공개 cases.json 에는 이 자료에서 파생한 기대값을 넣지 않는다.
HKO = json.loads(HKO_FILE.read_text(encoding="utf-8")) if HKO_FILE.exists() else None
HKT, KST, BJ = timezone(timedelta(hours=8)), ZoneInfo("Asia/Seoul"), timezone(timedelta(hours=8))
LP = {"tool": "lunar-python", "version": "1.4.8"}
HKO_REF = {"tool": "HKO", "version": "accessed " + HKO["meta"]["accessed"]} if HKO else None
cases = []
ext_cases = []  # 비공개(외부 자료 파생)
_target = cases
seq = {}


def add(cat, desc, inp, profile, expect, refs, fields, tol, note=""):
    seq[cat] = seq.get(cat, 0) + 1
    _target.append({"test_id": f"G-{cat}-{seq[cat]:03d}", "category": cat, "description": desc, "synthetic_input": True,
                  "input": inp, "profile": profile, "expect": expect, "references": refs, "fields_checked": fields,
                  "tolerance": tol, "note": note})


def lp_pillars(utc, clock, zi):
    bj = utc.astimezone(BJ)
    ym = Solar.fromYmdHms(bj.year, bj.month, bj.day, bj.hour, bj.minute, bj.second).getLunar()
    dh = Solar.fromYmdHms(clock.year, clock.month, clock.day, clock.hour, clock.minute, clock.second).getLunar()
    p = {"year": ym.getYearInGanZhiExact(), "month": ym.getMonthInGanZhiExact(),
         "day": dh.getDayInGanZhiExact() if zi == "ZI_2300_DAY_CHANGE" else dh.getDayInGanZhi(),
         "hour": dh.getTimeInGanZhi() if clock.hour < 23 else None}
    return {k: v for k, v in p.items() if v}


def local_utc(naive):
    return naive.replace(tzinfo=KST).astimezone(timezone.utc)


def inp(naive, gender="male", place="서울특별시", **kw):
    return {"year": naive.year, "month": naive.month, "day": naive.day, "hour": naive.hour, "minute": naive.minute,
            "gender": gender, "place": place, **kw}


CIVIL = {"time_profile": "CIVIL_TIME", "zi_profile": "ZI_2300_DAY_CHANGE"}
rng = random.Random(61)

# 1) 일반 날짜 24 — 절기·자시 경계에서 먼저 멀리 떨어진 시각
n = 0
while n < 24:
    d = datetime(1950, 1, 1) + timedelta(minutes=rng.randrange(0, 60 * 24 * 365 * 90))
    d = d.replace(hour=rng.choice([3, 6, 9, 12, 14, 16, 18, 20]), minute=rng.choice([10, 20, 40, 50]))
    try:
        u = local_utc(d)
        if min(abs((u - t).total_seconds()) for t, _ in eph.solar_terms_around(u)) < 3 * 86400:
            continue
        if u.astimezone(KST).replace(tzinfo=None) != d or u.astimezone(KST).dst():
            continue
    except ValueError:
        continue
    n += 1
    add("GEN", "일반 날짜(가상 입력)", inp(d, rng.choice(["male", "female"])), CIVIL,
        {"pillars": lp_pillars(u, d, CIVIL["zi_profile"])}, [LP], ["year", "month", "day", "hour"], "exact")

# 2) 절입 전후 24 — lunar-python 2027 12절 시각 ±3분 (공개 가능: MIT 라이브러리 계산값)
JIE_ZH = ("小寒", "立春", "惊蛰", "清明", "立夏", "芒种", "小暑", "立秋", "白露", "寒露", "立冬", "大雪")
_tab = Solar.fromYmd(2027, 6, 1).getLunar().getJieQiTable()
for i, nm in enumerate(JIE_ZH):
    o = _tab[nm] if nm != "大雪" else Solar.fromYmd(2027, 12, 20).getLunar().getJieQiTable()[nm]
    ref = datetime(o.getYear(), o.getMonth(), o.getDay(), o.getHour(), o.getMinute(), o.getSecond(), tzinfo=BJ)
    for side, delta in (("before", -3), ("after", 3)):
        u = (ref + timedelta(minutes=delta)).astimezone(timezone.utc)
        kst = u.astimezone(KST).replace(tzinfo=None)
        exp = lp_pillars(u, kst, CIVIL["zi_profile"])
        add("TERM", f"절입 {side} 3분 (lunar-python 2027 {nm})", inp(kst), CIVIL,
            {"pillars": {k: exp[k] for k in ("year", "month")}, "boundary_side": side}, [LP], ["year", "month"],
            "exact", "기대 간지·경계 시각=lunar-python. 엔진과 5초 이내 차이이므로 ±3분은 안전")

# 3) 자시 경계 12
for (y, m, d) in ((2015, 6, 10), (2023, 11, 3)):
    for zi in ("ZI_2300_DAY_CHANGE", "MIDNIGHT_SAME_DAY_STEM"):
        for (hh, mi) in ((22, 59), (23, 0), (23, 30), (0, 0), (0, 30), (1, 0)):
            if (y, m, d) == (2023, 11, 3) and (hh, mi) not in ((23, 30), (0, 30)):
                continue
            naive = datetime(y, m, d, hh, mi)
            exp = lp_pillars(local_utc(naive), naive, zi)
            fields = [k for k in ("day", "hour") if k in exp]
            add("ZI", f"자시 경계 {zi}", inp(naive), {"time_profile": "CIVIL_TIME", "zi_profile": zi},
                {"pillars": {k: exp[k] for k in fields}}, [LP], fields, "exact",
                "23시대 시주 천간은 학파차이라 lunar-python 비교 제외")

# 4) 평균/진태양시 12 — 경도(°×4분)+Meeus 균시차 → lunar-python 시주
places = {"서울특별시": 126.9780, "부산광역시": 129.0756, "광주광역시": 126.8526, "제주특별자치도": 126.5312}
cands = [(datetime(2010, 2, 11, 7, 40), "서울특별시"), (datetime(2012, 11, 3, 8, 20), "부산광역시"),
         (datetime(2005, 5, 15, 12, 20), "광주광역시"), (datetime(1999, 8, 20, 14, 5), "제주특별자치도"),
         (datetime(2021, 10, 25, 18, 50), "서울특별시"), (datetime(1990, 3, 3, 4, 45), "부산광역시")]
for naive, place in cands:
    u = local_utc(naive)
    for tp, with_eot in (("LOCAL_MEAN_SOLAR_TIME", False), ("LOCAL_APPARENT_SOLAR_TIME", True)):
        mins = places[place] * 4 + (eph.equation_of_time_meeus_minutes(u) if with_eot else 0)
        clock = (u + timedelta(minutes=mins)).replace(tzinfo=None)
        exp = lp_pillars(u, clock, "ZI_2300_DAY_CHANGE")
        add("SOLAR", f"{tp} {place}", inp(naive, place=place), {"time_profile": tp, "zi_profile": "ZI_2300_DAY_CHANGE"},
            {"pillars": {k: exp[k] for k in ("day", "hour") if k in exp}, "pillar_time": clock.isoformat()},
            [LP, {"tool": "Meeus EoT", "version": "Astronomical Algorithms ch.28"}], ["day", "hour", "pillar_time"],
            "pillar_time ±30s(근사식 차이), 간지 exact")

# 5) 역사적 시간대·서머타임 14 (기대 오프셋은 공개 연혁 — tzdata와 독립이 아님)
tzc = [(1948, 7, 1, 12, 0, 600, "1948 서머타임(+10:00, 초안의 540 기대값은 작성자 착오였음)"), (1951, 7, 1, 12, 0, 600, "1951 서머타임"), (1952, 7, 1, 12, 0, 540, "1952 서머타임 없음"), (1954, 7, 1, 12, 0, 510, "1954 +8:30 (서머타임 없음)"), (1955, 7, 1, 12, 0, 570, "1955 서머타임 +9:30"),
       (1957, 1, 1, 12, 0, 510, "1954~61 +8:30"), (1960, 7, 1, 12, 0, 570, "1960 서머타임"),
       (1961, 8, 9, 12, 0, 510, "표준시 변경 전날"), (1961, 8, 11, 12, 0, 540, "표준시 변경 후"),
       (1987, 5, 10, 3, 30, 600, "1987 서머타임 시작 직후"), (1987, 10, 11, 1, 0, 600, "1987 종료 직전"),
       (1988, 5, 8, 3, 30, 600, "1988 시작 직후"), (1988, 10, 9, 4, 0, 540, "1988 종료 후"),
       (1988, 7, 1, 12, 0, 600, "1988 한여름"), (1989, 7, 1, 12, 0, 540, "1989 서머타임 없음")]
TZREF = {"tool": "IANA tzdata/공개 연혁", "version": "tzdata 2024.1"}
for (y, m, d, hh, mi, off, why) in tzc:
    add("TZ", "가상 입력: " + why, {"year": y, "month": m, "day": d, "hour": hh, "minute": mi, "gender": "male"}, CIVIL,
        {"utc_offset_minutes": off}, [TZREF], ["utc_offset_minutes"], "exact", "tzdata와 독립 아님: 연혁 정합성 점검용")
add("TZ", "가상 입력: 1988-05-08 02:30 존재하지 않는 시각", {"year": 1988, "month": 5, "day": 8, "hour": 2, "minute": 30, "gender": "male"},
    CIVIL, {"error": "존재하지 않는"}, [TZREF], ["error"], "exact")
add("TZ", "가상 입력: 1988-10-09 02:30 중복 시각 → 경고", {"year": 1988, "month": 10, "day": 9, "hour": 2, "minute": 30, "gender": "male"},
    CIVIL, {"warning": "ambiguous_local_time"}, [TZREF], ["warning"], "exact")

# 6) 음력·윤달 — 기대값은 lunar-python(중국 음력). 한국 음력과 다른 해(2001·2012·2017)는 judgements.json 에서 별도 판정
from lunar_python import Lunar, LunarYear
for ys in ("1990", "2001", "2004", "2006", "2009", "2012", "2014", "2017", "2020", "2023"):
    leap_m = LunarYear.fromYear(int(ys)).getLeapMonth()
    base = {"calendar": "lunar", "year": int(ys), "month": leap_m, "day": 1, "gender": "male", "hour": 12, "minute": 0}
    add("LUNAR", f"{ys} 윤{leap_m}월 초하루", {**base, "is_leap_month": True}, CIVIL,
        {"solar_date": Lunar.fromYmd(int(ys), -leap_m, 1).getSolar().toYmd()}, [LP], ["solar_date"], "exact", "lunar-python(중국 음력) 기준")
    add("LUNAR", f"{ys} {leap_m}월(평달) 초하루", {**base, "is_leap_month": False}, CIVIL,
        {"solar_date": Lunar.fromYmd(int(ys), leap_m, 1).getSolar().toYmd()}, [LP], ["solar_date"], "exact", "lunar-python(중국 음력) 기준")
add("LUNAR", "2021 윤4월 없음 → 오류", {"calendar": "lunar", "year": 2021, "month": 4, "day": 1, "is_leap_month": True,
                                    "gender": "male", "hour": 12, "minute": 0}, CIVIL, {"error": "존재하지 않는"}, [LP], ["error"], "exact")
add("LUNAR", "2000 음력 설", {"calendar": "lunar", "year": 2000, "month": 1, "day": 1, "gender": "male", "hour": 12, "minute": 0},
    CIVIL, {"solar_date": Lunar.fromYmd(2000, 1, 1).getSolar().toYmd()}, [LP], ["solar_date"], "exact")

# 7) 대운 10 — 방향 exact, 시작 나이는 시진 단위 반올림 차이를 감안해 ±10일
for (y, m, d, hh, g) in [(1984, 6, 15, 10, "male"), (1984, 6, 15, 10, "female"), (1999, 3, 3, 9, "male"), (1999, 3, 3, 9, "female"),
                         (2000, 1, 1, 19, "male"), (1975, 3, 3, 3, "female"), (2008, 11, 7, 15, "male"), (1966, 9, 9, 21, "female"),
                         (2013, 5, 28, 13, "male"), (1992, 12, 25, 7, "female")]:
    bj = local_utc(datetime(y, m, d, hh)).astimezone(BJ)  # lunar-python 은 북경시 기준: KST 벽시계를 북경시로 환산해 입력
    yun = Solar.fromYmdHms(bj.year, bj.month, bj.day, bj.hour, bj.minute, 0).getLunar().getEightChar().getYun(1 if g == "male" else 0, 2)
    add("DAEUN", "대운 순역·기산 (3일=1년)", {"year": y, "month": m, "day": d, "hour": hh, "minute": 0, "gender": g}, CIVIL,
        {"direction": "forward" if yun.isForward() else "backward",
         "start_age": [yun.getStartYear(), yun.getStartMonth(), yun.getStartDay()]},
        [LP], ["direction", "start_age"], "방향 exact; 시작일수 ±1일(sect=2 분 단위 환산)")


# ===== 비공개 외부 자료 파생 케이스 (data_private/cases_external.json, gitignored) =====
_target = ext_cases
HG, HZ = dict(zip("갑을병정무기경신임계", "甲乙丙丁戊己庚辛壬癸")), dict(zip("자축인묘진사오미신유술해", "子丑寅卯辰巳午未申酉戌亥"))
if HKO:
    for ys, rows in HKO["terms_hm"].items():
        for i, (mo, dd, hh, mi) in enumerate(rows):
            add("TERMTIME", f"HKO 절기 시각 {ys}#{i}", {"year": int(ys), "ordinal_in_year": i}, {},
                {"term_hkt": [int(ys), mo, dd, hh, mi]}, [HKO_REF], ["term_time"], "±60s (HKO 분 단위 표기)", "분 단위: 초 단위 정답 아님")
if KASI_FILE.exists():
    _k = json.loads(KASI_FILE.read_text(encoding="utf-8"))
    KASI, KASI_REF = _k["years"], {"tool": "KASI 달력자료", "version": "accessed " + _k["meta"]["accessed"]}
    for ys, v in KASI.items():
        for i, t in enumerate(v["terms"]):
            add("KASITERM", f"KASI 절기 시각 {ys}#{i}", {"year": int(ys), "ordinal_in_year": i}, {}, {"term_kst": t["kst"]}, [KASI_REF],
                ["term_time"], "±60s (KASI 분 단위)", "비공식 달력자료")
        for m in v["months"]:
            y, mo, d = map(int, m["solar"].split("-"))
            add("KASILUNAR", f"KASI 음력 {ys} {m['lunar_month']}월{'(윤)' if m['is_leap'] else ''} 1일",
                {"calendar": "lunar", "year": int(ys), "month": m["lunar_month"], "day": 1, "is_leap_month": m["is_leap"], "gender": "male",
                 "hour": 12, "minute": 0}, CIVIL, {"solar_date": m["solar"]}, [KASI_REF], ["solar_date"], "exact", "비공식 달력자료")
            if m["day_gz"] and m["day_gz"][0] in HG:
                add("KASIDAY", f"KASI 일진(일주) {m['solar']}", {"year": y, "month": mo, "day": d, "hour": 12, "minute": 0, "gender": "male"}, CIVIL,
                    {"pillars": {"day": HG[m["day_gz"][0]] + HZ[m["day_gz"][1]]}}, [KASI_REF], ["day"], "exact", "KASI 일진 = 일주")

(G / "cases.json").write_text(json.dumps({"generated": datetime.now(timezone.utc).date().isoformat(), "cases": cases},
                                          ensure_ascii=False, indent=1), encoding="utf-8")
if ext_cases:
    EXT_CASES.parent.mkdir(parents=True, exist_ok=True)
    EXT_CASES.write_text(json.dumps({"generated": datetime.now(timezone.utc).date().isoformat(), "cases": ext_cases}, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(cases), dict(Counter(c["category"] for c in cases)), "| private:", len(ext_cases), dict(Counter(c["category"] for c in ext_cases)))
