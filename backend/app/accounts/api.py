"""회원 API: 가입·로그인·세션, 분석 결과 저장·재열람·후속 질문·내보내기·삭제, 사용자별 격리, rate limit, 무료 사용량 제한.

- 인증: Authorization: Bearer <세션 토큰>. 쿠키를 쓰지 않으므로 CSRF 표면이 없다. 서버에는 토큰의 SHA-256 만 저장한다.
- 비밀번호: scrypt(솔트 포함). 로그인 실패는 이메일·IP 별로 제한한다. 오류 메시지는 계정 존재 여부를 알려 주지 않는다.
- 저장: 출생 원문은 저장하지 않는다(사전 분석 기록의 비식별 명식·구조·답변만). 본문은 Fernet 암호화. 로그에는 개인정보·질문 원문을 남기지 않는다.
- 사용자 격리: 모든 저장소 호출이 user_id 를 받는다. 다른 사용자의 리포트는 404 로만 응답한다(존재 여부 비공개).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import time
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from .ratelimit import RateLimiter
from .repo import DuplicateEmail, Repo, SqliteRepo



LOCAL_HOSTS = ("localhost", "127.", "0.0.0.0", "::1", "host.docker.internal", "myeongri-pg", "db:")


def _db_is_managed(url: str | None) -> tuple[bool, str]:
    """운영형 환경에서 허용되는 DB 인지: postgres 이고 로컬/컨테이너 주소가 아니며 TLS(sslmode=require 이상)를 요구."""
    if not url or not url.startswith(("postgres://", "postgresql://")):
        return False, "DATABASE_URL(Postgres)이 없음"
    host = url.split("@", 1)[-1].split("/", 1)[0].lower()
    if any(host.startswith(h) or h in host.split(":")[0] + ":" for h in LOCAL_HOSTS):
        return False, "로컬/컨테이너 DB 주소는 운영형 환경에서 사용할 수 없음"
    if "sslmode=require" not in url and "sslmode=verify" not in url:
        return False, "DATABASE_URL 에 sslmode=require 가 필요함"
    return True, ""


def accounts_status() -> dict:
    """회원 기능 사용 가능 여부와 사유. 로컬 개발은 기본 허용. Vercel·운영(APP_ENV=production)에서는 관리형 Postgres·암호화 키·명시적 플래그가 모두 있어야 한다
    (휘발성 파일 저장소나 로컬 DB 에 회원 데이터를 쓰지 않기 위함)."""
    prodlike = bool(os.environ.get("VERCEL")) or os.environ.get("APP_ENV") == "production"
    if not prodlike:
        return {"enabled": True, "reason": "local"}
    if os.environ.get("ACCOUNTS_ENABLED") != "1":
        return {"enabled": False, "reason": "ACCOUNTS_ENABLED=1 이 아님"}
    ok, why = _db_is_managed(os.environ.get("DATABASE_URL"))
    if not ok:
        return {"enabled": False, "reason": why}
    if not os.environ.get("APP_DATA_KEY"):
        return {"enabled": False, "reason": "APP_DATA_KEY 가 없음"}
    return {"enabled": True, "reason": "managed"}


def accounts_enabled() -> bool:
    return accounts_status()["enabled"]


def _gate() -> None:
    if not accounts_enabled():
        raise HTTPException(status_code=503, detail={"code": "ACCOUNTS_DISABLED", "message": "회원 기능은 아직 제공되지 않습니다."})


router = APIRouter(prefix="/api/v1", dependencies=[Depends(_gate)])
SESSION_TTL = float(os.environ.get("SESSION_TTL_SECONDS", 14 * 86400))
FREE_DAILY_REPORTS = int(os.environ.get("FREE_DAILY_REPORTS", 20))
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")

_repo: Repo | None = None
limiter = RateLimiter()


def configure(repo: Repo | None = None, rl: RateLimiter | None = None) -> None:
    """테스트·운영 구성에서 저장소와 제한기를 교체한다(운영: 관리형 DB·공유 제한기 어댑터)."""
    global _repo, limiter
    if repo is not None:
        _repo = repo
    if rl is not None:
        limiter = rl


def repo() -> Repo:
    global _repo
    if _repo is None:
        url = os.environ.get("DATABASE_URL")
        if url and url.startswith(("postgres://", "postgresql://")):
            from .pg_repo import PostgresRepo  # 지연 import: SQLite 만 쓰는 환경에서는 psycopg 가 필요 없다
            _repo = PostgresRepo(url, schema=os.environ.get("DATABASE_SCHEMA") or None)
        else:
            _repo = SqliteRepo()
    return _repo


# ------------------------------------------------------------------ 보안 유틸
def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return "scrypt$16384$8$1$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, dk = stored.split("$")
        got = hashlib.scrypt(pw.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(got, base64.b64decode(dk))
    except Exception:
        return False


def _tok_hash(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


def client_ip(req: Request) -> str:
    if os.environ.get("TRUST_PROXY") == "1" and req.headers.get("x-forwarded-for"):
        return req.headers["x-forwarded-for"].split(",")[0].strip()
    return req.client.host if req.client else "?"


def _ip_tag(req: Request) -> str:
    return hashlib.sha256(client_ip(req).encode()).hexdigest()[:10]  # 감사 로그에는 IP 원문 대신 짧은 해시만


def _limit(key: str, limit: int, window: float) -> None:
    ok, wait = limiter.check(key, limit, window)
    if not ok:
        raise HTTPException(status_code=429, detail={"code": "RATE_LIMITED", "message": "요청이 너무 많습니다. 잠시 후 다시 시도하세요.", "retry_after": wait},
                            headers={"Retry-After": str(wait)})


def current_user(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "로그인이 필요합니다."})
    uid = repo().session_user(_tok_hash(authorization[7:].strip()))
    if not uid:
        raise HTTPException(status_code=401, detail={"code": "SESSION_EXPIRED", "message": "세션이 없거나 만료되었습니다. 다시 로그인하세요."})
    return uid


# ------------------------------------------------------------------ 모델
class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=200)
    invite: str | None = Field(default=None, max_length=100)


def registration_mode() -> str:
    """개인용 배포 보호: open(기본) / invite(초대 코드 필요, ACCOUNTS_INVITE_CODE) / closed(가입 불가, tools/create_owner.py 로만 계정 생성).
    초대 코드가 설정되지 않은 invite 모드는 안전하게 closed 로 취급한다."""
    m = os.environ.get("ACCOUNTS_REGISTRATION", "open").strip().lower()
    if m not in ("open", "invite", "closed"):
        return "closed"
    if m == "invite" and not os.environ.get("ACCOUNTS_INVITE_CODE"):
        return "closed"
    return m


class DeleteMe(BaseModel):
    password: str = Field(max_length=200)


class ReportCreate(BaseModel):
    title: str = Field(default="", max_length=80)
    request: dict


class ReportAsk(BaseModel):
    focus_year: int | None = Field(default=None, ge=1901, le=2049)
    focus_domain: str | None = Field(default=None, max_length=30)
    focus_month: str | None = Field(default=None, max_length=10)
    question: str = Field(min_length=1, max_length=500)
    years: list[int] | None = Field(default=None, max_length=10)
    domains: list[str] | None = Field(default=None, max_length=12)
    depth: Literal["summary", "detailed", "expert"] | None = None


class ReportAnalyze(BaseModel):
    years: list[int] = Field(min_length=1, max_length=10)
    domains: list[str] | None = Field(default=None, max_length=12)


class ReportFeedback(BaseModel):
    rating: int = Field(ge=1, le=5)
    target: Literal["reading", "year", "followup"] = "reading"
    note: str = Field(default="", max_length=300)


class ReportEvent(BaseModel):
    kind: Literal["event", "condition"] = "event"
    type: str | None = Field(default=None, max_length=40)
    year: int | None = None


# ------------------------------------------------------------------ 인증
def _issue(uid: str) -> str:
    t = secrets.token_urlsafe(32)
    repo().create_session(_tok_hash(t), uid, SESSION_TTL)
    return t


@router.post("/auth/register", status_code=201)
def register(b: Credentials, req: Request):
    _limit("reg:" + client_ip(req), 10, 3600)
    mode = registration_mode()
    if mode == "closed":
        raise HTTPException(status_code=403, detail={"code": "REGISTRATION_CLOSED", "message": "이 서비스는 새 가입을 받지 않습니다."})
    if mode == "invite" and not hmac.compare_digest((b.invite or "").encode(), os.environ["ACCOUNTS_INVITE_CODE"].encode()):
        raise HTTPException(status_code=403, detail={"code": "INVITE_REQUIRED", "message": "초대 코드가 올바르지 않습니다."})
    email = b.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail={"code": "BAD_EMAIL", "message": "이메일 형식을 확인하세요."})
    if len(b.password) < 10 or not re.search(r"[A-Za-z]", b.password) or not re.search(r"\d", b.password):
        raise HTTPException(status_code=422, detail={"code": "WEAK_PASSWORD", "message": "비밀번호는 10자 이상이며 영문과 숫자를 포함해야 합니다."})
    try:
        uid = repo().create_user(email, hash_password(b.password))
    except DuplicateEmail:
        raise HTTPException(status_code=409, detail={"code": "EMAIL_TAKEN", "message": "가입할 수 없는 이메일입니다."})
    repo().audit(uid, "register", _ip_tag(req))
    return {"token": _issue(uid), "user": {"id": uid, "email": email}}


@router.post("/auth/login")
def login(b: Credentials, req: Request):
    email = b.email.strip().lower()
    _limit("login-ip:" + client_ip(req), 30, 600)
    _limit("login-em:" + hashlib.sha256(email.encode()).hexdigest(), 5, 900)
    u = repo().user_by_email(email)
    # 존재하지 않는 계정도 같은 비용의 해시 계산을 수행해 응답 시간으로 계정 존재 여부를 알 수 없게 한다
    ok = verify_password(b.password, u["pw_hash"] if u else hash_password("dummy-password-1"))
    if not (u and ok):
        repo().audit(u["id"] if u else None, "login_failed", _ip_tag(req))
        raise HTTPException(status_code=401, detail={"code": "BAD_LOGIN", "message": "이메일 또는 비밀번호가 올바르지 않습니다."})
    limiter.reset("login-em:" + hashlib.sha256(email.encode()).hexdigest())
    repo().audit(u["id"], "login", _ip_tag(req))
    return {"token": _issue(u["id"]), "user": {"id": u["id"], "email": email}}


@router.post("/auth/logout", status_code=204)
def logout(authorization: str | None = Header(default=None)):
    uid = current_user(authorization)
    repo().delete_session(_tok_hash(authorization[7:].strip()))
    repo().audit(uid, "logout")


@router.get("/me")
def me(authorization: str | None = Header(default=None)):
    from . import crypto
    from .repo import _dec
    uid = current_user(authorization)
    u = repo().get_user(uid)
    return {"id": uid, "email": _dec(u["email_enc"])["email"], "reports": len(repo().list_reports(uid)), "daily_report_limit": FREE_DAILY_REPORTS}


@router.delete("/me", status_code=204)
def delete_me(b: DeleteMe, req: Request, authorization: str | None = Header(default=None)):
    """계정과 모든 저장 데이터를 삭제한다. 비밀번호 재확인 필요."""
    uid = current_user(authorization)
    _limit("delme:" + uid, 5, 3600)
    u = repo().get_user(uid)
    if not verify_password(b.password, u["pw_hash"]):
        raise HTTPException(status_code=403, detail={"code": "BAD_PASSWORD", "message": "비밀번호가 올바르지 않습니다."})
    repo().delete_user(uid)
    repo().audit(None, "account_deleted", _ip_tag(req))  # 삭제된 사용자 id 는 남기지 않는다


# ------------------------------------------------------------------ 리포트
def _summary(pre: dict) -> dict:
    return {"years": pre["years"], "domains": pre["domains"], "depth": pre["depth"], "pillars": pre["natal_structure"]["pillars"], "verification_status": pre["verification"]["status"],
            "ruleset_version": pre["ruleset_version"], "content_hash": pre["content_hash"]}


@router.post("/reports", status_code=201)
def create_report(b: ReportCreate, req: Request, authorization: str | None = Header(default=None)):
    from .. import main as M
    from ..consult import agent as consult_agent
    uid = current_user(authorization)
    _limit("an-ip:" + client_ip(req), 60, 60)
    if repo().count_reports_since(uid, time.time() - 86400) >= FREE_DAILY_REPORTS:
        raise HTTPException(status_code=429, detail={"code": "DAILY_LIMIT", "message": f"하루 분석 저장 한도({FREE_DAILY_REPORTS}건)에 도달했습니다."})
    try:
        body = M.OneshotBody(**b.request)
    except Exception:
        raise HTTPException(status_code=422, detail={"code": "BAD_REQUEST", "message": "입력 값을 확인하세요."})
    pre = M._oneshot_pre(body)
    ans = consult_agent.answer(pre, body.question or "종합 상담을 시작합니다", domains_=body.domains, years=body.years)
    title = b.title.strip() or ("분석 " + (f"{pre['years'][0]}년" if pre["years"] else "원국") + " · " + ", ".join(pre["domains"][:2]))
    rid = repo().save_report(uid, title, _summary(pre), {"pre": pre, "answer": ans})  # 저장본은 내부 근거를 포함한 전체(암호화). 응답은 사용자용만.
    repo().audit(uid, "report_created", rid[:8])
    return {"id": rid, "title": title, "precommit": M.user_precommit(pre), "answer": M.user_answer(ans)}


@router.get("/reports")
def list_reports(authorization: str | None = Header(default=None)):
    return {"reports": repo().list_reports(current_user(authorization))}


def _own(uid: str, rid: str) -> dict:
    r = repo().get_report(uid, rid) if re.fullmatch(r"[0-9a-f]{32}", rid) else None
    if not r:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "리포트를 찾을 수 없습니다."})
    return r


@router.get("/reports/{rid}")
def get_report(rid: str, authorization: str | None = Header(default=None)):
    from .. import main as M
    uid = current_user(authorization)
    r = _own(uid, rid)
    turns = repo().get_turns(uid, rid)
    if not M.expose_internal():
        from ..consult import verdict as V
        turns = [V.public_turn(t) for t in turns]
    return {"id": rid, "title": r["title"], "created_at": r["created_at"], "precommit": M.user_precommit(r["body"]["pre"]), "answer": M.user_answer(r["body"]["answer"]), "turns": turns}


@router.post("/reports/{rid}/ask")
def ask(rid: str, b: ReportAsk, req: Request, authorization: str | None = Header(default=None)):
    from ..consult import agent as consult_agent
    uid = current_user(authorization)
    _limit("ask:" + uid, 60, 3600)
    r = _own(uid, rid)
    pre = r["body"]["pre"]
    turns = repo().get_turns(uid, rid)
    last = next((t["body"] for t in reversed(turns) if t["kind"] == "answer"), None)
    # 후속 질문 맥락 유지: 분야·연도를 비우면 직전 상담(없으면 최초 리포트)의 것을 이어받는다
    doms = b.domains or (last and last.get("domains")) or pre["domains"]
    years = b.years if b.years is not None else ((last and last.get("years")) or pre["years"])
    if any(y < 1901 or y > 2049 for y in years):
        raise HTTPException(status_code=422, detail={"code": "BAD_YEAR", "message": "분석 연도는 1901~2049 범위입니다."})
    qa_prev = (last or {}).get("answer", {}).get("qa") or {}
    ctx = {k: qa_prev.get(k) for k in ("domain", "year", "kind") if qa_prev.get(k)}  # 직전 답변의 분야·연도만 이어받는다(질문 원문은 넘기지 않는다)
    from ..consult import qa as _qa
    ctx.update(_qa.focus_context(years, b.focus_year, b.focus_domain, b.focus_month))                # 화면에서 지금 보고 있는 연도·분야가 있으면 그것이 우선
    ans = consult_agent.answer(pre, b.question, domains_=doms, years=years, depth=b.depth or pre["depth"], context=ctx)
    n = repo().add_turn(uid, rid, "answer", {"question": b.question, "domains": ans.get("domains", doms), "years": ans.get("years", years), "answer": ans})
    repo().audit(uid, "ask", rid[:8])
    from .. import main as M
    return {"turn": n, "answer": M.user_answer(ans)}


@router.post("/reports/{rid}/analyze")
def analyze(rid: str, b: ReportAnalyze, req: Request, authorization: str | None = Header(default=None)):
    """저장된 명식으로 연도·분야만 바꿔 다시 풀이한다(출생 정보를 다시 입력하지 않는다). 결과는 답변 기록으로 남아 다음 후속 질문의 맥락이 된다."""
    from ..consult import agent as consult_agent
    from .. import main as M
    uid = current_user(authorization)
    _limit("ask:" + uid, 60, 3600)
    r = _own(uid, rid)
    pre = r["body"]["pre"]
    if any(y < 1901 or y > 2049 for y in b.years):
        raise HTTPException(status_code=422, detail={"code": "BAD_YEAR", "message": "분석 연도는 1901~2049 범위입니다."})
    turns = repo().get_turns(uid, rid)
    last = next((t["body"] for t in reversed(turns) if t["kind"] == "answer"), None)
    doms = b.domains or (last and last.get("domains")) or pre["domains"]
    ans = consult_agent.answer(pre, "종합 상담을 시작합니다", domains_=doms, years=b.years, depth=pre["depth"])
    n = repo().add_turn(uid, rid, "answer", {"question": "", "view": True, "domains": ans.get("domains", doms), "years": ans.get("years", b.years), "answer": ans})
    repo().audit(uid, "analyze", rid[:8])
    return {"turn": n, "answer": M.user_answer(ans)}


@router.post("/reports/{rid}/feedback", status_code=201)
def feedback(rid: str, b: ReportFeedback, authorization: str | None = Header(default=None)):
    """본인 평가(1~5점·짧은 메모). 해석 내용이 아니라 평가만 저장한다. 상담 품질 ‘검증’이 아니라 개인 사용 기록이다."""
    uid = current_user(authorization)
    _limit("fb:" + uid, 120, 3600)
    _own(uid, rid)
    n = repo().add_turn(uid, rid, "feedback", b.model_dump())
    repo().audit(uid, "feedback", rid[:8])
    return {"turn": n}


@router.post("/reports/{rid}/reality")
def reality(rid: str, b: ReportEvent, authorization: str | None = Header(default=None)):
    from ..consult import agent as consult_agent
    uid = current_user(authorization)
    r = _own(uid, rid)
    res = consult_agent.classify_event(r["body"]["pre"], b.model_dump())
    n = repo().add_turn(uid, rid, "reality", {"event": b.model_dump(), "result": res})
    from .. import main as M
    return {"turn": n, **(res if M.expose_internal() else __import__("app.consult.verdict", fromlist=["x"]).public_reality(res))}


@router.get("/reports/{rid}/export")
def export(rid: str, format: Literal["md", "json"] = "md", authorization: str | None = Header(default=None)):
    from .export import to_markdown
    import json
    uid = current_user(authorization)
    r = _own(uid, rid)
    turns = repo().get_turns(uid, rid)
    if format == "json":
        return PlainTextResponse(json.dumps({"title": r["title"], "report": r["body"], "turns": turns}, ensure_ascii=False, indent=1), media_type="application/json",
                                 headers={"Content-Disposition": f'attachment; filename="report_{rid[:8]}.json"'})
    return PlainTextResponse(to_markdown(r, turns), media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="report_{rid[:8]}.md"'})


@router.delete("/reports/{rid}", status_code=204)
def delete_report(rid: str, authorization: str | None = Header(default=None)):
    uid = current_user(authorization)
    if not (re.fullmatch(r"[0-9a-f]{32}", rid) and repo().delete_report(uid, rid)):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "리포트를 찾을 수 없습니다."})
    repo().audit(uid, "report_deleted", rid[:8])
