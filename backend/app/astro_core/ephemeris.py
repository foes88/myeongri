"""천문 계산 계층: Skyfield + JPL DE421. 간지 규칙은 모른다(순수 천문량만).

DE421 유효 범위는 1899-07 ~ 2053-10 이다. 범위 밖은 계산하지 않고 오류로 거절한다.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import skyfield
from skyfield import almanac, almanac_east_asia
from skyfield.api import Loader

EPHEMERIS_NAME = "de421.bsp"
DATA_DIR = Path(os.environ.get("MYEONGRI_EPHEMERIS_DIR", Path(__file__).resolve().parents[2] / "data"))
SUPPORTED_UTC_RANGE = (datetime(1901, 1, 1, tzinfo=timezone.utc), datetime(2050, 12, 31, tzinfo=timezone.utc))
SOLAR_TERM_SOURCE = f"skyfield {skyfield.__version__} almanac_east_asia.solar_terms / JPL {EPHEMERIS_NAME}"

# 24절기 index k ↔ 태양 황경 15k°. 홀수 k 가 월을 여는 12절(節): 입춘(21)=315°, 경칩(23)…소한(19)
JIE_INDICES = (21, 23, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19)


@lru_cache(maxsize=1)
def _load():
    loader = Loader(str(DATA_DIR))
    eph = loader(EPHEMERIS_NAME)  # 파일이 없으면 최초 1회 다운로드
    return loader.timescale(), eph


def _check_range(dt: datetime) -> None:
    lo, hi = SUPPORTED_UTC_RANGE
    if not lo <= dt <= hi:
        raise ValueError(f"지원 범위(1901~2050, DE421)를 벗어났습니다: {dt.isoformat()}")


@lru_cache(maxsize=64)
def solar_terms_in_utc_year(year: int) -> tuple[tuple[datetime, int], ...]:
    """UTC 기준 해당 연도에 걸린 24절기 (UTC 시각, k) 목록. 초 이하는 반올림하지 않는다."""
    ts, eph = _load()
    times, idx = almanac.find_discrete(ts.utc(year, 1, 1), ts.utc(year + 1, 1, 1), almanac_east_asia.solar_terms(eph))
    return tuple((t.utc_datetime(), int(k)) for t, k in zip(times, idx))


def solar_terms_around(utc_dt: datetime) -> list[tuple[datetime, int]]:
    _check_range(utc_dt)
    out: list[tuple[datetime, int]] = []
    for y in (utc_dt.year - 1, utc_dt.year, utc_dt.year + 1):
        if 1900 <= y <= 2051:
            out.extend(solar_terms_in_utc_year(y))
    return sorted(out)


def equation_of_time_minutes(utc_dt: datetime) -> float:
    """균시차 = 시태양시 − 평균태양시 (분). 양수면 해시계가 시계보다 빠르다(11월 초 약 +16분).

    겉보기 적경(RA of date)과 겉보기 항성시(GAST)에서 직접 구한다:
      그리니치 시태양시 = GAST − RA + 12h,  EoT = 그리니치 시태양시 − UT1 시각(시).
    """
    _check_range(utc_dt)
    ts, eph = _load()
    t = ts.from_datetime(utc_dt)
    ra, _, _ = eph["earth"].at(t).observe(eph["sun"]).apparent().radec(epoch="date")
    apparent_h = (t.gast - ra.hours + 12.0) % 24.0
    mean_h = ((t.ut1 + 0.5) % 1.0) * 24.0  # UT1 자정 기준 시각(시)
    diff_h = (apparent_h - mean_h + 12.0) % 24.0 - 12.0
    return diff_h * 60.0


def equation_of_time_meeus_minutes(utc_dt: datetime) -> float:
    """Meeus 근사식(Astronomical Algorithms ch.28)으로 구한 독립 교차검증용 균시차 (분)."""
    import math
    jd = (utc_dt - datetime(2000, 1, 1, 12, tzinfo=timezone.utc)) / timedelta(days=1)
    T = jd / 36525.0
    L0 = math.radians((280.46646 + 36000.76983 * T + 0.0003032 * T * T) % 360)
    M = math.radians((357.52911 + 35999.05029 * T - 0.0001537 * T * T) % 360)
    e = 0.016708634 - 0.000042037 * T
    eps = math.radians(23.439291 - 0.0130042 * T)
    y = math.tan(eps / 2) ** 2
    E = (y * math.sin(2 * L0) - 2 * e * math.sin(M) + 4 * e * y * math.sin(M) * math.cos(2 * L0)
         - 0.5 * y * y * math.sin(4 * L0) - 1.25 * e * e * math.sin(2 * M))
    return math.degrees(E) * 4.0


def library_versions() -> dict[str, str]:
    return {"skyfield": skyfield.__version__, "ephemeris": EPHEMERIS_NAME}
