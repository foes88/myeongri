"""Track A 자동 평가 실행. python -m app.evaluation.run  → golden/eval_trackA_report.json (합성 명식만; 개인정보 없음)

자동 평가가 보장하는 것: 사실표·출처·논리·차이·일관성. 보장하지 않는 것: 상담의 깊이, 실제 도움, 일반인 이해도의 실제 값(사람 평가 필요).
전문 상담 결과가 없으므로 철학관 대비 우수성에 대해 어떤 주장도 하지 않는다.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from ..consult import agent
from . import barnum, dataset as DS, metrics as M

GOLDEN = Path(__file__).resolve().parents[2] / "golden"
QUESTION = "종합 상담을 부탁합니다"


def ask(pre: dict, spec: DS.Spec, depth="expert") -> dict:
    return agent.answer(pre, QUESTION, domains_=list(spec.domains), years=list(spec.years), depth=depth)


def per_answer_metrics(a: dict, pre: dict) -> dict:
    return {"specificity": M.specificity(a, pre), "evidence": M.evidence(a, pre), "domain_counter": M.domain_evidence(a), "assertion": M.assertion(a),
            "readability": M.readability(a), "consistency_ok": a["consistency"]["ok"]}


def pair_result(p: DS.Pair) -> dict:
    pa, pb = DS.pre_of(p.a), DS.pre_of(p.b)
    aa, ab = ask(pa, p.a), ask(pb, p.b)
    changed = M.changed_facets(aa, ab)
    sig_d = M.jacc_dist(M.signature(aa, pa), M.signature(ab, pb))
    txt_d = M.token_dist(" ".join(x["text"] for x in aa["paragraphs"]), " ".join(x["text"] for x in ab["paragraphs"]))
    realizable = [DS.calendar_realizable(p.a.pillars), DS.calendar_realizable(p.b.pillars)]
    return {"pair_id": p.pair_id, "factor": p.factor, "note": p.note, "expected_facets": sorted(p.expected_facets), "changed_facets": sorted(changed),
            "sensitive": p.expected_facets <= changed, "missing_facets": sorted(p.expected_facets - changed), "unexpected_facets": sorted(changed - p.expected_facets),
            "signature_distance": sig_d, "text_distance": txt_d, "cosmetic_only": txt_d > 0.05 and sig_d == 0.0, "calendar_realizable": realizable,
            "metrics_a": per_answer_metrics(aa, pa), "metrics_b": per_answer_metrics(ab, pb)}


def repeat_consistency(spec: DS.Spec, k: int = 3) -> dict:
    pre = DS.pre_of(spec)
    outs = [ask(pre, spec) for _ in range(k)]
    same = all(json.dumps(o["paragraphs"], ensure_ascii=False, sort_keys=True) == json.dumps(outs[0]["paragraphs"], ensure_ascii=False, sort_keys=True) for o in outs)
    return {"runs": k, "identical": same, "consistency_ok": all(o["consistency"]["ok"] for o in outs)}


def main() -> dict:
    pairs = [pair_result(p) for p in DS.build_pairs()]
    control = DS.build_pairs()[0]
    ctrl_pre = DS.pre_of(control.a)
    ca, cb = ask(ctrl_pre, control.a), ask(ctrl_pre, control.a)
    controls = {"identical_input_signature_distance": M.jacc_dist(M.signature(ca, ctrl_pre), M.signature(cb, ctrl_pre)), "identical_input_text_distance": M.token_dist(" ".join(x["text"] for x in ca["paragraphs"]), " ".join(x["text"] for x in cb["paragraphs"]))}
    specs = DS.barnum_set()
    pres = [DS.pre_of(s) for s in specs]
    answers = [ask(p, s) for p, s in zip(pres, specs)]
    bar = barnum.analyze(answers, pres)
    conflict = DS.conflict_chart_spec()
    conflict_res = None
    if conflict:
        pc = DS.pre_of(conflict)
        ac = ask(pc, conflict)
        txt = " ".join(x["text"] for x in ac["paragraphs"] if x["kind"] == "schools")
        conflict_res = {"has_school_conflict": True, "explained": "서로 겹치지 않습니다" in txt and "각각 설명" in txt}
    allm = [per_answer_metrics(a, p) for a, p in zip(answers, pres)]
    mean = lambda f: round(sum(f(m) for m in allm) / len(allm), 3)
    agg = {"specificity_ratio_mean": mean(lambda m: m["specificity"]["ratio"]), "cited_claims_mean": mean(lambda m: m["evidence"]["cited_claims"]),
           "graph_connectivity_mean": mean(lambda m: m["evidence"]["graph_connectivity"]), "counter_coverage_mean": mean(lambda m: m["evidence"]["counter_coverage"]),
           "domain_counter_ratio_mean": mean(lambda m: m["domain_counter"]["ratio"]), "classical_overclaim_total": sum(m["evidence"]["classical_overclaim_sentences"] for m in allm),
           "assertive_ratio_mean": mean(lambda m: m["assertion"]["assertive_ratio"]), "hedged_claim_ratio_mean": mean(lambda m: m["assertion"]["hedged_claim_ratio"]),
           "avg_sentence_chars_mean": mean(lambda m: m["readability"]["avg_sentence_chars"]), "jargon_density_mean": mean(lambda m: m["readability"]["jargon_density"]),
           "glossary_coverage_mean": mean(lambda m: m["readability"]["glossary_coverage"]), "consistency_ok_all": all(m["consistency_ok"] for m in allm)}
    report = {
        "dataset": {"pairs": len(pairs), "barnum_charts": len(specs), "synthetic": True, "personal_data": False,
                    "realizable_barnum_charts": sum(DS.calendar_realizable(s.pillars) for s in specs),
                    "note": "합성 명식은 달력상 실현 불가능한 조합일 수 있으며 실제 출생정보와 연결하지 않는다. calendar_realizable 은 불리언만 기록."},
        "pairs": pairs, "pair_summary": {"sensitive": sum(p["sensitive"] for p in pairs), "total": len(pairs), "cosmetic_only": sum(p["cosmetic_only"] for p in pairs)},
        "controls": controls, "repeat_consistency": repeat_consistency(DS.Spec(DS.BASE)), "aggregate": agg, "barnum": {k: v for k, v in bar.items() if k != "per_chart"},
        "school_conflict_chart": conflict_res,
        "limits": ["자동 평가는 사실표·출처·논리·차이·일관성만 측정한다.", "상담의 깊이와 실제 도움, 일반인 이해도의 실제 값은 사람 평가가 필요하다(eval_human_template.csv).",
                   "전문 상담 결과와의 비교 자료가 없으므로 철학관 대비 우수성을 주장하지 않는다.", "문장이 다르다는 것은 좋은 분석의 증거가 아니다. signature 거리와 함께 본다.",
                   "예측력(Track B)은 이 평가의 대상이 아니다."],
    }
    (GOLDEN / "eval_trackA_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(GOLDEN / "eval_human_template.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rater_id", "rater_type(expert/general)", "case_id", "answer_source(blind_label)", "구체성(1-5)", "명식 고유 구조 반영(1-5)", "고전 근거 정확성(1-5)", "복합 통변 깊이(1-5)",
                    "논리 일관성(1-5)", "일반인 이해도(1-5)", "실질적 도움(1-5)", "후속 질문 대응(1-5)", "과잉 단정 여부(Y/N)", "비고"])
        for p in pairs:
            for side in ("A", "B"):
                w.writerow(["", "", f"{p['pair_id']}-{side}", "", "", "", "", "", "", "", "", "", "", ""])
    return report


if __name__ == "__main__":
    r = main()
    print(json.dumps({"pair_summary": r["pair_summary"], "controls": r["controls"], "aggregate": r["aggregate"], "barnum": {k: r["barnum"][k] for k in ("generic_ratio", "generic_candidate_sentences", "content_sentences", "mean_signature_distance", "mean_text_distance", "cosmetic_difference_pairs")}, "conflict": r["school_conflict_chart"], "repeat": r["repeat_consistency"]}, ensure_ascii=False, indent=1))
    for p in r["pairs"]:
        print(p["pair_id"], p["factor"], "sensitive" if p["sensitive"] else "MISSING " + ",".join(p["missing_facets"]), "unexpected:", ",".join(p["unexpected_facets"]), "sig", p["signature_distance"], "realizable", p["calendar_realizable"])
