"""상담 리포트(JSON)의 영역 간 모순·근거·학파 충돌·재현성 검사 (knowledge/17 §5.2, 보강 지시 §3).

계산 오류(kind=calculation)와 해석 오류(kind=interpretation)를 분리해 기록한다.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Callable

from .chart_analysis import analyze_chart
from .report_checks import KNOWLEDGE_DIR, Finding, error_kind, run_text_checks

SECTION_IDS = ["basic", "temperament", "wealth", "career", "documents", "health", "relations", "luck", "advice", "sources"]
PART_KEYS = ("summary", "detail", "positive", "caution", "daily", "basis")


def x01_cross_section(report: dict, analysis: dict) -> Finding:
    """각 영역 claims 가 하나의 기준표(analysis)와 같은 방향인지."""
    bad = []
    for sec in report["sections"]:
        for c in sec.get("claims", []):
            if "group" in c and analysis["groups"][c["group"]]["level"] != c["level"]:
                bad.append(f"{sec['id']}:{c['group']}={c['level']} (기준표 {analysis['groups'][c['group']]['level']})")
            if "day_strength" in c and analysis["strength_candidate"] != c["day_strength"]:
                bad.append(f"{sec['id']}:day_strength={c['day_strength']} (기준표 {analysis['strength_candidate']})")
    return Finding("X01", not bad, f"영역 간 모순={bad}" if bad else "")


def x02_school_conflict(report: dict) -> Finding:
    stances = {s["stance"] for s in report.get("schools", [])}
    if len(stances) > 1 and not report.get("conflict_note", "").strip():
        return Finding("X02", False, "학파 판단이 갈리는데 차이 설명(conflict_note)이 없음")
    if len({s["id"] for s in report.get("schools", [])}) != len(report.get("schools", [])):
        return Finding("X02", False, "학파 id 중복")
    return Finding("X02", True)


def _ref_exists(ref: str) -> bool:
    m = re.match(r"근거:\s*(\d{2})\s+(.+)$", ref.strip())
    if not m:
        return False
    files = list(KNOWLEDGE_DIR.glob(f"{m.group(1)}_*.md"))
    return bool(files) and m.group(2).strip() in files[0].read_text(encoding="utf-8")


def x03_basis(report: dict) -> Finding:
    """모든 영역(단 sources 제외)에 실재하는 근거가 1개 이상."""
    bad = [s["id"] for s in report["sections"] if s["id"] != "sources" and not any(_ref_exists(r) for r in s.get("basis", []))]
    return Finding("X03", not bad, f"근거 누락/미실재={bad}" if bad else "")


def x04_luck(report: dict) -> Finding:
    luck = report["luck"]
    if luck.get("profile") == "unset" or luck.get("status") != "computed":
        leak = luck.get("start_age") is not None or any(y.get("ganji") for y in luck.get("years", []))
        return Finding("X04", not leak, "미산출인데 시작 나이/세운 간지가 표시됨" if leak else "")
    return Finding("X04", luck.get("verified") is True, "" if luck.get("verified") is True else "미검산 대운을 표시")


def x07_structure(report: dict) -> Finding:
    ids = [s["id"] for s in report["sections"]]
    miss = [s["id"] for s in report["sections"] for k in PART_KEYS if not s.get(k)]
    ok = ids == SECTION_IDS and not miss
    return Finding("X07", ok, f"영역 순서/구성 오류 ids={ids} 누락={miss}" if not ok else "")


def x08_yongshin_separate(report: dict) -> Finding:
    """격국/억부/조후용신이 서로 다른 이름·학파 라벨의 별도 항목이고 내용이 비어 있지 않은지 (10 실패조건)."""
    y = report.get("yongshin", {})
    want = {"pattern": "격국용신", "balance": "억부용신", "climate": "조후용신"}
    bad = [k for k, n in want.items() if y.get(k, {}).get("name") != n or not y.get(k, {}).get("text", "").strip()]
    texts = [y.get(k, {}).get("text") for k in want]
    if not bad and len(set(texts)) < 3:
        bad.append("identical_text")
    return Finding("X08", not bad, f"용신 3축 분리 위반={bad}" if bad else "")


def x05_reproducibility(fn: Callable[[], object], runs: int = 20) -> Finding:
    digests = {hashlib.sha256(json.dumps(fn(), sort_keys=True, ensure_ascii=False).encode()).hexdigest() for _ in range(runs)}
    return Finding("X05", len(digests) == 1, f"{runs}회 중 서로 다른 결과 {len(digests)}종" if len(digests) > 1 else "")


def x06_report_matches_analysis(report: dict, analysis: dict) -> Finding:
    ok = report.get("analysis") == analysis
    return Finding("X06", ok, "" if ok else "리포트 사실표가 chart 재계산 결과와 다름")


def render_markdown(report: dict) -> str:
    out = []
    for s in report["sections"]:
        out += [f"## {s['title']}", s["summary"], s["detail"], f"긍정: {s['positive']}", f"주의: {s['caution']}",
                f"생활: {s['daily']}", s.get("label", ""), *[f"({r})" for r in s["basis"]], ""]
    y = report["yongshin"]
    out += ["## 용신 후보", *[f"{y[k]['name']}: {y[k]['text']}" for k in ("pattern", "balance", "climate")], ""]
    out += [f"## 학파", *[f"{s['name']}: {s['reading']}" for s in report["schools"]], report.get("conflict_note", ""), ""]
    out += [report["disclaimer"], report["status_notice"]]
    return "\n".join(out)


def review_report(report: dict) -> list[Finding]:
    """report 하나에 대한 전 검사. 사실표는 chart 에서 재계산해 대조한다."""
    pillars = {k: v["stem"] + v["branch"] for k, v in report["chart"]["pillars"].items()}
    analysis = analyze_chart(pillars)
    status = report["chart"]["verification"]["status"]
    findings = [x01_cross_section(report, analysis), x02_school_conflict(report), x03_basis(report), x04_luck(report),
                x06_report_matches_analysis(report, analysis), x07_structure(report), x08_yongshin_separate(report)]
    findings += run_text_checks(render_markdown(report), status, report["luck"]["profile"])
    return findings


def split_by_kind(findings: list[Finding]) -> dict[str, list[Finding]]:
    out: dict[str, list[Finding]] = {"calculation": [], "interpretation": []}
    for f in findings:
        if not f.ok:
            out[error_kind(f.check)].append(f)
    return out
