"""v6.6 고전 대조에서 발견한 구현 오류·프로필의 회귀 테스트(가상 명식)."""
import pytest

from app.mingli import analyze_structure
from app.mingli.evidence import EvidenceGraph
from app.mingli.layer1 import TONGGEUN_PROFILES, analyze_layer1, twelve_stage_root
from app.mingli.layer2 import HAE, HYUNG_PROFILES, CHUNG, YUKHAP, analyze_layer2, month_tier, stem_gap


def rels(p, kind, **kw):
    return [x for x in analyze_structure(p, **kw)["layer2"]["relations"] if x["relation_type"] == kind]


def cond(rel, prefix):
    return next(c for c in rel["conditions"] if c["name"].startswith(prefix))


# ---- 天干合: 間隔 (沈孝瞻 論十干合而不合) ----
def test_stem_gap_blocks_hap_and_is_recorded():
    p = {"year": "甲子", "month": "庚午", "day": "己巳", "hour": "丙寅"}  # 甲 庚 己: 사이의 庚(金)이 甲(木)을 극함
    hap = rels(p, "천간합")
    assert len(hap) == 1 and hap[0]["pillars"] == ["year", "day"]
    assert "間隔" in hap[0]["candidate_effect"] and cond(hap[0], "사이 글자")["status"] == "unsatisfied"
    hwa = rels(p, "합화 후보")[0]
    assert hwa["candidate_effect"] == "합화 불성립 근거 있음" and "사이 글자가 합 상대를 극하지 않음(間隔)" in hwa["not_satisfied"]


def test_far_pair_without_blocker_is_not_gap_and_adjacent_has_no_gap():
    far = {"year": "甲子", "month": "丙寅", "day": "己巳", "hour": "壬申"}  # 사이의 丙(火)은 甲·己를 극하지 않음 → 間隔 아님, 다만 원격
    h = rels(far, "천간합")[0]
    assert cond(h, "사이 글자")["status"] == "satisfied" and cond(h, "인접")["status"] == "unsatisfied"
    assert "間隔" not in h["candidate_effect"]
    adj = {"year": "甲子", "month": "己巳", "day": "丙寅", "hour": "壬申"}
    a = rels(adj, "천간합")[0]
    assert cond(a, "사이 글자")["note"] == "인접이라 해당 없음" and stem_gap(["year", "month"], {"year": "甲", "month": "己"}, "year", "month") == []


def test_stem_gap_helper_uses_control_relation():
    st = {"year": "甲", "month": "庚", "day": "己", "hour": "丙"}
    pos = ["year", "month", "day", "hour"]
    assert stem_gap(pos, st, "year", "day") == ["month"]
    assert stem_gap(pos, dict(st, month="丙"), "year", "day") == []   # 火는 木·土를 극하지 않음


# ---- 合化: 월령 得時乘令 (沈孝瞻 論外格用舍) ----
@pytest.mark.parametrize("el,mb,expect", [("木", "辰", "season"), ("木", "寅", "season"), ("木", "亥", "secondary"), ("木", "未", "secondary"),
                                          ("火", "未", "season"), ("火", "寅", "secondary"), ("水", "丑", "season"), ("水", "辰", "secondary"),
                                          ("金", "戌", "season"), ("土", "辰", "season"), ("木", "午", None), ("土", "子", None)])
def test_month_tier_table(el, mb, expect):
    assert month_tier(el, mb) == expect


def test_hwa_month_condition_uses_season_not_only_element():
    p = {"year": "甲辰", "month": "壬辰", "day": "丁卯", "hour": "乙巳"}  # 丁壬合, 化神 木, 월지 辰(봄 → 得時). 예전 구현은 辰을 土로만 보아 '월령 불성립'
    h = rels(p, "합화 후보")[0]
    c = cond(h, "월령이")
    assert c["status"] == "satisfied" and "得時" in c["note"]
    assert h["candidate_effect"] != "합화 불성립 근거 있음"
    water = {"year": "甲子", "month": "辛丑", "day": "丙子", "hour": "壬辰"}   # 丙辛合 水, 丑월(겨울)
    assert cond(rels(water, "합화 후보")[0], "월령이")["status"] == "satisfied"
    neg = {"year": "甲寅", "month": "己卯", "day": "甲戌", "hour": "丙寅"}      # 甲己합 土, 卯월 → 뒷받침 없음
    assert cond(rels(neg, "합화 후보")[0], "월령이")["status"] == "unsatisfied"


# ---- 害: 六合의 상대를 沖하는 글자 (任氏曰) ----
def test_hae_table_equals_derivation_from_yukhap_and_chung():
    chong = {}
    for k in CHUNG:
        a, b = tuple(k)
        chong[a], chong[b] = b, a
    derived = set()
    for k in YUKHAP:
        a, b = tuple(k)
        derived |= {frozenset((a, chong[b])), frozenset((b, chong[a]))}
    assert derived == set(HAE)


# ---- 刑 프로필: 自刑 (任氏曰 俗謬) ----
def test_hyung_profile_no_self_drops_self_punishment():
    p = {"year": "甲午", "month": "丙午", "day": "戊子", "hour": "丁巳"}  # 午午 자형
    g1, g2 = EvidenceGraph(), EvidenceGraph()
    common = analyze_layer2(p, g1, "v1", "modern_6", "common")
    no_self = analyze_layer2(p, g2, "v1", "modern_6", "no_self")
    assert any(r["relation_type"] == "자형" for r in common["relations"]) and not any(r["relation_type"] == "자형" for r in no_self["relations"])
    assert no_self["hyung_profile"] == "no_self" and no_self["profile_conflicts"][0]["result_in_this_run"] == "제외됨"
    assert common["profile_conflicts"][0]["result_in_this_run"] == "자형 후보로 기록"
    with pytest.raises(ValueError):
        analyze_layer2(p, EvidenceGraph(), "v1", "modern_6", "nope")
    assert set(HYUNG_PROFILES) == {"common", "no_self"}


def test_default_profiles_keep_existing_behavior():
    r = analyze_structure({"year": "庚申", "month": "甲寅", "day": "甲辰", "hour": "丙寅"})
    assert r["layer1"]["tonggeun_profile"] == "position_role" and r["layer2"]["hyung_profile"] == "common" and r["layer2"]["pa_profile"] == "modern_6"
    assert r["layer1"]["tonggeun"]["day"]["strict_level"] == "강" and r["validation"]["ok"]


# ---- 通根: 십이운성 프로필 (沈孝瞻) ----
def test_tonggeun_twelve_stage_profile_matches_shen_xiaozhan_examples():
    assert twelve_stage_root("甲", "亥") == (3, "장생") and twelve_stage_root("甲", "寅") == (3, "건록") and twelve_stage_root("甲", "卯") == (3, "제왕(양인)")
    assert twelve_stage_root("甲", "未")[0] == 1 and twelve_stage_root("丙", "戌")[0] == 1       # 甲逢未, 丙逢戌: 墓庫(輕根)
    assert twelve_stage_root("乙", "戌")[0] == 0 and twelve_stage_root("丁", "丑")[0] == 0       # 戌中無木, 丑中無火: 인정 안 함
    assert twelve_stage_root("乙", "辰")[0] == 1 and twelve_stage_root("丁", "未")[0] == 1       # 餘氣
    assert twelve_stage_root("乙", "午") == (1, "음간 장생(明根)") and twelve_stage_root("丁", "酉")[0] == 1   # 陰長生은 重根 아님
    assert set(TONGGEUN_PROFILES) == {"position_role", "twelve_stage"}


def test_tonggeun_profiles_differ_where_the_sources_differ():
    p = {"year": "癸亥", "month": "丙午", "day": "甲子", "hour": "戊辰"}  # 甲: 亥(長生)에 있으나 亥中 甲은 중기
    a = analyze_layer1(p, EvidenceGraph(), "v1", None, "position_role")["tonggeun"]["day"]
    b = analyze_layer1(p, EvidenceGraph(), "v1", None, "twelve_stage")["tonggeun"]["day"]
    assert a["strict_level"] == "중" and b["strict_level"] == "강" and b["roots"][0]["type"] == "십이운성(沈孝瞻)"
    with pytest.raises(ValueError):
        analyze_layer1(p, EvidenceGraph(), "v1", None, "nope")
