"""PostgreSQL 저장소(Repo 인터페이스 구현). 환경변수 DATABASE_URL 이 있으면 api.repo() 가 이 구현을 쓴다.

- 서버리스 친화: 호출마다 짧은 연결을 열고 닫는다(운영에서는 관리형 DB 의 풀러(PgBouncer 등) 연결 문자열을 쓴다).
- 스키마는 최초 사용 시 `CREATE TABLE IF NOT EXISTS` 로 만든다(마이그레이션 도구 도입 전의 단순 방식).
- 사용자 격리·암호화·삭제 의미는 SQLite 구현과 같다(같은 테스트를 두 구현에 모두 돌린다).
- 전송 구간 암호화: DATABASE_URL 에 sslmode=require 를 쓴다(운영). 저장 데이터 본문은 앱 계층에서 이미 Fernet 으로 암호화된다.
"""
from __future__ import annotations

import json
import time
import uuid

import psycopg
from psycopg import errors, sql

from . import crypto
from .repo import DuplicateEmail, _dec, _enc

SCHEMA = [
    "CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, email_idx TEXT UNIQUE NOT NULL, email_enc BYTEA NOT NULL, pw_hash TEXT NOT NULL, created_at DOUBLE PRECISION NOT NULL)",
    "CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, created_at DOUBLE PRECISION NOT NULL, expires_at DOUBLE PRECISION NOT NULL)",
    "CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, created_at DOUBLE PRECISION NOT NULL, title TEXT NOT NULL, meta TEXT NOT NULL, blob BYTEA NOT NULL)",
    "CREATE TABLE IF NOT EXISTS turns(report_id TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE, user_id TEXT NOT NULL, n INTEGER NOT NULL, created_at DOUBLE PRECISION NOT NULL, kind TEXT NOT NULL, blob BYTEA NOT NULL, PRIMARY KEY(report_id, n))",
    "CREATE TABLE IF NOT EXISTS audit(id BIGSERIAL PRIMARY KEY, ts DOUBLE PRECISION NOT NULL, user_id TEXT, event TEXT NOT NULL, detail TEXT)",
    "CREATE INDEX IF NOT EXISTS ix_reports_user ON reports(user_id, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_sessions_user ON sessions(user_id)",
    "CREATE INDEX IF NOT EXISTS ix_sessions_exp ON sessions(expires_at)",
]


class PostgresRepo:
    def __init__(self, url: str, schema: str | None = None):
        self.url, self.schema = url, schema
        with self._conn() as c:
            if schema:
                c.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
                c.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            for stmt in SCHEMA:
                c.execute(stmt)

    def _conn(self):
        c = psycopg.connect(self.url, autocommit=False, connect_timeout=10)
        if self.schema:
            c.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(self.schema)))
        return c

    def _q(self, q, args=(), one=False, many=False):
        with self._conn() as c:
            cur = c.execute(q, args)
            if one:
                return cur.fetchone()
            if many:
                return cur.fetchall()
            return cur.rowcount

    def drop_schema(self):
        if self.schema:
            with self._conn() as c:
                c.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(self.schema)))

    # 사용자·세션
    def create_user(self, email, pw_hash):
        uid = uuid.uuid4().hex
        try:
            self._q("INSERT INTO users VALUES(%s,%s,%s,%s,%s)", (uid, crypto.blind_index(email), _enc({"email": email}), pw_hash, time.time()))
        except errors.UniqueViolation:
            raise DuplicateEmail("이미 가입된 이메일")
        return uid

    def _user(self, where, arg):
        r = self._q(f"SELECT id, email_idx, email_enc, pw_hash, created_at FROM users WHERE {where}", (arg,), one=True)
        return {"id": r[0], "email_idx": r[1], "email_enc": bytes(r[2]), "pw_hash": r[3], "created_at": r[4]} if r else None

    def user_by_email(self, email):
        return self._user("email_idx=%s", crypto.blind_index(email))

    def get_user(self, user_id):
        return self._user("id=%s", user_id)

    def create_session(self, token_hash, user_id, ttl):
        now = time.time()
        self._q("INSERT INTO sessions VALUES(%s,%s,%s,%s)", (token_hash, user_id, now, now + ttl))

    def session_user(self, token_hash):
        r = self._q("SELECT user_id, expires_at FROM sessions WHERE token_hash=%s", (token_hash,), one=True)
        if not r:
            return None
        if r[1] < time.time():
            self.delete_session(token_hash)
            return None
        return r[0]

    def delete_session(self, token_hash):
        self._q("DELETE FROM sessions WHERE token_hash=%s", (token_hash,))

    def purge_expired_sessions(self) -> int:
        return self._q("DELETE FROM sessions WHERE expires_at<%s", (time.time(),))

    # 리포트(모든 질의에 user_id)
    def save_report(self, user_id, title, meta, body):
        rid = uuid.uuid4().hex
        self._q("INSERT INTO reports VALUES(%s,%s,%s,%s,%s,%s)", (rid, user_id, time.time(), title, json.dumps(meta, ensure_ascii=False), _enc(body)))
        return rid

    def list_reports(self, user_id):
        rows = self._q("SELECT id, created_at, title, meta FROM reports WHERE user_id=%s ORDER BY created_at DESC", (user_id,), many=True)
        return [{"id": r[0], "created_at": r[1], "title": r[2], **json.loads(r[3])} for r in rows]

    def get_report(self, user_id, report_id):
        r = self._q("SELECT id, created_at, title, meta, blob FROM reports WHERE id=%s AND user_id=%s", (report_id, user_id), one=True)
        return {"id": r[0], "created_at": r[1], "title": r[2], "meta": json.loads(r[3]), "body": _dec(bytes(r[4]))} if r else None

    def add_turn(self, user_id, report_id, kind, body):
        with self._conn() as c:
            if not c.execute("SELECT 1 FROM reports WHERE id=%s AND user_id=%s", (report_id, user_id)).fetchone():
                return None
            c.execute("SELECT 1 FROM reports WHERE id=%s FOR UPDATE", (report_id,))  # 같은 리포트의 동시 질문이 같은 번호를 받지 않게 직렬화
            n = c.execute("SELECT COALESCE(MAX(n),0)+1 FROM turns WHERE report_id=%s", (report_id,)).fetchone()[0]
            c.execute("INSERT INTO turns VALUES(%s,%s,%s,%s,%s,%s)", (report_id, user_id, n, time.time(), kind, _enc(body)))
            return n

    def get_turns(self, user_id, report_id):
        rows = self._q("SELECT n, created_at, kind, blob FROM turns WHERE report_id=%s AND user_id=%s ORDER BY n", (report_id, user_id), many=True)
        return [{"n": r[0], "created_at": r[1], "kind": r[2], "body": _dec(bytes(r[3]))} for r in rows]

    def delete_report(self, user_id, report_id):
        return bool(self._q("DELETE FROM reports WHERE id=%s AND user_id=%s", (report_id, user_id)))  # turns 는 ON DELETE CASCADE

    def count_reports_since(self, user_id, since):
        return self._q("SELECT COUNT(*) FROM reports WHERE user_id=%s AND created_at>=%s", (user_id, since), one=True)[0]

    def all_user_ids(self):
        return [r[0] for r in self._q("SELECT id FROM users", many=True)]

    def delete_user(self, user_id):
        self._q("DELETE FROM users WHERE id=%s", (user_id,))  # sessions·reports·turns 는 CASCADE

    def audit(self, user_id, event, detail=""):
        self._q("INSERT INTO audit(ts,user_id,event,detail) VALUES(%s,%s,%s,%s)", (time.time(), user_id, event, detail[:200]))

    def audit_events(self, user_id=None):
        q, a = ("SELECT id, ts, user_id, event, detail FROM audit WHERE user_id=%s ORDER BY id", (user_id,)) if user_id else ("SELECT id, ts, user_id, event, detail FROM audit ORDER BY id", ())
        return [{"id": r[0], "ts": r[1], "user_id": r[2], "event": r[3], "detail": r[4]} for r in self._q(q, a, many=True)]

    def count(self, table: str) -> int:
        assert table in ("users", "sessions", "reports", "turns")
        return self._q(f"SELECT COUNT(*) FROM {table}", one=True)[0]

    def raw_blobs(self) -> bytes:
        """테스트용: 저장된 본문 바이트(암호화 확인)."""
        return b"".join(bytes(r[0]) for r in self._q("SELECT blob FROM reports", many=True)) + b"".join(bytes(r[0]) for r in self._q("SELECT email_enc FROM users", many=True))
