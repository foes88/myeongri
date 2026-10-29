"""v6.9 해석 종합 계층 품질 테스트. 합성 명식(실제 출생 정보 아님)만 사용한다.

기준: 이해 가능, 명식별 차이, 이유 설명, 문장 반복 없음, 반대 근거 노출, 고전/현대 구분, 실제 명식 조건과 일치.
"""
import re

import pytest

from app.consult import agent, synthesis
from app.evaluation import dataset as DS

CONFLICT = {"year": "丁巳", "month": "乙未", "day": "戊寅", "hour": "庚戌"}
SPARSE = {"year": "己未", "month": "甲寅", "day": "丙寅", "hour": "己未"}
OLD_STYLE = ["식상생재 약함", "중기 암장 있음", "정관격 성격 후보", "금 기운 부족하므로 승진운 약함", "(약함(중기·여기 암장))"]
SENT_KEYS = ("headline", "favorable", "cautions", "uncertainty")


def run(pillars=None, years=(2030,), domains=("overall", "wealth", "career"), depth="detailed", cycles_first_year=2000):
    spec = DS.Spec(pillars or DS.BASE, domains=tuple(domains), years=tuple(years), cycles_first_year=cycles_first_year)
    pre = DS.pre_of(spec)
    ans = agent.answer(pre, "질문", domains_=list(domains), years=list(years), depth=depth)
    return pre, ans, ans["synthesis"]


def sentences(syn):
    out = [x for k in SENT_KEYS for x in syn[k]]
    f = syn["period_flow"]
    out += [x for v in (f.get("year_sentences") or {}).values() for x in v] + (f.get("sentences") or [])
    return out


def test_every_sentence_has_basis_and_claims_or_is_a_stated_limit():
    for pillars in (DS.BASE, CONFLICT, SPARSE):
        pre, ans, syn = run(pillars)
        for s in sentences(syn):
            assert s["basis"] in ("modern_explanation", "engine_fact")
            if s["kind"] in ("reading", "relief", "counter") and s["basis"] == "modern_explanation":
                assert s["claim_ids"], s["text"]  # 풀이 문장은 근거 번호가 있어야 한다
                assert s.get("rule_status") or s["kind"] == "counter" or re.search(r"L5-", ",".join(s["claim_ids"])), s
        graph_ids = {n["claim_id"] for n in pre["natal_structure"]["graph"]["nodes"]}
        for cid in syn["claim_ids"]:
            assert cid in graph_ids or cid.startswith("L5-"), cid


def test_no_old_label_style_and_forbidden_wording():
    for pillars in (DS.BASE, CONFLICT, SPARSE):
        _, ans, syn = run(pillars, years=(2027, 2028, 2029, 2030, 2031))
        for bad in OLD_STYLE:
            assert bad not in syn["text"], bad
        assert not re.search(r"약함\(|뚜렷\(|보통\(|성격 후보|지장간", syn["text"])  # 용어 라벨 노출 금지
        assert not re.search(r"반드시|확실히|틀림없|보장합니다|될 것입니다", syn["text"])


def test_same_chart_2027_vs_2030_differs_and_names_the_daeun_change():
    _, a27, s27 = run(years=(2027,), domains=("wealth",))
    _, a30, s30 = run(years=(2030,), domains=("wealth",))
    assert s27["text"] != s30["text"]
    assert "대운 교체" in s30["text"] and "대운 교체" not in s27["text"]  # 2030 은 6/15 에 대운이 바뀌는 합성 배열
    assert s30["period_flow"]["year"] == 2030 and s27["period_flow"]["year"] == 2027


def test_same_year_wealth_vs_career_summaries_differ():
    _, _, syn = run(years=(2030,), domains=("wealth", "career"))
    d = {x["domain"]: x for x in syn["domain_summaries"]}
    assert d["wealth"]["text"] != d["career"]["text"]
    assert "수입" in d["wealth"]["text"] and "지위" in d["career"]["text"] + syn["text"]
    # 분야별 요약은 각 분야 구조의 근거 번호만 인용한다(다른 분야 구조를 끌어오지 않음)
    pre, _, _ = run(years=(2030,), domains=("wealth", "career"))
    nm = {s["name"]: s["claim_id"] for s in pre["natal_structure"]["layer3"]["structures"]}
    assert nm["관인상생"] not in d["wealth"]["claim_ids"] and nm["식상생재"] not in d["career"]["claim_ids"]


def test_gyeokguk_eokbu_conflict_chart_keeps_counter_evidence_visible():
    pre, ans, syn = run(CONFLICT, domains=("overall",))
    assert pre["natal_structure"]["layer4"]["yongshin"]["conflicts"]
    assert any("학파마다" in c["text"] for c in syn["cautions"] + syn["more"]["cautions"])  # 학파 충돌을 숨기지 않고 나란히 놓는다고 말함
    assert syn["cautions"], "반대 근거가 비어 있음"


def test_before_after_daeun_change_is_split_and_not_blended():
    _, ans, syn = run(years=(2030,), domains=("overall",))
    flow = syn["period_flow"]
    assert flow["mode"] == "single" and flow["split"]
    pers = ans["periods"][0]["segments"]
    assert {s["luck"] for s in pers} >= {"丁巳", "丙辰"}
    assert any("경계일 전후" in u["text"] for u in syn["uncertainty"])


def test_single_year_vs_ten_years_structure_and_length():
    _, a1, s1 = run(years=(2030,))
    ys = tuple(range(2027, 2037))
    _, a10, s10 = run(years=ys)
    assert s1["mode"] == "single" and s10["mode"] == "multi"
    assert len(s10["period_flow"]["years"]) == 10
    # 10년 첫 화면 합성문은 기존 서술(narrative)보다 짧다
    assert len(s10["text"]) < len(a10["narrative"]) * 0.6
    # 한 줄 요약은 서로 다른 해의 문장이 통째로 반복되지 않는다(공통 흐름은 한 번만)
    lines = [y["one_line"] for y in s10["period_flow"]["years"]]
    assert len(set(lines)) >= 3
    common = s10["period_flow"]["common"]
    for y in s10["period_flow"]["years"]:
        for n in common["ups"]:
            assert synthesis.STRUCT[n]["short"] not in y["one_line"].split("더해짐")[0] or "더해짐" in y["one_line"]


def test_standout_years_follow_rule_changes_not_probability():
    _, _, syn = run(years=tuple(range(2027, 2032)))
    f = syn["period_flow"]
    assert "확률이 아니라" in f["standout_note"]
    assert 2030 in f["standout"]  # 대운 교체가 있는 해
    for y in f["years"]:
        if y["standout"]:
            assert y["reasons"], y
    assert not re.search(r"\d+\s*%|확률이 높|가능성이 높", syn["text"])


def test_no_repeated_sentences_in_top_section():
    for yrs in ((2030,), tuple(range(2027, 2037))):
        _, _, syn = run(years=yrs)
        top = [x["text"] for k in ("headline", "favorable", "cautions") for x in syn[k]]
        assert len(top) == len(set(top))


def test_insufficient_evidence_is_stated_not_filled():
    pre, ans, syn = run(SPARSE, years=(), domains=("wealth",))
    assert all(s["rank"] == 0 for s in pre["natal_structure"]["layer3"]["structures"])
    assert syn["insufficient_evidence"]
    assert any("근거가 부족" in h["text"] for h in syn["headline"])
    assert not syn["favorable"]  # 돕는 조건을 지어내지 않는다
    assert "수입으로 이어지는" not in syn["text"]
    d = syn["domain_summaries"][0]
    assert d.get("insufficient") and "근거가 부족" in d["text"]


def test_classical_vs_modern_distinction_is_machine_readable():
    _, _, syn = run()
    reading = [s for s in syn["headline"] + syn["favorable"] if s.get("rule_status")]
    assert reading
    for s in reading:
        assert s["basis"] == "modern_explanation"  # 쉬운말 풀이는 항상 현대적 설명
        assert s["rule_status"] in synthesis.STATUS_KO and s["rule_status_ko"]


def test_claims_in_synthesis_match_actual_chart_structures():
    """원국에 없는 구조를 있는 것처럼 말하지 않는다: '원국에는 …이 ~ 보입니다' 문장은 해당 구조 rank>0 이어야 한다."""
    pre, _, syn = run(domains=("overall",))
    nm = {s["claim_id"]: s for s in pre["natal_structure"]["layer3"]["structures"]}
    for s in syn["favorable"]:
        if s["text"].startswith("원국에는"):
            assert any(nm[c]["rank"] > 0 for c in s["claim_ids"] if c in nm)
    for name, rank in syn["natal"]["present"].items():
        assert rank > 0


def test_evidence_bundle_can_be_built_from_the_same_answer():
    """LLM 연결 준비: 같은 답변에서 EvidenceBundle 을 만들 수 있고, 합성 문장의 claim_id 가 번들에 있는 근거를 가리킨다."""
    from app.consult import contracts
    pre, ans, syn = run(domains=("wealth",))
    assert hasattr(contracts, "build_bundle")
    assert syn["version"] == synthesis.SYNTH_VERSION
    assert pre["content_hash"] == ans["ref"]["precommit_hash"]  # 합성은 사전 기록을 바꾸지 않는다
