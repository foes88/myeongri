"""개인용 배포: 가입을 닫아 둔 상태(ACCOUNTS_REGISTRATION=closed)에서 본인 계정을 직접 만든다.
사용: python -m tools.create_owner you@example.com   (비밀번호는 화면에 입력하며 기록되지 않는다. 자동화 시 환경변수 OWNER_PASSWORD)
DATABASE_URL / APP_DATA_KEY 등은 서버와 같은 환경변수를 쓴다."""
from __future__ import annotations

import getpass
import os
import re
import sys

from app.accounts import api as A
from app.accounts.repo import DuplicateEmail


def create(email: str, password: str) -> str:
    email = email.strip().lower()
    if not A.EMAIL_RE.match(email):
        raise SystemExit("이메일 형식을 확인하세요.")
    if len(password) < 10 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise SystemExit("비밀번호는 10자 이상이며 영문과 숫자를 포함해야 합니다.")
    try:
        uid = A.repo().create_user(email, A.hash_password(password))
    except DuplicateEmail:
        raise SystemExit("이미 있는 계정입니다.")
    A.repo().audit(uid, "owner_created", "cli")
    return uid


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    pw = os.environ.get("OWNER_PASSWORD") or getpass.getpass("비밀번호: ")
    create(argv[1], pw)
    print("계정을 만들었습니다. ACCOUNTS_REGISTRATION=closed 로 두면 다른 사람은 가입할 수 없습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
