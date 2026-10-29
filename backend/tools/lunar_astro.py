"""천문 계산으로 음력을 유도하는 검증 도구(공식 자료 아님). 서비스 코드에서 쓰지 않는다.

규칙(현행 한·중 공통): 삭(朔, 합삭)이 속한 '현지 표준시 날짜'가 월의 초하루. 동지를 포함하는 달이 11월.
두 11월 사이가 13개월이면 중기(中氣)가 없는 첫 달이 윤달. 차이는 표준시 자오선뿐이다(중국 UTC+8, 한국 UTC+9).
※ 1954~1961년 한국은 UTC+8:30 이므로 이 도구는 1962년 이후에만 한국 기준으로 사용한다.
"""
from datetime import date, datetime, timedelta, timezone

from skyfield import almanac

from app.astro_core import ephemeris as eph

_cache = {}


def new_moons(y0, y1):
    key = (y0, y1)
    if key not in _cache:
        ts, e = eph._load()
        t, ph = almanac.find_discrete(ts.utc(y0, 1, 1), ts.utc(y1, 1, 1), almanac.moon_phases(e))
        _cache[key] = [x.utc_datetime() for x, p in zip(t, ph) if p == 0]
    return _cache[key]


def zhongqi(y):  # 짝수 index = 중기
    return [t for t, k in eph.solar_terms_in_utc_year(y) if k % 2 == 0]


def lunar_year_months(Y, hours):
    """[(월번호, 윤달여부, 초하루 date)] — 전년 11월(동지월)부터 음력 Y년 12월까지."""
    tz = timezone(timedelta(hours=hours))
    nm = [t.astimezone(tz).date() for t in new_moons(Y - 2, Y + 2)]
    zq = [t.astimezone(tz).date() for yy in (Y - 1, Y, Y + 1) for t in zhongqi(yy)]
    solstices = [t.astimezone(tz).date() for yy in (Y - 1, Y, Y + 1) for t, k in eph.solar_terms_in_utc_year(yy) if k == 18]

    def idx_of_month_containing(d):
        return max(i for i, s in enumerate(nm) if s <= d)
    a, b = idx_of_month_containing(solstices[0]), idx_of_month_containing(solstices[1])   # 전년 동지월, 올해 동지월(=11월)
    has_leap = b - a == 13
    months, num, leap_done = [], 11, False
    for i in range(a, b + 2):
        lo, hi = nm[i], nm[i + 1]
        if i == a:
            num, is_leap = 11, False
        else:
            has_zq = any(lo <= z < hi for z in zq)
            if i < b and has_leap and not leap_done and not has_zq:
                is_leap, leap_done = True, True       # 번호는 직전 달 유지
            else:
                num = num % 12 + 1
                is_leap = False
        months.append((num, is_leap, lo))
    return months  # 전년 동지월(11월)부터 올해 12월까지; 호출자는 초하루 날짜로 대조
