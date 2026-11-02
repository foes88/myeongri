"""v9.3 명식 전체 종합 통변(profile-1.0.0) 테스트. 합성 명식만 사용. 중심 구조 선정·유보·학파 충돌 보존·대운/세운 구분·분야 근거 공유 표시·전문용어 비노출을 검증한다."""
import re

import pytest

from app import cases as C
from app.consult import agent, profile as PF, verdict as V
from tools.bias_probe import charts

JARGON = re.compile(r"(?:^|[\s(·])지지|원국|천간|대운|세운|월운|지장간|암장|궁위|월주|연주|일주|시주|일지|월지|연지|시지|본기|중기|여기|십성|통근|득령|투간|격국|용신|조후|억부|"
                    r"식상|재성|관성|인성|비겁|생극제화|식상생재|재생관|관인상생|살인상생|상관견관|군겁쟁재|claim|ruleset|[一-鿿]|\[?[A-Z]\d?-[A-Z0-9-]*\d{3}")
DOMS = ["overall", "wealth", "career", "job_change", "family", "love_marriage"]


def texts(p):
    out = [p["conclusion"]] + p["why"] + p["reality"] + p["conditions"] + [v["text"] for v in p["views"]]
    return out


@pytest.fixture(scope="module")
def answers():
    out = []
    for ci in list(charts(10, seed=5)):
        pre, _ = C.pre_for(ci, [2027])
        a = agent.answer(pre, "종합 상담을 시작합니다", domains_=DOMS, years=[2027, 2028, 2029], depth="detailed")
        out.append((ci, pre, a))
    return out


def test_profile_has_four_parts_and_no_jargon_for_many_charts(answers):
    for ci, pre, a in answers:
        p = a["verdict"]["profile"]
        assert p["version"] == PF.PROFILE_VERSION and p["conclusion"] and p["why"] and p["conditions"]
        assert "internal" not in p
        bad = [(t[:50], m.group()) for t in texts(p) for m in JARGON.finditer(t)]
        assert not bad, (ci.case_id, bad[:3])
        assert not re.search(r"반드시|틀림없|확실히|100%|보장합니다", " ".join(texts(p)))


def test_internal_keeps_rule_and_claim_ids_but_public_view_does_not(answers):
    _, _, a = answers[0]
    inn = a["verdict"]["internal"]["profile"]
    assert inn["version"] == PF.PROFILE_VERSION and "center" in inn and "schools_state" in inn
    from app.consult import verdict as V
    pub = V.public_view(a)
    assert "internal" not in pub["verdict"] and "profile" in pub["verdict"]
    assert "rule_ids" not in str(pub["verdict"]["profile"])


def test_same_input_same_profile(answers):
    ci, pre, a = answers[1]
    again = agent.answer(pre, "종합 상담을 시작합니다", domains_=DOMS, years=[2027, 2028, 2029], depth="detailed")
    assert again["verdict"]["profile"] == a["verdict"]["profile"]


# ---------------------------------------------------------------- 중심 구조: 선정과 유보
def fake_pre(ranks, ys=None):
    sts = [{"name": n, "rank": r, "claim_id": f"L3-{i:03d}", "label": "x", "supporting": [], "counter": []} for i, (n, r) in enumerate(ranks.items(), 1)]
    return {"natal_structure": {"layer3": {"structures": sts}}}


def test_center_picks_most_distinct_and_keeps_both_polarities():
    c = PF.center(fake_pre({"식상생재": 3, "재생관": 1, "상관견관": 3}))
    assert set(c["names"]) == {"식상생재", "상관견관"} and c["support"] == ["식상생재"] and c["tension"] == ["상관견관"] and c["withheld"] is None


def test_center_is_withheld_when_every_structure_is_only_hidden():
    c = PF.center(fake_pre({"식상생재": 1, "재생관": 1}))
    assert c["names"] == [] and c["withheld"] == "all_hidden"
    assert PF.center(fake_pre({}))["withheld"] == "no_structure"


def test_conclusion_text_for_withheld_and_for_center():
    pre = fake_pre({"식상생재": 1})
    pre["natal_structure"].update({"layer4": {"yongshin": {"geukguk": {"groups": []}, "eokbu": {"groups": []}, "johu": {"groups": []}}, "johu": {"month_axis": "한(寒)"}},
                                   "layer1": {"deukryeong": {}}})
    out = PF.build(pre, {}, [], [])
    assert out["withheld"] is True and "한마디로 요약하지 않습니다" in out["conclusion"] and out["internal"]["center"]["withheld"] == "all_hidden"


# ---------------------------------------------------------------- 학파: 일치·충돌·단일·없음
def pre_with(g, e, j):
    return {"natal_structure": {"layer4": {"yongshin": {"geukguk": {"groups": g}, "eokbu": {"groups": e}, "johu": {"groups": j}}, "johu": {"month_axis": "한(寒)"}}}}


def test_schools_agree_conflict_single_none_are_distinguished_and_never_merged():
    assert PF.schools_view(pre_with(["식상"], [], ["식상", "재성"]))["state"] == "agree"
    r = PF.schools_view(pre_with(["비겁"], [], ["식상"]))
    assert r["state"] == "conflict" and "합치지 않고" in r["note"] and len(r["views"]) == 3
    assert PF.schools_view(pre_with([], [], ["식상"]))["state"] == "single"
    assert PF.schools_view(pre_with([], [], []))["state"] == "none"


def test_school_groups_never_leak_god_names_or_hanja():
    r = PF.schools_view(pre_with(["食神", "비겁", "알수없음"], [], []))
    t = " ".join(v["text"] for v in r["views"])
    assert not re.search(r"[一-鿿]", t) and "표현·기술의 기운" in t and "해당하는 기운" in t


# ---------------------------------------------------------------- 분야 근거 공유: 억지로 다르게 만들지 않는다
def blk(dom, name, tone, S, T):
    return {"domain": dom, "name": name, "tone": tone, "scores": {"S": S, "T": T}}


def test_domains_with_the_same_basis_and_same_conclusion_are_explained_not_forced_apart():
    notes = PF.shared_basis_notes([blk("career", "직업·승진운", "opportunity", 3, 0), blk("job_change", "이직·취업운", "opportunity", 3, 0), blk("overall", "종합운", "opportunity", 3, 0)])
    assert len(notes) == 1 and "직업·승진운·이직·취업운" in notes[0] and "종합운" not in notes[0] and "억지로 나누지 않았습니다" in notes[0]


def test_different_scores_or_non_directional_tones_produce_no_shared_note():
    assert PF.shared_basis_notes([blk("career", "직업", "opportunity", 3, 0), blk("job_change", "이직", "opportunity", 2, 0)]) == []
    assert PF.shared_basis_notes([blk("career", "직업", "thin", 1, 0), blk("job_change", "이직", "thin", 1, 0)]) == []


# ---------------------------------------------------------------- 대운·세운 구분
def test_luck_year_names_the_driver_and_marks_luck_change_years(answers):
    ci, pre, a = answers[0]
    from app.consult import synthesis as S
    base = [c for c in pre["chart"]["daeun"]["cycles"]]
    y_change = int(base[2]["start_date"][:4])
    pre2, _ = C.pre_for(ci, [y_change])
    a2 = agent.answer(pre2, "종합 상담을 시작합니다", domains_=["overall", "wealth"], years=[y_change], depth="detailed")
    ly = a2["verdict"]["internal"]["profile"]["luck_year"]
    assert ly and ly[0]["luck_split"] is True
    assert any("10년 큰 흐름이 바뀌어" in w for w in a2["verdict"]["profile"]["why"]) and any("큰 흐름이 바뀌는 해" in c for c in a2["verdict"]["profile"]["conditions"])
    for r in a["verdict"]["internal"]["profile"]["luck_year"]:
        assert set(r["yearly"]).isdisjoint(r["luck"]) and set(r["yearly"]).isdisjoint(r["both"]) and set(r["luck"]).isdisjoint(r["both"])


# ---------------------------------------------------------------- 판단이 달라질 수 있는 조건
def test_ambiguous_birth_time_and_unconfirmed_rules_appear_in_conditions(answers):
    amb = [(ci, a) for ci, pre, a in answers if pre.get("variants_count", 1) > 1]
    for _ci, a in amb:
        assert any("달라질 수 있는 명식" in c or "시각" in c for c in a["verdict"]["profile"]["conditions"])
    assert PF._rule_state(["식상생재"]) in ([], ["식상생재"])     # 규칙 상태 조회가 동작한다


def test_profile_blocks_use_the_first_selected_year():
    pre = fake_pre({"식상생재": 3})
    pre["natal_structure"].update({"layer4": {"yongshin": {"geukguk": {"groups": []}, "eokbu": {"groups": []}, "johu": {"groups": []}}, "johu": {"month_axis": "한(寒)"}}, "layer1": {"deukryeong": {}}})
    blocks = [blk("wealth", "재물운", "opportunity", 3, 0), blk("family", "가족·인간관계운", "thin", 1, 0), blk("career", "직업·승진운", "mixed", 3, 2)]
    out = PF.build(pre, {}, [2027], blocks)
    rt = " ".join(out["reality"])
    assert "2027년에는 재물운에서 방향이 읽힙니다" in rt and "판단을 유보한 분야: 가족·인간관계운" in rt and "하나로 정하지 않은 분야: 직업·승진운" in rt
