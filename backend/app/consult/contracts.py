"""공급업체에 독립적인 LLM 연결 계약. 이 모듈은 외부 API 를 호출하지 않는다.

흐름: 결정론적 상담(answer) → EvidenceBundle(허용 사실·문단 초안·고지) → Provider.generate(request, bundle) → ConsultationDraft
      → validate(draft, bundle) → ValidatedResponse(최종 출력). 검증 실패·예외·시간 초과면 결정론적 상담문으로 대체한다.
LLM 은 자연어 표현만 담당한다. 만세력 계산·명리 규칙 판정·고전 인용 생성은 하지 않는다.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Protocol

from ..report_checks import FIXED_DISCLAIMER
from . import llm as L


@dataclass(frozen=True)
class EvidenceBundle:
    """LLM 에 줄 수 있는 모든 것. 출생 원문·명식 전체·토큰은 포함하지 않는다(구조 JSON 에서 뽑은 문단과 허용 사실만)."""
    precommit_hash: str
    ruleset_version: str
    paragraphs: tuple[dict, ...]              # {kind, text, claim_ids}
    allowed_terms: frozenset[str]
    allowed_ganzhi: frozenset[str]
    allowed_years: frozenset[int]
    allowed_claim_ids: frozenset[str]
    classical_status: dict                    # {claim_id/rule 요약: 원문 검증 상태} — 확정되지 않은 규칙을 고전 근거처럼 쓰지 못하게 하는 정보
    limits: tuple[str, ...]
    fallback_text: str                        # 결정론적 대체 출력

    def to_prompt_payload(self) -> dict:
        return {"paragraphs": [dict(p) for p in self.paragraphs], "limits": list(self.limits), "rules": "허용된 사실만 사용. 새 명리 용어·간지·연도·claim_id 금지. 예측·보장·단정 금지"}


@dataclass(frozen=True)
class ConsultationRequest:
    question: str
    depth: str = "detailed"
    domains: tuple[str, ...] = ()
    years: tuple[int, ...] = ()
    style: str = "easy_korean"                # 일반인 이해 우선
    max_chars: int = 4000


@dataclass
class ConsultationDraft:
    text: str
    provider: str
    model: str = ""
    usage: dict = field(default_factory=dict)  # 토큰·비용 추적용 (실제 호출 시 채움)


@dataclass
class ValidatedResponse:
    text: str
    source: str                                # "provider" | "deterministic_fallback"
    ok: bool
    provider: str
    model: str
    problems: list[str] = field(default_factory=list)
    bundle_hash: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class ConsultationProvider(Protocol):
    name: str

    def generate(self, request: ConsultationRequest, bundle: EvidenceBundle) -> ConsultationDraft: ...


def build_bundle(ans: dict, pre: dict) -> EvidenceBundle:
    from ..mingli.rules import RULES
    allowed = L.allowed_from_answer(ans)
    cls = {rid: r["classical_status"] for rid, r in RULES.items()}
    node_rule = {n["claim_id"]: n["rule_id"] for n in pre["natal_structure"]["graph"]["nodes"]}
    used = {node_rule[c]: cls[node_rule[c]] for p in ans.get("paragraphs", []) for c in p["claim_ids"] if c in node_rule}
    return EvidenceBundle(
        precommit_hash=pre["content_hash"], ruleset_version=pre["ruleset_version"],
        paragraphs=tuple({"kind": p["kind"], "text": p["text"], "claim_ids": list(p["claim_ids"])} for p in ans.get("paragraphs", [])),
        allowed_terms=frozenset(allowed.terms), allowed_ganzhi=frozenset(allowed.ganzhi), allowed_years=frozenset(allowed.years),
        allowed_claim_ids=frozenset(allowed.claim_ids), classical_status=used, limits=tuple(ans["limits"]),
        fallback_text="\n\n".join(p["text"] for p in ans.get("paragraphs", [])))


def validate(draft: ConsultationDraft | None, bundle: EvidenceBundle, request: ConsultationRequest) -> ValidatedResponse:
    allowed = L.AllowedFacts(set(bundle.allowed_terms), set(bundle.allowed_ganzhi), set(bundle.allowed_years), set(bundle.allowed_claim_ids))
    if draft is None:
        return ValidatedResponse(bundle.fallback_text, "deterministic_fallback", False, "none", "", ["제공자 없음/예외"], bundle.precommit_hash)
    problems = L.validate_llm_text(draft.text, allowed)
    if len(draft.text) > request.max_chars:
        problems.append("길이 초과")
    # 고전 근거 위장 검사: 원문 상태가 text_confirmed 가 아닌 규칙을 쓴 문단에서 '고전/원전에 따르면' 식 표현 금지
    if any(s != "text_confirmed" for s in bundle.classical_status.values()) and re.search(r"(고전|원전|원문|자평진전|적천수|궁통보감|삼명통회)[^.]{0,6}(에 따르면|에서는|은 말|에 나와)", draft.text):
        problems.append("원문 확인이 끝나지 않은 규칙을 고전 근거처럼 서술")
    if FIXED_DISCLAIMER not in draft.text and "예측" not in draft.text:
        draft = ConsultationDraft(draft.text + "\n\n" + FIXED_DISCLAIMER + ".", draft.provider, draft.model, draft.usage)
    if problems:
        return ValidatedResponse(bundle.fallback_text, "deterministic_fallback", False, draft.provider, draft.model, sorted(set(problems)), bundle.precommit_hash)
    return ValidatedResponse(draft.text, "provider", True, draft.provider, draft.model, [], bundle.precommit_hash)


def run(ans: dict, pre: dict, request: ConsultationRequest, provider: ConsultationProvider | None) -> ValidatedResponse:
    bundle = build_bundle(ans, pre)
    if provider is None:
        return ValidatedResponse(bundle.fallback_text, "deterministic_fallback", True, "none", "", [], bundle.precommit_hash)
    try:
        draft = provider.generate(request, bundle)
    except Exception as e:
        return ValidatedResponse(bundle.fallback_text, "deterministic_fallback", False, getattr(provider, "name", "?"), "", [f"제공자 오류: {e!r}"[:200]], bundle.precommit_hash)
    return validate(draft, bundle, request)


class TemplateProvider:
    """외부 호출 없는 참조 구현: 결정론적 문단을 쉬운 말투로 이어 붙인다. 계약 시험과 로컬 데모용."""
    name = "template-provider"

    def generate(self, request: ConsultationRequest, bundle: EvidenceBundle) -> ConsultationDraft:
        body = "\n\n".join(p["text"] for p in bundle.paragraphs)
        return ConsultationDraft("질문하신 내용을 구조 분석 결과에 맞춰 정리했습니다.\n\n" + body, self.name, "template-1")
