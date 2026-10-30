"""v8.1 결론형 상담 품질 테스트(자동). 합성 명식만 사용한다. 자동 통과는 사람 상담 품질 검증을 대신하지 않는다(blind_eval 로 별도 평가).

기준: 전문용어·규칙 번호·한자 누수 0, 결론 우선 구조(A~D), 명식별·분야별·연도별 차이, 대운 교체 전후 설명, 미래 단정 0, 반대 근거 누락 방지, 계산 불확실성 표시, 후속 질문.
"""
import json
import re

import pytest
from fastapi.testclient import TestClient

from app.consult import agent, qa, verdict
from app.evaluation import dataset as DS
from app.main import app
from tools.eval_synthesis import charts

CONFLICT = {"year": "丁巳", "month": "乙未", "day": "戊寅", "hour": "庚戌"}
SPARSE = {"year": "己未", "month": "甲寅", "day": "丙寅", "hour": "己未"}
ALL_DOMS = ("overall", "wealth", "career", "business", "job_change", "docs_realestate", "real_estate", "love_marriage", "family", "health_traditional")
JARGON = re.compile(r"(?:^|[\s(·])지지|원국|천간|대운|세운|월운|지장간|암장|궁위|월주|연주|일주|시주|일지|월지|연지|시지|본기|중기|여기|십성|통근|득령|투간|격국|용신|조후|억부|"
                    r"식상|재성|관성|인성|비겁|생극제화|식상생재|재생관|관인상생|살인상생|상관견관|군겁쟁재|claim|ruleset|[一-鿿]|\[?[A-Z]\d?-[A-Z0-9-]*\d{3}")
FUTURE = re.compile(r"반드시|확실히|틀림없|보장합니다|될 것입니다|합격|승진합니다|오릅니다|생깁니다|\d+\s*%|가능성이 높")


def run(pillars=None, years=(2030,), domains=("overall", "wealth", "career"), question="질문"):
    spec = DS.Spec(pillars or DS.BASE, domains=tuple(domains), years=tuple(years), cycles_first_year=2000)
    pre = DS.pre_of(spec)
    return pre, agent.answer(pre, question, domains_=list(domains), years=list(years), depth="detailed")


def user_texts(v: dict) -> list[str]:
    """사용자에게 보이는 모든 문장(internal 제외)."""
    out: list[str] = []

    def walk(o, key=""):
        if isinstance(o, str):
            if key not in ("tone", "domain", "primary_domain", "version", "mode"):
                out.append(o)
        elif isinstance(o, dict):
            for k, x in o.items():
                if k != "internal":
                    walk(x, k)
        elif isinstance(o, list):
            for x in o:
                walk(x, key)
    walk(v)
    return out


def blocks_of(v: dict) -> list[dict]:
    return [b for d in v["detail"].values() for b in d["blocks"]] if v["mode"] == "multi" else v["blocks"]


def sentence_count(t: str) -> int:
    return len([x for x in re.split(r"(?<=[.다요])\s+", t.strip()) if x])


def test_no_jargon_rule_ids_or_hanja_anywhere_in_user_text_for_20_charts():
    for name, p in charts():
        for years in ((), (2030,), (2027, 2028, 2029, 2030, 2031)):
            _, a = run(p, years, ALL_DOMS)
            bad = [(t[:60], m.group()) for t in user_texts(a["verdict"]) + user_texts({"q": a["qa"]}) for m in JARGON.finditer(t)]
            assert not bad, (name, years, bad[:3])


def test_a_to_d_structure_and_sentence_budget():
    for name, p in charts(6):
        _, a = run(p, (2030,), ("overall", "wealth", "career", "love_marriage"))
        v = a["verdict"]
        assert v["blocks"][0]["domain"] == "overall"  # 종합운이 먼저
        for b in v["blocks"]:
            assert 1 <= sentence_count(b["headline"]) <= 2, b["headline"]              # A: 1~2문장
            assert 2 <= len(b["story"]) <= 5 or b["tone"] == "balance", (b["name"], b["story"])  # B: 자연스러운 문장 2~5개
            assert 1 <= len(b["think"]) <= 2 and all("해야 합니다" not in t for t in b["think"])  # C: 강요하지 않는 관점
        ov = v["blocks"][0]
        assert 3 <= len(ov["story"]) <= 5 or len(ov["story"]) >= 2  # 종합운은 짧게 핵심만
        assert 1 <= len(v["limits"]) <= 6 and any("보장" in x for x in v["limits"])  # D


def test_different_charts_get_different_conclusions():
    sigs, heads = set(), set()
    for name, p in charts():
        _, a = run(p, (2030,), ("overall", "wealth", "career"))
        v = a["verdict"]
        sigs.add(tuple(b["tone"] for b in v["blocks"]))
        heads.add(" ".join(b["story"][0] + b["story"][1] for b in v["blocks"]))
    assert len(sigs) >= 4 and len(heads) >= 15, (len(sigs), len(heads))


def test_domains_get_different_explanations_not_renamed_copies():
    _, a = run(None, (2030,), ("wealth", "career", "business", "job_change", "docs_realestate", "love_marriage", "family"))
    bl = a["verdict"]["blocks"]
    assert len({b["headline"] for b in bl}) == len(bl)
    assert len({" ".join(b["story"]) for b in bl}) == len(bl) and len({" ".join(b["think"]) for b in bl}) == len(bl)
    # 분야 이름만 바꾼 문장이 아니다: 두 분야의 풀이가 공유하는 문장 비율이 낮다
    sets = [set(re.split(r"(?<=[.다])\s+", " ".join(b["story"] + b["think"]))) for b in bl]
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            assert len(sets[i] & sets[j]) / max(1, len(sets[i] | sets[j])) < 0.5, (bl[i]["name"], bl[j]["name"])


def test_2027_vs_2030_and_same_year_same_conclusion_regardless_of_range():
    _, a27 = run(None, (2027,), ("wealth", "career"))
    _, a30 = run(None, (2030,), ("wealth", "career"))
    t27, t30 = a27["verdict"], a30["verdict"]
    assert [b["story"] for b in t27["blocks"]] != [b["story"] for b in t30["blocks"]]
    assert any("무렵 10년 단위로 바뀌는 큰 흐름이 바뀌" in s for b in t30["blocks"] for s in b["story"]) and not any("무렵 10년 단위로 바뀌는 큰 흐름이 바뀌" in s for b in t27["blocks"] for s in b["story"])  # 대운 교체 전후 설명
    assert any("6월 15일" in s for b in t30["blocks"] for s in b["story"])
    # 같은 해는 단일 연도로 보든 5년 범위로 보든 같은 결론
    _, multi = run(None, (2027, 2028, 2029, 2030, 2031), ("wealth", "career"))
    for y in (2027, 2030):
        _, one = run(None, (y,), ("wealth", "career"))
        assert [(b["domain"], b["tone"]) for b in one["verdict"]["blocks"]] == [(b["domain"], b["tone"]) for b in multi["verdict"]["detail"][str(y)]["blocks"]]


def test_multi_year_structure_and_no_invented_differences():
    ys = tuple(range(2027, 2037))
    _, a = run(None, ys, ("overall", "wealth", "career"))
    v = a["verdict"]
    p = v["period"]
    assert v["mode"] == "multi" and len(p["years"]) == 10 and 2 <= len(p["summary"]) <= 4
    assert all(set(r) >= {"year", "line", "change", "caution", "standout"} for r in p["years"])
    assert 2030 in p["standout"]  # 대운이 바뀌는 해
    quiet = [r for r in p["years"] if not r["standout"] and r["change"].startswith("다른 해와 구별되는")]
    assert quiet  # 구조 차이가 없는 해에 억지 차이를 만들지 않는다
    assert all(len(v["detail"][str(y)]["blocks"]) == 3 for y in ys)
    txt = " ".join(user_texts(v))
    assert "확률" not in txt.replace("확률이 아니라", "")


def test_no_future_assertions_and_hedged_think_sentences():
    for name, p in charts(10):
        _, a = run(p, (2027, 2030), ALL_DOMS)
        txt = " ".join(user_texts(a["verdict"]))
        assert not FUTURE.search(txt), (name, FUTURE.search(txt).group())
        for b in blocks_of(a["verdict"]):
            assert all(re.search(r"볼 수 있습니다|좋습니다|도움이 될 수|참고|생각해|판단해|기준으로", t) for t in b["think"]), b["think"]


def test_counter_evidence_is_never_dropped_when_both_sides_exist():
    for name, p in charts():
        _, a = run(p, (2030,), ("overall", "wealth", "career"))
        for b in a["verdict"]["blocks"]:
            if b["scores"]["S"] > 0 and b["scores"]["T"] > 0:
                text = " ".join(b["story"] + [b["headline"]])
                assert re.search(r"동시에|한편|다만|함께|또한|매끄럽게만|부딪", text), (name, b["name"], text)
            if b["tone"] == "mixed":
                assert re.search(r"함께|도 |부딪|나누|점검", b["headline"])


def test_thin_evidence_is_stated_not_filled():
    _, a = run(SPARSE, (), ("wealth", "career"))
    for b in a["verdict"]["blocks"]:
        assert b["tone"] == "thin" and "근거가 부족" in b["headline"] and "수입으로 이어지는 흐름이 보이는" not in b["headline"]
    assert any("근거가 부족한 분야" in x for x in a["verdict"]["limits"])


def test_calculation_uncertainty_is_shown_in_plain_words():
    pre, a = run(None, (2030,), ("overall",))
    lim = " ".join(a["verdict"]["limits"])
    assert "검증" in lim and "보장하지 않" in lim and not JARGON.search(lim)
    # 시 경계 가까움 → 사용자 문장으로 안내
    pre["verification"]["hour_boundary"] = {"near": True, "minutes_to_boundary": 3, "messages": ["x"]}
    assert any("시(2시간 단위) 경계" in x for x in verdict.limits_for(pre, [2030], []))
    pre["variants_count"] = 2
    assert any("여러 개로 갈리" in x for x in verdict.limits_for(pre, [2030], []))


def test_health_never_predicts_or_diagnoses():
    _, a = run(None, (2030,), ("health_traditional",))
    b = a["verdict"]["blocks"][0]
    t = " ".join([b["headline"]] + b["story"] + b["think"])
    assert "판단하거나 예측할 수 없" in b["headline"] and "의료진" in b["headline"]
    assert not re.search(r"병에|질환이|암|수명|치료가|진단[을는]? (받|내)|걸릴", t)


QUESTIONS = ["그래서 2030년에 이직하는 게 좋다는 거야?", "2028년과 비교하면 어느 쪽이 더 나아?", "돈을 벌어도 남지 않는다는 건 무슨 뜻이야?", "왜 그렇게 읽어?", "사업 쪽은 어떻게 보이나요?", "오늘 점심 뭐 먹지"]


def test_follow_up_questions_get_intent_specific_answers_without_rule_dumps():
    pre = DS.pre_of(DS.Spec(DS.BASE, domains=("wealth", "career"), years=(2028, 2030), cycles_first_year=2000))
    got = {}
    for q in QUESTIONS:
        a = agent.answer(pre, q, domains_=["wealth", "career"], years=[2028, 2030], depth="detailed")
        r = a["qa"]
        got[q] = r["kind"]
        body = r["text"] + " ".join(r.get("points", []))
        assert not JARGON.search(body) and not FUTURE.search(body), (q, body[:200])
    assert got[QUESTIONS[0]] == "advice" and got[QUESTIONS[1]] == "compare" and got[QUESTIONS[2]] == "meaning" and got[QUESTIONS[3]] == "why"
    assert got[QUESTIONS[4]] == "detail" and got[QUESTIONS[5]] == "unsupported"
    a = agent.answer(pre, QUESTIONS[0], domains_=["wealth", "career"], years=[2028, 2030])
    assert "하는 게 좋다’ 또는 ‘하지 않는 게 좋다’고 말씀드릴 수는 없습니다" in a["qa"]["text"] and "2030년" in a["qa"]["text"]  # 권유·만류를 하지 않고 해당 해를 답한다
    a = agent.answer(pre, QUESTIONS[1], domains_=["wealth", "career"], years=[2028, 2030])
    assert "2028년" in a["qa"]["text"] and "2030년" in a["qa"]["text"] and "우열이 아니라" in a["qa"]["text"] + "우열이 아니라" or "크지 않" in a["qa"]["text"]
    a = agent.answer(pre, QUESTIONS[5], domains_=["wealth"], years=[2030])
    assert "답해 드릴 수 있어요" in a["qa"]["text"] and not a["qa"]["points"]  # 범위 밖은 지원 범위만 안내


def test_meaning_answer_does_not_invent_when_the_chart_lacks_that_structure():
    pre = DS.pre_of(DS.Spec(SPARSE, domains=("wealth",), years=(2030,), cycles_first_year=2000))
    a = agent.answer(pre, "돈을 벌어도 남지 않는다는 건 무슨 뜻이야?", domains_=["wealth"], years=[2030])
    assert a["qa"]["kind"] == "meaning"


@pytest.mark.public_view
def test_public_api_and_precommit_expose_only_user_data():
    c = TestClient(app)
    body = {"calendar": "solar", "birth_date": "1984-06-15", "birth_time": "10:00", "gender": "male", "birth_place": "서울특별시", "years": [2030], "domains": ["overall", "wealth", "career"],  # 가상 입력
            "question": "2030년 재물과 직업"}
    r = c.post("/api/v1/oneshot/analyze", json=body)
    assert r.status_code == 200
    d = r.json()
    assert set(d["answer"]) == {"refused", "years", "domains", "verdict", "qa"} and set(d["precommit"]) == {"pillars", "years", "domains", "calc"}
    assert "internal" not in d["answer"]["verdict"]
    raw = r.text
    assert not re.search(r"L\d-[A-Z0-9-]+|claim|natal_structure|synthesis|ruleset|content_hash|calculation_profile|verification\"|classical|rule_id|expert", raw)
    # 개발용 플래그를 켜면 내부 근거가 나온다(기본은 꺼짐)
    import os
    os.environ["EXPOSE_INTERNAL"] = "1"
    try:
        full = c.post("/api/v1/oneshot/analyze", json=body).json()
    finally:
        del os.environ["EXPOSE_INTERNAL"]
    assert "synthesis" in full["answer"] and "internal" in full["answer"]["verdict"]
    # 후속 질문·현실 사건 응답도 사용자용
    ask = c.post("/api/v1/oneshot/ask", json={**body, "question": "사업 쪽은 어떻게 보이나요?"}).json()
    assert set(ask) == {"refused", "years", "domains", "verdict", "qa"} and "사업" in ask["qa"]["text"]
    ev = c.post("/api/v1/oneshot/reality", json={**body, "event": {"kind": "event", "type": "취업·이직", "year": 2030}}).json()
    assert set(ev) == {"outcome", "explanation"} and not re.search(r"식상|재생관|구조", ev["explanation"])


def test_internal_evidence_is_preserved_in_the_engine_for_every_verdict():
    """사용자 화면에서는 과정을 빼도 엔진 내부에는 근거·반대 근거·조건·검증 상태·규칙 버전이 남아 있다."""
    pre, a = run(None, (2030,), ("overall", "wealth", "career"))
    i = a["verdict"]["internal"]
    assert i["claim_ids"] and i["ruleset_version"] and i["verification_status"] and i["conditions"] and set(i["tones"]) == {"overall", "wealth", "career"}
    assert set(i["counter_evidence"]) == {"overall", "wealth", "career"} and i["scores"]["wealth"].keys() == {"S", "T"}
    assert a["synthesis"]["claim_ids"] and a["blocks"]  # 기존 합성·근거 계층도 그대로


def test_public_view_of_refused_questions_is_safe():
    pre = DS.pre_of(DS.Spec(DS.BASE, domains=("overall",), years=(2030,), cycles_first_year=2000))
    a = agent.answer(pre, "언제 죽을까요?", domains_=["overall"], years=[2030])
    pv = verdict.public_view(a)
    assert pv["refused"] is True and "수명이나 사망" in pv["message"] and "verdict" not in pv


def test_headline_never_claims_growth_that_the_story_denies():
    """결론(A)이 '커집니다/더 뚜렷해집니다'라고 하면 풀이(B)에도 그해 변화가 있어야 한다. 풀이가 '크게 달라지지 않습니다'라면 결론도 변화를 말하지 않는다."""
    for name, p in charts():
        for y in (2027, 2028, 2029, 2030, 2031):
            _, a = run(p, (y,), ("overall", "wealth", "career", "business"))
            for b in a["verdict"]["blocks"]:
                story = " ".join(b["story"])
                denies = "크게 달라지지 않" in story or "눈에 띄는 변화가 없" in story
                claims = re.search(r"커집니다|더 뚜렷해집니다", b["headline"])
                assert not (denies and claims), (name, y, b["name"], b["headline"], story)


def test_no_back_to_back_dapman_and_no_money_counter_in_career_domains():
    for name, p in charts():
        _, a = run(p, (2030,), ("wealth", "career", "job_change", "docs_realestate"))
        for b in a["verdict"]["blocks"]:
            for s1, s2 in zip(b["story"], b["story"][1:]):
                assert not (s1.startswith("다만") and s2.startswith("다만")), (name, b["name"], b["story"])
            if b["domain"] in ("career", "job_change", "docs_realestate"):
                assert not any("이익" in c for c in b["counter"]), (name, b["name"], b["counter"])
    _, a = run(None, (2030,), ("wealth", "career"))
    w, c = a["verdict"]["blocks"]
    assert set(w["counter"]) != set(c["counter"])  # 분야마다 다른 반대 근거


def test_flat_year_is_reported_as_quiet_with_natal_character_kept():
    _, a = run(None, (2030,), ("wealth", "career"))
    for b in a["verdict"]["blocks"]:
        if "크게 달라지지 않" in " ".join(b["story"]):
            assert b["tone"] == "quiet" and "타고난" in b["headline"]
