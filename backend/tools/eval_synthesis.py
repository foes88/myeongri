"""v7.0 합성 통변 품질 평가: 합성 명식 20개(실제 출생 정보 아님). 자동 지표만 계산한다 — 사람의 주관 평가와 구분.
실행: python -m tools.eval_synthesis > data_private/v70_eval.md
"""
import random
import re
import sys

from app.consult import agent
from app.consult.synthesis import STATUS_KO
from app.evaluation import dataset as DS
from app.mingli import analyze_structure

sys.stdout.reconfigure(encoding="utf-8")
CONFLICT = {"year": "丁巳", "month": "乙未", "day": "戊寅", "hour": "庚戌"}
SPARSE = {"year": "己未", "month": "甲寅", "day": "丙寅", "hour": "己未"}
HANJA = re.compile(r"[一-鿿]")
FUTURE = re.compile(r"반드시|확실히|틀림없|보장|될 것입니다|하게 됩니다|생깁니다|오릅니다|승진합니다|성공합니다|\d+\s*%|가능성이 높")
JARGON = re.compile(r"지장간|암장|성격 후보|투출|통근|득령|십성|비겁|식상|재성|관성|인성|격국|용신")
DOMS = ("overall", "wealth", "career")


def charts(n=20, seed=11):
    rnd = random.Random(seed)
    gzs = [a + b for a in DS.STEMS for b in DS.BR if DS.valid_gz(a + b)]
    out = [("기준", DS.BASE), ("격국·억부 충돌", CONFLICT), ("근거 희박", SPARSE)]
    while len(out) < n:
        p = {k: rnd.choice(gzs) for k in ("year", "month", "day", "hour")}
        try:
            analyze_structure(p, "v1")
        except Exception:
            continue
        out.append((f"무작위{len(out) - 2}", p))
    return out


def ans(p, years, doms):
    pre = DS.pre_of(DS.Spec(p, domains=tuple(doms), years=tuple(years), cycles_first_year=2000))
    return pre, agent.answer(pre, "질문", domains_=list(doms), years=list(years), depth="detailed")


def top_text(a):
    s = a["synthesis"]
    parts = [x["text"] for k in ("headline", "favorable", "cautions") for x in s[k]] + [d["text"] for d in s["domain_summaries"]]
    parts += [" ".join([r["meaning"], r["reality"], *r["counter"], r["scope"]]) for r in s["readings"]]
    return "\n".join(parts)


def sents(t):
    return [x.strip() for x in re.split(r"(?<=[.다])\s+|\n+", t) if len(x.strip()) > 8]


def main():
    rows, all_head, all_dom = [], {}, {}
    for name, p in charts():
        pre, a30 = ans(p, (2030,), DOMS)
        _, a27 = ans(p, (2027,), DOMS)
        _, a10 = ans(p, tuple(range(2027, 2037)), DOMS)
        s30, s27, s10 = a30["synthesis"], a27["synthesis"], a10["synthesis"]
        t30 = top_text(a30)
        ss = sents(t30)
        wealth = next((d["text"] for d in s30["domain_summaries"] if d["domain"] == "wealth"), "")
        career = next((d["text"] for d in s30["domain_summaries"] if d["domain"] == "career"), "")
        has_counter = any(sum(1 for s in pre["natal_structure"]["layer3"]["structures"] if s["rank"] and s["counter"]) for _ in [0])
        L = pre["natal_structure"]["layer3"]["structures"]
        rule_ok = all(x.get("rule_status") in STATUS_KO for x in s30["headline"] + s30["favorable"] if x.get("rule_status"))
        no_claim = [x["text"] for k in ("headline", "favorable", "cautions") for x in s30[k] if x["basis"] == "modern_explanation" and not x["claim_ids"]]
        claims_ok = all(c in {n["claim_id"] for n in pre["natal_structure"]["graph"]["nodes"]} or c.startswith("L5-") for c in s30["claim_ids"])
        row = {
            "chart": name, "pillars": " ".join(p.values()),
            "structures": ",".join(f"{s['name']}{s['rank']}" for s in L if s["rank"]) or "없음",
            "insufficient": s30["insufficient_evidence"],
            "wealth_vs_career_differ": wealth != career,
            "y2027_vs_2030_differ": s27["text"] != s30["text"],
            "daeun_change_named": "대운" in s30["text"] and "바뀌" in s30["text"] + " ".join(x["text"] for x in s30["period_flow"].get("sentences", [])) or "교체" in s30["text"],
            "counter_shown": bool(s30["cautions"]) or not has_counter,
            "dup_ratio": round(1 - len(set(ss)) / max(1, len(ss)), 3),
            "jargon_leak": len(JARGON.findall(t30)), "hanja_in_top": len(HANJA.findall(re.sub(r"\([^)]*[一-鿿][^)]*\)", "", t30))),
            "future_assertion": len(FUTURE.findall(t30)), "claim_missing": len(no_claim), "claim_ids_valid": claims_ok, "status_labels_ok": rule_ok,
            "avg_sent_len": round(sum(map(len, ss)) / max(1, len(ss)), 1), "max_sent_len": max(map(len, ss)) if ss else 0,
            "len_30": len(s30["text"]), "len_10yr": len(s10["text"]), "old_len_10yr": len(a10["narrative"]),
            "standout_10": s10["period_flow"].get("standout"),
            "conflict_flagged": any("학파마다" in x["text"] for x in s30["cautions"] + s30["more"]["cautions"]),
            "readings": len(s30["readings"]),
        }
        rows.append(row)
        all_head[name] = " | ".join(x["text"] for x in s30["headline"][:2])
        all_dom[name] = wealth + "||" + career
    n = len(rows)
    print("# v7.0 합성 통변 자동 평가 (합성 명식 20개, 실제 출생 정보 아님)\n")
    print("> 아래는 **자동 지표**입니다. 사람의 주관 평가(이해도·통변의 설득력)는 포함하지 않았습니다.\n")
    print("| 명식 | 사주 | 구조(rank) | 근거희박 | 재물≠직업 | 27≠30 | 대운교체 언급 | 반대근거 | 중복율 | 용어누수 | 단정표현 | 근거없는문장 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['chart']} | {r['pillars']} | {r['structures']} | {r['insufficient']} | {r['wealth_vs_career_differ']} | {r['y2027_vs_2030_differ']} | {r['daeun_change_named']} | {r['counter_shown']} | {r['dup_ratio']} | {r['jargon_leak']} | {r['future_assertion']} | {r['claim_missing']} |")
    uniq_head = len(set(all_head.values()))
    uniq_dom = len(set(all_dom.values()))
    sets = [set(sents(v)) for v in all_head.values()]
    jac = [len(a & b) / max(1, len(a | b)) for i, a in enumerate(sets) for b in sets[i + 1:]]
    agg = lambda k: sum(1 for r in rows if r[k]) if isinstance(rows[0][k], bool) else None
    print("\n## 집계\n")
    print(f"- 명식 고유성: 핵심 해석 첫 두 문장이 서로 다른 명식 수 {uniq_head}/{n}, 재물·직업 요약 조합이 서로 다른 수 {uniq_dom}/{n}, 명식 쌍 평균 문장 겹침(Jaccard) {sum(jac) / max(1, len(jac)):.2f}")
    for k, label in (("wealth_vs_career_differ", "재물과 직업 요약이 다름"), ("y2027_vs_2030_differ", "2027과 2030 결과가 다름"), ("daeun_change_named", "대운 교체 전후를 언급"), ("counter_shown", "반대 근거 노출"),
                     ("claim_ids_valid", "근거 번호가 실제 그래프에 존재"), ("status_labels_ok", "고전 확인 상태 표기가 유효")):
        print(f"- {label}: {agg(k)}/{n}")
    print(f"- 평균 중복 문장 비율 {sum(r['dup_ratio'] for r in rows) / n:.3f}, 용어 누수 합계 {sum(r['jargon_leak'] for r in rows)}, 첫 화면 한자 잔존(괄호 밖) 합계 {sum(r['hanja_in_top'] for r in rows)}")
    print(f"- 미래 단정 표현 검출 {sum(r['future_assertion'] for r in rows)}건, 근거 번호 없는 풀이 문장 {sum(r['claim_missing'] for r in rows)}건")
    print(f"- 문장 길이: 평균 {sum(r['avg_sent_len'] for r in rows) / n:.0f}자, 최장 {max(r['max_sent_len'] for r in rows)}자")
    print(f"- 길이(10년): 기존 평균 {sum(r['old_len_10yr'] for r in rows) / n:.0f}자 → 합성 평균 {sum(r['len_10yr'] for r in rows) / n:.0f}자")
    print(f"- 근거 희박 판정 명식: {[r['chart'] for r in rows if r['insufficient']]}, 격국·억부 충돌 표시: {[r['chart'] for r in rows if r['conflict_flagged']]}")
    print(f"- 구조가 하나도 없는 명식 수: {sum(1 for r in rows if r['structures'] == '없음')}, 해석 5단 항목 평균 {sum(r['readings'] for r in rows) / n:.1f}개")


if __name__ == "__main__":
    main()
