"""Mingli-Graph 1·2층: 구조·경계·모호성·금지 표현 검사."""
import random

from app.mingli import analyze_chart_variants, analyze_structure
from app.mingli.evidence import ClaimNode, EvidenceGraph
from app.mingli.rules import RULES
from app.astro_core import calculate_chart

STEMS, BR = "甲乙丙丁戊己庚辛壬癸", "子丑寅卯辰巳午未申酉戌亥"
SAMPLE = {"year": "庚申", "month": "甲寅", "day": "甲辰", "hour": "丙寅"}  # 가상 명식(구조 시험용)


def rnd_pillar(rng):
    i = rng.randrange(60)
    return STEMS[i % 10] + BR[i % 12]


def test_sample_layer1_facts():
    r = analyze_structure(SAMPLE)
    l1 = r["layer1"]
    assert l1["deukryeong"] == {"by_bongi": "득령", "by_season_element": "득령", "agree": True, "claims": l1["deukryeong"]["claims"]}
    assert [h["role"] for h in l1["wolryeong"]["hidden"]] == ["본기", "중기", "여기"]
    assert l1["tonggeun"]["day"]["strict_level"] == "강"  # 甲 이 寅 본기에 같은 간으로 통근
    assert any(t["revealed_at"] == ["month"] for t in l1["tugan"]["month_branch_hidden"] if t["stem"] == "甲")
    assert r["validation"]["ok"]


def test_sample_layer2_relations_exist_but_are_not_asserted_as_damage():
    r = analyze_structure(SAMPLE)
    kinds = {x["relation_type"] for x in r["layer2"]["relations"]}
    assert {"충", "공합(拱合)·논쟁", "방합(부분)", "합충 경합"} <= kinds
    for x in r["layer2"]["relations"]:
        assert x["existence"] is True
        if x["relation_type"] == "충":
            assert x["damages_hidden_stems"] == "unconfirmed"
    # 뿌리 지지가 충에 걸린 사실은 반대 근거로 남지만 손상을 확정하지 않는다
    node = next(n for n in r["graph"]["nodes"] if n["claim_id"] == r["layer1"]["tonggeun"]["year"]["claim_id"])
    assert any("확정하지 않음" in c for c in node["counter_evidence"])


def test_silryeong_case_and_school_disagreement_is_recorded():
    r = analyze_structure({"year": "丙子", "month": "壬申", "day": "甲子", "hour": "甲戌"})
    d = r["layer1"]["deukryeong"]
    assert d["by_bongi"] == "부분득령(논쟁)" or d["by_bongi"] == "실령 후보"
    # 본기 기준(庚=관성)은 득령이 아니지만 계절 오행(金→水→木)은 월지 金이 일간 木을 생하지 않으므로 둘 다 실령 계열
    assert d["by_season_element"] == "실령 후보"
    assert r["validation"]["ok"]


def test_partial_deukryeong_is_flagged_as_school_conflict():
    # 戌월 일간 丁: 본기 戊(식상)는 돕지 않고 여기 丁만 비겁 → 본기 기준 '부분득령(논쟁)', 계절 오행 기준 '실령 후보'
    r = analyze_structure({"year": "癸卯", "month": "甲戌", "day": "丁卯", "hour": "丁未"})
    d = r["layer1"]["deukryeong"]
    assert d["by_bongi"] == "부분득령(논쟁)" and d["by_season_element"] == "실령 후보" and not d["agree"]
    assert any(e["type"] == "conflicts" and {e["from"], e["to"]} == set(d["claims"]) for e in r["graph"]["edges"])


def test_hwahwa_is_never_asserted_and_conditions_recorded():
    r = analyze_structure({"year": "丙寅", "month": "己未", "day": "甲子", "hour": "乙亥"})  # 甲己 인접, 未월 土
    hw = [x for x in r["layer2"]["relations"] if x["relation_type"] == "합화 후보"]
    assert hw and all("성립" not in x["candidate_effect"] or "불성립" in x["candidate_effect"] for x in hw)
    assert hw[0]["candidate_effect"] == "합화 논쟁/보류"  # 일간 합화 허용 여부가 학파 논쟁
    assert any(c["name"].startswith("일간 합화") and c["status"] == "contested" for c in hw[0]["conditions"])


def test_non_adjacent_stem_hap_has_no_hwa_basis():
    r = analyze_structure({"year": "甲戌", "month": "丙寅", "day": "丁卯", "hour": "己酉"})
    hw = [x for x in r["layer2"]["relations"] if x["relation_type"] == "합화 후보"]
    assert hw and hw[0]["candidate_effect"] == "합화 불성립 근거 있음" and "인접" in hw[0]["not_satisfied"]


def test_hour_unknown_works():
    r = analyze_structure({"year": "庚申", "month": "甲寅", "day": "甲辰"})
    assert r["validation"]["ok"] and not r["layer1"]["hour_known"]


def test_random_charts_never_break_invariants():
    rng = random.Random(3)
    banned = ("반드시", "확정적으로 흉", "손상되었다", "합화가 성립한다")
    for _ in range(300):
        p = {k: rnd_pillar(rng) for k in ("year", "month", "day", "hour")}
        r = analyze_structure(p)
        assert r["validation"]["ok"], (p, r["validation"]["problems"][:2])
        for n in r["graph"]["nodes"]:
            text = " ".join([n["interpretation_summary"], n["status"]] + n["supporting_evidence"] + n["counter_evidence"])
            assert not any(b in text for b in banned), text
            assert n["rule_id"] in RULES and n["source_references"] and n["uncertainty"]
        for x in r["layer2"]["relations"]:
            assert x["existence"] and x["conditions"] is not None


def test_validator_flags_missing_evidence():
    g = EvidenceGraph()
    base = dict(chart_variant_id="v1", school_id="common", supporting_evidence=["a"], counter_evidence=[], applicability=[],
                exclusions=[], conflicting_claims=[], source_references=RULES["MG-L2-CHUNG"]["sources"], uncertainty="u", interpretation_summary="s")
    g.add(ClaimNode(claim_id="X-1", rule_id="MG-L2-CHUNG", **base))  # 반대 근거 누락 + 검토 표시 없음
    g.add(ClaimNode(claim_id="X-2", rule_id="NOPE", **base | {"counter_evidence": ["b"]}))
    g.add(ClaimNode(claim_id="X-3", rule_id="MG-L2-CHUNG", **base | {"supporting_evidence": [], "counter_checked": True,
                                                                      "conflicting_claims": ["X-99"]}))
    codes = {(p["claim_id"], p["code"]) for p in g.validate()}
    assert ("X-1", "MISSING_COUNTER_EVIDENCE") in codes and ("X-2", "UNKNOWN_RULE_ID") in codes
    assert ("X-3", "MISSING_SUPPORTING_EVIDENCE") in codes and ("X-3", "DANGLING_CONFLICT") in codes


def test_rules_record_classical_verification_status_from_verification_file():
    for rid, r in RULES.items():
        assert r["sources"] and all(s["classical_verification"] == r["classical_status"] for s in r["sources"]), rid
        assert r["classical_status"] in ("text_confirmed", "location_confirmed", "implementer_convention", "pending")


def test_variants_are_analyzed_separately():
    chart = calculate_chart(year=2000, month=1, day=1, hour=19, minute=25, gender="male").to_dict()  # 가상 입력
    out = analyze_chart_variants(chart)
    assert len(out["analyses"]) == 2 and out["variant_differences"]
    assert {a["pillars"]["hour"] for a in out["analyses"]} == {"壬戌", "辛酉"}
    assert out["verification"]["status"] != "V1"
