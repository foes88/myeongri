"""v9.2 판정 기준(judge-2.0.0) 테스트. 분포를 맞추는 테스트가 아니라 판정 원칙(근거 없는 주장 차단·충돌 보존·합은 방향 아님)을 검증한다. 합성 명식만 사용."""
import pytest

from app import cases as C
from app.consult import agent, judge as J
from tools.bias_probe import charts


# ---------------------------------------------------------------- classify 원칙
@pytest.mark.parametrize("S,T,basis,yc,tone,cls", [
    (0, 0, False, True, "thin", "C"),            # 근거 자체가 없음
    (0, 0, True, True, "quiet", "none"),         # 근거는 있으나 달라지는 것 없음
    (2, 0, True, True, "opportunity", "A"),
    (3, 1, True, True, "opportunity", "A"),
    (0, 2, True, True, "cautious", "A"),
    (1, 3, True, True, "cautious", "A"),
    (3, 2, True, True, "mixed", "B"),            # 양쪽 모두 충분하고 비슷 → 충돌
    (2, 2, True, True, "mixed", "B"),
    (1, 0, True, True, "thin", "C"),             # 약한 한쪽 근거로 방향을 정하지 않는다(예전에는 '혼합')
    (2, 1, True, True, "thin", "C"),
    (1, 1, True, True, "thin", "C"),
    (1, 2, True, False, "quiet", "none"),        # 약하고 이 해에 달라지는 것도 없음 → 달라지지 않음
])
def test_classification_table(S, T, basis, yc, tone, cls):
    r = J.classify(S, T, basis, yc)
    assert (r["tone"], r["cls"]) == (tone, cls)
    assert J.consistent(r["tone"], S, T)


def test_no_directional_or_conflict_claim_without_enough_evidence():
    for S in range(0, 6):
        for T in range(0, 6):
            r = J.classify(S, T, True, True)
            if r["tone"] == "opportunity":
                assert S >= J.MIN_DOMINANT and S - T >= J.MARGIN
            if r["tone"] == "cautious":
                assert T >= J.MIN_DOMINANT and T - S >= J.MARGIN
            if r["tone"] == "mixed":
                assert S >= J.MIN_CONFLICT and T >= J.MIN_CONFLICT and abs(S - T) < J.MARGIN
            if r["tone"] in ("opportunity", "cautious", "mixed"):
                assert max(S, T) >= 2


def test_inconsistent_tone_is_detected():
    assert not J.consistent("opportunity", 1, 3)
    assert not J.consistent("mixed", 1, 0)


# ---------------------------------------------------------------- 관계의 원문 확인 상태
def test_only_text_confirmed_rules_count_toward_direction():
    assert J.relation_confirmed("충") and J.relation_confirmed("천간합") and J.relation_confirmed("육합")
    for t in ("형(부분)", "삼형", "파", "해", "자형"):     # 위치만 확인된 규칙(형·파·해)은 방향 판정에서 제외
        assert not J.relation_confirmed(t), t


# ---------------------------------------------------------------- 궁위 분야 점수 원칙(합성 입력)
def rels_stub(natal_hits):
    def f(pre, pos, kinds=None):
        return [{"relation_type": k, "pillars": [p]} for p, k in natal_hits if p in pos and (kinds is None or k in kinds)]
    return f


def fake_palace_relations(period, palaces):
    from app.consult import facts as FA
    acc = {}
    for s in period["segments"]:
        for r in s["relations"]:
            if r["with"] in palaces:
                pol = "bad" if r["type"] in FA.BAD_REL else "good"
                a = acc.setdefault((r["who"], r["type"], r["with"]), {"who": r["who"], "type": r["type"], "palace": r["with"], "polarity": pol, "frac": 0.0})
                a["frac"] += s["_days"] / 365
    return list(acc.values())


def score(rows, ex=None, natal_hits=(), pre=None, base=None, pals=("year", "month", "hour")):
    """rows: [(who, type, palace, days)]"""
    segs = [{"from": f"2030-01-{1 + i:02d}", "to": f"2030-01-{1 + i:02d}", "relations": [{"who": w, "type": t, "with": p}], "_days": d} for i, (w, t, p, d) in enumerate(rows)]
    return J.palace_scores(pre or {"variants_count": 1}, "family", segs, ex, pals, rels_stub(natal_hits), 0.5, fake_palace_relations, base)


def test_absence_of_a_star_is_not_counted_as_opposing_evidence():
    ex = {"evidence_for": [], "evidence_against": ["인성(어머니·윗사람 상징): 원국에 보이지 않음", "비겁: 원국에 보이지 않음"]}
    r = score([], ex)
    assert r["T"] == 0 and r["S"] == 0 and r["neg"] == 0


def test_hap_relations_are_signals_not_support():
    r = score([("year", "육합", "month", 365)])
    assert r["S"] == 0 and r["palace_good"] == 1 and r["has_basis"]
    assert J.classify(r["S"], r["T"], r["has_basis"], r["year_change"])["tone"] == "quiet"


def test_confirmed_year_clash_counts_once_even_across_several_palaces():
    rows = [("year", "충", "year", 365), ("year", "충", "month", 365), ("year", "충", "hour", 365)]
    r = score(rows)
    assert r["T"] == 2 and r["palace_bad"] == 1           # 같은 세운 충은 한 번(예전에는 궁위·구간마다 중복 집계)
    assert J.classify(r["S"], r["T"], r["has_basis"], r["year_change"])["tone"] == "cautious"


def test_unconfirmed_relation_types_are_reference_only():
    rows = [("year", "파", "year", 365), ("year", "해", "month", 365), ("year", "형(부분)", "hour", 365)]
    r = score(rows)
    assert r["T"] == 0 and set(r["reference"]) == {"파", "해", "형(부분)"}
    assert J.classify(r["S"], r["T"], r["has_basis"], r["year_change"])["tone"] != "cautious"


def test_partial_year_clash_is_weaker_than_whole_year_and_luck_persistence_counts_one():
    assert score([("year", "충", "year", 100)])["T"] == 1
    assert score([("luck", "충", "year", 365)])["T"] == 1
    assert score([("year", "충", "year", 300)])["T"] == 2


def test_hour_palace_is_ignored_when_hour_pillar_is_ambiguous():
    rows = [("year", "충", "hour", 365)]
    assert score(rows, pre={"variants_count": 1})["T"] == 2
    r = score(rows, pre={"variants_count": 2})
    assert r["T"] == 0 and r["hour_excluded"] is True


def test_natal_background_is_capped_below_a_year_change():
    ex = {"evidence_for": ["인성: 천간 노출 1개, 지지 암장 1개", "비겁: 천간 노출 2개, 지지 암장 0개", "자녀성(식상): 천간 노출 1개, 지지 암장 0개"], "evidence_against": []}
    r = score([], ex)
    assert r["S"] == J.NATAL_CAP == 1                       # 원국 배경만으로는 방향성 주장(2 이상)에 이르지 못한다
    assert J.classify(r["S"], r["T"], r["has_basis"], r["year_change"])["tone"] in ("thin", "quiet")


# ---------------------------------------------------------------- 실제 엔진(합성 명식) 불변식
@pytest.fixture(scope="module")
def sample():
    return [(ci, C.generate_predictions(ci, 2026)) for ci in list(charts(8, seed=77))]


def test_conclusions_never_contradict_scores(sample):
    for ci, rec in sample:
        pre, _ = C.pre_for(ci, [rec["years"][0]["year"]])
        for r in rec["years"][::5]:
            v = agent.answer(pre, "종합 상담을 시작합니다", domains_=C.PRED_DOMAINS, years=[r["year"]], depth="detailed")["verdict"]
            assert v["internal"]["judge"]["version"] == J.JUDGE_VERSION and v["internal"]["judge"]["consistent"] is True
            for b in v["blocks"]:
                assert J.consistent(b["tone"], b["scores"]["S"], b["scores"]["T"])
                if b["tone"] in ("opportunity", "cautious", "mixed"):
                    assert max(b["scores"]["S"], b["scores"]["T"]) >= 2


def test_family_and_love_never_claim_opportunity_without_a_support_basis(sample):
    # 가족·연애 분야에는 방향을 줄 지지 구조가 선언되어 있지 않다 → 기회 판정이 나오면 안 된다(근거 없는 긍정 차단)
    for _ci, rec in sample:
        for r in rec["years"]:
            for dom in ("family", "love_marriage"):
                assert r["domains"][dom]["tone"] != "opportunity", (dom, r["year"])


def test_same_input_gives_identical_predictions(sample):
    ci, rec = sample[0]
    again = C.generate_predictions(ci, 2026)
    assert again["hash"] == rec["hash"] and again["ruleset_version"].endswith(J.JUDGE_VERSION)


def test_ruleset_for_freeze_includes_judge_version():
    assert C.current_ruleset().endswith("+" + J.JUDGE_VERSION)
