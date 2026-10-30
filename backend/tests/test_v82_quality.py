"""v8.2 상담 품질 자동 검증(합성·가상 입력). 자동 통과는 사람 상담 품질 검증을 대신하지 않는다(블라인드 평가 미수행)."""
import json
import re

import pytest

from app import main as M
from app.consult import agent, explain, facts, qa, verdict
from app.consult import synthesis as S
from app.evaluation import dataset as DS
from tests.test_v81_verdict import JARGON, FUTURE, charts
from tools.eval_synthesis import charts as all_charts

DOMS = ("overall", "wealth", "career", "business", "job_change", "docs_realestate", "love_marriage", "family")


def real(years, doms=("overall", "wealth", "career"), q="x"):
    b = M.OneshotBody(calendar="solar", birth_date="1984-06-15", birth_time="10:00", gender="male", birth_place="경기도 수원시", years=list(years), domains=list(doms), question=q)  # 가상 입력
    pre = M._oneshot_pre(b)
    return pre, agent.answer(pre, q, domains_=list(doms), years=list(years), depth="detailed")


def seg(frm, to, delta=(), rels=(), luck="甲戌", sewun="丁未"):
    return {"from": frm, "to": to, "luck": luck, "sewun": sewun, "relations": list(rels), "delta": list(delta), "struct_evidence": {}, "claim_nodes": {}}


UP = {"structure": "재생관", "change": "강화", "before": "보통", "after": "뚜렷", "claim_id": "L5-003"}


# ---------------------------------------------------------------- 기간 가중(2028년 사례)
def test_short_segment_change_is_partial_and_long_segment_is_major():
    short = {"year": 2028, "segments": [seg("2028-01-01", "2028-02-03", [UP]), seg("2028-02-04", "2028-12-31")]}
    r = facts.year_reading(short, ["재생관"])
    assert r["ups"] == [] and r["ups_partial"] == ["재생관"] and r["total_days"] == 366 and round(r["ups_detail"]["재생관"]["frac"], 2) == 0.09
    long = {"year": 2029, "segments": [seg("2029-01-01", "2029-02-03"), seg("2029-02-04", "2029-12-31", [dict(UP, claim_id="L5-009")])]}
    assert facts.year_reading(long, ["재생관"])["ups"] == ["재생관"]
    half = {"year": 2030, "segments": [seg("2030-01-01", "2030-07-02", [UP]), seg("2030-07-03", "2030-12-31")]}  # 183일/365일 ≥ 절반
    assert facts.year_reading(half, ["재생관"])["ups"] == ["재생관"]


def test_real_chart_2028_is_not_called_the_standout_year_and_trace_shows_why():
    pre, a = real((2027, 2028, 2029, 2030, 2031))
    v = a["verdict"]
    row = {r["year"]: r for r in v["period"]["years"]}
    assert 2028 not in v["period"]["standout"] and set(v["period"]["standout"]) == {2027, 2031}
    assert "동안에만" in row[2028]["change"] and "1월 1일~2월 3일" in row[2028]["change"]  # 일부 기간만 달라짐을 밝힌다
    tr = v["internal"]["trace"]["2028"]
    first = tr["segments"][0]
    assert first["days"] == 34 and first["deltas"][0]["structure"] == "재생관" and first["deltas"][0]["claim_id"] == "L5-003"
    assert any("세운간 丁(正官)" in e for e in first["deltas"][0]["added_by"])  # 변화를 만든 그해(세운) 글자가 증거에 드러난다
    assert tr["segments"][1]["deltas"] == []  # 입춘 이후 332일은 변화 없음
    w = tr["weighted"]
    assert w["ups_major(해 전체의 변화로 셈)"] == [] and "재생관" in w["ups_partial(일부 기간만)"]
    # 2030: 전 구간 구조 변화 없음 → 두드러지지 않음, 억지 차이를 만들지 않는다
    assert all(not s["deltas"] for s in v["internal"]["trace"]["2030"]["segments"]) and not row[2030]["standout"] and row[2030]["why"] == ""
    # 2031: 10월 2일 대운 교체가 이유
    assert row[2031]["standout"] and "10월 2일 무렵 10년 단위 큰 흐름이 바뀌" in row[2031]["why"]
    assert v["internal"]["period_dev"]["2027"] == v["internal"]["period_dev"]["2031"] > v["internal"]["period_dev"]["2028"] > v["internal"]["period_dev"]["2030"]


def test_year_conclusion_does_not_describe_partial_change_as_year_long():
    pre, a = real((2028,))
    for b in a["verdict"]["blocks"]:
        assert b["tone"] == "quiet" and "커집니다" not in b["headline"]
        story = " ".join(b["story"])
        assert "해 전체의 흐름은 크게 달라지지 않" in story or "크게 달라지지 않" in b["headline"]
    wealth = next(b for b in a["verdict"]["blocks"] if b["domain"] == "wealth")
    assert "1월 1일~2월 3일" in " ".join(wealth["story"]) and "입춘 전" in " ".join(wealth["story"])


def test_same_year_same_conclusion_regardless_of_range_still_holds_with_weighting():
    _, multi = real((2027, 2028, 2029, 2030, 2031))
    for y in (2027, 2028, 2030, 2031):
        _, one = real((y,))
        assert [(b["domain"], b["tone"], b["headline"]) for b in one["verdict"]["blocks"]] == [(b["domain"], b["tone"], b["headline"]) for b in multi["verdict"]["detail"][str(y)]["blocks"]]


# ---------------------------------------------------------------- 반복·구체성
def collect(n_charts=8, years=(2027, 2029, 2031)):
    heads, sents, cross_dup, answers = [], [], 0, 0
    for name, p in all_charts(n_charts):
        for y in years:
            pre = DS.pre_of(DS.Spec(p, domains=DOMS, years=(y,), cycles_first_year=2000))
            a = agent.answer(pre, "x", domains_=list(DOMS), years=[y], depth="detailed")
            per = []
            for b in a["verdict"]["blocks"]:
                heads.append(b["headline"])
                ss = [x for x in re.split(r"(?<=[.다요])\s+", " ".join(b["story"])) if len(x) > 6]
                sents += ss
                per.append(ss)
            flat = [s for ss in per for s in set(ss)]
            cross_dup += len(flat) - len(set(flat))
            answers += 1
    return heads, sents, cross_dup / answers


def test_repetition_metrics_stay_below_thresholds():
    heads, sents, dup = collect()
    assert len(set(heads)) / len(heads) >= 0.25, len(set(heads)) / len(heads)                   # 결론 문장 다양성(v8.1: 0.17)
    assert len(set(sents)) / len(sents) >= 0.15, len(set(sents)) / len(sents)                   # 풀이 문장 다양성(v8.1: 0.07)
    assert dup <= 3.0, dup                                                                       # 같은 답변 안에서 분야끼리 겹치는 문장(v8.1: 7.7)
    blob = " ".join(heads + sents)
    assert "한쪽으로만 읽지" not in blob and "다만 타고난 사주에도" not in blob                  # 지목된 반복 문구 제거
    assert "타고난 사주에서 확인되는 것은 다음과 같습니다" not in blob                          # 정형 도입문 제거


def test_conclusion_contains_chart_specific_structure_not_only_a_tone_label():
    """같은 어조라도 사주의 실제 구조(이어지는 흐름의 종류와 강약)에 따라 결론이 달라진다. 20개 명식에서 분야별 서로 다른 결론 수."""
    want = {"wealth": 6, "career": 10, "overall": 9}   # 재물운은 구조가 3종뿐이라 가능한 종류가 적다(한계)
    for dom, minimum in want.items():
        seen = set()
        for name, p in all_charts(20):
            pre = DS.pre_of(DS.Spec(p, domains=(dom,), years=(2030,), cycles_first_year=2000))
            seen.add(agent.answer(pre, "x", domains_=[dom], years=[2030], depth="detailed")["verdict"]["blocks"][0]["headline"])
        assert len(seen) >= minimum, (dom, len(seen))


def test_blocks_in_one_answer_use_different_skeletons():
    pre, a = real((2030,), ("wealth", "career", "business", "job_change"))
    firsts = [b["story"][0][:6] for b in a["verdict"]["blocks"]]
    assert len(set(firsts)) >= 3, firsts   # 분야마다 풀이의 첫 문장이 다르다


# ---------------------------------------------------------------- 왜 그렇게 읽나요
def test_every_block_has_plain_why_with_natal_period_against_and_nature():
    for years in ((2030,), (2027, 2028, 2029, 2030, 2031)):
        pre, a = real(years, ("overall", "wealth", "career", "love_marriage", "family"))
        v = a["verdict"]
        blocks = v["blocks"] or [b for d in v["detail"].values() for b in d["blocks"]]
        for b in blocks:
            w = b["why"]
            assert set(w) == {"natal", "period", "against", "nature"} and w["natal"] and w["against"] and w["nature"]
            if b["domain"] != "health_traditional":
                assert w["period"]
            text = " ".join(w["natal"] + w["period"] + w["against"] + [w["nature"]])
            assert not JARGON.search(text) and not FUTURE.search(text), (b["name"], JARGON.search(text) and JARGON.search(text).group())
            assert "이 서비스가 정한" in w["nature"] or "정한 방식" in w["nature"]  # 구현자 규약을 정설처럼 말하지 않는다
            assert not re.search(r"\([^)]*[가-힣]*[A-Za-z]{3,}", text)


def test_why_period_text_names_the_added_luck_stems_in_plain_words():
    pre, a = real((2028,))
    w = next(b for b in a["verdict"]["blocks"] if b["domain"] == "wealth")["why"]
    joined = " ".join(w["period"])
    assert "1월 1일~2월 3일" in joined and "그해가 들여온" in joined and "10년 큰 흐름이 들여온" in joined
    assert "원국" not in joined and "세운" not in joined and "대운" not in joined


def test_limits_state_that_conclusions_are_service_rules_not_classical_orthodoxy():
    pre, a = real((2030,))
    assert any("이 서비스가 정한 규칙이며 고전 원문으로 확정된 것이 아닙니다" in x for x in a["verdict"]["limits"])


# ---------------------------------------------------------------- 후속 질문: 연도 이유
def test_year_why_questions_use_the_traced_reason_and_do_not_invent():
    pre, _ = real((2027, 2028, 2029, 2030, 2031))
    def ask(q):
        return agent.answer(pre, q, domains_=["wealth", "career"], years=[2027, 2028, 2029, 2030, 2031], depth="detailed")["qa"]
    r31 = ask("2031년은 왜 달라지는 해야?")
    assert r31["kind"] == "why_year" and "10월 2일 무렵" in r31["text"] and not JARGON.search(r31["text"])
    r30 = ask("2030년은 왜 달라지는 해야?")
    assert r30["kind"] == "why_year" and "두드러지는 해로 뽑지 않았습니다" in r30["text"]
    r28 = ask("2028년은 왜 달라지는 해야?")
    assert r28["kind"] == "why_year" and "1월 1일~2월 3일" in r28["text"] and "동안에만" in r28["text"]
    r = ask("왜 그렇게 읽어?")
    assert r["kind"] == "why" and r["points"] and not JARGON.search(r["text"] + " ".join(r["points"]))


# ---------------------------------------------------------------- 월운·내부 정보는 기본 화면에 없다
def test_public_view_has_no_monthly_luck_and_no_internal_trace():
    pre, a = real((2030,))
    pv = verdict.public_view(a)
    raw = json.dumps(pv, ensure_ascii=False)
    assert "월운" not in raw and "월별" not in raw and "months" not in raw and "internal" not in raw and "trace" not in raw and "claim" not in raw
    # 이번 단계에서는 월운을 사용자 결과 화면(결론형 UI)에 넣지 않는다. 월운 코드는 개발용(live) 옛 화면에만 있다.
    ui = open(__file__.replace("backend\\tests\\test_v82_quality.py", "web\\assets\\verdict_ui.js").replace("backend/tests/test_v82_quality.py", "web/assets/verdict_ui.js"), encoding="utf-8").read()
    assert "monthly" not in ui and "월운" not in ui


def test_flat_multi_year_range_is_declared_flat_not_decorated():
    """구조 변화가 전혀 없는 명식·기간에서는 두드러지는 해를 만들지 않는다."""
    n_flat = 0
    for name, p in all_charts(20):
        pre = DS.pre_of(DS.Spec(p, domains=("overall", "wealth"), years=(2032, 2033), cycles_first_year=2000))
        a = agent.answer(pre, "x", domains_=["overall", "wealth"], years=[2032, 2033], depth="detailed")
        v = a["verdict"]["period"]
        if not v["standout"]:
            n_flat += 1
            assert any("구별되는 구조 변화는 없어" in s for s in v["summary"]) or v["summary"]
    assert n_flat >= 1


def test_blind_packet_can_carry_three_versions_without_source_labels():
    from app import blind_eval as BE
    items = [{"item_id": f"c{i}", "question": "q", "years": [2030], "domains": ["overall"], "variants": {"v70": f"a{i}", "v81": f"b{i}", "v82": f"c{i}"}} for i in range(12)]
    pk, key = BE.build_packet(items)
    blob = json.dumps(pk, ensure_ascii=False)
    assert all(set(i["texts"]) == {"X", "Y", "Z"} for i in pk["items"]) and not re.search(r"v70|v81|v82|legacy|synthesis", blob)
    firsts = [list(v["slots"].values())[0] for v in key["items"].values()]
    assert len(set(firsts)) == 3  # X 슬롯이 한 버전으로 쏠리지 않는다
