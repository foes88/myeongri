"""v6.5: 고전 근거 연결, 破 프로필, 상담 품질(연도/분야 변경, 다분야, 후속 일관성), 변조, 로그 노출, LLM 검증, 모델 변경."""
import json
import logging
import os
import re

import pytest
from fastapi.testclient import TestClient

from app.astro_core import calculate_chart
from app.consult import agent, llm, store
from app.main import app
from app.mingli import analyze_structure, classical, rules
from app.mingli.rules import RULES, detect_conflicts

BODY = {"birth_date": "1984-06-15", "birth_time": "10:00", "gender": "male", "years": [2030, 2031], "domains": ["wealth", "career"], "depth": "detailed"}  # 가상 입력


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CONSULT_DIR", str(tmp_path / "consult"))
    return TestClient(app)


def make_pre(**kw):
    chart = calculate_chart(year=1984, month=6, day=15, hour=10, gender="male").to_dict()  # 가상 입력
    args = dict(variant_id="v1", years=[2030, 2031], domains=["wealth", "career", "business"], depth="detailed", input_fingerprint={"t": 1})
    args.update(kw)
    pre = agent.build_precommit(chart, **args)
    pre["content_hash"] = store.sha256({k: v for k, v in pre.items() if k != "content_hash"})
    return pre


# ------------------------------------------------------------ P2: 고전 규칙 연결
def test_rules_carry_classical_status_and_do_not_disguise_conventions():
    cnt = {}
    for rid, r in RULES.items():
        assert r["classical_status"] in rules.CLASSICAL_STATES
        cnt[r["classical_status"]] = cnt.get(r["classical_status"], 0) + 1
        assert r["classical_status"] == ("implementer_convention" if classical.classical_status(rid) == "implementation_convention" else classical.classical_status(rid))
        has_text = any(x.get("type") == "classical_text" for x in r["sources"])
        if r["classical_status"] == "implementer_convention":
            assert r["classical_claim"] is False and not has_text  # 고전 원문으로 위장 금지
        else:
            assert r["classical_claim"] is True and has_text
            src = next(x for x in r["sources"] if x.get("type") == "classical_text")
            assert src["url"].startswith("http") and src["scope_note"]
        assert all(x["classical_verification"] == r["classical_status"] for x in r["sources"])
    assert cnt == {"text_confirmed": 27, "location_confirmed": 4, "implementer_convention": 6}  # v6.6: 심화 조사로 4개 승격(partial), 4개 location 유지


def test_location_only_rules_each_have_documented_engine_gap():
    for rid, r in RULES.items():
        if r["classical_status"] == "location_confirmed":
            assert r["engine_vs_classical"] and r["engine_vs_classical"]["note"], rid


def test_engine_vs_classical_conflicts_detected():
    cs = {c["rule_id"]: c for c in detect_conflicts()}
    assert cs["MG-L2-PA"]["kind"] == "conflict" and "寅亥" in cs["MG-L2-PA"]["note"]
    assert all(RULES[c]["classical_claim"] for c in cs)  # 구현자 규약은 충돌 검출 대상이 아님
    assert {"conflict", "simplified", "later_concept", "partial", "school_variant"} >= {c["kind"] for c in cs.values()}


PAIR = {"year": "甲寅", "month": "乙亥", "day": "丙子", "hour": "丁丑"}  # 가상 명식: 寅亥 쌍 포함


def test_pa_profile_switch_changes_relations_and_records_conflict():
    a = analyze_structure(PAIR)
    b = analyze_structure(PAIR, profiles={"pa": "sanmyeongtonghoe_4"})
    pa_a = [r for r in a["layer2"]["relations"] if r["relation_type"] == "파"]
    pa_b = [r for r in b["layer2"]["relations"] if r["relation_type"] == "파"]
    assert len(pa_a) == 1 and not pa_b and a["layer2"]["count"] == b["layer2"]["count"] + 1
    assert a["layer2"]["profile_conflicts"][0]["pair"] == "寅亥" and "제외됨" in b["layer2"]["profile_conflicts"][0]["result_in_this_run"]
    assert any(c["name"] == "원문 대조" and c["status"] == "contested" for c in pa_a[0]["conditions"])
    assert any(r["relation_type"] == "육합" for r in b["layer2"]["relations"])  # 합으로는 계속 기록
    with pytest.raises(ValueError):
        analyze_structure(PAIR, profiles={"pa": "nope"})


def test_graph_nodes_link_classical_location_and_counter_evidence():
    r = analyze_structure(PAIR)
    node = next(n for n in r["graph"]["nodes"] if n["rule_id"] == "MG-L2-PA")
    assert node["attributes"]["classical"]["status"] == "location_confirmed" and node["attributes"]["classical"]["url"].startswith("http")
    assert any("원문 대조(conflict)" in c for c in node["counter_evidence"])
    ref = [x for x in node["source_references"] if x.get("type") == "classical_text"]
    assert ref and ref[0]["work"]
    conv = next(n for n in r["graph"]["nodes"] if RULES[n["rule_id"]]["classical_status"] == "implementer_convention")
    assert conv["attributes"]["classical"]["classical_claim"] is False and "구현자 규약" in conv["attributes"]["classical"]["note"]
    assert r["validation"]["ok"]


def test_classical_fail_closed_when_verification_file_missing(monkeypatch):
    monkeypatch.setattr(classical, "_load", lambda: {})
    rules._merge_classical()
    try:
        assert all(r["classical_status"] == "pending" for r in RULES.values())
        assert classical.summary()["classical_rules_pending"] == len(RULES)
    finally:
        monkeypatch.undo()
        classical.reload()
        rules._merge_classical()
    assert RULES["MG-L2-PA"]["classical_status"] == "location_confirmed"


# ------------------------------------------------------------ P3: 상담 품질
def test_same_chart_year_change_keeps_natal_features_but_changes_period_text():
    pre = make_pre()
    a = agent.answer(pre, "재물운", domains_=["wealth"], years=[2030])
    b = agent.answer(pre, "재물운", domains_=["wealth"], years=[2031])
    assert a["natal_feature_items"] == b["natal_feature_items"] and a["blocks"] == b["blocks"]
    ta = " ".join(s["text"] for p in a["periods"] for s in p["segments"])
    tb = " ".join(s["text"] for p in b["periods"] for s in p["segments"])
    assert ta != tb and "2030" in ta and "2031" in tb and "2031" not in ta
    assert pre["content_hash"] == a["ref"]["precommit_hash"] == b["ref"]["precommit_hash"]


def test_same_year_domain_change_changes_blocks_and_context():
    pre = make_pre()
    w = agent.answer(pre, "재물운", domains_=["wealth"], years=[2030])
    c = agent.answer(pre, "직업", domains_=["career"], years=[2030])
    assert w["blocks"][0]["domain"] == "wealth" and c["blocks"][0]["domain"] == "career"
    assert {i["structure"] for i in w["blocks"][0]["structures"]} != {i["structure"] for i in c["blocks"][0]["structures"]}
    assert w["periods"] == c["periods"]  # 같은 연도의 대운·세운 구간은 분야와 무관하게 동일


def test_multi_domain_answer_covers_each_domain_with_its_own_evidence():
    pre = make_pre()
    a = agent.answer(pre, "재물, 직업, 사업을 한꺼번에 알고 싶어요", domains_=["wealth", "career", "business"], years=[2030])
    assert [b["domain"] for b in a["blocks"]] == ["wealth", "career", "business"]
    doms = [p["domain"] for p in a["paragraphs"] if p["kind"] == "domain"]
    assert doms == ["wealth", "career", "business"] and a["consistency"]["ok"]
    assert len(a["followup_questions"]) <= 2


def test_question_context_uses_precommit_and_never_retrofits():
    pre = make_pre(domains=["wealth"])
    a = agent.answer(pre, "내년에 이직하고 싶어요", years=[2030])
    item = a["question_context"]["items"][0]
    assert item["event"] == "취업·이직" and item["in_precommit"] is False and "소급" in item["text"]
    pre2 = make_pre(domains=["career"])
    b = agent.answer(pre2, "내년에 이직하고 싶어요", years=[2030])
    it2 = b["question_context"]["items"][0]
    assert it2["in_precommit"] is True and "2030" in it2["text"] and "재생관" in it2["text"]


def test_school_conflict_is_explained_in_answer():
    found = None
    for y in range(1970, 2000):
        chart = calculate_chart(year=y, month=3, day=9, hour=10, gender="male").to_dict()
        pre = agent.build_precommit(chart, variant_id="v1", years=[2030], domains=["wealth"], depth="expert", input_fingerprint={"y": y})
        if any(p["relation"] == "충돌" for p in pre["natal_structure"]["schools"]["pairs"]):
            pre["content_hash"] = store.sha256({k: v for k, v in pre.items() if k != "content_hash"})
            found = pre
            break
    assert found
    a = agent.answer(found, "종합", domains_=["wealth"], depth="expert")
    sch = next(p for p in a["paragraphs"] if p["kind"] == "schools")["text"]
    assert "서로 겹치지 않습니다" in sch and "각각 설명" in sch
    assert a["expert"]["classical_conflicts"] and a["expert"]["profiles"]["pa"]


def test_followup_consistency_same_topic_same_claims(client):
    j = client.post("/api/v1/consultations", json=BODY).json()
    h = {"X-Consult-Token": j["access_token"]}
    q1 = client.post(f"/api/v1/consultations/{j['thread_id']}/ask", json={"question": "재물운이 궁금해요", "years": [2030]}, headers=h).json()
    q2 = client.post(f"/api/v1/consultations/{j['thread_id']}/ask", json={"question": "아까 재물운 더 자세히 알려주세요", "years": [2030]}, headers=h).json()
    ids = lambda a: sorted({c for p in a["paragraphs"] for c in p["claim_ids"]})
    assert ids(q1) == ids(q2) and q1["blocks"] == q2["blocks"] and q1["ref"] == q2["ref"]
    assert q1["natal_feature_items"] == q2["natal_feature_items"] and q2["consistency"]["ok"]


def test_consistency_check_catches_wrong_label_and_unknown_claim():
    pre = make_pre()
    a = agent.answer(pre, "재물운", domains_=["wealth"])
    bad = json.loads(json.dumps(a))
    bad["paragraphs"].append({"kind": "domain", "text": "'식상생재'(뚜렷(천간 노출))입니다.", "claim_ids": ["L3-999"]})
    probs = agent.compose.check_consistency(bad, pre)
    assert any("존재하지 않는 claim_id" in p for p in probs)
    real = next(s for s in pre["natal_structure"]["layer3"]["structures"] if s["name"] == "식상생재")
    if not real["label"].startswith("뚜렷"):
        assert any("라벨 불일치" in p for p in probs)


# ------------------------------------------------------------ 변조·이력·로그
def test_revision_is_separate_and_tamper_evident(client):
    j = client.post("/api/v1/consultations", json=BODY).json()
    tid, h = j["thread_id"], {"X-Consult-Token": j["access_token"]}
    orig = store.read_precommit(tid)["content_hash"]
    r = client.post(f"/api/v1/consultations/{tid}/reanalyze", json={"reason": "규칙 버전 점검", "pa_profile": "sanmyeongtonghoe_4"}, headers=h).json()
    assert r["revision"] == 1 and r["original_hash"] == orig and "ruleset" in r["diff"]
    assert store.read_precommit(tid)["content_hash"] == orig  # 원본 불변
    revs = client.get(f"/api/v1/consultations/{tid}/revisions", headers=h).json()
    assert revs["revisions"][0]["supersedes"] == orig and revs["revisions"][0]["reason"] == "규칙 버전 점검"
    path = store._tdir(tid) / "precommit_r1.json"
    os.chmod(path, 0o666)
    d = json.loads(path.read_text(encoding="utf-8"))
    d["depth"] = "summary"
    path.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(store.TamperError):
        store.read_precommit(tid, 1)
    assert store.read_precommit(tid)["content_hash"] == orig
    # 턴 기록에도 변경 이력이 남는다
    turns = client.get(f"/api/v1/consultations/{tid}", headers=h).json()["turns"]
    assert any(t["kind"] == "revision" for t in turns)


def test_reanalyze_profile_diff_reports_relation_change(client):
    pre = agent.build_precommit(calculate_chart(year=1984, month=6, day=15, hour=10, gender="male").to_dict(), variant_id="v1", years=[2030], domains=["wealth"], depth="summary", input_fingerprint={})
    pre["content_hash"] = store.sha256({k: v for k, v in pre.items() if k != "content_hash"})
    new, diff = agent.reanalyze(pre, reason="t", profiles={"pa": "sanmyeongtonghoe_4"})
    assert new["reanalysis"]["of"] == pre["content_hash"] and diff["ruleset"][0] == diff["ruleset"][1]


def test_no_personal_chart_in_logs(client, caplog):
    caplog.set_level(logging.DEBUG)
    j = client.post("/api/v1/consultations", json=BODY).json()
    tid, tok = j["thread_id"], j["access_token"]
    h = {"X-Consult-Token": tok}
    client.post(f"/api/v1/consultations/{tid}/ask", json={"question": "내 사주에서 재물운이 어때요 1984년생"}, headers=h)
    client.post(f"/api/v1/consultations/{tid}/reality", json={"kind": "event", "type": "취업·이직", "year": 2030, "note": "개인 메모"}, headers=h)
    client.post(f"/api/v1/consultations/{tid}/reanalyze", json={"reason": "점검"}, headers=h)
    pre = store.read_precommit(tid)
    pillars = [p for v in pre["chart"]["variants"] for p in v["pillars"].values()]
    blob = "\n".join(r.getMessage() for r in caplog.records)
    assert "consult.create" in blob and tid in blob
    for secret in pillars + [tok, "1984-06-15", "1984", "재물운이 어때요", "개인 메모"]:
        assert secret not in blob, secret


# ------------------------------------------------------------ LLM 선택 계층
class Good:
    name = "fake-good-v1"

    def narrate(self, payload):
        return "\n".join(p["text"] for p in payload["paragraphs"]) + "\n쉽게 정리하면 위 내용과 같습니다."


class GoodRephrase:
    name = "fake-good-v2"

    def narrate(self, payload):
        return "상담 결과를 다시 풀어 씁니다.\n\n" + "\n".join(reversed([p["text"] for p in payload["paragraphs"]]))


class Invent:
    name = "fake-bad"

    def __init__(self, extra):
        self.extra = extra

    def narrate(self, payload):
        return "\n".join(p["text"] for p in payload["paragraphs"]) + "\n" + self.extra


class Boom:
    name = "fake-boom"

    def narrate(self, payload):
        raise TimeoutError("timeout")


def det_answer():
    return agent.answer(make_pre(), "재물과 직업, 2030년", domains_=["wealth", "career"], years=[2030])


def test_llm_validated_output_is_used_and_deterministic_text_kept():
    a = det_answer()
    r = llm.with_llm(a, Good(), force=True)
    assert r["llm"] == {"used": True, "status": "validated", "model": "fake-good-v1", "problems": []}
    assert r["narrative"] == a["narrative"] and r["narrative_final"] != a["narrative"] and "쉽게 정리하면" in r["narrative_final"]


@pytest.mark.parametrize("extra,expect", [
    ("이 분은 도화살과 천을귀인이 있어 연애운이 좋습니다.", "근거 없는 명리 용어"),
    ("2045년에 큰 변화가 있습니다.", "근거 없는 연도"),
    ("근거는 L3-777 입니다.", "존재하지 않는 claim_id"),
    ("일주가 乙卯라서 성격이 급합니다.", "근거 없는 간지"),
    ("반드시 승진합니다.", "금지 표현"),
    ("이 해에는 확실히 재물이 늘어납니다.", "단정"),
])
def test_llm_invented_claims_fail_validation_and_fall_back(extra, expect):
    a = det_answer()
    r = llm.with_llm(a, Invent(extra), force=True)
    assert r["llm"]["used"] is False and r["llm"]["status"] == "failed_validation_fallback"
    assert any(expect in p for p in r["llm"]["problems"]), r["llm"]["problems"]
    assert r["narrative_final"] == a["narrative"]  # 설명 가능한 결정론적 출력 유지


def test_llm_errors_and_default_disabled_fall_back():
    a = det_answer()
    assert llm.with_llm(a, Boom(), force=True)["llm"]["status"] == "error_fallback"
    assert llm.with_llm(a, Good())["llm"]["status"] == "disabled"  # CONSULT_LLM 기본 off
    assert llm.with_llm(a, None, force=True)["llm"]["status"] == "disabled"
    assert llm.with_llm(a, Good(), force=True)["narrative_final"] != ""


def test_model_change_changes_text_but_not_facts():
    a = det_answer()
    r1 = llm.with_llm(a, Good(), force=True)
    r2 = llm.with_llm(a, GoodRephrase(), force=True)
    assert r1["narrative_final"] != r2["narrative_final"] and r1["llm"]["model"] != r2["llm"]["model"]
    assert r1["llm"]["used"] and r2["llm"]["used"]
    assert r1["paragraphs"] == r2["paragraphs"] and r1["ref"] == r2["ref"] and r1["blocks"] == r2["blocks"]  # 사실·근거는 모델과 무관
    f1, f2 = llm.allowed_from_answer(r1), llm.allowed_from_answer(r2)
    assert (f1.terms, f1.ganzhi, f1.years, f1.claim_ids) == (f2.terms, f2.ganzhi, f2.years, f2.claim_ids)


def test_llm_text_cannot_widen_allowed_facts_via_disclaimer_path():
    a = det_answer()
    allowed = llm.allowed_from_answer(a)
    assert 2030 in allowed.years and not any(g for g in allowed.ganzhi if g not in json.dumps(a, ensure_ascii=False))
    assert llm.validate_llm_text("", allowed) == ["빈 출력"]
