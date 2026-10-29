"""커밋 전 개인정보/비밀정보 스캔. 사용: python -m app.privacy_scan  (backend 에서)  — 발견 시 종료코드 1.

- 비밀: API 키/토큰/개인키 패턴
- 개인정보: 실제 출생일시로 보이는 '날짜+시각' 조합, 이메일(예시 도메인 제외)
- 허용: 합성 센티널 날짜(2000-01-01) 및 '가상/합성/예시' 표시가 있는 줄
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC_DATE = "2000-01-01"
TEXT_SUFFIX = {".md", ".py", ".json", ".html", ".txt", ".bat", ".yml", ".yaml", ".toml", ".example", ".js", ".css", ""}
SKIP_PARTS = {".git", "node_modules", ".venv", "__pycache__", ".pytest_cache"}

SECRET_PATTERNS = {
    "api_key": re.compile(r"\b(sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35})\b"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "assigned_secret": re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"][^'\"\s]{12,}['\"]"),
}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@(?!example\.|users\.noreply|anthropic\.com)[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
BIRTH_DATETIME = re.compile(r"(?:19|20)\d{2}[-./년 ]\s?\d{1,2}[-./월 ]\s?\d{1,2}일?[^\n]{0,24}?\d{1,2}[:시]\s?\d{0,2}")
SYNTHETIC_MARK = re.compile(r"가상|합성|예시|synthetic|YYYY")


def tracked_and_staged_files(root: Path = ROOT) -> list[Path]:
    """git 추적/스테이징 대상 + 아직 추적 안 된(무시되지 않은) 파일."""
    try:
        out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=root, capture_output=True,
                             text=True, encoding="utf-8", check=True).stdout.splitlines()
        return [root / p for p in out]
    except Exception:
        return [p for p in root.rglob("*") if p.is_file()]


def scan_text(text: str, name: str = "") -> list[str]:
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        for label, pat in SECRET_PATTERNS.items():
            if pat.search(line):
                hits.append(f"{name}:{i}: secret/{label}")
        if EMAIL.search(line):
            hits.append(f"{name}:{i}: email")
        m = BIRTH_DATETIME.search(line)
        if m and SYNTHETIC_DATE not in m.group(0) and not SYNTHETIC_MARK.search(line):
            hits.append(f"{name}:{i}: possible_birth_datetime")
    return hits


def scan_files(files: list[Path], root: Path = ROOT) -> list[str]:
    hits: list[str] = []
    for f in files:
        if not f.is_file() or SKIP_PARTS & set(f.parts) or f.suffix.lower() not in TEXT_SUFFIX:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        hits += scan_text(text, str(f.relative_to(root)))
    return hits


if __name__ == "__main__":
    found = scan_files(tracked_and_staged_files())
    print("\n".join(found) if found else "privacy scan: clean")
    sys.exit(1 if found else 0)
