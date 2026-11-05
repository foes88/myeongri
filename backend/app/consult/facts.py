"""시기 사실 계층: 구간(입춘·대운 교체로 나뉜 기간)별 구조 변화·관계를 해(年) 단위 사실로 모은다.

한 해의 변화를 '대표 해석'과 '일부 기간의 변화'로 나누는 기준(구현자 규약. 고전 원문 근거 없음. 자동 지표에 맞추려고 정한 값이 아니라 아래 논리로 정했다):

1) 지속 일수(frac): 한 구조의 변화가 이어지는 일수 ÷ 그해 일수.
2) 원인 글자(drivers): 변화를 만든 운 글자가 10년 큰 흐름(대운)뿐인지, 그해(세운)가 끼어 있는지(구간 증거의 '대운…/세운…' 항목으로 판별).
   세운이 끼면 그 변화는 그 세운이 적용되는 기간(입춘~다음 입춘)에만 존재하므로 구간 길이가 곧 변화의 수명이다.
   대운만으로 생긴 변화는 해가 끝나도 새 대운이 이어지는 동안 계속된다(수명이 해를 넘는다).
3) 구간 위치와 종류: 입춘 전 구간(1월 1일~입춘 전날)은 전해 세운이 적용되는 기간이다. '신규 출현'과 '강화'는 구분해 말한다.
4) 대운 교체 여부: 해 안에서 대운이 바뀌면 교체일 앞뒤를 따로 읽는다.
5) 불확실성: 대운 교체일은 '3일=1년' 환산이라 며칠~몇 주 달라질 수 있다. 변화 구간의 경계가 교체일이면 그 사실을 밝힌다.

분류(구조별):
- year(대표): 지속 일수가 그해의 절반 이상. 그해를 대표하는 변화로 말한다.
- persistent(이어지는 변화): 절반 미만이지만 원인이 대운뿐이고 해 끝까지 이어진다. 해의 대표 변화는 아니지만 '이후 해에도 이어질 변화의 시작'으로 따로 말한다.
- partial(일부 기간): 그 밖의 짧은 변화. 해당 기간에 한정해 말하고 해 전체의 흐름으로 세지 않는다.
절반(0.5) 기준은 '과반이면 그해를 대표한다'는 뜻이며, 원인·수명을 함께 보므로 임계값 하나가 판정을 정하지 않는다.
"""
from __future__ import annotations

from datetime import date, timedelta

UP = ("강화", "신규 출현")
DOWN = ("약화", "소멸")
BAD_REL = ("충", "형(부분)", "삼형", "무례지형(子卯)", "자형", "파", "해")
GOOD_REL = ("육합", "천간합", "반합 형성 후보", "삼합 완성 후보", "방합 완성 후보", "삼합(완전)")
MAJOR_FRAC = 0.5


def _days(seg: dict) -> int:
    return (date.fromisoformat(seg["to"]) - date.fromisoformat(seg["from"])).days + 1


def _drivers(seg: dict, name: str) -> set[str]:
    """이 구간에서 구조 증거에 들어온 운 글자의 출처. 증거 항목은 '대운간 甲(…)', '→ 세운지 지장간 …' 형태."""
    out = set()
    for e in seg.get("struct_evidence", {}).get(name, []):
        e = e.lstrip("→ ").strip()
        if e.startswith("대운"):
            out.add("luck")
        elif e.startswith("세운"):
            out.add("sewun")
    return out


def classify_change(rec: dict, year: int, total_days: int) -> str:
    """구조 하나의 변화 기록(rec: days, ranges, drivers, ends_year_end)을 year / persistent / partial 로 분류."""
    frac = rec["days"] / total_days
    if frac >= MAJOR_FRAC:
        return "year"
    if rec["drivers"] == {"luck"} and rec["ends_year_end"]:
        return "persistent"
    return "partial"


def year_reading(period: dict, rel: list[str]) -> dict:
    segs = period["segments"]
    year = period["year"]
    days = [_days(s) for s in segs]
    total = sum(days)
    luck_edges = {s["from"] for i, s in enumerate(segs) if i > 0 and s["luck"] != segs[i - 1]["luck"]}  # 대운이 바뀐 날(구간 시작일)
    ups: dict[str, dict] = {}
    downs: dict[str, dict] = {}
    for s, d in zip(segs, days):
        for x in s["delta"]:
            if x["structure"] not in rel:
                continue
            tgt = ups if x["change"] in UP else (downs if x["change"] in DOWN else None)
            if tgt is None:
                continue
            r = tgt.setdefault(x["structure"], {"days": 0, "ranges": [], "claim_ids": [], "change": x["change"], "kinds": set(), "drivers": set(), "ends_year_end": False, "luck_edge": False})
            r["days"] += d
            r["ranges"].append((s["from"], s["to"]))
            r["claim_ids"].append(x["claim_id"])
            r["kinds"].add(x["change"])
            r["drivers"] |= _drivers(s, x["structure"])
            r["ends_year_end"] = r["ends_year_end"] or s["to"] == f"{year}-12-31"
            r["luck_edge"] = r["luck_edge"] or s["from"] in luck_edges
    for r in ups.values():
        r["frac"] = r["days"] / total
        r["category"] = classify_change(r, year, total)
    for r in downs.values():
        r["frac"] = r["days"] / total
        r["category"] = classify_change(r, year, total)
    bad: dict[str, int] = {}
    for s, d in zip(segs, days):
        for t in {r["type"] for r in s["relations"] if r["who"] == "year" and r["type"] in BAD_REL}:
            bad[t] = bad.get(t, 0) + d
    lucks = [s["luck"] for s in segs]
    cat = lambda dct, c: [n for n, r in dct.items() if r["category"] == c]
    return {"year": year, "pre_end": pre_ipchun_end(segs), "total_days": total, "split": len(segs) > 1, "luck_split": len(set(lucks)) > 1, "luck_edges": sorted(luck_edges),
            "ups": cat(ups, "year"), "ups_persistent": cat(ups, "persistent"), "ups_partial": cat(ups, "partial"), "ups_detail": ups,
            "downs": cat(downs, "year"), "downs_detail": downs,
            "bad": sorted(t for t, d in bad.items() if d / total >= MAJOR_FRAC), "bad_partial": sorted(t for t, d in bad.items() if d / total < MAJOR_FRAC),
            "_segments": segs, "claim_ids": sorted({c for r in list(ups.values()) + list(downs.values()) for c in r["claim_ids"]})}


def palace_relations(period: dict, palaces: tuple[str, ...]) -> list[dict]:
    """그해(세운)·10년 큰 흐름(대운)이 이 분야의 궁위(원국 기둥)와 맺는 관계를 기간으로 모은다. 사실(존재)만 담는다."""
    segs = period["segments"]
    total = sum(_days(s) for s in segs)
    acc: dict[tuple, dict] = {}
    for s in segs:
        d = _days(s)
        for r in s["relations"]:
            if r["with"] not in palaces:
                continue
            pol = "bad" if r["type"] in BAD_REL else ("good" if r["type"] in GOOD_REL else None)
            if pol is None:
                continue
            k = (r["who"], r["type"], r["with"])
            a = acc.setdefault(k, {"who": r["who"], "type": r["type"], "palace": r["with"], "polarity": pol, "days": 0, "ranges": []})
            a["days"] += d
            a["ranges"].append((s["from"], s["to"]))
    out = []
    for a in acc.values():
        a["frac"] = a["days"] / total
        out.append(a)
    return sorted(out, key=lambda x: (-x["frac"], x["who"], x["type"]))


def pre_ipchun_end(segs: list[dict]) -> str | None:
    """엔진이 나눈 구간에서 ‘전해의 세운이 적용되는’ 앞쪽 구간의 마지막 날. 해의 마지막 세운과 다른 세운을 가진 첫머리 구간들의 끝이며,
    날짜를 직접 정해 두지 않는다(대운 교체가 입춘 전에 끼어 구간이 둘 이상이어도 맞는다). 입춘 전 구간이 없으면 None."""
    if len(segs) < 2:
        return None
    final, end = segs[-1]["sewun"], None
    for s in segs:
        if s["sewun"] == final:
            break
        end = s["to"]
    return end


def contiguous_ranges(ranges: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """실제로 이어진(하루 차이 이내) 범위만 하나로 합치고, 떨어져 있는 범위는 따로 둔다(‘최소 시작~최대 끝’으로 이으면 없는 기간까지 말하게 된다)."""
    out: list[list[str]] = []
    for a, b in sorted(ranges):
        if out and date.fromisoformat(a) <= date.fromisoformat(out[-1][1]) + timedelta(days=1):
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


PRE_NOTE = "(입춘 전이라 전해의 기운이 적용되는 기간)"


def _fmt_rng(a: str, b: str) -> str:
    return f"{int(a[5:7])}월 {int(a[8:10])}일~{int(b[5:7])}월 {int(b[8:10])}일"


def _list_join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else (f"{items[0]}과 {items[1]}" if len(items) == 2 else ", ".join(items[:-1]) + f"과 {items[-1]}")


def range_phrase(ranges, pre_end: str | None = None) -> str:
    """기간을 사실대로 말한다. 이어진 범위만 합치고(떨어진 범위는 따로), pre_end(입춘 전 마지막 날, 엔진 구간에서 구함)가 있으면
    그 앞쪽 기간에만 ‘입춘 전’ 설명을 붙인다. 입춘 전과 후가 이어져 있으면 둘로 나누어 각각 말한다."""
    items: list[str] = []
    for a, b in contiguous_ranges(list(ranges)):
        if pre_end and a <= pre_end:
            if b <= pre_end:
                items.append(_fmt_rng(a, b) + PRE_NOTE)
            else:
                items.append(_fmt_rng(a, pre_end) + PRE_NOTE)
                items.append(_fmt_rng((date.fromisoformat(pre_end) + timedelta(days=1)).isoformat(), b))
        else:
            items.append(_fmt_rng(a, b))
    return _list_join(items)


def merged_range(ranges: list[tuple[str, str]]) -> tuple[str, str]:
    return min(r[0] for r in ranges), max(r[1] for r in ranges)
