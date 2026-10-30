"""v9.0 Personal Alpha: 저장된 명식 재분석(출생 정보 재입력 없음). 가상 입력만 사용."""
import pytest
from fastapi.testclient import TestClient

from app.accounts import api as A
from app.accounts.ratelimit import RateLimiter
from app.accounts.repo import SqliteRepo
from app.main import app
from tests.test_v72_accounts import REQ, reg


@pytest.fixture()
def c():
    A.configure(SqliteRepo(":memory:"), RateLimiter())
    return TestClient(app)


def mk(c, h):
    r = c.post("/api/v1/reports", json={"title": "내 명식", "request": REQ}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_analyze_new_years_without_birth_input_and_is_remembered(c):
    h = reg(c)
    rid = mk(c, h)
    r = c.post(f"/api/v1/reports/{rid}/analyze", json={"years": [2027, 2028, 2029, 2030, 2031]}, headers=h)
    assert r.status_code == 200, r.text
    a = r.json()["answer"]
    assert a["years"] == [2027, 2028, 2029, 2030, 2031] and a["verdict"]
    g = c.get(f"/api/v1/reports/{rid}", headers=h).json()
    view = [t for t in g["turns"] if t["body"].get("view")]
    assert view and view[-1]["body"]["years"] == [2027, 2028, 2029, 2030, 2031]
    # 후속 질문은 직전 보기(연도)를 이어받는다
    q = c.post(f"/api/v1/reports/{rid}/ask", json={"question": "이 시기에 재물은 어때요?"}, headers=h).json()
    assert q["answer"]["years"] == [2027, 2028, 2029, 2030, 2031]


def test_analyze_validation_and_isolation(c):
    h = reg(c)
    rid = mk(c, h)
    assert c.post(f"/api/v1/reports/{rid}/analyze", json={"years": [1800]}, headers=h).status_code == 422
    assert c.post(f"/api/v1/reports/{rid}/analyze", json={"years": []}, headers=h).status_code == 422
    h2 = reg(c, "b@example.com")
    assert c.post(f"/api/v1/reports/{rid}/analyze", json={"years": [2030]}, headers=h2).status_code == 404
    assert c.post(f"/api/v1/reports/{rid}/analyze", json={"years": [2030]}).status_code in (401, 403)


def test_saved_body_has_no_birth_input(c):
    h = reg(c)
    rid = mk(c, h)
    body = A.repo().get_report(A.current_user(h["Authorization"]), rid)["body"]
    import json
    t = json.dumps(body, ensure_ascii=False)
    assert REQ["birth_date"] not in t and REQ["birth_time"] not in t and "birth_place" not in t  # 가상 입력
