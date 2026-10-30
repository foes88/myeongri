"""v7.2 회원·저장·격리·rate limit·삭제 테스트. 가상 입력만 사용. 매 테스트마다 메모리 DB 와 새 제한기를 쓴다."""
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.accounts import api as A
from app.accounts.ratelimit import RateLimiter
from app.accounts.repo import SqliteRepo
from app.main import app

PW = "correct-horse-9"
REQ = {"calendar": "solar", "birth_date": "1984-06-15", "birth_time": "10:00", "gender": "male", "birth_place": "서울특별시",  # 가상 입력
       "years": [2030], "domains": ["overall", "wealth"], "question": "2030년 재물 흐름이 궁금합니다"}


PG_URL = os.environ.get("PG_TEST_URL")  # 예: postgresql://postgres:***@127.0.0.1:55499/myeongri_test (로컬 컨테이너). 없으면 Postgres 변형은 건너뜀


@pytest.fixture(params=["sqlite", "postgres"])
def c(request):
    if request.param == "postgres":
        if not PG_URL:
            pytest.skip("PG_TEST_URL 없음")
        from app.accounts.pg_repo import PostgresRepo
        repo = PostgresRepo(PG_URL, schema="t_" + uuid.uuid4().hex[:12])
        A.configure(repo, RateLimiter())
        yield TestClient(app)
        repo.drop_schema()
        return
    A.configure(SqliteRepo(":memory:"), RateLimiter())
    yield TestClient(app)


def reg(c, email="a@example.com", pw=PW):
    r = c.post("/api/v1/auth/register", json={"email": email, "password": pw})
    assert r.status_code == 201, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def test_register_login_logout_and_session_checks(c):
    h = reg(c)
    assert c.get("/api/v1/me", headers=h).json()["email"] == "a@example.com"
    assert c.get("/api/v1/me").status_code == 401 and c.get("/api/v1/me", headers={"Authorization": "Bearer nope"}).status_code == 401
    t = c.post("/api/v1/auth/login", json={"email": "a@example.com".replace("a", "A", 1), "password": PW}).json()["token"]  # 대소문자 정규화 확인
    c.post("/api/v1/auth/logout", headers={"Authorization": "Bearer " + t})
    assert c.get("/api/v1/me", headers={"Authorization": "Bearer " + t}).status_code == 401  # 로그아웃한 토큰은 무효


def test_password_policy_duplicate_and_no_account_enumeration(c):
    assert c.post("/api/v1/auth/register", json={"email": "b@example.com", "password": "short1"}).status_code == 422
    assert c.post("/api/v1/auth/register", json={"email": "bad", "password": PW}).status_code == 422
    reg(c)
    assert c.post("/api/v1/auth/register", json={"email": "a@example.com", "password": PW}).status_code == 409
    r1 = c.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "wrong-pass-1"})
    r2 = c.post("/api/v1/auth/login", json={"email": "zz@example.com", "password": "wrong-pass-1"})
    assert r1.status_code == r2.status_code == 401 and r1.json() == r2.json()  # 계정 존재 여부를 알려 주지 않음


def test_login_brute_force_is_rate_limited_and_resets_on_success(c):
    reg(c)
    codes = [c.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "bad-pass-123"}).status_code for _ in range(7)]
    assert codes[:5] == [401] * 5 and codes[5:] == [429, 429]
    assert c.post("/api/v1/auth/login", json={"email": "a@example.com", "password": PW}).status_code == 429  # 잠금 중에는 올바른 비밀번호도 거절


def test_save_reopen_follow_up_with_context_and_export(c):
    h = reg(c)
    r = c.post("/api/v1/reports", headers=h, json={"title": "내 2030 분석", "request": REQ})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    assert r.json()["answer"]["synthesis"]["readings"]
    lst = c.get("/api/v1/reports", headers=h).json()["reports"]
    assert [x["id"] for x in lst] == [rid] and lst[0]["title"] == "내 2030 분석"
    # 재열람: 저장된 답변과 사전 기록 요약이 그대로
    g = c.get(f"/api/v1/reports/{rid}", headers=h).json()
    assert g["answer"]["synthesis"]["headline"] == r.json()["answer"]["synthesis"]["headline"] and g["precommit"]["content_hash"] == r.json()["precommit"]["content_hash"]
    # 후속 질문: 분야·연도를 비우면 맥락 유지
    a1 = c.post(f"/api/v1/reports/{rid}/ask", headers=h, json={"question": "사업 쪽은 어떻게 보이나요?"}).json()
    assert a1["turn"] == 1 and 2030 in a1["answer"]["years"] and "business" in a1["answer"]["domains"]
    a2 = c.post(f"/api/v1/reports/{rid}/ask", headers=h, json={"question": "그럼 직업은요?", "years": [2031]}).json()
    assert a2["turn"] == 2 and a2["answer"]["years"] == [2031]
    ev = c.post(f"/api/v1/reports/{rid}/reality", headers=h, json={"kind": "event", "type": "취업·이직", "year": 2030}).json()
    assert ev["turn"] == 3 and ev["outcome"] in ("consistent", "inconsistent", "not_judged")
    turns = c.get(f"/api/v1/reports/{rid}", headers=h).json()["turns"]
    assert [t["kind"] for t in turns] == ["answer", "answer", "reality"]
    # 원본 사전 분석 기록은 후속 상담으로 바뀌지 않는다
    assert c.get(f"/api/v1/reports/{rid}", headers=h).json()["precommit"]["content_hash"] == r.json()["precommit"]["content_hash"]
    md = c.get(f"/api/v1/reports/{rid}/export", headers=h)
    assert md.status_code == 200 and "# 내 2030 분석" in md.text and "후속 질문 1" in md.text and "예측하거나 결과를 보장하지 않습니다" in md.text
    assert "1984-06-15" not in md.text  # 출생 원문 미포함
    assert c.get(f"/api/v1/reports/{rid}/export?format=json", headers=h).status_code == 200


def test_user_isolation_other_user_gets_404_everywhere(c):
    h1, h2 = reg(c, "a@example.com"), reg(c, "b@example.com")
    rid = c.post("/api/v1/reports", headers=h1, json={"request": REQ}).json()["id"]
    assert c.get("/api/v1/reports", headers=h2).json()["reports"] == []
    for method, path, kw in (("get", f"/api/v1/reports/{rid}", {}), ("post", f"/api/v1/reports/{rid}/ask", {"json": {"question": "q?"}}),
                             ("post", f"/api/v1/reports/{rid}/reality", {"json": {"kind": "event", "type": "취업·이직", "year": 2030}}), ("get", f"/api/v1/reports/{rid}/export", {}),
                             ("delete", f"/api/v1/reports/{rid}", {})):
        r = getattr(c, method)(path, headers=h2, **kw)
        assert r.status_code == 404, (method, path, r.status_code)
    assert c.get(f"/api/v1/reports/{rid}", headers=h1).status_code == 200  # 소유자는 영향 없음
    assert c.get(f"/api/v1/reports/{'0' * 32}", headers=h1).status_code == 404


def _raw(repo) -> bytes:
    if hasattr(repo, "raw_blobs"):
        return repo.raw_blobs()
    db = repo.db
    return b"".join(bytes(r[0]) for r in db.execute("SELECT blob FROM reports").fetchall()) + b"".join(bytes(r[0]) for r in db.execute("SELECT email_enc FROM users").fetchall())


def _count(repo, t) -> int:
    return repo.count(t) if hasattr(repo, "count") else repo.db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]


def test_data_is_encrypted_at_rest_and_email_not_plaintext(c):
    h = reg(c)
    c.post("/api/v1/reports", headers=h, json={"request": REQ})
    raw = _raw(A.repo())
    assert b"natal_structure" not in raw and b"a@example.com" not in raw


def test_delete_report_and_account_remove_everything(c):
    h = reg(c)
    rid = c.post("/api/v1/reports", headers=h, json={"request": REQ}).json()["id"]
    c.post(f"/api/v1/reports/{rid}/ask", headers=h, json={"question": "q?"})
    assert c.delete(f"/api/v1/reports/{rid}", headers=h).status_code == 204 and c.get(f"/api/v1/reports/{rid}", headers=h).status_code == 404
    rid2 = c.post("/api/v1/reports", headers=h, json={"request": REQ}).json()["id"]
    assert c.request("DELETE", "/api/v1/me", headers=h, json={"password": "wrong-pass-1"}).status_code == 403
    assert c.request("DELETE", "/api/v1/me", headers=h, json={"password": PW}).status_code == 204
    for t in ("users", "sessions", "reports", "turns"):
        assert _count(A.repo(), t) == 0, t
    assert c.get("/api/v1/me", headers=h).status_code == 401 and rid2
    assert not any("@" in (e["detail"] or "") for e in A.repo().audit_events())  # 감사 로그에 개인정보 없음


def test_daily_limit_request_size_and_validation(c, monkeypatch):
    h = reg(c)
    assert c.post("/api/v1/reports", headers=h, json={"request": {"birth_date": "x" * 70000}}).status_code == 413
    assert c.post("/api/v1/reports", headers=h, json={"request": {**REQ, "years": [1800]}}).status_code == 422
    monkeypatch.setattr(A, "FREE_DAILY_REPORTS", 2)
    assert [c.post("/api/v1/reports", headers=h, json={"request": REQ}).status_code for _ in range(3)] == [201, 201, 429]
    assert c.post("/api/v1/reports", json={"request": REQ}).status_code == 401  # 비로그인 저장 불가


def test_session_expiry(c, monkeypatch):
    h = reg(c)
    r = A.repo()
    (r.db.execute("UPDATE sessions SET expires_at=1") if hasattr(r, "db") else r._q("UPDATE sessions SET expires_at=1"))
    assert c.get("/api/v1/me", headers=h).status_code == 401


def test_cors_allows_authorization_header_only_for_configured_origins(c):
    r = c.options("/api/v1/me", headers={"Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "Authorization"})
    assert r.status_code == 200 and "authorization" in r.headers["access-control-allow-headers"].lower()
    r = c.options("/api/v1/me", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in r.headers


def test_accounts_are_disabled_in_production_without_explicit_flag(c, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("ACCOUNTS_ENABLED", raising=False)
    assert c.get("/api/v1/health").json()["accounts"] is False
    r = c.post("/api/v1/auth/register", json={"email": "p@example.com", "password": PW})
    assert r.status_code == 503 and r.json()["detail"]["code"] == "ACCOUNTS_DISABLED"
    monkeypatch.setenv("ACCOUNTS_ENABLED", "1")
    assert c.get("/api/v1/health").json()["accounts"] is True


def test_production_requires_data_key_not_a_file_key(monkeypatch):
    from app.accounts import crypto
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("APP_DATA_KEY", raising=False)
    with pytest.raises(RuntimeError):
        crypto.encrypt(b"x")


@pytest.mark.skipif(not PG_URL, reason="PG_TEST_URL 없음")
def test_postgres_persists_across_instances_serializes_turns_and_cascades():
    import concurrent.futures as cf

    from app.accounts.pg_repo import PostgresRepo
    schema = "t_" + uuid.uuid4().hex[:12]
    r1 = PostgresRepo(PG_URL, schema=schema)
    try:
        uid = r1.create_user("pg@example.com", "h")
        rid = r1.save_report(uid, "t", {"years": [2030]}, {"pre": {}, "answer": {}})
        # 앱 재시작처럼 새 인스턴스를 만들어도 데이터가 남아 있다(서버리스 파일 저장소와의 차이)
        r2 = PostgresRepo(PG_URL, schema=schema)
        assert r2.get_report(uid, rid)["title"] == "t" and r2.user_by_email("pg@example.com")["id"] == uid
        # 같은 리포트에 동시에 질문해도 번호가 겹치지 않는다
        with cf.ThreadPoolExecutor(8) as ex:
            ns = list(ex.map(lambda i: r2.add_turn(uid, rid, "answer", {"i": i}), range(12)))
        assert sorted(ns) == list(range(1, 13))
        assert r2.add_turn("someone-else", rid, "answer", {}) is None  # 소유자가 아니면 추가 불가
        r2.delete_user(uid)
        assert (r2.count("users"), r2.count("reports"), r2.count("turns"), r2.count("sessions")) == (0, 0, 0, 0)
    finally:
        r1.drop_schema()
