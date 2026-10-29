"""Layer 4 — 격국·조후: 월령 격국 후보, 성격·파격·구응 후보, 한난조습 방향, 용신 후보(격국/억부/조후 분리).

모든 결과는 '후보'다. 학파가 다르면 결과가 갈릴 수 있으므로 격국용신·억부용신·조후용신을 하나의 용신으로 합치지 않는다.
궁통보감의 일간×월지 개별 조후 표는 원문 대조 없이 옮기지 않았다(미구현). 조건표는 구현자 단순화이며 원전과 동일하다고 주장하지 않는다.
"""
from __future__ import annotations

from ..report_checks import STEMS, _CONTROLS, _ELEMENT, _GENERATES, ten_god
from .evidence import ClaimNode, EvidenceGraph
from .layer1 import POS, POS_KO, hidden_with_roles
from .layer3 import find, occurrences
from .rules import RULES

GEOK_NAME = {"正官": "정관격", "七殺": "칠살격", "正印": "정인격", "偏印": "편인격", "食神": "식신격", "傷官": "상관격", "正財": "정재격", "偏財": "편재격"}
# 일간의 건록 지지 / 양인 지지(양간만)
GEONROK = dict(zip(STEMS, "寅卯巳午巳午申酉亥子"))
YANGIN = {"甲": "卯", "丙": "午", "戊": "午", "庚": "酉", "壬": "子"}
SEASON_AXIS = {"亥": "한(寒)", "子": "한(寒)", "丑": "한(寒)", "寅": "한난 중간(초봄)", "卯": "한난 중간(봄)", "辰": "한난 중간(늦봄)",
               "巳": "난(熱)", "午": "난(熱)", "未": "난(熱)", "申": "한난 중간(초가을)", "酉": "한난 중간(가을)", "戌": "한난 중간(늦가을)"}
EL_GROUP_NAME = {"木": "목", "火": "화", "土": "토", "金": "금", "水": "수"}

# 격별 조건표: 성격(이루는 요소), 파격(깨는 요소), 구응(깨짐을 구하는 요소). 값은 (이름, 키 목록) — 키는 십성 이름 또는 십성군
SEONGPA = {
    "정관격": {"성": [("재성 보좌(財生官)", ("재성",)), ("인성 보좌(官印相生)", ("인성",))],
             "파": [("상관견관", ("傷官",)), ("칠살 혼잡", ("七殺",))], "구": {"상관견관": [("인성이 상관을 제어", ("인성",))], "칠살 혼잡": [("식신이 칠살을 제어", ("食神",))]}},
    "칠살격": {"성": [("식신제살", ("食神",)), ("인성화살", ("인성",))],
             "파": [("재자약살(제화 없이 재가 살을 생함)", ("재성",))], "구": {"재자약살(제화 없이 재가 살을 생함)": [("식신 제살", ("食神",)), ("인성 화살", ("인성",))]}},
    "정인격": {"성": [("관인상생", ("관성",))], "파": [("재파인", ("재성",))], "구": {"재파인": [("비겁이 인성을 호위", ("비겁",)), ("관성이 재의 기운을 설기", ("관성",))]}},
    "편인격": {"성": [("관살 보좌", ("관성",)), ("비겁 보좌", ("비겁",))], "파": [("재파인", ("재성",))], "구": {"재파인": [("비겁이 인성을 호위", ("비겁",))]}},
    "식신격": {"성": [("식신생재", ("재성",)), ("식신제살", ("七殺",))], "파": [("효신탈식(偏印이 食神을 압박)", ("偏印",))],
             "구": {"효신탈식(偏印이 食神을 압박)": [("재성이 편인을 제어", ("재성",))]}},
    "상관격": {"성": [("상관생재", ("재성",)), ("상관패인", ("인성",))], "파": [("상관견관", ("正官",))], "구": {"상관견관": [("인성이 상관을 제어", ("인성",))]}},
    "정재격": {"성": [("재생관", ("관성",)), ("식상생재", ("식상",))], "파": [("비겁탈재", ("비겁",))],
             "구": {"비겁탈재": [("관살이 비겁을 제어", ("관성",)), ("식상이 비겁을 설기", ("식상",))]}},
    "편재격": {"성": [("재생관", ("관성",)), ("식상생재", ("식상",))], "파": [("비겁탈재", ("비겁",))],
             "구": {"비겁탈재": [("관살이 비겁을 제어", ("관성",)), ("식상이 비겁을 설기", ("식상",))]}},
}


def _node(g, vid, rule_id, prefix, **kw) -> ClaimNode:
    return g.add(ClaimNode(claim_id=g.new_id(prefix), chart_variant_id=vid, rule_id=rule_id, school_id=RULES[rule_id]["school_id"],
                           source_references=RULES[rule_id]["sources"], counter_checked=True, **kw))


def _hits(occ, keys, min_rank=2):
    return [o for o in find(occ, *keys) if o["rank"] >= min_rank]


def _fmt(os):
    return ", ".join(f"{POS_KO.get(o['pos'], o['pos'])}{'간' if o['kind'] == 'stem' else '지'}{o['char']}({o['god']})" for o in os[:4])


def analyze_layer4(pillars: dict[str, str], g: EvidenceGraph, vid: str = "v1", l1: dict | None = None) -> dict:
    day_stem, mb = pillars["day"][0], pillars["month"][1]
    occ = occurrences(pillars)
    hid = hidden_with_roles(mb)
    revealed = {h["stem"]: [p for p in POS if p in pillars and p != "day" and pillars[p][0] == h["stem"]] for h in hid}
    out: dict = {"ruleset": "L4"}

    # ---- 격국 후보 (투출 우선 / 본기 중심 병렬) ----
    def geok_of(stem):
        god = ten_god(day_stem, stem)
        if god in ("比肩", "劫財"):
            return None, god
        return GEOK_NAME[god], god
    cands = []
    for h in hid:
        name, god = geok_of(h["stem"])
        cands.append({"stem": h["stem"], "role": h["role"], "god": god, "geokguk": name or "비겁(건록/양인 계열)", "revealed_at": revealed[h["stem"]]})
    rev = [c for c in cands if c["revealed_at"]]
    bongi = cands[0]
    primary_tugan = (next((c for c in rev if c["role"] == "본기"), None) or (rev[0] if rev else bongi))
    록 = GEONROK[day_stem] == mb
    인 = YANGIN.get(day_stem) == mb
    special = "건록격 후보(월겁)" if 록 else ("양인격 후보" if 인 else None)
    tg_name = special or primary_tugan["geokguk"]
    n1 = _node(g, vid, "MG-L4-GYEOKGUK-CAND", "L4-GEOK",
               supporting_evidence=[f"월지 {mb} 지장간 {c['role']} {c['stem']}({c['god']})" + (f" 가 {','.join(POS_KO[x] + '간' for x in c['revealed_at'])}에 투출" if c["revealed_at"] else " 암장") for c in cands] +
               ([f"월지 {mb} 는 일간 {day_stem} 의 {'건록' if 록 else '양인'} 지지"] if special else []),
               counter_evidence=([f"투출 우선 원칙: 본기 {bongi['stem']} 이(가) 투출하지 않아 중기·여기 투출 {primary_tugan['stem']} 을 택하는 것은 학파별 논쟁"] if rev and primary_tugan is not bongi else []) +
               (["월겁(건록·양인)은 일반 격국으로 보지 않고 외격 별도 평가가 필요(미구현)"] if special else []) +
               (["투출 글자가 없어 본기를 암장 상태로 격 이름 삼음"] if not rev else []),
               applicability=["월주 확정(절입 모호성 없음)", "지장간 표 프로필", "사령 일수 미적용"], exclusions=["인원사령(절입 후 일수) 방식", "합충 후 변화한 격"],
               conflicting_claims=[], uncertainty="격 이름은 후보이며 투출 우선설과 본기 중심설이 갈림",
               interpretation_summary=f"투출 우선 기준 격국 후보: {tg_name}", status=tg_name,
               attributes={"candidates": cands})
    n2 = _node(g, vid, "MG-L4-GYEOKGUK-BONGI", "L4-GEOK",
               supporting_evidence=[f"월지 {mb} 본기 {bongi['stem']}({bongi['god']})"], counter_evidence=[f"본기가 투출하지 않았음에도 본기로 이름 짓는 것에 반대하는 견해" if not bongi["revealed_at"] else "중기·여기 투출을 무시한다는 반론"] if (not bongi["revealed_at"] or (rev and primary_tugan is not bongi)) else ["본기 중심은 월령 사령 개념을 반영하지 못한다는 반론"],
               applicability=["본기 기준"], exclusions=[], conflicting_claims=[], uncertainty="본기 중심설",
               interpretation_summary=f"본기 중심 격국 후보: {special or bongi['geokguk']}", status=special or bongi["geokguk"])
    if (special or bongi["geokguk"]) != tg_name:
        g.link(n1.claim_id, n2.claim_id, "conflicts", "투출 우선 vs 본기 중심 격 이름 불일치")
    out["gyeokguk"] = {"candidates": cands, "tugan_priority": tg_name, "bongi_centered": special or bongi["geokguk"], "special": special,
                       "claims": [n1.claim_id, n2.claim_id], "agree": (special or bongi["geokguk"]) == tg_name}

    # ---- 성격·파격·구응 (투출 우선 격 기준; 본기 중심이 다르면 그 격도 병렬 평가) ----
    evaluated = {}
    for label, gname in (("투출 우선", tg_name), ("본기 중심", special or bongi["geokguk"])):
        if gname in evaluated or gname not in SEONGPA:
            continue
        tbl = SEONGPA[gname]
        sung = [(n, _hits(occ, k)) for n, k in tbl["성"]]
        sung_ok = [(n, h) for n, h in sung if h]
        pa = [(n, _hits(occ, k)) for n, k in tbl["파"]]
        pa_hit = [(n, h) for n, h in pa if h]
        rescue = {}
        for n, h in pa_hit:
            rescue[n] = [(rn, _hits(occ, rk)) for rn, rk in tbl["구"].get(n, [])]
        # 칠살격: 제화(식신·인성) 둘 다 없고 재성이 있으면 파격 후보
        if gname == "칠살격" and pa_hit and (_hits(occ, ("食神",)) or _hits(occ, ("인성",))):
            pa_hit = []
        saved = [n for n, _ in pa_hit if any(h for _, h in rescue.get(n, []))]
        unsaved = [n for n, _ in pa_hit if n not in saved]
        if unsaved:
            status = "파격 후보(구응 없음)"
        elif pa_hit and saved:
            status = "파격이나 구응 후보"
        elif sung_ok:
            status = "성격 후보"
        else:
            status = "성패 미정(성격 요소 없음)"
        sup = [f"성격 요소 {n}: {_fmt(h)}" for n, h in sung_ok] + [f"구응 요소 {rn}: {_fmt(h)}" for n in saved for rn, h in rescue[n] if h]
        cnt = [f"파격 요소 {n}: {_fmt(h)}" for n, h in pa_hit] + [f"성격 요소 {n}: 출현 없음" for n, h in sung if not h]
        nn = _node(g, vid, "MG-L4-SEONGPA", "L4-SP", supporting_evidence=sup or ["(성격·구응 요소 출현 없음)"], counter_evidence=cnt,
                   applicability=[f"{label} 격국 {gname}", "요소 출현 기준: 천간 또는 지지 본기(중·여기 암장은 제외)"],
                   exclusions=["합충으로 요소가 변하거나 제거되는 경우(Layer 2 참조)", "대운·세운"], conflicting_claims=[],
                   uncertainty="조건표는 구현자 단순화이며 원전의 성패 조건과 일치한다고 확정하지 않음. 길흉이나 사건이 아니라 구조 후보임",
                   interpretation_summary=f"{gname}: {status}", status=status, attributes={"geokguk": gname, "basis": label})
        evaluated[gname] = {"geokguk": gname, "basis": label, "status": status, "success_factors": [n for n, _ in sung_ok],
                            "break_factors": [n for n, _ in pa_hit], "rescue_factors": saved, "claim_id": nn.claim_id}
    if special and special not in evaluated:
        nn = _node(g, vid, "MG-L4-SEONGPA", "L4-SP", supporting_evidence=[f"월지가 {special} 계열"], counter_evidence=["외격·월겁용관 조건표 미구현이라 성패를 판정하지 않음"],
                   applicability=[special], exclusions=["건록·양인격의 성패 조건"], conflicting_claims=[],
                   uncertainty="성패 판정 보류", interpretation_summary=f"{special}: 판정 보류", status="판정 보류(미구현)")
        evaluated[special] = {"geokguk": special, "status": "판정 보류(미구현)", "claim_id": nn.claim_id}
    out["seongpa"] = evaluated

    # ---- 조후: 한난조습 방향 ----
    tally = {}
    for o in occ:
        if o["rank"] >= 2:
            tally[_ELEMENT[o["char"]]] = tally.get(_ELEMENT[o["char"]], 0) + 1
    axis = SEASON_AXIS[mb]
    direction = []
    if axis.startswith("한(寒)"):
        direction = ["火"]
    elif axis.startswith("난(熱)"):
        direction = ["水"]
    nj = _node(g, vid, "MG-L4-JOHU-DIRECTION", "L4-JOHU",
               supporting_evidence=[f"월지 {mb}: {axis}", f"천간·본기 오행 집계(사실): " + ", ".join(f"{e}{c}" for e, c in sorted(tally.items()))] +
               ([f"계절 방향상 필요한 오행 후보: {','.join(direction)}"] if direction else ["계절상 뚜렷한 한난 편중 없음(보류)"]),
               counter_evidence=["조습(燥濕) 판정 기준은 학파별로 달라 집계만 제공하고 판정하지 않음",
                                 "궁통보감 일간×월지 개별 용신 표는 원문 대조 없이 옮기지 않았음(미구현)"] + (["조후용신을 유일한 용신으로 삼는 것은 흔한 오류(knowledge/08)"] if direction else []),
               applicability=["월지 계절 기준"], exclusions=["궁통보감 개별 표", "조습 세부 판정"], conflicting_claims=[],
               uncertainty="방향 후보일 뿐 특정 천간·길흉이 아님", interpretation_summary=f"조후 방향: {axis}", status=axis,
               attributes={"element_tally": tally, "direction_elements": direction})
    out["johu"] = {"month_axis": axis, "element_tally": tally, "direction_elements": direction, "gungtong_table": "미구현", "claim_id": nj.claim_id}

    # ---- 용신 후보 3종 분리 ----
    main_eval = evaluated.get(tg_name) or next(iter(evaluated.values()), None)
    geuk_groups: list[str] = []
    geuk_ev: list[str] = []
    if main_eval and main_eval["status"] in ("성격 후보", "파격이나 구응 후보"):
        tbl = SEONGPA.get(main_eval["geokguk"], {})
        names = main_eval["success_factors"] + main_eval["rescue_factors"]
        for part, keys in [(n, k) for n, k in tbl.get("성", [])] + [(rn, rk) for lst in tbl.get("구", {}).values() for rn, rk in lst]:
            if part in names or any(part == rn for rn in names):
                geuk_groups += [k for k in keys]
        geuk_ev = [f"{main_eval['geokguk']} {main_eval['status']}: " + ", ".join(names)]
    elif main_eval:
        geuk_ev = [f"{main_eval['geokguk']} {main_eval['status']} — 격국용신 후보를 정하지 않음"]
    geuk_groups = sorted({x for x in geuk_groups})
    support = (l1 or {}).get("support_structure", {}).get("label", "중간/논쟁")
    eokbu = ["식상", "재성", "관성"] if support == "강 후보" else (["인성", "비겁"] if support == "약 후보" else [])
    johu_groups = sorted({_group_of_element(day_stem, e) for e in direction})
    ng = _node(g, vid, "MG-L4-GEUKGUK-YONGSHIN", "L4-YS", supporting_evidence=geuk_ev or ["(격국용신 근거 없음)"],
               counter_evidence=["격국용신과 억부·조후용신은 서로 다를 수 있음"], applicability=["격국 성패 후보 기준"], exclusions=["외격"], conflicting_claims=[],
               uncertainty="용신 후보는 십성군 수준이며 특정 오행·글자·사건을 가리키지 않음", interpretation_summary="격국용신 후보 십성군: " + (",".join(geuk_groups) or "없음"),
               status="후보" if geuk_groups else "정하지 않음", attributes={"groups": geuk_groups})
    ne = _node(g, vid, "MG-L4-EOKBU-YONGSHIN", "L4-YS", supporting_evidence=[f"일간 도움 구조 후보: {support}"],
               counter_evidence=["강약 후보는 구현 규칙이며 종격·기세론에서는 달리 볼 수 있음"] + ([] if eokbu else ["중간/논쟁이라 억부 방향을 정하지 않음"]),
               applicability=["억부론"], exclusions=["종격"], conflicting_claims=[], uncertainty="방향 후보일 뿐 사건 예측이 아님",
               interpretation_summary="억부용신 후보 십성군: " + (",".join(eokbu) or "정하지 않음"), status="후보" if eokbu else "정하지 않음", attributes={"groups": eokbu})
    nh = _node(g, vid, "MG-L4-JOHU-DIRECTION", "L4-YS", supporting_evidence=[f"조후 방향 오행 {','.join(direction) or '없음'}"],
               counter_evidence=["궁통보감 개별 표 미구현"], applicability=["조후론"], exclusions=[], conflicting_claims=[], uncertainty="방향 후보",
               interpretation_summary="조후용신 후보 십성군: " + (",".join(johu_groups) or "정하지 않음"), status="후보" if johu_groups else "정하지 않음",
               attributes={"groups": johu_groups, "elements": direction})
    sets = {"격국용신": set(geuk_groups), "억부용신": set(eokbu), "조후용신": set(johu_groups)}
    nonempty = {k: v for k, v in sets.items() if v}
    conflicts = []
    names = list(nonempty)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            if not (nonempty[a] & nonempty[b]):
                conflicts.append((a, b))
    idmap = {"격국용신": ng, "억부용신": ne, "조후용신": nh}
    for a, b in conflicts:
        g.link(idmap[a].claim_id, idmap[b].claim_id, "conflicts", "용신 후보 십성군이 겹치지 않음")
    out["yongshin"] = {"geukguk": {"groups": geuk_groups, "claim_id": ng.claim_id}, "eokbu": {"groups": eokbu, "claim_id": ne.claim_id},
                       "johu": {"groups": johu_groups, "elements": direction, "claim_id": nh.claim_id},
                       "conflicts": [{"between": [a, b], "note": "서로 겹치지 않음 — 하나의 용신/길흉 점수로 합치지 않고 각각 설명"} for a, b in conflicts],
                       "note": "세 용신은 서로 다른 학파의 질문에 대한 답이며 합산하지 않는다"}
    return out


def _group_of_element(day_stem: str, element: str) -> str:
    """오행 → 일간 기준 십성군 (양/음 구분 없는 군 단위)."""
    d = _ELEMENT[day_stem]
    if element == d:
        return "비겁"
    if _GENERATES[element] == d:
        return "인성"
    if _GENERATES[d] == element:
        return "식상"
    if _CONTROLS[d] == element:
        return "재성"
    return "관성"
