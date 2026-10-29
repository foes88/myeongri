"""v6.9 완료 보고용 샘플·지표 생성(합성 명식만 사용). 실행: python -m tools.synthesis_samples > data_private/v69_samples.md"""
import re
import sys

from app.consult import agent
from app.evaluation import dataset as DS

sys.stdout.reconfigure(encoding="utf-8")


def run(years, domains, pillars=None, depth="detailed"):
    spec = DS.Spec(pillars or DS.BASE, domains=tuple(domains), years=tuple(years), cycles_first_year=2000)
    pre = DS.pre_of(spec)
    return agent.answer(pre, "질문", domains_=list(domains), years=list(years), depth=depth)


def split_sents(t):
    return [s.strip() for s in re.split(r"(?<=[.다])\s+|\n+", t) if len(s.strip()) > 8]


def dup_ratio(t):
    ss = split_sents(t)
    return 0 if not ss else round(1 - len(set(ss)) / len(ss), 3), len(ss)


def show(a, title):
    s = a["synthesis"]
    print(f"\n### {title}\n")
    print("**핵심 해석**")
    for x in s["headline"]:
        print(f"- {x['text']}  `{','.join(x['claim_ids'][:3])}`")
    print("\n**유리하게 읽히는 조건**")
    for x in s["favorable"]:
        print(f"- {x['text']}")
    print("\n**주의/상반 조건**")
    for x in s["cautions"]:
        print(f"- {x['text']}")
    print("\n**분야별 핵심 요약**")
    for d in s["domain_summaries"]:
        print(f"- {d['name']}: {d['text']}")
    f = s["period_flow"]
    if f.get("mode") == "multi":
        print("\n**연도별 한 줄**")
        for y in f["years"]:
            print(f"- {y['year']}{' ★' if y['standout'] else ''}: {y['one_line']}")
    print("\n**읽을 때 유의할 점**")
    for x in s["uncertainty"]:
        print(f"- {x['text']}")


def main():
    a = run((2030,), ("overall", "wealth", "career"))
    show(a, "2030년 종합·재물·직업/승진")
    old, new = a["narrative"], a["synthesis"]["text"]
    print(f"\n길이: 기존 narrative {len(old)}자 → 종합 {len(new)}자")
    print("\n### 문장 비교 (기존 → 종합)")
    for o, n in [(next(p["text"] for p in a["paragraphs"] if p["kind"] == "domain" and "재물" in p["text"])[:200], next(d["text"] for d in a["synthesis"]["domain_summaries"] if d["domain"] == "wealth"))]:
        print(f"- 기존: {o}…\n- 종합: {n}")
    for yrs, label in ((tuple(range(2027, 2032)), "5년"), (tuple(range(2027, 2037)), "10년")):
        b = run(yrs, ("overall", "wealth", "career"))
        show(b, f"{label} 범위(2027~)")
        o, n = b["narrative"], b["synthesis"]["text"]
        print(f"\n{label} 길이: 기존 {len(o)}자 → 종합(첫 화면) {len(n)}자 · 중복 문장 비율 기존 {dup_ratio(o)} → 종합 {dup_ratio(n)}")


if __name__ == "__main__":
    main()
