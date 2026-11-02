"""저장소 인터페이스와 SQLite 구현. 모든 조회·변경 메서드는 user_id 를 받아 사용자 간 격리를 강제한다."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Protocol

from . import crypto

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data_private" / "app.sqlite3"
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, email_idx TEXT UNIQUE NOT NULL, email_enc BLOB NOT NULL, pw_hash TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, created_at REAL NOT NULL, title TEXT NOT NULL, meta TEXT NOT NULL, blob BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS turns(report_id TEXT NOT NULL, user_id TEXT NOT NULL, n INTEGER NOT NULL, created_at REAL NOT NULL, kind TEXT NOT NULL, blob BLOB NOT NULL, PRIMARY KEY(report_id, n));
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, user_id TEXT, event TEXT NOT NULL, detail TEXT);
CREATE INDEX IF NOT EXISTS ix_reports_user ON reports(user_id, created_at);
CREATE INDEX IF NOT EXISTS ix_sessions_user ON sessions(user_id);
"""


class DuplicateEmail(Exception):
    pass


class Repo(Protocol):
    def create_user(self, email: str, pw_hash: str) -> str: ...
    def user_by_email(self, email: str) -> dict | None: ...
    def get_user(self, user_id: str) -> dict | None: ...
    def create_session(self, token_hash: str, user_id: str, ttl: float) -> None: ...
    def session_user(self, token_hash: str) -> str | None: ...
    def delete_session(self, token_hash: str) -> None: ...
    def save_report(self, user_id: str, title: str, meta: dict, body: dict) -> str: ...
    def list_reports(self, user_id: str) -> list[dict]: ...
    def get_report(self, user_id: str, report_id: str) -> dict | None: ...
    def add_turn(self, user_id: str, report_id: str, kind: str, body: dict) -> int | None: ...
    def get_turns(self, user_id: str, report_id: str) -> list[dict]: ...
    def delete_report(self, user_id: str, report_id: str) -> bool: ...
    def count_reports_since(self, user_id: str, since: float) -> int: ...
    def all_user_ids(self) -> list[str]: ...
    def delete_user(self, user_id: str) -> None: ...
    def audit(self, user_id: str | None, event: str, detail: str = "") -> None: ...


def _enc(obj) -> bytes:
    return crypto.encrypt(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode())


def _dec(b: bytes):
    return json.loads(crypto.decrypt(bytes(b)))


class SqliteRepo:
    def __init__(self, path: str | None = None):
        p = path or os.environ.get("APP_DB") or str(DEFAULT_DB)
        if p != ":memory:":
            Path(p).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(p, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.db.executescript(SCHEMA)

    def _x(self, sql, args=()):
        with self.lock:
            return self.db.execute(sql, args)

    # 사용자·세션
    def create_user(self, email, pw_hash):
        uid = uuid.uuid4().hex
        try:
            self._x("INSERT INTO users VALUES(?,?,?,?,?)", (uid, crypto.blind_index(email), _enc({"email": email}), pw_hash, time.time()))
        except sqlite3.IntegrityError:
            raise DuplicateEmail("이미 가입된 이메일")
        return uid

    def user_by_email(self, email):
        r = self._x("SELECT * FROM users WHERE email_idx=?", (crypto.blind_index(email),)).fetchone()
        return dict(r) if r else None

    def get_user(self, user_id):
        r = self._x("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(r) if r else None

    def create_session(self, token_hash, user_id, ttl):
        now = time.time()
        self._x("INSERT INTO sessions VALUES(?,?,?,?)", (token_hash, user_id, now, now + ttl))

    def session_user(self, token_hash):
        r = self._x("SELECT user_id, expires_at FROM sessions WHERE token_hash=?", (token_hash,)).fetchone()
        if not r:
            return None
        if r["expires_at"] < time.time():
            self.delete_session(token_hash)
            return None
        return r["user_id"]

    def delete_session(self, token_hash):
        self._x("DELETE FROM sessions WHERE token_hash=?", (token_hash,))

    # 리포트(사용자 격리: 모든 질의에 user_id)
    def save_report(self, user_id, title, meta, body):
        rid = uuid.uuid4().hex
        self._x("INSERT INTO reports VALUES(?,?,?,?,?,?)", (rid, user_id, time.time(), title, json.dumps(meta, ensure_ascii=False), _enc(body)))
        return rid

    def list_reports(self, user_id):
        return [{"id": r["id"], "created_at": r["created_at"], "title": r["title"], **json.loads(r["meta"])}
                for r in self._x("SELECT * FROM reports WHERE user_id=? ORDER BY created_at DESC", (user_id,)).fetchall()]

    def get_report(self, user_id, report_id):
        r = self._x("SELECT * FROM reports WHERE id=? AND user_id=?", (report_id, user_id)).fetchone()
        if not r:
            return None
        return {"id": r["id"], "created_at": r["created_at"], "title": r["title"], "meta": json.loads(r["meta"]), "body": _dec(r["blob"])}

    def add_turn(self, user_id, report_id, kind, body):
        with self.lock:
            if not self._x("SELECT 1 FROM reports WHERE id=? AND user_id=?", (report_id, user_id)).fetchone():
                return None
            n = self._x("SELECT COALESCE(MAX(n),0)+1 FROM turns WHERE report_id=?", (report_id,)).fetchone()[0]
            self._x("INSERT INTO turns VALUES(?,?,?,?,?,?)", (report_id, user_id, n, time.time(), kind, _enc(body)))
            return n

    def get_turns(self, user_id, report_id):
        return [{"n": r["n"], "created_at": r["created_at"], "kind": r["kind"], "body": _dec(r["blob"])}
                for r in self._x("SELECT * FROM turns WHERE report_id=? AND user_id=? ORDER BY n", (report_id, user_id)).fetchall()]

    def delete_report(self, user_id, report_id):
        with self.lock:
            c = self._x("DELETE FROM reports WHERE id=? AND user_id=?", (report_id, user_id)).rowcount
            if c:
                self._x("DELETE FROM turns WHERE report_id=? AND user_id=?", (report_id, user_id))
            return bool(c)

    def count_reports_since(self, user_id, since):
        return self._x("SELECT COUNT(*) FROM reports WHERE user_id=? AND created_at>=?", (user_id, since)).fetchone()[0]

    def all_user_ids(self):
        return [r["id"] for r in self._x("SELECT id FROM users").fetchall()]

    def delete_user(self, user_id):
        with self.lock:
            for t in ("turns", "reports", "sessions"):
                self._x(f"DELETE FROM {t} WHERE user_id=?", (user_id,))
            self._x("DELETE FROM users WHERE id=?", (user_id,))

    def audit(self, user_id, event, detail=""):
        self._x("INSERT INTO audit(ts,user_id,event,detail) VALUES(?,?,?,?)", (time.time(), user_id, event, detail[:200]))

    def audit_events(self, user_id=None):
        q, a = ("SELECT * FROM audit WHERE user_id=? ORDER BY id", (user_id,)) if user_id else ("SELECT * FROM audit ORDER BY id", ())
        return [dict(r) for r in self._x(q, a).fetchall()]
