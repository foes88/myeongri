"""해석 종합 계층(InterpretationSynthesis). 구조 분석 결과를 '나열'이 아니라 '선택·종합'해 일반인이 읽을 수 있는 문장으로 만든다.

원칙
- 엔진이 만든 구조·관계·구조 변화(structure_delta)에 있는 것만 문장이 된다. 없는 관계·사건은 만들지 않는다.
- 모든 문장은 claim_ids 와 근거 구분(basis)을 가진다. 쉬운말 풀이는 항상 '현대적 설명'이고, 규칙의 고전 확인 상태는 rule_status 로 따로 둔다.
- 근거가 부족하면 그럴듯한 문장으로 채우지 않고 '근거 부족'을 그대로 말한다.
- 같은 문장을 반복하지 않는다(원국 설명은 한 번, 해마다는 변화분만).
"""
from __future__ import annotations

import re

from . import domains as D

SYNTH_VERSION = "synthesis-0.1.0"
BASIS_MODERN = "modern_explanation"
BASIS_ENGINE = "engine_fact"

# 구조 → 쉬운말 풀이(현대적 설명). polarity: support(돕는 흐름) / tension(부딪히거나 나누는 흐름)
STRUCT = {
    "식상생재": {"polarity": "support", "theme": "자신의 능력이나 결과물을 수입과 연결하는 흐름", "short": "능력이 수입으로 이어지는 흐름"},
    "재생관": {"polarity": "support", "theme": "벌어 둔 기반이 직책이나 평가로 이어지는 흐름", "short": "기반이 지위·평가로 이어지는 흐름"},
    "관인상생": {"polarity": "support", "theme": "조직 안에서 배움이나 문서, 윗사람의 도움을 받아 자리를 다지는 흐름", "short": "조직 안에서 도움을 받아 자리를 다지는 흐름"},
    "살인상생": {"polarity": "support", "theme": "강한 압박이나 경쟁을 공부와 준비, 조력으로 누그러뜨리며 버티는 흐름", "short": "압박을 준비와 조력으로 풀어 가는 흐름"},
    "상관견관": {"polarity": "tension", "theme": "자기 주장과 표현이 조직이나 규칙과 부딪히기 쉬운 흐름", "short": "표현과 규칙이 부딪히기 쉬운 흐름"},
    "군겁쟁재": {"polarity": "tension", "theme": "비슷한 처지의 사람과 이익을 나누거나 다투기 쉬운 흐름", "short": "이익을 나누거나 다투기 쉬운 흐름"},
}
RULE_OF = {"식상생재": "MG-L3-SIKSANG-SAENGJAE", "재생관": "MG-L3-JAE-SAENGGWAN", "관인상생": "MG-L3-GWAN-INSAENG", "살인상생": "MG-L3-SAL-INSAENG",
           "상관견관": "MG-L3-SANGGWAN-GYEONGWAN", "군겁쟁재": "MG-L3-GUNGEOP-JAENGJAE"}
TIER = {0: "없음", 1: "약하게", 2: "어느 정도", 3: "뚜렷하게"}
STATUS_KO = {"text_confirmed": "고전 원문 확인(표시한 범위)", "location_confirmed": "고전 원문 위치만 확인", "implementer_convention": "현대적 설명·구현자 규약", "pending": "고전 대조 전"}

# 원국 구조의 반대 근거(엔진 문구) → 쉬운 문장. (패턴, 문장, 대상 polarity)
SUPPORT_COUNTER = [
    (r"편인도식", "생각이 많아 표현과 실행이 더뎌질 수 있다고 보는 견해가 있습니다"),
    (r"비겁이 재를 다툼|탈재|군겁쟁재", "비슷한 처지의 사람과 이익을 나눌 수 있다고 보는 견해가 있습니다"),
    (r"충 관계", "관련된 자리가 서로 부딪히는 관계여서 안정적으로 이어지기 어렵다고 보는 견해가 있습니다"),
    (r"형\(부분\)|형 관계|삼형|자형", "관련된 자리 사이에 마찰이 있어 순탄하지 않을 수 있다고 보는 견해가 있습니다"),
    (r"재극인", "재물에 대한 관심이 배움이나 문서의 도움을 줄일 수 있다고 보는 견해가 있습니다"),
    (r"식상극관", "표현과 주장이 강해 조직의 도움을 해칠 수 있다고 보는 견해가 있습니다"),
    (r"재자약살", "현실 문제가 압박을 키울 수 있다고 보는 견해가 있습니다"),
    (r"상관이 있어 관을 해친다", "자기 주장이 직책의 흐름을 해칠 수 있다고 보는 견해가 있습니다"),
    (r"암장", "겉으로 뚜렷하게 드러나지 않고 속에 있어 힘이 약하다고 보는 견해가 있습니다"),
]
TENSION_RELIEF = [
    (r"제겁", "직책·규율의 기운이 있어 다툼을 눌러 조절한다고 보는 견해가 있습니다"),
    (r"화겁생재", "표현·기술의 기운이 있어 경쟁의 기운을 수입으로 돌린다고 보는 견해가 있습니다"),
    (r"상관패인", "배움·보호의 기운이 있어 거친 표현을 다듬어 준다고 보는 견해가 있습니다"),
    (r"상관생재", "재물·현실 자원의 기운이 있어 표현의 기운을 재물로 풀어 준다고 보는 견해가 있습니다"),
    (r"억부론 견해", "나 자신이 약한 편이면 같은 기운이 오히려 도움이 된다고 보는 견해가 있습니다"),
    (r"군겁.{0,6}부르기 어렵", "다툼으로 볼 만큼 같은 기운이 많지 않다고 보는 견해가 있습니다"),
]

REL_PHRASE = "원국과 부딪히거나 흐트러지는"
REL_PLAIN = {"충": "부딪히는", "형(부분)": "마찰이 생기는", "삼형": "마찰이 생기는", "무례지형(子卯)": "마찰이 생기는", "자형": "마찰이 생기는",
             "파": "흐트러지는", "해": "서로 해치는 쪽으로 보는"}


def _md(d: str) -> str:
    return f"{int(d[5:7])}월 {int(d[8:10])}일"
CHANGE_UP = ("강화", "신규 출현")
CHANGE_DOWN = ("약화", "소멸")


def _rank(label: str) -> int:
    for k, t in (("뚜렷", 3), ("보통", 2), ("약함", 1)):
        if label.startswith(k):
            return t
    return 0


def _sent(text: str, claim_ids: list[str], basis: str = BASIS_MODERN, rule_status: str | None = None, kind: str = "reading") -> dict:
    s = {"text": text, "claim_ids": [c for c in dict.fromkeys(claim_ids) if c], "basis": basis, "kind": kind}
    if rule_status:
        s["rule_status"] = rule_status
        s["rule_status_ko"] = STATUS_KO.get(rule_status, rule_status)
    return s


def _rule_status(rule_id: str) -> str:
    from ..mingli.rules import RULES
    return RULES[rule_id]["classical_status"]


def _natal_map(base: dict) -> dict[str, dict]:
    return {s["name"]: s for s in base["layer3"]["structures"]}


def _relevant(doms: list[str]) -> list[str]:
    seen: list[str] = []
    for d in doms:
        for s in D.DOMAINS.get(d, {}).get("structures", []):
            if s not in seen:
                seen.append(s)
    return seen or list(STRUCT)


def _counters_plain(s: dict, pol: str) -> list[str]:
    table = SUPPORT_COUNTER if pol == "support" else TENSION_RELIEF
    out: list[str] = []
    for c in s.get("counter", []):
        for pat, sent in table:
            if re.search(pat, c):
                if sent not in out:
                    out.append(sent)
                break
    return out


def _join_themes(names: list[str], key: str = "theme") -> str:
    return "과 ".join(STRUCT[n][key] for n in names[:2]) if len(names) <= 2 else ", ".join(STRUCT[n][key] for n in names[:3])


def _delta_for(seg: dict, rel: list[str]) -> list[dict]:
    return [d for d in seg.get("delta", []) if d["structure"] in rel]


def _bad_relations(seg: dict) -> list[dict]:
    return [r for r in seg.get("relations", []) if r["type"] in REL_PLAIN]


# ------------------------------------------------------------------ 원국
def natal_reading(pre: dict, doms: list[str]) -> dict:
    """원국에서 선택 분야와 관련된 중심 흐름·돕는 조건·제한 조건. 약하면 약하다고, 없으면 없다고 말한다."""
    base = pre["natal_structure"]
    nm = _natal_map(base)
    rel = _relevant(doms)
    present = [(n, nm[n]) for n in rel if n in nm and nm[n]["rank"] > 0]
    sup = sorted([(n, s) for n, s in present if STRUCT[n]["polarity"] == "support"], key=lambda x: -x[1]["rank"])
    ten = sorted([(n, s) for n, s in present if STRUCT[n]["polarity"] == "tension"], key=lambda x: -x[1]["rank"])
    favorable, cautions = [], []
    for n, st_ in sup[:3]:
        favorable.append(_sent(f"원국에는 {STRUCT[n]['theme']}이 {TIER[st_['rank']]} 보입니다.", [st_["claim_id"]], rule_status=_rule_status(RULE_OF[n])))
    for n, st_ in ten[:1]:
        cautions.append(_sent(f"한편 {STRUCT[n]['theme']}도 {TIER[st_['rank']]} 있어, 이 부분은 조심해서 살펴볼 필요가 있습니다.", [st_["claim_id"]], rule_status=_rule_status(RULE_OF[n])))
        rl = _counters_plain(st_, "tension")[:1]
        if rl:
            cautions.append(_sent(f"다만 {rl[0]}.", [st_["claim_id"]], rule_status=_rule_status(RULE_OF[n]), kind="relief"))
    by_counter: dict[str, list[tuple[str, str]]] = {}
    for n, st_ in sup[:3]:
        for r in _counters_plain(st_, "support")[:2]:
            by_counter.setdefault(r, []).append((n, st_["claim_id"]))
    for r, items in list(by_counter.items())[:2]:
        names = [n for n, _ in items]
        cautions.append(_sent(f"'{STRUCT[names[0]]['short']}'{' 등' if len(names) > 1 else ''}에 대해서는 {r}.", [c for _, c in items], rule_status=_rule_status(RULE_OF[names[0]]), kind="counter"))
    # 월령·격국(있는 경우만)
    l1, l4 = base["layer1"], base["layer4"]
    gk = l4["gyeokguk"]
    wol = []
    if gk.get("tugan_priority"):
        sp = l4["seongpa"].get(gk["tugan_priority"], {})
        wol.append(_sent(f"태어난 달의 기운으로 보면 '{gk['tugan_priority']}'의 틀로 읽어 볼 수 있으며, 그 틀이 이루어졌는지는 {sp.get('status', '판단 보류')} 정도로만 볼 수 있습니다.",
                         list(gk.get("claims", [])) + ([sp["claim_id"]] if sp.get("claim_id") else []), rule_status=_rule_status("MG-L4-SEONGPA")))
    de = l1["deukryeong"]
    if not de["agree"]:
        wol.append(_sent("태어난 달이 일간을 얼마나 돕는지는 기준에 따라 평가가 갈려, 강하다 약하다를 한쪽으로 단정하지 않습니다.", list(de["claims"]), BASIS_ENGINE, kind="limit"))
    conflict = [c for c in l4["yongshin"].get("conflicts", [])]
    if conflict:
        cautions.append(_sent("학파마다 필요한 기운을 다르게 보는 부분이 있어, 하나의 처방으로 합치지 않고 나란히 놓고 살펴봅니다.", [l4["yongshin"]["geukguk"]["claim_id"]], BASIS_ENGINE, kind="limit"))
    center = None
    if sup:
        center = sup[0][0]
    insufficient = not present
    return {"favorable": favorable, "cautions": cautions, "month": wol, "center": center, "insufficient": insufficient,
            "present": {n: s["rank"] for n, s in present}}


# ------------------------------------------------------------------ 기간(대운·세운)
def _seg_summary(seg: dict, rel: list[str]) -> dict:
    ups = [d for d in _delta_for(seg, rel) if d["change"] in CHANGE_UP]
    downs = [d for d in _delta_for(seg, rel) if d["change"] in CHANGE_DOWN]
    bad = _bad_relations(seg)
    return {"ups": ups, "downs": downs, "bad": bad}


def year_reading(y: dict, rel: list[str], natal_nm: dict) -> dict:
    """한 해(1~2구간)의 변화분. 원국 설명을 되풀이하지 않고, 원국 대비 달라지는 것만 말한다."""
    segs = y["segments"]
    parts = []
    claims: list[str] = []
    score = 0
    reasons: list[str] = []
    sentences = []
    for seg in segs:
        sm = _seg_summary(seg, rel)
        lk = seg.get("luck")
        span = f"{_md(seg['from'])}~{_md(seg['to'])}"
        sup_up = [d for d in sm["ups"] if STRUCT[d["structure"]]["polarity"] == "support"]
        ten_up = [d for d in sm["ups"] if STRUCT[d["structure"]]["polarity"] == "tension"]
        txt, neg = [], []
        if sup_up:
            txt.append(f"{_join_themes([d['structure'] for d in sup_up], 'short')}이 원국보다 {'뚜렷해지는' if all(d['change'] == '강화' for d in sup_up) else '뚜렷해지거나 새로 나타나는'} 구간")
            claims += [d["claim_id"] for d in sup_up]
            score += 2 * len(sup_up)
            reasons += [f"{d['structure']} {d['change']}" for d in sup_up]
        if ten_up:
            neg.append(f"{_join_themes([d['structure'] for d in ten_up], 'short')}이 커져 신중한 점검이 필요한 구간")
            claims += [d["claim_id"] for d in ten_up]
            score += 2 * len(ten_up)
            reasons += [f"{d['structure']} {d['change']}" for d in ten_up]
        if sm["downs"]:
            neg.append(f"{_join_themes([d['structure'] for d in sm['downs']], 'short')}은 원국보다 줄어드는 구간")
            claims += [d["claim_id"] for d in sm["downs"]]
            score += len(sm["downs"])
            reasons += [f"{d['structure']} {d['change']}" for d in sm["downs"]]
        if sm["bad"]:
            kinds = sorted({r["type"] for r in sm["bad"]})
            score += len(kinds)
            reasons.append("원국과 " + "·".join(kinds) + " 관계")
        parts.append({"from": seg["from"], "to": seg["to"], "span": span, "luck": lk, "sewun": seg["sewun"], "texts": txt, "neg": neg, "bad": sorted({r["type"] for r in sm["bad"]}),
                      "claim_ids": [d["claim_id"] for d in sm["ups"] + sm["downs"]]})
    luck_split = len({x.get("luck") for x in segs}) > 1
    if luck_split:
        score += 2  # 한 해 안에서 대운이 바뀌면 그 자체가 변화(입춘 경계만으로는 변화로 세지 않는다)
        reasons.append("한 해 안에서 대운이 바뀜")
    merged: list[dict] = []  # 변화 내용이 같은 이웃 구간은 한 번만 말한다(같은 문장 반복 방지)
    for p in parts:
        if merged and merged[-1]["texts"] == p["texts"] and merged[-1]["neg"] == p["neg"]:
            m = merged[-1]
            m["bad"] = sorted(set(m["bad"]) | set(p["bad"]))
            m["to"] = p["to"]
            m["span"] = f"{_md(m['from'])}~{_md(m['to'])}"
            m["lucks"] = list(dict.fromkeys(m["lucks"] + [p["luck"]]))
            m["sewuns"] = list(dict.fromkeys(m["sewuns"] + [p["sewun"]]))
            m["claim_ids"] = list(dict.fromkeys(m["claim_ids"] + p["claim_ids"]))
        else:
            merged.append(dict(p, lucks=[p["luck"]], sewuns=[p["sewun"]]))
    ups_set = sorted({d["structure"] for seg in segs for d in _delta_for(seg, rel) if d["change"] in CHANGE_UP})
    downs_set = sorted({d["structure"] for seg in segs for d in _delta_for(seg, rel) if d["change"] in CHANGE_DOWN})
    bad_set = sorted({r["type"] for seg in segs for r in _bad_relations(seg)})
    return {"year": y["year"], "split": len(segs) > 1, "luck_split": luck_split, "parts": merged, "score": score, "reasons": list(dict.fromkeys(reasons)), "claim_ids": list(dict.fromkeys(claims)),
            "ups": ups_set, "downs": downs_set, "bad": bad_set, "sewuns": list(dict.fromkeys(p["sewun"] for p in merged for p in [p] if p["sewun"])) or []}


def one_line(yr: dict, common: dict | None = None) -> str:
    """연도별 한 줄. 여러 해를 비교할 때는 모든 해에 공통인 흐름(common)을 뺀 '그 해만의 차이'만 말한다. 차이가 없으면 없다고 말한다."""
    sw = "·".join(f"{x}세운" for x in yr["sewuns"])
    if common is None:
        bits = [x for p in yr["parts"] for x in p["texts"] + p["neg"]]
        return "; ".join(bits) or "원국의 흐름에서 구조상 달라지는 점이 확인되지 않습니다."
    extra = [n for n in yr["ups"] if n not in common["ups"]]
    lost = [n for n in common["ups"] if n not in yr["ups"]]
    bits = []
    if extra:
        bits.append(f"{_join_themes(extra, 'short')}이 더해짐")
    if lost:
        bits.append(f"{_join_themes(lost, 'short')}은 이 해에는 두드러지지 않음")
    if yr["downs"]:
        bits.append(f"{_join_themes(yr['downs'], 'short')}이 줄어듦")
    extra_bad = [k for k in yr["bad"] if k not in common["bad"]]
    if yr["bad"]:
        bits.append("원국과의 관계: " + "·".join(yr["bad"]))
    if yr["luck_split"]:
        lk = [x for p in yr["parts"] for x in p["lucks"]]
        bits.append(f"대운이 {'→'.join(l or '시작 전' for l in dict.fromkeys(lk))}로 바뀌어 앞뒤 구간을 나누어 읽음")
    return (f"{sw}: " if sw else "") + ("; ".join(bits) if bits else "공통 흐름 외에 달라지는 점이 확인되지 않습니다.")


def _lead(yr: dict, p: dict) -> str:
    whole = len(yr["parts"]) == 1
    where = f"{yr['year']}년" if whole else f"{yr['year']}년 {p['span']}"
    if len(p["lucks"]) == 1 and len(p["sewuns"]) == 1:
        return f"{where}({p['lucks'][0]}대운, {p['sewuns'][0]}세운)" if p["lucks"][0] else f"{where}({p['sewuns'][0]}세운)"
    if len(p["lucks"]) > 1:
        return f"{where}({'→'.join(l or '시작 전' for l in p['lucks'])} 대운 교체)"
    return where


def year_sentences(yr: dict) -> list[dict]:
    out = []
    for p in yr["parts"]:
        lead = _lead(yr, p)
        for t in p["texts"]:
            out.append(_sent(f"{lead}은 {t}입니다.", p["claim_ids"]))
        for t in p["neg"]:
            out.append(_sent(f"{lead}은 {t}입니다.", p["claim_ids"], kind="counter"))
        if p["bad"]:
            out.append(_sent(f"{lead}에는 {REL_PHRASE} 관계({'·'.join(p['bad'])})가 생겨, 같은 흐름이라도 매끄럽게만 이어진다고 보기는 어렵습니다.", p["claim_ids"], BASIS_ENGINE, kind="counter"))
        if not p["texts"] and not p["neg"] and not p["bad"]:
            out.append(_sent(f"{lead}은 원국의 흐름에서 구조상 달라지는 점이 확인되지 않는 구간입니다.", [], BASIS_ENGINE, kind="limit"))
    return out


def luck_change(periods: list[dict]) -> list[dict]:
    """범위 안에서 대운이 바뀌는 지점(사실)."""
    prev = None
    out = []
    for y in periods:
        for s in y["segments"]:
            lk = s.get("luck")
            if prev is not None and lk != prev:
                out.append({"date": s["from"], "before": prev, "after": lk})
            prev = lk
    return out


# ------------------------------------------------------------------ 분야별 요약
def domain_summary(pre: dict, block: dict, periods_r: list[dict], natal_nm: dict) -> dict:
    dom = block["domain"]
    spec = D.DOMAINS[dom]
    claims = [i["claim_id"] for i in block["structures"]] + block.get("extra_claim_ids", [])
    if spec.get("kind") == "palace":
        first = block["easy_text"].split(". ")[0].split("입니다.")[0].rstrip(".") + "."
        return {"domain": dom, "name": spec["name"], "text": first.replace(" 생극제화 구조로는", ""), "claim_ids": claims, "basis": BASIS_MODERN,
                "note": "궁위와 십성 신호를 중심으로 보는 분야로, 세부 근거는 아래 '더 자세히'에서 확인합니다.",
                "counter": bool(block["evidence_against"])}
    pres = [(i["structure"], natal_nm[i["structure"]]) for i in block["structures"] if natal_nm[i["structure"]]["rank"] > 0]
    pres.sort(key=lambda x: (-(STRUCT[x[0]]["polarity"] == "support"), -x[1]["rank"]))
    if not pres:
        return {"domain": dom, "name": spec["name"], "text": f"{spec['name']}과 직접 이어지는 뚜렷한 구조는 원국에서 확인되지 않아, 이 틀로는 특별히 짚을 만한 내용이 없습니다. 나쁘다는 뜻이 아니라 근거가 부족하다는 뜻입니다.",
                "claim_ids": claims, "basis": BASIS_ENGINE, "insufficient": True, "counter": False}
    sup = [p for p in pres if STRUCT[p[0]]["polarity"] == "support"]
    ten = [p for p in pres if STRUCT[p[0]]["polarity"] == "tension"]
    segs = []
    for yr in periods_r:
        for part in yr["parts"]:
            segs.append(part)
    rel_names = [i["structure"] for i in block["structures"]]
    ups = [d for yr in periods_r for d in yr.get("_delta", []) if d["structure"] in rel_names and d["change"] in CHANGE_UP]
    txt = []
    if sup:
        n, s = sup[0]
        txt.append(f"{spec['name']}은 {STRUCT[n]['short']}을 중심으로 살펴볼 수 있으며, 원국에서는 {TIER[s['rank']]} 나타납니다.")
    if ten:
        n, s = ten[0]
        txt.append(f"다만 {STRUCT[n]['short']}도 함께 있어 한쪽으로만 읽지 않습니다.")
    if ups:
        names = list(dict.fromkeys(d["structure"] for d in ups))
        txt.append(f"선택한 기간에는 {_join_themes(names[:2], 'short')}이 원국보다 커지는 구간이 있습니다.")
    return {"domain": dom, "name": spec["name"], "text": " ".join(txt), "claim_ids": list(dict.fromkeys(claims)), "basis": BASIS_MODERN, "counter": any(natal_nm[n]["counter"] for n, _ in pres)}


def _dedupe(items: list[dict]) -> list[dict]:
    seen, out = set(), []
    for x in items:
        if x["text"] not in seen:
            seen.add(x["text"])
            out.append(x)
    return out


# ------------------------------------------------------------------ 종합
def monthly_summary(months: dict | None, rel: list[str]) -> dict | None:
    """월운 한 줄 요약. 선택 분야 구조의 변화(대운·세운 포함 대비)와 원국과의 부딪히는 관계만 쓰고, 변화가 없으면 없다고 말한다. 구현자 규약이며 예측이 아니다."""
    if not months or not months.get("months"):
        return None
    items, scores = [], []
    for m in months["months"]:
        d = [x for x in m["structure_delta"] if x["structure"] in rel and x["change"] in CHANGE_UP]
        sup = [x["structure"] for x in d if STRUCT[x["structure"]]["polarity"] == "support"]
        ten = [x["structure"] for x in d if STRUCT[x["structure"]]["polarity"] == "tension"]
        bad = sorted({r["type"] for r in m["relations"] if r["type"] in REL_PLAIN})
        bits = []
        if sup:
            bits.append(_join_themes(sup, "short") + "이 더해짐")
        if ten:
            bits.append(_join_themes(ten, "short") + "이 커짐")
        if bad:
            bits.append("원국과 " + "·".join(bad) + " 관계")
        score = 2 * len(sup) + 2 * len(ten) + len(bad)
        scores.append(score)
        items.append({"span": f"{_md(m['from'])}~{_md(m['to'])}", "month_pillar": m["month_pillar"], "luck": m["luck"], "one_line": "; ".join(bits) or "이 분야 구조에서 달라지는 점이 확인되지 않음",
                      "score": score, "claim_ids": [m["claim_id"]] + [x["claim_id"] for x in d]})
    top = max(scores)
    for it in items:
        it["standout"] = top > 0 and it["score"] == top
    return {"year": months["year"], "items": items, "standout": [i["span"] for i in items if i["standout"]][:3], "note": months["note"], "rule_status": "implementer_convention",
            "basis": BASIS_MODERN}


def build(pre: dict, blocks: list[dict], periods: list[dict], doms: list[str], years: list[int], question: str = "", months: dict | None = None) -> dict:
    base = pre["natal_structure"]
    nm = _natal_map(base)
    sdoms = [d for d in doms if d != "luck"] or ["overall"]
    rel = _relevant(sdoms)
    natal = natal_reading(pre, sdoms)
    yrs = [year_reading(y, rel, nm) for y in periods]
    deltas = {y["year"]: [d for s in y["segments"] for d in s.get("delta", [])] for y in periods}
    for r in yrs:
        r["_delta"] = deltas[r["year"]]
    mode = "none" if not yrs else ("single" if len(yrs) == 1 else "multi")
    ver = pre["verification"]
    verification = {"v_status": ver.get("status"),
                    "notice": (ver.get("unverified_notice") or [])[:2],
                    "limit": "전통 명리학의 해석 틀로 읽은 것이며, 미래를 예측하거나 결과를 보장하지 않습니다."}
    headline: list[dict] = []
    favorable = list(natal["favorable"])
    cautions = list(natal["cautions"])
    flow: dict = {"mode": mode}
    # 핵심 해석
    if natal["insufficient"] and not any(r["score"] for r in yrs):
        headline.append(_sent("선택하신 분야와 기간에서는 이 해석 틀이 뚜렷하게 짚을 만한 근거가 부족합니다. 억지로 의미를 붙이지 않고, 아래 한계와 더 자세한 내용을 함께 봐 주세요.", [], BASIS_ENGINE, kind="limit"))
    else:
        if natal["center"]:
            c = natal["center"]
            headline.append(_sent(f"타고난 명식에서는 {STRUCT[c]['theme']}이 중심에 놓입니다.", [nm[c]["claim_id"]], rule_status=_rule_status(RULE_OF[c])))
        elif not natal["insufficient"]:
            headline.append(_sent("타고난 명식에는 돕는 흐름보다 부딪히거나 나누는 흐름이 먼저 보여, 조건을 가려 가며 읽어야 합니다.", [], BASIS_ENGINE))
        if mode == "single":
            y = yrs[0]
            ys = year_sentences(y)
            headline += [s for s in ys if s["kind"] == "reading"][:2]
            favorable = [s for s in ys if s["kind"] == "reading"] + favorable
            cautions = [s for s in ys if s["kind"] in ("counter", "limit")] + cautions
            flow.update({"year": y["year"], "split": y["split"], "sentences": ys})
        elif mode == "multi":
            lc = luck_change(periods)
            span = f"{yrs[0]['year']}~{yrs[-1]['year']}년"
            common = {"ups": [n for n in yrs[0]["ups"] if all(n in r["ups"] for r in yrs)], "bad": [k for k in yrs[0]["bad"] if all(k in r["bad"] for r in yrs)]}
            for r in yrs:  # 두드러짐 점수는 공통 흐름을 뺀 그 해만의 차이로 계산
                r["dev"] = 2 * len([n for n in r["ups"] if n not in common["ups"]]) + 2 * len([n for n in common["ups"] if n not in r["ups"]]) + len(r["downs"]) +                     len([k for k in r["bad"] if k not in common["bad"]]) + (2 if r["luck_split"] else 0)
            scores = [r["dev"] for r in yrs]
            top = max(scores)
            if top > min(scores):
                standout = [r for r in yrs if r["dev"] == top][:3]
            else:
                standout = []
            if standout:
                sy = ", ".join(f"{r['year']}년" for r in standout)
                headline.append(_sent(f"{span} 중 원국 대비 구조 변화가 가장 두드러지는 해는 {sy}입니다. 이는 변화가 크다는 뜻이지 좋거나 나쁜 일이 일어난다는 뜻이 아닙니다.", sum([r["claim_ids"] for r in standout], []), BASIS_ENGINE))
            else:
                headline.append(_sent(f"{span} 동안 해마다 눈에 띄게 달라지는 구조 변화는 확인되지 않아, 원국의 흐름이 비교적 일정하게 이어집니다.", [], BASIS_ENGINE))
            cs = [n for n in common["ups"] if STRUCT[n]["polarity"] == "support"]
            ct = [n for n in common["ups"] if STRUCT[n]["polarity"] == "tension"]
            if cs or ct:
                txt_ = (f"기간 내내 {_join_themes(cs, 'short')}이 원국보다 뚜렷한 쪽으로 기울어 있습니다." if cs else "") +                        ((" 다만 " if cs else "기간 내내 ") + f"{_join_themes(ct, 'short')}도 함께 커져 있습니다" if ct else "")
                headline.insert(1, _sent(txt_.strip().rstrip(".") + ". 해마다의 차이는 그 위에서 읽습니다.", [x["claim_id"] for r in yrs for x in r["_delta"] if x["structure"] in common["ups"] and x["change"] in CHANGE_UP][:6]))
            if lc:
                c0 = lc[0]
                headline.append(_sent(f"{c0['date'][:4]}년 {c0['date'][5:7].lstrip('0')}월 {c0['date'][8:].lstrip('0')}일 무렵 대운이 {c0['before'] or '시작 전'}→{c0['after']}로 바뀌어, 그 전후를 나누어 읽습니다.", [], BASIS_ENGINE))
            ups = list(dict.fromkeys(d for r in yrs for d in [x["structure"] for x in r["_delta"] if x["change"] in CHANGE_UP and STRUCT[x["structure"]]["polarity"] == "support" and x["structure"] in rel]))
            if ups:
                favorable.append(_sent(f"기간 안에서 {_join_themes(ups)}이 원국보다 뚜렷해지는 해가 있습니다.", [x["claim_id"] for r in yrs for x in r["_delta"] if x["structure"] in ups and x["change"] in CHANGE_UP]))
            many_bad = [r["year"] for r in yrs if r["bad"]]
            if len(many_bad) >= max(2, int(len(yrs) * 0.6)):
                cautions.append(_sent(f"기간 중 {len(many_bad)}개 해에서 세운이 {REL_PHRASE} 관계를 만들어, 매끄럽게만 이어지는 흐름으로 읽지 않습니다. 해마다 어떤 관계인지는 아래 한 줄 요약에 적었습니다.", [], BASIS_ENGINE, kind="counter"))
            tens = list(dict.fromkeys(x["structure"] for r in yrs for x in r["_delta"] if x["change"] in CHANGE_UP and STRUCT[x["structure"]]["polarity"] == "tension" and x["structure"] in rel))
            if tens:
                cautions.append(_sent(f"기간 안에서 {_join_themes(tens)}이 커지는 해가 있어 그 해에는 신중하게 살펴볼 만합니다.", [x["claim_id"] for r in yrs for x in r["_delta"] if x["structure"] in tens and x["change"] in CHANGE_UP], kind="counter"))
            flow.update({"years": [{"year": r["year"], "one_line": one_line(r, common), "standout": r in standout, "reasons": r["reasons"], "claim_ids": r["claim_ids"], "split": r["split"]} for r in yrs], "common": common,
                         "standout": [r["year"] for r in standout], "luck_changes": lc,
                         "standout_note": "두드러지는 해는 확률이 아니라 원국 대비 구조 변화·관계 수로 고른 것입니다." if standout else "",
                         "year_sentences": {r["year"]: year_sentences(r) for r in yrs}})
    if natal["insufficient"] and any(r["score"] for r in yrs):
        headline.insert(0, _sent("원국만으로는 이 분야에서 뚜렷한 구조가 확인되지 않고, 대운·세운이 들어오는 시기에 비로소 나타나는 구조를 중심으로 읽습니다.", [], BASIS_ENGINE, kind="limit"))
    monthly = monthly_summary(months, rel) if mode == "single" else None
    if monthly:
        flow["monthly"] = monthly
    # 한계·불확실성
    uncertainty = [_sent("같은 구조라도 실제 삶에서 어떻게 나타나는지는 사람마다 다르며, 이 풀이는 가능한 전통적 주제를 보여 줄 뿐입니다.", [], BASIS_ENGINE, kind="limit")]
    if not base["layer1"]["deukryeong"]["agree"]:
        uncertainty.append(_sent("월령의 도움 정도를 평가하는 기준이 서로 달라 일간의 강약은 단정하지 않았습니다.", list(base["layer1"]["deukryeong"]["claims"]), BASIS_ENGINE, kind="limit"))
    if any(r["luck_split"] for r in yrs):
        uncertainty.append(_sent("한 해 안에서 대운이 바뀌는 경우 앞뒤 구간을 따로 읽었고, 경계일 전후의 해석은 서로 이어 붙이지 않습니다.", [], BASIS_ENGINE, kind="limit"))
    elif any(r["split"] for r in yrs):
        uncertainty.append(_sent("입춘을 기준으로 세운이 바뀌는 구간은 따로 읽었고, 입춘 전후의 해석은 서로 이어 붙이지 않습니다.", [], BASIS_ENGINE, kind="limit"))
    if monthly:
        uncertainty.append(_sent("월별 흐름(월운)은 대운·세운과 같은 방식을 월 기둥에 적용한 구현자 규약이며, 고전 원문과 대조하지 않았습니다.", [], BASIS_ENGINE, kind="limit"))
    summaries = [domain_summary(pre, b, yrs, nm) for b in blocks]
    from . import readings as R  # 순환 import 방지
    ups_by = {}
    for r in yrs:
        for n in r["ups"]:
            ups_by.setdefault(n, []).append(r["year"])
    yn = {n: (f"{ys[0]}년" if len(ys) == 1 else f"{ys[0]}~{ys[-1]}년") + " 흐름" for n, ys in ups_by.items()}
    readings = R.for_domains(pre, blocks, nm, yn)
    readings += R.palace_readings(pre, blocks)
    for rd in readings:
        ys = ups_by.get(rd["structure"], [])
        if ys:
            where = f"{ys[0]}년" if len(ys) == 1 else ", ".join(f"{y}년" for y in ys[:4]) + (" 등" if len(ys) > 4 else "")
            rd["period"] = f"선택한 기간 중 {where}에 이 흐름이 원국보다 {'더 두드러집니다' if rd['polarity'] == 'support' else '커집니다'}."
        elif yrs:
            rd["period"] = "선택한 기간에는 이 구조가 원국보다 달라지는 해가 확인되지 않습니다."
    seen_s: set[str] = set()
    for d in summaries:  # 분야 사이에서 같은 문장이 되풀이되지 않게 한다(첫 분야에서 한 말은 이후 분야에서 생략)
        keep = []
        for sent in re.split(r"(?<=다\.)\s+", d["text"]):
            if sent not in seen_s:
                seen_s.add(sent)
                keep.append(sent)
        d["text"] = " ".join(keep) or d["text"]
    # 분야 요약은 해당 분야 구조의 변화분만 사용
    used = {h["text"] for h in headline}  # 첫 줄에서 이미 한 말은 되풀이하지 않는다
    favorable = [x for x in _dedupe(favorable) if x["text"] not in used]
    cautions = [x for x in _dedupe(cautions) if x["text"] not in used]
    more = {"favorable": favorable[3:], "cautions": cautions[4:]}
    favorable, cautions = favorable[:3], cautions[:4]
    all_s = headline + favorable + cautions + uncertainty
    return {"version": SYNTH_VERSION, "mode": mode, "verification": verification, "headline": headline, "favorable": favorable, "cautions": cautions, "more": more,
            "domain_summaries": summaries, "readings": readings, "period_flow": flow, "uncertainty": uncertainty, "natal": {"present": natal["present"], "center": natal["center"], "month": natal["month"]},
            "insufficient_evidence": bool(natal["insufficient"] and not any(r["score"] for r in yrs)),
            "claim_ids": list(dict.fromkeys(c for s in all_s for c in s["claim_ids"])),
            "text": "\n".join([s["text"] for s in all_s] + [d["text"] for d in summaries] + [y["one_line"] for y in flow.get("years", [])] + [" ".join([x["meaning"], x["why"], x["reality"], " ".join(x["counter"]), x["scope"], x.get("period", "")]) for x in readings])}
