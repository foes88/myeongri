"""음양력 변환. 주 계산: 한국천문연구원(KARI) 자료 기반 korean_lunar_calendar.
교차검증: lunar_python(중국 음력). 한·중 음력이 다른 해에는 불일치를 경고로 남긴다.
"""
from __future__ import annotations

from datetime import date

from korean_lunar_calendar import KoreanLunarCalendar
from lunar_python import Lunar, Solar

LIBRARY = "korean_lunar_calendar 0.4.0 (KARI) / cross: lunar-python 1.4.8"


def lunar_to_solar(year: int, month: int, day: int, is_leap: bool) -> tuple[date, list[str]]:
    cal = KoreanLunarCalendar()
    if not cal.setLunarDate(year, month, day, is_leap):
        kind = "윤달" if is_leap else "평달"
        raise ValueError(f"존재하지 않는 음력 날짜입니다: {year}-{month:02d}-{day:02d} ({kind})")
    solar = date(cal.solarYear, cal.solarMonth, cal.solarDay)
    warnings: list[str] = []
    # 중국 음력과 대조: 같은 양력일에서 음력 연월일·윤달이 같아야 한다
    cn = Solar.fromYmd(solar.year, solar.month, solar.day).getLunar()
    cn_leap = cn.getMonth() < 0
    if (cn.getYear(), abs(cn.getMonth()), cn.getDay(), cn_leap) != (year, month, day, is_leap):
        warnings.append("lunar_calendar_kr_cn_mismatch")
    return solar, warnings


def solar_to_lunar(d: date) -> dict:
    cal = KoreanLunarCalendar()
    if not cal.setSolarDate(d.year, d.month, d.day):
        raise ValueError(f"음양력 변환 범위 밖입니다: {d}")
    return {"year": cal.lunarYear, "month": cal.lunarMonth, "day": cal.lunarDay, "is_leap": bool(cal.isIntercalation)}
