"""선택적 LLM 자연어 계층. 계산·규칙 판단은 LLM 에 맡기지 않는다.

계약
- 입력: 결정론적 상담 결과(answer)에서 뽑은 '허용 사실 집합'(구조 이름·라벨·간지·연도·claim_id·용어)과 문단 초안.
- 출력: 한국어 상담 문장. 출력이 허용 집합 밖의 명리 주장(용어·간지·연도·claim_id)을 만들거나 금지 표현을 쓰면 **검증 실패**.
- 실패·예외·시간 초과 시 결정론적 상담문(answer["narrative"])을 그대로 쓰고 사유를 기록한다.
- 이 모듈은 외부 LLM 을 호출하지 않는다. 실제 어댑터(Narrator 구현)는 별도 승인·키 설정 후 연결한다(기본 CONSULT_LLM=off).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Protocol

from ..report_checks import FIXED_DISCLAIMER, FORBIDDEN_PATTERNS
from . import domains as D

STEMS, BRANCHES = "甲乙丙丁戊己庚辛壬癸", "子丑寅卯辰巳午未申酉戌亥"
GANZHI = {STEMS[i % 10] + BRANCHES[i % 12] for i in range(60)}
SHIPSUNG = ["比肩", "劫財", "食神", "傷官", "偏財", "正財", "七殺", "正官", "偏印", "正印", "비견", "겁재", "식신", "상관", "편재", "정재", "칠살", "편관", "정관", "편인", "정인",
            "비겁", "식상", "재성", "관성", "인성"]
STRUCT_TERMS = ["식상생재", "재생관", "관인상생", "살인상생", "상관견관", "군겁쟁재", "상관패인", "식신제살", "재극인", "탈재", "편인도식", "제겁", "화겁생재",
                "격국", "용신", "억부용신", "조후용신", "격국용신", "통근", "투간", "득령", "실령", "월령", "대운", "세운", "합화", "천간합", "육합", "삼합", "방합", "충", "형", "파", "해",
                "건록격", "양인격", "정관격", "칠살격", "정인격", "편인격", "식신격", "상관격", "정재격", "편재격", "성격", "파격", "구응", "개고", "입묘", "신강", "신약", "조후"]
# 근거 구조에 없는 신살·기타 명리 주장은 전부 '허용 밖'으로 취급하기 위한 어휘
OTHER_MYEONGRI = ["귀인", "천을귀인", "도화", "역마", "화개", "공망", "원진", "백호", "양인살", "홍염", "문창", "학당", "괴강", "천덕", "월덕", "삼재", "대살", "상문", "조객",
                  "궁합", "택일", "작명", "부적", "액운", "팔자가 세다", "관재", "구설"]
LEXICON = sorted(set(SHIPSUNG + STRUCT_TERMS + OTHER_MYEONGRI), key=len, reverse=True)


@dataclass
class AllowedFacts:
    terms: set[str] = field(default_factory=set)
    ganzhi: set[str] = field(default_factory=set)
    years: set[int] = field(default_factory=set)
    claim_ids: set[str] = field(default_factory=set)


class Narrator(Protocol):
    name: str

    def narrate(self, payload: dict) -> str: ...


def allowed_from_answer(ans: dict) -> AllowedFacts:
    """결정론적 답변에 실제로 나온 사실만 허용한다."""
    text = " ".join([ans.get("summary_easy", "")] + [p["text"] for p in ans.get("paragraphs", [])] + ans.get("evidence_for", []) + ans.get("evidence_against", [])
                    + [s["text"] for pe in ans.get("periods", []) for s in pe["segments"]] + list((ans.get("school_view") or {}).get("per_school", [])) +
                    list((ans.get("school_view") or {}).get("relations", [])) + list(ans.get("glossary", {})) + [f for f in ans.get("natal_features", [])
                    if isinstance(f, str)] + [f["text"] for f in ans.get("natal_feature_items", [])])
    a = AllowedFacts()
    a.terms = {t for t in LEXICON if t in text} | set(D.GLOSSARY) & {t for t in D.GLOSSARY if t in text}
    a.ganzhi = {g for g in GANZHI if g in text}
    a.years = {int(y) for y in re.findall(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)", text)} | set(ans.get("years", []))
    a.claim_ids = set(re.findall(r"\b[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{3}\b", text))
    return a


def validate_llm_text(text: str, allowed: AllowedFacts) -> list[str]:
    problems = []
    if not text or not text.strip():
        return ["빈 출력"]
    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, text):
            problems.append(f"금지 표현 패턴: {pat}")
    for t in LEXICON:
        # 짧은 한 글자 용어(충·형·파·해)는 일반 단어와 겹치므로 앞뒤가 한글이 아닐 때만 용어로 취급
        pat = re.escape(t) if len(t) > 1 else rf"(?<![가-힣]){re.escape(t)}(?![가-힣])"
        if re.search(pat, text) and t not in allowed.terms and not any(t in a or a in t for a in allowed.terms if len(a) > 1 and len(t) > 1):
            problems.append(f"근거 없는 명리 용어: {t}")
    for g in GANZHI:
        if g in text and g not in allowed.ganzhi:
            problems.append(f"근거 없는 간지: {g}")
    for y in re.findall(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)", text):
        if int(y) not in allowed.years:
            problems.append(f"근거 없는 연도: {y}")
    for cid in re.findall(r"\b[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{3}\b", text):
        if cid not in allowed.claim_ids:
            problems.append(f"존재하지 않는 claim_id: {cid}")
    if re.search(r"(확실|틀림없|100%|보장|무조건)", text):
        problems.append("단정·보장 표현")
    return sorted(set(problems))


def enabled() -> bool:
    return os.environ.get("CONSULT_LLM", "off").lower() not in ("off", "", "0", "false")


def with_llm(ans: dict, narrator: Narrator | None, *, force: bool = False) -> dict:
    """결정론적 답변에 LLM 서술을 선택적으로 덧붙인다. 실패해도 결정론적 서술이 최종 출력이다."""
    out = dict(ans)
    base = "\n\n".join(p["text"] for p in ans.get("paragraphs", [])) or ans.get("summary_easy", "")
    out["narrative_final"] = base
    out["llm"] = {"used": False, "status": "disabled", "model": None, "problems": []}
    if ans.get("refused") or narrator is None or not (enabled() or force):
        return out
    payload = {"allowed_note": "허용된 사실만 사용. 새 명리 주장 금지", "paragraphs": ans["paragraphs"], "question": ans.get("question_context"),
               "limits": ans["limits"]}
    try:
        text = narrator.narrate(payload)
    except Exception as e:  # 네트워크·시간 초과·모델 오류 등
        out["llm"] = {"used": False, "status": "error_fallback", "model": getattr(narrator, "name", "?"), "problems": [repr(e)[:200]]}
        return out
    problems = validate_llm_text(text, allowed_from_answer(ans))
    if FIXED_DISCLAIMER not in text and "예측" not in text:
        text += "\n\n" + FIXED_DISCLAIMER + "."   # 고지는 LLM 이 빠뜨려도 코드가 붙인다
    if problems:
        out["llm"] = {"used": False, "status": "failed_validation_fallback", "model": getattr(narrator, "name", "?"), "problems": problems,
                      "rejected_text_chars": len(text)}
        return out
    out["narrative_final"] = text
    out["llm"] = {"used": True, "status": "validated", "model": getattr(narrator, "name", "?"), "problems": []}
    return out
