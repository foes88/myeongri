"""블라인드 상담 평가(사람 평가) 도구의 핵심 로직. 평가자에게는 출처 라벨 없이 X/Y(/Z) 문장만 보여 주고, 정답 키는 별도 파일에 둔다.

- 평가 대상 변형: legacy(v6.8 결정론 서술), synthesis(v7 종합), 선택적으로 llm(제공자 출력, 키·승인 없으면 생략).
- 사람 평가가 끝났다고 기록하려면 gate() 조건(전문가 평가자 수, 일반 평가자 수, 항목 커버리지)을 충족해야 한다. 자동 지표는 이를 대신하지 못한다.
- 합성 명식만 사용한다(실제 출생 정보 없음).
"""
from __future__ import annotations

import hashlib
import json
import random
import statistics
from collections import defaultdict

CRITERIA = [
    ("logic", "전통 명리 논리의 일관성"), ("trace", "근거 추적 가능성"), ("specific", "해석의 구체성"), ("easy", "이해하기 쉬움"),
    ("fit", "질문에 대한 답변 적합성"), ("consistent", "모순 없음"), ("satisfy", "상담 만족도"),
]
CRITERIA_KEYS = [k for k, _ in CRITERIA]
SLOTS = "XYZ"
MIN_EXPERTS = 3
MIN_LAY = 3
MIN_ITEMS_PER_RATER = 10


def build_packet(items: list[dict], seed: int = 20261030) -> tuple[dict, dict]:
    """items: [{item_id, question, years, domains, variants:{legacy:str, synthesis:str, llm?:str}}] → (packet, key).
    packet 에는 변형 이름이 없다. 변형 순서는 항목마다 시드 난수로 섞고 key 에만 기록한다."""
    rnd = random.Random(seed)
    packet_items, key = [], {}
    for it in items:
        names = [n for n in ("legacy", "synthesis", "llm") if it["variants"].get(n)]
        rnd.shuffle(names)
        slots = {SLOTS[i]: n for i, n in enumerate(names)}
        pid = hashlib.sha256(f"{seed}:{it['item_id']}".encode()).hexdigest()[:10]
        packet_items.append({"id": pid, "question": it["question"], "years": it["years"], "domains": it["domains"], "texts": {s: it["variants"][n] for s, n in slots.items()}})
        key[pid] = {"item_id": it["item_id"], "slots": slots}
    rnd.shuffle(packet_items)
    packet = {"schema": "blind-eval-packet/1", "criteria": [{"key": k, "label": l} for k, l in CRITERIA], "scale": "1(매우 나쁨)~5(매우 좋음)", "items": packet_items,
              "note": "합성 명식으로 만든 문장입니다. 실제 사람의 사주가 아닙니다. 문장의 출처(시스템·방식)는 공개하지 않습니다."}
    return packet, {"schema": "blind-eval-key/1", "seed": seed, "items": key}


def validate_rating(r: dict, packet: dict) -> list[str]:
    probs = []
    if r.get("role") not in ("expert", "lay"):
        probs.append("role 은 expert 또는 lay")
    if not r.get("rater_id"):
        probs.append("rater_id 없음")
    ids = {i["id"]: set(i["texts"]) for i in packet["items"]}
    for x in r.get("ratings", []):
        if x.get("id") not in ids:
            probs.append(f"알 수 없는 항목 {x.get('id')}")
            continue
        for slot, sc in (x.get("scores") or {}).items():
            if slot not in ids[x["id"]]:
                probs.append(f"{x['id']}: 없는 슬롯 {slot}")
            for k in CRITERIA_KEYS:
                v = sc.get(k)
                if v is not None and (not isinstance(v, int) or not 1 <= v <= 5):
                    probs.append(f"{x['id']}/{slot}/{k}: 1~5 정수여야 함")
        if x.get("preferred") is not None and x["preferred"] not in ids.get(x["id"], set()):
            probs.append(f"{x['id']}: 선호 슬롯 오류")
    return probs


def aggregate(packet: dict, key: dict, rating_files: list[dict]) -> dict:
    """평가 파일들을 변형별로 집계한다. 입력 검증에 실패한 파일은 제외하고 사유를 남긴다."""
    valid, rejected = [], []
    for r in rating_files:
        p = validate_rating(r, packet)
        (rejected.append({"rater_id": r.get("rater_id"), "problems": p}) if p else valid.append(r))
    score = defaultdict(lambda: defaultdict(list))   # variant → criterion → [values]
    pref = defaultdict(int)
    pref_by_item = defaultdict(lambda: defaultdict(int))
    n_pref = 0
    per_role = defaultdict(set)
    per_rater_items = defaultdict(set)
    for r in valid:
        per_role[r["role"]].add(r["rater_id"])
        for x in r["ratings"]:
            slots = key["items"][x["id"]]["slots"]
            for slot, sc in (x.get("scores") or {}).items():
                for k, v in sc.items():
                    if k in CRITERIA_KEYS and v is not None:
                        score[slots[slot]][k].append(v)
                        per_rater_items[r["rater_id"]].add(x["id"])
            if x.get("preferred"):
                pref[slots[x["preferred"]]] += 1
                pref_by_item[x["id"]][slots[x["preferred"]]] += 1
                n_pref += 1
    means = {v: {k: round(statistics.mean(vals), 2) for k, vals in cs.items()} for v, cs in score.items()}
    overall = {v: round(statistics.mean([x for vals in cs.values() for x in vals]), 2) for v, cs in score.items()}
    # 항목별 평가자 간 일치: 같은 항목에 2명 이상이 선호를 낸 경우 최다 선택 비율의 평균
    agree = [max(c.values()) / sum(c.values()) for c in pref_by_item.values() if sum(c.values()) >= 2]
    return {"raters": {r: len(s) for r, s in per_role.items()}, "rejected": rejected, "means": means, "overall": overall,
            "preference": dict(pref), "n_preferences": n_pref, "agreement": round(statistics.mean(agree), 2) if agree else None,
            "rater_item_counts": {k: len(v) for k, v in per_rater_items.items()}}


def gate(agg: dict) -> dict:
    """사람 평가 완료 게이트. 부족하면 completed=False 와 사유를 돌려준다(완료로 기록하지 않는다)."""
    reasons = []
    raters = agg["raters"]
    if raters.get("expert", 0) < MIN_EXPERTS:
        reasons.append(f"전문가 평가자 {raters.get('expert', 0)}/{MIN_EXPERTS}")
    if raters.get("lay", 0) < MIN_LAY:
        reasons.append(f"일반 평가자 {raters.get('lay', 0)}/{MIN_LAY}")
    short = [r for r, n in agg["rater_item_counts"].items() if n < MIN_ITEMS_PER_RATER]
    if short:
        reasons.append(f"평가 항목 수 부족 평가자 {len(short)}명(최소 {MIN_ITEMS_PER_RATER}항목)")
    if agg["agreement"] is None:
        reasons.append("평가자 간 일치도를 계산할 중복 평가 없음")
    return {"completed": not reasons, "reasons": reasons}
