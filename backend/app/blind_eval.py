"""블라인드 상담 평가(사람 평가) 도구의 핵심 로직. 평가자에게는 출처 라벨 없이 X/Y(/Z) 문장만 보여 주고, 정답 키는 별도 파일에 둔다.

- 평가 대상 변형: 항목마다 2~3개의 서로 다른 버전 문장(예: v70 종합, v81 결론형, v82 개선). 이름은 key 에만 있고 평가자에게는 보이지 않는다.
- 사람 평가가 끝났다고 기록하려면 gate() 조건(전문가 평가자 수, 일반 평가자 수, 항목 커버리지)을 충족해야 한다. 자동 지표는 이를 대신하지 못한다.
- 합성 명식만 사용한다(실제 출생 정보 없음).
"""
from __future__ import annotations

import hashlib
import json
import random
import statistics
from collections import defaultdict

# 파일럿(v8.3): 명리학 전문지식이 없어도 평가할 수 있는 5개 항목. (전문가 평가용 항목은 CRITERIA_EXPERT 로 별도 유지)
CRITERIA = [("understand", "이해도: 읽고 내용을 이해할 수 있다"), ("specific", "구체성: 내 사주·그 시기에 맞는 구체적인 설명이다"), ("useful", "유용성: 내 질문에 답이 되고 생각해 볼 거리를 준다"),
            ("natural", "자연스러움: 사람이 쓴 듯 읽기 편하다(같은 말의 반복이나 어색함이 없다)"), ("trust", "신뢰도: 근거 없이 단정하지 않고 믿을 만하다")]
CRITERIA_EXPERT = [("logic", "전통 명리 논리의 일관성"), ("trace", "근거 추적 가능성"), ("consistent", "모순 없음")]
CRITERIA_KEYS = [k for k, _ in CRITERIA]
SLOTS = "XYZ"
MIN_EXPERTS = 3
MIN_LAY = 3
MIN_ITEMS_PER_RATER = 10
PILOT_MIN_RATERS = 5          # 파일럿 완료: 평가자 5명 이상(역할 무관), 각자 10항목 이상, 같은 항목에 2명 이상 중복 평가
ROLES = ("general", "lay", "expert")


def build_packet(items: list[dict], seed: int = 20261030) -> tuple[dict, dict]:
    """items: [{item_id, question, years, domains, variants:{legacy:str, synthesis:str, llm?:str}}] → (packet, key).
    packet 에는 변형 이름이 없다. 변형 순서는 항목마다 시드 난수로 섞고 key 에만 기록한다."""
    rnd = random.Random(seed)
    packet_items, key = [], {}
    for it in items:
        names = [n for n in it["variants"] if it["variants"].get(n)]  # 변형 이름은 자유(예: v70, v81, v82). 슬롯은 X/Y/Z 로 가려진다
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
    if r.get("role") not in ROLES:
        probs.append("role 은 general(비전문) / expert(명리 전문가)")
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
    reasons = defaultdict(list)
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
                if (x.get("reason") or "").strip():
                    reasons[slots[x["preferred"]]].append(x["reason"].strip())
    means = {v: {k: round(statistics.mean(vals), 2) for k, vals in cs.items()} for v, cs in score.items()}
    overall = {v: round(statistics.mean([x for vals in cs.values() for x in vals]), 2) for v, cs in score.items()}
    # 항목별 평가자 간 일치: 같은 항목에 2명 이상이 선호를 낸 경우 최다 선택 비율의 평균
    agree = [max(c.values()) / sum(c.values()) for c in pref_by_item.values() if sum(c.values()) >= 2]
    return {"raters": {r: len(s) for r, s in per_role.items()}, "rejected": rejected, "means": means, "overall": overall,
            "preference": dict(pref), "n_preferences": n_pref, "reasons": {k: v for k, v in reasons.items()}, "n_valid_raters": len(valid), "agreement": round(statistics.mean(agree), 2) if agree else None,
            "rater_item_counts": {k: len(v) for k, v in per_rater_items.items()}}


def gate(agg: dict) -> dict:
    """사람 평가 완료 게이트. 부족하면 completed=False 와 사유를 돌려준다(완료로 기록하지 않는다)."""
    reasons = []
    raters = agg["raters"]
    if raters.get("expert", 0) < MIN_EXPERTS:
        reasons.append(f"전문가 평가자 {raters.get('expert', 0)}/{MIN_EXPERTS}")
    lay = raters.get("lay", 0) + raters.get("general", 0)  # general(일반)·lay 는 같은 비전문 평가자
    if lay < MIN_LAY:
        reasons.append(f"일반 평가자 {lay}/{MIN_LAY}")
    short = [r for r, n in agg["rater_item_counts"].items() if n < MIN_ITEMS_PER_RATER]
    if short:
        reasons.append(f"평가 항목 수 부족 평가자 {len(short)}명(최소 {MIN_ITEMS_PER_RATER}항목)")
    if agg["agreement"] is None:
        reasons.append("평가자 간 일치도를 계산할 중복 평가 없음")
    return {"completed": not reasons, "reasons": reasons}


def pilot_gate(agg: dict) -> dict:
    """파일럿 상태. 응답이 없으면 '미평가'를 유지하고, 파일럿이 끝나도 '상담 품질 검증 완료'로 표시하지 않는다(그것은 gate() 의 전문가·일반 기준)."""
    n = agg.get("n_valid_raters", sum(agg["raters"].values()))
    if n == 0:
        return {"status": "미평가", "pilot_complete": False, "validation_complete": False, "reasons": ["유효한 평가 응답 0건"]}
    reasons = []
    if n < PILOT_MIN_RATERS:
        reasons.append(f"평가자 {n}/{PILOT_MIN_RATERS}명")
    short = [r for r, c in agg["rater_item_counts"].items() if c < MIN_ITEMS_PER_RATER]
    if short:
        reasons.append(f"{MIN_ITEMS_PER_RATER}항목 미만 평가자 {len(short)}명")
    if agg["agreement"] is None:
        reasons.append("같은 항목을 2명 이상이 평가한 선호 응답 없음")
    done = not reasons
    return {"status": "파일럿 완료(예비 결과)" if done else "진행 중", "pilot_complete": done, "validation_complete": bool(gate(agg)["completed"]), "reasons": reasons,
            "note": "파일럿은 표본이 작아 통계적 결론이 아니다. 상담 품질 검증 완료는 전문가 3명·일반 3명 이상 기준(gate)을 따로 충족해야 한다."}


# ------------------------------------------------------------------ CSV 입출력(평가 폼이 내려받는 형식)
CSV_COLUMNS = ["rater_id", "role", "item_id", "slot", "understand", "specific", "useful", "natural", "trust", "preferred", "reason"]


def ratings_from_csv(text: str) -> list[dict]:
    """평가 폼 CSV → 평가자별 평가 딕셔너리(aggregate 입력). 같은 rater_id 의 여러 파일/행을 한 평가자로 합친다."""
    import csv
    import io
    by: dict[str, dict] = {}
    for row in csv.DictReader(io.StringIO(text.lstrip("\ufeff"))):
        rid = (row.get("rater_id") or "").strip()
        r = by.setdefault(rid, {"rater_id": rid, "role": (row.get("role") or "").strip(), "ratings": {}})
        it = r["ratings"].setdefault(row["item_id"], {"id": row["item_id"], "scores": {}, "preferred": None, "reason": ""})
        sc = {}
        for k in CRITERIA_KEYS:
            v = (row.get(k) or "").strip()
            if v:
                try:
                    sc[k] = int(v)
                except ValueError:
                    sc[k] = v  # validate_rating 이 거른다
        if sc:
            it["scores"][row["slot"].strip()] = sc
        if str(row.get("preferred", "")).strip() in ("1", "Y", "y", "true", "True"):
            it["preferred"] = row["slot"].strip()
            it["reason"] = (row.get("reason") or "").strip()
    return [{**r, "ratings": list(r["ratings"].values())} for r in by.values()]


def summary_rows(agg: dict) -> list[dict]:
    """버전별 항목 평균 + 선호 수를 표로(CSV 저장용)."""
    out = []
    for v in sorted(set(agg["means"]) | set(agg["preference"])):
        row = {"variant": v, "overall_mean": agg["overall"].get(v), "preferred_count": agg["preference"].get(v, 0)}
        row.update({k: agg["means"].get(v, {}).get(k) for k in CRITERIA_KEYS})
        out.append(row)
    return out
