"""Multi-School — 격국론·억부론·조후론 독립 평가기 + 학파 간 공통·충돌 분석.

각 평가기는 서로의 결과를 입력으로 쓰지 않는다(필요한 하위층 사실만 받는다). 결과를 하나의 길흉 점수로 합치지 않고
'어떤 질문에 대한 답인가'를 설명한다. 용신 후보가 일치해도 '전통적 해석의 합의'일 뿐 검증된 예측이 아니다.
기세론·통관병약론·신살은 아직 미구현이다(NOT_IMPLEMENTED 로 명시).
"""
from __future__ import annotations

IMPLEMENTED = ("gyeokguk", "eokbu", "johu")
NOT_IMPLEMENTED = ("gisee", "tonggwan_byeongyak", "sinsal")
QUESTION = {
    "gyeokguk": "월령에서 취한 격(십성 구조)이 이루어졌는가 깨졌는가",
    "eokbu": "일간의 도움과 소모 중 어느 쪽으로 기울었는가",
    "johu": "계절의 한난(寒暖)이 한쪽으로 치우쳤는가",
}


def evaluate_gyeokguk(l4: dict) -> dict:
    gk, sp = l4["gyeokguk"], l4["seongpa"]
    main = sp.get(gk["tugan_priority"]) or next(iter(sp.values()), None)
    status = main["status"] if main else "판정 불가"
    counter = []
    if not gk["agree"]:
        counter.append(f"격 이름이 학파 규칙에 따라 갈림: 투출 우선 '{gk['tugan_priority']}' vs 본기 중심 '{gk['bongi_centered']}'")
    if main and main.get("break_factors"):
        counter.append("파격 요소: " + ", ".join(main["break_factors"]) + (f" (구응 후보: {', '.join(main['rescue_factors'])})" if main.get("rescue_factors") else " (구응 요소 없음)"))
    if gk.get("special"):
        counter.append("월겁(건록·양인) 격은 외격 조건표가 없어 성패를 판정하지 못함")
    groups = l4["yongshin"]["geukguk"]["groups"]
    return {"school_id": "gyeokguk", "name": "격국론", "question": QUESTION["gyeokguk"],
            "core_judgement": f"{gk['tugan_priority']}: {status}",
            "applicability": ["월주 확정", "월지 지장간 프로필", "조건표는 구현자 단순화(원전 대조 전)"],
            "yongshin_candidates": groups, "yongshin_kind": "격국용신(십성군)",
            "supporting": (main or {}).get("success_factors", []) + (main or {}).get("rescue_factors", []), "counter_evidence": counter,
            "scope": "격의 성패 구조. 일간의 강약이나 계절은 묻지 않음", "claim_ids": gk["claims"] + ([main["claim_id"]] if main else []),
            "state": status}


def evaluate_eokbu(l1: dict) -> dict:
    ss, dk = l1["support_structure"], l1["deukryeong"]
    counter = []
    if not dk["agree"]:
        counter.append(f"득령 기준이 갈림: 본기 기준 '{dk['by_bongi']}' vs 계절 오행 기준 '{dk['by_season_element']}'")
    contested = [p for p, t in l1["tonggeun"].items() if t["contested"]]
    if contested:
        counter.append("통근이 엄격/관대 기준에서 다르게 나오는 기둥: " + ", ".join(contested))
    label = ss["label"]
    groups = ["식상", "재성", "관성"] if label == "강 후보" else (["인성", "비겁"] if label == "약 후보" else [])
    if not groups:
        counter.append("강도 후보가 '중간/논쟁'이라 억부 방향을 정하지 않음")
    return {"school_id": "eokbu", "name": "억부론", "question": QUESTION["eokbu"], "core_judgement": f"일간 도움 구조: {label}",
            "applicability": ["월주 확정", "신강·신약 이분법 관점", "종격·기세론 관점은 제외"],
            "yongshin_candidates": groups, "yongshin_kind": "억부용신(십성군)", "supporting": [f"득령(본기): {dk['by_bongi']}", f"천간 도움 {ss['visible_helpers']}개"],
            "counter_evidence": counter, "scope": "일간 강약의 방향. 격의 성패나 계절은 묻지 않음",
            "claim_ids": dk["claims"] + [ss["claim_id"]], "state": label}


def evaluate_johu(l4: dict) -> dict:
    j = l4["johu"]
    groups = l4["yongshin"]["johu"]["groups"]
    counter = ["궁통보감 일간×월지 개별 표 미구현(원문 대조 전)", "조습(燥濕)은 집계만 제공하고 판정하지 않음"]
    if not j["direction_elements"]:
        counter.append("계절상 뚜렷한 한난 편중이 없어 조후 방향을 정하지 않음")
    return {"school_id": "johu", "name": "조후론", "question": QUESTION["johu"], "core_judgement": f"월지 계절: {j['month_axis']}",
            "applicability": ["월지 계절 기준", "한난 방향만 판단"], "yongshin_candidates": groups, "yongshin_kind": "조후용신(십성군; 방향 오행 " + ",".join(j["direction_elements"]) + ")",
            "supporting": [f"오행 집계 {j['element_tally']}"], "counter_evidence": counter, "scope": "계절 한난의 균형. 격의 성패나 일간 강약은 묻지 않음",
            "claim_ids": [j["claim_id"]], "state": j["month_axis"]}


def _pair_text(a: dict, b: dict) -> tuple[str, str, str]:
    """(관계, 원인, 설명) — 하나의 점수로 환산하지 않는다."""
    sa, sb = set(a["yongshin_candidates"]), set(b["yongshin_candidates"])
    if not sa or not sb:
        who = a["name"] if not sa else b["name"]
        return "비교 불가", f"{who}은(는) 용신 후보를 정하지 않음", f"{a['name']}과 {b['name']}은 {who}이(가) 방향을 정하지 않아 비교하지 않습니다."
    common = sa & sb
    if common:
        return "공통", "후보 십성군이 겹침", (f"{a['name']}과 {b['name']}은 '{', '.join(sorted(common))}' 쪽을 함께 가리킵니다. "
                                             "이는 서로 다른 관점이 같은 방향을 말한다는 전통 해석상의 일치일 뿐, 실제 사건을 예측한다는 뜻은 아닙니다.")
    return "충돌", f"묻는 질문이 다름({a['question']} / {b['question']})", (
        f"{a['name']}은 '{', '.join(sorted(sa))}' 쪽을, {b['name']}은 '{', '.join(sorted(sb))}' 쪽을 가리켜 서로 겹치지 않습니다. "
        f"{a['name']}은 '{a['question']}'를, {b['name']}은 '{b['question']}'를 묻기 때문에 답이 달라질 수 있습니다. 어느 쪽이 맞다고 정하지 않고 각각 설명합니다.")


def evaluate_schools(l1: dict, l4: dict) -> dict:
    schools = {"gyeokguk": evaluate_gyeokguk(l4), "eokbu": evaluate_eokbu(l1), "johu": evaluate_johu(l4)}
    pairs, expl = [], []
    keys = list(schools)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = schools[keys[i]], schools[keys[j]]
            rel, cause, text = _pair_text(a, b)
            pairs.append({"between": [a["school_id"], b["school_id"]], "relation": rel, "cause": cause, "explanation": text})
            expl.append(text)
    tally: dict[str, list[str]] = {}
    for s in schools.values():
        for g in s["yongshin_candidates"]:
            tally.setdefault(g, []).append(s["school_id"])
    consensus = {g: v for g, v in tally.items() if len(v) >= 2}
    # 단면 설명(문장): 학파별 한 줄
    lines = [f"{s['name']}({s['question']}): {s['core_judgement']}" + (f" — 용신 후보 {', '.join(s['yongshin_candidates'])}" if s["yongshin_candidates"] else " — 용신 후보를 정하지 않음") for s in schools.values()]
    return {"schools": schools, "not_implemented": list(NOT_IMPLEMENTED), "pairs": pairs, "consensus_groups": consensus,
            "consensus_note": "학파 간 후보 일치는 전통적 해석의 합의일 뿐 과학적으로 검증된 예측이 아니다. 하나의 길흉 점수로 합치지 않는다.",
            "natural_language": {"per_school": lines, "relations": expl}}
