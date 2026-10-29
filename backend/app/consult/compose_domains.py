"""분야별 궁위·십성 신호. 모든 문장은 구조 분석 결과에서만 만든다(새 주장 없음).

- 연애·결혼: 일지(배우자궁) + 배우자성(남: 재성, 여: 관성)
- 가족·인간관계: 연·월·시주 궁위와 인성·비겁·자녀성(남: 관성, 여: 식상)
- 건강 관련 전통 해석: 오행 집계와 조후 방향만 '균형의 상징'으로 설명. 진단·질병명·장기 대응 서술 금지
- 부동산: 재성·인성 + 고(庫) 지지 + 개고 후보
- 이직·취업: 직업궁(월주) 관계 + 관성·인성 구조
이 대응은 구현자 규약이며 고전 원문 대조가 끝나지 않았다(rules 의 classical 상태 참조).
"""
from __future__ import annotations

from ..chart_analysis import GROUP_OF
from ..mingli.layer1 import hidden_with_roles
from ..report_checks import ten_god

PALACE_KO = {"year": "연주(조상·초년궁)", "month": "월주(부모·사회·직업궁)", "day": "일주(자신·배우자궁)", "hour": "시주(자녀·말년궁)"}
BAD_REL = ("충", "삼형", "형(부분)", "무례지형(子卯)", "자형", "파", "해")
STORE_BRANCH = set("辰戌丑未")
HEALTH_NOTICE = "건강 문제나 증상은 이 해석으로 판단할 수 없습니다. 걱정되는 부분은 의료진과 상담하세요."


def spouse_star(gender: str | None) -> str:
    return "재성" if gender == "male" else ("관성" if gender == "female" else "재성/관성")


def child_star(gender: str | None) -> str:
    return "관성" if gender == "male" else ("식상" if gender == "female" else "관성/식상")


def _day_palace(pre: dict) -> list[dict]:
    P = pre["natal_structure"]["pillars"]
    ds, db = P["day"][0], P["day"][1]
    return [{"stem": h["stem"], "role": h["role"], "god": ten_god(ds, h["stem"]), "group": GROUP_OF[ten_god(ds, h["stem"])]} for h in hidden_with_roles(db)]


def _rels_at(pre: dict, positions: tuple[str, ...], kinds: tuple[str, ...] | None = None) -> list[dict]:
    out = []
    for r in pre["natal_structure"]["layer2"]["relations"]:
        if set(r["pillars"]) & set(positions) and (kinds is None or r["relation_type"] in kinds):
            out.append(r)
    return out


def _count(pre: dict, group: str) -> tuple[int, int]:
    gc = pre["natal_structure"]["layer1"]["support_structure"]["group_counts"]
    if "/" in group:
        return sum(_count(pre, g)[0] for g in group.split("/")), sum(_count(pre, g)[1] for g in group.split("/"))
    return gc[group]["visible"], gc[group]["hidden"]


def domain_extra(dom: str, pre: dict) -> dict | None:
    gender = pre.get("gender")
    b = pre["natal_structure"]
    P = b["pillars"]
    for_, against, cids, text = [], [], [], ""
    if dom == "love_marriage":
        star = spouse_star(gender)
        v, h = _count(pre, star)
        pal = _day_palace(pre)
        db = P["day"][1]
        text = f"연애·결혼은 전통 해석에서 일지(배우자궁)와 배우자성({star})을 중심으로 봅니다."
        if v or h:
            for_.append(f"배우자성({star}): 천간 노출 {v}개, 지지 암장 {h}개")
        if pal:
            for_.append(f"배우자궁 일지 '{db}'의 본기 '{pal[0]['stem']}'({pal[0]['god']})")
            if any(p["group"] in star for p in pal):
                for_.append(f"배우자궁 안에 배우자성({star}) 십성군이 들어 있음")
        if not (v or h):
            against.append(f"배우자성({star})이 원국 천간·지지에 보이지 않음")
        for r in _rels_at(pre, ("day",), BAD_REL):
            against.append(f"배우자궁(일지)이 {r['relation_type']} 관계 후보에 있음(존재만 확인, 관계의 질은 확정하지 않음) [{r['claim_id']}]")
            cids.append(r["claim_id"])
        for r in _rels_at(pre, ("day",), ("육합", "천간합", "삼합(완전)", "반합")):
            for_.append(f"일주가 {r['relation_type']} 관계 후보에 관여 [{r['claim_id']}] (합이 곧 좋다는 뜻은 아님)")
            cids.append(r["claim_id"])
        if gender not in ("male", "female"):
            against.append("성별 정보가 없어 배우자성을 재성/관성 모두로 보았음")
    elif dom == "family":
        ch = child_star(gender)
        text = "가족·인간관계는 전통 해석에서 연·월·시주의 궁위와 인성(윗사람·보호), 비겁(형제·동료), 자녀성을 함께 봅니다."
        for g, label in (("인성", "인성(어머니·윗사람 상징)"), ("비겁", "비겁(형제·동료 상징)"), (ch, f"자녀성({ch})")):
            v, h = _count(pre, g)
            (for_ if (v or h) else against).append(f"{label}: " + (f"천간 노출 {v}개, 지지 암장 {h}개" if (v or h) else "원국에 보이지 않음"))
        for pos in ("year", "month", "hour"):
            for r in _rels_at(pre, (pos,), BAD_REL):
                against.append(f"{PALACE_KO[pos]}가 {r['relation_type']} 관계 후보에 있음(존재만 확인) [{r['claim_id']}]")
                cids.append(r["claim_id"])
    elif dom == "health_traditional":
        tally = b["layer4"]["johu"]["element_tally"]
        miss = [e for e in "木火土金水" if e not in tally]
        j = b["layer4"]["johu"]
        text = ("건강 관련 전통 해석은 오행의 편중과 계절의 한난 균형을 '균형의 상징'으로만 설명합니다. 진단이나 예측이 아니며 병명·증상과 연결하지 않습니다. " + HEALTH_NOTICE)
        for_.append("천간·지지 본기 오행 집계(사실): " + ", ".join(f"{e}{c}" for e, c in sorted(tally.items())))
        for_.append(f"월지 계절 방향: {j['month_axis']}" + (f", 균형 방향 오행 후보 {','.join(j['direction_elements'])}" if j["direction_elements"] else ""))
        if miss:
            against.append("집계에 나타나지 않은 오행: " + ", ".join(miss) + " (집계는 사실일 뿐 부족이나 결함을 뜻하지 않음)")
        against.append("오행 집계는 건강 상태와 관계가 검증되지 않았으며 의학적 근거가 없음")
        cids.append(j["claim_id"])
    elif dom == "real_estate":
        text = "부동산은 전통 해석에서 재성(재산의 상징), 인성(문서·거처의 상징), 그리고 창고 역할을 하는 지지(辰戌丑未)의 상태를 봅니다."
        for g in ("재성", "인성"):
            v, h = _count(pre, g)
            (for_ if (v or h) else against).append(f"{g}: " + (f"천간 노출 {v}개, 지지 암장 {h}개" if (v or h) else "원국에 보이지 않음"))
        stores = [p for p in P if P[p][1] in STORE_BRANCH]
        if stores:
            for_.append("창고 지지(辰戌丑未): " + ", ".join(f"{PALACE_KO[p].split('(')[0]} '{P[p][1]}'" for p in stores))
        else:
            against.append("원국에 창고 지지(辰戌丑未)가 없음")
        for r in b["layer2"]["relations"]:
            if r["relation_type"] == "개고·입묘 후보":
                against.append(f"개고·입묘 후보는 학파별로 해석이 갈림 [{r['claim_id']}]")
                cids.append(r["claim_id"])
    elif dom == "job_change":
        text = "이직·취업은 전통 해석에서 직업궁(월주)과 관성·인성 구조, 그리고 운에서 직업궁에 닿는 관계를 함께 봅니다."
        for r in _rels_at(pre, ("month",), BAD_REL):
            against.append(f"직업궁(월주)이 원국에서 {r['relation_type']} 관계 후보에 있음(존재만 확인) [{r['claim_id']}]")
            cids.append(r["claim_id"])
        for r in _rels_at(pre, ("month",), ("육합", "천간합", "삼합(완전)", "반합")):
            for_.append(f"월주가 {r['relation_type']} 관계 후보에 관여 [{r['claim_id']}]")
            cids.append(r["claim_id"])
        for g in ("관성", "인성"):
            v, h = _count(pre, g)
            (for_ if (v or h) else against).append(f"{g}: " + (f"천간 노출 {v}개, 지지 암장 {h}개" if (v or h) else "원국에 보이지 않음"))
    else:
        return None
    return {"text": text, "evidence_for": for_, "evidence_against": against, "claim_ids": cids}


DOMAIN_PALACES = {"love_marriage": ("day",), "family": ("year", "month", "hour"), "job_change": ("month",), "real_estate": ("day", "hour"),
                  "career": ("month",), "business": ("month", "hour"), "wealth": ("month", "day"), "docs_realestate": ("year", "month"), "health_traditional": ()}


def period_palace_notes(dom: str, segment_relations: list[dict]) -> list[str]:
    """운(대운·세운)이 이 분야의 궁위와 맺는 관계 후보. 분야마다 보는 궁위가 달라 같은 해라도 문장이 달라진다."""
    pals = DOMAIN_PALACES.get(dom, ())
    out = []
    for r in segment_relations:
        if r["with"] in pals:
            who = {"luck": "대운", "year": "세운"}[r["who"]]
            out.append(f"{who}이 {PALACE_KO[r['with']]}와 {r['type']} 관계 후보({r['chars']})를 이룸 — 존재만 확인")
    return out


def cross_links(blocks: list[dict]) -> str | None:
    """여러 분야에 공통으로 쓰인 생극제화 구조가 있으면 연결 관계를 설명한다."""
    seen: dict[str, list[str]] = {}
    for b in blocks:
        for s in b["structures"]:
            if s["label"] != "없음":
                seen.setdefault(s["structure"], []).append(b["name"])
    shared = {k: v for k, v in seen.items() if len(v) >= 2}
    if not shared:
        return None
    parts = "; ".join(f"'{k}' 구조는 {', '.join(v)}에서 모두 참고됩니다" for k, v in shared.items())
    return parts + ". 한 분야의 해석이 다른 분야의 결과를 정하는 것이 아니라, 같은 구조가 여러 주제에 걸쳐 읽힌다는 연결로만 이해하세요."


def special_event_state(ev: str, pre_base: dict, gender: str | None) -> str:
    """연애·가족 사건 유형의 사전 판단(구현자 규약)."""
    fake = {"natal_structure": pre_base, "gender": gender}
    if ev == "연애·결혼 관련 변화":
        star = spouse_star(gender)
        v, h = _count(fake, star)
        pal = any(p["group"] in star for p in _day_palace(fake))
        return "indicated" if (v and pal) else ("weak" if (v or h) else "not_indicated")
    if ev == "가족·관계 변화":
        n = len(_rels_at(fake, ("year", "month", "hour"), BAD_REL))
        return "indicated" if n >= 2 else ("weak" if n == 1 else "not_indicated")
    return "not_indicated"
