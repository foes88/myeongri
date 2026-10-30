"""실행 중인 서버의 회원 여정 종단 점검(가상 입력, 테스트 계정은 끝에 삭제). 사용: python -m tools.smoke_member http://127.0.0.1:8000
가입 → 분석 저장 → 목록 → 재열람 → 후속 질문 → 내보내기 → 다른 계정 접근 차단 → 로그아웃 → 계정 삭제 → 삭제 확인."""
import json
import sys
import urllib.error
import urllib.request
import uuid

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
REQ = {"calendar": "solar", "birth_date": "1984-06-15", "birth_time": "10:00", "gender": "male", "birth_place": "서울특별시",  # 가상 입력
       "years": [2030], "domains": ["overall", "wealth", "career"], "question": "2030년 재물과 직업 흐름이 궁금합니다"}
PW = "smoke-" + uuid.uuid4().hex[:10] + "9"


def call(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = "Bearer " + token
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE + path, data=data, method=method, headers=h), timeout=60) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw and r.headers.get("content-type", "").startswith("application/json") else raw.decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw.decode("utf-8", "replace")


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {extra}" if extra and not cond else ""))
    if not cond:
        sys.exit(1)


def main():
    s, h = call("GET", "/api/v1/health")
    check("서버·회원 기능 사용 가능", s == 200 and h.get("accounts") is True, str(h))
    ea, eb = f"smoke-a-{uuid.uuid4().hex[:8]}@example.com", f"smoke-b-{uuid.uuid4().hex[:8]}@example.com"
    s, a = call("POST", "/api/v1/auth/register", {"email": ea, "password": PW})
    check("가입(A)", s == 201, str(a))
    s, b = call("POST", "/api/v1/auth/register", {"email": eb, "password": PW})
    check("가입(B)", s == 201, str(b))
    ta, tb = a["token"], b["token"]
    s, r = call("POST", "/api/v1/reports", {"title": "점검 리포트", "request": REQ}, ta)
    check("분석 저장", s == 201 and r["answer"]["synthesis"]["readings"] and r["answer"]["consultation"]["validated"], str(r)[:200])
    rid = r["id"]
    s, lst = call("GET", "/api/v1/reports", token=ta)
    check("목록에 보임", s == 200 and [x["id"] for x in lst["reports"]] == [rid])
    s, g = call("GET", f"/api/v1/reports/{rid}", token=ta)
    check("재열람(저장된 결과 동일)", s == 200 and g["precommit"]["content_hash"] == r["precommit"]["content_hash"])
    s, q = call("POST", f"/api/v1/reports/{rid}/ask", {"question": "사업 쪽은 어떻게 보이나요?"}, ta)
    check("후속 질문(맥락 유지)", s == 200 and 2030 in q["answer"]["years"] and q["turn"] == 1, str(q)[:200])
    s, md = call("GET", f"/api/v1/reports/{rid}/export", token=ta)
    check("내보내기(.md, 출생 원문 없음)", s == 200 and "후속 질문 1" in md and "1984-06-15" not in md)
    s, _ = call("GET", f"/api/v1/reports/{rid}", token=tb)
    check("다른 계정 접근 차단(404)", s == 404)
    s, _ = call("GET", "/api/v1/reports")
    check("비로그인 접근 차단(401)", s == 401)
    s, _ = call("POST", "/api/v1/auth/logout", token=ta)
    check("로그아웃 후 토큰 무효", s == 204 and call("GET", "/api/v1/me", token=ta)[0] == 401)
    s, l = call("POST", "/api/v1/auth/login", {"email": ea, "password": PW})
    check("재로그인 후 같은 리포트 열람", s == 200 and call("GET", f"/api/v1/reports/{rid}", token=l["token"])[0] == 200)
    s, _ = call("DELETE", "/api/v1/me", {"password": PW}, l["token"])
    check("계정 삭제(A)", s == 204 and call("POST", "/api/v1/auth/login", {"email": ea, "password": PW})[0] == 401)
    call("DELETE", "/api/v1/me", {"password": PW}, tb)
    print("ALL PASS — 회원 여정 종단 점검 통과")


if __name__ == "__main__":
    main()
