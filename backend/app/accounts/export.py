"""저장 리포트 내보내기(마크다운). 종합 해석·5단 해석·한계·검증 상태를 포함하고 출생 원문은 포함하지 않는다(저장하지 않았음)."""
from __future__ import annotations

import datetime


def _sents(items):
    return "\n".join(f"- {x['text']}" for x in items) or "- (해당 없음)"


def _block(title: str, ans: dict) -> str:
    S = ans.get("synthesis")
    if not S:
        return f"## {title}\n\n" + ans.get("narrative", "")
    parts = [f"## {title}", "", "### 핵심 해석", "\n".join(x["text"] for x in S["headline"]), "", "### 유리하게 읽히는 조건", _sents(S["favorable"]), "", "### 주의하거나 상반되는 조건", _sents(S["cautions"])]
    if S["domain_summaries"]:
        parts += ["", "### 관심 분야별 핵심 요약"] + [f"- **{d['name']}**: {d['text']}" for d in S["domain_summaries"]]
    f = S["period_flow"]
    if f.get("mode") == "multi":
        parts += ["", "### 연도별 한 줄 요약"] + [f"- {y['year']}년{' ★' if y['standout'] else ''}: {y['one_line']}" for y in f["years"]]
    for r in S["readings"]:
        parts += ["", f"### {r['name']} — {r['structure']}", f"- 의미: {r['meaning']}", f"- 판단 근거: {r['why']}", f"- 현실 연결(살펴볼 상황의 예): {r['reality']}", f"- 반대 근거: {' / '.join(r['counter'])}"]
        if r.get("period"):
            parts.append(f"- 선택한 기간: {r['period']}")
        parts.append(f"- 해석 범위: {r['scope']}")
    parts += ["", "### 읽을 때 유의할 점", _sents(S["uncertainty"])]
    return "\n".join(parts)


def to_markdown(report: dict, turns: list[dict]) -> str:
    pre, ans = report["body"]["pre"], report["body"]["answer"]
    v = pre["verification"]
    ts = datetime.datetime.fromtimestamp(report["created_at"]).strftime("%Y-%m-%d %H:%M")
    head = [f"# {report['title']}", "", f"- 작성: {ts} · 규칙 버전 {pre['ruleset_version']} · 기록 해시 {pre['content_hash'][:12]}…",
            f"- 명식: {' '.join(pre['natal_structure']['pillars'].values())}", f"- 검증 상태: {v['status']} — " + (" / ".join(v.get("unverified_notice", [])[:2]) or "표시된 범위에서 검증됨"),
            "- 이 문서는 전통 명리학의 해석이며 미래를 예측하거나 결과를 보장하지 않습니다.", ""]
    body = [_block("분석 결과", ans)]
    for t in turns:
        b = t["body"]
        if t["kind"] == "answer":
            body += ["", _block(f"후속 질문 {t['n']}: {b['question']}", b["answer"])]
        else:
            body += ["", f"## 현실 사건 기록 {t['n']}", f"- {b['event']} → {b['result'].get('outcome')}: {b['result'].get('explanation')}"]
    return "\n".join(head + body) + "\n"
