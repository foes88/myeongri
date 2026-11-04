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


COMMON = re.compile(r"입춘|전해의 기운이 적용|예측|보장|구간이 나뉘|사주만으로 말할 수 있는 것이 적으니|근거가 부족")   # 공통 안내·범위 제한 문장(반복이 필요)


def classify(area: str, sentence: str) -> str:
    """반복 문장의 성격. common=공통 안내·범위 제한(반복 필요) / generic_advice=근거 없이 (분야,톤)만으로 붙는 조언 / template_explain=분야·자리의 고정 설명 / evidence_text=근거 문장."""
    if COMMON.search(sentence):
        return "common"
    if area == "think":
        return "generic_advice"
    if area in ("headline", "story", "why", "period"):
        return "template_explain" if area in ("story", "why") else "evidence_text"
    return "evidence_text"


def run(n: int) -> dict:
    per_chart = []
    freq: dict[str, set[int]] = defaultdict(set)
    area_of: dict[str, str] = {}
    cross: Counter = Counter()          # 같은 명식·같은 해의 서로 다른 분야에서 같은 문장이 나오는 횟수
    for i, ci in enumerate(charts(n, seed=7)):
        pre, _ = C.pre_for(ci, [YEARS[0]])
        a = agent.answer(pre, "종합 상담을 시작합니다", domains_=DOMS, years=YEARS, depth="detailed")
        v = a["verdict"]
        col = collect(v)
        within: Counter = Counter()
        by_year_sent: dict[tuple[str, str], set[str]] = defaultdict(set)
        for area, items in col.items():
            for where, s in items:
                freq[s].add(i)
                area_of.setdefault(s, area)
                within[s] += 1
                y, _, dom = where.partition("/")
                if dom:
                    by_year_sent[(y, s)].add(dom)
        for (y, sent), doms in by_year_sent.items():
            if len(doms) >= 2:
                cross[sent] += 1
        allv = [s for items in col.values() for _, s in items]
        per_chart.append({"chart": i, "sentences": len(allv), "unique": len(set(allv)), "within_dup_ratio": round(1 - len(set(allv)) / max(1, len(allv)), 3),
                          "vague": sum(1 for s in allv if VAGUE.search(s)), "rows_changing": sum(1 for r in v["period"]["years"] if r.get("change"))})
    shared = {s: len(c) for s, c in freq.items() if len(c) >= max(2, n // 2)}
    kinds = Counter(classify(area_of[s], s) for s in shared)
    all_sent = sum(p["sentences"] for p in per_chart)
    tot_sent = sum(p["sentences"] for p in per_chart)
    return {"charts": n, "per_chart": per_chart, "mean_within_dup_ratio": round(sum(p["within_dup_ratio"] for p in per_chart) / n, 3),
            "mean_vague_ratio": round(sum(p["vague"] for p in per_chart) / max(1, tot_sent), 3),
            "sentences_shared_by_half_or_more_charts": len(shared), "shared_by_kind": dict(kinds),
            "cross_domain_same_sentence_cases": sum(cross.values()), "cross_domain_examples": [(c, k[:70]) for k, c in cross.most_common(6)],
            "denominator": {"charts": n, "domains": DOMS, "years": YEARS, "sentences_total": all_sent, "unique_sentences": len(freq), "min_sentence_chars": 12,
                            "rules": "문장=마침표/물음표/느낌표 뒤 공백으로 분리, 12자 이상, 공백 정규화 후 완전 일치. within_dup=1-고유/전체(명식 하나 안에서 연도·분야를 가로지른 반복). shared=절반 이상의 명식에 같은 문장.",
                            "vague_regex": VAGUE.pattern},
            "examples_shared": [(s, c, classify(area_of[s], s)) for s, c in sorted(shared.items(), key=lambda kv: -kv[1])[:10]]}


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
