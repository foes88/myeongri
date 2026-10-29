"""정적 미리보기용 합성 데모 데이터 생성: web/assets/demo_consult.js (window.MINGLI_DEMO).
실제 엔진(결정론적 상담)이 합성 명식(간지 4쌍, 실제 출생정보 아님)으로 만든 답변을 그대로 저장한다. 서버·네트워크 불필요.
실행: python -m tools.build_static_demo
"""
import json
from pathlib import Path

from app.consult import agent
from app.evaluation import dataset as DS

OUT = Path(__file__).resolve().parents[2] / "web" / "assets" / "demo_consult.js"
Q_MAIN = "2030년 재물과 직업의 흐름이 궁금합니다"
Q_REC = "사업 쪽은 어떻게 보이나요?"


def build() -> dict:
    spec = DS.Spec(DS.BASE, domains=("overall", "wealth", "career"), years=(2030,), cycles_first_year=2000)  # 2030년 중반에 대운이 바뀌는 합성 배열
    pre = DS.pre_of(spec)
    answers = {d: agent.answer(pre, Q_MAIN, domains_=list(spec.domains), years=[2030], depth=d) for d in ("summary", "detailed", "expert")}
    rec = agent.answer(pre, Q_REC, domains_=[], years=[2030], depth="detailed")
    keys = ("content_hash", "generated_at", "ruleset_version", "engine_version", "model_version", "calculation_profile_id", "variant_id", "variants_count", "verification", "domains", "years", "depth")
    summary = {k: pre[k] for k in keys} | {"pillars": pre["natal_structure"]["pillars"]}
    summary["verification"] = dict(summary["verification"])
    summary["verification"]["unverified_notice"] = ["합성 데모입니다. 실제 출생 정보로 계산한 결과가 아니며 만세력 검증 대상이 아닙니다."] + summary["verification"].get("unverified_notice", [])[1:]
    turns = [{"turn_no": 1, "kind": "answer", "question": Q_MAIN, "answer": answers["detailed"]}, {"turn_no": 2, "kind": "answer", "question": Q_REC, "answer": rec}]
    return {"synthetic": True, "note": "합성 명식 데모 — 실제 분석 결과가 아닙니다", "precommit": summary, "answers": answers, "record": {"question": Q_REC, "answer": rec}, "turns": turns}


if __name__ == "__main__":
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("/* 자동 생성: python -m tools.build_static_demo — 합성 데모 데이터(개인정보 없음) */\nwindow.MINGLI_DEMO=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print("wrote", OUT, OUT.stat().st_size, "bytes")
