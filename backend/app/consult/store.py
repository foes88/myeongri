"""상담 저장소(파일 기반, 개발용). 위치: data_private/consult/ (gitignored, 환경변수 CONSULT_DIR 로 변경).

- precommit(사전 분석 기록)은 write-once: 같은 id 로 다시 쓰려 하면 거부하고, 읽을 때마다 해시를 재검증한다.
- turns 는 append-only(JSON Lines). 현실 입력(reality_input)은 turns 에만 쌓이며 precommit 을 바꿀 수 없다.
- 소유 토큰은 해시만 저장한다. 출생 원문은 기본적으로 저장하지 않는다(명식·대운 요약만).
※ 개발용 저장소: 암호화·백업·접근 감사가 없다. 실서비스 전 v6.3 문서(02)의 요건을 구현해야 한다.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import uuid
from pathlib import Path

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "data_private" / "consult"


def base_dir() -> Path:
    d = Path(os.environ.get("CONSULT_DIR", DEFAULT_DIR))
    d.mkdir(parents=True, exist_ok=True)
    return d


def canonical(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(obj) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


class TamperError(Exception):
    pass


def _tdir(tid: str) -> Path:
    if not tid.isalnum() or len(tid) != 32:
        raise KeyError("invalid thread id")
    return base_dir() / tid


def create_thread(precommit: dict, token_hash: str, meta: dict) -> str:
    tid = uuid.uuid4().hex
    d = _tdir(tid)
    d.mkdir()
    body = dict(precommit, content_hash=None)
    body["content_hash"] = sha256({k: v for k, v in precommit.items() if k != "content_hash"})
    p = d / "precommit.json"
    with open(p, "x", encoding="utf-8") as f:   # 'x' = 이미 있으면 실패 (덮어쓰기 불가)
        f.write(json.dumps(body, ensure_ascii=False))
    os.chmod(p, 0o444)
    (d / "meta.json").write_text(json.dumps({"token_hash": token_hash, **meta}, ensure_ascii=False), encoding="utf-8")
    (d / "turns.jsonl").touch()
    return tid


def overwrite_precommit(tid: str, *_a, **_k):
    raise PermissionError("precommit 은 변경할 수 없다. 조건이 바뀌면 새 상담(revision)을 만든다")


def read_precommit(tid: str, rev: int | None = None) -> dict:
    """rev=None 이면 최초 기록(원본). 재분석 기록은 precommit_r{n}.json 으로 별도 보존된다(원본은 그대로)."""
    p = _tdir(tid) / ("precommit.json" if not rev else f"precommit_r{int(rev)}.json")
    if not p.exists():
        raise KeyError(tid)
    body = json.loads(p.read_text(encoding="utf-8"))
    h = body.get("content_hash")
    if h != sha256({k: v for k, v in body.items() if k != "content_hash"}):
        raise TamperError("precommit 해시 불일치: 사전 분석 기록이 변경되었다")
    return body


def add_revision(tid: str, pre_new: dict, reason: str, diff: dict) -> int:
    """재분석 기록을 새 파일로 추가한다(write-once). 원본 precommit.json 은 바뀌지 않는다."""
    d = _tdir(tid)
    revs = read_revisions(tid)
    n = len(revs) + 1
    body = dict(pre_new)
    body["content_hash"] = sha256({k: v for k, v in pre_new.items() if k != "content_hash"})
    with open(d / f"precommit_r{n}.json", "x", encoding="utf-8") as f:
        f.write(json.dumps(body, ensure_ascii=False))
    os.chmod(d / f"precommit_r{n}.json", 0o444)
    prev = revs[-1]["content_hash"] if revs else read_precommit(tid)["content_hash"]
    rec = {"revision": n, "content_hash": body["content_hash"], "supersedes": prev, "reason": reason, "generated_at": body["generated_at"],
           "ruleset_version": body["ruleset_version"], "model_version": body["model_version"], "diff": diff}
    with open(d / "revisions.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return n


def read_revisions(tid: str) -> list[dict]:
    f = _tdir(tid) / "revisions.jsonl"
    return [json.loads(x) for x in open(f, encoding="utf-8") if x.strip()] if f.exists() else []


def new_token() -> tuple[str, str]:
    t = secrets.token_urlsafe(24)
    return t, hashlib.sha256(t.encode()).hexdigest()


def check_token(tid: str, token: str | None) -> bool:
    try:
        meta = json.loads((_tdir(tid) / "meta.json").read_text(encoding="utf-8"))
    except (OSError, KeyError):
        return False
    return bool(token) and hmac.compare_digest(meta["token_hash"], hashlib.sha256(token.encode()).hexdigest())


def append_turn(tid: str, turn: dict) -> int:
    f = _tdir(tid) / "turns.jsonl"
    n = sum(1 for _ in open(f, encoding="utf-8")) + 1
    with open(f, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(turn, turn_no=n), ensure_ascii=False) + "\n")
    return n


def read_turns(tid: str) -> list[dict]:
    f = _tdir(tid) / "turns.jsonl"
    return [json.loads(x) for x in open(f, encoding="utf-8") if x.strip()]


def list_threads() -> list[str]:
    return sorted(p.name for p in base_dir().iterdir() if p.is_dir())


def delete_thread(tid: str) -> None:
    import shutil
    d = _tdir(tid)
    for p in d.glob("*"):
        os.chmod(p, 0o666)
    shutil.rmtree(d)
