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


# ---------------------------------------------------------------- v9.4 계절 균형(한난) 점검
def pre_johu(axis, need, tally):
    """tally: {오행: 개수} → 그 개수만큼 해당 오행 글자를 가진 가짜 네 기둥으로 바꿔 준다(점검은 네 기둥 글자를 센다)."""
    ch = {"木": "甲", "火": "丙", "土": "戊", "金": "庚", "水": "壬"}
    letters = [ch[e] for e, n in tally.items() for _ in range(n)]
    pil = {"year": "".join(letters[:2]) or None, "month": "".join(letters[2:4]) or None, "day": "".join(letters[4:6]) or None, "hour": "".join(letters[6:8]) or None}
    return {"natal_structure": {"pillars": pil, "layer4": {"johu": {"month_axis": axis, "direction_elements": need, "element_tally": tally}}}}


def test_johu_check_states_and_plain_words():
    miss = PF.johu_check(pre_johu("한(寒)", ["火"], {"水": 3, "土": 2}))
    assert miss["state"] == "missing" and "추운 계절" in miss["text"] and "속에 숨어 있을 수는 있습니다" in miss["text"] and "불" in miss["text"]
    ok = PF.johu_check(pre_johu("난(熱)", ["水"], {"火": 3, "水": 1}))
    assert ok["state"] == "present" and "더운 계절" in ok["text"] and "식혀 주는" in ok["text"]
    part = PF.johu_check(pre_johu("한(寒)", ["火", "木"], {"木": 1}))
    assert part["state"] == "partial"
    assert PF.johu_check(pre_johu("한난 중간(봄)", [], {"木": 2})) is None          # 치우치지 않은 계절은 점검하지 않는다
    for r in (miss, ok, part):
        assert not re.search(r"[一-鿿]", r["text"])


def test_johu_check_never_changes_tones_and_always_carries_its_limit(answers):
    for ci, pre, a in answers:
        p = a["verdict"]["profile"]
        jc = a["verdict"]["internal"]["profile"]["johu_check"]
        if jc:
            assert any("계절 균형" in c and "참고 수준" in c for c in p["conditions"])
            assert any("계절" in w and "기운" in w for w in p["why"])
        else:
            assert not any("계절 균형" in c for c in p["conditions"])
    # 판정(S/T)은 점검과 무관하다: judge 입력에 한난 점검이 없다
    import inspect
    from app.consult import judge
    assert "johu" not in inspect.getsource(judge).lower().replace("johu_", "x")


# ---------------------------------------------------------------- 첫 장면(이야기 카드)
def story_pre(pillars, axis, need):
    return {"natal_structure": {"pillars": pillars, "layer4": {"johu": {"month_axis": axis, "direction_elements": need, "element_tally": {}}}}}


def seg(luck, sewun, days=365):
    return {"segments": [{"from": "2030-01-01", "to": "2030-12-31", "luck": luck, "sewun": sewun}]}


def test_shape_counts_all_eight_letters_including_the_day_master():
    sh = PF.shape_of({"year": "壬申", "month": "辛亥", "day": "甲子", "hour": "乙亥"})
    assert sh == {"木": 2, "火": 0, "土": 4, "金": 0, "水": 2} and sum(sh.values()) == 8
    assert sum(PF.shape_of({"year": "壬申", "month": "辛亥", "day": "甲子", "hour": None}).values()) == 6        # 시주를 모르면 여섯 글자


def test_story_image_uses_day_master_and_birth_season_and_says_it_is_a_metaphor(monkeypatch):
    import app.consult.facts as FA
    monkeypatch.setattr(FA, "_days", lambda s: 365)
    st = PF.story(story_pre({"year": "壬申", "month": "辛亥", "day": "甲子", "hour": "乙亥"}, "한(寒)", ["火"]), {2030: seg("丁卯", "庚午")}, [2030])
    assert st["image"] == "겨울에 선 큰 나무" and st["need"] == ["불"]
    assert st["timeline"] == [{"year": 2030, "luck_hit": True, "year_hit": True}]
    text = " ".join(st["beats"])
    assert "불의 기운이 필요" in text and "겉으로 드러나 있지 않습니다" in text and "10년 큰 흐름은 필요한 불의 기운을 가져옵니다" in text and "2030년" in text
    assert "비유" in st["note"] and "성격이나 일어날 일을 말하는 것이 아니며" in st["note"] and "궁통보감" in st["note"]
    assert not re.search(r"[一-鿿]", " ".join(st["beats"]) + st["image"])


def test_story_marks_years_when_need_does_not_arrive_and_never_claims_events(monkeypatch):
    import app.consult.facts as FA
    monkeypatch.setattr(FA, "_days", lambda s: 365)
    st = PF.story(story_pre({"year": "丙午", "month": "丁巳", "day": "庚午", "hour": "庚申"}, "난(熱)", ["水"]), {2027: seg("丁卯", "丁未"), 2028: seg("丁卯", "戊申"), 2029: seg("丁卯", "壬子")}, [2027, 2028, 2029])
    assert [r["luck_hit"] for r in st["timeline"]] == [False] * 3 and [r["year_hit"] for r in st["timeline"]] == [False, False, True]
    assert "큰 흐름에는 필요한 물의 기운이 들어 있지 않습니다" in " ".join(st["beats"])
    assert not re.search(r"반드시|틀림없|성공|실패|좋은 일|나쁜 일|합격|이직합니다", " ".join(st["beats"]))


def test_story_skips_need_part_in_balanced_seasons_and_returns_none_without_day_pillar():
    st = PF.story(story_pre({"year": "壬申", "month": "乙卯", "day": "甲子", "hour": None}, "한난 중간(봄)", []), {}, [])
    assert st["image"] == "봄에 선 큰 나무" and st["need"] == [] and st["timeline"] == [] and len(st["beats"]) == 2
    assert PF.story(story_pre({"year": "壬申", "month": "乙卯", "day": None, "hour": None}, "한(寒)", ["火"]), {}, []) is None


def test_topic_particle_follows_final_consonant():
    assert PF._topic("쇠") == "는" and PF._topic("불") == "은" and PF._topic("흙") == "은" and PF._topic("물") == "은"
    st = PF.story(story_pre({"year": "丙午", "month": "丁巳", "day": "丙午", "hour": "丙午"}, "한난 중간(봄)", []), {}, [])
    assert "나무·흙·쇠·물은 겉으로 드러나지 않습니다" in " ".join(st["beats"])      # 마지막 낱말(물)에 받침이 있어 '은'
    st2 = PF.story(story_pre({"year": "甲子", "month": "乙丑", "day": "甲寅", "hour": "乙卯"}, "한난 중간(봄)", []), {}, [])
    assert "불·쇠는 겉으로 드러나지 않습니다" in " ".join(st2["beats"])      # 마지막 낱말(쇠)은 받침이 없어 '는' 
