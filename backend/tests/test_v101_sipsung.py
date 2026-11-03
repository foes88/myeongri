"""v10.1 십성·궁위 풀이(sipsung-1.0.0) 테스트. 합성 명식만 사용. 설명 문장이 이 사주의 글자 배치에서만 나오는지, 판정과 독립인지, 전문용어·한자·단정이 없는지를 본다."""
import re

import pytest

from app import cases as C
from app.consult import agent, profile as PF, sipsung as SS
from tools.bias_probe import charts

JARGON = re.compile(r"(?:^|[\s(·])지지|원국|천간|대운|세운|월운|지장간|암장|궁위|월주|연주|일주|시주|일지|월지|연지|시지|본기|중기|여기|십성|통근|득령|투간|격국|용신|조후|억부|"
                    r"식상|재성|관성|인성|비겁|생극제화|식상생재|재생관|관인상생|살인상생|상관견관|군겁쟁재|claim|ruleset|[一-鿿]|\[?[A-Z]\d?-[A-Z0-9-]*\d{3}")
FUTURE = re.compile(r"반드시|확실히|틀림없|보장합니다|될 것입니다|합격|승진합니다|오릅니다|생깁니다|\d+\s*%|가능성이 높|운명|팔자가")
DOMS = ["overall", "wealth", "career", "love_marriage", "family"]


def all_text(ss):
    t = [ss["label"], ss["summary"]]
    for s in ss["sections"]:
        t += [s["title"], s["text"]] + s["evidence"]
    t += [p["text"] for p in ss["palaces"]]
    for y in ss["years"]:
        t += [y["theme"], y["link"], y["prep"], y["luck"]]
    return t


# ---------------------------------------------------------------- 가중치(손계산)
def test_weights_for_a_hand_computed_chart():
    pil = {"year": "甲子", "month": "甲子", "day": "甲子", "hour": "甲子"}     # 일간 甲. 다른 천간 甲×3=比肩, 지지 子의 숨은 글자 癸=正印
    tot, where = SS._weights(pil)
    assert tot["比肩"] == 6 and tot["正印"] == 2 + 3 + 2 + 2 == 9 and sum(tot.values()) == 15
    assert [g for g, how, w in where["month"]] == ["比肩", "正印"] and where["month"][1][2] == 3        # 태어난 달의 지지는 가중 3
    assert SS.dominant(tot) == ["正印"]                                                              # 둘째(6)는 첫째(9)의 70%(6.3) 미만


def test_dominant_needs_enough_weight_and_a_close_second():
    base = {g: 0.0 for g in SS.G}
    assert SS.dominant(base | {"正官": 2.5}) == []                                  # 앞서는 기운이 없다
    assert SS.dominant(base | {"正官": 5, "偏印": 3.4}) == ["正官"]
    assert SS.dominant(base | {"正官": 5, "偏印": 3.6}) == ["正官", "偏印"]
    assert SS.dominant(base | {"正官": 3, "偏印": 3}) == ["正官", "偏印"]


def test_hour_unknown_is_handled():
    pf = SS.profile({"year": "壬申", "month": "辛亥", "day": "甲子", "hour": None}, "male")
    assert pf and len(pf["palaces"]) == 3 and all("말년" not in p["area"] for p in pf["palaces"])
    assert SS.profile({"year": "壬申", "month": None, "day": "甲子", "hour": None}) is None


# ---------------------------------------------------------------- 시기별 주제
def seg(luck, sewun):
    return {"segments": [{"from": "2030-01-01", "to": "2030-12-31", "luck": luck, "sewun": sewun}]}


def test_year_theme_names_the_year_god_and_links_to_the_natal_balance(monkeypatch):
    import app.consult.facts as FA
    monkeypatch.setattr(FA, "_days", lambda s: 365)
    pil = {"year": "甲子", "month": "甲子", "day": "甲子", "hour": "甲子"}          # 比肩이 많은 사주(같은 기운 묶음 6)
    r = SS.year_themes(pil, {2030: seg("乙丑", "丙寅"), 2031: seg("乙丑", "癸酉")}, [2030, 2031])
    assert r[0]["theme"].startswith("2030년은 표현·") is False and "재능과 표현" in r[0]["theme"]            # 丙 = 일간 甲이 낳는 食神
    assert "이미 이 기운이 많아" in r[1]["link"] or "타고난 사주" in r[1]["link"]
    assert r[1]["theme"].count("2031년") == 1 and "배움과 자격" in r[1]["theme"]                                # 癸 = 正印
    r2 = SS.year_themes({"year": "甲子", "month": "甲子", "day": "甲子", "hour": "甲子"}, {2030: seg("乙丑", "庚申")}, [2030])
    assert "거의 없어서" in r2[0]["link"] and "압박과 도전" in r2[0]["theme"]                                  # 庚 = 일간 甲을 극하는 七殺, 타고난 사주에는 거의 없음


def test_themes_do_not_judge_good_or_bad():
    for g in SS.G:
        assert not re.search(r"좋은 운|나쁜 운|길한|흉|행운|불운", SS.G[g]["year"] + SS.G[g]["prep"])


# ---------------------------------------------------------------- 실제 엔진(합성 명식)
@pytest.fixture(scope="module")
def answers():
    out = []
    for ci in list(charts(12, seed=21)):
        pre, _ = C.pre_for(ci, [2027])
        a = agent.answer(pre, "종합 상담을 시작합니다", domains_=DOMS, years=[2027, 2028, 2029], depth="detailed")
        out.append((ci, pre, a))
    return out


def test_texts_have_no_jargon_hanja_or_fortune_claims(answers):
    for ci, pre, a in answers:
        ss = a["verdict"]["profile"]["sipsung"]
        for t in all_text(ss):
            assert not JARGON.search(t), (ci.case_id, t, JARGON.search(t).group())
            assert not FUTURE.search(t), (ci.case_id, t)
        assert "원전 원문과의 대조는 아직 하지 않았" in ss["label"] and "경향" in ss["label"]


def test_every_statement_is_a_polite_tendency_without_absolutes():
    for g, d in SS.G.items():
        for k in ("tendency", "career", "money", "relation"):
            assert d[k].endswith("다."), (g, k)
            assert not re.search(r"반드시|항상|절대|틀림없|무조건|100%", d[k]), (g, k)
        assert d["tendency"].count("경향") + d["tendency"].count("편") >= 1 or "중시" in d["tendency"], g


def test_output_is_specific_to_the_chart_not_one_generic_text(answers):
    tend = {a["verdict"]["profile"]["sipsung"]["sections"][0]["text"] for _, _, a in answers}
    pal = {tuple(p["text"] for p in a["verdict"]["profile"]["sipsung"]["palaces"]) for _, _, a in answers}
    assert len(tend) >= 4 and len(pal) >= 10          # 12개 명식에서 성향 문장이 4종 이상, 자리별 설명은 거의 전부 다르다


def test_sipsung_has_no_influence_on_any_judgement(answers, monkeypatch):
    ci, pre, a0 = answers[0]
    ys = [2027, 2028, 2029]
    run = lambda: agent.answer(pre, "종합 상담을 시작합니다", domains_=DOMS, years=ys, depth="detailed")
    core = lambda a: {"blocks": a["verdict"].get("blocks"), "detail": a["verdict"].get("detail"), "period": a["verdict"].get("period"), "tones": a["verdict"]["internal"]["tones"],
                      "scores": a["verdict"]["internal"]["scores"], "judge": a["verdict"]["internal"]["judge"]}
    base = core(run())
    monkeypatch.setattr(SS, "build", lambda *a, **k: None)
    assert core(run()) == base                                        # 십성 풀이를 없애도 분야 판정·점수·문장이 같다


def test_conclusion_uses_dominant_group_when_no_single_structure_leads():
    pre = {"gender": "male", "natal_structure": {"pillars": {"year": "壬申", "month": "辛亥", "day": "甲子", "hour": "乙亥"},
           "layer3": {"structures": [{"name": "식상생재", "rank": 1, "claim_id": "L3-001", "label": "x", "supporting": [], "counter": []}]},
           "layer4": {"yongshin": {"geukguk": {"groups": []}, "eokbu": {"groups": []}, "johu": {"groups": []}}, "johu": {"month_axis": "한난 중간(봄)", "direction_elements": [], "element_tally": {}}},
           "layer1": {"deukryeong": {}}}}
    out = PF.build(pre, {}, [], [])
    assert out["internal"]["center"]["withheld"] == "all_hidden"
    assert out["conclusion"] == "이 사주는 ‘남과 다른 관심을 파고드는’ 쪽으로 힘이 모이는 모습으로 읽힙니다."
    assert out["sipsung"]["sections"][0]["key"] == "tendency" and out["sipsung"]["years"] == []


def test_internal_has_weights_and_year_gods_but_public_does_not(answers):
    from app.consult import verdict as V
    ci, pre, a = answers[0]
    inn = a["verdict"]["internal"]["profile"]["sipsung"]
    assert set(inn["weights"]) == set(SS.G) and inn["years"][0]["year_god"] in SS.G
    pub = V.public_view(a)["verdict"]["profile"]["sipsung"]
    assert "internal" not in pub and "weights" not in str(pub) and "year_god" not in str(pub)


def test_same_input_same_output(answers):
    ci, pre, a = answers[1]
    again = agent.answer(pre, "종합 상담을 시작합니다", domains_=DOMS, years=[2027, 2028, 2029], depth="detailed")
    assert again["verdict"]["profile"]["sipsung"] == a["verdict"]["profile"]["sipsung"]
