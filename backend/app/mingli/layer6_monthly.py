"""Layer 6 — 월운(월별 흐름). 대운·세운에 월 기둥을 더해 '그 달이 년 단위 판단에 더하는 변화'만 기록한다.

- 월 기둥은 검증된 Astro-Core 의 연·월주 계산(절입 기준)을 그대로 사용한다. 월 경계는 절입이 속한 '날짜(한국 날짜)' 단위로 표시한다(절입 시각은 같은 날 안에서 달라질 수 있음).
- 새 규칙을 등록하지 않는다: 대운·세운 관계 계산(MG-L5-LUCK-BRANCH)과 구조 변화(MG-L5-STRUCTURE-DELTA)를 월 기둥에 적용한 확장이며 구현자 규약이다(고전 원문 대조 없음).
- 비교 기준은 '원국 + 대운 + 세운'이고, 월운 포함 후의 변화만 구조 변화로 기록한다(원국과의 비교가 아니므로 연 단위 변화를 되풀이하지 않는다).
- 월운 관계는 후보일 뿐 사건 예측이 아니다.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ..astro_core import engine as astro
from ..chart_analysis import GROUP_OF
from ..report_checks import HIDDEN_STEMS_PROFILE, ten_god
from .evidence import EvidenceGraph
from .layer3 import analyze_layer3
from .layer5 import SEOUL, _incoming_relations, _node, segments_for_year

NOTE = "월운은 대운·세운과 같은 관계 계산을 월 기둥에 적용한 확장이며 구현자 규약입니다(고전 원문 대조 없음). 사건 예측이 아닙니다."


def month_segments(year: int) -> list[dict]:
    """해당 양력 연도를 절입(월 경계)으로 나눈 구간. 정오(한국시간) 기준으로 날짜별 월 기둥을 읽어 같은 기둥이 이어지는 날들을 묶는다."""
    out: list[dict] = []
    d = date(year, 1, 1)
    while d.year == year:
        utc = datetime(d.year, d.month, d.day, 12, tzinfo=SEOUL).astimezone(timezone.utc)
        ypil, mpil, _ = astro.year_month_pillars(utc)
        if out and out[-1]["month_pillar"] == mpil and out[-1]["sewun_pillar"] == ypil:
            out[-1]["to"] = d.isoformat()
        else:
            out.append({"from": d.isoformat(), "to": d.isoformat(), "month_pillar": mpil, "sewun_pillar": ypil})
        d += timedelta(days=1)
    return out


def _luck_on(chart: dict, day: str) -> str | None:
    cur = None
    first = date.fromisoformat(chart["daeun"]["first_luck_date"])
    dd = date.fromisoformat(day)
    if dd < first:
        return None
    for c in chart["daeun"]["cycles"]:
        if date.fromisoformat(c["start_date"]) <= dd:
            cur = c["pillar"]
    return cur


def analyze_months(chart: dict, natal: dict[str, str], year: int, vid: str = "v1", l1_label: str | None = None) -> dict:
    g = EvidenceGraph()
    day_stem = natal["day"][0]
    months = []
    for m in month_segments(year):
        # 한 월 구간 안에서 대운이 바뀌는 날이 있으면 구간을 나눈다(대운 기준이 하나인 구간만 분석)
        pieces, cur = [], None
        d, end = date.fromisoformat(m["from"]), date.fromisoformat(m["to"])
        while d <= end:
            lk = _luck_on(chart, d.isoformat())
            if cur and cur["luck"] == lk:
                cur["to"] = d.isoformat()
            else:
                cur = {"from": d.isoformat(), "to": d.isoformat(), "luck": lk}
                pieces.append(cur)
            d += timedelta(days=1)
        for p in pieces:
            mp, yp, lk = m["month_pillar"], m["sewun_pillar"], p["luck"]
            god = ten_god(day_stem, mp[0])
            rels = _incoming_relations(natal, "month", mp)
            n = _node(g, vid, "MG-L5-LUCK-BRANCH", "L6", supporting_evidence=[f"월운 {mp} 지지 {mp[1]} ↔ 원국 {r['with']}: {r['type']} {r['chars']}" for r in rels] or [f"월운 {mp} 와 원국 사이에 합·충·형·파·해 관계 없음"],
                      counter_evidence=["새 관계는 후보이며 작용·결과를 확정하지 않음", "월운의 비중과 적용 방식은 학파마다 다름", NOTE],
                      applicability=["원국 확정", "월 기둥은 절입 기준(날짜 단위 경계)"], exclusions=["일운", "소운"], conflicting_claims=[],
                      uncertainty="월운 해석은 구현자 규약이며 고전 원문과 대조하지 않았음", interpretation_summary=f"월운 {mp}: 신규 관계 후보 {len(rels)}개",
                      status="신규 관계 있음" if rels else "신규 관계 없음", attributes={"who": "month", "month_pillar": mp})
            delta = []
            if lk:
                base = analyze_layer3(natal, EvidenceGraph(), vid, None, l1_label, extra={"luck": lk, "year": yp})
                plus = analyze_layer3(natal, g, vid, None, l1_label, extra={"luck": lk, "year": yp, "month_luck": mp}, tag="L6-S")
                for b, a in zip(base["structures"], plus["structures"]):
                    if b["rank"] != a["rank"]:
                        kind = "신규 출현" if b["rank"] == 0 else ("강화" if a["rank"] > b["rank"] else "약화")
                        nn = _node(g, vid, "MG-L5-STRUCTURE-DELTA", "L6", supporting_evidence=[f"{b['name']}: 대운·세운 포함 '{b['label']}' → 월운 포함 '{a['label']}'"],
                                   counter_evidence=["월운은 짧은 기간만 작용하므로 대운·세운과 같은 비중으로 보지 않는다는 견해", NOTE], applicability=["Layer 3 출현 순위 비교(월운 포함 전후)"],
                                   exclusions=["합충으로 인한 글자 변화"], conflicting_claims=[], uncertainty="구조 순위 변화이며 사건 발생을 뜻하지 않음",
                                   interpretation_summary=f"{b['name']} {kind}(월운)", status=kind, attributes={"structure": b["name"], "before": b["rank"], "after": a["rank"]})
                        delta.append({"structure": b["name"], "before": b["label"], "after": a["label"], "change": kind, "claim_id": nn.claim_id})
            months.append({"from": p["from"], "to": p["to"], "month_pillar": mp, "sewun_pillar": yp, "luck": lk, "stem_god": god, "stem_group": GROUP_OF[god],
                           "branch_main_hidden_god": ten_god(day_stem, HIDDEN_STEMS_PROFILE[mp[1]][0]), "relations": rels, "structure_delta": delta, "claim_id": n.claim_id})
    problems = g.validate()
    return {"year": year, "months": months, "graph": g.to_dict(), "validation": {"ok": not problems, "problems": problems}, "note": NOTE,
            "daeun_profile": chart["daeun"]["calculation_profile_id"]}
