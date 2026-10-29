"""공개 배포 점검: 추적 파일 중 재배포가 불명확한 외부 자료가 없는지, 데이터 파일이 매니페스트에 분류되어 있는지 검사한다.
실행: python -m tools.check_distribution  (종료코드 1 = 문제 있음)

분류(DATA_MANIFEST.json "class")
  SELF_AUTHORED          직접 작성한 판정·레지스트리·짧은 발췌
  SELF_GENERATED         직접 계산한 결과/보고서(외부 자료 원문 없음)
  SYNTHETIC              합성 입력과 라이브러리(MIT 등)·공개 연혁에서 만든 기대값
  EXTERNAL_AGGREGATE     외부 자료와의 대조 '집계'와 소수의 개별 사실(행 단위 표 아님)
  EXTERNAL_FACTS         소규모(수십 건) 역사적 사실 목록(법령·연혁). 2차 자료에서 사실만 추출, 출처 표기
금지: 외부 자료 원문/행 단위 표(EXTERNAL_RAW) 추적. data_private/ 및 알려진 원자료 파일명 추적.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
MANIFEST = BACKEND / "golden" / "DATA_MANIFEST.json"
FORBIDDEN = re.compile(r"data_private|hko_lunar_terms|kasi_calendar\.json|kasi_almanac\.json|kasi_service\.json|cases_external|report_external|term_analysis_full|\.bsp$|golden/_wsl/")
ALLOWED_CLASSES = {"SELF_AUTHORED", "SELF_GENERATED", "SYNTHETIC", "EXTERNAL_AGGREGATE", "EXTERNAL_FACTS"}
MAX_BYTES = 600_000
DATE_RE = re.compile(r"\b(19|20)\d{2}-\d{2}-\d{2}")
MAX_DATES_IN_EXTERNAL_AGG = 40
# 서비스 의존성 라이선스(확인 근거는 docs/08)
LICENSES = {"skyfield": "MIT", "numpy": "BSD-3-Clause", "tzdata": "Apache-2.0", "korean-lunar-calendar": "MIT (상위 저장소 LICENSE 확인)", "lunar-python": "MIT",
            "fastapi": "MIT", "uvicorn": "BSD-3-Clause", "pydantic": "MIT"}


def tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
    return [f.strip('"') for f in out]


def check(files: list[str] | None = None, manifest: dict | None = None) -> list[str]:
    files = files if files is not None else tracked()
    manifest = manifest if manifest is not None else json.loads(MANIFEST.read_text(encoding="utf-8"))
    entries = manifest["files"]
    problems = []
    for f in files:
        if FORBIDDEN.search(f):
            problems.append(f"추적 금지 경로: {f}")
        p = ROOT / f
        if p.exists() and p.is_file() and p.stat().st_size > MAX_BYTES and not f.endswith(".md") and "web/" not in f:
            problems.append(f"큰 파일({p.stat().st_size}B): {f}")
        if f.startswith("backend/golden/") and f != "backend/golden/DATA_MANIFEST.json":
            rel = f[len("backend/golden/"):]
            if rel not in entries:
                problems.append(f"매니페스트에 없는 데이터 파일: {rel}")
    for rel, e in entries.items():
        if e["class"] not in ALLOWED_CLASSES:
            problems.append(f"허용되지 않은 분류 {e['class']}: {rel}")
        if e["class"] == "EXTERNAL_AGGREGATE":
            if e.get("row_level") is not False or not e.get("origins"):
                problems.append(f"외부 집계 파일은 row_level=false 와 origins 필요: {rel}")
            p = BACKEND / "golden" / rel
            if p.exists() and len(DATE_RE.findall(p.read_text(encoding="utf-8"))) > MAX_DATES_IN_EXTERNAL_AGG:
                problems.append(f"외부 집계 파일에 날짜가 너무 많음(행 단위 표 의심): {rel}")
        if e["class"] == "EXTERNAL_FACTS":
            p = BACKEND / "golden" / rel
            if e.get("row_level") != "facts_small" or not e.get("origins"):
                problems.append(f"EXTERNAL_FACTS 는 row_level=facts_small 와 origins 필요: {rel}")
            if p.exists() and len(DATE_RE.findall(p.read_text(encoding="utf-8"))) > 120:
                problems.append(f"EXTERNAL_FACTS 날짜가 너무 많음: {rel}")
        if e.get("redistribution") not in ("ok", "facts_only_terms_unverified", "n/a"):
            problems.append(f"redistribution 값 확인 필요: {rel}")
    req = (BACKEND / "requirements.txt").read_text(encoding="utf-8").lower()
    for line in req.splitlines():
        name = re.split(r"[<>=\[\s]", line.strip())[0]
        if name and name not in LICENSES:
            problems.append(f"라이선스 미확인 의존성: {name}")
        if name == "sxtwl":
            problems.append("sxtwl 은 서비스 의존성 금지(검증 전용)")
    return problems


if __name__ == "__main__":
    probs = check()
    print("distribution check:", "clean" if not probs else probs)
    sys.exit(1 if probs else 0)
