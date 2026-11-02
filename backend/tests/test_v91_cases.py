"""v9.1 사례 검증 도구 테스트. 모든 사례·사건은 도구 동작 검증용 합성 데이터이며 실제 사람이나 실제 사건이 아니다(출생일은 숫자로 조립한다).
핵심: 사건이 해석 생성 경로에 들어가지 않는다 / 봉인 전에는 비교할 수 없다 / 규칙이 바뀌면 검증이 무효 표시된다 / 사건 구별 능력이 없으면 그렇게 보고한다."""
import datetime
import json

import pytest
from cryptography.fernet import Fernet

from app import cases as C
from tools import case_eval as CE

TODAY = datetime.date(2026, 3, 1)


@pytest.fixture()
def st(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_KEY", Fernet.generate_key().decode())
    return C.Store(tmp_path / "cases")


def birth(y, m, d):
    return f"{y:04d}-{m:02d}-{d:02d}"


def rec(i, tc="A", scope="both", place="서울특별시", y=None):
    t = None if tc == "D" else f"{(7 + i) % 24:02d}:{(10 * i) % 60:02d}"
    return {"case_id": f"SYN-{i:03d}", "calendar": "solar", "leap": False, "birth_date": birth(y or 1996 + i, 1 + i % 12, 3 + i), "birth_time": t, "birth_place": place,
            "gender": "male" if i % 2 else "female", "time_confidence": tc, "consent": {"given": True, "scope": scope, "note": "합성"}, "kind": "synthetic",
            "observation": {"from": 2015, "to": 2026, "complete_domains": ["career", "love_marriage", "job_change"]}}


def ev(year, dom="job_change", month=6, conf="high"):
    return {"year": year, "month": month, "domain": dom, "kind": "합성", "source": "합성 출처", "source_confidence": conf}


# ---------------------------------------------------------------- 입력·분리·암호화
def test_validation_rejects_missing_consent_bad_id_and_unsourced_events(st):
    bad = rec(1) | {"consent": {"given": False, "scope": "both"}}
    with pytest.raises(C.CaseError, match="동의"):
        st.add_case(bad, [])
    with pytest.raises(C.CaseError, match="익명"):
        st.add_case(rec(1) | {"case_id": "홍길동"}, [])
    with pytest.raises(C.CaseError, match="time_confidence"):
        st.add_case(rec(1, tc="A") | {"time_confidence": "Z"}, [])
    with pytest.raises(C.CaseError, match="D"):
        st.add_case(rec(1) | {"birth_time": None}, [])        # 시각이 없는데 신뢰도 A
    with pytest.raises(C.CaseError, match="출처"):
        st.add_case(rec(1), [ev(2020) | {"source": ""}])
    with pytest.raises(C.CaseError, match="분야"):
        st.add_case(rec(1), [ev(2020, dom="lottery")])
    assert st.case_ids() == []


def test_split_is_fixed_at_entry_by_scope_or_hash_not_by_hand(st):
    assert st.add_case(rec(1, scope="dev"), [])["split"] == "dev"
    assert st.add_case(rec(2, scope="validation"), [])["split"] == "validation"
    assert C.assign_split("SYN-777", "both") == C.assign_split("SYN-777", "both")      # 결정적
    shares = [C.assign_split(f"SYN-{i:04d}", "both") for i in range(1000)]
    assert 0.2 < shares.count("validation") / 1000 < 0.4                               # 약 30%
    with pytest.raises(C.CaseError):
        st.add_case(rec(1), [])                                                         # 중복 ID


def test_storage_is_encrypted_and_has_no_plaintext_birth_data(st):
    st.add_case(rec(3, place="경기도 수원시"), [ev(2021)])
    blob = b"".join(f.read_bytes() for f in st.dir.glob("*.enc"))
    for needle in ("경기도 수원시".encode(), b"SYN-003", b"job_change", birth(1999, 4, 6).encode()):
        assert needle not in blob
    assert st.case_input("SYN-003").birth_place == "경기도 수원시"                      # 복호화하면 읽힌다


def test_case_input_has_no_event_or_split_fields():
    assert set(C.CaseInput.__dataclass_fields__) == {"case_id", "calendar", "leap", "birth_date", "birth_time", "birth_place", "gender", "time_confidence"}


# ---------------------------------------------------------------- 사후 맞춤 방지
def test_freeze_never_reads_the_events_file(st, monkeypatch):
    st.add_case(rec(4, scope="validation"), [ev(2022)])
    read = []
    orig = C.Store._read
    monkeypatch.setattr(C.Store, "_read", lambda self, name, default: (read.append(name), orig(self, name, default))[1])
    st.freeze("SYN-004", today=TODAY)
    assert "events" not in read and "cases" in read


def test_events_are_sealed_until_frozen_and_freeze_is_once_only(st):
    st.add_case(rec(5), [ev(2022)])
    with pytest.raises(C.CaseError, match="봉인"):
        st.events_for_compare("SYN-005")
    st.freeze("SYN-005", today=TODAY)
    assert st.events_for_compare("SYN-005")[0]["year"] == 2022
    with pytest.raises(C.CaseError, match="이미 봉인"):
        st.freeze("SYN-005", today=TODAY)
    st.freeze("SYN-005", force=True, today=TODAY)
    assert st.frozen()["SYN-005"]["refrozen"] is True and CE.cmd_status(st)["refrozen(검증 무효 표시)"] == 1


def test_analysis_window_does_not_depend_on_events(st):
    ys = C.analysis_years(1999, 2026)
    assert ys[0] == 1999 + C.AGE_FROM and ys[-1] == 2026
    assert C.analysis_years(1960, 2040)[-1] == 1960 + C.AGE_TO
    st.add_case(rec(6), [ev(2019)])
    st.add_case(rec(7, y=1996 + 6), [ev(2003)])      # 사건이 구간 밖이어도 구간은 같은 규칙
    st.freeze("SYN-006", today=TODAY)
    assert [r["year"] for r in st.frozen()["SYN-006"]["years"]] == C.analysis_years(2002, 2026)


def test_tampered_or_stale_ruleset_predictions_are_excluded_and_validation_contamination_flagged(st, monkeypatch):
    for i in (8, 9):
        st.add_case(rec(i, scope="validation"), [ev(2022)])
        st.freeze(f"SYN-00{i}", today=TODAY)
    fr = st.frozen()
    fr["SYN-008"]["years"][0]["domains"]["career"]["tone"] = "opportunity" if fr["SYN-008"]["years"][0]["domains"]["career"]["tone"] != "opportunity" else "cautious"
    st._write("frozen", fr)
    monkeypatch.setattr(C, "current_ruleset", lambda: "mingli-new")      # 봉인 뒤 규칙이 바뀐 상황
    rep = C.build_report(st, include_synthetic=True)
    assert rep["skipped"]["tampered"] == 1 and rep["skipped"]["ruleset_changed"] == 1
    # 같은 검증 세트가 다른 규칙 버전에서 이미 평가된 기록이 있으면 오염
    st.log_eval({"split": "validation", "ruleset_version": "mingli-old", "at": "x", "cases": 1})
    assert C.build_report(st, include_synthetic=True)["validation_contaminated"] is True


def test_remove_case_deletes_everything(st):
    st.add_case(rec(10), [ev(2022)])
    st.freeze("SYN-010", today=TODAY)
    assert st.remove_case("SYN-010") and st.case_ids() == [] and st.frozen() == {}
    assert st._read("events", {}) == {}


# ---------------------------------------------------------------- 지표(손계산 일치)
def fake_pred(dom_tones: dict[int, str], dom="career"):
    return {"years": [{"year": y, "daeun_change": False, "has_limits": True, "domains": {dom: {"tone": t, "S": 1, "T": 1, "headline": "h", "has_counter": True, "story": "s"}}} for y, t in dom_tones.items()]}


def test_detection_table_matches_hand_calculation_and_excludes_boundary_and_low_confidence():
    tones = {y: "quiet" for y in range(2000, 2010)}
    for y in (2001, 2003, 2005):
        tones[y] = "opportunity"
    events = [ev(2003, "career"), ev(2007, "career"), ev(2005, "career", month=1), ev(2008, "career", conf="low")]
    t = C.detection_table([{"predictions": fake_pred(tones), "events": events, "observation": {"from": 2000, "to": 2009, "complete_domains": ["career"]}}], "career", "strong", n_perm=200)
    # 2005 는 1월 사건이라 입춘 경계로 제외, 2008(출처 low)은 사건으로 세지 않는다 → 해 9개: 사건 {2003, 2007}, 주장 {2001, 2003}
    assert (t["tp"], t["fp"], t["fn"], t["tn"]) == (1, 1, 1, 6)
    assert t["detection"] == 0.5 and t["false_alarm"] == pytest.approx(1 / 7) and t["precision"] == 0.5
    assert t["base_rate"] == pytest.approx(2 / 9) and t["lift"] == pytest.approx(0.5 / (2 / 9))
    assert not t["sufficient"]                                   # 사건 해 2개 → 결론 불가


def test_weak_mixed_claims_count_only_in_any_level():
    tones = {2000: "mixed", 2001: "quiet", 2002: "quiet"}
    p = [{"predictions": fake_pred(tones), "events": [ev(2000, "career")], "observation": {"from": 2000, "to": 2009, "complete_domains": ["career"]}}]
    assert C.detection_table(p, "career", "any", n_perm=10)["tp"] == 1
    assert C.detection_table(p, "career", "strong", n_perm=10)["tp"] == 0


def test_permutation_test_is_deterministic_and_separates_signal_from_noise():
    # 신호: 40개 사건 해를 정확히 주장 / 잡음: 주장과 사건이 무관
    n = 120
    sig_t = {y: ("opportunity" if y % 3 == 0 else "quiet") for y in range(n)}
    sig_e = [ev(1000 + y if False else 1900 + y, "career") for y in range(n) if y % 3 == 0]
    sig_t = {1900 + y: t for y, t in sig_t.items()}
    s = C.detection_table([{"predictions": fake_pred(sig_t), "events": sig_e, "observation": {"from": 1900, "to": 2100, "complete_domains": ["career"]}}], "career", "strong", n_perm=300)
    assert s["sufficient"] and s["p_perm"] < 0.01 and s["lift"] > 2
    noise_t = {1900 + y: ("opportunity" if y % 3 == 0 else "quiet") for y in range(n)}
    noise_e = [ev(1900 + y, "career") for y in range(n) if y % 3 == 1]
    z = C.detection_table([{"predictions": fake_pred(noise_t), "events": noise_e, "observation": {"from": 1900, "to": 2100, "complete_domains": ["career"]}}], "career", "strong", n_perm=300)
    assert z["tp"] == 0 and z["p_perm"] > 0.5
    assert C.detection_table([{"predictions": fake_pred(sig_t), "events": sig_e, "observation": {"from": 1900, "to": 2100, "complete_domains": ["career"]}}], "career", "strong", n_perm=50) == C.detection_table([{"predictions": fake_pred(sig_t), "events": sig_e, "observation": {"from": 1900, "to": 2100, "complete_domains": ["career"]}}], "career", "strong", n_perm=50)


def part_with(det_by_dom, primary=5):
    return {"primary_cases": primary, "detection": {d: {"strong": t} for d, t in det_by_dom.items()}}


def test_judge_reports_unconfirmed_ability_honestly_and_never_calls_it_prediction_accuracy():
    assert C.judge({"primary_cases": 0, "detection": {}}, False)["status"] == "미평가"
    small = {"career": {"sufficient": False, "p_perm": 0.01, "lift": 3.0, "cases_scored": 5}}
    j = C.judge(part_with(small), False)
    assert j["status"] == "표본 부족" and "예측 정확도로 해석하지" in j["reason"]
    flat = {"career": {"sufficient": True, "p_perm": 0.4, "lift": 1.02, "cases_scored": 5}}
    j = C.judge(part_with(flat), False)
    assert j["status"] == "구별 능력 미확인" and "자기 이해" in j["reason"]
    good = {"career": {"sufficient": True, "p_perm": 0.01, "lift": 1.8, "cases_scored": 5}}
    j = C.judge(part_with(good), False)
    assert j["status"] == "예비 단서(재현 필요)" and "일반화할 수 없" in j["reason"] and "정확도" not in j["status"]


def test_distinctiveness_flags_flat_interpretation_and_measures_chart_uniqueness():
    flat = {"year": 0, "years": [{"year": 2000 + i, "domains": {"career": {"tone": "mixed"}, "wealth": {"tone": "mixed"}}} for i in range(10)], "birth_year": 1980}
    d = C.distinctiveness([flat])
    assert d["year_distinct_median"] == 0 and d["low_year_distinct_share"] == 1.0 and d["domain_distinct_median"] == 0.5
    a = {"years": [{"year": 2000 + i, "domains": {"career": {"tone": "opportunity" if i % 2 else "quiet"}}} for i in range(10)], "birth_year": 1980}
    b = {"years": [{"year": 2000 + i, "domains": {"career": {"tone": "quiet" if i % 2 else "opportunity"}}} for i in range(10)], "birth_year": 1980}
    assert C.distinctiveness([a, b])["chart_uniqueness"]["career"] == 1.0 and C.distinctiveness([a, a])["chart_uniqueness"]["career"] == 0.0


# ---------------------------------------------------------------- 종단(합성) · CSV · CLI
def test_end_to_end_synthetic_pipeline_reports_insufficient_sample_and_no_real_case_claim(st):
    for i in range(1, 5):
        st.add_case(rec(i, scope="dev" if i < 3 else "validation"), [ev(2019 + i % 3, "career"), ev(2021, "love_marriage", conf="medium")])
    st.add_case(rec(5, tc="C", scope="dev"), [])                         # 시각 신뢰도 C: 1차 분석 제외, 사건 없는 대조 사례
    for cid in st.case_ids():
        st.freeze(cid, today=TODAY)
    s = CE.cmd_status(st)
    assert s["cases"] == 5 and s["frozen"] == 5 and s["not_frozen"] == 0 and s["split"] == {"dev": 3, "validation": 2} and s["primary_analysis_cases(A·B)"] == 4
    assert C.build_report(st)["skipped"]["synthetic_excluded"] == 5     # 기본 보고서는 합성 사례를 실제 성능에 넣지 않는다
    rep = C.build_report(st, include_synthetic=True)
    dev, val = rep["split"]["dev"], rep["split"]["validation"]
    assert dev["cases"] == 3 and dev["primary_cases"] == 2 and dev["verdict"]["status"] == "표본 부족"
    assert val["verdict"]["status"] == "표본 부족" and rep["validation_contaminated"] is False
    assert dev["detection"]["career"]["strong"]["event_years"] >= 1
    assert 0 <= dev["tones"]["claim_rate"] <= 1 and dev["uncertainty"]["definitive_phrases"] == 0 and dev["uncertainty"]["limits_share"] == 1.0
    assert json.dumps(rep, ensure_ascii=False).count("SYN-") == 0          # 보고서에 사례 ID·출생 정보 없음
    assert len(st.eval_log()) == 1
    assert "birth" not in json.dumps(rep).lower()


def test_generation_is_deterministic_and_range_invariant(st):
    st.add_case(rec(6), [])
    c = C.consistency_check(st.case_input("SYN-006"), 2026, sample=3)
    assert c == {"deterministic": True, "range_invariant_share": 1.0}


def test_status_without_cases_says_unverified(st):
    assert "미검증" in CE.cmd_status(st)["real_case_validation"]
    st.add_case(rec(1), [])                                  # 합성 사례만 있어도 실제 사례 검증은 '미검증'
    s = CE.cmd_status(st)
    assert "미검증" in s["real_case_validation"] and s["real_cases"] == 0 and s["synthetic_cases(도구 검증용)"] == 1


def test_csv_import_roundtrip_rejects_unconsented_and_inconsistent_rows(st, tmp_path):
    hdr = ",".join(CE.COLS)
    r1 = f"SYN-101,solar,false,{birth(1998, 5, 9)},,서울특별시,male,D,true,dev,합성,synthetic,2018,2026,wealth,2020,3,wealth,합성,합성 출처,high"
    r1b = f"SYN-101,solar,false,{birth(1998, 5, 9)},,서울특별시,male,D,true,dev,합성,synthetic,2018,2026,wealth,2022,,career,합성,합성 출처,medium"
    r2 = f"SYN-102,solar,false,{birth(1999, 7, 1)},{(9):02d}:{(5):02d},서울특별시,female,A,false,both,,synthetic,,,,,,,,,"
    parsed = CE.parse_csv("\n".join([hdr, r1, r1b, r2]))
    assert len(parsed["SYN-101"][1]) == 2 and parsed["SYN-101"][0]["birth_time"] is None
    st.add_case(*parsed["SYN-101"])
    with pytest.raises(C.CaseError, match="동의"):
        st.add_case(*parsed["SYN-102"])
    bad = r1b.replace("male", "female")
    with pytest.raises(C.CaseError, match="다릅니다"):
        CE.parse_csv("\n".join([hdr, r1, bad]))
    assert st.case_ids() == ["SYN-101"] and st.meta()["SYN-101"]["time_confidence"] == "D"


def test_generated_text_has_no_definitive_phrases_and_birth_data_not_in_frozen_predictions(st):
    st.add_case(rec(7, place="경기도 수원시"), [])
    st.freeze("SYN-007", today=TODAY)
    raw = json.dumps(st.frozen()["SYN-007"], ensure_ascii=False)
    assert "경기도 수원시" not in raw and birth(2003, 8, 10) not in raw
    assert not C.DEFINITIVE.search(raw)


# ---------------------------------------------------------------- CLI 종단(합성) · 고전 현황 문서
def test_cli_end_to_end_with_synthetic_csv(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("APP_DATA_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("CASES_DIR", str(tmp_path / "c"))
    hdr = ",".join(CE.COLS)
    rows = [f"SYN-201,solar,false,{birth(1997, 4, 12)},{9:02d}:{20:02d},서울특별시,male,A,true,dev,합성,synthetic,2016,2026,job_change,2019,5,job_change,합성,합성 출처,high",
            f"SYN-202,solar,false,{birth(1998, 9, 21)},{14:02d}:{40:02d},서울특별시,female,B,true,validation,합성,synthetic,2016,2026,career,,,,,,",
            f"SYN-203,solar,false,{birth(1999, 2, 17)},{3:02d}:{15:02d},서울특별시,female,A,false,both,,synthetic,,,,,,,,,"]
    f = tmp_path / "in.csv"
    f.write_text("\n".join([hdr] + rows), encoding="utf-8")
    assert CE.main(["import", str(f)]) == 0
    out = capsys.readouterr().out
    assert "추가: SYN-201 → dev" in out and "추가: SYN-202 → validation" in out and "거부: SYN-203" in out and "동의" in out
    assert CE.main(["freeze", "--all"]) == 0 and capsys.readouterr().out.count("봉인:") == 2
    rep = tmp_path / "rep.json"
    assert CE.main(["report", "--out", str(rep), "--include-synthetic"]) == 0
    out = capsys.readouterr().out
    assert "표본 부족" in out and "미검증" not in out
    j = json.loads(rep.read_text(encoding="utf-8"))
    assert j["split"]["dev"]["cases"] == 1 and j["split"]["validation"]["cases"] == 1
    assert CE.main(["remove", "SYN-201"]) == 0 and "삭제됨" in capsys.readouterr().out
    assert CE.main(["status"]) == 0
    assert '"cases": 1' in capsys.readouterr().out


def test_classical_audit_document_matches_registry():
    from pathlib import Path
    from tools import classical_audit as CA
    from app.mingli import classical as CL
    s = CL.summary()
    rs = CA.rows()
    assert len(rs) == s["total"] == 37
    unconfirmed = [r for r in rs if r["basis"] == "미확인"]
    assert len(unconfirmed) == s["classical_rules_pending"]                    # 위치만 확인 + pending
    assert {r["rule_id"] for r in rs if r["basis"] == "구현자 규약"} == {r["rule_id"] for r in rs if r["status"] == "implementation_convention"}
    md = CA.build_markdown()
    assert "고전 검증 완료’라고 표시하지 않는다" in md and "새 원문을 내려받거나 재배포하지 않았다" in md
    doc = Path(__file__).resolve().parents[2] / "docs" / "24_V91_CLASSICAL_AUDIT.md"
    assert doc.exists() and doc.read_text(encoding="utf-8") == md              # 문서가 현재 레지스트리와 동기화되어 있다
