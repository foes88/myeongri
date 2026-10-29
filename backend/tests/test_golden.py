"""골든 스위트·검증 레벨·절입 모호성·문서 회귀. 불일치 케이스를 지우거나 기대값을 바꿔 통과시키지 않는다."""
import json
from collections import Counter
from pathlib import Path

import pytest

from app.astro_core import TimeProfile, calculate_chart, engine
from app.astro_core import verification_levels as vl
from tools.run_golden import run_case

G = Path(__file__).resolve().parents[1] / "golden"
CASES = json.loads((G / "cases.json").read_text(encoding="utf-8"))["cases"]
JUDGE = json.loads((G / "judgements.json").read_text(encoding="utf-8"))["judgements"]
MINIMUM = {"GEN": 20, "TERM": 24, "ZI": 12, "SOLAR": 12, "TZ": 12, "LUNAR": 10, "DAEUN": 10}


def test_golden_counts_and_metadata():
    ids = [c["test_id"] for c in CASES]
    assert len(ids) == len(set(ids)) and len(ids) >= 100
    cnt = Counter(c["category"] for c in CASES)
    for cat, n in MINIMUM.items():
        assert cnt[cat] >= n, (cat, cnt[cat])
    for c in CASES:
        assert c["synthetic_input"] is True and c["references"] and c["fields_checked"] and c["tolerance"]
        assert all(r.get("tool") and r.get("version") for r in c["references"])


@pytest.mark.parametrize("case", CASES, ids=[c["test_id"] for c in CASES])
def test_golden_case(case):
    ok, detail = run_case(case)
    if case["test_id"] in JUDGE:
        assert not ok, "판정 파일의 불일치가 사라졌다면 judgements.json 에서 제거하라"
        assert JUDGE[case["test_id"]]["verdict"] and JUDGE[case["test_id"]]["reason"]
    else:
        assert ok, (case["expect"], detail)


def test_report_matches_cases_and_has_no_unexplained():
    rep = json.loads((G / "report.json").read_text(encoding="utf-8"))
    assert rep["total"] == len(CASES)
    assert all(f["judgement"] != "UNEXPLAINED" for f in rep["failures"])


def test_sources_registry_records_scope_license_and_lineage():
    src = json.loads((G / "sources.json").read_text(encoding="utf-8"))
    for name in ("KASI", "sxtwl", "lunar-python", "HKO"):
        assert src[name]["status"] in ("OBTAINED", "PARTIAL_UNOFFICIAL", "NOT_OBTAINED", "NOT_RUN") and "license" in src[name] and src[name]["lineage"]
    assert src["KASI"]["status"] == "PARTIAL_UNOFFICIAL" and "공식 발표 자료가 아니며" in src["KASI"]["reason"]
    assert src["sxtwl"]["status"] == "OBTAINED" and "BSD-3-Clause" in src["sxtwl"]["license"]
    assert src["sxtwl"]["lineage"] == src["lunar-python"]["lineage"]  # 동일 계열은 독립 2종으로 세지 않는다
    assert "sxtwl" not in (Path(__file__).resolve().parents[1] / "requirements.txt").read_text().lower()


def test_sxtwl_crosscheck_report():
    rep = json.loads((G / "sxtwl_report.json").read_text(encoding="utf-8"))
    assert rep["sxtwl_version"] == "sxtwl 2.0.7" and rep["terms_compared"] >= 3000
    assert rep["pillar_fields_disagree"] == 0 and rep["pillar_fields_agree_with_lunar_python"] > 100
    assert rep["terms_max_abs_s_vs_skyfield"] < 120


def test_kr_lunar_derivation_report():
    rep = json.loads((G / "lunar_check.json").read_text(encoding="utf-8"))
    assert rep["hko_vs_derived8_mismatch_years"] == [2033] and rep["klc_vs_derived9_mismatch_years"] == [2033]  # 2033 은 예외 규칙 미구현
    assert all(rep["kasi_vs_klc"].values()) and all(rep["kasi_vs_derived9"].values())
    assert rep["detail_focus"]["2012"]["klc_leap"] != rep["detail_focus"]["2012"]["hko_leap"]
    for jid, j in JUDGE.items():
        assert j["verdict"] == "EXPLAINED_BY_DERIVATION_OFFICIAL_UNRESOLVED" and "UNRESOLVED_OFFICIAL" in j["evidence"]["official_kasi"]


def test_levels_are_separate_and_v1_blocked():
    lv = vl.levels()
    assert lv["ASTRO_VERIFIED"]["granted"]  # HKO + KASI 달력자료 + 寿星 계열 3계열
    for k in ("PILLARS_VERIFIED", "PROFILE_VERIFIED", "DAEUN_VERIFIED", "LUNAR_VERIFIED"):
        assert not lv[k]["granted"] and lv[k]["blockers"], k
    cov = vl.pillar_coverage()
    assert cov["day"] == ["KASI", "shouxing"] and cov["year"] == cov["month"] == cov["hour"] == ["shouxing"]
    ok, blockers = vl.v1_allowed()
    assert not ok and any("KASI" in b for b in blockers) and any("라이선스" in b for b in blockers)
    assert engine.GOLDEN_SUITE_COMPLETE is False


def test_v1_gate_fails_closed_without_report(monkeypatch):
    monkeypatch.setattr(vl, "_load", lambda: ({}, {}, {}))
    assert not vl.v1_allowed()[0] and not any(v["granted"] for v in vl.levels().values())


def test_ambiguous_near_jie_returns_both_charts():
    # HKO 2027 입춘 04:?? 근처: 정확한 순간에서 20초 이내
    t = next(t for t, k in engine.eph.solar_terms_in_utc_year(2027) if k == 21)
    kst = (t + engine.timedelta(seconds=20)).astimezone(engine.ZoneInfo("Asia/Seoul"))
    r = calculate_chart(year=kst.year, month=kst.month, day=kst.day, hour=kst.hour, minute=kst.minute, second=kst.second, gender="male")
    months = {v["pillars"]["month"] for v in r.variants}
    assert len(months) >= 2 and r.verification["status"] == "V3" and "solar_term_ambiguous" in r.verification["reasons"]
    assert r.verification["ambiguity"]["ambiguous"] and r.verification["may_claim_verified"] is False


def test_not_ambiguous_far_from_jie():
    r = calculate_chart(year=2015, month=6, day=20, hour=12, gender="male")
    assert not r.verification["ambiguity"]["ambiguous"]


def test_lunar_kr_cn_mismatch_year_is_not_trusted():
    r = calculate_chart(calendar="lunar", year=2012, month=3, day=1, is_leap_month=True, gender="male", hour=12)
    assert "lunar_kr_cn_mismatch" in r.verification["reasons"] and r.verification["status"] == "V3"


# ---- docs/03 회귀: 2000-01-01 19:25 서울 (합성 입력) ----
def test_doc03_apparent_solar_time_regression():
    rows = {}
    for tp in TimeProfile:
        r = calculate_chart(year=2000, month=1, day=1, hour=19, minute=25, gender="male", time_profile=tp)
        rows[tp] = (r.time_profile["pillar_time_local"][11:16], r.pillars["hour"])
    assert rows[TimeProfile.CIVIL_TIME] == ("19:25", "壬戌")
    assert rows[TimeProfile.LOCAL_MEAN_SOLAR_TIME] == ("18:52", "辛酉")
    assert rows[TimeProfile.LOCAL_APPARENT_SOLAR_TIME] == ("18:49", "辛酉")  # 예전 문서의 '戌시' 주장은 오류
    doc = (Path(__file__).resolve().parents[2] / "docs" / "03_CALENDAR_VALIDATION.md").read_text(encoding="utf-8")
    assert "진태양시는 戌시 후보로 기록" not in doc and "합성 입력" in doc and "독립 검산 미완료" in doc


# ---- 개인정보: 골든 전체 제외 대신 구조 검증 ----
def test_golden_privacy_structural_validation():
    from app import privacy_scan as ps
    assert ps.validate_golden_cases(CASES) == []
    bad = [dict(CASES[0], synthetic_input=False), dict(CASES[1], input=dict(CASES[1]["input"], name="홍길동")),
           dict(CASES[2], references=[{"tool": "어딘가", "version": "?"}]), dict(CASES[3], input=dict(CASES[3]["input"], place="내 집 주소"))]
    probs = ps.validate_golden_cases(bad)
    assert len(probs) == 4


def test_golden_files_still_get_secret_and_email_scan(tmp_path):
    from app import privacy_scan as ps
    f = tmp_path / "backend" / "golden"
    f.mkdir(parents=True)
    (f / "x.json").write_text('{"note": "contact " + "me" + "@" + "gmail.com", "k": "2001-02-03T04:05:00"}'.replace('" + "', ''), encoding="utf-8")  # 가상 예시
    hits = ps.scan_files([f / "x.json"], root=tmp_path)
    assert any("email" in h for h in hits) and not any("birth_datetime" in h for h in hits)
    (tmp_path / "other.json").write_text('{"k": "2001-02-03T04:05:00"}', encoding="utf-8")  # 가상 예시
    assert any("birth_datetime" in h for h in ps.scan_files([tmp_path / "other.json"], root=tmp_path))
