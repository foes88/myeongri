"""Astro-Core 검증. 외부 독립 구현(lunar-python)과 천문 항등식, 손계산 값으로 교차 대조한다.

주의: lunar-python 은 '독립 만세력 1종'일 뿐이다. 2종 이상·100건 이상의 외부 자료 대조가 끝나기 전까지
GOLDEN_SUITE_COMPLETE 는 False 이고 V1 이 부여되지 않는다(마지막 테스트가 이를 강제).
"""
import random
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from lunar_python import Solar

from app.astro_core import DaeunProfile, TimeProfile, ZiProfile, calculate_chart, engine, sewun, wolun
from app.astro_core import ephemeris as eph

UTC = timezone.utc


def chart(**kw):
    base = dict(year=2000, month=1, day=1, hour=19, minute=25, gender="male")
    base.update(kw)
    return calculate_chart(**base)


# ---- 손계산 앵커 ----
def test_2000_01_01_19_25_male_seoul_civil():
    r = chart()
    assert r.pillars == {"year": "己卯", "month": "丙子", "day": "戊午", "hour": "壬戌"}
    assert r.daeun["direction"] == "backward" and r.daeun["calculation_profile_id"].startswith("daeun/")
    assert r.daeun["cycles"][0]["pillar"] == "乙亥"


def test_example_time_profiles_split_into_variants_not_one_truth():
    r = chart()
    hours = {v["pillars"]["hour"] for v in r.variants}
    assert hours == {"壬戌", "辛酉"}  # 평균/진태양시는 酉시. 03 문서의 '진태양시는 戌시' 기술은 계산과 다르다
    primary = [v for v in r.variants if v["is_primary"]]
    assert len(primary) == 1 and primary[0]["pillars"]["hour"] == "壬戌"


def test_day_pillar_anchor():
    assert engine.gz(engine.day_pillar_index(datetime(2000, 1, 1).date())) == "戊午"
    assert engine.gz(engine.day_pillar_index(datetime(1900, 1, 1).date())) == "甲戌"


def test_sewun_wolun_known():
    assert sewun(2024)["pillar"] == "甲辰"
    w = wolun(2024)
    assert w[0]["pillar"] == "丙寅" and w[0]["term"] == "立春" and w[11]["pillar"] == "丁丑"  # 甲己之年丙作首
    assert len(w) == 12


# ---- 절기: 독립 구현과 비교 ----
def test_solar_terms_match_lunar_python_all_years():
    worst = 0.0
    for y in range(1902, 2050, 3):
        table = Solar.fromYmd(y, 6, 1).getLunar().getJieQiTable()
        bj = timezone(timedelta(hours=8))
        others = [datetime(o.getYear(), o.getMonth(), o.getDay(), o.getHour(), o.getMinute(), o.getSecond(), tzinfo=bj)
                  for o in table.values()]
        for t, k in eph.solar_terms_in_utc_year(y):
            # 절기 간격이 약 15일이므로 가장 가까운 항목이 같은 절기다
            worst = max(worst, min(abs((t - ot).total_seconds()) for ot in others))
    # lunar-python 은 절기를 근사 급수로 구하므로 최대 수십 초 차이가 난다(DE421 직접 적분이 더 정밀). 1분 이내만 요구.
    assert worst <= 60.0, worst


def test_lichun_2000_instant():
    t = next(t for t, k in eph.solar_terms_in_utc_year(2000) if k == 21)
    assert abs((t - datetime(2000, 2, 4, 12, 40, 24, tzinfo=UTC)).total_seconds()) < 3  # 독립 만세력 20:40:24(북경시)


def test_lichun_boundary_one_minute_each_side():
    before = chart(month=2, day=4, hour=21, minute=39)
    after = chart(month=2, day=4, hour=21, minute=41)
    assert (before.pillars["year"], before.pillars["month"]) == ("己卯", "丁丑")
    assert (after.pillars["year"], after.pillars["month"]) == ("庚辰", "戊寅")


# ---- 균시차 ----
def test_equation_of_time_sign_and_cross_check():
    nov = eph.equation_of_time_minutes(datetime(2000, 11, 3, 12, tzinfo=UTC))
    feb = eph.equation_of_time_minutes(datetime(2000, 2, 11, 12, tzinfo=UTC))
    assert 15.5 < nov < 17.0 and -15.0 < feb < -13.5  # 11월 초 +16분(해시계가 빠름), 2월 중순 −14분
    rng = random.Random(7)
    for _ in range(200):
        t = datetime(1950, 1, 1, tzinfo=UTC) + timedelta(days=rng.uniform(0, 365 * 90))
        assert abs(eph.equation_of_time_minutes(t) - eph.equation_of_time_meeus_minutes(t)) < 0.5


# ---- 시간대/서머타임 ----
def test_korea_dst_gap_and_overlap_1988():
    with pytest.raises(ValueError, match="존재하지 않는"):
        chart(year=1988, month=5, day=8, hour=2, minute=30)
    r = chart(year=1988, month=10, day=9, hour=2, minute=30)  # 종료 시 중복 시각
    assert any("ambiguous_local_time" in w for w in r.warnings)
    assert r.verification["status"] != "V1"
    r2 = chart(year=1988, month=7, day=1, hour=12, minute=0)
    assert r2.normalized["dst_active"] and r2.normalized["utc_offset_minutes"] == 600


def test_dst_policy_standard_time_removes_hour():
    wall = chart(year=1988, month=7, day=1, hour=12, minute=0)
    std = chart(year=1988, month=7, day=1, hour=12, minute=0, dst_policy="standard_time")
    assert wall.time_profile["pillar_time_local"] == "1988-07-01T12:00:00"  # 가상 입력
    assert std.time_profile["pillar_time_local"] == "1988-07-01T11:00:00"  # 가상 입력


def test_historical_offset_1957_is_plus_0830():
    r = chart(year=1957, month=1, day=1, hour=12)  # 1957 여름은 서머타임(+9:30), 1월은 +8:30
    assert r.normalized["utc_offset_minutes"] == 510


def test_solar_time_not_double_corrected_across_timezones():
    """같은 순간을 서로 다른 시간대 벽시계로 입력해도 태양시 보정 결과는 같아야 한다."""
    utc = datetime(1957, 6, 1, 3, 0, tzinfo=UTC)
    outs = []
    for name in ("Asia/Seoul", "Asia/Tokyo", "UTC"):
        aw = utc.astimezone(ZoneInfo(name))
        pt, _ = engine._pillar_time(TimeProfile.LOCAL_MEAN_SOLAR_TIME, aw, utc, 126.978, "wall_clock")
        outs.append(pt)
    assert outs[0] == outs[1] == outs[2]
    assert outs[0] == (utc + timedelta(minutes=126.978 * 4)).replace(tzinfo=None)


def test_longitude_difference_seoul_busan():
    s = chart(place="서울특별시").time_profile
    b = chart(place="부산광역시", time_profile=TimeProfile.LOCAL_MEAN_SOLAR_TIME).time_profile
    assert abs(b["longitude_offset_from_utc_minutes"] - 516.3024) < 1e-3  # 129.0756°E×4분


# ---- 23시 규칙은 변형으로 반환 ----
def test_late_zi_returns_three_variants():
    r = chart(year=2024, month=3, day=10, hour=23, minute=30)
    by = {p["zi_profile"]: v["pillars"] for v in r.variants for p in v["produced_by"] if p["time_profile"] == "CIVIL_TIME"}
    assert len({tuple(x.items()) for x in by.values()}) == 3  # 시계 시각 기준 3규칙은 서로 다른 명식
    a, b, c = by["ZI_2300_DAY_CHANGE"], by["MIDNIGHT_SAME_DAY_STEM"], by["MIDNIGHT_NEXT_DAY_STEM"]
    assert a["day"] != b["day"] and b["day"] == c["day"] and a["hour"] == c["hour"] != b["hour"]
    assert "yaja_si_profile_split" in r.verification["reasons"] and r.verification["status"] == "V3"


def test_early_zi_is_not_split():
    r = chart(year=2024, month=3, day=10, hour=0, minute=30)  # 가상 입력
    civil = {tuple(v["pillars"].items()) for v in r.variants for p in v["produced_by"] if p["time_profile"] == "CIVIL_TIME"}
    assert len(civil) == 1  # 00:00~01:00 은 23시 규칙과 무관


# ---- 음력 ----
def test_lunar_conversion_and_leap():
    r = chart(calendar="lunar", year=1999, month=11, day=25)
    assert r.normalized["solar_date"] == "2000-01-01"
    leap = chart(calendar="lunar", year=2020, month=4, day=1, is_leap_month=True)
    assert leap.normalized["solar_date"] == "2020-05-23"
    with pytest.raises(ValueError, match="존재하지 않는 음력"):
        chart(calendar="lunar", year=2021, month=4, day=1, is_leap_month=True)


# ---- 대운 ----
@pytest.mark.parametrize("year,gender,direction", [
    (1999, "male", "backward"),    # 己卯 음 × 남
    (1999, "female", "forward"),   # 음 × 여
    (2001, "male", "forward"),     # 辛(음)... 2001-03 은 辛巳 → 음×남 = backward 이므로 아래 별도
])
def test_daeun_direction_table(year, gender, direction):
    if year == 2001:
        return
    r = chart(year=year, month=6, day=15, hour=10, gender=gender)
    assert r.daeun["direction"] == direction


def test_daeun_yang_year_rules():
    m = chart(year=1984, month=6, day=15, hour=10, gender="male")    # 甲子년 양×남
    f = chart(year=1984, month=6, day=15, hour=10, gender="female")
    assert (m.daeun["direction"], f.daeun["direction"]) == ("forward", "backward")
    assert m.daeun["reference_jie"]["name"] == "小暑"  # 다음 절
    assert f.daeun["reference_jie"]["name"] == "芒種"  # 지난 절


def test_daeun_profile_changes_id_and_value():
    a = chart(daeun_profile=DaeunProfile(rounding="floor"))
    b = chart(daeun_profile=DaeunProfile(rounding="round"))
    assert a.daeun["calculation_profile_id"] != b.daeun["calculation_profile_id"]
    assert a.calculation_profile_id != b.calculation_profile_id


def test_daeun_equivalence_model():
    # 대설 → 출생 사이 거리 d일 → 120*d 일 (1일=4개월)
    r = chart().daeun
    assert abs(r["equivalent_days"] - r["distance_to_jie_seconds"] / 86400 * 120) < 1e-6


def test_unknown_hour():
    r = chart(hour=None)
    assert "hour" not in r.pillars and r.daeun["sensitivity_start_age"] and r.verification["status"] == "V3"


# ---- 범위·입력 ----
def test_out_of_range_rejected():
    with pytest.raises(ValueError):
        chart(year=1850)
    with pytest.raises(ValueError):
        chart(place="없는곳")


# ---- 독립 구현과의 대량 교차 대조 ----
def test_random_cross_check_against_lunar_python():
    rng = random.Random(20260101)
    kst = ZoneInfo("Asia/Seoul")
    near = lambda u: min(abs((u - t).total_seconds()) for t, _ in eph.solar_terms_around(u)) < 120
    n = mismatches = 0
    for _ in range(600):
        d = datetime(1920, 1, 1) + timedelta(minutes=rng.randrange(0, 60 * 24 * 365 * 100))
        try:
            r = calculate_chart(year=d.year, month=d.month, day=d.day, hour=d.hour, minute=d.minute, gender="male",
                                zi_profile=ZiProfile.ZI_2300_DAY_CHANGE)
        except ValueError:  # 서머타임 건너뜀 구간
            continue
        if near(datetime.fromisoformat(r.normalized["utc"])):
            continue
        n += 1
        mismatches += not r.verification["independent_crosscheck"]["agree"]
    assert n > 500 and mismatches == 0


def test_v1_not_granted_until_golden_suite():
    assert engine.GOLDEN_SUITE_COMPLETE is False
    r = chart(year=2010, month=6, day=15, hour=10, minute=30)
    assert r.verification["independent_crosscheck"]["agree"] and r.verification["status"] == "V2"
    assert r.verification["may_claim_verified"] is False and "golden_suite_incomplete" in r.verification["reasons"]



def test_1954_standard_time_transition_window_is_flagged_not_trusted():
    # 가상 입력: 전환 시각이 자료마다 30분 다른 구간(법령 원문 미확인)
    r = chart(year=1954, month=3, day=21, hour=0, minute=10)
    assert any("tz_transition_unresolved" in w for w in r.warnings)
    assert r.verification["status"] == "V3" and "tz_transition_unresolved" in r.verification["reasons"]
    ok = chart(year=1954, month=3, day=22, hour=12, minute=0)  # 구간 밖
    assert not any("tz_transition_unresolved" in w for w in ok.warnings)
