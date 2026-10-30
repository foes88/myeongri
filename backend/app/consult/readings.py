"""분야별 5단 해석(의미 · 판단 근거 · 현실 연결 · 반대 근거 · 해석 범위). synthesis 가 고른 구조에 대해 설명 문장을 만든다.

- 판단 근거는 엔진의 지지 증거(supporting)를 위치·십성 뜻풀이로 옮긴 것이며, 증거에 없는 글자나 위치는 말하지 않는다.
- 현실 연결은 '살펴볼 수 있는 상황의 예'이며 특정 결과(승진·수입·계약)가 생긴다는 뜻이 아니다. 현대적 설명으로 표시한다.
"""
from __future__ import annotations

import re

from . import domains as D
from . import synthesis as S

GOD_PLAIN = {"比肩": "나와 같은 기운", "劫財": "나와 같은 기운", "食神": "표현·기술의 기운", "傷官": "표현·기술의 기운", "偏財": "재물·현실 자원의 기운", "正財": "재물·현실 자원의 기운",
             "七殺": "압박·경쟁의 기운", "正官": "직책·규율의 기운", "偏印": "배움·보호의 기운", "正印": "배움·보호의 기운"}
POS_PLAIN = {"연간": "태어난 해의 위쪽 글자", "월간": "태어난 달의 위쪽 글자", "시간": "태어난 시의 위쪽 글자", "연지 지장간": "태어난 해의 아래 글자 속", "월지 지장간": "태어난 달의 아래 글자 속",
             "일지 지장간": "태어난 날의 아래 글자 속(배우자 자리)", "시지 지장간": "태어난 시의 아래 글자 속", "대운간": "10년 단위 흐름의 위쪽 글자", "세운간": "그해의 위쪽 글자"}
EV_RE = re.compile(r"(연간|월간|시간|연지 지장간|월지 지장간|일지 지장간|시지 지장간)\s+(\S)\(([^)·]+)(?:·([^)]+))?\)")

# 구조 × 분야 군 → 현실에서 살펴볼 상황의 예. 결과를 단정하지 않는 '살펴볼 수 있는' 문장만 쓴다.
LENS = {
    "식상생재": {"wealth": "맡은 일이나 기술, 결과물이 수입으로 연결되는 방식(성과급, 부수입, 사업·프리랜서 수입 등)을 살펴볼 수 있습니다.",
             "business": "자신의 기술이나 아이디어를 상품·서비스로 만들어 수익으로 잇는 방식을 살펴볼 수 있습니다.",
             "career": "전문성이나 결과물이 평가와 보상으로 이어지는 경로를 살펴볼 수 있습니다.",
             "default": "자신의 능력이 현실의 이익으로 이어지는 경로를 살펴볼 수 있습니다."},
    "재생관": {"career": "쌓아 온 실적과 현실적 기반이 직책·평가·승진 논의와 맞물리는 방식을 살펴볼 수 있습니다.",
            "wealth": "수입의 기반이 안정된 자리나 직책으로 이어지는 경로를 살펴볼 수 있습니다.",
            "default": "현실적 기반이 지위나 평가로 이어지는 경로를 살펴볼 수 있습니다."},
    "관인상생": {"career": "조직 안에서 윗사람의 신뢰, 자격이나 학습, 문서(평가서·계약서·인사 서류)가 자리를 다지는 데 어떻게 작용하는지 살펴볼 수 있습니다.",
             "docs": "계약이나 문서 관련 일이 조직·제도의 틀 안에서 안정적으로 처리되는 방식을 살펴볼 수 있습니다.",
             "default": "제도와 조직 안에서 배움이나 후원이 자리를 지켜 주는 방식을 살펴볼 수 있습니다."},
    "살인상생": {"career": "강한 업무 압박이나 경쟁 상황을 공부·자격·조력자의 도움으로 풀어 가는 방식을 살펴볼 수 있습니다.",
             "default": "압박이나 경쟁을 준비와 도움으로 누그러뜨리는 방식을 살펴볼 수 있습니다."},
    "상관견관": {"career": "자기 주장이나 표현 방식이 조직의 규칙·상사와 부딪히는 상황에서 어떻게 조율할지 살펴볼 수 있습니다.",
             "default": "표현과 규칙이 부딪힐 때 조율하는 방식을 살펴볼 수 있습니다."},
    "군겁쟁재": {"wealth": "동료·동업자·경쟁자와 이익을 나누거나 비용이 새는 상황을 점검해 볼 수 있습니다.",
             "business": "동업이나 경쟁 관계에서 이익 배분이 어떻게 정해지는지 점검해 볼 수 있습니다.",
             "default": "비슷한 처지의 사람과 이익을 나누는 상황을 점검해 볼 수 있습니다."},
}
OUTCOME = {"wealth": "수입·재산", "career": "승진·평가·직무", "business": "사업 성과", "overall": "구체적인 사건", "docs_realestate": "계약·거래", "real_estate": "부동산 거래", "job_change": "이직·취업"}


def _lens_key(dom: str) -> str:
    return {"wealth": "wealth", "career": "career", "business": "business", "docs_realestate": "docs", "real_estate": "wealth", "job_change": "career"}.get(dom, "default")


def plain_evidence(supporting: list[str]) -> str:
    """엔진 지지 증거 문구('시간 丙(食神)', '→ 월지 지장간 戊(偏財·여기)')를 위치·뜻풀이 문장으로 옮긴다. 증거에 있는 것만 말한다."""
    src, dst = [], []
    for e in supporting:
        m = EV_RE.search(e)
        if not m:
            continue
        pos, ch, god, role = m.groups()
        if god not in GOD_PLAIN or pos not in POS_PLAIN:
            continue
        tail = "에 숨어 있는" if "지장간" in pos else "에 드러난"
        phrase = f"{POS_PLAIN[pos]}{tail} {GOD_PLAIN[god]}"
        (dst if e.strip().startswith("→") else src).append(phrase)
    src, dst = list(dict.fromkeys(src))[:1], list(dict.fromkeys(dst))[:1]
    if not src and not dst:
        return ""
    return " → ".join(src + dst)


def build_reading(pre: dict, dom: str, name: str, s: dict, year_note: str | None) -> dict:
    """한 구조에 대한 5단 해석. s 는 layer3 구조 항목."""
    st = S.STRUCT[name]
    status = S._rule_status(S.RULE_OF[name])
    tier = S.TIER[s["rank"]]
    pol = st["polarity"]
    why_e = plain_evidence(s.get("supporting", []))
    meaning = f"{st['theme']}이 {tier} 나타난다는 뜻입니다." if pol == "support" else f"{st['theme']}이 {tier} 보인다는 뜻입니다."
    why = (f"원국의 근거: {why_e}. 이 짜임을 바탕으로 {'읽습니다' if s['rank'] >= 2 else '조심스럽게 읽습니다'}." if why_e else "원국의 글자 배치에서 이 구조의 두 축이 모두 확인되어 읽습니다.")
    if s["rank"] == 1:
        why += " 다만 겉으로 드러나지 않고 속에 숨은 글자가 중심이라 힘이 크지 않다고 봅니다."
    lens = LENS[name].get(_lens_key(dom), LENS[name]["default"])
    counters = S._counters_plain(s, pol)[:2]
    out_name = OUTCOME.get(dom, "구체적인 사건")
    scope = f"원국의 글자 구조{'와 ' + year_note if year_note else ''}만 근거로 한 전통적 해석이며, {out_name}에 대한 실제 결과를 확정하지 않습니다."
    if status != "text_confirmed":
        scope += f" 이 풀이가 기대는 규칙은 '{S.STATUS_KO.get(status, status)}' 단계입니다."
    claim_ids = [s["claim_id"]]
    return {"domain": dom, "structure": name, "polarity": pol, "tier": s["rank"],
            "meaning": meaning, "why": why, "reality": lens, "counter": counters or ["이 구조에 대해 눈에 띄는 반대 견해는 확인되지 않았습니다."], "scope": scope,
            "claim_ids": claim_ids, "rule_status": status, "rule_status_ko": S.STATUS_KO.get(status, status), "basis": S.BASIS_MODERN}


def for_domains(pre: dict, blocks: list[dict], nm: dict, year_notes: dict[str, str]) -> list[dict]:
    """분야마다 중심 구조(돕는 쪽 1개)와, 있으면 부딪히는 구조 1개에 5단 해석을 붙인다. 구조가 없으면 만들지 않는다."""
    out = []
    for b in blocks:
        dom = b["domain"]
        if D.DOMAINS[dom].get("kind") == "palace":
            continue
        items = [(i["structure"], nm[i["structure"]]) for i in b["structures"] if nm[i["structure"]]["rank"] > 0]
        sup = sorted([x for x in items if S.STRUCT[x[0]]["polarity"] == "support"], key=lambda x: -x[1]["rank"])[:1]
        ten = sorted([x for x in items if S.STRUCT[x[0]]["polarity"] == "tension"], key=lambda x: -x[1]["rank"])[:1]
        for n, s in sup + ten:
            r = build_reading(pre, dom, n, s, year_notes.get(n))
            r["name"] = b["name"]
            out.append(r)
    seen, final = set(), []
    for r in sorted(out, key=lambda x: x["domain"] == "overall"):  # 구체 분야에서 이미 설명한 구조는 종합운에서 되풀이하지 않는다
        if r["structure"] in seen and r["domain"] == "overall":
            continue
        seen.add(r["structure"])
        final.append(r)
    order = {id(r): i for i, r in enumerate(out)}
    return sorted(final, key=lambda r: order[id(r)])


def block_evidence(pre: dict, blocks: list[dict], nm: dict) -> list[dict]:
    """분야별 '긍정 근거 / 주의 근거'를 용어 없이 쉬운 말로. 엔진 원문(근거 번호·한자·용어)은 화면에서 '전문가용 근거'로 따로 접어 둔다.
    구조 이름 대신 '무엇이 어떻게 이어지는 흐름인가'로 부르고, 증거에 있는 위치·기운만 말한다."""
    from . import compose_domains as CD
    out = []
    for b in blocks:
        dom = b["domain"]
        pos, neg, cids = [], [], []
        cnt_pos: dict[str, list[str]] = {}  # 같은 반대 견해는 한 번만 쓰고 해당하는 흐름을 함께 적는다
        cnt_neg: dict[str, list[str]] = {}
        if D.DOMAINS[dom].get("kind") == "palace":
            ex = CD.domain_extra(dom, pre) or {"evidence_for": [], "evidence_against": [], "claim_ids": []}
            pos = [_plain(x) for x in ex["evidence_for"]]
            neg = [_plain(x) for x in ex["evidence_against"]]
            cids = list(ex["claim_ids"])
        else:
            for i in b["structures"]:
                s = nm[i["structure"]]
                if not s["rank"]:
                    continue
                st = S.STRUCT[i["structure"]]
                why = plain_evidence(s.get("supporting", []))
                head = st["short"] + f"({S.TIER[s['rank']]} 나타남)"
                (pos if st["polarity"] == "support" else neg).append(head + (": " + why if why else ""))
                for c in S._counters_plain(s, st["polarity"]):
                    (cnt_neg if st["polarity"] == "support" else cnt_pos).setdefault(c, []).append(st["short"])
                cids.append(s["claim_id"])
        fmt = lambda m: [f"{c}. (해당: {', '.join(v[:2])}{' 등' if len(v) > 2 else ''})" for c, v in m.items()]
        pos, neg = pos + fmt(cnt_pos), neg + fmt(cnt_neg)
        out.append({"domain": dom, "name": b["name"], "positive": list(dict.fromkeys(pos)), "negative": list(dict.fromkeys(neg)), "claim_ids": list(dict.fromkeys(cids)),
                    "basis": S.BASIS_MODERN})
    return out


# ------------------------------------------------------------------ 궁위·십성 신호 분야(연애·가족·건강·이직·부동산)
PLAIN_FIRST = [("연주(조상·초년궁)", "태어난 해의 자리(조상·어린 시절)"), ("월주(부모·사회·직업궁)", "태어난 달의 자리(부모·사회·직업)"), ("시주(자녀·말년궁)", "태어난 시의 자리(자녀·말년)"),
               ("일주(자신·배우자궁)", "태어난 날의 자리(자기 자신·배우자)"), ("일주가", "태어난 날의 자리가"), ("직업궁(월주)", "직업 자리(태어난 달의 자리)"), ("직업궁", "직업 자리"),
               ("배우자궁", "배우자 자리"), ("일지(태어난 날의 지지)", "태어난 날의 아래 글자"), ("일지", "태어난 날의 아래 글자"), ("창고 지지", "재물을 저장하는 역할의 글자"),
               ("천간·지지 본기 오행 집계(사실): ", "오행 분포: "), ("타고난 사주 천간·지지에 보이지 않음", "타고난 사주 어디에도 보이지 않음"), ("천간·지지", "위·아래 글자"), ("천간합", "위쪽 글자끼리 묶이는 합"), ("육합", "아래 글자끼리 묶이는 합"), ("삼합 완성 후보", "세 글자가 모이는 합"), ("삼합(완전)", "세 글자가 모이는 합"), ("월지 계절 방향", "태어난 달의 계절 방향"), ("본기", "중심 글자"), ("월주", "태어난 달의 자리"), ("연주", "태어난 해의 자리"), ("시주", "태어난 시의 자리"), ("일주", "태어난 날의 자리"), ("원국에서", "타고난 사주에서"), ("원국에", "타고난 사주에"), ("원국", "타고난 사주")]
ELEMENT_KO = {"木": "목", "火": "화", "土": "토", "金": "금", "水": "수"}
PLAIN_SUBS = [("배우자성(관성)", "배우자를 뜻하는 직책·규율의 기운"), ("배우자성(재성)", "배우자를 뜻하는 재물·현실 자원의 기운"), ("배우자성", "배우자를 뜻하는 기운"), ("자녀성", "자녀를 뜻하는 기운"),
              ("관성", "직책·규율의 기운"), ("인성", "배움·보호의 기운"), ("비겁", "나와 같은 기운"), ("식상", "표현·기술의 기운"), ("재성", "재물·현실 자원의 기운"),
              ("지지 암장", "아래 글자 속에 숨은 것"), ("천간 노출", "겉으로 드러난 것"), ("십성군", "기운"), ("개고·입묘 후보", "창고가 열리고 닫히는 관계"),
              ("관계 후보에 있음(존재만 확인, 관계의 질은 확정하지 않음)", "관계에 놓여 있음(있다는 사실만 확인한 것)"), ("관계 후보에 있음(존재만 확인)", "관계에 놓여 있음(있다는 사실만 확인한 것)"),
              ("관계 후보에 관여", "관계에 얽혀 있음"), ("무례지형(子卯)", "마찰이 생기는 형"), ("형(부분)", "마찰이 생기는 형"), ("반합", "서로 끌어당기는 합"), ("충 관계", "부딪히는 관계")]
PALACE = {
    "love_marriage": {"meaning": "배우자 자리(태어난 날의 아래 글자)와 배우자를 뜻하는 기운이 어떻게 놓였는지로 관계를 맺는 방식과 조건을 살펴봅니다.",
                      "reality": "관계를 맺을 때 중요하게 여기는 조건, 갈등이 생겼을 때의 조율 방식, 가까운 사람과의 거리감을 돌아보는 데 참고할 수 있습니다."},
    "family": {"meaning": "태어난 해·달·시의 자리와 윗사람·형제·자녀를 뜻하는 기운으로 가까운 사람들과의 관계 틀을 살펴봅니다.",
               "reality": "부모·형제·동료·자녀와의 거리, 도움을 주고받는 방식, 부딪히기 쉬운 지점을 점검하는 데 참고할 수 있습니다."},
    "job_change": {"meaning": "직업 자리(태어난 달의 자리)와 직책·배움의 기운, 운에서 그 자리에 닿는 관계를 함께 살펴봅니다.",
                   "reality": "자리를 옮길 때 조직이 요구하는 역할, 준비해 둔 자격·경력이 맞물리는 방식, 환경 변화에 대한 부담을 점검하는 데 참고할 수 있습니다."},
    "real_estate": {"meaning": "재물을 뜻하는 기운, 문서·거처를 뜻하는 기운, 재물을 저장하는 역할의 글자(진·술·축·미)의 상태로 부동산과 거처에 대한 틀을 살펴봅니다.",
                    "reality": "거래·계약 서류를 챙기는 방식, 자산을 묶어 두는 성향, 이사나 거처 변화에 대한 준비를 점검하는 데 참고할 수 있습니다."},
    "health_traditional": {"meaning": "오행의 쏠림과 계절의 한난 균형을 '균형의 상징'으로만 살펴봅니다. 몸의 상태를 판단하는 해석이 아닙니다.",
                           "reality": "생활 리듬과 휴식의 균형을 돌아보는 일상적 참고로만 쓸 수 있으며, 몸 상태를 판단하는 용도로는 쓸 수 없습니다."},
}
COUNT_CLAIM = "L1-SUP-001"


def _plain(t: str) -> str:
    t = re.sub(r"배우자궁 일지 '[\u4e00-\u9fff]'의 본기 '[\u4e00-\u9fff]'\(([\u4e00-\u9fff]{2})\)", lambda m: "배우자 자리(태어난 날의 아래 글자) 속 중심 기운은 " + GOD_PLAIN.get(m.group(1), "어떤 기운"), t)
    t = re.sub(r"\([\u4e00-\u9fff·]+\)", "", t)  # 괄호 속 한자 표기(예: 辰戌丑未)는 쉬운 설명에서 뺀다
    for a, b in PLAIN_FIRST:
        t = t.replace(a, b)
    t = re.sub(r"([木火土金水])", lambda m: ELEMENT_KO[m.group(1)], t)
    t = re.sub(r"\s*\[[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{3}\](?:\s*\([^)]*\))?", "", t)
    for a, b in PLAIN_SUBS:
        t = t.replace(a, b)
    t = re.sub(r"'([一-鿿])'\(([一-鿿]{2})\)", lambda m: GOD_PLAIN.get(m.group(2), m.group(0)), t)
    t = re.sub(r"일지 '[一-鿿]'의 본기", "일지(태어난 날의 지지) 속 중심 기운은", t)
    t = re.sub(r"'[一-鿿]'", "", t)  # 남은 한자 글자(지지·천간) 표기는 쉬운 설명에서 뺀다
    return t.replace("관계 관계", "관계").strip()


def palace_readings(pre: dict, blocks: list[dict]) -> list[dict]:
    from . import compose_domains as CD
    out = []
    for b in blocks:
        dom = b["domain"]
        if dom not in PALACE:
            continue
        ex = CD.domain_extra(dom, pre)
        if not ex:
            continue
        status = "implementer_convention"
        why = [_plain(x) for x in ex["evidence_for"]][:3]
        counter = [_plain(x) for x in ex["evidence_against"]][:3]
        scope = "원국의 글자 배치만 근거로 한 전통적 해석이며, 결과나 사건을 확정하지 않습니다. 이 분야의 판단 기준은 구현자 규약(고전 원문 대조 전) 단계입니다."
        if dom == "health_traditional":
            scope = CD.HEALTH_NOTICE + " " + scope
        cids = list(dict.fromkeys(ex["claim_ids"] + [COUNT_CLAIM]))
        out.append({"domain": dom, "name": b["name"], "structure": b["name"], "polarity": "support", "tier": 2, "meaning": PALACE[dom]["meaning"],
                    "why": "원국의 근거: " + (" / ".join(why) if why else "이 분야와 직접 이어지는 뚜렷한 근거가 확인되지 않았습니다."),
                    "reality": PALACE[dom]["reality"], "counter": counter or ["눈에 띄는 반대 근거는 확인되지 않았습니다."], "scope": scope,
                    "claim_ids": cids, "rule_status": status, "rule_status_ko": S.STATUS_KO[status], "basis": S.BASIS_MODERN, "thin": not why})
    return out


def natural(line: str) -> str:
    """_plain 을 거친 근거 한 줄을 사용자가 읽는 문장으로 다듬는다(개수 나열 → 서술). 증거에 없는 내용은 더하지 않는다."""
    t = _plain(line).strip()
    m = re.match(r"^(.*): 겉으로 드러난 것 (\d+)개, 아래 글자 속에 숨은 것 (\d+)개(.*)$", t)
    if m:
        subj, a, b = m.group(1), int(m.group(2)), int(m.group(3))
        if a and b:
            return f"{subj}이 겉으로도 속에도 있습니다."
        if a:
            return f"{subj}이 겉으로 드러나 있습니다."
        if b:
            return f"{subj}이 겉으로는 드러나지 않고 속에 숨어 있습니다."
        return f"{subj}이 보이지 않습니다."
    m = re.match(r"^오행 분포: (.*)$", t)
    if m:
        return "오행의 분포는 " + re.sub(r"(\S)(\d)", r"\1 \2", m.group(1)) + "입니다."
    m = re.match(r"^집계에 나타나지 않은 오행: (\S+)", t)
    if m:
        el = m.group(1)
        return f"오행 중 {el}{'은' if el in ('목', '금') else '는'} 집계에 나타나지 않았지만, 이는 부족이나 결함을 뜻하지 않습니다."
    m = re.match(r"^태어난 달의 계절 방향: (.*)$", t)
    if m:
        return f"태어난 달의 계절은 {m.group(1)}입니다."
    t = t.replace("에 놓여 있음(있다는 사실만 확인한 것)", "에 놓여 있습니다(있다는 사실만 확인한 것이며 결과를 뜻하지 않습니다)")
    t = re.sub(r"(얽혀 있|놓여 있|있|없|않)음$", r"\1습니다", t)
    if t.endswith("기운"):
        t += "입니다"
    return t if t.endswith(("다.", "요.")) else (t + "." if not t.endswith((".", ")")) else t)
