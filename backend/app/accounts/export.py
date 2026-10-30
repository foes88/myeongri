"""저장 리포트 내보내기(마크다운). 사용자용 결론형 데이터(verdict)만 사용한다 — 규칙 번호·근거 번호·구조 이름·원시 근거는 포함하지 않고, 출생 원문도 포함하지 않는다(저장하지 않았음)."""
from __future__ import annotations

import datetime

from ..consult import verdict as V


def _block_md(b: dict, level: int = 3) -> list[str]:
    h = "#" * level
    out = [f"{h} {b['name']}", "", f"**{b['headline']}**", "", " ".join(b["story"]), ""]
    if b.get("think"):
        out += ["**현실에서 생각해 볼 점**", ""] + [f"- {t}" for t in b["think"]] + [""]
    return out


def verdict_md(v: dict, title: str = "분석 결과") -> str:
    out = [f"## {title}", ""]
    if v["mode"] == "multi":
        p = v["period"]
        out += [f"### {p['span']} 핵심 흐름", "", " ".join(p["summary"]), "", "#### 연도별 한 줄"]
        for r in p["years"]:
            out.append(f"- {r['year']}년{' ★' if r['standout'] else ''}: {r['line']} — {r['change']}" + (f" (주의: {r['caution']})" if r["caution"] else ""))
        out.append("")
        for y in v["years"]:
            out.append(f"### {y}년 자세한 풀이")
            out.append("")
            for b in v["detail"][str(y)]["blocks"]:
                out += _block_md(b, 4)
    else:
        for b in v["blocks"]:
            out += _block_md(b)
    out += ["### 해석의 한계", ""] + [f"- {x}" for x in v["limits"]]
    return "\n".join(out)


def to_markdown(report: dict, turns: list[dict]) -> str:
    pre, ans = report["body"]["pre"], report["body"]["answer"]
    ts = datetime.datetime.fromtimestamp(report["created_at"]).strftime("%Y-%m-%d %H:%M")
    head = [f"# {report['title']}", "", f"- 작성: {ts}", f"- 사주: {' '.join(pre['natal_structure']['pillars'].values())}",
            "- 이 문서는 전통 명리학의 해석이며 미래를 예측하거나 결과를 보장하지 않습니다.", ""]
    body = [verdict_md(ans["verdict"])]
    for t in turns:
        b = t["body"]
        if t["kind"] == "answer":
            qa = b["answer"].get("qa") or {}
            body += ["", f"## 후속 질문 {t['n']}: {b['question']}", "", qa.get("text", "")] + [f"- {p}" for p in qa.get("points", [])]
        else:
            body += ["", f"## 현실 사건 기록 {t['n']}", f"- {b['event'].get('type')} {b['event'].get('year')}년: " + V.public_reality(b["result"])["explanation"]]
    return "\n".join(head + body) + "\n"
