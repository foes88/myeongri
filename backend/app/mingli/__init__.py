"""Mingli-Graph 1·2층. 진입점: analyze_structure / analyze_chart_variants"""
from __future__ import annotations

from .evidence import EvidenceGraph
from .layer1 import analyze_layer1
from .layer2 import analyze_layer2
from .layer3 import analyze_layer3
from .layer4 import analyze_layer4
from .layer5 import analyze_year, analyze_years
from .schools import evaluate_schools
from .rules import RULES, RULESET_VERSION

DISCLAIMER = "전통 명리학의 구조 분석이며 미래 사건을 예측하거나 길흉을 확정하지 않습니다. 고전 원문 대조는 미완료입니다."


def analyze_structure(pillars: dict[str, str], variant_id: str = "v1") -> dict:
    g = EvidenceGraph()
    l1 = analyze_layer1(pillars, g, variant_id)
    l2 = analyze_layer2(pillars, g, variant_id)
    l3 = analyze_layer3(pillars, g, variant_id, l2["relations"], l1["support_structure"]["label"])
    l4 = analyze_layer4(pillars, g, variant_id, l1)
    # 통근 근거 노드에 '뿌리 지지가 충·형·파·해 관계에 있음'을 반대 근거로 연결(존재만, 손상 확정 아님)
    pos_rel: dict[str, list[dict]] = {}
    for r in l2["relations"]:
        if r["relation_type"] in ("충", "형(부분)", "삼형", "무례지형(子卯)", "자형", "파", "해"):
            for p in r["pillars"]:
                pos_rel.setdefault(p, []).append(r)
    for pos, info in l1["tonggeun"].items():
        node = g.nodes[info["claim_id"]]
        for root in info["roots"]:
            for r in pos_rel.get(root["branch_pos"], []):
                node.counter_evidence.append(f"뿌리 지지 {root['branch']}가 {r['relation_type']} 관계에 있음(존재만 확인, 뿌리 손상은 확정하지 않음)")
                g.link(node.claim_id, r["claim_id"], "opposes", "뿌리 지지가 충·형·파·해 관계에 관여")
    problems = g.validate()
    return {"ruleset_version": RULESET_VERSION, "variant_id": variant_id, "pillars": pillars, "layer1": l1, "layer2": l2, "layer3": l3, "layer4": l4, "schools": evaluate_schools(l1, l4),
            "graph": g.to_dict(), "validation": {"ok": not problems, "problems": problems}, "disclaimer": DISCLAIMER}


def analyze_chart_variants(chart: dict) -> dict:
    """ChartCalculationResult.to_dict() 의 variants 각각을 독립 분석한다. 변형 간 분석이 달라지는 항목을 요약한다."""
    results = [analyze_structure(v["pillars"], v["variant_id"]) for v in chart["variants"]]
    diffs = []
    if len(results) > 1:
        base = results[0]
        for r in results[1:]:
            diffs.append({"variant_id": r["variant_id"], "deukryeong_same": r["layer1"]["deukryeong"]["by_bongi"] == base["layer1"]["deukryeong"]["by_bongi"],
                          "support_label": [base["layer1"]["support_structure"]["label"], r["layer1"]["support_structure"]["label"]],
                          "relation_count": [base["layer2"]["count"], r["layer2"]["count"]]})
    return {"verification": chart["verification"], "analyses": results, "variant_differences": diffs,
            "release_note": "명식 검증 상태가 V1 이 아니면 구조 분석은 '조건부 참고'이다"}


def analyze_periods(chart: dict, years: list[int], variant_id: str = "v1") -> dict:
    """특정 연도·복수 연도(최대 10개) 분석. 변형 명식은 variant_id 로 선택한다(기본: 첫 변형)."""
    if not years or len(years) > 10 or any(y < 1901 or y > 2049 for y in years):
        raise ValueError("연도는 1~10개, 1901~2049 범위")
    v = next((x for x in chart["variants"] if x["variant_id"] == variant_id), chart["variants"][0])
    natal = v["pillars"]
    base = analyze_structure(natal, v["variant_id"])
    out = analyze_years(chart, natal, sorted(set(years)), v["variant_id"], base["layer1"]["support_structure"]["label"])
    return {"variant_id": v["variant_id"], "natal": natal, "verification": chart["verification"], "natal_structure_ref": base["validation"],
            "periods": out, "calculation_profile_id": chart["calculation_profile_id"], "disclaimer": DISCLAIMER}
