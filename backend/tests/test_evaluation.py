"""Eval-Harness Track A: 데이터셋, 지표, 바넘 검사, 보고서. 합성 데이터만 사용."""
import json
from pathlib import Path

import pytest

from app.consult import agent
from app.consult import contracts as C
from app.evaluation import barnum, dataset as DS, metrics as M, run as R
from app.report_checks import FIXED_DISCLAIMER

GOLDEN = Path(__file__).resolve().parents[1] / "golden"


def ans(spec, **kw):
    pre = DS.pre_of(spec)
    return agent.answer(pre, R.QUESTION, domains_=list(spec.domains), years=list(spec.years), depth="expert"), pre


def test_calendar_realizability_flags():
    assert DS.calendar_realizable({"year": "甲丑", "month": "丙寅", "day": "戊午", "hour": "壬子"}) is False  # 음양 불일치 간지
    assert DS.calendar_realizable({"year": "癸卯", "month": "庚申", "day": "甲子", "hour": "己卯"}) is False  # 음양은 맞지만 시주 천간이 일간과 맞지 않음(甲日 卯시는 丁卯)
    # 실제 계산 엔진이 만든 명식은 실현 가능
    from app.astro_core import calculate_chart
    p = calculate_chart(year=1999, month=5, day=5, hour=12, minute=0, gender="male").pillars
    assert DS.calendar_realizable(p) is True


def test_pairs_cover_required_factors_and_use_only_synthetic_data():
    pairs = DS.build_pairs()
    factors = " ".join(p.factor for p in pairs)
    for need in ("일간만", "월령", "통근", "격국", "조후", "합충", "대운만", "세운", "분야만"):
        assert need in factors, need
    for p in pairs:
        for s in (p.a, p.b):
            assert all(DS.valid_gz(v) for v in s.pillars.values())
    r = json.loads((GOLDEN / "eval_trackA_report.json").read_text(encoding="utf-8"))
    assert r["dataset"]["synthetic"] is True and r["dataset"]["personal_data"] is False
    blob = json.dumps(r, ensure_ascii=False)
    assert "birth_date" not in blob and not __import__("re").search(r"(19|20)\d{2}-\d{2}-\d{2}", blob)  # 날짜 형태 없음


@pytest.mark.parametrize("pair", DS.build_pairs(), ids=lambda p: p.pair_id)
def test_each_factor_changes_expected_facets(pair):
    r = R.pair_result(pair)
    assert r["sensitive"], (pair.factor, r["missing_facets"])
    assert r["signature_distance"] > 0 and not r["cosmetic_only"]


def test_identical_input_has_zero_distance_and_repeats_identically():
    p = DS.build_pairs()[0]
    a1, pre = ans(p.a)
    a2, _ = ans(p.a)
    assert M.jacc_dist(M.signature(a1, pre), M.signature(a2, pre)) == 0 and M.token_dist(" ".join(x["text"] for x in a1["paragraphs"]), " ".join(x["text"] for x in a2["paragraphs"])) == 0
    assert R.repeat_consistency(DS.Spec(DS.BASE))["identical"]


def test_cosmetic_rewrite_is_detected_as_same_judgement_different_text():
    a, pre = ans(DS.Spec(DS.BASE))
    a2 = json.loads(json.dumps(a))
    for p in a2["paragraphs"]:
        p["text"] = "쉽게 말해, " + p["text"].replace("입니다", "이에요").replace("합니다", "해요").replace("있습니다", "있어요")
    sig_d = M.jacc_dist(M.signature(a, pre), M.signature(a2, pre))
    txt_d = M.token_dist(" ".join(x["text"] for x in a["paragraphs"]), " ".join(x["text"] for x in a2["paragraphs"]))
    assert sig_d == 0.0 and txt_d > 0.05  # 문장은 달라졌지만 판단 내용(서명)은 같다 → 좋은 분석의 증거가 아님


def test_barnum_flags_generic_sentence_but_not_fact_bearing_templates():
    specs = DS.barnum_set(6)
    pres = [DS.pre_of(s) for s in specs]
    answers = [R.ask(p, s) for p, s in zip(pres, specs)]
    base = barnum.analyze(answers, pres)
    # 모든 답변에 같은 일반론을 주입하면 other_generic 이 증가해야 한다
    inj = json.loads(json.dumps(answers))
    for a in inj:
        a["paragraphs"].insert(1, {"kind": "domain", "text": "당신은 겉으로는 강해 보이지만 속으로는 외로움을 탈 때가 있습니다.", "claim_ids": []})
    after = barnum.analyze(inj, pres)
    assert after["generic_by_type"]["other_generic"] >= base["generic_by_type"]["other_generic"] + 6
    assert any("외로움" in s for s in after["other_generic_examples"])
    assert base["fact_bearing_template_sentences"] > 0  # 틀은 같아도 사실이 다른 문장은 일반론으로 세지 않는다
    assert base["mean_signature_distance"] > 0.5


def test_metrics_detect_assertions_overclaim_and_missing_counter():
    a, pre = ans(DS.Spec(DS.BASE))
    assert M.assertion(a)["assertive_ratio"] == 0.0
    bad = json.loads(json.dumps(a))
    bad["paragraphs"].append({"kind": "domain", "text": "2030년에는 반드시 재물이 늘어납니다.", "claim_ids": []})
    assert M.assertion(bad)["assertive_sentences"] >= 1
    over = json.loads(json.dumps(a))
    over["paragraphs"].append({"kind": "domain", "text": "자평진전에 따르면 이 명식은 정관격이 확실합니다.", "claim_ids": []})
    assert M.evidence(over, pre)["classical_overclaim_sentences"] >= 1
    assert M.evidence(a, pre)["classical_overclaim_sentences"] == 0 and M.evidence(a, pre)["counter_coverage"] == 1.0
    assert M.domain_evidence(a)["ratio"] == 1.0
    assert M.readability(a)["proxy_only"] is True


def test_school_conflict_chart_is_explained():
    spec = DS.conflict_chart_spec()
    assert spec is not None
    a, _ = ans(spec)
    txt = " ".join(p["text"] for p in a["paragraphs"] if p["kind"] == "schools")
    assert "서로 겹치지 않습니다" in txt and "각각 설명" in txt


def test_report_states_limits_and_makes_no_superiority_claims():
    r = json.loads((GOLDEN / "eval_trackA_report.json").read_text(encoding="utf-8"))
    lim = " ".join(r["limits"])
    assert "사람 평가" in lim and "우수성을 주장하지 않는다" in lim and "Track B" in lim
    assert r["pair_summary"]["sensitive"] == r["pair_summary"]["total"] == 12
    assert r["controls"]["identical_input_signature_distance"] == 0
    assert r["aggregate"]["classical_overclaim_total"] == 0 and r["aggregate"]["consistency_ok_all"] is True
    assert r["barnum"]["generic_by_type"]["scaffold_or_hedge"] >= 0 and "other_generic_ratio" in r["barnum"]
    assert (GOLDEN / "eval_human_template.csv").exists()
    for bad in ("철학관보다 우수", "전문가보다 정확"):
        assert bad not in json.dumps(r, ensure_ascii=False)
