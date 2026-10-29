"""Consult-Agent (결정론적 템플릿 버전). LLM 호출 없음 — 구조 JSON 의 claim 만 인용해 쉬운 한국어로 설명한다.

흐름: ① 사전 분석 기록(precommit) 생성·고정 → ② 질문/분야/연도 → 원국 구조 설명(정·반 근거) → ③ 필요한 현실 변수 1~2개 질문
      → ④ 현실 조언(명리 해석과 분리) → ⑤ 후속 질문·현실 사건 입력은 기록만 하고 precommit 을 바꾸지 않는다.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timezone

from ..astro_core import engine as astro
from ..mingli import RULESET_VERSION, analyze_periods, analyze_structure
from ..report_checks import FIXED_DISCLAIMER, FORBIDDEN_PATTERNS
from . import compose, compose_domains
from . import domains as D
from . import store

CONSULT_VERSION = "consult-0.1.0"
MODEL_VERSION = "deterministic-template (LLM 미사용)"
DEPTHS = ("summary", "detailed", "expert")
FOLLOWUPS = {
    "wealth": ["현재 주된 수입원은 근로소득과 사업소득 중 어느 쪽인가요?", "올해 큰 지출이나 계약 계획이 있나요?"],
    "career": ["지금 직무와 근무 형태(조직·프리랜서 등)는 무엇인가요?", "이직이나 보직 변경을 고민하는 시기가 있나요?"],
    "business": ["지금 사업을 하고 있나요, 준비 중인가요?", "혼자 하시나요, 동업인가요?"],
    "docs_realestate": ["계약이나 거래 예정 시기가 있나요?", "매매·임대 중 어떤 유형인가요?"],
    "luck": ["특히 살펴보고 싶은 연도나 기간이 있나요?"], "overall": ["가장 궁금한 분야 한 가지를 고르시겠어요?"],
}
ADVICE = {  # 사주 해석이 아니라 일반 생활 조언
    "wealth": "수입과 지출을 한 달만 기록해 보고, 비상 자금(생활비 몇 달분)을 먼저 확보해 두세요.",
    "career": "하고 싶은 일과 가능한 일의 목록을 만들고, 이직·보직 변경은 정보 수집 후 결정하세요.",
    "business": "시작 전에 최소 비용으로 시험해 보고, 계약서와 정산 방식을 문서로 남기세요.",
    "docs_realestate": "계약 전에는 조건을 문서로 확인하고 전문가(법무사·공인중개사)의 검토를 받으세요.",
    "luck": "특정 해에 몰아서 큰 결정을 하기보다 평소 준비와 일정 여유를 챙기세요.", "overall": "관심 분야 한 가지부터 차근차근 점검해 보세요.",
}


def redact_chart(chart: dict) -> dict:
    """저장용: 출생 원문과 출생 시각이 드러나는 필드를 제거한다(명식·대운·검증 요약만 남김)."""
    keep = {k: chart[k] for k in ("variants", "verification", "calculation_profile_id", "zi_profile", "pillars", "libraries", "warnings") if k in chart}
    d = chart["daeun"]
    keep["daeun"] = {k: d[k] for k in ("calculation_profile_id", "direction", "first_luck_date", "cycles")}
    return keep


def build_precommit(chart: dict, *, variant_id: str, years: list[int], domains: list[str], depth: str, input_fingerprint: dict, store_birth: bool = False,
                    gender: str | None = None) -> dict:
    if depth not in DEPTHS:
        raise ValueError("depth 는 summary|detailed|expert")
    v = next((x for x in chart["variants"] if x["variant_id"] == variant_id), None)
    if v is None:
        raise ValueError("알 수 없는 variant_id")
    if len(chart["variants"]) > 1 and variant_id is None:
        raise ValueError("variant_id 필요")
    gender = gender or (chart.get("input") or {}).get("gender")
    base = analyze_structure(v["pillars"], v["variant_id"])
    periods = analyze_periods(chart, years, v["variant_id"]) if years else None
    ranks = {s["name"]: s["rank"] for s in base["layer3"]["structures"]}
    gc = base["layer1"]["support_structure"]["group_counts"]
    # 사건 유형별 사전 판단(원국 + 요청 연도). 여기 없는 유형은 이후 상담에서 판단 대상이 아니다.
    judged: dict = {}
    for dom in domains:
        for ev in D.DOMAINS.get(dom, {}).get("events", []):
            structs, groups = D.EVENT_RULE[ev]
            if ev in D.SPECIAL_EVENTS:
                natal = compose_domains.special_event_state(ev, base, gender)
            else:
                r = max((ranks.get(s, 0) for s in structs), default=0)
                gv = any(gc[g]["visible"] for g in groups) if groups else False
                natal = "indicated" if r >= 2 else ("weak" if (r == 1 or gv) else "not_indicated")
            yrs = {}
            for y in years:
                st = natal
                reasons = []
                if periods:
                    for seg in periods["periods"]["per_year"][y]["segments"]:
                        for d in seg["analysis"]["structure_delta"]:
                            if d["structure"] in structs and d["change"] in ("강화", "신규 출현"):
                                reasons.append(f"{seg['from']}~{seg['to']} {d['structure']} {d['change']}")
                if reasons and natal != "indicated":
                    st = "indicated" if natal == "weak" else "weak"
                yrs[str(y)] = {"state": st, "reasons": reasons}
            judged[ev] = {"natal": natal, "years": yrs, "basis_structures": structs, "rule": "구현자 규약(고전 대조 전)"}
    pre = {
        "schema": "consult-precommit/1", "consult_version": CONSULT_VERSION, "ruleset_version": RULESET_VERSION, "engine_version": astro.CALC_VERSION,
        "model_version": MODEL_VERSION, "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_hash": hashlib.sha256((secrets.token_hex(8) + store.canonical(input_fingerprint).decode()).encode()).hexdigest(),
        "calculation_profile_id": chart["calculation_profile_id"], "variant_id": v["variant_id"], "variants_count": len(chart["variants"]),
        "verification": chart["verification"], "depth": depth, "domains": domains, "years": years,
        "natal_structure": base, "periods": periods, "event_judgements": judged,
        "chart": redact_chart(chart) if not store_birth else chart,
        "disclaimer": FIXED_DISCLAIMER, "reality_inputs_used": False, "gender": gender,
    }
    return pre


# ------------------------------------------------------------------ 설명 생성
def _node(base: dict, cid: str) -> dict:
    return next(n for n in base["graph"]["nodes"] if n["claim_id"] == cid)


def _domain_block(pre: dict, dom: str) -> dict:
    base = pre["natal_structure"]
    spec = D.DOMAINS[dom]
    items, for_, against = [], [], []
    for name in spec["structures"]:
        s = next(x for x in base["layer3"]["structures"] if x["name"] == name)
        n = _node(base, s["claim_id"])
        items.append({"structure": name, "label": s["label"], "claim_id": s["claim_id"]})
        if s["rank"]:
            for e in n["supporting_evidence"][:3]:
                for_.append(f"[{s['claim_id']}] {name}: {e}")
        for e in n["counter_evidence"][:3]:
            against.append(f"[{s['claim_id']}] {name}: {e}")
    present = [i for i in items if i["label"] != "없음"]
    extra = compose_domains.domain_extra(dom, pre) if spec.get("kind") == "palace" else None
    if extra:
        for_ += [e for e in extra["evidence_for"]]
        against += [e for e in extra["evidence_against"]]
        text = extra["text"]
        if present:
            text += " 생극제화 구조로는 " + ", ".join(f"'{i['structure']}'({i['label']})" for i in present) + "이(가) 함께 참고됩니다."
        if against:
            text += " 반대로 보는 근거도 함께 있어 한쪽으로 단정하지 않습니다."
        return {"domain": dom, "name": spec["name"], "structures": items, "easy_text": text, "evidence_for": for_, "evidence_against": against,
                "extra_claim_ids": extra["claim_ids"]}
    if present:
        parts = ", ".join(f"'{i['structure']}'({i['label']})" for i in present)
        text = f"{spec['name']}과 관련해 원국에서 전통 해석상 눈에 띄는 구조는 {parts}입니다."
        if against:
            text += " 다만 같은 구조에 대해 반대로 보는 근거도 함께 있어 한쪽으로 단정하지 않습니다."
    else:
        text = f"{spec['name']}과 직접 연결되는 뚜렷한 구조는 원국에서 확인되지 않았습니다. 이는 해당 분야가 나쁘다는 뜻이 아니라 이 해석 틀에서 특별히 짚을 구조가 없다는 뜻입니다."
    return {"domain": dom, "name": spec["name"], "structures": items, "easy_text": text, "evidence_for": for_, "evidence_against": against}


def _period_block(pre: dict, years: list[int], chart_fallback: dict | None = None) -> list[dict]:
    out = []
    for y in years:
        per = (pre.get("periods") or {}).get("periods", {}).get("per_year", {}).get(str(y)) or (pre.get("periods") or {}).get("periods", {}).get("per_year", {}).get(y)
        precommitted = per is not None
        if per is None:
            res = analyze_periods(pre["chart"], [y], pre["variant_id"])
            per = res["periods"]["per_year"][y]
        segs = []
        for s in per["segments"]:
            rel = s["analysis"]["relations"]
            n_rel = sum(len(v) for k, v in rel.items() if not k.endswith("_claim"))
            kinds = sorted({x["type"] for k, v in rel.items() if not k.endswith("_claim") for x in v})
            delta = [f"{d['structure']} {d['change']}" for d in s["analysis"]["structure_delta"]]
            lk = s["luck"].get("pillar")
            text = (f"{s['from']}~{s['to']}: " + (f"대운 {lk}, " if lk else "첫 대운 시작 전, ") + f"세운 {s['sewun_pillar']}. "
                    f"원국과 새로 생기는 관계 후보가 {n_rel}개({', '.join(kinds) or '없음'})이며, 구조 변화는 {', '.join(delta) or '확인되지 않음'}입니다.")
            raw = [{"who": who, "type": x["type"], "with": x["with"], "chars": x["chars"]} for who, lst in rel.items() if not who.endswith("_claim") for x in lst]
            segs.append({"from": s["from"], "to": s["to"], "luck": lk, "sewun": s["sewun_pillar"], "text": text, "boundaries": s["starts_at_boundary"], "relations": raw})
        out.append({"year": y, "precommitted": precommitted, "split": len(segs) > 1, "segments": segs,
                    "note": "한 해가 대운 교체·입춘으로 나뉘어 구간별로 설명합니다." if len(segs) > 1 else ""})
    return out


def _check_safe(text: str) -> None:
    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, text):
            raise AssertionError(f"금지 표현 패턴 검출: {pat}")


def answer(pre: dict, question: str, *, domains_: list[str] | None = None, years: list[int] | None = None, depth: str | None = None) -> dict:
    ref = {"precommit_hash": pre["content_hash"], "precommit_generated_at": pre["generated_at"], "ruleset_version": pre["ruleset_version"],
           "calculation_profile_id": pre["calculation_profile_id"], "variant_id": pre["variant_id"]}
    rf = D.refusal(question)
    if rf:
        return {"refused": True, **rf, "ref": ref, "limits": [FIXED_DISCLAIMER]}
    depth = depth or pre["depth"]
    doms = D.route(question, domains_)
    ys = sorted(set((years or []) + D.extract_years(question)))
    if "luck" in doms and not ys:
        ys = list(pre["years"])
    blocks = [_domain_block(pre, d) for d in doms if d != "luck"]
    periods = _period_block(pre, [y for y in ys if 1901 <= y <= 2049]) if ys else []
    base = pre["natal_structure"]
    sch = base["schools"]
    summary = " ".join(b["easy_text"] for b in blocks) or "대운·세운 흐름을 구간별로 설명합니다."
    if periods:
        summary += " 요청하신 연도는 입춘과 대운 교체일을 기준으로 구간을 나누어 살펴봤고, 새 구조 변화는 '가능한 전통적 주제'일 뿐 사건 예측이 아닙니다."
    out = {
        "refused": False, "ref": ref, "domains": doms, "years": ys, "depth": depth,
        "summary_easy": summary, "blocks": blocks, "periods": periods,
        "evidence_for": [e for b in blocks for e in b["evidence_for"]], "evidence_against": [e for b in blocks for e in b["evidence_against"]],
        "school_view": sch["natural_language"] if depth != "summary" else None,
        "followup_questions": [q for d in doms for q in FOLLOWUPS.get(d, [])][:2],
        "followup_note": "답해 주신 현실 정보는 조언에만 쓰이며 사주 해석(사전 분석 기록)을 바꾸지 않습니다.",
        "life_advice": {"label": "현실 조언(명리 해석 아님)", "items": [ADVICE[d] for d in doms if d in ADVICE]},
        "glossary": {t: g for t, g in D.GLOSSARY.items() if any(t in b["easy_text"] or t in " ".join(b["evidence_for"] + b["evidence_against"]) for b in blocks) or (t in ("대운", "세운") and periods)},
        "limits": [FIXED_DISCLAIMER, "이 내용은 전통 명리학의 해석이며 미래를 예측하거나 결과를 보장하지 않습니다.", *pre["verification"].get("unverified_notice", [])],
    }
    if depth == "expert":
        out["expert"] = {"rule_ids": sorted({n["rule_id"] for n in base["graph"]["nodes"]}), "claims": [i["claim_id"] for b in blocks for i in b["structures"]],
                         "schools": sch["pairs"], "variants_count": pre["variants_count"], "classical_status": "원문 대조 전 규칙 다수(pending)"}
    feats = compose.natal_features(pre)
    ctx = compose.question_context(pre, question, ys)
    out["natal_feature_items"] = feats
    out["question_context"] = ctx
    out["paragraphs"] = compose.compose_paragraphs(feats, blocks, periods, ctx, out["school_view"], depth)
    probs = compose.check_consistency(out, pre)
    if probs:  # 모순 문단은 내보내지 않고 사유를 남긴다
        bad = {int(re.match(r"문단(\d+)", x).group(1)) for x in probs if x.startswith("문단")}
        out["paragraphs"] = [q for i, q in enumerate(out["paragraphs"]) if i not in bad]
    out["consistency"] = {"ok": not probs, "problems": probs}
    out["classical_basis"] = compose.classical_basis(pre, out["paragraphs"])
    out["procedure"] = compose.analysis_procedure(pre, periods, doms, not probs, len(out["paragraphs"]))
    out["narrative"] = "\n\n".join(q["text"] for q in out["paragraphs"])
    if depth == "expert":
        out["expert"]["classical_conflicts"] = base["classical_conflicts"]
        out["expert"]["profiles"] = base["profiles"]
    _check_safe(summary + " " + out["narrative"] + " ".join(out["life_advice"]["items"]) + " ".join(out["limits"]))
    return out


# ------------------------------------------------------------------ 현실 사건 (사후 끼워 맞추기 방지)
OUTCOMES = ("consistent", "inconsistent", "not_judged", "condition_changed")


def classify_event(pre: dict, event: dict) -> dict:
    """event: {kind:'event'|'condition', type, year}. precommit 의 사전 판단과만 비교한다. 새 유형 추가·기대값 수정 없음."""
    base = {"precommit_hash": pre["content_hash"], "event": {k: event.get(k) for k in ("kind", "type", "year")}}
    if event.get("kind") == "condition":
        return {**base, "outcome": "condition_changed",
                "explanation": "입력 조건(출생 정보·시각 등)이 바뀌면 사전 분석 기록을 고치지 않고 새 상담(revision)으로 다시 분석해야 합니다. 기존 기록은 그대로 보존됩니다."}
    j = pre["event_judgements"].get(event.get("type"))
    if j is None:
        return {**base, "outcome": "not_judged", "explanation": "사전 분석 기록에서 판단하지 않은 사건 유형입니다. 지금 새로 해석해 적중으로 세지 않습니다."}
    y = str(event.get("year"))
    if y not in j["years"]:
        return {**base, "outcome": "not_judged", "explanation": "사전 분석 기록에 포함되지 않은 기간입니다."}
    st = j["years"][y]["state"]
    if st in ("indicated", "weak"):
        return {**base, "outcome": "consistent", "strength": st, "explanation": f"사전 기록에서 '{event['type']}' 관련 구조가 {'뚜렷' if st == 'indicated' else '약하게'} 있다고 판단되어 있었습니다(근거: {', '.join(j['basis_structures'])}). 구조가 있다는 것과 사건이 일어난다는 것은 다르며 예측 적중으로 계산하지 않습니다.",
                "reasons": j["years"][y]["reasons"]}
    return {**base, "outcome": "inconsistent", "explanation": f"사전 기록에서 '{event['type']}' 관련 구조는 근거가 없다고 판단되어 있었습니다. 기록은 수정하지 않으며, 해석 틀의 한계로 남깁니다."}



def structure_diff(old: dict, new: dict) -> dict:
    """두 사전 분석 기록의 구조 판단 차이(규칙 버전·프로필 변경 시 무엇이 바뀌었는지)."""
    def lab(p):
        b = p["natal_structure"]
        return {s["name"]: s["label"] for s in b["layer3"]["structures"]}, b["layer4"]["gyeokguk"]["tugan_priority"], {k: v["status"] for k, v in b["layer4"]["seongpa"].items()},             {k: v["yongshin_candidates"] for k, v in b["schools"]["schools"].items()}, len(b["layer2"]["relations"])
    a, b = lab(old), lab(new)
    return {"structures_changed": {k: [a[0][k], b[0].get(k)] for k in a[0] if a[0][k] != b[0].get(k)}, "gyeokguk": [a[1], b[1]] if a[1] != b[1] else None,
            "seongpa": [a[2], b[2]] if a[2] != b[2] else None, "yongshin_changed": {k: [a[3][k], b[3].get(k)] for k in a[3] if a[3][k] != b[3].get(k)},
            "relation_count": [a[4], b[4]] if a[4] != b[4] else None, "ruleset": [old["ruleset_version"], new["ruleset_version"]],
            "event_judgements_changed": {k: [old["event_judgements"][k]["natal"], new["event_judgements"].get(k, {}).get("natal")] for k in old["event_judgements"]
                                         if old["event_judgements"][k]["natal"] != new["event_judgements"].get(k, {}).get("natal")}}


def reanalyze(base_pre: dict, *, reason: str, profiles: dict | None = None) -> tuple[dict, dict]:
    """저장된 명식(redacted chart)으로 현재 규칙 버전·프로필로 다시 분석한 새 기록과 원본 대비 차이를 만든다. 현실 입력은 사용하지 않는다."""
    chart = base_pre["chart"]
    new = build_precommit(chart, variant_id=base_pre["variant_id"], years=base_pre["years"], domains=base_pre["domains"], depth=base_pre["depth"],
                          input_fingerprint={"reanalysis_of": base_pre["content_hash"]}, store_birth=True, gender=base_pre.get("gender"))
    if profiles:
        v = next(x for x in chart["variants"] if x["variant_id"] == base_pre["variant_id"])
        new["natal_structure"] = analyze_structure(v["pillars"], v["variant_id"], profiles)
    new["reanalysis"] = {"of": base_pre["content_hash"], "reason": reason, "profiles": profiles or {}}
    return new, structure_diff(base_pre, new)
