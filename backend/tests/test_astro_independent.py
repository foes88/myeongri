"""v6.6 §6: 월주·시주·대운·시간대의 독립 검증 시도 결과(집계 JSON)를 검증한다.
이 테스트는 외부 라이브러리(korean-saju, bazi 등)를 import 하지 않는다 — 결과 JSON 과 서비스 경계만 본다.
"""
import json
import sys
from pathlib import Path

from app.astro_core import verification_levels as vl

G = Path(__file__).resolve().parents[1] / "golden"
IP = json.loads((G / "independent_pillars_check.json").read_text(encoding="utf-8"))
TZ = json.loads((G / "tz_history_check.json").read_text(encoding="utf-8"))
ROOT = Path(__file__).resolve().parents[1]


def all_cmp(section):
    return [v for v in IP[section].values() if isinstance(v, dict) and "cases" in v]


def test_tools_are_recorded_with_license_and_lineage():
    for name in ("korean-saju", "bazi", "celestial-calendar", "cnlunar"):
        t = IP["tools"][name]
        assert t["license"] == "MIT" and t["version"] and t["lineage"] and t["scope"]


def test_korean_saju_matches_engine_when_mapped_to_its_actual_rules():
    ks = IP["korean_saju_vs_engine"]
    assert "균시차가 없다" in ks["note"]  # korean-saju 의 '진태양시'는 경도 보정만 있는 평균태양시
    for key in ("yaja_separated__vs__MEAN_SOLAR__MIDNIGHT_NEXT_DAY_STEM", "yaja_unified__vs__MEAN_SOLAR__ZI_2300_DAY_CHANGE"):
        r = ks[key]
        assert r["cases"] == r["agree_all"] >= 500 and r["mismatch_unexplained_count"] == 0
        assert all(f["mismatch"] == 0 and f["compared"] >= 500 for f in r["fields"].values())


def test_equation_of_time_difference_is_visible_not_hidden():
    c = next(v for k, v in IP["korean_saju_vs_engine"].items() if k.startswith("contrast"))
    assert c["fields"]["hour"]["mismatch"] > 0  # 균시차를 넣으면 시주가 달라지는 사례가 실제로 존재한다
    assert c["fields"]["year"]["mismatch"] == 0 and c["fields"]["month"]["mismatch"] == 0


def test_bazi_matches_engine_for_both_day_rollover_options():
    for k, r in IP["bazi_vs_engine"].items():
        if isinstance(r, dict) and "cases" in r:
            assert r["cases"] == r["agree_all"] >= 500 and r["mismatch_unexplained_count"] == 0, k


def test_cnlunar_day_level_has_no_unexplained_mismatch():
    c = IP["cnlunar_vs_engine_civil_date_level"]
    assert c["compared"] >= 400 and c["mismatch_count"] == 0 and c["year_basis_lunar_new_year_expected"] >= 1  # 연주는 설날 기준이라 1~2월 차이는 예상된 것


def test_month_pillar_boundary_and_naming_evidence():
    m = IP["month_year_from_kasi_almanac_terms"]
    assert m["tested"] >= 500 and m["mismatch"] == 0
    w = IP["kasi_wolgun_arithmetic"]
    assert w["local_file"]["months"] >= 70 and w["local_file"]["mismatch"] == 0 and w["service_sample"]["queries"] >= 50 and w["service_sample"]["mismatch"] == 0
    assert "음력 월 기준" in w["wolgun_basis"]["conclusion"] and w["wolgun_basis"]["same_lunar_month"] is True  # KASI 월건은 절기 기준 월주가 아님


def test_jie_moments_vs_vsop87d_lineage():
    j = IP["celestial_calendar_jieqi_vs_engine"]
    assert j["compared"] == 3600 and j["over_60s"] == 0 and j["max_abs_s"] < 60
    assert all(v < 10 for k, v in j["max_abs_s_by_decade"].items() if int(k) >= 1970)


def test_equation_of_time_independent_agreement():
    e = IP["equation_of_time"]
    assert e["sign_convention_ok_apparent_minus_mean"] and e["engine_vs_celestial_calendar_max_min"] < 0.01
    assert e["engine_vs_noaa_formula_max_min"] < 1.5 and e["engine_vs_bazi_apparent_time_seconds"]["max_s"] < 1.0


def test_daeun_independent_implementations_agree_on_direction_and_differ_only_by_convention():
    d = IP["daeun_cross_implementation"]
    assert d["direction_agree_ks"] == d["direction_agree_bazi"] == d["cases"] >= 500
    assert set(d["ks_months_diff"]) <= {"0", "1"}  # 월 반올림 방식 차이
    assert d["bazi_first_luck_date_minus_engine_days"]["within_10_days"] == d["bazi_first_luck_date_minus_engine_days"]["n"]
    assert "정답이 없는 관습" in d["interpretation"]


def test_summary_has_no_unexplained_mismatches():
    s = IP["summary"]
    assert s["unexplained_mismatches_korean_saju"] == s["unexplained_mismatches_bazi"] == s["unexplained_mismatches_cnlunar"] == 0 and s["kasi_derived_month_year_mismatch"] == 0


# ---------------- 시간대·서머타임 ----------------
def test_tz_history_facts_and_unresolved_item_are_explicit():
    s = TZ["summary"]
    assert s["facts"] >= 28 and s["status_counts"].get("MATCH", 0) >= 27 and s["primary_law_text_checked"] is False
    assert any("1954" in u for u in s["unresolved"])  # 전환 시각 30분 차이: 숨기지 않고 미해결로 둔다
    f = next(x for x in TZ["facts"] if "1954" in x["fact"])
    assert f["status"] == "DATE_MATCH_TIME_OF_DAY_MISMATCH" and "30분" in f["note"]
    assert "법령 원문" in s["independence"]


def test_tz_history_sources_opened_and_listed():
    for name in ("ko.wikipedia 한국 표준시", "namu.wiki 서머타임", "en.wikipedia Time in South Korea"):
        assert TZ["sources"][name]["opened"] is True
    assert TZ["sources"]["namu.wiki 서머타임"]["dst_years_parsed"] == [1948, 1949, 1950, 1951, 1955, 1956, 1957, 1958, 1959, 1960, 1987, 1988]


def test_recorded_tzdata_transitions_match_current_zoneinfo():
    """저장된 tzdata 전환 목록이 현재 환경의 zoneinfo 와 같은지(데이터 갱신으로 달라졌다면 재실행 필요)."""
    sys.path.insert(0, str(ROOT))
    from tools.check_tz_history import tz_transitions
    assert tz_transitions() == TZ["tzdata_transitions"]


# ---------------- fail-closed / 범위 경계 ----------------
def test_investigation_did_not_relax_v1_gate():
    lv = vl.levels()
    assert not lv["PILLARS_VERIFIED"]["granted"] and not lv["PROFILE_VERIFIED"]["granted"] and not lv["DAEUN_VERIFIED"]["granted"]
    ok, blockers = vl.v1_allowed()
    assert not ok and blockers


def test_independent_libraries_are_not_service_dependencies():
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    for lib in ("korean-saju", "korean_saju", "bazi", "celestial", "cnlunar", "sxtwl", "ephem"):
        assert lib not in req.replace("korean-lunar-calendar", "")
    import app.astro_core.engine  # noqa: F401
    assert not [m for m in sys.modules if m.split(".")[0] in ("korean_saju", "bazi", "celestial_calendar", "cnlunar", "sxtwl")]


def test_public_golden_files_have_no_raw_external_tables():
    for name in ("independent_pillars_check.json", "tz_history_check.json"):
        text = (G / name).read_text(encoding="utf-8")
        assert len(text) < 120_000  # 집계·개별 사실만 — 원문 자료집 아님
