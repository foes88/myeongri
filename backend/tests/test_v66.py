"""v6.6: 새 분야(궁위 신호), 분야·연도별 차이, LLM 계약(공급업체 독립), 특정 연도 상담 절차."""
import inspect
import json
import re

import pytest

from app.consult import agent, compose_domains
from app.consult import contracts as C
from app.consult import domains as D
from app.consult import llm as L
from app.evaluation import dataset as DS

SP = DS.Spec(DS.BASE, domains=("love_marriage", "family", "health_traditional", "real_estate", "job_change", "career", "wealth"), years=(2030,))
ORGANS_AND_DISEASES = ["심장", "간장", "신장", "폐", "위장", "암", "당뇨", "고혈압", "우울증", "질환", "병명"]


def answer_for(spec, q="종합 상담", **kw):
    pre = DS.pre_of(spec)
    return agent.answer(pre, q, domains_=list(spec.domains), years=list(spec.years), depth=kw.get("depth", "expert")), pre


def test_new_domains_exist_and_route_from_free_text():
    for d in ("job_change", "love_marriage", "family", "health_traditional", "real_estate"):
        assert d in D.DOMAINS
    assert "love_marriage" in D.route("연애와 결혼운이 궁금해요", None) and "family" in D.route("부모님과 인간관계", None)
    assert "health_traditional" in D.route("올해 건강운", None) and "job_change" in D.route("이직 준비 중", None)
    assert D.refusal("암에 걸릴까요")  # 진단성 질문은 여전히 거절


def test_each_new_domain_has_its_own_evidence_and_counter_and_no_medical_claims():
    a, pre = answer_for(SP)
    blocks = {b["domain"]: b for b in a["blocks"]}
    for d in ("love_marriage", "family", "health_traditional", "real_estate", "job_change"):
        assert blocks[d]["evidence_for"] and blocks[d]["evidence_against"], d
    h = " ".join([blocks["health_traditional"]["easy_text"]] + blocks["health_traditional"]["evidence_for"] + blocks["health_traditional"]["evidence_against"])
    assert "진단이나 예측이 아니며" in h and "의료진과 상담" in h
    body = h.replace("진단이나 예측이 아니며", "").replace("병명·증상과 연결하지 않습니다", "")  # 부정형 고지 문구는 제외
    assert not [w for w in ORGANS_AND_DISEASES if w in body], [w for w in ORGANS_AND_DISEASES if w in body]
    assert a["consistency"]["ok"]


def test_love_uses_gender_specific_spouse_star():
    m, _ = answer_for(DS.Spec(DS.BASE, domains=("love_marriage",), gender="male"))
    f, _ = answer_for(DS.Spec(DS.BASE, domains=("love_marriage",), gender="female"))
    assert "배우자성(재성)" in m["blocks"][0]["easy_text"] and "배우자성(관성)" in f["blocks"][0]["easy_text"]
    assert m["blocks"][0]["evidence_for"] != f["blocks"][0]["evidence_for"]


def test_domains_do_not_repeat_identical_sentences_for_same_palace():
    a, _ = answer_for(DS.Spec(DS.BASE, domains=("career", "job_change", "love_marriage"), years=(2030,)))
    dp = [p for p in a["paragraphs"] if p["kind"] == "domain_period"]
    texts = [p["text"] for p in dp]
    assert len(texts) == len(set(texts))
    merged = [p for p in dp if "직업·승진운" in p["text"] and "이직·취업운" in p["text"]]
    assert merged and "공통" in merged[0]["text"]  # 같은 궁위(월주)를 보는 두 분야는 한 문단으로 묶여 반복되지 않음
    assert any("연애·결혼운" in p["text"] and "직업" not in p["text"] for p in dp)  # 일주를 보는 분야는 다른 문장


def test_cross_domain_link_is_explained_not_repeated():
    a, _ = answer_for(DS.Spec(DS.BASE, domains=("wealth", "career")))
    cross = [p for p in a["paragraphs"] if p["kind"] == "cross"]
    assert len(cross) <= 1
    if cross:
        assert "결과를 정하는 것이 아니라" in cross[0]["text"]


def test_year_and_domain_changes_change_period_notes():
    a30, _ = answer_for(DS.Spec(DS.BASE, domains=("love_marriage",), years=(2030,)))
    a31, _ = answer_for(DS.Spec(DS.BASE, domains=("love_marriage",), years=(2031,)))
    t = lambda a: " ".join(p["text"] for p in a["paragraphs"] if p["kind"] in ("period", "domain_period"))
    assert t(a30) != t(a31) and "2030" in t(a30) and "2031" in t(a31)


def test_specific_year_procedure_records_steps_and_splits_on_daeun_change():
    spec = DS.build_pairs()[10].a   # 연중(6월)에 대운이 교체되는 합성 배열
    a, _ = answer_for(spec)
    steps = {s["step"]: s["detail"] for s in a["procedure"]}
    assert "2030년 구간별 세운" in steps["세운 계산"] and "직전 해 세운" in steps["세운 계산"]
    assert "대운 교체 있음" in steps["대운 교체 기간 분할"] and "구간 3개" in steps["입춘 전후 구분"]
    assert any("미검증 계산은 확정값으로 표시하지 않음" in v for v in steps.values())
    order = [s["step"] for s in a["procedure"]]
    assert order.index("세운 계산") < order.index("적용 대운 계산") < order.index("원국-운 관계 분석") < order.index("정·반 근거 및 모순 검증") < order.index("쉬운 설명 작성")
    nochange, _ = answer_for(DS.build_pairs()[10].b)
    assert "교체 없음" in {s["step"]: s["detail"] for s in nochange["procedure"]}["대운 교체 기간 분할"]


# ---------------------------------------------------------------- LLM 계약
class ProviderOK:
    name = "fake-ok"

    def generate(self, request, bundle):
        return C.ConsultationDraft("쉽게 정리하면 아래와 같습니다.\n\n" + "\n\n".join(p["text"] for p in bundle.paragraphs), self.name, "m1", {"in_tokens": 1})


class ProviderInvents:
    name = "fake-invent"

    def __init__(self, extra):
        self.extra = extra

    def generate(self, request, bundle):
        return C.ConsultationDraft("\n".join(p["text"] for p in bundle.paragraphs) + "\n" + self.extra, self.name, "m2")


class ProviderBoom:
    name = "fake-boom"

    def generate(self, request, bundle):
        raise ConnectionError("down")


def test_contracts_never_call_external_services():
    src = inspect.getsource(C) + inspect.getsource(L)
    assert not re.search(r"^\s*(import|from)\s+(requests|httpx|urllib|http\.client|openai|anthropic|socket)", src, re.M)


def test_bundle_excludes_personal_chart_data_and_has_fallback():
    a, pre = answer_for(DS.Spec(DS.BASE))
    b = C.build_bundle(a, pre)
    blob = json.dumps(b.to_prompt_payload(), ensure_ascii=False)
    assert "birth" not in blob and "access_token" not in blob and "input_hash" not in blob
    assert b.fallback_text == "\n\n".join(p["text"] for p in a["paragraphs"]) and b.precommit_hash == pre["content_hash"]
    assert b.classical_status and set(b.classical_status.values()) <= {"text_confirmed", "location_confirmed", "implementer_convention", "pending"}


def test_provider_output_validated_or_falls_back():
    a, pre = answer_for(DS.Spec(DS.BASE))
    req = C.ConsultationRequest("종합")
    ok = C.run(a, pre, req, ProviderOK())
    assert ok.ok and ok.source == "provider" and "쉽게 정리하면" in ok.text
    none = C.run(a, pre, req, None)
    assert none.source == "deterministic_fallback" and none.ok
    boom = C.run(a, pre, req, ProviderBoom())
    assert boom.source == "deterministic_fallback" and not boom.ok and "제공자 오류" in boom.problems[0]
    for extra, expect in [("도화살이 있어 연애운이 좋습니다.", "근거 없는 명리 용어"), ("2044년이 중요합니다.", "근거 없는 연도"), ("근거 L3-909.", "claim_id"),
                          ("이 명식은 乙亥 일주입니다.", "근거 없는 간지")]:
        r = C.run(a, pre, req, ProviderInvents(extra))
        assert not r.ok and r.source == "deterministic_fallback" and any(expect in p for p in r.problems), (extra, r.problems)
        assert r.text == C.build_bundle(a, pre).fallback_text


def test_unconfirmed_rule_cannot_be_described_as_classical_fact():
    a, pre = answer_for(DS.Spec(DS.BASE))
    b = C.build_bundle(a, pre)
    if not any(s != "text_confirmed" for s in b.classical_status.values()):
        pytest.skip("모든 인용 규칙이 text_confirmed")
    r = C.run(a, pre, C.ConsultationRequest("t"), ProviderInvents("자평진전에 따르면 이 격국은 분명합니다."))
    assert not r.ok and any("고전 근거처럼" in p for p in r.problems)


def test_template_provider_reference_implementation_validates():
    a, pre = answer_for(DS.Spec(DS.BASE))
    r = C.run(a, pre, C.ConsultationRequest("t"), C.TemplateProvider())
    assert r.ok and r.provider == "template-provider" and r.bundle_hash == pre["content_hash"]


def test_model_change_does_not_change_facts_or_bundle():
    a, pre = answer_for(DS.Spec(DS.BASE))
    b1, b2 = C.build_bundle(a, pre), C.build_bundle(a, pre)
    assert b1 == b2
    r1 = C.run(a, pre, C.ConsultationRequest("t"), ProviderOK())
    r2 = C.run(a, pre, C.ConsultationRequest("t"), C.TemplateProvider())
    assert r1.text != r2.text and r1.bundle_hash == r2.bundle_hash and r1.ok and r2.ok
