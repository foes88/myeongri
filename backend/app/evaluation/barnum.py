"""바넘 효과 검사: 서로 다른 명식의 답변에 '어느 명식에나 성립할 일반론'이 얼마나 섞였는지 본다.

문자열 중복률만 쓰지 않는다. 문장을 마스킹(간지·연도·claim_id·따옴표 라벨·숫자 → 자리표시자)해 '틀'이 같은지 보고,
틀이 같아도 언급된 사실이 명식마다 다르면 '사실을 담은 틀'(fact-bearing template)로 구분한다.
사실이 하나도 없는 문장이 여러 명식에서 그대로 반복되면 '일반론 후보'다. 문장이 다르다는 것만으로 좋은 분석이라고 보지 않는다(차이는 의미 서명으로도 확인).
"""
from __future__ import annotations

import math
import re
from collections import defaultdict

from . import metrics as M

MASKS = [(re.compile(r"[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]"), "<GZ>"), (re.compile(r"[甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥]"), "<G>"),
         (re.compile(r"\b[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{3}\b"), "<ID>"), (re.compile(r"(?<!\d)(19|20)\d{2}(?!\d)"), "<Y>"),
         (re.compile(r"\d{4}-\d{2}-\d{2}"), "<D>"), (re.compile(r"'[^']{1,12}'"), "<Q>"), (re.compile(r"\d+"), "<N>")]
PLACEHOLDER = re.compile(r"<[A-Z]+>")
SCAFFOLD = re.compile(r"^먼저 원국의 특징입니다|확정하지 않습니다|단정하지 않습니다|단정하지 않|연결로만 이해|다릅니다\.?$|사전 분석 기록을 바꾸지|존재만 확인|작용 정도")


RULE_LEVEL = re.compile(r"에서 모두 참고됩니다")  # 같은 구조가 여러 분야에 쓰인다는 연결 문장(구조를 가진 명식이면 동일)


def _evidence_texts(pre: dict) -> list[str]:
    out = []
    for n in pre["natal_structure"]["graph"]["nodes"]:
        out += [e.split(": ", 1)[-1] for e in n["supporting_evidence"] + n["counter_evidence"]]
    return [e for e in out if len(e) >= 8]


def mask(s: str) -> str:
    for pat, rep in MASKS:
        s = pat.sub(rep, s)
    return s


def analyze(answers: list[dict], pres: list[dict], threshold: float = 0.6) -> dict:
    n = len(answers)
    per = []
    by_mask: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for i, a in enumerate(answers):
        for s in M.content_sentences(a):
            by_mask[mask(s)].append((i, s))
    k = max(2, math.ceil(threshold * n))
    shared_masks = {m for m, v in by_mask.items() if len({i for i, _ in v}) >= k}
    generic_examples, fact_templates = [], 0
    generic_total = content_total = 0
    kinds = {"scaffold_or_hedge": 0, "rule_level_statement": 0, "other_generic": 0}
    ev_texts = [_evidence_texts(p) for p in pres]
    for i, a in enumerate(answers):
        cs = M.content_sentences(a)
        content_total += len(cs)
        g = 0
        for s in cs:
            m = mask(s)
            if m in shared_masks:
                variants = {raw for j, raw in by_mask[m]}
                if PLACEHOLDER.search(m) and len(variants) > 1:
                    fact_templates += 1            # 틀은 같지만 사실이 명식마다 다름
                elif len(variants) == 1 or not PLACEHOLDER.search(m):
                    g += 1                         # 사실이 없고 여러 명식에 같은 문장 = 일반론 후보
                    if SCAFFOLD.search(s):
                        kinds["scaffold_or_hedge"] += 1    # 전개 문구·단서 문구(분석 주장이 아님)
                    elif any(t in s for t in ev_texts[i]) or RULE_LEVEL.search(s):
                        kinds["rule_level_statement"] += 1  # 규칙 수준의 근거 문장: 같은 구조를 가진 명식이면 같은 문장(명식 고유 사실은 아님)
                    else:
                        kinds["other_generic"] += 1         # 진짜 바넘 위험 후보
                        if len(generic_examples) < 6 and s not in generic_examples:
                            generic_examples.append(s)
        generic_total += g
        per.append({"content_sentences": len(cs), "generic_candidates": g})
    # 의미 서명 거리 vs 문장 거리: 문장은 다른데 판단이 같으면 '표현만 다름'
    sigs = [M.signature(a, p) for a, p in zip(answers, pres)]
    texts = [" ".join(p["text"] for p in a["paragraphs"]) for a in answers]
    pair_sig, pair_txt, cosmetic = [], [], 0
    for i in range(n):
        for j in range(i + 1, n):
            ds, dt = M.jacc_dist(sigs[i], sigs[j]), M.token_dist(texts[i], texts[j])
            pair_sig.append(ds)
            pair_txt.append(dt)
            if dt > 0.05 and ds == 0.0:
                cosmetic += 1
    return {"charts": n, "content_sentences": content_total, "generic_candidate_sentences": generic_total,
            "generic_ratio": round(generic_total / content_total, 3) if content_total else 0.0,
            "fact_bearing_template_sentences": fact_templates, "generic_by_type": kinds, "other_generic_ratio": round(kinds["other_generic"] / content_total, 3) if content_total else 0.0,
            "other_generic_examples": generic_examples,
            "mean_signature_distance": round(sum(pair_sig) / len(pair_sig), 3) if pair_sig else 0.0,
            "mean_text_distance": round(sum(pair_txt) / len(pair_txt), 3) if pair_txt else 0.0,
            "cosmetic_difference_pairs": cosmetic, "per_chart": per,
            "note": "일반론 후보=사실 자리표시자가 없고 여러 명식에서 같은 문장. 문장이 다른 것 자체는 품질의 증거가 아니다(signature 거리와 함께 본다)."}
