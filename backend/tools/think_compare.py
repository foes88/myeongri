"""v11.0 '현실에서 생각해 볼 점' 수정 전후 비교(합성 명식, 사건 없음, 예측 정확성·상담 품질과 무관).
수정 전 = (분야, 톤)만으로 고른 고정 조언(THINK), 수정 후 = 이 해·이 명식에서 부각된 구조와 연결한 조언(think_for).
사용: python -m tools.think_compare [--n 12] [--out 파일.json]"""
from __future__ import annotations

import argparse
import json
from collections import Counter

from app import cases as C
from app.consult import agent, domains as D, synthesis as S, verdict as V
from tools.bias_probe import charts

DOMS = ["overall", "wealth", "career", "business"]
YEARS = [2027, 2028, 2029, 2030, 2031]
LINKED = ("쪽 변화가 있어,", "쪽이 이어져,", "쪽이 있어,")


def drivers(pre: dict, dom: str, year: int, a: dict) -> dict:
    nm = {s["name"]: s for s in pre["natal_structure"]["layer3"]["structures"]}
    P = {p["year"]: p for p in a.get("periods") or []}
    rel = D.DOMAINS[dom]["structures"] or list(S.STRUCT)
    yr = V.FA.year_reading(P[year], rel) if P.get(year) else None
    t = V.tone_for(pre, dom, yr, nm)
    return {"tone": t["tone"], "year_changes": t["sup_up"] + t["ten_up"], "partial": t["sup_part"] + t["ten_part"], "persist": t["sup_pers"] + t["ten_pers"],
            "natal": t["natal_support"] + t["natal_tension"]}, t


def run(n: int) -> dict:
    rows, linked, total, by_dom = [], 0, 0, {}
    sig_after: dict[tuple, set] = {}
    for i, ci in enumerate(charts(n, seed=7)):
        pre, _ = C.pre_for(ci, [YEARS[0]])
        a = agent.answer(pre, "종합 상담을 시작합니다", domains_=DOMS, years=YEARS, depth="detailed")
        v = a["verdict"]
        for y in YEARS:
            for b in v["detail"][str(y)]["blocks"]:
                dr, t = drivers(pre, b["domain"], y, a)
                before = list(V.THINK.get(b["domain"], {}).get(b["tone"], V.THINK["overall"]["thin"]))[:2]
                after = b["think"]
                is_linked = any(k in x for x in after for k in LINKED)
                total += 1
                linked += int(is_linked)
                c = by_dom.setdefault(b["domain"], [0, 0])
                c[0] += 1
                c[1] += int(is_linked)
                rows.append({"chart": i, "year": y, "domain": b["domain"], "tone": b["tone"], "drivers": dr, "before": before, "after": after, "linked": is_linked})
                sig_after.setdefault((b["domain"], b["tone"]), set()).add(tuple(after))
    distinct_before = Counter()
    for r in rows:
        distinct_before[(r["domain"], r["tone"], tuple(r["before"]))] += 1
    return {"blocks": total, "linked_blocks": linked, "linked_ratio": round(linked / max(1, total), 3),
            "by_domain_linked": {d: {"blocks": c[0], "linked": c[1]} for d, c in by_dom.items()},
            "distinct_think_sets_before": len({(r["domain"], tuple(r["before"])) for r in rows}),
            "distinct_think_sets_after": len({(r["domain"], tuple(r["after"])) for r in rows}),
            "tone_unchanged_note": "think 만 바꿨고 톤·판정·헤드라인은 건드리지 않는다(테스트 보장)", "rows": rows}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--out")
    a = ap.parse_args()
    res = run(a.n)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, ensure_ascii=False, indent=1))
