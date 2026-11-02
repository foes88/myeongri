"""v10.1 십성·궁위 풀이 — 이 사주의 글자 배치로 성향·일하는 방식·돈을 다루는 방식·관계의 모습, 그리고 시기별 주제를 말로 풀어 준다. sipsung-1.0.0

성격
  - 전통 명리에서 널리 쓰는 일반 해석(십성의 뜻, 네 기둥의 자리 의미)을 구현자가 쉬운 말로 정리한 것이다. 원전 원문과 대조하지 않았고,
    사람을 단정하는 말이 아니라 '이런 쪽으로 읽히는 경향'이다. 화면에도 그렇게 밝힌다(LABEL).
  - 판정 로직(judge)·종합 통변(profile)의 톤 판정에는 값을 넘기지 않는다. 이 모듈의 출력은 설명 문장이다.
  - 문장이 사람마다 같아지지 않도록 '이 사주에 실제로 있는 글자'(어느 자리에 어떤 기운이 드러나 있고 속에 얼마나 숨어 있는가)에서만 고른다.
    근거가 약하면(뚜렷하게 앞서는 기운이 없으면) 그렇게 말하고 일반론으로 채우지 않는다.
  - 사용자 문장에는 전문 용어·한자·규칙 번호가 없다.
"""
from __future__ import annotations

from ..report_checks import HIDDEN_STEMS_PROFILE, ten_god

SIPSUNG_VERSION = "sipsung-1.0.0"
LABEL = "전통에서 널리 쓰는 일반 해석을 쉬운 말로 정리한 것입니다. 원전 원문과의 대조는 아직 하지 않았고, 사람을 단정하는 말이 아니라 ‘이런 쪽으로 읽히는 경향’입니다."
DOMINANT_MIN = 3.0      # 이 이상 모인 기운만 '두드러진다'고 말한다(가중치 합, 아래 weights 참조)
AREA = {"year": "어린 시절과 집안 쪽(태어난 해)", "month": "사회생활과 일하는 환경(태어난 달)", "day": "나 자신과 배우자 자리(태어난 날)", "hour": "말년과 자녀·결과물 쪽(태어난 시)"}
GROUP = {"比肩": "peer", "劫財": "peer", "食神": "output", "傷官": "output", "偏財": "wealth", "正財": "wealth", "七殺": "power", "正官": "power", "偏印": "support", "正印": "support"}
GROUP_PLAIN = {"peer": "나와 같은 기운(자립·동료·경쟁)", "output": "표현·기술의 기운", "wealth": "재물·현실 자원의 기운", "power": "직책·규율·압박의 기운", "support": "배움·보호의 기운"}

# 십성별 풀이. core=그 기운을 한마디로, 나머지는 '이 기운이 두드러질 때'의 경향이다(문장은 모두 경향 표현).
G = {
    "比肩": {"name": "나와 같은 기운(동료·자립)", "core": "자기 방식을 지키는",
            "tendency": "자기 방식과 독립심이 강하고, 남에게 휘둘리기보다 스스로 정하려는 경향이 있습니다.",
            "career": "혼자 책임지고 해내는 일, 동료와 대등하게 협력하는 일에서 편안함을 느끼는 편입니다.",
            "money": "내 힘으로 번 돈을 지키려 하지만, 동료·친구와 돈을 나누거나 함께 쓰는 일이 생기기 쉽습니다.",
            "relation": "대등한 관계를 좋아하고, 상하 관계나 간섭에는 답답함을 느끼기 쉽습니다.",
            "year": "나 자신과 동료, 경쟁 상대가 주제로 올라오는 해", "prep": "혼자 끌고 가기보다 역할과 몫을 먼저 정해 두는 편이 좋습니다."},
    "劫財": {"name": "나와 같은 기운(승부·경쟁)", "core": "승부욕이 강한",
            "tendency": "승부욕과 추진력이 강하고, 경쟁 속에서 오히려 힘을 내는 경향이 있습니다.",
            "career": "경쟁이 있는 환경, 성과가 눈에 보이는 일에서 힘을 냅니다.",
            "money": "돈이 들어오는 만큼 나가기도 쉬워, 동업·보증·공동 지출은 조건을 분명히 하는 편이 좋습니다.",
            "relation": "가까운 사이에서도 주도권을 두고 부딪히기 쉬우니, 서운함을 말로 푸는 것이 좋습니다.",
            "year": "경쟁과 분배, 협력의 몫이 주제로 올라오는 해", "prep": "공동 자금과 역할 분담은 문서로 남겨 두세요."},
    "食神": {"name": "표현·기술의 기운(여유·재능)", "core": "재능을 편안하게 펼치는",
            "tendency": "표현하고 만들어 내는 일을 편안하게 즐기고, 여유와 꾸준함이 있는 경향입니다.",
            "career": "손으로 만들거나 가르치고 표현하는 일, 결과물을 꾸준히 쌓아 가는 일에 맞습니다.",
            "money": "재능과 기술이 수입으로 이어지는 방식에 가깝고, 큰 한 방보다 꾸준한 흐름을 만듭니다.",
            "relation": "주변을 편하게 해 주는 편이지만, 속마음을 드러내는 데는 시간이 걸릴 수 있습니다.",
            "year": "재능과 표현, 먹고사는 방식이 주제로 올라오는 해", "prep": "하고 싶은 작업이나 기술을 하나 정해 꾸준히 쌓아 보세요."},
    "傷官": {"name": "표현·기술의 기운(날카로움·창의)", "core": "틀에 매이지 않는",
            "tendency": "표현이 날카롭고 창의적이며, 틀에 매이는 것을 답답해하는 경향이 있습니다.",
            "career": "새로운 것을 만들거나 기존 방식을 바꾸는 일, 말과 기술로 승부하는 일에서 힘이 납니다.",
            "money": "재능을 돈으로 바꾸는 힘이 있지만, 조직의 규칙과 부딪혀 기회를 놓치지 않도록 조율이 필요합니다.",
            "relation": "솔직한 말이 상처가 될 수 있어, 표현의 시기와 방식을 고르는 편이 좋습니다.",
            "year": "표현과 변화, 규칙과의 마찰이 주제로 올라오는 해", "prep": "말하기 전에 한 번 정리하고, 바꾸고 싶은 점은 제안의 형태로 전하세요."},
    "偏財": {"name": "재물·현실 자원의 기운(유동적·사업)", "core": "기회를 넓게 잡는",
            "tendency": "사람과 돈의 흐름을 넓게 보고, 기회가 보이면 움직이는 활동적인 경향이 있습니다.",
            "career": "사람을 만나고 거래하는 일, 사업·영업·유통처럼 움직임이 큰 일에 맞습니다.",
            "money": "수입이 일정하기보다 기회에 따라 크게 움직이는 편이라, 들어올 때 지출 한도를 정해 두는 것이 좋습니다.",
            "relation": "인간관계가 넓고 베푸는 편이지만, 한 사람에게 깊이 머무는 데는 노력이 필요할 수 있습니다.",
            "year": "돈의 흐름과 사업, 넓은 인간관계가 주제로 올라오는 해", "prep": "새 기회는 얻을 것과 위험을 나란히 적어 비교하세요."},
    "正財": {"name": "재물·현실 자원의 기운(안정적·성실)", "core": "성실하게 쌓아 가는",
            "tendency": "성실하고 계획적이며, 안정을 중시하는 경향이 있습니다.",
            "career": "월급이나 정기 수익처럼 안정적인 구조, 꼼꼼함이 필요한 일에 맞습니다.",
            "money": "꾸준히 모으고 지키는 방식에 가깝고, 지출을 계획적으로 관리하는 편입니다.",
            "relation": "책임감 있고 현실적인 관계를 중시합니다.",
            "year": "안정적인 수입과 생활 기반이 주제로 올라오는 해", "prep": "고정 지출과 저축 구조를 점검해 보세요."},
    "七殺": {"name": "직책·규율·압박의 기운(도전)", "core": "압박 속에서 힘을 내는",
            "tendency": "압박 속에서 오히려 힘을 내고, 도전과 위기에 정면으로 부딪히는 경향이 있습니다.",
            "career": "경쟁이 치열하거나 책임이 큰 일, 위기를 수습하는 역할에서 능력이 드러납니다.",
            "money": "큰 책임과 함께 돈이 움직이는 편이라, 무리한 확장은 점검이 필요합니다.",
            "relation": "강한 인상을 주는 편이며, 가까운 사람에게 엄격해지지 않도록 살피는 것이 좋습니다.",
            "year": "압박과 도전, 책임이 커지는 일이 주제로 올라오는 해", "prep": "일을 나누고 쉬는 시간을 먼저 확보하세요."},
    "正官": {"name": "직책·규율·압박의 기운(책임·평가)", "core": "책임과 규칙을 중시하는",
            "tendency": "책임감과 체면, 규칙을 중시하고 신뢰를 쌓아 가는 경향이 있습니다.",
            "career": "조직 안에서 역할과 평가가 분명한 일, 공적인 신뢰가 필요한 일에 맞습니다.",
            "money": "안정된 자리에서 나오는 수입과 지위에 가까운 보상을 중시합니다.",
            "relation": "예의와 약속을 중요하게 생각하며, 상대에게도 같은 기준을 기대하기 쉽습니다.",
            "year": "직책과 평가, 책임과 규칙이 주제로 올라오는 해", "prep": "평가 시기와 기준을 미리 확인해 두세요."},
    "偏印": {"name": "배움·보호의 기운(독특한 관심·직관)", "core": "남과 다른 관심을 파고드는",
            "tendency": "남과 다른 관심사와 직관이 있고, 혼자 파고드는 경향이 있습니다.",
            "career": "전문 기술이나 연구, 틈새 분야처럼 정해진 틀에서 벗어난 일에서 개성이 드러납니다.",
            "money": "안정적인 수입보다 전문성이 쌓여야 돈이 따르는 편이라 시간이 걸릴 수 있습니다.",
            "relation": "속마음을 쉽게 열지 않는 편이라, 가까운 사람에게는 먼저 말해 주는 노력이 필요합니다.",
            "year": "새로운 배움과 전문성, 혼자 하는 고민이 주제로 올라오는 해", "prep": "관심 분야 하나를 정해 결과물로 남겨 보세요."},
    "正印": {"name": "배움·보호의 기운(학업·도움)", "core": "배우고 도움을 받는",
            "tendency": "배우고 이해하는 것을 중시하고, 주변의 도움과 보호를 받는 경향이 있습니다.",
            "career": "교육·상담처럼 신뢰를 바탕으로 하는 일, 자격이나 문서가 중요한 일에 맞습니다.",
            "money": "자격과 신뢰가 쌓이면서 수입이 따라오는 방식에 가깝습니다.",
            "relation": "배려가 깊고 도움을 주고받는 관계를 중시하지만, 의존하지 않도록 균형이 필요합니다.",
            "year": "배움과 자격, 문서와 도움받는 일이 주제로 올라오는 해", "prep": "공부하거나 문서를 정리할 일을 이 해에 맞춰 두세요."},
}
SPOUSE_GROUP = {"male": "wealth", "female": "power"}
SPOUSE_PLAIN = {"male": "배우자를 뜻하는 재물·현실 자원의 기운", "female": "배우자를 뜻하는 직책·규율의 기운"}


def _weights(pil: dict) -> tuple[dict[str, float], dict[str, list[tuple[str, str, float]]]]:
    """기운별 가중치 합과 자리별 근거. 천간(일간 제외)=2, 지지 본기=2(태어난 달의 지지는 3), 지지 속에 숨은 글자=1."""
    day = pil["day"][0]
    tot: dict[str, float] = {g: 0.0 for g in G}
    where: dict[str, list[tuple[str, str, float]]] = {"year": [], "month": [], "day": [], "hour": []}
    for pos in ("year", "month", "day", "hour"):
        p = pil.get(pos)
        if not p:
            continue
        if pos != "day":
            g = ten_god(day, p[0])
            tot[g] += 2
            where[pos].append((g, "드러남", 2))
        hid = HIDDEN_STEMS_PROFILE[p[1]]
        for i, st in enumerate(hid):
            g = ten_god(day, st)
            w = (3 if pos == "month" else 2) if i == 0 else 1
            tot[g] += w
            where[pos].append((g, "본기" if i == 0 else "숨음", w))
    return tot, where


def _group_totals(tot: dict[str, float]) -> dict[str, float]:
    out = {k: 0.0 for k in GROUP_PLAIN}
    for g, w in tot.items():
        out[GROUP[g]] += w
    return out


def dominant(tot: dict[str, float]) -> list[str]:
    """두드러지는 기운(십성) 1~2개. 가장 큰 값이 DOMINANT_MIN 미만이면 앞서는 기운이 없다고 본다. 둘째는 첫째의 70% 이상일 때만."""
    order = sorted(tot, key=lambda g: (-tot[g], list(G).index(g)))
    if tot[order[0]] < DOMINANT_MIN:
        return []
    out = [order[0]]
    if tot[order[1]] >= max(DOMINANT_MIN, tot[order[0]] * 0.7):
        out.append(order[1])
    return out


def _spouse(pil: dict, gender: str | None, tot: dict, where: dict) -> str | None:
    grp = SPOUSE_GROUP.get(gender or "")
    if not grp:
        return None
    gs = {g for g in G if GROUP[g] == grp}
    shown = any(g in gs for pos in ("year", "month", "hour") for g, how, _ in where[pos] if how == "드러남")
    hidden = any(g in gs for pos in where for g, how, _ in where[pos] if how != "드러남")
    nm = SPOUSE_PLAIN[gender]
    if shown:
        return f"{nm}이 겉으로 드러나 있어, 관계에 대한 관심과 기대가 비교적 분명하게 나타나는 편입니다."
    if hidden:
        return f"{nm}은 겉으로 드러나지 않고 속에 숨어 있어, 관계에 대한 마음이 천천히 드러나는 편으로 읽습니다."
    return f"{nm}이 타고난 글자에는 보이지 않아, 관계의 모습은 이 기운보다 배우자 자리와 다른 요소에서 읽어야 합니다."


def profile(pil: dict, gender: str | None = None) -> dict | None:
    """성향·일하는 방식·돈·관계를 이 사주의 글자 배치에서 말로 푼다. 반환 sections 의 text 는 사용자용, evidence 는 '왜 그렇게 읽나요?'용."""
    if not pil or not pil.get("day") or not pil.get("month"):
        return None
    tot, where = _weights(pil)
    dom = dominant(tot)
    grp = _group_totals(tot)
    top_grp = max(grp, key=lambda k: grp[k])
    month_gods = [g for g, how, _ in where["month"]]
    month_main = where["month"][0][0] if where["month"] else None          # 태어난 달의 천간
    month_branch = next((g for g, how, _ in where["month"] if how == "본기"), None)
    ev: dict[str, list[str]] = {"tendency": [], "career": [], "money": [], "relation": []}
    sections = []

    # 성향
    if dom:
        txt = G[dom[0]]["tendency"] + (" 한편 " + G[dom[1]]["tendency"] if len(dom) > 1 else "")
        names = " 그리고 ".join(f"‘{G[g]['core']}’" for g in dom)
        ev["tendency"].append(f"타고난 글자를 자리마다 세어 보면 {names} 쪽 기운이 가장 크게 모입니다.")
    else:
        txt = "타고난 글자에서 한 가지 기운이 뚜렷하게 앞서지는 않습니다. 그래서 성향을 한 가지로 말하기보다, 상황에 따라 여러 모습이 나오는 쪽으로 읽습니다."
        ev["tendency"].append("한 기운이 가장 크게 모이지 않아 성향을 한 가지로 정하지 않았습니다.")
    sections.append({"key": "tendency", "title": "이 사주의 성향", "text": txt})

    # 일하는 방식: 태어난 달(사회·직업 자리)의 기운 + 가장 큰 기운 묶음
    c_gods = [g for g in (month_main, month_branch) if g]
    seen = []
    for g in c_gods:
        if g not in seen:
            seen.append(g)
    if seen:
        ctxt = G[seen[0]]["career"] + (" 한편 " + G[seen[1]]["career"] if len(seen) > 1 else "")
        ev["career"].append(f"일하는 환경을 뜻하는 자리(태어난 달)에는 {' 그리고 '.join('‘' + G[g]['core'] + '’' for g in seen[:2])} 기운이 놓여 있습니다.")
    else:
        ctxt = "일하는 환경을 뜻하는 자리에서 뚜렷하게 읽히는 기운이 없어, 일의 방식은 성향 쪽에서 읽습니다."
    sections.append({"key": "career", "title": "일하는 방식", "text": ctxt})

    # 돈을 다루는 방식: 재물 기운이 있으면 그 방식, 없으면 두드러지는 기운이 돈을 다루는 법
    wealth = [g for g in ("偏財", "正財") if tot[g] > 0]
    if wealth:
        top_w = max(wealth, key=lambda g: tot[g])
        mtxt = G[top_w]["money"]
        ev["money"].append(f"돈을 뜻하는 기운 중 ‘{G[top_w]['core']}’ 쪽이 더 크게 놓여 있습니다.")
    elif dom:
        mtxt = "돈을 뜻하는 기운이 타고난 글자에는 뚜렷하게 보이지 않습니다. 그래서 돈은 " + G[dom[0]]["money"]
        ev["money"].append("재물을 뜻하는 기운이 보이지 않아, 가장 큰 기운이 돈을 다루는 방식으로 읽었습니다.")
    else:
        mtxt = "돈을 뜻하는 기운도, 앞서는 다른 기운도 뚜렷하지 않아 돈을 다루는 방식은 말하지 않습니다."
    sections.append({"key": "money", "title": "돈을 다루는 방식", "text": mtxt})

    # 관계: 배우자 자리(태어난 날 아래 글자)의 기운 + 배우자를 뜻하는 기운
    day_branch = next((g for g, how, _ in where["day"] if how == "본기"), None)
    rel = []
    if day_branch:
        rel.append(G[day_branch]["relation"])
        ev["relation"].append(f"배우자 자리(태어난 날의 아래 글자)에 ‘{G[day_branch]['core']}’ 기운이 놓여 있습니다.")
    sp = _spouse(pil, gender, tot, where)
    if sp:
        rel.append(sp)
        ev["relation"].append(sp)
    sections.append({"key": "relation", "title": "관계에서의 모습", "text": " ".join(rel) if rel else "관계의 모습을 읽을 만한 뚜렷한 기운이 없습니다."})

    for s in sections:
        s["evidence"] = ev.get(s["key"], [])

    palaces = []
    for pos in ("year", "month", "day", "hour"):
        if not pil.get(pos):
            continue
        shown = [g for g, how, _ in where[pos] if how in ("드러남", "본기")]
        hidden = [g for g, how, _ in where[pos] if how == "숨음"]
        bits = []
        if shown:
            bits.append("겉으로는 " + "·".join(dict.fromkeys(G[g]["core"] for g in shown)) + " 기운")
        if hidden:
            bits.append("속에는 " + "·".join(dict.fromkeys(G[g]["core"] for g in hidden)) + " 기운이 숨어 있음")
        palaces.append({"palace": pos, "area": AREA[pos], "text": f"{AREA[pos]}: " + (", ".join(bits) if bits else "특별히 읽히는 기운이 없음")})
    summary = (f"한 줄로 말하면, ‘{' 그리고 '.join(G[g]['core'] for g in dom)}’ 쪽으로 힘이 모이는 사주로 읽힙니다." if dom
               else "한 줄로 요약할 만큼 한 가지 기운이 앞서지는 않습니다.")
    internal = {"version": SIPSUNG_VERSION, "weights": {g: tot[g] for g in tot}, "dominant": dom, "group_top": top_grp}
    return {"version": SIPSUNG_VERSION, "label": LABEL, "summary": summary, "dominant": [G[g]["core"] for g in dom], "sections": sections, "palaces": palaces, "internal": internal}


def _luck_theme(g: str) -> str:
    """10년 큰 흐름의 배경 문구: '…주제로 올라오는 해' → '…주제가 되는 시기'."""
    return G[g]["year"].replace("주제로 올라오는 해", "주제가 되는 시기")


def year_themes(pil: dict, P: dict, years: list[int]) -> list[dict]:
    """그해(세운)와 10년 큰 흐름(대운)의 천간이 이 사주의 일간에게 어떤 기운인지로 그해의 주제를 말한다.
    이미 많은 기운이면 '과해질 수 있음', 거의 없던 기운이면 '새롭게 느껴질 수 있음'으로 타고난 사주와 연결한다. 좋고 나쁨을 정하지 않는다."""
    if not pil or not pil.get("day"):
        return []
    from .facts import _days
    day = pil["day"][0]
    tot, _ = _weights(pil)
    grp = _group_totals(tot)
    out = []
    for y in years:
        p = P.get(y)
        if not p:
            continue
        seg = max(p["segments"], key=_days)
        yg, lg = ten_god(day, seg["sewun"][0]), ten_god(day, seg["luck"][0])
        w = grp[GROUP[yg]]
        if w >= 6:
            link = "타고난 사주에 이미 이 기운이 많아, 더해지면 한쪽으로 쏠리지 않게 살피는 것이 좋습니다."
        elif w <= 1:
            link = "타고난 사주에는 이 기운이 거의 없어서, 이 해에는 새롭고 낯설게 느껴질 수 있습니다."
        else:
            link = "타고난 사주의 기운과 이어지는 주제입니다."
        out.append({"year": y, "theme": f"{y}년은 {_luck_theme(yg)}로 읽습니다.", "link": link, "prep": G[yg]["prep"], "luck": f"이 시기 10년 큰 흐름의 배경은 {_luck_theme(lg)}입니다.",
                    "year_core": G[yg]["core"], "luck_core": G[lg]["core"], "_internal": {"year_god": yg, "luck_god": lg, "group_weight": w}})
    return out


def build(pre: dict, P: dict, years: list[int]) -> dict | None:
    pil = pre["natal_structure"].get("pillars") or {}
    pf = profile(pil, pre.get("gender"))
    if pf is None:
        return None
    ys = year_themes(pil, P, years[:10])
    pf["years"] = [{k: v for k, v in r.items() if k != "_internal"} for r in ys]
    pf["internal"]["years"] = [{"year": r["year"], **r["_internal"]} for r in ys]
    return pf
