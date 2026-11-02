"""v9.1 고전 규칙 검증 현황 정리. golden/classical_verification.json·classical_differences.json 만 읽는다(새 자료를 내려받지 않는다).
구분: 원문 / 후대 주석 / 현대적 해석 / 구현자 규약 / 미확인. 사용: python -m tools.classical_audit [--write docs/24_V91_CLASSICAL_AUDIT.md]"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from app.mingli import classical as C
from app.mingli.rules import RULES

BASIS = ("원문", "후대 주석", "현대적 해석", "구현자 규약", "미확인")


def basis_of(rid: str) -> tuple[str, list[str]]:
    """규칙의 주된 근거 구분과 부가 표시(범위 한정·현대 확장 등)."""
    e = C.entry(rid)
    st = C.classical_status(rid)
    diff = (C.difference_for(rid) or {}).get("classification")
    extra: list[str] = []
    if C.coverage(rid) == "partial":
        extra.append("일부 조건만 확인(범위 한정)")
    if diff == "MODERN_CONVENTION":
        extra.append("현대적 확장 포함")
    if diff == "SCHOOL_VARIANT":
        extra.append("학파 차이")
    if diff == "IMPLEMENTATION_BUG":
        extra.append("구현 오류 수정 이력")
    if st == "implementation_convention":
        return "구현자 규약", extra
    if st == "text_confirmed":
        if e.get("original_excerpt"):
            return "원문", extra
        if e.get("commentary_excerpt"):
            return "후대 주석", extra
        return "미확인", extra + ["발췌 없음"]
    return "미확인", extra + (["위치(키워드)만 확인 — 구절이 규칙을 뒷받침하는지 미판단"] if st == "location_confirmed" else ["미확인"])


def rows() -> list[dict]:
    out = []
    for rid in RULES:
        e = C.entry(rid)
        b, extra = basis_of(rid)
        d = C.difference_for(rid) or {}
        host = (e.get("url") or "").split("/")[2] if (e.get("url") or "").startswith("http") else None
        out.append({"rule_id": rid, "status": C.classical_status(rid), "basis": b, "extra": extra, "work": e.get("work"), "section": e.get("section"), "cond": e.get("school_conditions"), "host": host,
                    "unconfirmed": e.get("unconfirmed_parts") or [], "gaps": d.get("known_gaps") or [], "diff": d.get("classification")})
    return out


def build_markdown() -> str:
    rs = rows()
    s = C.summary()
    by_basis = Counter(r["basis"] for r in rs)
    todo = [r for r in rs if r["basis"] == "미확인" or r["unconfirmed"] or r["gaps"]]
    works = defaultdict(list)
    for r in rs:
        if r["work"]:
            works[r["work"]].append(r["rule_id"])
    L = ["# v9.1 고전 규칙 검증 현황 (자동 생성)", "",
         "`python -m tools.classical_audit --write docs/24_V91_CLASSICAL_AUDIT.md` 로 다시 만든다. 이 문서는 저장소에 이미 있는 검증 기록만 정리하며, **새 원문을 내려받거나 재배포하지 않았다.**", "",
         "## 요약", "", f"- 전체 규칙 {s['total']}개 — " + ", ".join(f"{k} {by_basis.get(k, 0)}" for k in BASIS),
         f"- 원문 대조 전(위치만 확인): {s['by_status']['location_confirmed']}개, pending: {s['by_status']['pending']}개 → 고전 대조가 끝나지 않은 규칙 {s['classical_rules_pending']}개",
         f"- 일부 조건만 확인된 규칙(범위 한정): {len(s['partial_text_confirmed'])}개 — " + ", ".join(s["partial_text_confirmed"]),
         f"- 구현자 규약(고전 주장 없음): {s['by_status']['implementation_convention']}개 — 고전의 결론으로 쓰지 않는다.", "",
         "‘원문 확인’은 고전과 일치한다는 뜻이 아니라 **표시한 범위에서 원문이 뒷받침한다**는 뜻이다. 외부 전사본은 판본 교감 전이며 짧은 발췌만 저장한다.", "",
         "## 구분 정의", "", "| 구분 | 뜻 |", "|---|---|",
         "| 원문 | 원전 구절(짧은 발췌)이 규칙 내용에 대응함을 사람이 확인 |", "| 후대 주석 | 원문이 아니라 주석자(예: 任鐵樵, 徐樂吾)의 해설이 근거 |",
         "| 현대적 해석 | 고전에 없는 현대 통용·확장(예: 반합·공합 범위) |", "| 구현자 규약 | 구현 편의·단순화. 고전의 결론이 아님 |", "| 미확인 | 위치만 확인했거나 확인 못함 |", "",
         "## 우선 정리할 항목 (미확인·일부 확인·알려진 누락)", "", "| 규칙 | 구분 | 상태 | 확인 못한 부분 | 전제 조건(학파·적용) | 필요한 자료 |", "|---|---|---|---|---|---|"]
    for r in todo:
        need = f"{r['work'] or '출처 미지정'}" + (f" · {r['section']}" if r["section"] else "")
        parts = "; ".join(r["unconfirmed"] + r["gaps"] + r["extra"]) or "-"
        L.append(f"| {r['rule_id']} | {r['basis']} | {r['status']} | {parts} | {(r['cond'] or '-').replace('|', '/')} | {need} — 판본 확인 필요 |")
    L += ["", "## 전체 규칙", "", "| 규칙 | 구분 | 상태 | 차이 분류 | 출처 |", "|---|---|---|---|---|"]
    for r in rs:
        L.append(f"| {r['rule_id']} | {r['basis']} | {r['status']} | {r['diff'] or '-'} | {r['work'] or '-'} |")
    L += ["", "## 출처 작품과 판본 확인이 필요한 항목", ""]
    for w, ids in sorted(works.items()):
        L.append(f"- **{w}**: {len(ids)}개 규칙 — 현재 근거는 외부 전사본(판본 교감 전). 어느 판본인지, 평주 부분(徐樂吾 평주, 任鐵樵 注)이 원문과 구분되어 인용되는지 확인해야 한다.")
    L += ["", "- **궁통보감(窮通寶鑑/欄江網)**: 현재 규칙 레지스트리에 근거로 올라 있지 않다. 조사 결과와 등록 조건은 `docs/28_V94_CLASSICAL_AND_JOHU.md` 참조. 일간×월지 개별 표는 판본·사용 권한 확인 전이라 쓰지 않으며, 조후는 한난 방향(滴天髓 寒暖論, 범위 한정) 수준으로만 쓴다.",
          "", "## 전사본 호스트(판본 교감 전)", ""]
    hosts = defaultdict(set)
    for r in rs:
        if r["host"]:
            hosts[r["host"]].add(r["work"] or "-")
    L += [f"- {h}: " + ", ".join(sorted(w)) for h, w in sorted(hosts.items())]
    L += ["", "## 자료 접근 실패 기록", ""]
    fs = s["failed_sources"]
    L += [f"- {k}: 접속 실패(시간 초과)" for k in fs] or ["- 없음"]
    L += ["", "## 자료 사용 원칙", "", "- 사용 권한이 확인되지 않은 자료는 수집·재배포하지 않는다. 한글 번역본은 저작권을 확인하기 전에는 인용하지 않는다.",
          "- 원문(한문 원전)도 전사본의 이용 조건을 확인한 뒤에만 짧은 발췌를 저장한다. 전문 복제는 하지 않는다.",
          "- 이 상태에서 ‘고전 검증 완료’라고 표시하지 않는다."]
    return "\n".join(L) + "\n"


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--write")
    a = ap.parse_args(argv)
    md = build_markdown()
    if a.write:
        Path(a.write).write_text(md, encoding="utf-8")
        print("저장:", a.write)
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
