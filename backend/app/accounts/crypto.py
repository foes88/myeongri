"""저장 데이터 암호화(Fernet). 키는 환경변수 APP_DATA_KEY. 로컬 개발에서만 gitignored 파일 키를 자동 생성한다(APP_ENV=production 이면 환경변수 필수)."""
from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

KEYFILE = Path(__file__).resolve().parents[2] / "data_private" / "app_data.key"


def _key() -> bytes:
    k = os.environ.get("APP_DATA_KEY")
    if k:
        return k.encode()
    if os.environ.get("APP_ENV") == "production":
        raise RuntimeError("APP_DATA_KEY 가 필요합니다(운영 환경에서는 파일 키를 쓰지 않음)")
    if not KEYFILE.exists():
        KEYFILE.parent.mkdir(parents=True, exist_ok=True)
        KEYFILE.write_bytes(Fernet.generate_key())
    return KEYFILE.read_bytes().strip()


def fernet() -> Fernet:
    return Fernet(_key())


def encrypt(b: bytes) -> bytes:
    return fernet().encrypt(b)


def decrypt(b: bytes) -> bytes:
    try:
        return fernet().decrypt(b)
    except InvalidToken as e:
        raise ValueError("복호화 실패(키 불일치 또는 변조)") from e


def blind_index(value: str) -> str:
    """이메일 등 조회용 고정 해시(HMAC). DB 에 평문을 두지 않고 일치 검색만 가능하게 한다."""
    return hmac.new(_key(), value.encode(), hashlib.sha256).hexdigest()
