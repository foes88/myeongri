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


# ---- 후속 질문 맥락(규칙 기반 답변; 자유 대화형 AI 아님)
def _ask(c, h, rid, q):
    r = c.post(f"/api/v1/reports/{rid}/ask", json={"question": q}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()["answer"]["qa"]


def test_followups_keep_context_and_new_intents(c):
    h = reg(c)
    rid = c.post("/api/v1/reports", json={"title": "x", "request": {**REQ, "years": [2027, 2028, 2029, 2030], "domains": ["overall", "wealth", "career"]}}, headers=h).json()["id"]
    q1 = _ask(c, h, rid, "2029년 재물운 자세히 알려줘")
    assert q1["kind"] == "detail" and q1["domain"] == "wealth" and q1["year"] == 2029
    q2 = _ask(c, h, rid, "앞에서 말한 결론은 왜 그렇게 판단했어?")      # 직전 답변의 분야·연도를 이어받는다
    assert q2["kind"] == "recap_why" and q2["domain"] == "wealth" and q2["year"] == 2029 and q2["points"]
    q3 = _ask(c, h, rid, "2028년 이직 고려할 점은?")
    assert q3["kind"] == "consider" and q3["domain"] == "career" and q3["year"] == 2028 and "보장하지 않" in q3["text"]
    q4 = _ask(c, h, rid, "재물과 직업은 어떤 관계야?")
    assert q4["kind"] == "relation" and len(q4["points"]) == 2
    q5 = _ask(c, h, rid, "2027년과 2030년은 뭐가 달라? 차이를 알려줘")
    assert q5["kind"] == "compare" and q5["years"] == [2027, 2030]


def test_this_year_outside_range_is_stated_not_substituted(c):
    import datetime
    now = datetime.date.today().year
    h = reg(c)
    rid = c.post("/api/v1/reports", json={"title": "x", "request": {**REQ, "years": [now + 5], "domains": ["overall", "career"]}}, headers=h).json()["id"]
    q = _ask(c, h, rid, "올해 이직 고려할 점은?")
    assert q["kind"] == "unsupported" and str(now) in q["text"] and "범위에 없" in q["text"]


def test_followup_never_promises_outcomes(c):
    h = reg(c)
    rid = c.post("/api/v1/reports", json={"title": "x", "request": {**REQ, "years": [2028], "domains": ["overall", "career"]}}, headers=h).json()["id"]
    for q in ("2028년에 이직하면 성공해?", "2028년 이직 고려할 점은?"):
        t = _ask(c, h, rid, q)
        s = t["text"] + " ".join(t.get("points", []))
        assert not any(w in s for w in ("반드시", "틀림없", "100%", "확실히 성공"))
