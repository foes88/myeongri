"""Layer 1 — 세력 구조: 월령·득령·통근·본/중/여기·투간·일간 도움 구조.

수치 가중치를 쓰지 않는다. 사실(어느 글자가 어디에 있는가)과 조건별 순서형 라벨만 만들고,
학파 이견은 conflicting_claims 로 남긴다. 미래 사건·길흉은 이 층에서 말하지 않는다.
"""
from __future__ import annotations

from ..chart_analysis import GROUP_OF, _BRANCH_ELEMENT
from ..report_checks import BRANCH_SEASON, HIDDEN_STEMS_PROFILE, STEMS, _ELEMENT, _GENERATES, ten_god
from .evidence import ClaimNode, EvidenceGraph
from .rules import RULES

POS = ("year", "month", "day", "hour")
POS_KO = {"year": "연", "month": "월", "day": "일", "hour": "시"}
ROLES = ("본기", "중기", "여기")
HELPERS = ("비겁", "인성")


def _refs(rule_id: str) -> list[dict]:
    return RULES[rule_id]["sources"]


# 沈孝瞻 論十干得時不旺失時不弱: 長生·祿·旺(羊刃)=根之重, 墓庫·餘氣=根之輕, 陰干 長生은 重根이 아니고 明根(≈餘氣). 지장간에 같은 오행이 있어야 墓庫로 인정.
LONGSAENG = dict(zip("甲乙丙丁戊己庚辛壬癸", "亥午寅酉寅酉巳子申卯"))
LOK = dict(zip("甲乙丙丁戊己庚辛壬癸", "寅卯巳午巳午申酉亥子"))
WANG = dict(zip("甲乙丙丁戊己庚辛壬癸", "卯寅午巳午巳酉申子亥"))
TONGGEUN_PROFILES = {"position_role": "지장간 위치(본기=강·중기=중·여기=약) 기준 — 구현 규약(기본)",
                     "twelve_stage": "沈孝瞻 십이운성 기준: 長生·祿·旺=강(陰干 長生은 明根=약), 墓庫·餘氣=약"}


def twelve_stage_root(stem: str, branch: str) -> tuple[int, str | None]:
    """(등급 3=강/1=약/0=없음, 단계 이름)."""
    if branch == LOK[stem]:
        return 3, "건록"
    if branch == WANG[stem]:
        return 3, "제왕(양인)"
    if branch == LONGSAENG[stem]:
        return (3, "장생") if STEMS.index(stem) % 2 == 0 else (1, "음간 장생(明根)")
    same = [h for h in HIDDEN_STEMS_PROFILE[branch] if _ELEMENT[h] == _ELEMENT[stem]]
    if same:
        return 1, ("묘고" if branch in "辰戌丑未" else "여기·중기(餘氣)")
    return 0, None


def hidden_with_roles(branch: str) -> list[dict]:
    return [{"stem": s, "role": ROLES[i]} for i, s in enumerate(HIDDEN_STEMS_PROFILE[branch])]


def _group(day_stem: str, stem: str) -> str:
    return GROUP_OF[ten_god(day_stem, stem)]


def _node(g: EvidenceGraph, vid: str, rule_id: str, prefix: str, **kw) -> ClaimNode:
    return g.add(ClaimNode(claim_id=g.new_id(prefix), chart_variant_id=vid, rule_id=rule_id, school_id=RULES[rule_id]["school_id"],
                           source_references=_refs(rule_id), **kw))


def analyze_layer1(pillars: dict[str, str], g: EvidenceGraph, vid: str = "v1", days_since_jie: float | None = None,
                   tonggeun_profile: str = "position_role") -> dict:
    day_stem, mb = pillars["day"][0], pillars["month"][1]
    present = [p for p in POS if p in pillars]
    if tonggeun_profile not in TONGGEUN_PROFILES:
        raise ValueError(f"알 수 없는 통근 프로필: {tonggeun_profile}")
    out: dict = {"ruleset": "L1", "hour_known": "hour" in pillars, "tonggeun_profile": tonggeun_profile}

    # 월령 사실
    out["wolryeong"] = {"month_branch": mb, "season": BRANCH_SEASON[mb], "branch_element": _BRANCH_ELEMENT[mb],
                        "hidden": [dict(h, ten_god=ten_god(day_stem, h["stem"]), group=_group(day_stem, h["stem"]))
                                   for h in hidden_with_roles(mb)],
                        "hidden_table": "HIDDEN_STEMS_PROFILE(report_checks) — 판본별 이견 있음(knowledge/15 I07)",
                        "saryeong_days_applied": False}
    _node(g, vid, "MG-L1-WOLRYEONG", "L1-WOL", supporting_evidence=[f"월지 {mb} = {BRANCH_SEASON[mb]}, 오행 {_BRANCH_ELEMENT[mb]}"],
          counter_evidence=[], counter_checked=True, applicability=["월주 확정(절입 모호성 없음)이 전제"],
          exclusions=["사령(절입 후 일수별 사령 지장간)은 적용하지 않음"],
          conflicting_claims=[], uncertainty="월주는 절입 순간 기준; 절입 모호 입력이면 변형별로 따로 분석해야 함",
          interpretation_summary=f"월령은 {mb}({BRANCH_SEASON[mb]}). 지장간 {''.join(HIDDEN_STEMS_PROFILE[mb])}.", status="사실")

    # 득령 — 학파별 두 기준을 병렬 평가
    hid = out["wolryeong"]["hidden"]
    bongi = hid[0]
    sup = [h for h in hid if h["group"] in HELPERS]
    if bongi["group"] in HELPERS:
        bongi_label = "득령"
    elif sup:
        bongi_label = "부분득령(논쟁)"
    else:
        bongi_label = "실령 후보"
    d_el, m_el = _ELEMENT[day_stem], _BRANCH_ELEMENT[mb]
    season_label = "득령" if (m_el == d_el or _GENERATES[m_el] == d_el) else "실령 후보"
    n1 = _node(g, vid, "MG-L1-DEUKRYEONG-BONGI", "L1-DEUK",
               supporting_evidence=[f"월지 {mb} 본기 {bongi['stem']}({bongi['group']}) → 일간 {day_stem} 도움"] if bongi["group"] in HELPERS else
               [f"{h['role']} {h['stem']}({h['group']})가 일간을 돕는 군" for h in sup],
               counter_evidence=[f"월지 본기 {bongi['stem']}은 {bongi['group']}(일간을 돕지 않음)"] if bongi["group"] not in HELPERS else
               [f"{h['role']} {h['stem']}({h['group']})는 일간을 돕지 않음" for h in hid if h["group"] not in HELPERS],
               counter_checked=True, applicability=["월지 지장간 표 프로필 사용", "일간 기준"], exclusions=["사령 일수 미적용"],
               conflicting_claims=[], uncertainty="본기 기준과 계절 오행 기준은 서로 다른 결론을 낼 수 있으며 어느 쪽이 맞다고 확정하지 않음",
               interpretation_summary=f"본기 기준: {bongi_label}", status=bongi_label)
    n2 = _node(g, vid, "MG-L1-DEUKRYEONG-SEASON", "L1-DEUK",
               supporting_evidence=[f"월지 오행 {m_el}과 일간 오행 {d_el}: 같거나 생함"] if season_label == "득령" else [],
               counter_evidence=[] if season_label == "득령" else [f"월지 오행 {m_el}은 일간 오행 {d_el}과 같지도 생하지도 않음"],
               counter_checked=True, applicability=["계절 오행 기준"], exclusions=["본기·중기 세부 미반영"],
               conflicting_claims=[], uncertainty="토(辰戌丑未)월은 본기가 土여도 계절 성격이 다르다는 견해가 있음",
               interpretation_summary=f"계절 오행 기준: {season_label}", status=season_label)
    if not n1.supporting_evidence:
        n1.supporting_evidence = ["(찬성 근거 없음: 월지 지장간 중 일간을 돕는 십성군이 없음)"]
    if not n2.supporting_evidence:
        n2.supporting_evidence = ["(찬성 근거 없음: 월지 오행이 일간을 돕지 않음)"]
    if bongi_label != "득령" and bongi_label != season_label or (bongi_label == "득령") != (season_label == "득령"):
        g.link(n1.claim_id, n2.claim_id, "conflicts", "득령 기준 불일치")
    out["deukryeong"] = {"by_bongi": bongi_label, "by_season_element": season_label, "agree": bongi_label == season_label or (bongi_label != "부분득령(논쟁)" and (bongi_label == "득령") == (season_label == "득령")),
                         "claims": [n1.claim_id, n2.claim_id]}

    # 통근
    roots_out, strict_best = {}, {}  # strict_best: 위치별 엄격 통근 등급(3=본기)
    for p in present:
        stem = pillars[p][0]
        found = []
        for q in present:
            for h in hidden_with_roles(pillars[q][1]):
                if h["stem"] == stem:
                    found.append({"branch_pos": q, "branch": pillars[q][1], "role": h["role"], "type": "같은 간"})
                elif _ELEMENT[h["stem"]] == _ELEMENT[stem]:
                    found.append({"branch_pos": q, "branch": pillars[q][1], "role": h["role"], "type": "같은 오행(음양 다름)"})
        strict = [f for f in found if f["type"] == "같은 간"]
        grade_s = max((3 - ROLES.index(f["role"]) for f in strict), default=0)
        grade_l = max((3 - ROLES.index(f["role"]) for f in found), default=0)
        if tonggeun_profile == "twelve_stage":  # 학파 프로필: 십이운성 기준(엄격/관대 구분 없음)
            found = []
            for q in present:
                gr, stage = twelve_stage_root(stem, pillars[q][1])
                if gr:
                    found.append({"branch_pos": q, "branch": pillars[q][1], "role": stage, "type": "십이운성(沈孝瞻)", "grade": gr})
            grade_s = grade_l = max((f["grade"] for f in found), default=0)
        lab = {0: "없음", 1: "약", 2: "중", 3: "강"}
        strict_best[p] = grade_s
        roots_out[p] = {"stem": stem, "roots": found, "strict_level": lab[grade_s], "lenient_level": lab[grade_l],
                        "contested": lab[grade_s] != lab[grade_l]}
        n = _node(g, vid, "MG-L1-TONGGEUN", "L1-ROOT",
                  supporting_evidence=[f"{POS_KO[f['branch_pos']]}지 {f['branch']} {f['role']} — {f['type']}" for f in found] or
                  ["(찬성 근거 없음: 어느 지지 지장간에도 같은 오행 글자가 없음)"],
                  counter_evidence=([f"엄격 기준(같은 간)으로는 {lab[grade_s]}, 관대 기준(같은 오행)으로는 {lab[grade_l]}"] if lab[grade_s] != lab[grade_l] else []) +
                  ([f"뿌리가 여기·중기에만 있음"] if found and max(grade_s, grade_l) < 3 else []),
                  counter_checked=True, applicability=(["지장간 표 프로필", "십이운성 기준 통근은 미적용(프로필 twelve_stage 에서 적용)"] if tonggeun_profile == "position_role" else ["십이운성 기준(沈孝瞻 論十干得時不旺失時不弱)", "墓庫는 지장간에 같은 오행이 있을 때만"]),
                  exclusions=(["십이운성(장생·건록 등) 통근 학설은 기본 프로필에서 미적용"] if tonggeun_profile == "position_role" else ["지장간 위치(본기/중기/여기) 등급은 이 프로필에서 사용하지 않음"]), conflicting_claims=[],
                  uncertainty="통근의 정도를 수치화하는 원전 알고리즘은 없음(knowledge/04). 강·중·약은 본기·중기·여기 순서의 구현 규칙",
                  interpretation_summary=f"{POS_KO[p]}간 {stem}: 엄격 {lab[grade_s]} / 관대 {lab[grade_l]}", status=f"엄격 {lab[grade_s]}",
                  attributes={"position": p})
        roots_out[p]["claim_id"] = n.claim_id
    out["tonggeun"] = roots_out

    # 투간
    vis = {p: pillars[p][0] for p in present}
    tug = []
    for h in hidden_with_roles(mb):
        hits = [p for p, s in vis.items() if s == h["stem"] and p != "day"]
        day_same = day_stem == h["stem"]
        tug.append({"stem": h["stem"], "role": h["role"], "revealed_at": hits, "same_as_day_stem": day_same})
    revealed = [t for t in tug if t["revealed_at"]]
    nt = _node(g, vid, "MG-L1-TUGAN", "L1-TUG",
               supporting_evidence=[f"월지 {t['role']} {t['stem']} 이(가) {','.join(POS_KO[x] + '간' for x in t['revealed_at'])}에 투출" for t in revealed] or
               ["(찬성 근거 없음: 월지 지장간이 연·월·시간에 나타나지 않음)"],
               counter_evidence=[f"월지 {t['role']} {t['stem']} 는 투출하지 않음(암장)" for t in tug if not t["revealed_at"]],
               counter_checked=True, applicability=["월간 자체가 월지 지장간이면 투간으로 본다"], exclusions=["일간은 투출 판정에서 제외하고 same_as_day_stem 으로 별도 표시"],
               conflicting_claims=[], uncertainty="투출 여부가 격국 귀속에 미치는 영향은 학파별로 달라 이 층에서는 사실만 기록",
               interpretation_summary="투출 " + (",".join(t["stem"] for t in revealed) or "없음"), status="투출 있음" if revealed else "암장만")
    out["tugan"] = {"month_branch_hidden": tug, "claim_id": nt.claim_id}

    # 일간 도움 구조(순서형 후보) — 사실 카운트 + 규칙 라벨
    counts = {k: {"visible": 0, "hidden": 0} for k in ("비겁", "식상", "재성", "관성", "인성")}
    for p in present:
        if p != "day":
            counts[_group(day_stem, pillars[p][0])]["visible"] += 1
        for h in hidden_with_roles(pillars[p][1]):
            counts[_group(day_stem, h["stem"])]["hidden"] += 1
    vis_help = counts["비겁"]["visible"] + counts["인성"]["visible"]
    deuk = out["deukryeong"]["by_bongi"] == "득령"
    if tonggeun_profile == "twelve_stage":
        strict_root = roots_out["day"]["strict_level"] == "강"
    else:
        strict_root = any(r["role"] == "본기" and r["type"] == "같은 간" for r in roots_out["day"]["roots"])
    if deuk and strict_root:
        label = "강 후보"
    elif not deuk and not strict_root and vis_help <= 1:
        label = "약 후보"
    else:
        label = "중간/논쟁"
    sup_ev = []
    cnt_ev = []
    (sup_ev if deuk else cnt_ev).append("본기 기준 득령" if deuk else "본기 기준 득령 아님")
    (sup_ev if strict_root else cnt_ev).append("일간이 본기에 엄격 통근" if strict_root else "일간이 본기에 엄격 통근하지 못함")
    (sup_ev if vis_help >= 2 else cnt_ev).append(f"천간 도움(비겁·인성) {vis_help}개")
    ns = _node(g, vid, "MG-L1-SUPPORT-ORDINAL", "L1-SUP", supporting_evidence=sup_ev or ["(찬성 근거 없음)"], counter_evidence=cnt_ev,
               counter_checked=True, applicability=["신강·신약 구분은 억부론 관점"], exclusions=["격국론의 성격·파격은 Layer 4", "대운·세운 미반영"],
               conflicting_claims=[], uncertainty="강약 후보는 구현 규칙이며 기세론·종격 관점에서는 달리 판정될 수 있음",
               interpretation_summary=f"일간 도움 구조: {label}", status=label)
    out["support_structure"] = {"label": label, "group_counts": counts, "visible_helpers": vis_help, "claim_id": ns.claim_id,
                                "note": "카운트는 사실 집계이며 세력의 크기가 아니다"}
    return out
