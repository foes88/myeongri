"""상담 서술 구성: 원국 특징 추출, 질문 맥락 반영, 문단 작성, 근거·모순 검사. 모두 구조 분석 결과에서만 문장을 만든다(새 주장 없음)."""
from __future__ import annotations

import re

from . import compose_domains

STATE_KO = {"indicated": "관련 구조가 뚜렷하다", "weak": "관련 구조가 약하게 있다", "not_indicated": "관련 구조가 확인되지 않는다"}
EVENT_KEYWORDS = [
    (r"이직|취업|퇴사|직장", "취업·이직"), (r"승진|평가|인사", "평가·승진 관련 변화"), (r"직무|보직|부서", "직무 변화"),
    (r"창업|사업.{0,4}(시작|준비)|가게", "사업 시작"), (r"확장|축소|동업", "사업 확장·축소"), (r"계약|문서|서류", "계약·문서 변화"),
    (r"부동산|집|전세|매매|이사|토지", "부동산 거래"), (r"투자|자산|재산|취득", "자산 취득"), (r"수입|월급|소득", "수입 변화"), (r"손실|빚|손해", "재무 손실"),
]
L3_NAMES = ["식상생재", "재생관", "관인상생", "살인상생", "상관견관", "군겁쟁재"]
POS_KO = {"year": "연", "month": "월", "day": "일", "hour": "시"}


def _by_rule(base: dict, rule_id: str) -> list[dict]:
    return [n for n in base["graph"]["nodes"] if n["rule_id"] == rule_id]


def natal_features(pre: dict) -> list[dict]:
    b = pre["natal_structure"]
    l1, l2, l3, l4 = b["layer1"], b["layer2"], b["layer3"], b["layer4"]
    P = b["pillars"]
    out = []
    wol = _by_rule(b, "MG-L1-WOLRYEONG")
    out.append({"kind": "month", "text": f"일간은 '{P['day'][0]}'이고 태어난 달의 지지는 '{l1['wolryeong']['month_branch']}'({l1['wolryeong']['season']})입니다.",
                "claim_ids": [n["claim_id"] for n in wol][:1]})
    dk = l1["deukryeong"]
    t = f"달의 기운이 일간을 돕는 정도는 본기 기준으로 '{dk['by_bongi']}', 계절 오행 기준으로 '{dk['by_season_element']}'로 평가됩니다."
    if not dk["agree"]:
        t += " 두 기준이 서로 달라 한쪽으로 단정하지 않습니다."
    out.append({"kind": "deukryeong", "text": t, "claim_ids": dk["claims"]})
    ss = l1["support_structure"]
    out.append({"kind": "strength", "text": f"일간을 돕는 기운과 덜어내는 기운의 균형은 '{ss['label']}'로 보는 것이 전통적 억부론의 한 관점입니다(종격·기세론에서는 다르게 볼 수 있습니다).",
                "claim_ids": [ss["claim_id"]]})
    gk = l4["gyeokguk"]
    main = l4["seongpa"].get(gk["tugan_priority"])
    t = f"월령에서 취한 격국 후보는 '{gk['tugan_priority']}'" + (f"이며 성패 후보 판단은 '{main['status']}'입니다." if main else "입니다.")
    if not gk["agree"]:
        t += f" 본기 중심으로 보면 '{gk['bongi_centered']}'로 이름이 달라져 학파 간 차이가 있습니다."
    out.append({"kind": "gyeokguk", "text": t, "claim_ids": gk["claims"] + ([main["claim_id"]] if main else [])})
    strong = [(k, v) for k, v in l1["tonggeun"].items() if v["strict_level"] == "강"]
    if strong:
        names = ", ".join(f"{POS_KO[k]}간 '{v['stem']}'" for k, v in strong)
        out.append({"kind": "tonggeun", "text": f"천간 중 지지 본기에 같은 글자로 뿌리를 내린 것은 {names}입니다.", "claim_ids": [v["claim_id"] for k, v in strong][:3]})
    top = [x for x in sorted(l3["structures"], key=lambda x: -x["rank"]) if x["rank"] >= 2][:2]
    if top:
        out.append({"kind": "structure", "text": "생극제화 구조 중 비교적 뚜렷한 것은 " + ", ".join(f"'{x['name']}'({x['label']})" for x in top) + "입니다.",
                    "claim_ids": [x["claim_id"] for x in top]})
    kinds: dict[str, int] = {}
    for r in l2["relations"]:
        kinds[r["relation_type"]] = kinds.get(r["relation_type"], 0) + 1
    if kinds:
        out.append({"kind": "relations", "text": "원국 안에서 확인되는 간지 관계 후보는 " + ", ".join(f"{k} {v}개" for k, v in kinds.items()) +
                    "입니다. 관계가 있다는 사실과 실제로 작용하는 정도는 다르며 이 단계에서는 작용을 확정하지 않습니다.", "claim_ids": [r["claim_id"] for r in l2["relations"]][:4]})
    return out


def question_context(pre: dict, question: str, ys: list[int]) -> dict:
    found = []
    for pat, ev in EVENT_KEYWORDS:
        if re.search(pat, question or "") and ev not in found:
            found.append(ev)
    items = []
    for ev in found:
        j = pre["event_judgements"].get(ev)
        if j is None:
            items.append({"event": ev, "in_precommit": False,
                          "text": f"'{ev}' 관련 분야는 사전 분석 기록에 포함되지 않았습니다. 지금 소급해서 판단하지 않으며, 필요하면 해당 분야를 포함한 새 상담 기록을 만들어야 합니다."})
            continue
        ytxt = "; ".join(f"{y}년은 {STATE_KO[v['state']]}" for y, v in j["years"].items() if int(y) in ys) if ys else ""
        items.append({"event": ev, "in_precommit": True, "natal": j["natal"], "years": {y: v["state"] for y, v in j["years"].items() if int(y) in ys},
                      "text": f"질문하신 '{ev}' 주제에 대한 사전 분석 기록의 판단은 다음과 같습니다. 원국에서는 {STATE_KO[j['natal']]}(근거 구조: {', '.join(j['basis_structures'])})."
                              + (f" 요청 연도별로는 {ytxt}." if ytxt else "") + " 구조가 있다는 것과 실제로 일어난다는 것은 다릅니다."})
    return {"question": (question or "")[:200], "events": found, "items": items}


def compose_paragraphs(features, blocks, periods, ctx, school_view, depth) -> list[dict]:
    paras = []
    fs = features[: 3 if depth == "summary" else len(features)]
    paras.append({"kind": "features", "text": "먼저 원국의 특징입니다. " + " ".join(f["text"] for f in fs), "claim_ids": [c for f in fs for c in f["claim_ids"]]})
    for it in ctx["items"]:
        paras.append({"kind": "context", "text": it["text"], "claim_ids": []})
    for b in blocks:
        cids = [i["claim_id"] for i in b["structures"] if i["label"] != "없음"]
        txt = b["easy_text"]
        if b["evidence_against"]:
            txt += " 반대로 보는 근거로는 " + "; ".join(e.split(": ", 1)[1] if ": " in e else e for e in b["evidence_against"][:2]) + " 등이 있습니다."
        paras.append({"kind": "domain", "domain": b["domain"], "text": txt, "claim_ids": cids})
    link = compose_domains.cross_links(blocks)
    if link and len(blocks) > 1:
        paras.append({"kind": "cross", "text": link, "claim_ids": []})
    for pe in periods:
        for sg in pe["segments"]:
            paras.append({"kind": "period", "year": pe["year"], "text": sg["text"], "claim_ids": []})
        groups: dict[tuple, list[str]] = {}
        for b in blocks:  # 분야마다 보는 궁위가 달라 문장이 달라지고, 궁위가 같아 내용이 같으면 한 문단으로 묶어 반복하지 않는다
            notes = tuple(dict.fromkeys(n for sg in pe["segments"] for n in compose_domains.period_palace_notes(b["domain"], sg.get("relations", []))))
            if notes:
                groups.setdefault(notes, []).append(b["name"])
        for notes, names in groups.items():
            lead = "·".join(names) + (" 공통" if len(names) > 1 else "")
            paras.append({"kind": "domain_period", "domain": names[0], "year": pe["year"], "text": f"{pe['year']}년 {lead} 관점: " + "; ".join(notes) + ".", "claim_ids": []})
    if school_view and depth != "summary":
        paras.append({"kind": "schools", "text": "학파별로 보면 " + " ".join(school_view["per_school"]) + " " + " ".join(school_view["relations"]), "claim_ids": []})
    paras.append({"kind": "closing", "text": "이 설명은 전통 명리학의 구조 해석이며, 사전 분석 기록을 바꾸지 않고 질문에 맞춰 풀어 쓴 것입니다. 현실 사정은 아래 조언 부분에서 따로 다룹니다.", "claim_ids": []})
    return paras


def check_consistency(ans: dict, pre: dict) -> list[str]:
    """인용 claim_id 존재, 구조 라벨 일치(없는 구조를 있는 것처럼 언급 금지), 요청 연도, 고지 포함 여부."""
    problems = []
    base = pre["natal_structure"]
    ids = {n["claim_id"] for n in base["graph"]["nodes"]}
    lab = {s["name"]: s["label"] for s in base["layer3"]["structures"]}
    for i, p in enumerate(ans["paragraphs"]):
        for c in p["claim_ids"]:
            if c not in ids:
                problems.append(f"문단{i}: 존재하지 않는 claim_id {c}")
        if p["kind"] in ("features", "domain"):
            for nm in L3_NAMES:
                m = re.search(r"'" + nm + r"'\(([^)]*\)?[^)]*)\)", p["text"])
                if m and not m.group(1).startswith(lab.get(nm, "?").split("(")[0]):
                    problems.append(f"문단{i}: '{nm}' 라벨 불일치({m.group(1)} ≠ {lab.get(nm)})")
    asked = set(ans.get("years", []))
    for pe in ans["periods"]:
        if pe["year"] not in asked:
            problems.append(f"요청하지 않은 연도 {pe['year']}")
    if "명리학은 과학적으로 검증된 미래 예측 방법이 아닙니다" not in " ".join(ans["limits"]):
        problems.append("고지 누락")
    return problems


def analysis_procedure(pre: dict, periods: list[dict], doms: list[str], consistency_ok: bool, n_paragraphs: int) -> list[dict]:
    """특정 연도 상담에서 실제로 수행된 단계 기록(§4.2). 계산 단계는 미검증 범위를 함께 표시한다."""
    v = pre["verification"]
    steps = []
    for pe in periods:
        lucks = [s["luck"] for s in pe["segments"]]
        luck_set = list(dict.fromkeys(l for l in lucks if l))
        sewun = list(dict.fromkeys(s["sewun"] for s in pe["segments"]))
        bnames = [b for s in pe["segments"] for b in s.get("boundaries", [])]
        steps.append({"step": "세운 계산", "year": pe["year"], "detail": f"{pe['year']}년 구간별 세운: {', '.join(sewun)} (입춘 이전은 직전 해 세운)"})
        steps.append({"step": "입춘 전후 구분", "year": pe["year"], "detail": f"구간 {len(pe['segments'])}개" + (f" — 경계: {', '.join(dict.fromkeys(bnames))}" if bnames else "")})
        steps.append({"step": "적용 대운 계산", "year": pe["year"], "detail": "대운: " + (", ".join(luck_set) if luck_set else "첫 대운 시작 전")})
        steps.append({"step": "대운 교체 기간 분할", "year": pe["year"], "detail": "연중 대운 교체 있음 — 기간 분할" if len(luck_set) > 1 else "연중 대운 교체 없음"})
        n_rel = sum(len(s.get("relations", [])) for s in pe["segments"])
        steps.append({"step": "원국-운 관계 분석", "year": pe["year"], "detail": f"새 관계 후보 {n_rel}개(존재만 확인)"})
    steps.append({"step": "종합운 생성", "detail": "포함" if "overall" in doms else "선택하지 않음(개별 분야만)"})
    steps.append({"step": "선택 분야 해석", "detail": ", ".join(doms)})
    steps.append({"step": "정·반 근거 및 모순 검증", "detail": "통과" if consistency_ok else "일부 문단 제외"})
    steps.append({"step": "쉬운 설명 작성", "detail": f"문단 {n_paragraphs}개"})
    steps.append({"step": "검증 상태 고지", "detail": f"판정 {v['status']}, 미검증 안내 {len(v.get('unverified_notice', []))}건 — 미검증 계산은 확정값으로 표시하지 않음"})
    return steps


STATUS_KO = {"text_confirmed": "원문 확인(표시한 범위)", "location_confirmed": "원문 위치만 확인", "implementer_convention": "구현자 규약(고전 근거 아님)", "pending": "확인 전"}


def classical_basis(pre: dict, paragraphs: list[dict]) -> list[dict]:
    """답변이 인용한 근거 노드의 규칙별 고전 출처. 확인되지 않은 규칙은 상태를 그대로 드러내고 고전 근거처럼 쓰지 않는다."""
    from ..mingli.rules import RULES
    node_rule = {n["claim_id"]: n["rule_id"] for n in pre["natal_structure"]["graph"]["nodes"]}
    seen: dict[str, dict] = {}
    for p in paragraphs:
        for c in p["claim_ids"]:
            rid = node_rule.get(c)
            if not rid or rid in seen:
                continue
            r = RULES[rid]
            loc = next((x for x in r["sources"] if x.get("type") == "classical_text"), None)
            ev = r.get("engine_vs_classical")
            seen[rid] = {"rule_id": rid, "name": r["name"], "status": r["classical_status"], "status_ko": STATUS_KO[r["classical_status"]], "claim_ids": [],
                         "work": loc and loc["work"], "section": loc and loc["section"], "url": loc and loc["url"], "excerpt": loc and loc.get("original_excerpt"),
                         "scope_note": loc and loc.get("scope_note"), "school": r.get("school_id"), "engine_difference": ev and {"kind": ev["kind"], "note": ev["note"]},
                         "knowledge_file": next((x["file"] for x in r["sources"] if x.get("type") == "repo_knowledge"), None)}
        # 같은 규칙을 인용한 claim 을 모아 둔다
    for p in paragraphs:
        for c in p["claim_ids"]:
            rid = node_rule.get(c)
            if rid in seen and c not in seen[rid]["claim_ids"]:
                seen[rid]["claim_ids"].append(c)
    return list(seen.values())
