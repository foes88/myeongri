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



def accounts_enabled() -> bool:
    """운영(APP_ENV=production)에서는 영속 DB 어댑터가 준비되어 ACCOUNTS_ENABLED=1 로 명시할 때만 켠다. 서버리스의 휘발성 파일 저장소에 회원 데이터를 쓰지 않기 위함."""
    return os.environ.get("ACCOUNTS_ENABLED") == "1" or os.environ.get("APP_ENV") != "production"


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


class DeleteMe(BaseModel):
    password: str = Field(max_length=200)


class ReportCreate(BaseModel):
    title: str = Field(default="", max_length=80)
    request: dict


class ReportAsk(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    years: list[int] | None = Field(default=None, max_length=10)
    domains: list[str] | None = Field(default=None, max_length=12)
    depth: Literal["summary", "detailed", "expert"] | None = None


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
    rid = repo().save_report(uid, title, _summary(pre), {"pre": pre, "answer": ans})
    repo().audit(uid, "report_created", rid[:8])
    return {"id": rid, "title": title, "precommit": M._oneshot_summary(pre), "answer": ans}


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
    return {"id": rid, "title": r["title"], "created_at": r["created_at"], "precommit": M._oneshot_summary(r["body"]["pre"]), "answer": r["body"]["answer"],
            "turns": repo().get_turns(uid, rid)}


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
    ans = consult_agent.answer(pre, b.question, domains_=doms, years=years, depth=b.depth or pre["depth"])
    n = repo().add_turn(uid, rid, "answer", {"question": b.question, "domains": ans.get("domains", doms), "years": ans.get("years", years), "answer": ans})
    repo().audit(uid, "ask", rid[:8])
    return {"turn": n, "answer": ans}


@router.post("/reports/{rid}/reality")
def reality(rid: str, b: ReportEvent, authorization: str | None = Header(default=None)):
    from ..consult import agent as consult_agent
    uid = current_user(authorization)
    r = _own(uid, rid)
    res = consult_agent.classify_event(r["body"]["pre"], b.model_dump())
    n = repo().add_turn(uid, rid, "reality", {"event": b.model_dump(), "result": res})
    return {"turn": n, **res}


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
