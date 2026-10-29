"""커밋 전 개인정보/비밀정보 스캔. 사용: python -m app.privacy_scan  (backend 에서)  — 발견 시 종료코드 1.

- 비밀: API 키/토큰/개인키 패턴
- 개인정보: 실제 출생일시로 보이는 '날짜+시각' 조합, 이메일(예시 도메인 제외)
- 허용: 합성 센티널 날짜(2000-01-01) 및 '가상/합성/예시' 표시가 있는 줄
"""
from __future__ import annotations

import json
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


def scan_text(text: str, name: str = "", check_birth: bool = True) -> list[str]:
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        for label, pat in SECRET_PATTERNS.items():
            if pat.search(line):
                hits.append(f"{name}:{i}: secret/{label}")
        if EMAIL.search(line):
            hits.append(f"{name}:{i}: email")
        m = BIRTH_DATETIME.search(line) if check_birth else None
        if m and SYNTHETIC_DATE not in m.group(0) and not SYNTHETIC_MARK.search(line):
            hits.append(f"{name}:{i}: possible_birth_datetime")
    return hits


# 골든 디렉터리는 날짜+시각 형태가 본질적으로 많아 'possible_birth_datetime' 줄 검사만 구조 검증으로 대체한다.
# 비밀키·이메일 검사는 그대로 적용하고, cases.json 은 validate_golden_cases() 로 가상 표시·허용 필드·출처를 검증한다.
SYNTHETIC_DATA_DIRS = (("backend", "golden"),)
ALLOWED_INPUT_KEYS = {"calendar", "year", "month", "day", "hour", "minute", "gender", "place", "is_leap_month", "ordinal_in_year"}
ALLOWED_PLACES = {"서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시", "울산광역시", "제주특별자치도"}
ALLOWED_REF_TOOLS = ("lunar-python", "HKO", "KASI", "IANA", "Meeus", "공개 연혁")


def _in_synthetic_dir(f: Path, root: Path) -> bool:
    parts = f.relative_to(root).parts
    return any(parts[:len(d)] == d for d in SYNTHETIC_DATA_DIRS)


def validate_golden_cases(cases: list[dict]) -> list[str]:
    """골든 케이스가 실제 개인 출생정보를 담지 않았는지 구조적으로 검사한다."""
    problems = []
    for c in cases:
        cid = c.get("test_id", "?")
        if c.get("synthetic_input") is not True:
            problems.append(f"{cid}: synthetic_input 이 true 가 아님")
        extra = set(c.get("input", {})) - ALLOWED_INPUT_KEYS
        if extra:
            problems.append(f"{cid}: 허용되지 않은 입력 필드 {sorted(extra)}")
        if c.get("input", {}).get("place", "서울특별시") not in ALLOWED_PLACES:
            problems.append(f"{cid}: 허용되지 않은 출생지")
        if not c.get("references") or not all(any(t in r.get("tool", "") for t in ALLOWED_REF_TOOLS) for r in c["references"]):
            problems.append(f"{cid}: 출처 불명 케이스")
        text = json.dumps(c, ensure_ascii=False)
        if EMAIL.search(text) or re.search(r"0\d{1,2}-\d{3,4}-\d{4}", text):
            problems.append(f"{cid}: 이메일/전화번호 형태")
    return problems


def scan_files(files: list[Path], root: Path = ROOT) -> list[str]:
    hits: list[str] = []
    for f in files:
        if not f.is_file() or SKIP_PARTS & set(f.parts) or f.suffix.lower() not in TEXT_SUFFIX:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        golden = _in_synthetic_dir(f, root)
        hits += scan_text(text, str(f.relative_to(root)), check_birth=not golden)
        if golden and f.name == "cases.json":
            hits += [f"{f.relative_to(root)}: {m}" for m in validate_golden_cases(json.loads(text)["cases"])]
    return hits


if __name__ == "__main__":
    found = scan_files(tracked_and_staged_files())
    print("\n".join(found) if found else "privacy scan: clean")
    sys.exit(1 if found else 0)
