"""v9.3 명식 전체 종합 통변 — 개별 분야 풀이를 모아 '이 사주에서 무엇이 중요하게 읽히는가'를 하나로 연결한다. profile-1.0.0

설계 원칙
  - 같은 문장을 길게 만들지 않는다. 원국의 중심 구조(가장 뚜렷한 구조) → 그것을 지지·제한하는 조건 → 학파별 관점의 일치·충돌 → 대운·세운 중 무엇이 변화를 이끄는가 → 분야 연결 순서로 말한다.
  - 중심이 뚜렷하지 않으면(구조가 모두 속에 숨은 정도) 억지로 요약하지 않고 판단을 유보한다. 학파가 서로 다른 쪽을 가리키면 하나로 합치지 않고 그대로 둔다.
  - 판단 근거가 같은 분야(예: 직업과 이직은 같은 구조를 쓴다)는 같은 결론이 나오며, 그 사실을 밝힌다. 억지로 다른 결론을 만들지 않는다.
  - 사용자 문장에는 규칙 ID·전문 용어가 없다. 내부 근거(claim_ids·규칙 ID)는 반환값의 internal 에만 둔다.
출력 4단: 핵심 결론 / 왜 그렇게 읽는가 / 현실에서 참고할 부분 / 판단이 달라질 수 있는 조건
"""
from __future__ import annotations

from ..mingli import classical
from . import domains as D
from . import explain as E
from .readings import GOD_PLAIN
from . import facts as FA
from . import synthesis as S

PROFILE_VERSION = "profile-1.0.0"
CENTER_MIN_RANK = 2          # 이 이상(뚜렷함)이어야 '중심'으로 말한다. 1(암장 약함)뿐이면 요약을 유보한다.
GROUP_PLAIN = {"비겁": "나와 같은 기운(자립·경쟁)", "식상": "표현·기술의 기운", "재성": "재물·현실 자원의 기운", "관성": "직책·규율의 기운", "인성": "배움·보호의 기운"}
SCHOOL_PLAIN = {"gyeokguk": "태어난 달의 기운으로 판을 읽는 관점", "eokbu": "나의 힘이 도움을 받는지 소모되는지 보는 관점", "johu": "태어난 계절의 한난을 보는 관점"}
AXIS_PLAIN = {"한(寒)": "추운 계절", "열(熱)": "더운 계절", "조(燥)": "건조한 계절", "습(濕)": "습한 계절"}


def _theme(name: str) -> str:
    return S.STRUCT[name]["short"]


def _groups(gs: list[str]) -> str:
    """십성군(비겁 등)이든 구체 십신(食神 등)이든 쉬운 말로. 같은 말은 한 번만, 모르는 이름은 한자를 그대로 내보내지 않고 일반 표현으로."""
    out = []
    for g in gs:
        t = GROUP_PLAIN.get(g) or GOD_PLAIN.get(g) or "해당하는 기운"
        if t not in out:
            out.append(t)
    return "·".join(out)


def center(pre: dict) -> dict:
    """원국에서 가장 뚜렷한 구조. rank 가 같으면 돕는 쪽·부딪히는 쪽을 모두 말한다(합산하지 않는다)."""
    sts = [s for s in pre["natal_structure"]["layer3"]["structures"] if s["rank"] > 0]
    if not sts:
        return {"names": [], "withheld": "no_structure"}
    top = max(s["rank"] for s in sts)
    if top < CENTER_MIN_RANK:
        return {"names": [], "withheld": "all_hidden", "weak": [s["name"] for s in sts]}
    names = [s["name"] for s in sts if s["rank"] == top]
    sup = [n for n in names if S.STRUCT[n]["polarity"] == "support"]
    ten = [n for n in names if S.STRUCT[n]["polarity"] == "tension"]
    return {"names": names, "support": sup, "tension": ten, "rank": top, "withheld": None}


def schools_view(pre: dict) -> dict:
    """격국·억부·조후가 가리키는 방향(십성군)을 쉬운 말로. 겹치면 일치, 서로 다르면 충돌로 두고 합치지 않는다."""
    ys = pre["natal_structure"]["layer4"]["yongshin"]
    johu = pre["natal_structure"]["layer4"]["johu"]
    out, seen = [], {}
    for key, label in (("geukguk", "gyeokguk"), ("eokbu", "eokbu"), ("johu", "johu")):
        gs = ys.get(key, {}).get("groups", [])
        if gs:
            seen[label] = gs
        txt = SCHOOL_PLAIN[label]
        if label == "johu":
            ax = AXIS_PLAIN.get(johu.get("month_axis"), "계절의 한난이 한쪽으로 치우친 쪽")
            out.append({"school": label, "text": f"{txt}에서는 {ax}이라 " + (f"{_groups(gs)} 쪽을 중요하게 봅니다." if gs else "방향을 정하지 않습니다.")})
        else:
            out.append({"school": label, "text": f"{txt}에서는 " + (f"{_groups(gs)} 쪽을 중요하게 봅니다." if gs else "뚜렷한 방향을 정하지 않습니다.")})
    pick = list(seen.values())
    if len(pick) >= 2:
        common = set(pick[0]).intersection(*pick[1:])
        state = "agree" if common else "conflict"
    elif len(pick) == 1:
        state = "single"
    else:
        state = "none"
    note = {"agree": "관점이 같은 쪽을 가리킵니다.", "conflict": "관점마다 가리키는 쪽이 달라, 하나로 합치지 않고 각각 설명합니다.", "single": "한 관점에서만 방향이 나와 그 방향의 뒷받침은 약합니다.",
            "none": "어느 관점에서도 뚜렷한 방향이 나오지 않아 방향을 말하지 않습니다."}[state]
    return {"views": out, "state": state, "note": note}


def luck_year(pre: dict, P: dict, years: list[int]) -> list[dict]:
    """해마다 그해의 구조 변화를 이끈 것이 그해의 기운(세운)인지 10년 큰 흐름(대운)인지. 해 전체의 절반 이상을 덮는 변화만 센다."""
    rows = []
    for y in years[:5]:
        p = P.get(y)
        if not p:
            continue
        yr = FA.year_reading(p, list(S.STRUCT))
        yearly, luck, both = [], [], []
        for n, d in yr["ups_detail"].items():
            if d.get("category") != "year":
                continue
            dr = d["drivers"]
            (both if {"luck", "sewun"} <= dr else luck if dr == {"luck"} else yearly).append(n)
        txt = None
        if yearly or luck or both:
            parts = []
            if yearly:
                parts.append(f"그해의 기운이 이끄는 변화({'·'.join(_theme(n) for n in yearly[:1])})")
            if luck:
                parts.append(f"10년 큰 흐름이 이끄는 변화({'·'.join(_theme(n) for n in luck[:1])})")
            if both:
                parts.append(f"그해의 기운과 10년 큰 흐름이 함께 이끄는 변화({'·'.join(_theme(n) for n in both[:1])})")
            txt = f"{y}년: " + ", ".join(parts) + "가 있습니다."
        else:
            txt = f"{y}년: 해 전체로 이어지는 구조 변화는 읽히지 않습니다."
        if yr["luck_split"]:
            txt += " 이 해에는 10년 큰 흐름이 바뀌어 전과 후를 나누어 봐야 합니다."
        rows.append({"year": y, "text": txt, "yearly": yearly, "luck": luck, "both": both, "luck_split": yr["luck_split"]})
    return rows


def domain_links(names: list[str]) -> list[dict]:
    """중심 구조가 가장 직접적으로 드러나는 분야(분야가 선언한 구조에 포함된 분야)."""
    out = []
    for dom, spec in D.DOMAINS.items():
        hit = [n for n in names if n in spec["structures"]]
        if dom in ("overall", "luck") or not hit:
            continue
        out.append({"domain": dom, "name": spec["name"], "via": hit})
    return out


def shared_basis_notes(blocks: list[dict]) -> list[str]:
    """같은 구조를 근거로 쓰는 분야가 같은 결론을 낸 경우 그 사실을 밝힌다(억지로 다르게 만들지 않는다)."""
    pairs = []
    by = {b["domain"]: b for b in blocks if b["domain"] != "overall"}   # 종합은 다른 분야를 모은 것이므로 비교에서 뺀다
    for a in by:
        for b in by:
            if a >= b:
                continue
            sa, sb = set(D.DOMAINS[a]["structures"]), set(D.DOMAINS[b]["structures"])
            if len(sa & sb) >= 2 and by[a]["tone"] == by[b]["tone"] and by[a]["scores"] == by[b]["scores"] and by[a]["tone"] not in ("thin", "quiet", "steady", "balance"):
                pairs.append(f"{by[a]['name']}·{by[b]['name']}")
    if not pairs:
        return []
    return ["같은 구조를 근거로 읽는 분야(" + ", ".join(pairs[:3]) + ")는 같은 방향으로 나옵니다. 다르게 읽을 만한 별도의 근거가 없어 억지로 나누지 않았습니다."]


def _rule_state(names: list[str]) -> list[str]:
    out = []
    for n in names:
        rid = S.RULE_OF.get(n)
        st = classical.classical_status(rid) if rid else "pending"
        if st != "text_confirmed" or classical.coverage(rid) == "partial":
            out.append(n)
    return out


def build(pre: dict, P: dict, years: list[int], blocks: list[dict], calc_items: list[str] | None = None) -> dict:
    """blocks: 대표 연도(첫 연도)의 분야 블록. 반환: 사용자용 필드 + internal(규칙·근거 ID)."""
    c = center(pre)
    sv = schools_view(pre)
    ly = luck_year(pre, P, years) if years else []
    deuk = pre["natal_structure"]["layer1"]["deukryeong"]
    withheld = c["withheld"] is not None and sv["state"] in ("none",)

    # --- 핵심 결론
    if c["names"]:
        parts = [f"‘{_theme(n)}’" for n in c["names"][:2]]
        concl = f"이 사주에서 가장 뚜렷하게 읽히는 것은 {' 그리고 '.join(parts)}입니다."
        if c["support"] and c["tension"]:
            concl += " 돕는 흐름과 부딪히는 흐름이 함께 뚜렷해 한쪽으로 정하지 않습니다."
        elif c["tension"]:
            concl += " 이 흐름은 점검과 조율이 필요한 쪽으로 읽힙니다."
    elif sv["state"] in ("agree", "single", "conflict") and any(v["text"].endswith("중요하게 봅니다.") for v in sv["views"]):
        concl = "한 가지 구조가 뚜렷하게 앞서 읽히지는 않습니다. 대신 관점별로 중요하게 보는 쪽이 있어, 아래에서 관점마다 따로 설명합니다."
    else:
        concl = "이 사주에서는 한 가지 구조가 뚜렷하게 앞서 읽히지 않고 관점별 방향도 나오지 않아, 한마디로 요약하지 않습니다."

    # --- 왜 그렇게 읽는가
    why: list[str] = []
    layer3 = {s["name"]: s for s in pre["natal_structure"]["layer3"]["structures"]}
    for n in c["names"][:2]:
        r = E.natal_reason(layer3[n], _theme(n))
        if r:
            why.append(r)
    if c["withheld"] == "all_hidden":
        why.append("읽히는 구조가 모두 겉으로 드러나지 않고 속에 숨은 정도라서, 그중 하나를 중심이라고 고르지 않았습니다.")
    if deuk.get("agree") is True and deuk.get("by_season_element") == "득령":
        why.append("태어난 계절의 기운이 나와 같은 쪽이라 자기 힘이 받쳐지는 바탕이 있습니다(계절 기준).")
    elif deuk.get("agree") is False:
        why.append("태어난 달이 나를 돕는지는 기준에 따라 다르게 나와, 이 부분은 한쪽으로 정하지 않았습니다.")
    why += [v["text"] for v in sv["views"]]
    why.append(sv["note"])
    if ly:
        why += [r["text"] for r in ly]

    # --- 현실에서 참고할 부분
    reality: list[str] = []
    links = domain_links(c["names"]) if c["names"] else []
    if links:
        reality.append("이 구조는 " + "·".join(x["name"] for x in links[:3]) + " 쪽에서 가장 직접적으로 드러납니다.")
    firm = [b["name"] for b in blocks if b["tone"] in ("opportunity", "cautious")]
    held = [b["name"] for b in blocks if b["tone"] == "thin"]
    clash = [b["name"] for b in blocks if b["tone"] == "mixed"]
    if firm:
        reality.append(f"{years[0]}년에는 {'·'.join(firm[:4])}에서 방향이 읽힙니다." if years else "·".join(firm[:4]) + "에서 방향이 읽힙니다.")
    if clash:
        reality.append("서로 다른 근거가 맞서 하나로 정하지 않은 분야: " + "·".join(clash[:4]) + ". 돕는 쪽과 부딪히는 쪽을 각각 분야 풀이에서 설명합니다.")
    if held:
        reality.append("근거가 부족해 판단을 유보한 분야: " + "·".join(held[:5]) + ". 이 분야는 현실의 상황과 계획을 우선 기준으로 삼는 편이 좋습니다.")
    reality += shared_basis_notes(blocks)

    # --- 판단이 달라질 수 있는 조건
    conds: list[str] = []
    for t in (calc_items or []):
        conds.append(t)
    if sv["state"] == "conflict":
        conds.append("관점에 따라 중요하게 보는 쪽이 달라, 어느 관점을 택하느냐에 따라 해석이 달라질 수 있습니다.")
    weak_rules = _rule_state(c["names"])
    if weak_rules:
        conds.append("이 구조를 읽는 규칙은 고전 원문과의 대조가 일부만 끝났습니다. 해석의 무게를 낮춰 받아들여 주세요.")
    if any(r["luck_split"] for r in ly):
        conds.append("선택한 연도 중 10년 큰 흐름이 바뀌는 해가 있어, 그 전과 후는 다르게 읽어야 합니다.")
    if clash:
        conds.append("서로 맞서는 근거가 있는 분야는 어느 쪽 근거가 현실에 더 맞는지에 따라 판단이 달라질 수 있습니다.")
    if held:
        conds.append("근거가 부족한 분야는 새로운 정보(실제 상황)가 더해지면 판단이 달라질 수 있습니다.")
    if not conds:
        conds.append("출생 시각이나 날짜가 달라지면 결과가 달라집니다. 입력한 정보가 정확한지 확인해 주세요.")

    internal = {"version": PROFILE_VERSION, "center": c, "schools_state": sv["state"], "luck_year": [{k: v for k, v in r.items() if k != "text"} for r in ly],
                "rule_ids": [S.RULE_OF[n] for n in c["names"] if n in S.RULE_OF], "claim_ids": [layer3[n]["claim_id"] for n in c["names"] if n in layer3],
                "unconfirmed_center_rules": weak_rules}
    return {"version": PROFILE_VERSION, "withheld": bool(withheld or (not c["names"] and sv["state"] == "none")), "conclusion": concl, "why": why, "reality": reality, "conditions": conds,
            "views": sv["views"], "internal": internal}
