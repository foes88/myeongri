"""Mingli-Graph 3~5층: 생극제화, 격국·조후·용신 분리, 대운·세운 구간 분리와 복수 연도 비교."""
import random

import pytest
from fastapi.testclient import TestClient

from app.astro_core import calculate_chart, engine
from app.main import app
from app.mingli import analyze_periods, analyze_structure
from app.mingli.layer3 import RANK_LABEL

STEMS, BR = "甲乙丙丁戊己庚辛壬癸", "子丑寅卯辰巳午未申酉戌亥"
client = TestClient(app)


def rnd(rng):
    i = rng.randrange(60)
    return STEMS[i % 10] + BR[i % 12]


def struct(r, name):
    return next(s for s in r["layer3"]["structures"] if s["name"] == name)


def test_random_charts_l345_invariants():
    rng = random.Random(11)
    banned = ("반드시", "확정적으로", "대길", "대흉", "점수")
    for _ in range(300):
        p = {k: rnd(rng) for k in ("year", "month", "day", "hour")}
        r = analyze_structure(p)
        assert r["validation"]["ok"], (p, r["validation"]["problems"][:2])
        assert {s["label"] for s in r["layer3"]["structures"]} <= set(RANK_LABEL.values()) | {"없음"}
        ys = r["layer4"]["yongshin"]
        assert set(ys) >= {"geukguk", "eokbu", "johu", "conflicts"} and r["layer4"]["johu"]["gungtong_table"] == "미구현"
        for n in r["graph"]["nodes"]:
            text = " ".join([n["interpretation_summary"]] + n["supporting_evidence"] + n["counter_evidence"])
            assert not any(b in text for b in banned), text


def test_sanggwan_gyeongwan_with_counter_candidates():
    r = analyze_structure({"year": "辛未", "month": "丁丑", "day": "甲子", "hour": "乙亥"})  # 가상 명식: 傷官 丁 + 正官 辛 모두 천간
    s = struct(r, "상관견관")
    assert s["label"] == "뚜렷(천간 노출)"
    assert any("상관패인" in c for c in s["counter"]) and any("통관" in c for c in s["counter"])


def test_gunggeop_requires_two_bigeop_and_records_counter():
    one = struct(analyze_structure({"year": "己巳", "month": "庚午", "day": "甲戌", "hour": "丙寅"}), "군겁쟁재")
    assert one["label"] == "없음" and any("2개 미만" in c for c in one["counter"])
    many = struct(analyze_structure({"year": "甲寅", "month": "乙卯", "day": "甲辰", "hour": "戊辰"}), "군겁쟁재")
    assert many["rank"] >= 2 and many["label"] != "없음"


def test_pyeonin_dosik_counter_is_recorded():
    r = analyze_structure({"year": "丙寅", "month": "壬申", "day": "甲午", "hour": "乙亥"})
    assert any("편인도식" in c for c in struct(r, "식상생재")["counter"])


def test_chain_edges_are_recorded():
    r = analyze_structure({"year": "庚申", "month": "甲寅", "day": "甲辰", "hour": "丙寅"})
    assert r["layer3"]["chains"]
    ids = {c["claim_id"] for c in r["layer3"]["chains"]}
    assert any(e["from"] in ids and e["type"] == "depends_on" for e in r["graph"]["edges"])


def test_jeonggwan_seonggyeok_candidate():
    r = analyze_structure({"year": "己丑", "month": "辛酉", "day": "甲子", "hour": "乙亥"})
    assert r["layer4"]["gyeokguk"]["tugan_priority"] == "정관격"
    assert r["layer4"]["seongpa"]["정관격"]["status"] == "성격 후보"


def test_jeonggwan_pagyeok_without_rescue():
    r = analyze_structure({"year": "己巳", "month": "辛酉", "day": "甲午", "hour": "丁卯"})  # 傷官 丁 있고 인성 없음
    sp = r["layer4"]["seongpa"]["정관격"]
    assert sp["status"] == "파격 후보(구응 없음)" and "상관견관" in sp["break_factors"]


def test_pagyeok_with_rescue_is_flagged_not_hidden():
    r = analyze_structure({"year": "己巳", "month": "辛酉", "day": "甲子", "hour": "丁卯"})  # 子 癸 인성이 구응 후보
    sp = r["layer4"]["seongpa"]["정관격"]
    assert sp["status"] == "파격이나 구응 후보" and sp["rescue_factors"]


def test_geonrok_is_held_not_decided():
    r = analyze_structure({"year": "庚申", "month": "甲寅", "day": "甲辰", "hour": "丙寅"})
    assert r["layer4"]["gyeokguk"]["special"] == "건록격 후보(월겁)"
    assert r["layer4"]["seongpa"]["건록격 후보(월겁)"]["status"] == "판정 보류(미구현)"


def test_school_disagreement_on_geokguk_name_is_linked():
    # 酉월(본기 辛=정관)이지만 중기·여기 없음 → 일치. 午월 己일: 본기 丁, 중기 己(비견)... 불일치 사례를 찾아 간선 확인
    rng = random.Random(5)
    found = False
    for _ in range(400):
        p = {k: rnd(rng) for k in ("year", "month", "day", "hour")}
        r = analyze_structure(p)
        gk = r["layer4"]["gyeokguk"]
        if not gk["agree"]:
            found = True
            assert any(e["type"] == "conflicts" and {e["from"], e["to"]} == set(gk["claims"]) for e in r["graph"]["edges"])
            break
    assert found


def test_yongshin_three_kinds_are_not_merged_and_conflicts_listed():
    rng = random.Random(9)
    saw_conflict = False
    for _ in range(300):
        p = {k: rnd(rng) for k in ("year", "month", "day", "hour")}
        ys = analyze_structure(p)["layer4"]["yongshin"]
        if ys["conflicts"]:
            saw_conflict = True
            assert "합치지 않고" in ys["conflicts"][0]["note"]
    assert saw_conflict


def test_johu_direction_by_season_without_table():
    cold = analyze_structure({"year": "癸亥", "month": "壬子", "day": "甲子", "hour": "甲子"})["layer4"]["johu"]
    hot = analyze_structure({"year": "丙午", "month": "丙午", "day": "甲午", "hour": "丙寅"})["layer4"]["johu"]
    assert cold["direction_elements"] == ["火"] and hot["direction_elements"] == ["水"]


# ---------- Layer 5 ----------
@pytest.fixture(scope="module")
def chart():
    return calculate_chart(year=1984, month=6, day=15, hour=10, minute=0, gender="male").to_dict()  # 가상 입력


def test_year_is_split_at_lichun(chart):
    p = analyze_periods(chart, [2030])
    segs = p["periods"]["per_year"][2030]["segments"]
    assert len(segs) >= 2
    assert segs[0]["sewun_pillar"] == engine.gz(2029 - 4) and segs[-1]["sewun_pillar"] == engine.gz(2030 - 4)  # 1월~입춘은 전년 세운
    assert any("입춘" in "".join(s["starts_at_boundary"]) for s in segs)
    assert p["periods"]["per_year"][2030]["validation"]["ok"]


def test_daeun_change_year_splits_luck(chart):
    cycles = chart["daeun"]["cycles"]
    y = int(cycles[2]["start_date"][:4])
    p = analyze_periods(chart, [y])
    segs = p["periods"]["per_year"][y]["segments"]
    lucks = [s["luck"]["pillar"] for s in segs]
    assert cycles[1]["pillar"] in lucks and cycles[2]["pillar"] in lucks and lucks.index(cycles[1]["pillar"]) < lucks.index(cycles[2]["pillar"])
    assert any("번째 대운 시작" in "".join(s["starts_at_boundary"]) for s in segs)
    assert p["periods"]["per_year"][y]["daeun_profile"] == chart["daeun"]["calculation_profile_id"]


def test_before_first_luck_has_no_luck_pillar(chart):
    y = int(chart["daeun"]["first_luck_date"][:4]) - 1
    p = analyze_periods(chart, [y])
    assert p["periods"]["per_year"][y]["segments"][0]["luck"]["pillar"] is None


def test_multi_year_comparison_has_no_scores(chart):
    p = analyze_periods(chart, [2030, 2031, 2029])
    rows = p["periods"]["comparison"]["rows"]
    assert [r["year"] for r in rows] == [2029, 2030, 2031] and "우열을 말하지 않는다" in p["periods"]["comparison"]["note"]

    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)
    assert not {"score", "points", "rating", "better", "luck_score"} & set(keys(p["periods"]["comparison"]))


def test_incoming_relations_include_chung_and_unconfirmed(chart):
    p = analyze_periods(chart, [2030])
    seg = p["periods"]["per_year"][2030]["segments"][-1]["analysis"]
    types = {x["type"] for x in seg["relations"]["year"]}
    assert types & {"충", "천간합", "육합", "파", "해", "복음(같은 지지)", "반합 형성 후보"}
    for who in ("luck", "year"):
        node = next(n for n in p["periods"]["per_year"][2030]["graph"]["nodes"] if n["claim_id"] == seg["relations"][who + "_claim"])
        assert any("확정하지 않음" in c for c in node["counter_evidence"])


def test_period_input_validation(chart):
    with pytest.raises(ValueError):
        analyze_periods(chart, list(range(2020, 2031)))
    with pytest.raises(ValueError):
        analyze_periods(chart, [1800])


def test_structure_delta_requires_rank_change():
    # 식상이 원국에 없고 운 천간이 食神이면 식상생재 '신규 출현' 또는 강화가 기록되어야 한다
    from app.mingli.evidence import EvidenceGraph
    from app.mingli.layer5 import analyze_period
    natal = {"year": "己丑", "month": "辛酉", "day": "甲子", "hour": "癸酉"}
    g = EvidenceGraph()
    res = analyze_period(natal, "丙寅", None, g)  # 丙=食神
    changes = {d["structure"]: d["change"] for d in res["structure_delta"]}
    assert "식상생재" in changes and changes["식상생재"] in ("신규 출현", "강화")
    assert not g.validate()


def test_api_periods_endpoint():
    body = {"birth_date": "1984-06-15", "birth_time": "10:00", "gender": "male", "years": [2030, 2031]}  # 가상 입력
    r = client.post("/api/v1/analysis/periods", json=body)
    assert r.status_code == 200 and r.json()["periods"]["years"] == [2030, 2031]
    assert r.json()["verification"]["may_claim_verified"] is False
    bad = client.post("/api/v1/analysis/periods", json={**body, "years": [1800]})
    assert bad.status_code == 422
