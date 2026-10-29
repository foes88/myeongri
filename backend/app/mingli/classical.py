"""고전 규칙 원문 검증 상태 조회. golden/classical_verification.json 을 읽는다(파일 없으면 전부 pending: fail-closed).

상태
  pending                    확인하지 못함(출처 접속 실패·핵심어 미발견 포함)
  location_confirmed         출처 페이지에서 장·핵심어 위치만 확인(구절이 규칙 내용을 직접 뒷받침한다고는 주장하지 않음)
  text_confirmed             사람이 구절을 읽고 규칙 내용(또는 명시한 범위)에 대응함을 확인, 발췌 첨부
  implementation_convention  고전 주장 없음(구현자 규약)
text_confirmed 는 '고전과 일치한다'가 아니라 '표시한 범위에서 원문이 뒷받침한다'는 뜻이며 scope_note 를 함께 읽어야 한다.
"""
from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).resolve().parents[2] / "golden" / "classical_verification.json"
DIFF_PATH = Path(__file__).resolve().parents[2] / "golden" / "classical_differences.json"
DIFF_CLASSES = ("IMPLEMENTATION_BUG", "SCHOOL_VARIANT", "MODERN_CONVENTION", "TRANSLATION_AMBIGUITY", "SOURCE_UNVERIFIED")
STATUSES = ("pending", "location_confirmed", "text_confirmed", "implementation_convention")


@lru_cache(maxsize=1)
def _load() -> dict:
    try:
        return json.loads(PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@lru_cache(maxsize=1)
def _load_diffs() -> dict:
    try:
        return json.loads(DIFF_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def reload() -> None:
    _load.cache_clear()
    _load_diffs.cache_clear()


def differences() -> dict:
    """원문·구현 차이 분류표 {rule_id: {...}}. 파일이 없으면 {} (fail-closed: 분류 없음으로 취급)."""
    return _load_diffs().get("differences", {})


def difference_for(rule_id: str) -> dict | None:
    d = differences().get(rule_id)
    return d if d and d.get("classification") in DIFF_CLASSES else None


def unclassified_differences() -> list[str]:
    """rules.ENGINE_VS_CLASSICAL 에 있는데 분류가 없는 규칙(분류표가 없으면 전부)."""
    from .rules import ENGINE_VS_CLASSICAL
    return sorted(r for r in ENGINE_VS_CLASSICAL if difference_for(r) is None)


def coverage(rule_id: str) -> str | None:
    """text_confirmed 규칙의 확인 범위: 'scoped'(scope_note 범위) / 'partial'(일부 조건만, unconfirmed_parts 참조)."""
    return entry(rule_id).get("coverage")


def entry(rule_id: str) -> dict:
    return _load().get("rules", {}).get(rule_id, {})


def classical_status(rule_id: str) -> str:
    s = entry(rule_id).get("status", "pending")
    return s if s in STATUSES else "pending"


def summary() -> dict:
    from .rules import RULES
    cnt = Counter(classical_status(r) for r in RULES)
    partial = sorted(r for r in RULES if classical_status(r) == "text_confirmed" and coverage(r) == "partial")
    return {"total": len(RULES), "by_status": {s: cnt.get(s, 0) for s in STATUSES}, "partial_text_confirmed": partial,
            "classical_rules_pending": cnt.get("pending", 0) + cnt.get("location_confirmed", 0),
            "all_confirmed": cnt.get("pending", 0) + cnt.get("location_confirmed", 0) == 0,
            "failed_sources": _load().get("failed_sources", {})}


# ---- 성립/불성립 사례 평가 (엔진의 실제 출력으로 판정) ----
def _nodes(res: dict, rid: str) -> list[dict]:
    return [n for n in res["graph"]["nodes"] if n["rule_id"] == rid]


def _always(res, rid):
    return bool(_nodes(res, rid))


PRED: dict[str, dict] = {
    # rule_id: {"pos": fn(nodes)->bool, "neg": fn(nodes)->bool}  (neg 가 None 이면 '항상 산출'되는 규칙이라 불성립 사례 없음)
    "MG-L1-WOLRYEONG": {"pos": lambda ns: bool(ns), "neg": None},
    "MG-L1-DEUKRYEONG-BONGI": {"pos": lambda ns: any(n["status"] == "득령" for n in ns), "neg": lambda ns: any(n["status"] == "실령 후보" for n in ns)},
    "MG-L1-DEUKRYEONG-SEASON": {"pos": lambda ns: any(n["status"] == "득령" for n in ns), "neg": lambda ns: any(n["status"] == "실령 후보" for n in ns)},
    "MG-L1-HIDDEN-ROLE": {"pos": None, "neg": None},
    "MG-L1-TONGGEUN": {"pos": lambda ns: any(n["status"] == "엄격 강" for n in ns), "neg": lambda ns: any(n["status"] == "엄격 없음" for n in ns)},
    "MG-L1-TUGAN": {"pos": lambda ns: any(n["status"] == "투출 있음" for n in ns), "neg": lambda ns: any(n["status"] == "암장만" for n in ns)},
    "MG-L2-STEM-HAP": {"pos": lambda ns: bool(ns), "neg": lambda ns: not ns},
    "MG-L2-HAP-HWA": {"pos": lambda ns: any(n["status"].startswith("합화 후보 조건 충족") for n in ns), "neg": lambda ns: any(n["status"] == "합화 불성립 근거 있음" for n in ns)},
    "MG-L2-BRANCH-YUKHAP": {"pos": lambda ns: bool(ns), "neg": lambda ns: not ns},
    "MG-L2-SAMHAP": {"pos": lambda ns: any(n["status"] == "삼합(완전) 존재" for n in ns), "neg": lambda ns: not ns},
    "MG-L2-BANGHAP": {"pos": lambda ns: any(n["status"] == "방합 존재" for n in ns), "neg": lambda ns: not ns},
    "MG-L2-CHUNG": {"pos": lambda ns: bool(ns), "neg": lambda ns: not ns},
    "MG-L2-HYUNG": {"pos": lambda ns: bool(ns), "neg": lambda ns: not ns},
    "MG-L2-PA": {"pos": lambda ns: bool(ns), "neg": lambda ns: not ns},
    "MG-L2-HAE": {"pos": lambda ns: bool(ns), "neg": lambda ns: not ns},
    "MG-L2-GOGO": {"pos": lambda ns: bool(ns), "neg": lambda ns: not ns},
    "MG-L2-COMPETITION": {"pos": lambda ns: bool(ns), "neg": lambda ns: not ns},
    "MG-L3-SIKSANG-SAENGJAE": {"pos": lambda ns: any(n["attributes"].get("rank", 0) >= 2 for n in ns), "neg": lambda ns: all(n["attributes"].get("rank", 0) == 0 for n in ns)},
    "MG-L3-JAE-SAENGGWAN": {"pos": lambda ns: any(n["attributes"].get("rank", 0) >= 2 for n in ns), "neg": lambda ns: all(n["attributes"].get("rank", 0) == 0 for n in ns)},
    "MG-L3-GWAN-INSAENG": {"pos": lambda ns: any(n["attributes"].get("rank", 0) >= 2 for n in ns), "neg": lambda ns: all(n["attributes"].get("rank", 0) == 0 for n in ns)},
    "MG-L3-SAL-INSAENG": {"pos": lambda ns: any(n["attributes"].get("rank", 0) >= 2 for n in ns), "neg": lambda ns: all(n["attributes"].get("rank", 0) == 0 for n in ns)},
    "MG-L3-SANGGWAN-GYEONGWAN": {"pos": lambda ns: any(n["attributes"].get("rank", 0) == 3 for n in ns), "neg": lambda ns: all(n["attributes"].get("rank", 0) == 0 for n in ns)},
    "MG-L3-GUNGEOP-JAENGJAE": {"pos": lambda ns: any(n["status"] != "없음" and n["attributes"].get("rank", 0) >= 2 for n in ns), "neg": lambda ns: all(n["status"] == "없음" for n in ns)},
    "MG-L4-GYEOKGUK-CAND": {"pos": lambda ns: any(n["status"].endswith("격") for n in ns), "neg": lambda ns: any("월겁" in n["status"] or "양인" in n["status"] for n in ns)},
    "MG-L4-GYEOKGUK-BONGI": {"pos": lambda ns: bool(ns), "neg": None},
    "MG-L4-SEONGPA": {"pos": lambda ns: any(n["status"] == "성격 후보" for n in ns), "neg": lambda ns: any(n["status"].startswith("파격 후보") for n in ns)},
    "MG-L4-GEUKGUK-YONGSHIN": {"pos": lambda ns: any(n["status"] == "후보" for n in ns), "neg": lambda ns: any(n["status"] == "정하지 않음" for n in ns)},
    "MG-L4-EOKBU-YONGSHIN": {"pos": lambda ns: any(n["status"] == "후보" for n in ns), "neg": lambda ns: any(n["status"] == "정하지 않음" for n in ns)},
    "MG-L4-JOHU-DIRECTION": {"pos": lambda ns: any(n["attributes"].get("direction_elements") for n in ns), "neg": lambda ns: any(not n["attributes"].get("direction_elements", ["x"]) for n in ns)},
}


def evaluate_case(rule_id: str, kind: str, pillars: dict) -> bool | None:
    """사례(pos/neg)가 엔진 출력에서 기대대로 나오는지. 평가 불가 규칙이면 None."""
    p = PRED.get(rule_id)
    if not p or not p.get(kind):
        return None
    from . import analyze_structure
    res = analyze_structure(pillars)
    return bool(p[kind](_nodes(res, rule_id)))
