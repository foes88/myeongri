"""일회성 분석 API: 저장 없음, 로그 비노출, 캐시 금지, 입력 검증, 변형 선택."""
import json
import logging
import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

c = TestClient(app)
B = {"birth_date": "1984-06-15", "birth_time": "10:00", "gender": "male", "years": [2030], "domains": ["overall", "wealth"], "depth": "detailed"}  # 가상 입력


def test_analyze_returns_report_without_storing(tmp_path, monkeypatch):
    monkeypatch.setenv("CONSULT_DIR", str(tmp_path / "consult"))
    r = c.post("/api/v1/oneshot/analyze", json=B)
    assert r.status_code == 200
    j = r.json()
    assert j["stored"] is False and j["precommit"]["pillars"] and j["answer"]["paragraphs"] and j["answer"]["classical_basis"]
    assert not (tmp_path / "consult").exists() or not list((tmp_path / "consult").iterdir())  # 어떤 저장도 없음
    assert "access_token" not in json.dumps(j) and "thread_id" not in json.dumps(j)
    assert r.headers["cache-control"] == "no-store"


def test_ask_and_reality_are_stateless_and_deterministic():
    a = c.post("/api/v1/oneshot/ask", json={**B, "question": "재물운이 궁금해요"}).json()
    b = c.post("/api/v1/oneshot/ask", json={**B, "question": "재물운이 궁금해요"}).json()
    assert a["paragraphs"] == b["paragraphs"] and not a["refused"]
    ev = c.post("/api/v1/oneshot/reality", json={**B, "event": {"kind": "event", "type": "취업·이직", "year": 2030}}).json()
    assert ev["outcome"] in ("consistent", "inconsistent", "not_judged")
    ev2 = c.post("/api/v1/oneshot/reality", json={**B, "event": {"kind": "event", "type": "결혼", "year": 2030}}).json()
    assert ev2["outcome"] == "not_judged"


def test_refusals_and_validation():
    assert c.post("/api/v1/oneshot/ask", json={**B, "question": "암에 걸릴까요"}).json()["refused"] is True
    assert c.post("/api/v1/oneshot/ask", json={**B, "question": "  "}).status_code == 422
    assert c.post("/api/v1/oneshot/analyze", json={**B, "years": [1800]}).status_code == 422
    assert c.post("/api/v1/oneshot/analyze", json={**B, "domains": ["nope"]}).status_code == 422
    assert c.post("/api/v1/oneshot/analyze", json={**B, "years": list(range(2020, 2032))}).status_code == 422
    assert c.post("/api/v1/oneshot/analyze", json={**B, "birth_date": "1850-01-01"}).status_code == 422


def test_variant_must_be_chosen():
    body = {"birth_date": "2000-01-01", "birth_time": "19:25", "gender": "male", "years": [2030]}  # 가상 입력
    r = c.post("/api/v1/oneshot/analyze", json=body)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "VARIANT_REQUIRED"
    ok = c.post("/api/v1/oneshot/analyze", json={**body, "variant_id": "v2"})
    assert ok.status_code == 200 and ok.json()["precommit"]["variant_id"] == "v2"


def test_no_birth_data_in_logs(caplog):
    caplog.set_level(logging.DEBUG)
    c.post("/api/v1/oneshot/analyze", json={**B, "question": "개인 질문 원문"})
    blob = "\n".join(r.getMessage() for r in caplog.records)
    for secret in ("1984-06-15", "10:00", "개인 질문 원문"):  # 가상 입력 값
        assert secret not in blob


def test_stored_consultation_endpoints_remain_separate():
    assert c.post("/api/v1/consultations/" + "a" * 32 + "/ask", json={"question": "x"}).status_code in (403, 422)
