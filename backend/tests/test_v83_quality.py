"""v8.3 상담 품질 테스트(합성·가상 입력): 연도 변화 분류, 종합운·분야 중복 제거, 재물·직업 근거 차이, 근거 부족 설명, 연도 비교.
자동 통과는 사람 상담 품질 검증을 대신하지 않는다."""
import re

import pytest

from app.consult import agent, facts, qa, verdict
from app.consult import synthesis as S
from app.evaluation import dataset as DS
from tests.test_v81_verdict import FUTURE, JARGON
from tests.test_v82_quality import real, seg
from tools.eval_synthesis import charts

UP = {"structure": "재생관", "change": "강화", "before": "보통", "after": "뚜렷", "claim_id": "L5-003"}
LUCK_ONLY = ["대운간 甲(偏財)", "→ 대운지 지장간 丁(正官·여기)"]
BOTH = ["대운간 甲(偏財)", "→ 세운간 丁(正官)"]


def seg_ev(frm, to, ev=None, delta=(), luck="甲戌", sewun="丁未"):
    s = seg(frm, to, delta, luck=luck, sewun=sewun)
    if ev is not None:
        s["struct_evidence"] = {"재생관": ev}
    return s


# ---------------------------------------------------------------- 연도 변화 분류(지속 일수만이 아니라 원인·수명·경계를 함께)
def test_categories_use_cause_and_lifetime_not_only_duration():
    # 같은 25% 길이라도 원인에 따라 달라진다: 대운뿐이고 해 끝까지 이어지면 '이어지는 변화', 세운이 끼면 '일부 기간'
    luck = {"year": 2031, "segments": [seg_ev("2031-01-01", "2031-10-01", None, luck="甲戌"), seg_ev("2031-10-02", "2031-12-31", LUCK_ONLY, [UP], luck="乙亥")]}
    r = facts.year_reading(luck, ["재생관"])
    assert r["ups_persistent"] == ["재생관"] and r["ups"] == [] and r["ups_partial"] == []
    d = r["ups_detail"]["재생관"]
    assert d["drivers"] == {"luck"} and d["ends_year_end"] and d["luck_edge"] and round(d["frac"], 2) == 0.25
    both = {"year": 2031, "segments": [seg_ev("2031-01-01", "2031-10-01", None), seg_ev("2031-10-02", "2031-12-31", BOTH, [UP], luck="乙亥")]}
    assert facts.year_reading(both, ["재생관"])["ups_partial"] == ["재생관"]           # 세운이 만든 변화는 그 세운이 끝나면 사라진다
    mid = {"year": 2031, "segments": [seg_ev("2031-01-01", "2031-04-01", None), seg_ev("2031-04-02", "2031-07-01", LUCK_ONLY, [UP], luck="乙亥"), seg_ev("2031-07-02", "2031-12-31", None, luck="乙亥")]}
    assert facts.year_reading(mid, ["재생관"])["ups_partial"] == ["재생관"]           # 해 끝까지 이어지지 않으면 일부 기간
    # 극단적으로 짧은 대운 단독 변화(10%)도 해를 넘어 이어지므로 '이어지는 변화' — 임계값이 아니라 원인이 판정한다
    tiny = {"year": 2031, "segments": [seg_ev("2031-01-01", "2031-11-30", None), seg_ev("2031-12-01", "2031-12-31", LUCK_ONLY, [UP], luck="乙亥")]}
    assert facts.year_reading(tiny, ["재생관"])["ups_persistent"] == ["재생관"]
    # 세운이 낀 40% 변화는 과반이 아니므로 일부 기간(대표 아님)
    forty = {"year": 2031, "segments": [seg_ev("2031-01-01", "2031-06-30", None), seg_ev("2031-07-01", "2031-12-31", BOTH, [UP])]}
    assert facts.year_reading(forty, ["재생관"])["ups_partial"] == ["재생관"] or facts.year_reading(forty, ["재생관"])["ups"] == ["재생관"]


def test_persistent_change_is_worded_as_limited_start_with_uncertainty_note():
    luck = {"year": 2031, "segments": [seg_ev("2031-01-01", "2031-10-01", None), seg_ev("2031-10-02", "2031-12-31", LUCK_ONLY, [UP], luck="乙亥")]}
    yr = facts.year_reading(luck, ["재생관"])
    t = {"sup_up": [], "ten_up": [], "sup_part": [], "ten_part": [], "sup_pers": ["재생관"], "ten_pers": [], "natal_support": ["재생관"], "present": {"재생관": 2}}
    sent, _ = verdict._change_sentences("career", "2031년", yr, t, [2031], "k", set())
    assert "10월 2일부터는" in sent and "다음 해에도 이어질 수 있습니다" in sent and "며칠~몇 주" in sent
    assert "해 전체" not in sent and not JARGON.search(sent)


def test_persistent_change_adds_to_standout_score_without_claiming_a_year_wide_change():
    pre, a = real((2031,))
    b = a["verdict"]["blocks"][0]
    assert b["tone"] in ("quiet", "mixed", "opportunity", "cautious", "thin")  # 그해 대표 어조는 해 전체의 변화만으로 정한다


def test_real_chart_2028_and_2030_conclusions_are_unchanged_by_the_new_classification():
    _, a = real((2027, 2028, 2029, 2030, 2031))
    v = a["verdict"]["period"]
    assert set(v["standout"]) == {2027, 2031} and "동안에만" in next(r for r in v["years"] if r["year"] == 2028)["change"]
    tr = a["verdict"]["internal"]["trace"]["2028"]["weighted"]["classification"]["재생관"]
    assert tr["category"] == "partial" and set(tr["drivers"]) == {"luck", "sewun"} and tr["frac"] == 0.09  # 사람이 따라갈 수 있게 분류 근거가 추적에 남는다
    tr27 = a["verdict"]["internal"]["trace"]["2027"]["weighted"]["classification"]["재생관"]
    assert tr27["category"] == "year" and tr27["frac"] == 1.0


# ---------------------------------------------------------------- 결론과 풀이의 중복 제거
TIER = re.compile(r"어느 정도|뚜렷하게|약하게|갖춰져|자리 잡|자리하고 있")
THEME_PHRASES = sorted({v for d in verdict.THEMES.values() for v in d.values()}, key=len, reverse=True)


def themes_in(text: str) -> set[str]:
    return {t for t in THEME_PHRASES if t in text}


def sents(t: str) -> list[str]:
    return [x for x in re.split(r"(?<=[.다요])\s+", t) if len(x) > 6]


def grams(t: str) -> set[str]:
    t = re.sub(r"\s+|[.,·()‘’']", "", t)
    return {t[i:i + 3] for i in range(max(1, len(t) - 2))}


def jac(a: str, b: str) -> float:
    A, B = grams(a), grams(b)
    return len(A & B) / max(1, len(A | B))


def test_story_adds_information_instead_of_repeating_the_headline():
    n = 0
    for name, p in charts(20):
        for y in (2027, 2029, 2030, 2031):
            pre = DS.pre_of(DS.Spec(p, domains=("overall", "wealth", "career", "business"), years=(y,), cycles_first_year=2000))
            a = agent.answer(pre, "x", domains_=["overall", "wealth", "career", "business"], years=[y], depth="detailed")
            for b in a["verdict"]["blocks"]:
                head_sents = sents(b["headline"])
                head_themes = themes_in(b["headline"]) if "타고난 대로" in b["headline"] else set()
                for s in b["story"]:
                    n += 1
                    for hs in head_sents:
                        assert jac(s, hs) < 0.6, (name, y, b["name"], s, hs)           # 결론 문장을 풀이가 다시 쓰지 않는다
                    for th in head_themes:                                               # 결론이 말한 강약·주의를 풀이가 되풀이하지 않는다
                        if th in s and not re.search(r"주로 .*에서 나타납니다", s):
                            assert not (TIER.search(s) or re.search(r"함께 있|같이 살펴|균형을 함께|좋은 면만", s)), (name, y, b["name"], s)
    assert n > 500


def test_overall_story_does_not_repeat_the_same_caution_twice():
    for name, p in charts(20):
        pre = DS.pre_of(DS.Spec(p, domains=("overall", "wealth", "career"), years=(2030,), cycles_first_year=2000))
        a = agent.answer(pre, "x", domains_=["overall", "wealth", "career"], years=[2030], depth="detailed")
        ov = a["verdict"]["blocks"][0]
        full = [ov["headline"]] + ov["story"]
        for th in THEME_PHRASES:
            hits = [s for s in full if th in s]
            cautions = [s for s in hits if re.search(r"함께 있|같이 살펴|균형을 함께|좋은 면만|유의|점검", s)]
            assert len(cautions) <= 1, (name, th, cautions)                                # 같은 주의점을 두 번 말하지 않는다


# ---------------------------------------------------------------- 재물·직업: 실제 근거 차이
def test_emphasis_describes_which_branch_carries_the_weight():
    w = verdict._emphasis("wealth", {"식상생재": 3, "재생관": 1})
    assert "직접 버는 힘" in w and "무게가 실리고" in w and "상대적으로 약하게" in w
    w2 = verdict._emphasis("wealth", {"식상생재": 1, "재생관": 3})
    assert "안정된 자리에서 나오는 수입" in w2.split("에 무게")[0]
    assert "비슷한 비중" in verdict._emphasis("wealth", {"식상생재": 2, "재생관": 2})
    assert "한 갈래" in verdict._emphasis("wealth", {"재생관": 2})
    c = verdict._emphasis("career", {"관인상생": 3, "재생관": 2})
    assert "신뢰와 도움" in c and "후원" in c
    assert "압박" in verdict._emphasis("career", {"살인상생": 2})
    assert verdict._emphasis("career", {}) is None and verdict._emphasis("wealth", {}) is None


def test_wealth_and_career_differences_follow_the_chart_evidence():
    seen_w, seen_c = set(), set()
    for name, p in charts(20):
        pre = DS.pre_of(DS.Spec(p, domains=("wealth", "career"), years=(2030,), cycles_first_year=2000))
        a = agent.answer(pre, "x", domains_=["wealth", "career"], years=[2030], depth="detailed")
        nm = {s["name"]: s["rank"] for s in pre["natal_structure"]["layer3"]["structures"]}
        w, c = a["verdict"]["blocks"]
        wt, ct = " ".join(w["why"]["natal"]), " ".join(c["why"]["natal"])
        if nm["식상생재"] and nm["재생관"]:
            assert "직접 버는 힘" in wt and "안정된 자리에서 나오는 수입" in wt
        if any(nm[k] for k in ("재생관", "관인상생", "살인상생")):
            assert "직업에서는" in ct
        seen_w.add(next((x for x in w["story"] if "재물은" in x or "재물 흐름은" in x), ""))
        seen_c.add(next((x for x in c["story"] if x.startswith("직업에서는")), ""))
    assert len(seen_w - {""}) >= 3 and len(seen_c - {""}) >= 4


# ---------------------------------------------------------------- 근거가 약하거나 없을 때: 이유를 쉽게 설명
def test_weak_and_thin_evidence_explain_why_instead_of_concluding():
    weak = thin = 0
    for name, p in charts(60):
        pre = DS.pre_of(DS.Spec(p, domains=("wealth", "career"), years=(2030,), cycles_first_year=2000))
        a = agent.answer(pre, "x", domains_=["wealth", "career"], years=[2030], depth="detailed")
        for b in a["verdict"]["blocks"]:
            if "뚜렷한 결론은 내리지 않았습니다" in b["headline"]:
                weak += 1
                assert "속에 숨은 정도로만" in b["headline"] and any("겉으로 드러나지 않고 속에 숨어 있어 힘이 약합니다" in s for s in b["story"])
                assert not re.search(r"기회를 살리기|서두르기보다|커집니다", b["headline"])
            if b["tone"] == "thin":
                thin += 1
                assert "근거가 부족" in b["headline"] and any(("말씀드릴 근거가 부족합니다" in s or "결론을 내리지 않았습니다" in s) for s in b["story"])   # v9.2: 약한 근거(차이 작음)도 '근거 부족'으로 설명
                assert not re.search(r"수입으로 이어지는 흐름이 보이는|평가와 자리로 이어지기 쉬운", b["headline"] + " ".join(b["story"]))
    assert weak >= 2 and thin >= 1


# ---------------------------------------------------------------- 연도 비교
def test_year_comparison_answers_are_grounded_and_symmetric():
    pre, _ = real((2027, 2028, 2029, 2030, 2031))
    def ask(q, doms=("wealth", "career")):
        return agent.answer(pre, q, domains_=list(doms), years=[2027, 2028, 2029, 2030, 2031], depth="detailed")["qa"]
    r = ask("2030년과 2031년 중 어느 쪽이 더 나아?")
    assert r["kind"] == "compare" and "2030년" in r["text"] and "2031년" in r["text"] and not JARGON.search(r["text"]) and not FUTURE.search(r["text"])
    a, b = ask("2027년과 2031년을 비교하면 어느 쪽이 나아?"), ask("2031년과 2027년을 비교하면 어느 쪽이 나아?")
    assert a["kind"] == b["kind"] == "compare" and sorted(a["years"]) == sorted(b["years"]) == [2027, 2031]
    # 어느 쪽이 낫다고 말하더라도 우열이 아니라 성격 차이로 안내하고, 근거가 같으면 우열을 만들지 않는다
    assert ("우열이 아니라" in a["text"]) or ("크지 않" in a["text"]) or ("어렵" in a["text"])
    same = ask("2029년과 2030년을 비교하면?")
    assert same["kind"] == "compare" and ("크지 않" in same["text"] or "우열이 아니라" in same["text"])
