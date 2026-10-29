"""Consult-Agent: 사전 기록 고정, 정·반 근거 상담, 사후 끼워 맞추기 방지, 접근 통제, 거절."""
import json
import os
import re
import stat

import pytest
from fastapi.testclient import TestClient

from app.consult import domains as D
from app.consult import store
from app.main import app
from app.report_checks import FORBIDDEN_PATTERNS

BODY = {"birth_date": "1984-06-15", "birth_time": "10:00", "gender": "male", "years": [2030], "domains": ["wealth", "career"], "depth": "detailed"}  # 가상 입력


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CONSULT_DIR", str(tmp_path / "consult"))
    return TestClient(app)


def create(client, **kw):
    r = client.post("/api/v1/consultations", json={**BODY, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def test_create_returns_precommit_before_any_reality_input(client):
    j = create(client)
    p = j["precommit"]
    assert len(p["content_hash"]) == 64 and p["ruleset_version"] and p["model_version"] and p["generated_at"] and p["calculation_profile_id"]
    pre = store.read_precommit(j["thread_id"])
    assert pre["reality_inputs_used"] is False and pre["input_hash"]
    assert pre["verification"]["status"] != "V1" and j["answer"]["limits"]


def test_precommit_is_write_once_and_tamper_evident(client):
    j = create(client)
    tid = j["thread_id"]
    with pytest.raises(PermissionError):
        store.overwrite_precommit(tid, {})
    path = store._tdir(tid) / "precommit.json"
    assert not (path.stat().st_mode & stat.S_IWUSR)
    os.chmod(path, 0o666)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["depth"] = "expert"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(store.TamperError):
        store.read_precommit(tid)


def test_birth_data_not_stored_by_default(client):
    j = create(client)
    pre = store.read_precommit(j["thread_id"])
    raw = json.dumps(pre, ensure_ascii=False)
    assert "1984-06-15" not in raw and "birth_date" not in raw
    assert "input" not in pre["chart"] and "normalized" not in pre["chart"]


def test_access_control(client):
    j = create(client)
    tid, tok = j["thread_id"], j["access_token"]
    assert client.post(f"/api/v1/consultations/{tid}/ask", json={"question": "재물운"}).status_code == 403
    assert client.post(f"/api/v1/consultations/{tid}/ask", json={"question": "재물운"}, headers={"X-Consult-Token": "x" * 32}).status_code == 403
    assert client.get(f"/api/v1/consultations/{tid}", headers={"X-Consult-Token": tok}).status_code == 200
    assert client.get("/api/v1/consultations/" + "a" * 32, headers={"X-Consult-Token": tok}).status_code == 403


def test_followup_gives_for_and_against_and_separates_advice(client):
    j = create(client)
    h = {"X-Consult-Token": j["access_token"]}
    r = client.post(f"/api/v1/consultations/{j['thread_id']}/ask", json={"question": "올해 재물운과 사업 어때요? 2030년이 궁금해요"}, headers=h).json()
    assert not r["refused"] and r["evidence_for"] and r["evidence_against"]
    assert r["life_advice"]["label"].startswith("현실 조언") and r["followup_questions"] and len(r["followup_questions"]) <= 2
    assert 2030 in r["years"] and r["periods"][0]["split"] is True and r["periods"][0]["precommitted"] is True
    assert "명리학은 과학적으로 검증된 미래 예측 방법이 아닙니다" in r["limits"][0]
    assert any("고전 원문 대조 전" in x for x in r["limits"])
    assert r["school_view"]


def test_depth_levels(client):
    j = create(client, depth="summary")
    h = {"X-Consult-Token": j["access_token"]}
    s = client.post(f"/api/v1/consultations/{j['thread_id']}/ask", json={"question": "재물운", "depth": "summary"}, headers=h).json()
    e = client.post(f"/api/v1/consultations/{j['thread_id']}/ask", json={"question": "재물운", "depth": "expert"}, headers=h).json()
    assert s["school_view"] is None and "expert" not in s and e["expert"]["rule_ids"] and e["expert"]["claims"]


@pytest.mark.parametrize("q,kind", [("저 암에 걸릴까요?", "health"), ("언제 죽을까요", "death"), ("이 코인 대박 나나요", "investment"), ("승진 확정인가요", "certainty")])
def test_refuses_forbidden_questions(client, q, kind):
    j = create(client)
    r = client.post(f"/api/v1/consultations/{j['thread_id']}/ask", json={"question": q}, headers={"X-Consult-Token": j["access_token"]}).json()
    assert r["refused"] and r["kind"] == kind and r["alternative"]


def test_reality_input_never_changes_precommit_and_is_classified(client):
    j = create(client)
    tid, h = j["thread_id"], {"X-Consult-Token": j["access_token"]}
    before = store.read_precommit(tid)
    judged_before = json.dumps(before["event_judgements"], sort_keys=True)
    a = client.post(f"/api/v1/consultations/{tid}/reality", json={"kind": "event", "type": "취업·이직", "year": 2030}, headers=h).json()
    b = client.post(f"/api/v1/consultations/{tid}/reality", json={"kind": "event", "type": "결혼", "year": 2030}, headers=h).json()
    c = client.post(f"/api/v1/consultations/{tid}/reality", json={"kind": "event", "type": "취업·이직", "year": 2035}, headers=h).json()
    d = client.post(f"/api/v1/consultations/{tid}/reality", json={"kind": "condition", "type": "출생시각 정정"}, headers=h).json()
    assert a["outcome"] in ("consistent", "inconsistent")
    assert b["outcome"] == "not_judged" and "새로 해석해 적중으로 세지 않습니다" in b["explanation"]
    assert c["outcome"] == "not_judged" and d["outcome"] == "condition_changed" and "새 상담" in d["explanation"]
    after = store.read_precommit(tid)
    assert after["content_hash"] == before["content_hash"] and json.dumps(after["event_judgements"], sort_keys=True) == judged_before
    turns = client.get(f"/api/v1/consultations/{tid}", headers=h).json()["turns"]
    assert [t["kind"] for t in turns] == ["answer", "reality_input", "reality_input", "reality_input", "reality_input"]
    assert "결혼" not in after["event_judgements"]


def test_no_hit_rate_or_accuracy_claims(client):
    j = create(client)
    h = {"X-Consult-Token": j["access_token"]}
    client.post(f"/api/v1/consultations/{j['thread_id']}/reality", json={"kind": "event", "type": "취업·이직", "year": 2030}, headers=h)
    blob = json.dumps(client.get(f"/api/v1/consultations/{j['thread_id']}", headers=h).json(), ensure_ascii=False)
    assert not re.search(r"hit_rate|accuracy|적중률", blob)


def test_answers_never_contain_forbidden_patterns(client):
    j = create(client, domains=["overall", "wealth", "career", "business", "docs_realestate", "luck"], depth="expert", years=[2030, 2031])
    h = {"X-Consult-Token": j["access_token"]}
    for q in ("종합운", "재물", "직업 승진", "사업 창업", "계약 부동산", "대운 세운 2031년"):
        r = client.post(f"/api/v1/consultations/{j['thread_id']}/ask", json={"question": q, "depth": "expert"}, headers=h).json()
        text = json.dumps(r, ensure_ascii=False)
        for pat in FORBIDDEN_PATTERNS:
            assert not re.search(pat, text), (q, pat)


def test_variant_must_be_chosen(client):
    r = client.post("/api/v1/consultations", json={"birth_date": "2000-01-01", "birth_time": "19:25", "gender": "male", "years": [2030]})  # 가상 입력
    assert r.status_code == 409 and r.json()["detail"]["code"] == "VARIANT_REQUIRED" and len(r.json()["detail"]["variants"]) >= 2
    ok = client.post("/api/v1/consultations", json={"birth_date": "2000-01-01", "birth_time": "19:25", "gender": "male", "years": [2030], "variant_id": "v2"})
    assert ok.status_code == 200 and ok.json()["precommit"]["variant_id"] == "v2"


def test_period_outside_precommit_is_marked(client):
    j = create(client)
    r = client.post(f"/api/v1/consultations/{j['thread_id']}/ask", json={"question": "2033년 재물운"}, headers={"X-Consult-Token": j["access_token"]}).json()
    assert r["periods"][0]["year"] == 2033 and r["periods"][0]["precommitted"] is False


def test_reopen_and_delete(client):
    j = create(client)
    tid, h = j["thread_id"], {"X-Consult-Token": j["access_token"]}
    g = client.get(f"/api/v1/consultations/{tid}", headers=h).json()
    assert g["precommit_summary"]["content_hash"] == j["precommit"]["content_hash"] and g["turns"]
    assert client.delete(f"/api/v1/consultations/{tid}", headers=h).status_code == 204
    assert client.get(f"/api/v1/consultations/{tid}", headers=h).status_code == 403


def test_routing_helpers():
    assert D.route("올해 이직하고 싶어요", None)[0] == "career" and "docs_realestate" in D.route("전세 계약", None)
    assert D.extract_years("2030년과 2031년") == [2030, 2031]
