"""주어진 네 기둥의 '구조'를 결정론적으로 분석한다. 달력/절기 계산은 하지 않는다.

입력 간지가 맞는지는 이 모듈이 보증하지 않는다(검산 상태는 gate.py).
해석 문장이 아니라 해석이 참조할 사실표(십성, 지장간, 투출/암장)만 만든다.
"""
from __future__ import annotations

from .report_checks import (
    BRANCH_SEASON, HIDDEN_STEMS_PROFILE, STEMS, _ELEMENT, _GENERATES, ten_god,
)

POSITIONS = ("year", "month", "day", "hour")
GROUP_OF = {
    "比肩": "비겁", "劫財": "비겁", "食神": "식상", "傷官": "식상", "偏財": "재성", "正財": "재성",
    "七殺": "관성", "正官": "관성", "偏印": "인성", "正印": "인성",
}
GROUPS = ("비겁", "식상", "재성", "관성", "인성")
_BRANCH_ELEMENT = {"寅": "木", "卯": "木", "巳": "火", "午": "火", "申": "金", "酉": "金", "亥": "水", "子": "水",
                   "辰": "土", "戌": "土", "丑": "土", "未": "土"}


def analyze_chart(pillars: dict[str, str]) -> dict:
    """pillars: {'year':'庚申','month':'甲寅','day':'甲辰','hour':'丙寅'} (시 미상이면 'hour' 생략)."""
    for pos, gz in pillars.items():
        if pos not in POSITIONS or len(gz) != 2 or gz[0] not in STEMS or gz[1] not in HIDDEN_STEMS_PROFILE:
            raise ValueError(f"잘못된 간지 입력: {pos}={gz!r}")
    if "day" not in pillars or "month" not in pillars:
        raise ValueError("일주와 월주는 필수입니다")

    day_stem, month_branch = pillars["day"][0], pillars["month"][1]
    ten_gods = {p: ten_god(day_stem, gz[0]) for p, gz in pillars.items() if p != "day"}
    hidden = {p: {"branch": gz[1], "stems": [{"stem": s, "ten_god": ten_god(day_stem, s)} for s in HIDDEN_STEMS_PROFILE[gz[1]]]}
              for p, gz in pillars.items()}

    groups = {g: {"visible": 0, "hidden": 0, "level": "absent"} for g in GROUPS}
    for tg in ten_gods.values():
        groups[GROUP_OF[tg]]["visible"] += 1
    for h in hidden.values():
        for s in h["stems"]:
            groups[GROUP_OF[s["ten_god"]]]["hidden"] += 1
    for v in groups.values():
        v["level"] = "visible" if v["visible"] else ("hidden" if v["hidden"] else "absent")

    roots = [p for p, h in hidden.items() if any(s["stem"] == day_stem for s in h["stems"])]
    d_el, m_el = _ELEMENT[day_stem], _BRANCH_ELEMENT[month_branch]
    season_support = m_el == d_el or _GENERATES[m_el] == d_el
    # D등급 구현 편의 휴리스틱: 점수/퍼센트를 쓰지 않는 거친 후보 라벨 (04 금지 준수)
    if season_support and len(roots) >= 2:
        strength = "strong_candidate"
    elif not season_support and not roots:
        strength = "weak_candidate"
    else:
        strength = "undetermined"
    return {
        "day_stem": day_stem, "month_branch": month_branch, "season": BRANCH_SEASON[month_branch],
        "ten_gods": ten_gods, "hidden": hidden, "groups": groups,
        "day_stem_roots": roots, "season_support": season_support, "strength_candidate": strength,
    }
