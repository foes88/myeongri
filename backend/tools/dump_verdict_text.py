"""현재 코드 버전의 사용자용 결론 문장을 평가용 텍스트로 덤프한다(블라인드 패킷 재료). 이전 버전 코드(예: git worktree)에서도 같은 명령으로 실행해 버전별 문장을 만든다.
실행: python -m tools.dump_verdict_text OUT.json [--n 20]"""
import json
import sys

from tools.blind_eval import QUESTIONS, charts
from app.consult import agent
from app.evaluation import dataset as DS

sys.stdout.reconfigure(encoding="utf-8")


def verdict_text(v: dict) -> str:
    out = []

    def block(b):
        out.append(f"[{b['name']}] {b['headline']}")
        out.append(" ".join(b["story"]))
        out.append("현실에서 생각해 볼 점: " + " ".join(b["think"]))
    if v["mode"] == "multi":
        p = v["period"]
        out.append(f"[{p['span']} 핵심 흐름] " + " ".join(p["summary"]))
        out += [f"{r['year']}년{' ★' if r['standout'] else ''}: {r['line']} — {r['change']}" for r in p["years"]]
        y = str((p["standout"] or [v["years"][0]])[0])
        out.append(f"({y}년 자세히)")
        for b in v["detail"][y]["blocks"]:
            block(b)
    else:
        for b in v["blocks"]:
            block(b)
    out.append("해석의 한계: " + " ".join(v["limits"]))
    return "\n".join(out)


def main():
    path = sys.argv[1]
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 20
    res = {}
    for i, (name, p) in enumerate(charts(n)):
        doms, years, q = QUESTIONS[i % len(QUESTIONS)]
        pre = DS.pre_of(DS.Spec(p, domains=doms, years=years, cycles_first_year=2000))
        a = agent.answer(pre, q, domains_=list(doms), years=list(years), depth="detailed")
        res[name] = verdict_text(a["verdict"])
    json.dump(res, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote", path, len(res))


if __name__ == "__main__":
    main()
