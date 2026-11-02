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


# ---- 계산 상태 안내(쉬운 말)
from app.consult import verdict as V
import re as _re

BASE = {"verification": {"may_claim_verified": False, "independent_crosscheck": {"agree": True}, "nearest_jie_minutes": 13000.0, "ambiguity": {"ambiguous": False}}, "variants_count": 1}


def test_calc_notice_levels_in_plain_words():
    ok = V.calc_notice(BASE)
    assert ok["level"] == "ok" and any("검증 완료" in t for t in ok["items"])           # 미검증 부분은 숨기지 않는다
    near = V.calc_notice({**BASE, "verification": {**BASE["verification"], "nearest_jie_minutes": 25.0}})
    assert near["level"] == "check" and any("절기" in t and "25분" in t for t in near["items"])
    bad = V.calc_notice({**BASE, "verification": {**BASE["verification"], "independent_crosscheck": {"agree": False}}})
    assert bad["level"] == "caution"
    multi = V.calc_notice({**BASE, "variants_count": 2})
    assert multi["level"] == "check"
    assert V.calc_notice({}) is None
    txt = " ".join(ok["items"] + near["items"] + bad["items"] + [ok["title"]])
    assert not _re.search(r"PILLARS|PROFILE|V[0-9]\b|lunar-python|golden|shouxing|Skyfield", txt)   # 내부 등급·도구명 비노출


@pytest.mark.public_view
def test_public_precommit_includes_calc_and_no_internal_fields(c):
    h = reg(c)
    r = c.post("/api/v1/reports", json={"title": "x", "request": REQ}, headers=h).json()
    pc = r["precommit"]
    assert pc["calc"]["title"].startswith("계산 상태") and pc["calc"]["items"]
    assert not {"verification", "content_hash", "ruleset_version", "calculation_profile_id"} & set(pc)


# ---- 개인용 배포 보호: 가입 모드
def _reg(c, **kw):
    return c.post("/api/v1/auth/register", json={"email": "z@example.com", "password": "correct-horse-9", **kw})


def test_registration_modes(c, monkeypatch):
    monkeypatch.delenv("ACCOUNTS_REGISTRATION", raising=False)
    assert A.registration_mode() == "open"
    monkeypatch.setenv("ACCOUNTS_REGISTRATION", "closed")
    r = _reg(c)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "REGISTRATION_CLOSED"
    monkeypatch.setenv("ACCOUNTS_REGISTRATION", "invite")
    monkeypatch.setenv("ACCOUNTS_INVITE_CODE", "open-sesame-77")
    assert _reg(c).status_code == 403 and _reg(c, invite="wrong").status_code == 403
    assert _reg(c, invite="open-sesame-77").status_code == 201
    monkeypatch.delenv("ACCOUNTS_INVITE_CODE")
    assert A.registration_mode() == "closed"          # 코드 없는 invite 는 닫힘으로 취급
    monkeypatch.setenv("ACCOUNTS_REGISTRATION", "typo")
    assert A.registration_mode() == "closed"          # 알 수 없는 값도 닫힘


def test_owner_can_login_when_closed(c, monkeypatch):
    from tools import create_owner
    monkeypatch.setenv("ACCOUNTS_REGISTRATION", "closed")
    create_owner.create("owner@example.com", "correct-horse-9")
    r = c.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "correct-horse-9"})
    assert r.status_code == 200
    with pytest.raises(SystemExit):
        create_owner.create("owner@example.com", "correct-horse-9")
    with pytest.raises(SystemExit):
        create_owner.create("o2@example.com", "short")


# ---- 본인 평가 기록 / 공개 응답에서도 보기 복원이 되는지
@pytest.mark.public_view
def test_feedback_and_public_turns_keep_view_flag(c):
    h = reg(c)
    rid = mk(c, h)
    assert c.post(f"/api/v1/reports/{rid}/analyze", json={"years": [2028]}, headers=h).status_code == 200
    assert c.post(f"/api/v1/reports/{rid}/feedback", json={"rating": 4, "target": "reading", "note": "읽기 쉬웠다"}, headers=h).status_code == 201
    assert c.post(f"/api/v1/reports/{rid}/feedback", json={"rating": 9}, headers=h).status_code == 422
    g = c.get(f"/api/v1/reports/{rid}", headers=h).json()
    kinds = [(t["kind"], t["body"].get("view")) for t in g["turns"]]
    assert ("answer", True) in kinds and any(k == "feedback" for k, _ in kinds)
    md = c.get(f"/api/v1/reports/{rid}/export?format=md", headers=h)
    assert md.status_code == 200 and "다시 풀이" in md.text
    h2 = reg(c, "b@example.com")
    assert c.post(f"/api/v1/reports/{rid}/feedback", json={"rating": 3}, headers=h2).status_code == 404


def test_every_domain_headline_names_its_own_domain_not_wealth():
    """분야별 헤드라인 문구가 없는 톤(steady/balance)에서 재물 문장을 빌려 쓰던 오류 회귀 방지."""
    from app import main as M
    from app.consult import agent, domains as D
    doms = [d for d in D.DOMAINS if d not in ("luck",)]
    for yrs in ([2027], [2028], [2030]):
        body = M.OneshotBody(calendar="solar", birth_date=f"{1991:04d}-{4:02d}-{7:02d}", birth_time=f"{10:02d}:{0:02d}", gender="male", birth_place="경기도 수원시", years=yrs, domains=doms, question="x")  # 가상 입력
        pre = M._oneshot_pre(body)
        v = agent.answer(pre, "종합 상담을 시작합니다", domains_=doms, years=yrs, depth="detailed")["verdict"]
        for b in v["blocks"]:
            if b["domain"] not in ("wealth", "overall", "business", "docs_realestate"):
                assert "재물 흐름" not in b["headline"], (b["domain"], b["headline"])
