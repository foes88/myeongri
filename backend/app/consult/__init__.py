"""Consult-Agent: 사전 분석 기록 + 정·반 근거 상담 + 사후 끼워 맞추기 방지. LLM 미사용(결정론적 템플릿)."""
from .agent import CONSULT_VERSION, answer, build_precommit, classify_event  # noqa: F401
