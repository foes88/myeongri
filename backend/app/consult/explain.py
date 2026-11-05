"""'왜 그렇게 읽나요?'의 쉬운 말 설명과, 개발자용 근거 추적(trace).

- 쉬운 설명(public): 전문 용어·근거 번호·한자 없이 '삶의 영역(사회·직업, 말년·자녀 …)'과 '기운의 성격'으로 이유를 말한다. 증거에 있는 것만 말한다.
- 추적(internal): 어떤 해·구간의 어떤 규칙 노드(claim_id)가 어떤 운 글자 때문에 변화로 잡혔는지, 기간 가중과 판정 점수까지 남긴다.
"""
from __future__ import annotations

import re

from . import facts as F
from . import readings as R
from . import synthesis as S

AREA = {"year": "초년·집안 쪽(태어난 해)", "month": "사회·직업 쪽(태어난 달)", "day": "나 자신·배우자 쪽(태어난 날)", "hour": "말년·자녀 쪽(태어난 시)"}
POS_PREFIX = {"연": "year", "월": "month", "일": "day", "시": "hour"}
EV = re.compile(r"^(→\s*)?(연|월|일|시|대운|세운)(간|지 지장간|지 지장간)\s+\S\(([^)·]+)(?:·([^)]+))?\)$")
GODS = R.GOD_PLAIN
TIER_TXT = {1: "약하게", 2: "어느 정도", 3: "뚜렷하게"}


def _parse(items: list[str]) -> list[dict]:
    out = []
    for e in items:
        m = EV.match(e.strip())
        if not m or m.group(4) not in GODS:
            continue
        arrow, where, kind, god = bool(m.group(1)), m.group(2), m.group(3), m.group(4)
        out.append({"dst": arrow, "where": where, "hidden": "지장간" in kind, "god": GODS[god], "area": AREA.get(POS_PREFIX.get(where, ""), "")})
    return out


def _areas(parsed: list[dict]) -> str:
    seen = list(dict.fromkeys(p["area"] for p in parsed if p["area"]))
    return seen[0] if seen else ""


def _and(items: list[str]) -> str:
    """기운 이름 사이는 ‘과’로 잇는다(이름 안에 이미 ‘·’이 있어 ‘ · ’로 이으면 어디서 끊기는지 알 수 없다)."""
    return items[0] if len(items) == 1 else f"{items[0]}과 {items[1]}"


def _gods(parsed: list[dict]) -> str:
    return _and(list(dict.fromkeys(p["god"] for p in parsed))[:2])


def natal_reason(s: dict, theme: str) -> str | None:
    """타고난 사주에서 이 흐름을 읽는 이유(삶의 영역과 기운으로). s: layer3 구조 항목(rank>0)."""
    ev = _parse(s.get("supporting", []))
    src = [p for p in ev if not p["dst"] and p["area"]]
    dst = [p for p in ev if p["dst"] and p["area"]]
    if not src or not dst:
        return None
    hid = all(p["hidden"] for p in src + dst)
    tail = " 겉으로 드러나기보다 속에 있는 기운이라 힘은 약하게 봅니다." if hid else ""
    a_s, a_d = _areas(src), _areas(dst)
    link = f"{a_s} 안에서 {_gods(src)}이 {_gods(dst)}으로 이어지는 짜임이 있어" if a_s == a_d else f"{a_s}의 {_gods(src)}이 {a_d}의 {_gods(dst)}으로 이어지는 짜임이 있어"
    return f"{link}, {theme}이 {TIER_TXT[s['rank']]} 있다고 읽습니다." + tail


def _seg_gods(seg: dict, name: str) -> tuple[list[str], list[str]]:
    """한 구간에서 10년 큰 흐름·그해가 들여온 기운(증거 순서 그대로, 최대 2개씩)."""
    by: dict[str, list[str]] = {"luck": [], "year": []}
    for e in seg.get("struct_evidence", {}).get(name, []):
        if not e.lstrip("→ ").startswith(("대운", "세운")):
            continue
        m = EV.match(e.strip())
        if m and m.group(4) in GODS:
            by["luck" if m.group(2) == "대운" else "year"].append(GODS[m.group(4)])
    return list(dict.fromkeys(by["luck"]))[:2], list(dict.fromkeys(by["year"]))[:2]


def _reason_for(rngs: list, luck_g: list[str], year_g: list[str], theme: str, segs: list) -> str | None:
    both = [g for g in luck_g if g in year_g]
    only_l, only_y = [g for g in luck_g if g not in year_g], [g for g in year_g if g not in luck_g]
    parts = []                                                    # 같은 기운이 두 쪽에서 들어오면 '함께 들여온'으로 한 번만 말한다(같은 문구를 되풀이하지 않는다)
    if both:
        parts.append(f"10년 큰 흐름과 그해가 함께 들여온 {_and(both)}")
    if only_l:
        parts.append(f"10년 큰 흐름{'만' if both else '이'} 들여온 {_and(only_l)}")
    if only_y:
        parts.append(f"그해{'만' if both else '가'} 들여온 {_and(only_y)}")
    if not parts:
        return None
    if len(parts) == 1:
        subject = parts[0] + "이"
    elif both:                                                    # 겹치는 기운이 있으면 ‘과’를 두 번 쓰지 않고 쉼표로 잇는다
        subject = ", ".join(parts) + "이 모두"
    else:
        subject = ", ".join(parts[:-1]) + "과 " + parts[-1] + "이"
    a, b = F.merged_range(rngs)
    span = "그해 내내" if F._days({"from": a, "to": b}) >= 350 and len(F.contiguous_ranges(list(rngs))) == 1 else F.range_phrase(rngs, F.pre_ipchun_end(segs)) + " 동안"   # 이어진 범위만, 입춘 전은 그 기간에만
    return f"{span} {subject} 타고난 사주의 기운과 이어지면서 {theme}이 더 뚜렷해지는 쪽으로 읽힙니다."


def period_reasons(period: dict | None, name: str, theme: str, detail: dict, segments: list | None = None) -> list[str]:
    """그해(또는 일부 기간)에 이 흐름이 달라지는 이유: 어떤 운 글자가 들어왔는지(10년 큰 흐름/그해).
    기간이 여러 구간에 걸치면 구간마다 증거를 보고, 들여온 기운이 같은 구간끼리 묶어 각각 말한다(첫 구간의 증거로 전체를 설명하지 않는다)."""
    segs = segments if segments is not None else period["segments"]
    rng = [tuple(r) for r in detail["ranges"]]
    groups: list[tuple[tuple, list]] = []                         # (기운 서명, 그 서명을 가진 범위들)
    for r in rng:
        seg = next((x for x in segs if (x["from"], x["to"]) == r), None)
        if not seg:
            continue
        sig = tuple(map(tuple, _seg_gods(seg, name)))
        for g in groups:
            if g[0] == sig:
                g[1].append(r)
                break
        else:
            groups.append((sig, [r]))
    out = [t for t in (_reason_for(rs, list(sig[0]), list(sig[1]), theme, segs) for sig, rs in groups) if t]
    return list(dict.fromkeys(out))                               # 기간(기운 서명)별 문장을 하나씩 — 한 덩어리로 길게 잇지 않는다


def period_reason(period: dict | None, name: str, theme: str, detail: dict, segments: list | None = None) -> str | None:
    """호환용: period_reasons 를 한 문자열로 잇는다."""
    out = period_reasons(period, name, theme, detail, segments)
    return " ".join(out) if out else None


def _when(ranges) -> str:
    a, b = F.merged_range(ranges)
    return f"{int(a[5:7])}월 {int(a[8:10])}일~{int(b[5:7])}월 {int(b[8:10])}일에는"


def nature_note(rule_ids: list[str]) -> str:
    """이 읽는 방식이 고전에 근거하는지(원문 확인 상태)를 쉬운 말로. 구현자 규약을 정설처럼 말하지 않는다."""
    from ..mingli.rules import RULES
    st = {RULES[r]["classical_status"] for r in rule_ids if r in RULES}
    if st == {"text_confirmed"}:
        return "이 짜임을 보는 관점은 고전에서도 다루는 것으로 확인했지만, ‘기회·점검’ 같은 결론의 점수화는 이 서비스가 정한 읽는 방식입니다."
    if "text_confirmed" in st or "location_confirmed" in st:
        return "이 짜임을 보는 관점은 일부만 고전 원문에서 확인했고, ‘기회·점검’ 같은 결론의 점수화는 이 서비스가 정한 읽는 방식입니다."
    return "이 짜임을 보는 관점은 아직 고전 원문 대조를 마치지 못했고, 결론의 점수화도 이 서비스가 정한 읽는 방식입니다."


# ------------------------------------------------------------------ 개발자용 추적
def trace_year(pre: dict, ans: dict, year: int, domains: list[str] | None = None) -> dict:
    """한 해의 판정이 규칙 그래프 어디에서 나왔는지. 구간별 변화·증거·노드 번호·규칙 상태·가중 비율과 표시 판정까지."""
    from ..mingli.rules import RULES
    period = next(p for p in ans["periods"] if p["year"] == year)
    nm = {s["name"]: s for s in pre["natal_structure"]["layer3"]["structures"]}
    rel = S._relevant([d for d in (domains or ans["domains"]) if d != "luck"] or ["overall"])
    fr = F.year_reading(period, rel)
    segs = []
    for s in period["segments"]:
        days = F._days(s)
        segs.append({"from": s["from"], "to": s["to"], "days": days, "luck": s["luck"], "sewun": s["sewun"],
                     "year_relations": [f"{r['type']}↔{r['with']}" for r in s["relations"] if r["who"] == "year"], "luck_relations": [f"{r['type']}↔{r['with']}" for r in s["relations"] if r["who"] == "luck"],
                     "deltas": [{"structure": d["structure"], "change": d["change"], "before": d["before"], "after": d["after"], "claim_id": d["claim_id"],
                                 "rule_id": s["claim_nodes"].get(d["claim_id"], {}).get("rule_id"),
                                 "added_by": [e for e in s.get("struct_evidence", {}).get(d["structure"], []) if e.lstrip("→ ").startswith(("대운", "세운"))]} for d in s["delta"] if d["structure"] in rel]})
    return {"year": year, "total_days": fr["total_days"], "segments": segs,
            "weighted": {"ups_major(해 전체의 변화로 셈)": fr["ups"], "ups_persistent(이어지는 변화)": fr["ups_persistent"],
                         "ups_partial(일부 기간만)": {n: {"days": r["days"], "frac": round(r["frac"], 2), "ranges": r["ranges"]} for n, r in fr["ups_detail"].items() if n in fr["ups_partial"]},
                         "classification": {n: {"category": r["category"], "frac": round(r["frac"], 2), "drivers": sorted(r["drivers"]), "ends_year_end": r["ends_year_end"], "luck_edge": r["luck_edge"], "kinds": sorted(r["kinds"])} for n, r in fr["ups_detail"].items()},
                         "downs": fr["downs"], "bad_relations_major": fr["bad"], "bad_partial": fr["bad_partial"], "luck_split": fr["luck_split"]},
            "natal_ranks": {n: nm[n]["rank"] for n in rel if n in nm}, "rule_status": {r: RULES[r]["classical_status"] for r in {RULES_OF[n] for n in rel if n in RULES_OF}}}


RULES_OF = S.RULE_OF
