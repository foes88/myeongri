"""v10.3 월별 흐름 테스트. 월별 방향 판정은 하지 않으며(사실·관계만), 실제 절입 구간은 독립 라이브러리(lunar-python)와 대조한다. 합성 입력만 사용."""
from datetime import date, datetime, timedelta

import pytest

from app import cases as C
from app.consult import agent, months as MO, verdict as V
from tools.bias_probe import charts

DOMS = ["overall", "wealth", "career"]


@pytest.fixture(scope="module")
def sample():
    ci = next(iter(charts(1, seed=44)))
    pre, _ = C.pre_for(ci, [2027])
    return ci, pre


def ans(pre, years, doms=DOMS):
    return agent.answer(pre, "종합 상담을 시작합니다", domains_=doms, years=years, depth="detailed")


def test_months_cover_the_whole_year_without_gaps_or_overlaps(sample):
    ci, pre = sample
    for y in (2027, 2028):
        items = ans(pre, [y])["verdict"]["months"][str(y)]["items"]
        assert items[0]["from"] == f"{y}-01-01" and items[-1]["to"] == f"{y}-12-31"
        for a, b in zip(items, items[1:]):
            assert date.fromisoformat(b["from"]) == date.fromisoformat(a["to"]) + timedelta(days=1)


def test_month_boundaries_match_an_independent_solar_term_table(sample):
    """절입 시각을 lunar-python 절기표와 대조(한국시간 = 중국시간 + 1시간, 2분 이내)."""
    from lunar_python import Solar
    ci, pre = sample
    names = {"입춘": "立春", "경칩": "惊蛰", "청명": "清明", "입하": "立夏", "망종": "芒种", "소서": "小暑", "입추": "立秋", "백로": "白露", "한로": "寒露", "입동": "立冬", "대설": "大雪", "소한": "小寒"}
    checked = 0
    for y in (2026, 2027, 2028, 2030):
        items = ans(pre, [y])["verdict"]["months"][str(y)]["items"]
        tbl = Solar.fromYmd(y, 6, 1).getLunar().getJieQiTable()
        for it in items:
            if not it["term_at"]:
                continue
            ref = tbl[names[it["term"]]]
            kst = datetime(y, ref.getMonth(), ref.getDay(), ref.getHour(), ref.getMinute()) + timedelta(hours=1)
            mine = datetime.strptime(f"{y}-{it['term_at']}", "%Y-%m-%d %H:%M")
            assert abs((mine - kst).total_seconds()) <= 120, (y, it["term"], mine, kst)
            checked += 1
    assert checked >= 30


def test_ipchun_boundary_marks_the_year_switch(sample):
    ci, pre = sample
    items = ans(pre, [2027])["verdict"]["months"]["2027"]["items"]
    ip = next(i for i in items if i["term"] == "입춘")
    assert ip["from"] == "2027-02-04" and any("입춘부터 그해의 기운" in n for n in ip["notes"]) and ip["term_at"]
    before = items[items.index(ip) - 1]
    assert not any("입춘부터" in n for n in before["notes"])


def test_no_directional_verdict_or_score_for_months(sample):
    ci, pre = sample
    for y, m in ans(pre, [2027, 2028])["verdict"]["months"].items():
        assert m["direction"] is None and "좋고 나쁨을 가르는 판정은 하지 않" in m["withheld"]
        for it in m["items"]:
            assert not ({"tone", "score", "rank", "probability", "direction"} & set(it))
            assert it["level"] in ("changes", "relations", "none")
            for lst in it["changes"].values():
                assert all(set(c) == {"text", "polarity"} for c in lst)


def test_month_changes_only_cover_requested_domains_and_skip_unsupported_years(sample):
    ci, pre = sample
    it = ans(pre, [2027], ["wealth"])["verdict"]["months"]["2027"]["items"]
    assert all(set(i["changes"]) <= {"wealth"} for i in it)
    assert MO.build_year(pre, 1900, DOMS) is None and MO.build_year(pre, 2050, DOMS) is None


def test_same_month_is_identical_across_request_paths(sample):
    ci, pre = sample
    one = ans(pre, [2027])["verdict"]["months"]["2027"]
    many = ans(pre, [2027, 2028, 2029])["verdict"]["months"]["2027"]
    assert one == many


def test_months_do_not_change_the_verdict(sample, monkeypatch):
    ci, pre = sample
    base = ans(pre, [2027, 2028])["verdict"]
    monkeypatch.setattr(V.MO, "build", lambda *a, **k: {})
    off = ans(pre, [2027, 2028])["verdict"]
    assert off["months"] == {}
    strip = lambda v: {k: x for k, x in v.items() if k != "months"}
    assert strip(base) == strip(off)


def test_luck_change_inside_a_month_splits_the_period(sample):
    ci, pre = sample
    cycles = pre["chart"]["daeun"]["cycles"]
    ys = sorted({int(c["start_date"][:4]) for c in cycles if 1902 <= int(c["start_date"][:4]) <= 2048})
    found = False
    for y in ys[:4]:
        items = MO.build_year(pre, y, DOMS)["items"]
        if any(any("10년 큰 흐름이 바뀝니다" in n for n in i["notes"]) for i in items):
            found = True
            break
    assert found


def test_no_birth_data_in_public_months(sample):
    ci, pre = sample
    text = str(ans(pre, [2027])["verdict"]["months"])
    assert "birth_date" not in text and "1988" not in text
