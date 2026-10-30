"""v7.1 오프라인 Narrator 실험(합성 명식 20개, API 호출 없음). A=결정론 템플릿, B=Mock 제공자(실제 LLM 아님), 적대 제공자로 검증기 차단율 측정.
실제 LLM(B) 대 전문가 개선본(C) 비교는 API 승인과 사람 평가자가 필요해 차단 상태다. 실행: python -m tools.eval_narrator_offline"""
import sys

from app.consult import narrator as N
from app.consult.contracts import build_bundle
from tools.eval_synthesis import DOMS, ans, charts

sys.stdout.reconfigure(encoding="utf-8")
ATTACKS = {
    "환각 용어": lambda js: [{"text": "도화살이 들어옵니다.", "claim_ids": []}],
    "환각 연도": lambda js: [{"text": "2041년에 변화가 있습니다.", "claim_ids": []}],
    "가짜 claim": lambda js: [{"text": "근거가 있습니다.", "claim_ids": ["L9-999"]}],
    "단정": lambda js: [{"text": "반드시 승진합니다.", "claim_ids": []}],
    "고전 위장": lambda js: [{"text": "적천수에 따르면 귀격입니다.", "claim_ids": []}],
    "반대 근거 삭제": lambda js: [{"text": j["text"], "claim_ids": j["claim_ids"]} for j in js if j["section"] in ("headline", "favorable")],
}


class Atk:
    name, model = "attack", "a"

    def __init__(self, fn, keep):
        self.fn, self.keep = fn, keep

    def generate(self, p):
        import json
        js = json.loads(p["user"].split("<judgments>")[1].split("</judgments>")[0])
        base = [{"text": j["text"], "claim_ids": j["claim_ids"]} for j in js]
        return N.NarratorResult((base if self.keep else []) + self.fn(js) if self.keep else self.fn(js), N.Usage("attack", "a", p["version"], 1, 1))


def main():
    cs = charts()
    ok = fb = 0
    tok_in = tok_out = 0
    blocked = {k: 0 for k in ATTACKS}
    for name, p in cs:
        pre, a = ans(p, (2030,), DOMS)
        b = build_bundle(a, pre)
        r = N.narrate(b, N.MockNarrator(), "2030년 재물과 승진")
        ok += r.source == "llm"
        fb += r.source != "llm"
        tok_in += r.usage.input_tokens if r.usage else 0
        tok_out += r.usage.output_tokens if r.usage else 0
        for k, fn in ATTACKS.items():
            blocked[k] += N.narrate(b, Atk(fn, True if k != "반대 근거 삭제" else False), retries=0).source == "deterministic_fallback"
    n = len(cs)
    print(f"# v7.1 오프라인 Narrator 실험 (합성 명식 {n}개, 외부 호출 0)\n")
    print(f"- Mock 제공자 검증 통과 {ok}/{n}, fallback {fb}/{n} (Mock 은 실제 LLM 이 아니라 재배열기이므로 품질 비교에 쓰지 않음)")
    print(f"- 토큰 추정: 입력 평균 {tok_in / n:.0f}, 출력 평균 {tok_out / n:.0f} (실제 비용은 제공자 응답으로 기록, 현재 $0)")
    for k, v in blocked.items():
        print(f"- 적대 응답 '{k}' 차단 {v}/{n}")


if __name__ == "__main__":
    main()
