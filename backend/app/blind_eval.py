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
# v9.6: 상담 품질 평가 8개 항목(명리학 전문지식 없이도 평가 가능한 표현). 파일럿(v8.3) 5개 항목과 별도 세트로 두고, 패킷이 어느 세트를 쓰는지 기록한다.
CRITERIA_V96 = [("understand", "이해도: 문장을 읽고 내용을 이해할 수 있다"), ("specific", "명식별 구체성: 이 사주만의 내용이 담겨 있고 아무에게나 해당하는 말이 아니다"),
                ("domain_diff", "분야별 차이: 재물·직업 등 분야마다 서로 다른 근거와 내용으로 설명한다"), ("period_diff", "시기별 차이: 해마다·시기마다 무엇이 다른지 설명한다(차이가 없으면 없다고 말한다)"),
                ("evidence", "근거와의 일치: 결론과 그 이유가 서로 맞고 모순이 없다"), ("natural", "자연스러움: 사람이 쓴 듯 읽기 편하다(같은 말의 반복이나 어색함이 없다)"),
                ("fit", "질문 적합성: 내가 물은 것에 맞게 답한다"), ("cautious", "신중함: 미래를 단정하지 않고 모르는 부분은 모른다고 밝힌다")]
CRITERIA_EXPERT = [("logic", "전통 명리 논리의 일관성"), ("trace", "근거 추적 가능성"), ("consistent", "모순 없음")]
CRITERIA_KEYS = [k for k, _ in CRITERIA]
SLOTS = "XYZ"
MIN_EXPERTS = 3
MIN_LAY = 3
MIN_ITEMS_PER_RATER = 10
PILOT_MIN_RATERS = 5          # 파일럿 완료: 평가자 5명 이상(역할 무관), 각자 10항목 이상, 같은 항목에 2명 이상 중복 평가
ROLES = ("general", "lay", "expert", "user")      # user: 자기 사주로 직접 써 본 사용자(사용 경험 평가)


def criteria_keys(packet: dict | None) -> list[str]:
    return [c["key"] for c in (packet or {}).get("criteria", [])] or list(CRITERIA_KEYS)


def csv_columns(keys: list[str]) -> list[str]:
    return ["rater_id", "role", "item_id", "slot", *keys, "preferred", "reason"]


def build_packet(items: list[dict], seed: int = 20261030, criteria: list[tuple[str, str]] | None = None) -> tuple[dict, dict]:
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
    packet = {"schema": "blind-eval-packet/1", "criteria": [{"key": k, "label": l} for k, l in (criteria or CRITERIA)], "scale": "1(매우 나쁨)~5(매우 좋음)", "items": packet_items,
              "note": "합성 명식으로 만든 문장입니다. 실제 사람의 사주가 아닙니다. 문장의 출처(시스템·방식)는 공개하지 않습니다."}
    return packet, {"schema": "blind-eval-key/1", "seed": seed, "items": key}


def validate_rating(r: dict, packet: dict) -> list[str]:
    probs = []
    if r.get("role") not in ROLES:
        probs.append("role 은 general(비전문) / expert(명리 전문가)")
    if not r.get("rater_id"):
        probs.append("rater_id 없음")
    ids = {i["id"]: set(i["texts"]) for i in packet["items"]}
    keys = criteria_keys(packet)
    for x in r.get("ratings", []):
        if x.get("id") not in ids:
            probs.append(f"알 수 없는 항목 {x.get('id')}")
            continue
        for slot, sc in (x.get("scores") or {}).items():
            if slot not in ids[x["id"]]:
                probs.append(f"{x['id']}: 없는 슬롯 {slot}")
            for k in keys:
                v = sc.get(k)
                if v is not None and (not isinstance(v, int) or not 1 <= v <= 5):
                    probs.append(f"{x['id']}/{slot}/{k}: 1~5 정수여야 함")
        if x.get("preferred") is not None and x["preferred"] not in ids.get(x["id"], set()):
            probs.append(f"{x['id']}: 선호 슬롯 오류")
    return probs


def aggregate(packet: dict, key: dict, rating_files: list[dict]) -> dict:
    """평가 파일들을 변형별로 집계한다. 입력 검증에 실패한 파일은 제외하고 사유를 남긴다."""
    valid, rejected = [], []
    keys = criteria_keys(packet)
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
                    if k in keys and v is not None:
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
            "rater_item_counts": {k: len(v) for k, v in per_rater_items.items()}, "criteria_keys": keys}


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


_FIXED_COLS = {"rater_id", "role", "item_id", "slot", "preferred", "reason"}


def ratings_from_csv(text: str, keys: list[str] | None = None) -> list[dict]:
    """평가 폼 CSV → 평가자별 평가 딕셔너리(aggregate 입력). 같은 rater_id 의 여러 파일/행을 한 평가자로 합친다.
    keys 를 주지 않으면 CSV 머리글에서 항목 열(고정 열 이외)을 읽는다(파일럿 5항목·v9.6 8항목 모두 처리)."""
    import csv
    import io
    rd = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    keys = keys or [c for c in (rd.fieldnames or []) if c and c not in _FIXED_COLS] or list(CRITERIA_KEYS)
    by: dict[str, dict] = {}
    for row in rd:
        rid = (row.get("rater_id") or "").strip()
        r = by.setdefault(rid, {"rater_id": rid, "role": (row.get("role") or "").strip(), "ratings": {}})
        it = r["ratings"].setdefault(row["item_id"], {"id": row["item_id"], "scores": {}, "preferred": None, "reason": ""})
        sc = {}
        for k in keys:
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
        row.update({k: agg["means"].get(v, {}).get(k) for k in agg.get("criteria_keys", CRITERIA_KEYS)})
        out.append(row)
    return out


# ------------------------------------------------------------------ 선호 편향 분리(문장 길이·문체)
def _sentences(t: str) -> int:
    import re
    return max(1, len([x for x in re.split(r"[.!?。]\s|\n", t) if x.strip()]))


def _corr(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sx, sy = sum((x - mx) ** 2 for x in xs) ** 0.5, sum((y - my) ** 2 for y in ys) ** 0.5
    return None if sx == 0 or sy == 0 else sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def confounds(packet: dict, key: dict, ratings: list[dict]) -> dict:
    """버전 간 점수·선호 차이가 문장 길이 때문인지 구분한다. 항목 안(같은 질문·같은 명식)에서만 비교해 질문 난이도 차이를 없앤다.
    - length_by_variant: 변형별 평균 글자 수·문장 수·문장당 글자 수(문체)
    - length_score_corr: 항목 평균을 뺀 점수와 길이의 상관(항목 안). |r| 가 크면 길이가 점수에 영향
    - prefers_longest_share: 선호한 문장이 그 항목에서 가장 긴 문장인 비율(무작위 기대값 = 1/슬롯 수 평균)
    - length_adjusted_mean: 길이 영향을 선형으로 제거한 변형별 평균 점수(참고용 — 인과를 증명하지 않는다)"""
    keys = criteria_keys(packet)
    texts = {i["id"]: i["texts"] for i in packet["items"]}
    var_of = {pid: k["slots"] for pid, k in key["items"].items()}
    by_var = defaultdict(lambda: {"chars": [], "sent": []})
    for pid, tx in texts.items():
        for slot, t in tx.items():
            v = var_of[pid][slot]
            by_var[v]["chars"].append(len(t))
            by_var[v]["sent"].append(_sentences(t))
    length_by_variant = {v: {"mean_chars": round(statistics.mean(d["chars"]), 1), "mean_sentences": round(statistics.mean(d["sent"]), 1),
                             "chars_per_sentence": round(statistics.mean(d["chars"]) / statistics.mean(d["sent"]), 1)} for v, d in by_var.items()}
    pts = []     # (item, slot, variant, overall, length)
    longest_hits = chance = n_pref = 0
    for r in ratings:
        for x in r.get("ratings", []):
            tx = texts.get(x["id"])
            if not tx:
                continue
            for slot, sc in (x.get("scores") or {}).items():
                vals = [v for k, v in sc.items() if k in keys and isinstance(v, int)]
                if vals and slot in tx:
                    pts.append((x["id"], slot, var_of[x["id"]][slot], statistics.mean(vals), len(tx[slot])))
            if x.get("preferred") in tx:
                n_pref += 1
                longest_hits += len(tx[x["preferred"]]) == max(len(t) for t in tx.values())
                chance += 1 / len(tx)
    # 항목 안 중심화
    by_item = defaultdict(list)
    for p_ in pts:
        by_item[p_[0]].append(p_)
    cs, cl, rows = [], [], []
    for lst in by_item.values():
        ms, ml = statistics.mean(p_[3] for p_ in lst), statistics.mean(p_[4] for p_ in lst)
        for it, sl, v, sc, ln in lst:
            cs.append(sc - ms)
            cl.append(ln - ml)
            rows.append((v, sc - ms, ln - ml))
    r_len = _corr(cl, cs)
    slope = (sum(a * b for a, b in zip(cl, cs)) / sum(a * a for a in cl)) if cl and sum(a * a for a in cl) else 0.0
    adj = defaultdict(list)
    for v, ds, dl in rows:
        adj[v].append(ds - slope * dl)
    return {"length_by_variant": length_by_variant, "length_score_corr": None if r_len is None else round(r_len, 3), "n_scored": len(pts),
            "prefers_longest_share": round(longest_hits / n_pref, 3) if n_pref else None, "chance_prefers_longest": round(chance / n_pref, 3) if n_pref else None,
            "length_adjusted_mean": {v: round(statistics.mean(d), 3) for v, d in adj.items()},
            "length_bias_suspected": bool(r_len is not None and abs(r_len) >= 0.3 and len(pts) >= 20),
            "note": "문장이 길수록 점수가 높게 나오는 경향(길이 편향)을 분리해 보는 참고 지표다. 좋은 점수를 받은 문장 스타일을 규칙 검증 없이 다른 해석에 확대 적용하지 않는다."}
