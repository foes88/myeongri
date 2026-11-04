"""v11.0 '현실에서 생각해 볼 점' 근거 연결 테스트. 조언 문장은 기존 THINK 문장을 재사용하며(새 조언 없음), 톤·판정·헤드라인은 바뀌지 않는다. 합성 입력만 사용(예측 정확성과 무관)."""
import pytest

from app import cases as C
from app.consult import agent, verdict as V
from tools.bias_probe import charts
from tools.think_compare import drivers

DOMS = ["overall", "wealth", "career", "business"]
YEARS = [2027, 2028, 2029]
ALL_THINK = {s for d in V.THINK.values() for lst in d.values() for s in lst}
PROMISE = ("반드시", "확실히", "성공할", "실패", "보장", "틀림없")


def t_of(**kw):
    base = {"sup_up": [], "ten_up": [], "sup_part": [], "ten_part": [], "sup_pers": [], "ten_pers": [], "natal_support": [], "natal_tension": []}
    base.update(kw)
    return base


def test_advice_sentences_are_existing_think_sentences_only():
    for dom, adv in V.STRUCT_ADVICE.items():
        for n, (d, tone, i) in adv.items():
            assert V.THINK[d][tone][i] in ALL_THINK                                       # 새 조언 문장을 만들지 않았다


def test_similar_charts_with_one_condition_changed_get_matching_advice():
    """다른 조건이 같고 한 구조만 다르면, 조언도 그 구조에 맞게 바뀐다."""
    a = V.think_for("wealth", "cautious", t_of(ten_up=["군겁쟁재"]))
    b = V.think_for("wealth", "opportunity", t_of(sup_up=["식상생재"]))
    assert "이익을 나누거나 다투기 쉬운 흐름" in a[0] and "문서로 분명히" in a[0]
    assert "능력이 수입으로 이어지는 흐름" in b[0] and "수입으로 연결할 방법" in b[0]
    c = V.think_for("career", "opportunity", t_of(sup_up=["재생관"]))
    d = V.think_for("career", "opportunity", t_of(sup_up=["관인상생"]))
    assert c != d and "실적과 평판" in c[0] and "윗사람이나 선배" in d[0]


def test_year_change_leads_over_partial_persistent_and_natal_with_the_right_wording():
    t = t_of(sup_up=["식상생재"], sup_part=["군겁쟁재"], natal_support=["식상생재"])
    out = V.think_for("wealth", "mixed", t)
    assert out[0].startswith("이 해에 ‘") and len(out) == 2 and "이 해 일부 기간에" in out[1]
    assert V.think_for("wealth", "opportunity", t_of(natal_support=["식상생재"]))[0].startswith("타고난 사주에 ‘")
    assert V.think_for("wealth", "opportunity", t_of(sup_pers=["식상생재"]))[0].startswith("이어지는 10년 큰 흐름에서 ‘")


def test_falls_back_to_the_existing_tone_advice_when_nothing_links_and_for_limited_tones():
    assert V.think_for("wealth", "opportunity", t_of()) == V.THINK["wealth"]["opportunity"][:2]       # 연결할 근거가 없으면 기존 조언
    assert V.think_for("wealth", "thin", t_of(sup_up=["식상생재"])) == V.THINK["wealth"]["thin"]          # 근거 부족 톤은 범위 제한 문장 그대로
    assert V.think_for("wealth", "quiet", t_of(natal_support=["식상생재"])) == V.THINK["wealth"]["quiet"]
    assert V.think_for("love_marriage", "cautious", t_of(ten_up=["군겁쟁재"])) == V.THINK["love_marriage"]["cautious"]   # 구조 연결이 없는 분야는 그대로
    assert V.think_for("wealth", "opportunity", t_of(sup_up=["재생관"])) == V.THINK["wealth"]["opportunity"][:2]  # 이 분야에 맞는 조언이 없는 구조는 연결하지 않는다(억지 연결 금지)


def test_think_change_does_not_alter_tone_headline_story_or_why(monkeypatch):
    ci = next(iter(charts(1, seed=3)))
    pre, _ = C.pre_for(ci, [2027])
    new = agent.answer(pre, "종합 상담을 시작합니다", domains_=DOMS, years=YEARS, depth="detailed")["verdict"]
    monkeypatch.setattr(V, "think_for", lambda dom, tone, t: list(V.THINK.get(dom, {}).get(tone, V.THINK["overall"]["thin"]))[:2])
    old = agent.answer(pre, "종합 상담을 시작합니다", domains_=DOMS, years=YEARS, depth="detailed")["verdict"]

    def strip(v):
        out = dict(v)
        out["detail"] = {y: {"blocks": [{k: x for k, x in b.items() if k != "think"} for b in d["blocks"]]} for y, d in v["detail"].items()}
        out["profile"] = {k: x for k, x in v["profile"].items() if k not in ("story",)}
        return out
    assert strip(new)["detail"] == strip(old)["detail"] and new["period"] == old["period"] and new["months"] == old["months"]
    changed = sum(1 for y in new["detail"] for b, o in zip(new["detail"][y]["blocks"], old["detail"][y]["blocks"]) if b["think"] != o["think"])
    assert changed > 0                                                                       # 실제로 근거에 맞게 바뀐 블록이 있다


@pytest.mark.parametrize("seed", [3, 7])
def test_every_linked_advice_names_a_structure_that_is_really_a_driver_of_that_block(seed):
    for ci in charts(4, seed=seed):
        pre, _ = C.pre_for(ci, [2027])
        a = agent.answer(pre, "종합 상담을 시작합니다", domains_=DOMS, years=YEARS, depth="detailed")
        for y in YEARS:
            for b in a["verdict"]["detail"][str(y)]["blocks"]:
                dr, t = drivers(pre, b["domain"], y, a)
                assert 1 <= len(b["think"]) <= 2 and not any(w in x for x in b["think"] for w in PROMISE)
                names = set(dr["year_changes"]) | set(dr["partial"]) | set(dr["persist"]) | set(dr["natal"])
                for x in b["think"]:
                    if "쪽 변화가 있어," in x or "쪽이 이어져," in x or "쪽이 있어," in x:
                        shorts = {n for n in names if V.S.STRUCT[n]["short"] in x}
                        assert shorts, (b["domain"], y, x, names)                           # 연결 문구의 구조가 실제 근거 목록에 있다
                    # 조언 본문은 기존 THINK 문장 중 하나로 끝난다(재사용)
                    assert any(x.endswith(s) for s in ALL_THINK), x
