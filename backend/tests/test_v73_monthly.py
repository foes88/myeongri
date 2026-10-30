"""월운 테스트. 월 기둥은 독립 라이브러리(lunar-python, 절입 기준 월간지)와 날짜별로 대조한다. 가상 입력."""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from lunar_python import Solar

from app.astro_core import calculate_chart
from app.mingli import analyze_months
from app.mingli.layer6_monthly import month_segments


def indep_month_pillar(d: date) -> str:
    # 엔진이 읽은 것과 같은 절대 시각(한국 벽시계 정오, 서머타임 연도 포함)을 베이징 시각으로 바꿔 lunar-python(절입 기준 월간지)에 묻는다.
    utc = datetime(d.year, d.month, d.day, 12, tzinfo=ZoneInfo("Asia/Seoul")).astimezone(timezone.utc)
    bj = utc + timedelta(hours=8)
    return Solar.fromYmdHms(bj.year, bj.month, bj.day, bj.hour, bj.minute, 0).getLunar().getMonthInGanZhiExact()


@pytest.mark.parametrize("year", [1950, 1984, 2000, 2012, 2030, 2044])
def test_month_pillars_match_independent_library_every_day(year):
    d, bad = date(year, 1, 1), []
    segs = month_segments(year)
    while d.year == year:
        seg = next(s for s in segs if s["from"] <= d.isoformat() <= s["to"])
        if seg["month_pillar"] != indep_month_pillar(d):
            bad.append((d.isoformat(), seg["month_pillar"], indep_month_pillar(d)))
        d += timedelta(days=1)
    assert bad == []


def test_segments_cover_the_year_without_gaps_and_have_12_or_13_months():
    for y in (1990, 2030, 2049):
        s = month_segments(y)
        assert s[0]["from"] == f"{y}-01-01" and s[-1]["to"] == f"{y}-12-31" and len(s) in (12, 13)
        for a, b in zip(s, s[1:]):
            assert date.fromisoformat(b["from"]) - date.fromisoformat(a["to"]) == timedelta(days=1)
    # 입춘 전후로 세운이 바뀐다
    s = month_segments(2030)
    assert s[0]["sewun_pillar"] != next(x for x in s if x["from"].startswith("2030-02"))["sewun_pillar"]


def chart():
    return calculate_chart(year=1984, month=6, day=15, hour=10, minute=0, gender="male").to_dict()  # 가상 입력


def test_monthly_analysis_is_evidence_linked_and_marked_as_convention():
    c = chart()
    r = analyze_months(c, 2030)
    assert r["validation"]["ok"] and "구현자 규약" in r["note"] and len(r["months"]) >= 12
    nodes = {n["claim_id"]: n for n in r["graph"]["nodes"]}
    for m in r["months"]:
        assert m["claim_id"] in nodes and any("구현자 규약" in x or "후보" in x for x in nodes[m["claim_id"]]["counter_evidence"])
        for d in m["structure_delta"]:
            assert d["claim_id"] in nodes and d["change"] in ("강화", "약화", "신규 출현")
    # 월운 변화는 대운·세운 포함 대비 변화이므로 같은 해의 연 단위 분석과 독립이다
    assert r["months"][0]["luck"] is not None


def test_monthly_luck_follows_the_daeun_change_inside_a_month():
    c = chart()
    start = next(x["start_date"] for x in c["daeun"]["cycles"][1:3])  # 두 번째·세 번째 대운 시작일(가상 명식)
    year = int(start[:4])
    r = analyze_months(c, year)
    lucks = [(m["from"], m["to"], m["luck"]) for m in r["months"]]
    before = (date.fromisoformat(start) - timedelta(days=1)).isoformat()
    cut = [x for x in lucks if x[1] == before]
    assert cut and next(x for x in lucks if x[0] == start)[2] != cut[0][2]  # 대운 교체일에서 구간이 나뉘고 대운 기둥이 바뀐다


def test_monthly_rejects_out_of_range_year():
    with pytest.raises(ValueError):
        analyze_months(chart(), 1800)


def test_single_year_answer_has_monthly_flow_and_multi_year_does_not():
    from tests.test_v69_synthesis import run
    _, a, syn = run(years=(2030,), domains=("overall", "wealth", "career"))
    mo = syn["period_flow"]["monthly"]
    assert a["months"]["validation"]["ok"] and len(mo["items"]) >= 12 and mo["rule_status"] == "implementer_convention" and "구현자 규약" in mo["note"]
    assert any("월운" in u["text"] and "구현자 규약" in u["text"] for u in syn["uncertainty"])
    assert any(i["standout"] for i in mo["items"]) and all(i["claim_ids"] for i in mo["items"])
    _, a5, s5 = run(years=(2030, 2031), domains=("overall",))
    assert "monthly" not in s5["period_flow"] and a5["months"] is None
    assert not any(__import__("re").search(r"반드시|확실히|보장합니다|\d+\s*%", i["one_line"]) for i in mo["items"])
