"""v9.1 사례 검증 CLI. 출생 정보는 화면에 출력하지 않는다. 저장 위치: backend/data_private/cases/ (암호화·gitignored, CASES_DIR 로 변경).

  python -m tools.case_eval template            입력용 CSV 양식을 data_private/cases/template.csv 에 만든다(합성 예시 1건, 실제 사례 아님)
  python -m tools.case_eval import 파일.csv      CSV → 암호화 저장(동의 없는 행은 거부). 사건 행이 없는 사례(대조군)도 가능
  python -m tools.case_eval status              사례 수·시각 신뢰도 분포·개발/검증 분리·봉인 상태(개인정보 없음)
  python -m tools.case_eval freeze [--all|ID]   사건을 읽지 않고 해석을 만들어 봉인
  python -m tools.case_eval report [--baseline 파일.json] [--out 파일.json] [--include-synthetic]   사건과 대조(봉인된 실제 사례만; 합성은 기본 제외)
  python -m tools.case_eval remove ID           동의 철회: 사례·사건·예측 삭제
CSV 열: case_id,calendar,leap,birth_date,birth_time,birth_place,gender,time_confidence,consent_given,consent_scope,consent_note,
        kind(real|synthetic), obs_from, obs_to, obs_complete_domains(세미콜론 구분: 이 연도 구간·분야는 사건을 빠짐없이 확인함 — 비우면 무사건 해를 음성으로 쓰지 않음),
        event_year,event_month,event_domain,event_kind,event_source,event_source_confidence   (사례당 사건 수만큼 행 반복)
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

from app import cases as C

COLS = ["case_id", "calendar", "leap", "birth_date", "birth_time", "birth_place", "gender", "time_confidence", "consent_given", "consent_scope", "consent_note",
        "kind", "obs_from", "obs_to", "obs_complete_domains",
        "event_year", "event_month", "event_domain", "event_kind", "event_source", "event_source_confidence"]
TRUE = ("1", "true", "yes", "y", "예", "동의")


def parse_csv(text: str) -> dict[str, tuple[dict, list[dict]]]:
    out: dict[str, tuple[dict, list[dict]]] = {}
    for n, row in enumerate(csv.DictReader(text.splitlines()), start=2):
        cid = (row.get("case_id") or "").strip()
        rec = {"case_id": cid, "calendar": (row.get("calendar") or "solar").strip(), "leap": (row.get("leap") or "").strip().lower() in TRUE,
               "birth_date": (row.get("birth_date") or "").strip(), "birth_time": (row.get("birth_time") or "").strip() or None, "birth_place": row.get("birth_place") or "",
               "gender": (row.get("gender") or "").strip(), "time_confidence": (row.get("time_confidence") or "").strip().upper(),
               "consent": {"given": (row.get("consent_given") or "").strip().lower() in TRUE, "scope": (row.get("consent_scope") or "").strip(), "note": row.get("consent_note") or ""},
               "kind": (row.get("kind") or "real").strip().lower(),
               "observation": ({"from": row["obs_from"], "to": row["obs_to"], "complete_domains": [d for d in re.split(r"[;,\s]+", row.get("obs_complete_domains") or "") if d]}
                               if (row.get("obs_from") or "").strip() else None)}
        if cid not in out:
            out[cid] = (rec, [])
        elif out[cid][0] != rec:
            raise C.CaseError(f"{n}행: 같은 사례 ID({cid})의 출생·동의 정보가 행마다 다릅니다.")
        if (row.get("event_year") or "").strip():
            out[cid][1].append({"year": row["event_year"], "month": row.get("event_month"), "domain": (row.get("event_domain") or "").strip(), "kind": row.get("event_kind") or "",
                                "source": row.get("event_source") or "", "source_confidence": (row.get("event_source_confidence") or "").strip()})
    return out


def cmd_status(st: C.Store) -> dict:
    meta, fr = st.meta(), st.frozen()
    tc = Counter(m["time_confidence"] for m in meta.values())
    sp = Counter(m["split"] for m in meta.values())
    kinds = Counter(m["kind"] for m in meta.values())
    real = [m for m in meta.values() if m["kind"] == "real"]
    return {"cases": len(meta), "real_cases": kinds.get("real", 0), "synthetic_cases(도구 검증용)": kinds.get("synthetic", 0),
            "real_cases_with_observation_range": sum(1 for m in real if m["observation"]), "event_quality": st.event_quality(), "time_confidence": {k: tc.get(k, 0) for k in C.TIME_CONF}, "primary_analysis_cases(A·B)": sum(tc.get(k, 0) for k in C.PRIMARY_TIME_CONF),
            "split": {"dev": sp.get("dev", 0), "validation": sp.get("validation", 0)}, "frozen": len(fr), "not_frozen": len(set(meta) - set(fr)),
            "refrozen(검증 무효 표시)": sum(1 for r in fr.values() if r.get("refrozen")), "eval_runs_on_validation": len(st.eval_log()),
            "real_case_validation": "미검증 (실제 사례 0건)" if not real else "진행 중 — 결과는 report 의 verdict 를 따른다(표본이 작으면 결론 없음)"}


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="case_eval")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("template")
    p = sub.add_parser("import"); p.add_argument("csv")
    sub.add_parser("status")
    p = sub.add_parser("freeze"); p.add_argument("id", nargs="?"); p.add_argument("--all", action="store_true")
    p = sub.add_parser("report"); p.add_argument("--baseline"); p.add_argument("--out"); p.add_argument("--include-synthetic", action="store_true", help="합성 사례도 포함(도구 점검용, 실제 성능 아님)")
    p = sub.add_parser("remove"); p.add_argument("id")
    a = ap.parse_args(argv)
    st = C.Store()
    if a.cmd == "template":
        f = st.dir / "template.csv"
        f.parent.mkdir(parents=True, exist_ok=True)
        ex = ["SYN-001", "solar", "false", "1990-01-15", "08:30", "서울특별시", "male", "A", "true", "both", "합성 예시(실제 사례 아님)", "synthetic", "2010", "2024", "job_change;career", "2018", "6", "job_change", "이직", "예시 출처", "high"]
        with open(f, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh); w.writerow(COLS); w.writerow(ex)
        print("양식을 만들었습니다:", f)
    elif a.cmd == "import":
        added = 0
        for cid, (rec, ev) in parse_csv(Path(a.csv).read_text(encoding="utf-8-sig")).items():
            try:
                r = st.add_case(rec, ev)
                added += 1
                print(f"추가: {r['case_id']} → {r['split']} (사건 {r['events']}건)")
            except C.CaseError as e:
                print(f"거부: {cid or '(ID 없음)'} — {e}")
        print(f"{added}건 추가")
    elif a.cmd == "status":
        print(json.dumps(cmd_status(st), ensure_ascii=False, indent=2))
    elif a.cmd == "freeze":
        ids = st.case_ids() if a.all else [a.id]
        if not ids or ids == [None]:
            print("ID 또는 --all 이 필요합니다"); return 2
        for cid in ids:
            if cid in st.frozen() and a.all:
                continue
            try:
                r = st.freeze(cid)
                print(f"봉인: {cid} ({r['years']}개 연도, {r['hash']})")
            except (C.CaseError, Exception) as e:
                print(f"실패: {cid} — {e}")
    elif a.cmd == "report":
        base = json.loads(Path(a.baseline).read_text(encoding="utf-8")) if a.baseline else None
        rep = C.build_report(st, base, include_synthetic=a.include_synthetic)
        txt = json.dumps(rep, ensure_ascii=False, indent=2)
        if a.out:
            Path(a.out).write_text(txt, encoding="utf-8")
            print("보고서 저장:", a.out)
        for sp, part in rep["split"].items():
            print(f"[{sp}] 사례 {part['cases']} · 판정: {part['verdict']['status']} — {part['verdict']['reason']}")
        if rep["validation_contaminated"]:
            print("⚠ 검증 사례가 이전 규칙 버전에서 이미 평가되었습니다 — 이 검증은 더 이상 독립적이지 않습니다. 새 검증 사례가 필요합니다.")
    elif a.cmd == "remove":
        print("삭제됨" if st.remove_case(a.id) else "없는 사례")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
