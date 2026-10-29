"""Layer 5 — 대운·세운: 원국 + 운 결합, 합충 변화, 구조 변화, 대운 교체·입춘 구간 분리, 특정 연도·복수 연도 비교.

원국 판단과 운의 영향을 분리한다. 운에서 새로 생긴 관계는 '신규 관계 후보'일 뿐 사건 예측이 아니다.
세운은 입춘(절대 시각)에서 바뀌므로 양력 1월~입춘 사이는 직전 해의 세운이다. 대운 교체일이 해 안에 있으면 구간을 나눈다.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from itertools import combinations
from zoneinfo import ZoneInfo

from ..astro_core import engine as astro
from ..report_checks import HIDDEN_STEMS_PROFILE, ten_god
from ..chart_analysis import GROUP_OF
from .evidence import ClaimNode, EvidenceGraph
from .layer1 import POS_KO
from .layer2 import BANGHAP, CHUNG, HAE, PA, SAMHAP, STEM_HAP, WANGJI, YUKHAP
from .layer3 import analyze_layer3
from .rules import RULES

SEOUL = ZoneInfo("Asia/Seoul")
LABEL = {"luck": "대운", "year": "세운"}


def _node(g, vid, rule_id, prefix, **kw) -> ClaimNode:
    return g.add(ClaimNode(claim_id=g.new_id(prefix), chart_variant_id=vid, rule_id=rule_id, school_id=RULES[rule_id]["school_id"],
                           source_references=RULES[rule_id]["sources"], counter_checked=True, **kw))


def segments_for_year(chart: dict, year: int) -> list[dict]:
    """해당 양력 연도를 대운 교체일·입춘으로 나눈 구간. chart 는 ChartCalculationResult.to_dict()."""
    d = chart["daeun"]
    cycles = d["cycles"]
    first = date.fromisoformat(d["first_luck_date"])
    start, end = date(year, 1, 1), date(year + 1, 1, 1)
    lichun = datetime.fromisoformat(astro.sewun(year)["starts_utc"]).astimezone(SEOUL).date()
    bounds = {start, end}
    for b in [lichun, first] + [date.fromisoformat(c["start_date"]) for c in cycles]:
        if start < b < end:
            bounds.add(b)
    pts = sorted(bounds)

    def luck_at(day: date) -> dict:
        if day < first:
            return {"pillar": None, "label": "대운 이전(첫 대운 시작 전; 소운은 미구현)"}
        cur = None
        for c in cycles:
            if date.fromisoformat(c["start_date"]) <= day:
                cur = c
        return {"pillar": cur["pillar"], "label": f"{cur['order']}번째 대운", "order": cur["order"]} if cur else {"pillar": None, "label": "범위 밖"}

    names: dict[date, list[str]] = {}
    names.setdefault(lichun, []).append("입춘(세운 교체)")
    names.setdefault(first, []).append("첫 대운 시작")
    for c in cycles:
        names.setdefault(date.fromisoformat(c["start_date"]), []).append(f"{c['order']}번째 대운 시작")
    out = []
    for a, b in zip(pts, pts[1:]):
        year_for_pillar = year if a >= lichun else year - 1
        out.append({"from": a.isoformat(), "to": (b - timedelta(days=1)).isoformat(), "luck": luck_at(a), "sewun_year": year_for_pillar,
                    "sewun_pillar": astro.gz(year_for_pillar - 4), "starts_at_boundary": names.get(a, []) if a != start else []})
    return out


def _incoming_relations(natal: dict[str, str], who: str, pillar: str) -> list[dict]:
    """운 기둥(who) 의 천간·지지가 원국과 만드는 관계(후보). 인접 개념 없음 — 모든 원국 기둥과 쌍으로 비교."""
    rel = []
    stem, br = pillar[0], pillar[1]
    for pos, gz in natal.items():
        s2, b2 = gz[0], gz[1]
        key = frozenset((stem, s2))
        if key in STEM_HAP:
            rel.append({"type": "천간합", "with": pos, "chars": f"{stem}{s2}", "note": f"{STEM_HAP[key]} 합 후보(합화 여부 미확정)"})
        bk = frozenset((br, b2))
        for table, name in ((YUKHAP, "육합"),):
            if bk in table:
                rel.append({"type": name, "with": pos, "chars": f"{br}{b2}", "note": f"{table[bk]}"})
        for table, name in ((CHUNG, "충"), (PA, "파"), (HAE, "해")):
            if bk in table:
                rel.append({"type": name, "with": pos, "chars": f"{br}{b2}", "note": "존재만 확인"})
    # 삼합/반합/방합 완성 후보: 원국에 2글자가 있고 운이 나머지를 채우는 경우
    nb = {gz[1] for gz in natal.values()}
    for el, trio in SAMHAP.items():
        if br in trio and len(nb & set(trio)) >= 1 and br not in nb:
            have = nb & set(trio)
            if len(have) == 2:
                rel.append({"type": "삼합 완성 후보", "with": "원국 2글자", "chars": trio, "note": f"{el}국, 운이 {br} 을 채움"})
            elif have & WANGJI or br in WANGJI:
                rel.append({"type": "반합 형성 후보", "with": "원국 1글자", "chars": "".join(sorted(have | {br}, key=trio.index)), "note": f"{el}국 반합"})
    for el, trio in BANGHAP.items():
        if br in trio and br not in nb and len(nb & set(trio)) == 2:
            rel.append({"type": "방합 완성 후보", "with": "원국 2글자", "chars": trio, "note": f"{el}방"})
    # 복음(같은 글자): 운 지지가 원국 지지와 같음
    for pos, gz in natal.items():
        if gz[1] == br:
            rel.append({"type": "복음(같은 지지)", "with": pos, "chars": br * 2, "note": "동일 지지 재등장"})
        if gz[0] == stem:
            rel.append({"type": "복음(같은 천간)", "with": pos, "chars": stem * 2, "note": "동일 천간 재등장"})
    return rel


def analyze_period(natal: dict[str, str], luck: str | None, year_pillar: str | None, g: EvidenceGraph, vid: str = "v1", l1_label: str | None = None,
                   tag: str = "L5") -> dict:
    """원국 + (대운, 세운) 결합 분석. 둘 다 None 이면 원국만."""
    extra = {k: v for k, v in (("luck", luck), ("year", year_pillar)) if v}
    day_stem = natal["day"][0]
    res: dict = {"luck": luck, "sewun": year_pillar, "stems": {}, "relations": {}, "structure_delta": []}
    for who, pil in extra.items():
        god = ten_god(day_stem, pil[0])
        rels = _incoming_relations(natal, who, pil)
        res["stems"][who] = {"pillar": pil, "stem_god": god, "stem_group": GROUP_OF[god], "branch_main_hidden_god": ten_god(day_stem, HIDDEN_STEMS_PROFILE[pil[1]][0])}
        res["relations"][who] = rels
        n = _node(g, vid, "MG-L5-LUCK-BRANCH", tag,
                  supporting_evidence=[f"{LABEL[who]} {pil} 지지 {pil[1]} ↔ 원국 {POS_KO[r['with']] if r['with'] in POS_KO else r['with']}: {r['type']} {r['chars']}"
                                       for r in rels] or [f"{LABEL[who]} {pil} 와 원국 사이에 합·충·형·파·해 관계 없음"],
                  counter_evidence=["새 관계는 원국 구조를 바꾸는 후보이며, 합충이 있어도 작용·결과를 확정하지 않음",
                                    "원국의 인접·월령 조건이 운의 관계에서도 같이 적용되는지는 학파 논쟁"],
                  applicability=["원국 확정(변형·절입 모호성 없음)", f"{LABEL[who]} 기둥 확정"], exclusions=["월운", "소운"], conflicting_claims=[],
                  uncertainty="운 해석의 길흉은 학파별로 달라 구조 변화로만 기록", interpretation_summary=f"{LABEL[who]} {pil}: 신규 관계 후보 {len(rels)}개",
                  status="신규 관계 있음" if rels else "신규 관계 없음", attributes={"who": who})
        res["relations"][who + "_claim"] = n.claim_id
    # 구조 변화: Layer 3 순위 비교 (원국 vs 원국+운). 노드는 별도 그래프에 두지 않기 위해 임시 그래프 사용.
    if extra:
        base = analyze_layer3(natal, EvidenceGraph(), vid, None, l1_label)
        plus = analyze_layer3(natal, g, vid, None, l1_label, extra=extra, tag=tag + "-S")
        for b, p in zip(base["structures"], plus["structures"]):
            if b["rank"] != p["rank"]:
                kind = "강화" if p["rank"] > b["rank"] else "약화"
                if b["rank"] == 0:
                    kind = "신규 출현"
                nn = _node(g, vid, "MG-L5-STRUCTURE-DELTA", tag, supporting_evidence=[f"{b['name']}: 원국 '{b['label']}' → 운 포함 '{p['label']}'"],
                           counter_evidence=["운의 글자는 일정 기간만 작용하므로 원국 구조와 같은 비중으로 보지 않는다는 견해",
                                             "운 글자가 암장 본기로만 들어오면 천간 노출과 다름"],
                           applicability=["Layer 3 출현 순위 비교"], exclusions=["합충으로 인한 글자 변화"], conflicting_claims=[],
                           uncertainty="구조 순위 변화이며 사건 발생을 뜻하지 않음", interpretation_summary=f"{b['name']} {kind}", status=kind,
                           attributes={"structure": b["name"], "before": b["rank"], "after": p["rank"]})
                res["structure_delta"].append({"structure": b["name"], "before": b["label"], "after": p["label"], "change": kind, "claim_id": nn.claim_id})
    return res


def analyze_year(chart: dict, natal: dict[str, str], year: int, vid: str = "v1", l1_label: str | None = None) -> dict:
    g = EvidenceGraph()
    segs = segments_for_year(chart, year)
    out = []
    for s in segs:
        sub = analyze_period(natal, s["luck"]["pillar"], s["sewun_pillar"], g, vid, l1_label)
        seg_node = _node(g, vid, "MG-L5-SEGMENT", "L5-SEG", supporting_evidence=[f"{s['from']}~{s['to']}: {s['luck']['label']} {s['luck'].get('pillar') or ''} / 세운 {s['sewun_pillar']}({s['sewun_year']}년 입춘~)"],
                         counter_evidence=["대운 교체일은 3일=1년 환산(프로필 의존)이라 수일~수주 오차 범위가 있음", "입춘 기준 세운 외 정월(음력 설) 기준 학파가 있음"],
                         applicability=["calculation_profile_id 일치"], exclusions=["월운"], conflicting_claims=[],
                         uncertainty="구간 경계는 계산 프로필에 따라 이동할 수 있음", interpretation_summary="구간 분리", status="구간")
        out.append({**s, "analysis": sub, "segment_claim": seg_node.claim_id})
    problems = g.validate()
    return {"year": year, "segments": out, "split": len(out) > 1, "graph": g.to_dict(), "validation": {"ok": not problems, "problems": problems},
            "daeun_profile": chart["daeun"]["calculation_profile_id"]}


def analyze_years(chart: dict, natal: dict[str, str], years: list[int], vid: str = "v1", l1_label: str | None = None) -> dict:
    """복수 연도 분석 + 점수 없는 나란히 비교 구조(연도 비교·5년·10년 범위 공통)."""
    per = {y: analyze_year(chart, natal, y, vid, l1_label) for y in years}
    rows = []
    for y, r in per.items():
        feats = {"segments": len(r["segments"]), "relation_types": {}, "structure_changes": [], "luck_pillars": [], "sewun_pillars": []}
        for s in r["segments"]:
            feats["luck_pillars"].append(s["luck"].get("pillar")); feats["sewun_pillars"].append(s["sewun_pillar"])
            for who, rels in s["analysis"]["relations"].items():
                if who.endswith("_claim"):
                    continue
                for x in rels:
                    feats["relation_types"][f"{LABEL[who]}:{x['type']}"] = feats["relation_types"].get(f"{LABEL[who]}:{x['type']}", 0) + 1
            feats["structure_changes"] += [f"{d['structure']} {d['change']}" for d in s["analysis"]["structure_delta"]]
        rows.append({"year": y, **feats})
    return {"years": years, "per_year": per, "comparison": {"rows": rows, "note": "점수·순위·길흉 비교가 아니라 특징을 나란히 둔 것. 연도 간 우열을 말하지 않는다"},
            "rule_id": "MG-L5-COMPARE"}
