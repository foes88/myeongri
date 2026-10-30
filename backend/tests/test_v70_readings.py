"""v7.0 5단 해석(의미·판단 근거·현실 연결·반대 근거·해석 범위) 테스트. 합성 명식만 사용."""
import re

from app.consult import readings
from tests.test_v69_synthesis import CONFLICT, SPARSE, run

JARGON = re.compile(r"지장간|암장|성격 후보|투출|통근|득령|십성|비겁|식상|재성|관성|인성|격국|용신")
FUTURE = re.compile(r"반드시|확실히|틀림없|보장합니다|될 것입니다|생깁니다|오릅니다|승진합니다|\d+\s*%|가능성이 높")


def test_each_reading_has_five_parts_and_traceable_claims():
    pre, ans, syn = run(years=(2030,), domains=("wealth", "career"))
    assert syn["readings"]
    graph = {n["claim_id"] for n in pre["natal_structure"]["graph"]["nodes"]}
    for r in syn["readings"]:
        for k in ("meaning", "why", "reality", "counter", "scope"):
            assert r[k], k
        assert r["claim_ids"] and set(r["claim_ids"]) <= graph
        assert r["basis"] == "modern_explanation" and r["rule_status_ko"]
        assert "확정하지 않습니다" in r["scope"]  # 결과 단정 금지가 모든 해석에 붙는다


def test_reading_text_has_no_jargon_or_future_assertion():
    for p in (None, CONFLICT):
        _, _, syn = run(p, years=(2030,), domains=("overall", "wealth", "career"))
        for r in syn["readings"]:
            body = " ".join([r["meaning"], r["reality"], *r["counter"], r["scope"], r.get("period", "")])
            assert not JARGON.search(body), body
            assert not FUTURE.search(body + r["why"]), body


def test_why_uses_only_evidence_present_in_the_chart_and_has_no_hanja():
    """판단 근거 문장에는 한자가 없고, 말한 기운(쉬운 말)은 해당 구조의 지지 증거에 실제로 있는 십성에서만 나온다."""
    pre, _, syn = run(years=(2030,), domains=("wealth",))
    nm = {s["name"]: s for s in pre["natal_structure"]["layer3"]["structures"]}
    for r in syn["readings"]:
        assert not re.search(r"[一-鿿]", r["why"]), r["why"]
        ev_gods = {g for g in readings.GOD_PLAIN if any(f"({g}" in e for e in nm[r["structure"]]["supporting"])}
        allowed = {readings.GOD_PLAIN[g] for g in ev_gods}
        for phrase in set(readings.GOD_PLAIN.values()):
            if phrase in r["why"]:
                assert phrase in allowed, (phrase, r["why"])


def test_wealth_and_career_use_different_reality_lens_for_same_structure():
    lens = readings.LENS["식상생재"]
    assert lens["wealth"] != lens["career"] != lens["business"]
    assert "승진" not in lens["wealth"] and "수입" not in lens["career"].split("보상")[0]


def test_sparse_chart_does_not_invent_readings():
    pre, _, syn = run(SPARSE, years=(), domains=("wealth", "career"))
    assert syn["readings"] == []
    assert syn["insufficient_evidence"]


def test_overall_does_not_repeat_readings_already_given_by_specific_domains():
    _, _, syn = run(years=(2030,), domains=("overall", "wealth", "career"))
    keys = [(r["structure"]) for r in syn["readings"] if r["domain"] != "overall"]
    for r in syn["readings"]:
        if r["domain"] == "overall":
            assert r["structure"] not in keys


def test_palace_domains_get_five_part_readings_and_health_never_diagnoses():
    doms = ("love_marriage", "family", "job_change", "real_estate", "health_traditional")
    pre, _, syn = run(years=(2030,), domains=doms)
    got = {r["domain"]: r for r in syn["readings"] if r["domain"] in doms}
    assert set(got) == set(doms)
    for r in got.values():
        for k in ("meaning", "why", "reality", "counter", "scope"):
            assert r[k]
        assert "확정하지 않습니다" in r["scope"] and r["rule_status"] == "implementer_convention"
        assert not re.search(r"\[[A-Z0-9-]+-\d{3}\]", r["why"] + " ".join(r["counter"]))  # 내부 번호 노출 없음(번호는 claim_ids 로)
        assert not FUTURE.search(r["meaning"] + r["reality"] + r["scope"])
    h = got["health_traditional"]
    assert "의료진" in h["scope"] and not re.search(r"질환|질병|병이|진단|치료|수명", h["meaning"] + h["reality"])


def test_plain_evidence_per_domain_has_no_jargon_ids_or_hanja_and_no_repeated_sentences():
    pre, _, syn = run(years=(2030,), domains=("wealth", "career", "love_marriage", "family"))
    ev = syn["evidence_plain"]
    assert [e["domain"] for e in ev] == ["wealth", "career", "love_marriage", "family"]
    for e in ev:
        lines = e["positive"] + e["negative"]
        assert lines and len(lines) == len(set(lines))
        blob = " ".join(lines)
        assert not re.search(r"\[[A-Z0-9-]+-\d{3}\]|[一-鿿]|지장간|암장|투출|십성|비겁|식상|재성|관성|인성|식상생재|재생관|관인상생|살인상생|상관견관|군겁쟁재", blob), blob
        assert e["claim_ids"]
    for e in ev:  # 같은 반대 견해 문장이 한 분야 안에서 구조마다 되풀이되지 않는다
        sentences = [x.split(". (해당")[0] for x in e["positive"] + e["negative"] if ". (해당" in x]
        assert len(sentences) == len(set(sentences))
