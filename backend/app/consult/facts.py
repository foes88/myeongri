"""시기 사실 계층: 구간(입춘·대운 교체로 나뉜 기간)별 구조 변화·관계를 '기간(일수)'으로 가중해 해(年) 단위 사실로 모은다.

왜 필요한가: 양력 한 해에는 입춘 전(1월 1일~입춘 전날)처럼 전해의 세운이 적용되는 짧은 구간이 섞여 있다. 그 구간에서만 생기는 변화를
'그해 전체의 변화'로 말하면 틀린다. 구간이 한 해의 절반 이상을 덮을 때만 '그해의 흐름'으로 세고, 그보다 짧으면 '일부 기간'으로 따로 말한다.
이 규칙(절반 기준)은 구현자 규약이다.
"""
from __future__ import annotations

from datetime import date

UP = ("강화", "신규 출현")
DOWN = ("약화", "소멸")
BAD_REL = ("충", "형(부분)", "삼형", "무례지형(子卯)", "자형", "파", "해")
GOOD_REL = ("육합", "천간합", "반합 형성 후보", "삼합 완성 후보", "방합 완성 후보", "삼합(완전)")
MAJOR_FRAC = 0.5


def _days(seg: dict) -> int:
    return (date.fromisoformat(seg["to"]) - date.fromisoformat(seg["from"])).days + 1


def year_reading(period: dict, rel: list[str]) -> dict:
    segs = period["segments"]
    days = [_days(s) for s in segs]
    total = sum(days)
    ups: dict[str, dict] = {}
    downs: dict[str, dict] = {}
    for s, d in zip(segs, days):
        for x in s["delta"]:
            if x["structure"] not in rel:
                continue
            tgt = ups if x["change"] in UP else (downs if x["change"] in DOWN else None)
            if tgt is None:
                continue
            r = tgt.setdefault(x["structure"], {"days": 0, "ranges": [], "claim_ids": [], "change": x["change"]})
            r["days"] += d
            r["ranges"].append((s["from"], s["to"]))
            r["claim_ids"].append(x["claim_id"])
    for r in list(ups.values()) + list(downs.values()):
        r["frac"] = r["days"] / total
    bad: dict[str, int] = {}
    for s, d in zip(segs, days):
        for t in {r["type"] for r in s["relations"] if r["who"] == "year" and r["type"] in BAD_REL}:
            bad[t] = bad.get(t, 0) + d
    lucks = [s["luck"] for s in segs]
    return {"year": period["year"], "total_days": total, "split": len(segs) > 1, "luck_split": len(set(lucks)) > 1,
            "ups": [n for n, r in ups.items() if r["frac"] >= MAJOR_FRAC], "ups_partial": [n for n, r in ups.items() if r["frac"] < MAJOR_FRAC], "ups_detail": ups,
            "downs": [n for n, r in downs.items() if r["frac"] >= MAJOR_FRAC], "downs_detail": downs,
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


def merged_range(ranges: list[tuple[str, str]]) -> tuple[str, str]:
    return min(r[0] for r in ranges), max(r[1] for r in ranges)
