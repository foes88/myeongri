"""v7.4 오프라인 비교(합성 명식 20개, 외부 호출 0): A=기존 결정론 서술(narrative), B=종합 템플릿(synthesis.text 전체), C=내부 Narrator(검증 통과본).
자동 지표만 계산한다. 이해도·설득력 같은 주관 평가는 블라인드 평가 도구(tools.blind_eval)로 사람이 한다. 실행: python -m tools.eval_narrator_compare"""
import re
import statistics
import sys

from app.consult import narrator as N
from app.consult.contracts import build_bundle
from app.consult.internal_narrator import InternalNarrator
from tools.eval_synthesis import DOMS, FUTURE, JARGON, ans, charts

sys.stdout.reconfigure(encoding="utf-8")
Q = "2030년 재물과 직업·승진 흐름이 궁금합니다"


def sents(t):
    return [x.strip() for x in re.split(r"(?<=[.다])\s+|\n+", t) if len(x.strip()) > 8]


def metrics(text):
    ss = sents(text)
    opens = [s[:5] for s in ss]
    return {"chars": len(text), "n": len(ss), "dup": 1 - len(set(ss)) / max(1, len(ss)), "open_var": len(set(opens)) / max(1, len(opens)), "avg_len": statistics.mean(map(len, ss)) if ss else 0,
            "jargon": len(JARGON.findall(text)), "future": len(FUTURE.findall(text)), "counter_marks": len(re.findall(r"견해|어렵|조심|신중|다투기", text)), "limit_marks": len(re.findall(r"확정하지|예측하거나|사람마다|단정하지", text))}


def main():
    rows = {"A 결정론(기존)": [], "B 종합 템플릿": [], "C 내부 Narrator": []}
    ok = 0
    cov = []
    for name, p in charts():
        pre, a = ans(p, (2030,), DOMS)
        bundle = build_bundle(a, pre)
        r = N.narrate(bundle, InternalNarrator(), Q, retries=0)
        ok += r.source == "llm"
        S = a["synthesis"]
        b_text = "\n".join([x["text"] for k in ("headline", "favorable", "cautions", "uncertainty") for x in S[k]] + [d["text"] for d in S["domain_summaries"]])
        rows["A 결정론(기존)"].append(metrics(a["narrative"]))
        rows["B 종합 템플릿"].append(metrics(b_text))
        rows["C 내부 Narrator"].append(metrics(r.text))
        want = {c for j in bundle.key_judgments if j["section"] in ("headline", "cautions") for c in j["claim_ids"]}
        got = {c for s in r.sentences for c in s["claim_ids"]}
        cov.append(len(want & got) / max(1, len(want)))
    n = len(rows["A 결정론(기존)"])
    print(f"# v7.4 오프라인 비교 (합성 명식 {n}개, 외부 호출 0, 자동 지표)\n")
    print("| 방식 | 평균 글자 | 문장 수 | 중복 문장 비율 | 문장 시작 다양도 | 평균 문장 길이 | 용어 누수 | 단정 표현 | 반대 근거 표지 | 한계 표지 |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for k, v in rows.items():
        m = lambda f: statistics.mean(x[f] for x in v)
        print(f"| {k} | {m('chars'):.0f} | {m('n'):.0f} | {m('dup'):.3f} | {m('open_var'):.2f} | {m('avg_len'):.0f} | {sum(x['jargon'] for x in v)} | {sum(x['future'] for x in v)} | {m('counter_marks'):.1f} | {m('limit_marks'):.1f} |")
    print(f"\n- 내부 Narrator Claim Validator 통과 {ok}/{n}, 핵심(헤드라인·반대 근거) claim 보존율 평균 {statistics.mean(cov):.2f}")
    print("- 이 비교는 구조적 지표입니다. '더 잘 읽히는가·설득력이 있는가'는 블라인드 평가(사람)로만 판정할 수 있습니다.")


if __name__ == "__main__":
    main()
