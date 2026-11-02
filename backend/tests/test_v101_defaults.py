"""개인용 기본 입력값 엔드포인트 테스트. 가상 값만 사용(날짜와 시각은 숫자로 조립). 개인 정보가 저장소·공개 배포로 나가지 않는지가 핵심."""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

c = TestClient(app)
D = f"{2001:04d}-{3:02d}-{4:02d}"
T = f"{5:02d}:{6:02d}"


def put(tmp_path, monkeypatch, obj):
    f = tmp_path / "defaults.json"
    f.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("MYEONGRI_DEFAULTS", str(f))


def test_empty_when_not_configured(monkeypatch):
    monkeypatch.delenv("MYEONGRI_DEFAULTS", raising=False)
    r = c.get("/api/v1/local-defaults")
    assert r.status_code == 200 and r.json() == {} and r.headers["cache-control"] == "no-store"


def test_returns_only_whitelisted_valid_fields(tmp_path, monkeypatch):
    put(tmp_path, monkeypatch, {"birth_date": D, "birth_time": T, "gender": "male", "calendar": "solar", "birth_place": "서울특별시", "email": "x@example.com", "password": "secret", "name": "홍길동"})
    r = c.get("/api/v1/local-defaults").json()
    assert r == {"birth_date": D, "birth_time": T, "gender": "male", "calendar": "solar", "birth_place": "서울특별시"}
    assert "email" not in r and "password" not in r and "name" not in r


def test_invalid_values_are_dropped_and_date_is_required(tmp_path, monkeypatch):
    put(tmp_path, monkeypatch, {"birth_date": D, "birth_time": "99:99", "gender": "other", "calendar": "x", "birth_place": "가" * 41})
    assert c.get("/api/v1/local-defaults").json() == {"birth_date": D}
    put(tmp_path, monkeypatch, {"birth_time": T, "gender": "male"})
    assert c.get("/api/v1/local-defaults").json() == {}                      # 날짜가 없으면 아무것도 채우지 않는다
    put(tmp_path, monkeypatch, {"birth_date": "not-a-date"})
    assert c.get("/api/v1/local-defaults").json() == {}


def test_missing_or_broken_file_gives_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("MYEONGRI_DEFAULTS", str(tmp_path / "none.json"))
    assert c.get("/api/v1/local-defaults").json() == {}
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setenv("MYEONGRI_DEFAULTS", str(tmp_path / "bad.json"))
    assert c.get("/api/v1/local-defaults").json() == {}


def test_remote_clients_never_receive_defaults(tmp_path, monkeypatch):
    put(tmp_path, monkeypatch, {"birth_date": D})
    remote = TestClient(app, client=("203.0.113.9", 5000))
    assert remote.get("/api/v1/local-defaults").json() == {}
    assert TestClient(app, client=("127.0.0.1", 5000)).get("/api/v1/local-defaults").json() == {"birth_date": D}


def test_personal_defaults_are_not_in_the_repository():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    text = (root / "web" / "consult.html").read_text(encoding="utf-8") + (root / "scripts" / "_personal_env.bat").read_text(encoding="utf-8")
    assert "defaults.json" in text and "local-defaults" in text
    assert "안양" not in text and "1988" not in text                         # 개인 기본값 자체는 저장소 밖(.myeongri)에만 있다
