"""판정 기준(버전 관리) — 근거를 방향성 해석(A) / 충돌(B) / 근거 부족(C)으로 가른다. judge-2.0.0

v9.2 에서 바꾼 원칙(결과 분포를 맞추기 위한 조정이 아니라 근거의 성격에 따른 구분)
  1. 근거가 '없음'은 반대 근거가 아니다. 원국에 별이 안 보이는 것은 지지 근거가 없는 것일 뿐 T(부딪힘)로 세지 않는다.
  2. 규칙의 원문 확인 상태를 방향 판정에 반영한다. 원문 확인(text_confirmed)이 안 된 규칙(형·파·해 등)에서 나온 관계는 '참고'로만 남기고 S/T 에 넣지 않는다.
  3. 같은 운(세운/대운)의 같은 관계는 한 번만 센다. 기간 가중: 해의 절반 이상=2, 절반 미만·대운 지속=1. 원국 배경은 한쪽에 최대 1(운의 변화보다 작다).
  4. 방향성 주장(A)은 한쪽이 2 이상이고 반대쪽보다 2 이상 커야 한다. 양쪽이 모두 2 이상이면서 비슷하면 '충돌'(B)이고 하나로 정하지 않는다.
     그 밖의 약한 근거(한쪽 1~2, 차이 1 이하)는 결론을 내지 않고 '근거 부족'(C)으로 둔다. 자동으로 '기회와 주의가 함께'라고 쓰지 않는다.
  5. 계산 불확실성: 시주 후보가 갈리는 명식은 시주(hour) 궁위 근거를 방향 판정에서 제외한다.
"""
from __future__ import annotations

from ..mingli import classical

JUDGE_VERSION = "judge-2.0.0"

MIN_DOMINANT = 2      # 방향성 주장에 필요한 지배 쪽 최소 점수
MARGIN = 2            # 지배 쪽이 반대쪽보다 커야 하는 폭
MIN_CONFLICT = 2      # 충돌(B)로 인정하는 양쪽 최소 점수
NATAL_CAP = 1         # 원국 배경이 한쪽에 줄 수 있는 최대 점수
MAJOR_W, PARTIAL_W, PERSIST_W = 2, 1, 1

BAD_BY_RULE = {"충": "MG-L2-CHUNG", "삼형": "MG-L2-HYUNG", "형(부분)": "MG-L2-HYUNG", "무례지형(子卯)": "MG-L2-HYUNG", "자형": "MG-L2-HYUNG", "파": "MG-L2-PA", "해": "MG-L2-HAE"}
GOOD_BY_RULE = {"육합": "MG-L2-BRANCH-YUKHAP", "천간합": "MG-L2-STEM-HAP", "삼합(완전)": "MG-L2-SAMHAP", "삼합 완성 후보": "MG-L2-SAMHAP", "반합": "MG-L2-SAMHAP",
                "반합 형성 후보": "MG-L2-SAMHAP", "방합 완성 후보": "MG-L2-BANGHAP"}
NATAL_BAD = tuple(BAD_BY_RULE)
NATAL_GOOD = ("육합", "천간합", "삼합(완전)", "반합")


def relation_confirmed(rel_type: str) -> bool:
    """이 관계를 만드는 규칙이 원문 확인(text_confirmed)된 규칙인가. 확인 안 됐으면 방향 판정에 쓰지 않는다."""
    rid = BAD_BY_RULE.get(rel_type) or GOOD_BY_RULE.get(rel_type)
    return bool(rid) and classical.classical_status(rid) == "text_confirmed"


def classify(S: int, T: int, has_basis: bool, year_change: bool = True) -> dict:
    """tone: opportunity/cautious(A) · mixed(B 충돌) · thin(C 근거 부족) · quiet(근거는 있으나 이 해 전체로 달라지는 것 없음).
    year_change: 해의 절반 이상을 덮는 변화(또는 그런 관계)가 있는가. 약한 근거라도 이 해에 달라지는 것이 없으면 '근거 부족'이 아니라 '달라지지 않음'이다."""
    if not has_basis:
        return {"tone": "thin", "cls": "C", "reason": "no_basis"}
    if S == 0 and T == 0:
        return {"tone": "quiet", "cls": "none", "reason": "no_signal"}
    if S >= MIN_DOMINANT and S >= T + MARGIN:
        return {"tone": "opportunity", "cls": "A", "reason": "support_dominant"}
    if T >= MIN_DOMINANT and T >= S + MARGIN:
        return {"tone": "cautious", "cls": "A", "reason": "tension_dominant"}
    if S >= MIN_CONFLICT and T >= MIN_CONFLICT:
        return {"tone": "mixed", "cls": "B", "reason": "conflict"}
    if not year_change:
        return {"tone": "quiet", "cls": "none", "reason": "weak_signal_no_year_change"}
    return {"tone": "thin", "cls": "C", "reason": "weak_evidence"}


def consistent(tone: str, S: int, T: int) -> bool:
    """결론(톤)이 점수와 모순되지 않는가 — 테스트·검증용."""
    if tone in ("thin", "quiet", "steady", "balance"):
        return True
    return classify(S, T, True)["tone"] == tone


def palace_scores(pre: dict, dom: str, segments: list[dict], ex: dict | None, pals: tuple[str, ...], rels_at, major_frac: float, palace_relations, base: dict | None = None) -> dict:
    """궁위 분야(가족·연애·이직·부동산)의 S/T. 근거 목록(ex)과 운의 관계(segments)를 위 원칙대로 센다.
    합(合)류 관계는 '묶임·이어짐'의 존재만 확인되고 좋고 나쁨은 정해지지 않으므로(근거 문구도 그렇게 밝힌다) S 로 세지 않고 신호(palace_good)로만 둔다.
    분야가 구조(structures)를 선언했으면 구조 점수(base)를 출발점으로 쓴다."""
    ex = ex or {"evidence_for": [], "evidence_against": []}
    hour_unsure = (pre.get("variants_count") or 1) > 1 and "hour" in pals
    use = tuple(p for p in pals if not (hour_unsure and p == "hour"))
    pos = len([x for x in ex["evidence_for"] if "없음" not in x and "천간 노출 0개, 지지 암장 0개" not in x and "관계 후보에 관여" not in x])   # 별(십성)이 원국에 있는 근거만 — 합 관여는 방향 근거가 아님
    nat_bad = [r for r in rels_at(pre, use, NATAL_BAD) if relation_confirmed(r["relation_type"])] if use else []
    S = (base["S"] if base else 0) + (NATAL_CAP if pos >= 2 and not base else 0)
    T = (base["T"] if base else 0) + (NATAL_CAP if nat_bad else 0)
    reference: list[str] = []
    groups: dict[tuple, dict] = {}
    for r in palace_relations({"segments": segments}, use) if (segments and use) else []:
        if not relation_confirmed(r["type"]):
            reference.append(r["type"])
            continue
        k = (r["who"], r["type"])
        g = groups.get(k)
        if g is None or r["frac"] > g["frac"]:
            groups[k] = r
    bad_n = good_n = 0
    for (who, _t), r in groups.items():
        w = (MAJOR_W if r["frac"] >= major_frac else PARTIAL_W) if who == "year" else PERSIST_W
        if r["polarity"] == "bad":
            T += w
            bad_n += 1
        else:
            good_n += 1   # 합: 신호만(방향 아님)
    has_basis = bool(pos or nat_bad or groups or reference or (base and base["has_basis"]))
    year_change = any(who == "year" and r["frac"] >= major_frac for (who, _t), r in groups.items()) or bool(base and base.get("sup_up") or base and base.get("ten_up"))
    return {"year_change": year_change, "S": S, "T": T, "pos": pos, "neg": len(nat_bad), "palace_bad": bad_n, "palace_good": good_n, "reference": sorted(set(reference)), "has_basis": has_basis, "hour_excluded": hour_unsure}
