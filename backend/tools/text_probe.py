"""v11.0 풀이 문장 품질 점검(합성 명식, 사건 없음). 같은 문장이 서로 다른 명식·연도·분야에서 얼마나 반복되는지, 모호한 표현이 얼마나 쓰였는지 센다.
예측 정확성과 무관하며 '문장이 사람마다·시기마다 달라지는가'만 본다. 사용: python -m tools.text_probe [--n 12] [--out 파일.json]"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict

from app import cases as C
from app.consult import agent
from tools.bias_probe import charts

DOMS = ["overall", "wealth", "career", "love_marriage", "family"]
YEARS = [2027, 2028, 2029, 2030, 2031]
VAGUE = re.compile(r"수 있습니다|볼 만합니다|살펴볼 만|일 수도|어느 정도|있다고 읽|흐름이 있")


def sentences(t: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", t) if len(s.strip()) >= 12]


def collect(v: dict) -> dict[str, list[tuple[str, str]]]:
    """(영역, 문장) 목록: 연도 패널에 쓰이는 문장과 분야 블록 문장."""
    out: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for y, d in (v.get("detail") or {}).items():
        for b in d["blocks"]:
            for key in ("headline",):
                out["headline"] += [(f"{y}/{b['domain']}", x) for x in sentences(b[key])]
            for t in b.get("story", []):
                out["story"] += [(f"{y}/{b['domain']}", x) for x in sentences(t)]
            for t in b.get("think", []):
                out["think"] += [(f"{y}/{b['domain']}", x) for x in sentences(t)]
            for t in (b.get("why") or {}).get("natal", []) + (b.get("why") or {}).get("period", []):
                out["why"] += [(f"{y}/{b['domain']}", x) for x in sentences(t)]
    for r in (v.get("period") or {}).get("years", []):
        for k in ("change", "caution", "why"):
            if r.get(k):
                out["period"] += [(str(r["year"]), x) for x in sentences(r[k])]
    return out


def run(n: int) -> dict:
    per_chart = []
    freq: dict[str, set[int]] = defaultdict(set)
    for i, ci in enumerate(charts(n, seed=7)):
        pre, _ = C.pre_for(ci, [YEARS[0]])
        a = agent.answer(pre, "종합 상담을 시작합니다", domains_=DOMS, years=YEARS, depth="detailed")
        v = a["verdict"]
        col = collect(v)
        within: Counter = Counter()
        for area, items in col.items():
            for where, s in items:
                freq[s].add(i)
                within[s] += 1
        allv = [s for items in col.values() for _, s in items]
        per_chart.append({"chart": i, "sentences": len(allv), "unique": len(set(allv)), "within_dup_ratio": round(1 - len(set(allv)) / max(1, len(allv)), 3),
                          "vague": sum(1 for s in allv if VAGUE.search(s)), "rows_changing": sum(1 for r in v["period"]["years"] if r.get("change"))})
    shared = {s: len(c) for s, c in freq.items() if len(c) >= max(2, n // 2)}
    tot_sent = sum(p["sentences"] for p in per_chart)
    return {"charts": n, "per_chart": per_chart, "mean_within_dup_ratio": round(sum(p["within_dup_ratio"] for p in per_chart) / n, 3),
            "mean_vague_ratio": round(sum(p["vague"] for p in per_chart) / max(1, tot_sent), 3),
            "sentences_shared_by_half_or_more_charts": len(shared), "examples_shared": sorted(shared.items(), key=lambda kv: -kv[1])[:8]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--out")
    a = ap.parse_args()
    res = run(a.n)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "per_chart"}, ensure_ascii=False, indent=1))
    for p in res["per_chart"]:
        print(p)
