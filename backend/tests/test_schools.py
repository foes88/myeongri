"""Multi-School: 독립 평가, 공통·충돌, 점수 합치기 금지."""
import random

from app.mingli import analyze_structure
from app.mingli.schools import NOT_IMPLEMENTED, evaluate_eokbu, evaluate_gyeokguk, evaluate_johu

STEMS, BR = "甲乙丙丁戊己庚辛壬癸", "子丑寅卯辰巳午未申酉戌亥"


def rnd(rng):
    i = rng.randrange(60)
    return STEMS[i % 10] + BR[i % 12]


def test_schools_use_only_their_own_layer_inputs():
    r = analyze_structure({"year": "己丑", "month": "辛酉", "day": "甲子", "hour": "乙亥"})
    # 각 평가기는 서로의 결과 없이 단독 호출 가능해야 한다
    assert evaluate_gyeokguk(r["layer4"])["school_id"] == "gyeokguk"
    assert evaluate_eokbu(r["layer1"])["school_id"] == "eokbu"
    assert evaluate_johu(r["layer4"])["school_id"] == "johu"


def test_schools_output_fields_and_unimplemented_listed():
    r = analyze_structure({"year": "己丑", "month": "辛酉", "day": "甲子", "hour": "乙亥"})["schools"]
    for s in r["schools"].values():
        assert {"core_judgement", "applicability", "yongshin_candidates", "counter_evidence", "scope", "question", "claim_ids"} <= set(s)
    assert set(r["not_implemented"]) == set(NOT_IMPLEMENTED) and r["pairs"] and r["natural_language"]["relations"]


def test_conflict_is_explained_by_question_difference_not_score():
    rng = random.Random(21)
    seen_conflict = seen_common = False
    for _ in range(300):
        p = {k: rnd(rng) for k in ("year", "month", "day", "hour")}
        r = analyze_structure(p)
        sc = r["schools"]
        for pr in sc["pairs"]:
            if pr["relation"] == "충돌":
                seen_conflict = True
                assert "묻는 질문이 다름" in pr["cause"] and "정하지 않고 각각 설명" in pr["explanation"]
            if pr["relation"] == "공통":
                seen_common = True
                assert "예측한다는 뜻은 아닙니다" in pr["explanation"]
        assert "검증된 예측이 아니다" in sc["consensus_note"]
        assert not ({"score", "total", "verdict", "good_bad"} & set(sc))
        assert r["validation"]["ok"]
    assert seen_conflict and seen_common


def test_unknown_yongshin_is_not_forced():
    # 일간 강약이 '중간/논쟁' 이면 억부 후보는 비어 있어야 하고, 비교는 '비교 불가'로 남는다
    rng = random.Random(4)
    for _ in range(400):
        p = {k: rnd(rng) for k in ("year", "month", "day", "hour")}
        r = analyze_structure(p)
        if r["layer1"]["support_structure"]["label"] == "중간/논쟁":
            e = r["schools"]["schools"]["eokbu"]
            assert e["yongshin_candidates"] == [] and any("정하지 않음" in c for c in e["counter_evidence"])
            assert any(pr["relation"] == "비교 불가" for pr in r["schools"]["pairs"] if "eokbu" in pr["between"])
            return
    raise AssertionError("중간/논쟁 사례를 찾지 못함")
