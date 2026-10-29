"""고전 규칙 원문 검증 상태 테스트. 네트워크 없이 저장된 결과(golden/classical_verification.json)와 엔진 출력만 검사한다."""
import json

import pytest

from app.mingli import classical
from app.mingli.classical import PRED, classical_status, evaluate_case, summary
from app.mingli.rules import RULES

DATA = json.loads(classical.PATH.read_text(encoding="utf-8"))
RULE_ENTRIES = DATA["rules"]
STEMS, BR = "甲乙丙丁戊己庚辛壬癸", "子丑寅卯辰巳午未申酉戌亥"


def test_every_rule_has_an_entry_and_valid_status():
    assert set(RULE_ENTRIES) == set(RULES) and len(RULES) == 37
    for rid, e in RULE_ENTRIES.items():
        assert e["status"] in classical.STATUSES, rid
        assert e["classification"] in ("classical", "convention")
        assert (e["classification"] == "convention") == (e["status"] == "implementation_convention")
        assert e["accessed"] == "2026-10-29" and e["school_conditions"], rid


def test_text_confirmed_needs_excerpt_source_and_scope():
    for rid, e in RULE_ENTRIES.items():
        if e["status"] != "text_confirmed":
            continue
        ex = e["original_excerpt"] or e["commentary_excerpt"]
        assert ex and len(ex) <= 40, rid
        assert e["work"] and e["url"].startswith("https://") and e["scope_note"], rid
        # 원문/주석 구분이 기록되어야 한다
        assert bool(e["original_excerpt"]) != bool(e["commentary_excerpt"]) or rid in (
            "MG-L3-GUNGEOP-JAENGJAE", "MG-L3-GWAN-INSAENG", "MG-L3-SAL-INSAENG", "MG-L2-BANGHAP"), rid


def test_location_confirmed_is_not_overclaimed():
    for rid, e in RULE_ENTRIES.items():
        if e["status"] == "location_confirmed":
            assert all(len(k) >= 2 for k in e["keywords_found"]), rid
            assert "직접 뒷받침하는지는 판단하지 않음" in e["scope_note"], rid
            assert len(e.get("content_gap", "")) >= 30, f"{rid}: 위치만 확인된 규칙은 content_gap 설명이 있어야 한다"


def test_convention_rules_make_no_classical_claim():
    for rid in ("MG-L1-SUPPORT-ORDINAL", "MG-L3-CHAIN", "MG-L4-YONGSHIN-CONFLICT", "MG-L5-STRUCTURE-DELTA", "MG-L5-SEGMENT", "MG-L5-COMPARE"):
        e = RULE_ENTRIES[rid]
        assert e["status"] == "implementation_convention" and e["original_excerpt"] is None and e["url"] is None


def test_known_discrepancies_are_not_marked_confirmed():
    # 三命通會는 寅亥·巳申 破를 취하지 않음 → 본 구현 표와 불일치이므로 text_confirmed 금지
    pa = RULE_ENTRIES["MG-L2-PA"]
    assert pa["status"] == "location_confirmed" and "寅亥" in pa["school_conditions"]
    # 원문(沈孝瞻)은 三刑을 闕疑로 둠
    assert RULE_ENTRIES["MG-L2-HYUNG"]["status"] == "location_confirmed" and "闕疑" in RULE_ENTRIES["MG-L2-HYUNG"]["school_conditions"]
    # 구현 조건표는 원문과 동일하지 않다고 명시
    assert "단순화" in RULE_ENTRIES["MG-L4-SEONGPA"]["scope_note"]
    # 규칙은 등록되었지만 엔진 노드가 쓰지 않음
    assert "노드를 만들지 않음" in RULE_ENTRIES["MG-L5-LUCK-STEM"]["scope_note"] or "claim 노드를 만들지 않음" in RULE_ENTRIES["MG-L5-LUCK-STEM"]["scope_note"]


def test_summary_counts_and_not_all_confirmed():
    s = summary()
    assert s["total"] == 37 and sum(s["by_status"].values()) == 37
    assert s["by_status"]["text_confirmed"] >= 1 and s["by_status"]["implementation_convention"] == 6
    assert s["by_status"] == {"pending": 0, "location_confirmed": 4, "text_confirmed": 27, "implementation_convention": 6}
    assert set(s["partial_text_confirmed"]) == {"MG-L1-DEUKRYEONG-SEASON", "MG-L2-BANGHAP", "MG-L2-HAP-HWA", "MG-L4-GYEOKGUK-BONGI"}
    assert s["classical_rules_pending"] == s["by_status"]["pending"] + s["by_status"]["location_confirmed"]
    assert not s["all_confirmed"]  # location_confirmed 가 남아 있으므로 'CLASSICAL_RULES_PENDING' 유지
    assert isinstance(s["failed_sources"], dict)


def test_fail_closed_when_file_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(classical, "PATH", tmp_path / "nope.json")
    classical.reload()
    try:
        assert classical_status("MG-L2-CHUNG") == "pending"
        s = classical.summary()
        assert s["by_status"]["pending"] == 37 and not s["all_confirmed"]
    finally:
        monkeypatch.undo()
        classical.reload()
    assert classical_status("MG-L2-CHUNG") == "text_confirmed"


def _valid(p):
    return all(len(v) == 2 and v[0] in STEMS and v[1] in BR and STEMS.index(v[0]) % 2 == BR.index(v[1]) % 2 for v in p.values()) and set(p) == {"year", "month", "day", "hour"}


CASE_PARAMS = [(rid, k) for rid, e in RULE_ENTRIES.items() for k in ("positive_case", "negative_case") if e.get(k)]


def test_cases_exist_for_all_evaluable_rules():
    for rid, p in PRED.items():
        e = RULE_ENTRIES[rid]
        if p.get("pos"):
            assert e["positive_case"], rid
        if p.get("neg"):
            assert e["negative_case"], rid


@pytest.mark.parametrize("rid,key", CASE_PARAMS)
def test_positive_and_negative_cases_behave_as_recorded(rid, key):
    pillars = RULE_ENTRIES[rid][key]
    assert _valid(pillars)  # 가상(합성) 명식: 실제 출생정보 아님
    result = evaluate_case(rid, "pos" if key == "positive_case" else "neg", pillars)
    assert result is True, (rid, key, pillars)


def test_positive_and_negative_cases_differ():
    for rid, e in RULE_ENTRIES.items():
        if e.get("positive_case") and e.get("negative_case"):
            assert e["positive_case"] != e["negative_case"], rid


def test_partial_text_confirmed_lists_unconfirmed_parts_and_additional_excerpts_are_verified():
    for rid, e in RULE_ENTRIES.items():
        if e["status"] == "text_confirmed" and e.get("coverage") == "partial":
            assert e["unconfirmed_parts"], rid
        for a in e.get("additional_excerpts", []):
            assert len(a["text"]) <= 40 and a["verified_in_page"] is True and a["kind"] in ("original", "commentary", "annotation"), (rid, a["text"])
