"""후속 질문 응답(외부 LLM 없음). 자연어 질문을 몇 가지 의도로 나눠, 이미 계산된 결론형 데이터(verdict)로만 답한다.

지원: ① 조언형("좋다는 거야?", "해도 돼?") ② 연도 비교("2028년과 비교하면?") ③ 뜻 풀이("…는 무슨 뜻이야?", 우리가 쓴 표현 한정) ④ 이유("왜?") ⑤ 더 자세히.
범위 밖 질문에는 임의로 답하지 않고 지원 범위를 안내한다. 원시 규칙 목록은 돌려주지 않는다. 사건·결과를 단정하지 않는다.
"""
from __future__ import annotations

import re

from . import domains as D
from . import verdict as V

SUPPORTED = ["“2030년에 이직하는 게 좋다는 거야?” 처럼 선택에 대한 해석", "“2028년과 2030년 중 어느 쪽이 나아?” 처럼 두 해 비교", "“그 말이 무슨 뜻이야?” 처럼 결과에 나온 표현의 뜻",
             "“왜 그렇게 읽어?” 처럼 이유", "“재물운을 더 자세히 알려 줘” 처럼 분야·연도 자세히"]
ADVICE = re.compile(r"좋다는|좋을까|좋겠|해도 (돼|될까|되나)|하는 게 (좋|나)|해야 (해|할까|하나)|괜찮|추천|권해|말아야|하면 (안|될)|해볼까|할까\??")
COMPARE = re.compile(r"비교|어느 (쪽|해)|더 (나아|좋|유리|낫)|vs|보다")
WHY = re.compile(r"왜|이유|근거|어떻게 (그렇게|알)")
MEANING = re.compile(r"무슨 (뜻|말)|뜻이|의미|무슨 소리|어떤 의미")
DETAIL = re.compile(r"자세히|더 알려|풀어|구체적으로|설명해")

# 우리가 결과에 쓴 표현의 뜻(표현 → (키워드, 설명 생성에 필요한 구조 힌트))
PHRASES = [
    (re.compile(r"남지 않|새어|새는|나가|나누"), "wealth", "tension_share"),
    (re.compile(r"부딪|마찰|규칙"), "career", "tension_clash"),
    (re.compile(r"조율"), None, "coordinate"),
    (re.compile(r"점검"), None, "check"),
    (re.compile(r"기회"), None, "chance"),
    (re.compile(r"큰 흐름|10년 단위|바뀌"), None, "bigflow"),
    (re.compile(r"읽힙|해석|어떻게 읽"), None, "reading"),
    (re.compile(r"잔잔|변화 없|달라지지"), None, "quiet"),
]


def _scope_text() -> str:
    return "이 상담은 사주로 읽은 결과 안에서만 답할 수 있습니다. 이런 질문에 답해 드릴 수 있어요: " + " / ".join(SUPPORTED)


def _pick_block(v: dict, year: int | None, dom: str | None) -> dict | None:
    if v["mode"] == "multi":
        y = str(year) if year is not None else str(v["years"][0])
        blocks = v["detail"].get(y, {}).get("blocks", [])
    else:
        blocks = v.get("blocks", [])
    if dom:
        b = next((x for x in blocks if x["domain"] == dom), None)
        if b:
            return b
    return next((x for x in blocks if x["domain"] != "overall"), blocks[0] if blocks else None)


def _best_domain(v: dict, question: str, doms: list[str]) -> str | None:
    q_doms = D.route(question, None)
    q_doms = [d for d in q_doms if d not in ("luck",)]
    if q_doms and not (q_doms == ["overall"] and any(d != "overall" for d in doms)):
        return q_doms[0] if q_doms[0] != "overall" else None
    sel = [d for d in doms if d not in ("overall", "luck")]
    return sel[0] if sel else None


def answer_question(pre: dict, v: dict, question: str, doms: list[str], years: list[int]) -> dict:
    q = (question or "").strip()
    qy = D.extract_years(q)
    dom = _best_domain(v, q, doms)
    name = D.DOMAINS[dom]["name"] if dom else "전반적인 흐름"
    base = {"question": q}
    if not q or q == "종합 상담을 시작합니다":
        return {**base, "kind": "none", "text": "", "points": []}
    if MEANING.search(q):
        for rx, dd, key in PHRASES:
            if rx.search(q):
                return {**base, "kind": "meaning", **_meaning(pre, v, key, dom or dd)}
    cand = sorted(set(qy) if len(qy) >= 2 else (set(qy) | set(years)))
    if COMPARE.search(q) and len(cand) >= 2:
        ys = cand[:2] if len(qy) < 2 else qy[:2]
        return {**base, "kind": "compare", **_compare(v, ys, dom, name)}
    if ADVICE.search(q):
        y = qy[0] if qy else (years[0] if years else None)
        return {**base, "kind": "advice", **_advice(v, y, dom, name, q)}
    if WHY.search(q):
        return {**base, "kind": "why", **_why(v, dom, name)}
    q_dom = [d for d in D.route(q, None) if d not in ("overall", "luck")]  # 분야만 언급한 질문은 그 분야의 풀이로 답한다
    if DETAIL.search(q) or q_dom or (qy and not MEANING.search(q)):
        y = qy[0] if qy else (years[0] if years else None)
        b = _pick_block(v, y, dom)
        if not b:
            return {**base, "kind": "unsupported", "text": _scope_text(), "points": []}
        return {**base, "kind": "detail", "year": y, "domain": b["domain"], "text": f"{b['name']}({V.when_phrase([y] if y else [])})을 자세히 풀면 다음과 같습니다.", "points": b["story"] + b["think"]}
    return {**base, "kind": "unsupported", "text": _scope_text(), "points": []}


def _advice(v: dict, y: int | None, dom: str | None, name: str, q: str) -> dict:
    b = _pick_block(v, y, dom)
    if not b:
        return {"text": _scope_text(), "points": []}
    w = V.when_phrase([y] if y else [])
    lead = "사주 해석만으로 ‘하는 게 좋다’ 또는 ‘하지 않는 게 좋다’고 말씀드릴 수는 없습니다."
    if b["tone"] == "thin":
        return {"year": y, "domain": b["domain"], "text": lead + f" 이 사주에서는 {w} {name}에 대해 말할 수 있는 근거도 부족합니다. 현실의 조건(제안 내용, 자금, 시기)을 기준으로 판단해 주세요.", "points": []}
    return {"year": y, "domain": b["domain"],
            "text": lead + f" 다만 {w} {name}은 ‘{b['tone_label']}’으로 읽힙니다. " + b["headline"].split(". ")[0].rstrip(".") + ".",
            "points": b["think"] + ["최종 결정은 현실 조건을 기준으로 해 주세요. 이 해석은 결과를 보장하지 않습니다."]}


def _compare(v: dict, ys: list[int], dom: str | None, name: str) -> dict:
    ba, bb = _pick_block(v, ys[0], dom), _pick_block(v, ys[1], dom)
    if not ba or not bb or v["mode"] == "none":
        return {"text": "비교하려면 두 해가 모두 분석 범위에 있어야 합니다. 연도를 바꿔 다시 분석해 주세요.", "points": []}
    da, db_ = ba["scores"]["S"] - ba["scores"]["T"], bb["scores"]["S"] - bb["scores"]["T"]
    la, lb = f"{ys[0]}년은 ‘{ba['tone_label']}’", f"{ys[1]}년은 ‘{bb['tone_label']}’"
    if ba["tone"] == "thin" or bb["tone"] == "thin":
        text = f"{name} 기준으로 {la}, {lb}입니다. 한쪽 이상은 말할 근거가 부족해 비교하기 어렵습니다."
    elif abs(da - db_) <= 1 and ba["tone"] == bb["tone"]:
        text = f"{name} 기준으로 {la}, {lb}으로 읽혀 두 해의 구조 차이가 크지 않습니다. 어느 쪽이 낫다고 말하기 어렵습니다."
    else:
        better, worse = (ys[0], ys[1]) if da > db_ else (ys[1], ys[0])
        text = f"{name} 기준으로 {la}, {lb}으로 읽힙니다. 해석상으로는 {better}년 쪽이 기회가 더 두드러지고 {worse}년은 점검할 부분이 상대적으로 큽니다. 다만 좋고 나쁨의 우열이 아니라 시기의 성격 차이로 봐 주세요."
    same = ba["headline"].replace(str(ys[0]), "#") == bb["headline"].replace(str(ys[1]), "#")
    return {"years": ys, "domain": dom, "text": text, "points": [] if same else [f"{ys[0]}년: " + ba["headline"], f"{ys[1]}년: " + bb["headline"]]}


def _why(v: dict, dom: str | None, name: str) -> dict:
    r = (v.get("reasons") or {}).get(dom or "overall") or next(iter((v.get("reasons") or {}).values()), None)
    if not r:
        return {"text": "이 결론에 쓴 이유를 쉬운 말로 정리할 수 있는 항목이 없습니다.", "points": []}
    return {"domain": dom, "text": f"{name}을 이렇게 읽은 이유를 쉬운 말로 정리했습니다.", "points": (["뒷받침하는 이유"] + r["positive"][:3] + ["주의하거나 반대로 보는 이유"] + r["negative"][:3])}


def _meaning(pre: dict, v: dict, key: str, dom: str | None) -> dict:
    nm = {s["name"]: s for s in pre["natal_structure"]["layer3"]["structures"]}
    if key == "tension_share":
        has = nm.get("군겁쟁재", {}).get("rank", 0) > 0 or any(b.get("tone") in ("mixed", "cautious") and b["domain"] in ("wealth", "business") for b in _all_blocks(v))
        if not has:
            return {"text": "이 사주에서는 ‘수입이 남지 않는다’는 쪽의 해석이 뚜렷하게 나오지 않았습니다.", "points": ["재물 흐름은 현실의 지출·계약 조건이 더 큰 기준입니다."]}
        return {"text": "수입이 생겨도 동료·동업자·주변 사람과 나누거나 비용으로 나가기 쉬운 흐름이 커진다고 읽는 해석입니다. 실제로 돈이 남지 않는다는 뜻은 아닙니다.",
                "points": ["수입을 늘리는 일과 함께 고정 지출, 동업·보증 같은 나누는 구조를 점검해 보라는 관점입니다.", "이 부분은 이 사주에서 ‘약하게’ 또는 ‘어느 정도’로만 나타나는 흐름이며 확정이 아닙니다."]}
    texts = {
        "tension_clash": ("자기 주장이나 방식이 조직의 규칙·상사와 부딪히기 쉬운 흐름이 커진다고 읽는 해석입니다. 갈등이 생긴다는 뜻이 아니라 조율에 신경 쓰라는 신호로 봅니다.", ["의견을 전달하는 시기와 방식을 고르는 관점이 도움이 될 수 있습니다."]),
        "coordinate": ("‘조율’은 서로 다른 요구(수입과 지출, 성과와 관계 등)를 한쪽으로 몰지 않고 맞춰 가는 것을 뜻합니다.", []),
        "check": ("‘점검’은 좋은 흐름 속에서도 새어 나가거나 부딪힐 수 있는 부분을 미리 살펴보라는 뜻입니다. 나쁜 일이 생긴다는 뜻이 아닙니다.", []),
        "chance": ("‘기회’는 돕는 흐름이 타고난 모습보다 커진다고 읽는다는 뜻입니다. 실제 기회가 생긴다는 보장은 아닙니다.", []),
        "bigflow": ("사주에는 10년 단위로 바뀌는 큰 흐름이 있어, 그 기준이 바뀌는 날짜 전후로 분위기가 달라질 수 있다고 봅니다. 그래서 그 전과 후를 나누어 읽습니다.", []),
        "reading": ("‘읽힙니다’는 사주의 구조와 시기 변화를 전통 해석 틀로 읽으면 그렇게 해석된다는 뜻이며, 실제 결과를 말하는 것이 아닙니다.", []),
        "quiet": ("‘큰 변화 없이 이어지는 흐름’은 그 시기에 타고난 모습에서 구조가 크게 달라지지 않는다는 뜻입니다. 좋거나 나쁘다는 뜻이 아닙니다.", []),
    }
    t, pts = texts.get(key, ("이 표현에 대해 더 설명할 수 있는 내용이 없습니다.", []))
    return {"text": t, "points": pts}


def _all_blocks(v: dict) -> list[dict]:
    if v["mode"] == "multi":
        return [b for d in v["detail"].values() for b in d["blocks"]]
    return v.get("blocks", [])
