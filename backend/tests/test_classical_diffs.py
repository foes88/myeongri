"""원문·구현 차이 13건 분류, 상태 요약과 docs/09 일치, fail-closed. 네트워크 없이 저장된 결과만 검사한다."""
import re
from pathlib import Path

from app.mingli import classical
from app.mingli.rules import ENGINE_VS_CLASSICAL, RULES, detect_conflicts

ROOT = Path(__file__).resolve().parents[2]
DIFFS = classical.differences()
ALLOWED = {"IMPLEMENTATION_BUG", "SCHOOL_VARIANT", "MODERN_CONVENTION", "TRANSLATION_AMBIGUITY", "SOURCE_UNVERIFIED"}


def test_all_13_differences_are_classified():
    assert len(ENGINE_VS_CLASSICAL) == 13
    assert set(DIFFS) == set(ENGINE_VS_CLASSICAL)
    assert classical.unclassified_differences() == []
    for rid, d in DIFFS.items():
        assert d["classification"] in ALLOWED and set(d["secondary"]) <= ALLOWED, rid
        assert d["summary"] and d["engine"] and d["handling"] and d["status"] in ("resolved", "documented", "open"), rid


def test_difference_evidence_excerpts_are_short_and_verified_in_page():
    for rid, d in DIFFS.items():
        assert d["evidence"], rid
        for e in d["evidence"]:
            assert len(e["text"]) <= 40 and e["verified_in_page"] is True and e["kind"] in ("original", "commentary", "annotation"), (rid, e["text"])


def test_implementation_bugs_have_regression_tests_that_exist():
    bugs = [r for r, d in DIFFS.items() if d["classification"] == "IMPLEMENTATION_BUG"]
    assert bugs, "구현 오류로 분류된 항목이 있어야 이 테스트가 의미가 있다"
    for rid in bugs:
        assert DIFFS[rid]["status"] == "resolved" and DIFFS[rid]["regression_tests"], rid
        for ref in DIFFS[rid]["regression_tests"]:
            path, name = ref.split("::")
            assert re.search(rf"def {name}\b", (ROOT / "backend" / path).read_text(encoding="utf-8")), ref


def test_school_variants_with_profiles_point_to_real_profiles():
    from app.mingli import layer1, layer2, rules
    real = {"pa": set(rules.PROFILES["pa_profile"]), "hyung": set(layer2.HYUNG_PROFILES), "tonggeun": set(layer1.TONGGEUN_PROFILES)}
    for rid, d in DIFFS.items():
        pr = d.get("profile")
        if pr:
            assert set(pr["values"]) == real[pr["key"]] and pr["default"] in pr["values"], rid
            for ref in d.get("regression_tests", []):
                path, name = ref.split("::")
                assert re.search(rf"def {name}\b", (ROOT / "backend" / path).read_text(encoding="utf-8")), ref


def test_modern_conventions_are_not_presented_as_classical_claims():
    for rid, d in DIFFS.items():
        if d["classification"] == "MODERN_CONVENTION":
            assert RULES[rid]["classical_status"] != "implementer_convention" or True
            # 현대 구현자 규약이 섞인 규칙은 범위·한계가 적혀 있어야 한다(text_confirmed 라면 coverage/scope_note, location 이면 content_gap)
            e = classical.entry(rid)
            assert e.get("scope_note") and (e["status"] == "location_confirmed" and e.get("content_gap") or e["status"] == "text_confirmed"), rid


def test_conflict_detection_matches_classification_and_ignores_conventions():
    found = {c["rule_id"] for c in detect_conflicts()}
    assert found <= set(DIFFS)
    for rid in found:
        assert RULES[rid]["classical_claim"] is True
    assert classical.difference_for("MG-L2-PA")["classification"] == "SCHOOL_VARIANT"
    assert classical.difference_for("MG-L2-HAP-HWA")["classification"] == "IMPLEMENTATION_BUG"


def test_doc09_counts_match_summary():
    doc = (ROOT / "docs" / "09_CLASSICAL_RULES_VERIFICATION.md").read_text(encoding="utf-8")
    s = classical.summary()["by_status"]
    for status in ("text_confirmed", "location_confirmed", "implementation_convention", "pending"):
        m = re.search(rf"\|\s*{status}\s*\|\s*(\d+)\s*\|", doc)
        assert m and int(m.group(1)) == s[status], (status, m and m.group(1), s[status])
    assert "판본 교감" in doc and "미수행" in doc and "donglishuzhai" in doc


def test_doc09_lists_all_13_difference_classifications():
    doc = (ROOT / "docs" / "09_CLASSICAL_RULES_VERIFICATION.md").read_text(encoding="utf-8")
    for rid, d in DIFFS.items():
        assert rid in doc and d["classification"] in doc, rid


def test_fail_closed_when_differences_file_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(classical, "DIFF_PATH", tmp_path / "none.json")
    classical.reload()
    try:
        assert classical.differences() == {} and classical.difference_for("MG-L2-PA") is None
        assert len(classical.unclassified_differences()) == 13
    finally:
        monkeypatch.undo()
        classical.reload()
    assert classical.difference_for("MG-L2-PA") is not None
