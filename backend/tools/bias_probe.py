"""v9.2 해석 편향 측정(합성 명식, 사건 없음). 변경 전후 비교용. 사용: python -m tools.bias_probe [--n 30] [--out 파일.json]
분야별 톤 분포, 팰리스 분야(가족·연애·이직·부동산) 톤 결정 조건 분해, 주장 비율을 낸다. 예측 정확도와 무관하다."""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter

from app import cases as C
from app.consult import verdict as V


def charts(n: int, seed: int = 2024):
    rng = random.Random(seed)
    for i in range(n):
        y, m, d = rng.randint(1975, 2003), rng.randint(1, 12), rng.randint(1, 28)
        yield C.CaseInput(f"SYN-{i}", "solar", False, f"{y:04d}-{m:02d}-{d:02d}", f"{rng.randint(0, 23):02d}:{rng.choice([0, 15, 30, 45]):02d}", "서울특별시", rng.choice(["male", "female"]), "A")


def run(n: int = 30) -> dict:
    trace: list[tuple[str, dict]] = []
    orig = V._tone_palace

    def spy(pre, dom, yr, nm=None):
        t = orig(pre, dom, yr, nm)
        trace.append((dom, t))
        return t
    V._tone_palace = spy
    try:
        preds = []
        for ci in charts(n):
            r = C.generate_predictions(ci, 2026)
            preds.append(dict(r, birth_year=int(ci.birth_date[:4])))
    finally:
        V._tone_palace = orig
    tones = {dom: dict(Counter(r["domains"][dom]["tone"] for p in preds for r in p["years"] if dom in r["domains"])) for dom in C.PRED_DOMAINS}
    palace = {}
    for dom in ("family", "love_marriage", "job_change", "real_estate"):
        ts = [t for d, t in trace if d == dom]
        if not ts:
            continue
        palace[dom] = {"n": len(ts), "neg_gt_pos_plus1": sum(1 for t in ts if t.get("neg", 0) > t.get("pos", 0) + 1), "bad_rel_ge2": sum(1 for t in ts if t.get("palace_bad", 0) >= 2),
                       "bad_rel_ge1": sum(1 for t in ts if t.get("palace_bad", 0) >= 1), "good_rel_ge1": sum(1 for t in ts if t.get("palace_good", 0) >= 1),
                       "mean_pos": round(sum(t.get("pos", 0) for t in ts) / len(ts), 2), "mean_neg": round(sum(t.get("neg", 0) for t in ts) / len(ts), 2),
                       "mean_bad_rel": round(sum(t.get("palace_bad", 0) for t in ts) / len(ts), 2), "mean_good_rel": round(sum(t.get("palace_good", 0) for t in ts) / len(ts), 2)}
    return {"charts": n, "judge_version": getattr(V, "JUDGE_VERSION", "legacy"), "tones": tones, "tone_share": {d: {k: round(v / sum(c.values()), 3) for k, v in c.items()} for d, c in tones.items()},
            "claim_rate": C.tone_distribution(preds)["claim_rate"], "tone_overall": C.tone_distribution(preds), "distinct": C.distinctiveness(preds), "palace": palace}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--out")
    a = ap.parse_args()
    res = run(a.n)
    txt = json.dumps(res, ensure_ascii=False, indent=1)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(txt)
    print(txt)
