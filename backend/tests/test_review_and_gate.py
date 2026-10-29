import copy
import json
import re
from datetime import time
from pathlib import Path

import pytest

from app import chart_analysis, gate, privacy_scan, report_review as rr
from app.report_checks import error_kind

ROOT = Path(__file__).resolve().parents[2]
S01 = {"year": "庚申", "month": "甲寅", "day": "甲辰", "hour": "丙寅"}  # knowledge/14 합성 S01


def load_report():
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    raw = re.search(r'<script id="report-data" type="application/json">(.*?)</script>', html, re.S).group(1)
    return json.loads(raw.replace("<\\/", "</"))


@pytest.fixture
def report():
    return load_report()


# ---------- 정상 입력 ----------
def test_s01_structure_matches_kb():  # 14 S01: 甲일간, 寅월, 근 寅, 庚 七殺, 丙 食神
    a = chart_analysis.analyze_chart(S01)
    assert a["day_stem"] == "甲" and a["month_branch"] == "寅" and a["season"] == "봄"
    assert a["ten_gods"] == {"year": "七殺", "month": "比肩", "hour": "食神"}
    assert a["day_stem_roots"] == ["month", "hour"]
    assert a["groups"]["재성"]["level"] == "hidden" and a["groups"]["인성"]["level"] == "hidden"
    assert a["strength_candidate"] == "strong_candidate"


def test_invalid_pillars_rejected():
    with pytest.raises(ValueError):
        chart_analysis.analyze_chart({"year": "ZZ", "month": "甲寅", "day": "甲辰"})
    with pytest.raises(ValueError):
        chart_analysis.analyze_chart({"year": "庚申", "hour": "丙寅"})  # 월/일 없음


def test_web_page_passes_all_checks(report):
    bad = [f for f in rr.review_report(report) if not f.ok]
    assert bad == []


def test_web_html_is_up_to_date_with_sources():
    import subprocess, sys
    r = subprocess.run([sys.executable, str(ROOT / "scripts/build_web.py"), "--check"])
    assert r.returncode == 0, "web/index.html 이 web/src 와 다릅니다: python scripts/build_web.py"


# ---------- 재현성 ----------
def test_reproducibility_deterministic():
    assert rr.x05_reproducibility(lambda: chart_analysis.analyze_chart(S01), runs=30).ok


def test_reproducibility_detects_nondeterminism():
    import itertools
    c = itertools.count()
    assert not rr.x05_reproducibility(lambda: {"n": next(c)}, runs=3).ok


# ---------- 절기·시주 경계 / 미검산 ----------
def test_term_boundary_is_not_confirmed():
    r = gate.classify_verification(pillars_given=S01, term_distance_minutes=30)
    assert r["status"] == "V3" and "solar_term_boundary" in r["reasons"] and not r["may_claim_verified"]


def test_yaja_si_and_hour_unknown_split_profiles():
    assert "yaja_si_profile_split" in gate.classify_verification(pillars_given=S01, birth_time=time(23, 30))["reasons"]
    assert "yaja_si_profile_split" in gate.classify_verification(pillars_given=S01, birth_time=time(0, 20))["reasons"]
    no_hour = {k: v for k, v in S01.items() if k != "hour"}
    assert gate.classify_verification(pillars_given=no_hour, hour_known=False)["status"] == "V3"


def test_unspecified_leap_month_stops():
    assert gate.classify_verification(pillars_given=S01, calendar="lunar", is_leap_month=None)["status"] == "V3"


def test_unverified_pillars_are_v2_and_cannot_claim_verified():
    r = gate.classify_verification(pillars_given=S01, birth_time=time(12, 0))
    assert r["status"] == "V2" and not r["may_claim_verified"]


def test_v1_requires_two_independent_agreeing_tools():
    a = {"tool": "A", "version": "1", "pillars": S01}
    b = {"tool": "B", "version": "2", "pillars": S01}
    assert gate.classify_verification(pillars_given=S01, verifications=[a, b], birth_time=time(12, 0))["status"] == "V1"
    assert gate.classify_verification(pillars_given=S01, verifications=[a], birth_time=time(12, 0))["status"] == "V2"
    c = {"tool": "B", "version": "2", "pillars": {**S01, "hour": "丁卯"}}
    assert gate.classify_verification(pillars_given=S01, verifications=[a, c], birth_time=time(12, 0))["reasons"] == ["verifier_disagreement"]


def test_unverified_chart_cannot_say_verified(report):
    assert report["chart"]["verification"]["verified"] is False
    report["detail_hack"] = None
    report["sections"][0]["summary"] = "이 사주는 만세력으로 확인했습니다."
    assert any(f.check == "L04" and not f.ok for f in rr.review_report(report))


def test_luck_start_age_hidden_when_unverified(report):
    assert report["luck"]["start_age"] is None
    report["luck"]["start_age"] = 8
    assert not rr.x04_luck(report).ok
    report["luck"]["start_age"] = None
    report["luck"]["years"][0]["ganji"] = "丙午"
    assert not rr.x04_luck(report).ok


# ---------- 근거 누락 ----------
def test_missing_basis_detected(report):
    report["sections"][2]["basis"] = []
    assert not rr.x03_basis(report).ok


def test_fabricated_basis_detected(report):
    report["sections"][2]["basis"] = ["근거: 06 존재하지 않는 항목", "근거: 99 없는 파일"]
    assert not rr.x03_basis(report).ok


def test_fabricated_quote_detected(report):
    report["sections"][9]["quotes"].append("甲木參天")
    md = rr.render_markdown(report) + "「甲木參天」"
    from app.report_checks import l09_quotes
    assert not l09_quotes(md).ok


def test_missing_section_part_detected(report):
    report["sections"][3]["daily"] = ""
    assert not rr.x07_structure(report).ok


# ---------- 상충하는 해석 / 영역 간 모순 ----------
def test_cross_section_contradiction_detected(report):
    a = chart_analysis.analyze_chart(S01)
    assert rr.x01_cross_section(report, a).ok
    report["sections"][4]["claims"] = [{"group": "재성", "level": "visible"}]  # 문서 영역이 재성을 '드러남'으로 주장
    assert not rr.x01_cross_section(report, a).ok
    report["sections"][4]["claims"] = [{"day_strength": "weak_candidate"}]
    assert not rr.x01_cross_section(report, a).ok


def test_school_conflict_requires_explanation(report):
    assert rr.x02_school_conflict(report).ok
    report["conflict_note"] = ""
    assert not rr.x02_school_conflict(report).ok


def test_three_yongshin_not_merged(report):
    names = {report["yongshin"][k]["name"] for k in ("pattern", "balance", "climate")}
    assert names == {"격국용신", "억부용신", "조후용신"}
    assert rr.x08_yongshin_separate(report).ok
    merged = copy.deepcopy(report)
    merged["yongshin"]["balance"]["name"] = "용신"  # 이름을 뭉뚱그림
    assert not rr.x08_yongshin_separate(merged).ok
    same = copy.deepcopy(report)
    same["yongshin"]["climate"]["text"] = same["yongshin"]["pattern"]["text"]  # 내용을 하나로 합침
    assert not rr.x08_yongshin_separate(same).ok
    assert any(f.check == "X08" and not f.ok for f in rr.review_report(merged))


def test_forbidden_certainty_detected(report):
    report["sections"][2]["caution"] = "올해 큰돈을 반드시 벌게 됩니다."
    assert any(f.check == "L07" and not f.ok for f in rr.review_report(report))


def test_fact_table_must_match_recomputation(report):
    report["analysis"]["groups"]["재성"]["level"] = "visible"
    assert not rr.x06_report_matches_analysis(report, chart_analysis.analyze_chart(S01)).ok


# ---------- 계산 오류 vs 해석 오류 분리 ----------
def test_error_kind_separation(report):
    assert error_kind("L01") == "calculation" and error_kind("X06") == "calculation"
    assert error_kind("L07") == "interpretation" and error_kind("X01") == "interpretation"
    report["analysis"]["season"] = "여름"
    report["sections"][2]["caution"] = "반드시 성공합니다."
    out = rr.split_by_kind(rr.review_report(report))
    assert out["interpretation"] and any(f.check == "L07" for f in out["interpretation"])
    # 사실표 불일치는 review_report 가 chart 에서 재계산해 X06 계산 오류로 기록한다.
    assert any(f.check == "X06" for f in out["calculation"])


# ---------- 개인정보·비밀정보 ----------
def test_privacy_scan_flags_leaks():
    leaked = "생일 " + "1988" + "-11-15 19:25 출생"
    assert privacy_scan.scan_text(leaked)
    assert privacy_scan.scan_text("key = 'sk-" + "a" * 30 + "'")
    assert privacy_scan.scan_text("contact: someone@" + "gmail.com")
    assert privacy_scan.scan_text("-----BEGIN " + "RSA PRIVATE KEY-----")
    assert privacy_scan.scan_text("출생 2000-01-01 12:00 (가상)") == []
    assert privacy_scan.scan_text("예: 1990-05-05 10:30 가상 예시") == []


def test_repo_has_no_personal_or_secret_data():
    hits = privacy_scan.scan_files(privacy_scan.tracked_and_staged_files())
    assert hits == []


def test_web_page_contains_only_synthetic_data(report):
    assert report["chart"]["source_type"] == "synthetic" and report["input"]["date"] == privacy_scan.SYNTHETIC_DATE
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    assert "<input" not in html  # 공개 시안은 출생정보를 입력받지 않는다
    assert "fetch(" not in html and "XMLHttpRequest" not in html  # 외부 전송 없음
