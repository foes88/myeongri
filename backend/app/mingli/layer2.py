"""Layer 2 — 간지 관계: 천간합, 지지 육합·삼합·방합, 충·형·파·해, 합화 후보, 개고·입묘 후보.

'관계가 존재한다'(사실)와 '실제로 성립·작용한다'(해석)를 분리한다. 모든 관계는 existence=True 인 사실이고,
작용 여부는 conditions 의 충족 상태와 학파 논쟁으로만 기록한다. 충이 있어도 지장간 손상을 확정하지 않는다.
conditions[].status ∈ satisfied | unsatisfied | contested | unknown
"""
from __future__ import annotations

from itertools import combinations

from ..chart_analysis import _BRANCH_ELEMENT
from ..report_checks import HIDDEN_STEMS_PROFILE, _CONTROLS, _ELEMENT, _GENERATES
from .evidence import ClaimNode, EvidenceGraph
from .layer1 import POS_KO
from .rules import RULES

POS = ("year", "month", "day", "hour")
STEM_HAP = {frozenset("甲己"): "土", frozenset("乙庚"): "金", frozenset("丙辛"): "水", frozenset("丁壬"): "木", frozenset("戊癸"): "火"}
YUKHAP = {frozenset("子丑"): "土", frozenset("寅亥"): "木", frozenset("卯戌"): "火", frozenset("辰酉"): "金", frozenset("巳申"): "水",
          frozenset("午未"): "火/土(논쟁)"}
SAMHAP = {"水": "申子辰", "木": "亥卯未", "火": "寅午戌", "金": "巳酉丑"}
BANGHAP = {"木": "寅卯辰", "火": "巳午未", "金": "申酉戌", "水": "亥子丑"}
WANGJI = set("子午卯酉")
CHUNG = [frozenset(x) for x in ("子午", "丑未", "寅申", "卯酉", "辰戌", "巳亥")]
PA = [frozenset(x) for x in ("子酉", "丑辰", "寅亥", "卯午", "巳申", "未戌")]
HAE = [frozenset(x) for x in ("子未", "丑午", "寅巳", "卯辰", "申亥", "酉戌")]
SAMHYUNG = ("寅巳申", "丑戌未")
JAHYUNG = set("辰午酉亥")
GOGO = {"辰": ("水", "壬癸"), "戌": ("火", "丙丁"), "丑": ("金", "庚辛"), "未": ("木", "甲乙")}
ELEMENT_OVERCOMER = {v: k for k, v in _CONTROLS.items()}  # 어떤 오행을 극하는 오행


# 化神이 得時乘令인 월지(계절): 沈孝瞻 論外格用舍 "化出之物，得時乘令，四支局全". 次等: 화신을 생하는 월 또는 화신의 庫月("亥未之月亦是木地")
SEASON_BRANCHES = {"木": "寅卯辰", "火": "巳午未", "金": "申酉戌", "水": "亥子丑", "土": "辰戌丑未"}
KU_OF = {"木": "未", "火": "戌", "金": "丑", "水": "辰"}
HYUNG_PROFILES = {"common": "子卯·寅巳申·丑戌未·자형을 모두 '존재 후보'로 기록(기본)", "no_self": "자형(辰午酉亥)을 제외 — 任氏曰이 自刑을 俗謬로 배척"}


def month_tier(el: str, mb: str) -> str | None:
    """월지가 화신 오행(el)을 뒷받침하는 정도: 'season'(得時) / 'secondary'(次等) / None."""
    if mb in SEASON_BRANCHES[el]:
        return "season"
    if _GENERATES[_BRANCH_ELEMENT[mb]] == el or KU_OF.get(el) == mb:
        return "secondary"
    return None


def stem_gap(present: list[str], stems: dict[str, str], p1: str, p2: str) -> list[str]:
    """두 합 상대 사이에 끼어 어느 한쪽을 극하는 천간의 위치들(沈孝瞻 論十干合而不合: 間隔 → 合而不敢合)."""
    lo, hi = POS.index(p1), POS.index(p2)
    partners = {_ELEMENT[stems[p1]], _ELEMENT[stems[p2]]}
    return [q for q in present if lo < POS.index(q) < hi and _CONTROLS[_ELEMENT[stems[q]]] in partners]


def _cond(name, status, note=""):
    return {"name": name, "status": status, "note": note}


def _adjacent(p1, p2):
    return abs(POS.index(p1) - POS.index(p2)) == 1


def analyze_layer2(pillars: dict[str, str], g: EvidenceGraph, vid: str = "v1", pa_profile: str = "modern_6", hyung_profile: str = "common") -> dict:
    if hyung_profile not in HYUNG_PROFILES:
        raise ValueError(f"알 수 없는 刑 프로필: {hyung_profile}")
    present = [p for p in POS if p in pillars]
    stems = {p: pillars[p][0] for p in present}
    branches = {p: pillars[p][1] for p in present}
    relations: list[dict] = []
    node_of: dict[int, str] = {}

    def add(rule_id, rtype, positions, effect, conds, summary, *, school="common", attrs=None, extra_counter=()):
        not_sat = [c["name"] for c in conds if c["status"] in ("unsatisfied", "contested")]
        counter = [f"{c['name']}: {c['status']} {c['note']}".strip() for c in conds if c["status"] in ("unsatisfied", "contested")] + list(extra_counter)
        n = g.add(ClaimNode(
            claim_id=g.new_id("L2"), chart_variant_id=vid, rule_id=rule_id, school_id=school if school != "common" else RULES[rule_id]["school_id"],
            supporting_evidence=[f"{rtype} 구성 글자가 {','.join(positions)} 에 존재"] + [f"{c['name']}: 충족 {c['note']}".strip() for c in conds if c["status"] == "satisfied"],
            counter_evidence=counter, counter_checked=True, applicability=[c["name"] for c in conds], exclusions=["대운·세운 유입 시 변화는 Layer 5"],
            conflicting_claims=[], source_references=RULES[rule_id]["sources"],
            uncertainty="관계의 존재는 사실이나 실제 작용 정도와 결과는 학파별로 다르며 이 층에서는 확정하지 않음",
            interpretation_summary=summary, status=effect, attributes=attrs or {}))
        rel = {"claim_id": n.claim_id, "relation_type": rtype, "pillars": positions, "existence": True, "candidate_effect": effect,
               "school": n.school_id, "conditions": conds, "not_satisfied": not_sat, "confidence": "C", **(attrs or {})}
        relations.append(rel)
        return n

    # ---- 천간합 + 합화 후보 ----
    for p1, p2 in combinations([p for p in present], 2):
        key = frozenset((stems[p1], stems[p2]))
        if key not in STEM_HAP:
            continue
        el = STEM_HAP[key]
        adj = _adjacent(p1, p2)
        mb = branches["month"]
        tier = month_tier(el, mb)
        month_support = tier is not None
        blockers = stem_gap(present, stems, p1, p2)
        others = [stems[q] for q in present if q not in (p1, p2)]
        hwa_stem_visible = any(_ELEMENT[s] == el for s in others)
        hwa_root = any(_ELEMENT[h] == el for q in present for h in HIDDEN_STEMS_PROFILE[branches[q]])
        partner_competition = any(frozenset((stems[p1], s)) in STEM_HAP for s in others) or any(frozenset((stems[p2], s)) in STEM_HAP for s in others)
        breaker = any(_ELEMENT[s] == ELEMENT_OVERCOMER[el] for s in others)
        conds = [
            _cond("인접", "satisfied" if adj else "unsatisfied", "" if adj else "떨어져 있어 합 작용 약화(원문: 멀리 떨어지면 半合)"),
            _cond("월령이 화신 오행을 뒷받침", "satisfied" if month_support else "unsatisfied",
                  f"월지 {mb}, 화신 {el}: " + {"season": "得時(화신의 계절)", "secondary": "次等(화신을 생하거나 화신의 庫月)", None: "뒷받침 없음"}[tier]),
            _cond("화신 뿌리 또는 투출", "satisfied" if (hwa_stem_visible or hwa_root) else "unsatisfied", f"화신 {el}"),
            _cond("쟁합·투합 경쟁 없음", "contested" if partner_competition else "satisfied", "같은 글자에 합 상대가 둘 이상" if partner_competition else ""),
            _cond("화신을 극하는 오행 천간 없음", "contested" if breaker else "satisfied", f"{ELEMENT_OVERCOMER[el]} 오행 천간 존재" if breaker else ""),
        ]
        gap = _cond("사이 글자가 합 상대를 극하지 않음(間隔)", "unsatisfied" if blockers else "satisfied",
                    (f"{','.join(POS_KO[q] + '간 ' + stems[q] for q in blockers)} 가 사이에서 극함 → 合而不敢合(沈孝瞻 論十干合而不合)" if blockers else ("인접이라 해당 없음" if adj else "사이에 극하는 글자 없음")))
        conds.insert(1, gap)
        if "day" in (p1, p2):
            conds.append(_cond("일간 합화 허용 여부", "contested", "일간은 합해도 化하지 않는다는 견해와 종화격 허용 견해가 갈림"))
        n = add("MG-L2-STEM-HAP", "천간합", [p1, p2], "합 존재(합화 여부 미확정)" if not blockers else "합 존재하나 間隔으로 합이 안 됨(合而不敢合)", [conds[0], conds[1]],
                f"{stems[p1]}{stems[p2]} 합(→{el}). 합의 존재만 확인", attrs={"stems": [stems[p1], stems[p2]], "hwa_element": el})
        hard_fail = any(c["status"] == "unsatisfied" for c in conds[:4])  # 인접·間隔·월령·화신 뿌리/투출
        if hard_fail:
            hw_label = "합화 불성립 근거 있음"
        elif any(c["status"] == "contested" for c in conds):
            hw_label = "합화 논쟁/보류"
        else:
            hw_label = "합화 후보 조건 충족(일부 학파)"
        h = add("MG-L2-HAP-HWA", "합화 후보", [p1, p2], hw_label, conds, f"{stems[p1]}{stems[p2]}合 {el}化 조건 검토: {hw_label}",
                attrs={"hwa_element": el, "note": "합화 '성립'을 단정하지 않는다"})
        g.link(h.claim_id, n.claim_id, "depends_on", "합화 판정은 합의 존재에 의존")

    # ---- 지지: 육합 ----
    yukhap_pairs = []
    for p1, p2 in combinations(present, 2):
        key = frozenset((branches[p1], branches[p2]))
        if key in YUKHAP:
            adj = _adjacent(p1, p2)
            conds = [_cond("인접", "satisfied" if adj else "unsatisfied"),
                     _cond("합화 오행 일치", "contested" if "논쟁" in YUKHAP[key] else "unknown", f"화신 {YUKHAP[key]}")]
            n = add("MG-L2-BRANCH-YUKHAP", "육합", [p1, p2], "합 존재", conds, f"{branches[p1]}{branches[p2]} 육합({YUKHAP[key]})")
            yukhap_pairs.append((p1, p2, n.claim_id))

    # ---- 삼합 / 방합 ----
    samhap_members = []
    for el, trio in SAMHAP.items():
        hit = [p for p in present if branches[p] in trio]
        letters = {branches[p] for p in hit}
        if len(letters) == 3:
            kind = "삼합(완전)"
        elif len(letters) == 2:
            kind = "반합" if letters & WANGJI else "공합(拱合)·논쟁"
        else:
            continue
        has_month = "month" in hit
        stem_el = any(_ELEMENT[stems[q]] == el for q in present)
        conds = [_cond("월지 포함", "satisfied" if has_month else "unsatisfied"),
                 _cond("국 오행 천간 투출", "satisfied" if stem_el else "unsatisfied", f"{el}"),
                 _cond("글자 완전성", "satisfied" if len(letters) == 3 else "contested", "반합/공합은 학파별 인정 범위가 다름" if len(letters) < 3 else "")]
        n = add("MG-L2-SAMHAP", kind, hit, f"{kind} 존재", conds, f"{''.join(sorted(letters, key=trio.index))} → {el}국 후보", attrs={"element": el})
        samhap_members.append((set(hit), n.claim_id))
    for el, trio in BANGHAP.items():
        hit = [p for p in present if branches[p] in trio]
        letters = {branches[p] for p in hit}
        if len(letters) >= 2:
            full = len(letters) == 3
            conds = [_cond("월지 포함", "satisfied" if "month" in hit else "unsatisfied"),
                     _cond("글자 완전성", "satisfied" if full else "contested", "" if full else "2글자 방합은 별도 인정 여부 논쟁")]
            add("MG-L2-BANGHAP", "방합" if full else "방합(부분)", hit, "방합 존재" if full else "부분 방합 기록", conds, f"{trio} → {el}방")

    # ---- 충·형·파·해 ----
    profile_conflicts: list[dict] = []
    PA_CONTESTED = (frozenset("寅亥"), frozenset("巳申"))

    def pair_relations(table, rule_id, rtype):
        out = []
        for p1, p2 in combinations(present, 2):
            if frozenset((branches[p1], branches[p2])) in table:
                if rtype == "파" and frozenset((branches[p1], branches[p2])) in PA_CONTESTED:
                    profile_conflicts.append({"rule_id": rule_id, "pair": branches[p1] + branches[p2], "positions": [p1, p2], "profile_applied": pa_profile,
                                              "modern_6": "破로 기록", "sanmyeongtonghoe_4": "합으로 보아 破에서 제외(육합으로는 별도 기록)",
                                              "result_in_this_run": "제외됨" if pa_profile == "sanmyeongtonghoe_4" else "破 후보로 기록(원문 대조 불일치 조건 포함)"})
                    if pa_profile == "sanmyeongtonghoe_4":
                        continue
                adj = _adjacent(p1, p2)
                conds = [_cond("인접", "satisfied" if adj else "unsatisfied"),
                         _cond("월지 관여", "satisfied" if "month" in (p1, p2) else "unsatisfied")]
                if rtype == "파" and frozenset((branches[p1], branches[p2])) in (frozenset("寅亥"), frozenset("巳申")):
                    conds.append(_cond("원문 대조", "contested", "三命通會는 寅亥·巳申을 합으로 보아 破로 취하지 않음(docs/09)"))
                n = add(rule_id, rtype, [p1, p2], f"{rtype} 존재(작용 정도 미확정)", conds, f"{branches[p1]}{branches[p2]} {rtype}",
                        attrs={"damages_hidden_stems": "unconfirmed"} if rtype == "충" else None)
                out.append((p1, p2, n.claim_id))
        return out
    chung = pair_relations(CHUNG, "MG-L2-CHUNG", "충")
    pair_relations(PA, "MG-L2-PA", "파")
    pair_relations(HAE, "MG-L2-HAE", "해")

    hy_pos = {}
    for trio in SAMHYUNG:
        hit = [p for p in present if branches[p] in trio]
        letters = {branches[p] for p in hit}
        if len(letters) >= 2:
            full = len(letters) == 3
            add("MG-L2-HYUNG", "삼형" if full else "형(부분)", hit, "형 존재(작용 정도 미확정)",
                [_cond("글자 완전성", "satisfied" if full else "contested", "삼형 vs 2글자 형 인정 범위 학파차")], f"{trio} 형")
    for p1, p2 in combinations(present, 2):
        if frozenset((branches[p1], branches[p2])) == frozenset("子卯"):
            add("MG-L2-HYUNG", "무례지형(子卯)", [p1, p2], "형 존재(작용 정도 미확정)", [_cond("인접", "satisfied" if _adjacent(p1, p2) else "unsatisfied")], "子卯 형")
        if branches[p1] == branches[p2] and branches[p1] in JAHYUNG:
            profile_conflicts.append({"rule_id": "MG-L2-HYUNG", "pair": branches[p1] * 2, "positions": [p1, p2], "profile_applied": hyung_profile,
                                      "common": "자형 후보로 기록", "no_self": "自刑 제외(任氏曰: 俗謬)",
                                      "result_in_this_run": "제외됨" if hyung_profile == "no_self" else "자형 후보로 기록"})
            if hyung_profile == "no_self":
                continue
            add("MG-L2-HYUNG", "자형", [p1, p2], "형 존재(작용 정도 미확정)", [_cond("인접", "satisfied" if _adjacent(p1, p2) else "unsatisfied")], f"{branches[p1]}{branches[p2]} 자형")

    # ---- 합충 경합 ----
    pos_in_hap = {}
    for p1, p2, cid in yukhap_pairs:
        for p in (p1, p2):
            pos_in_hap.setdefault(p, []).append(cid)
    for members, cid in samhap_members:
        for p in members:
            pos_in_hap.setdefault(p, []).append(cid)
    for p1, p2, cid in chung:
        shared = [p for p in (p1, p2) if p in pos_in_hap]
        if shared:
            comp = add("MG-L2-COMPETITION", "합충 경합", [p1, p2] + [p for p in shared if p not in (p1, p2)], "경합 존재(우선순위는 학파 논쟁)",
                       [_cond("합이 충을 풀어주는가(탐합망충)", "contested", "합 우선설 / 충 우선설 / 인접·월령 우선설이 갈림")],
                       f"충({branches[p1]}{branches[p2]})에 관여하는 글자가 합에도 관여")
            g.link(comp.claim_id, cid, "depends_on", "경합 대상: 충")
            for hc in {x for p in shared for x in pos_in_hap[p]}:
                g.link(cid, hc, "conflicts", "같은 글자에서 충과 합이 경합")

    # ---- 개고·입묘 후보 ----
    for p in present:
        b = branches[p]
        if b not in GOGO:
            continue
        el, stems_of = GOGO[b]
        same_pillar = stems[p] in stems_of
        elsewhere = [q for q in present if q != p and stems[q] in stems_of]
        opener = [(a, c, cid) for a, c, cid in chung if p in (a, c)]
        conds = [_cond("같은 기둥 천간이 고(庫) 오행(자좌입묘)", "satisfied" if same_pillar else "unsatisfied", f"{el}고({b})"),
                 _cond("다른 기둥 천간에 고 오행 존재", "satisfied" if elsewhere else "unsatisfied"),
                 _cond("충으로 고를 여는 글자 존재(개고)", "contested" if opener else "unsatisfied", "충=개고설 / 충=손상설 / 형·합으로도 연다는 설이 갈림" if opener else "")]
        if not same_pillar and not elsewhere and not opener:
            continue
        n = add("MG-L2-GOGO", "개고·입묘 후보", [p] + [q for q in elsewhere], "후보 기록(성립 판정 보류)", conds,
                f"{b}는 {el}고. 입묘/개고는 학파별 조건이 달라 후보로만 기록", school="common")
        for a, c, cid in opener:
            g.link(n.claim_id, cid, "depends_on", "개고 후보는 충의 존재에 의존")

    return {"ruleset": "L2", "relations": relations, "count": len(relations), "pa_profile": pa_profile, "hyung_profile": hyung_profile, "profile_conflicts": profile_conflicts,
            "note": "existence 는 사실, candidate_effect 는 후보. 작용·길흉은 상위 층에서 학파별로 평가"}
