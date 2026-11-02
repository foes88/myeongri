"""v9.5 실제 사례 검증 체계 테스트. 모든 데이터는 합성(도구 점검용)이며 실제 사건 검증이 아니다. 출생일은 숫자로 조립한다."""
import datetime
import json
import re

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


def rec(i, kind="synthetic", obs=True, tc="A", scope="both"):
    r = {"case_id": f"SYN-{i:03d}", "calendar": "solar", "leap": False, "birth_date": birth(1990 + i, 1 + i % 12, 2 + i), "birth_time": f"{(8 + i) % 24:02d}:{(5 * i) % 60:02d}",
         "birth_place": "서울특별시", "gender": "male" if i % 2 else "female", "time_confidence": tc, "consent": {"given": True, "scope": scope, "note": "합성"}, "kind": kind}
    if obs:
        r["observation"] = {"from": 2015, "to": 2026, "complete_domains": ["career", "wealth"]}
    return r


def ev(year, dom="career", month=6, conf="high", kind="합성"):
    return {"year": year, "month": month, "domain": dom, "kind": kind, "source": "합성 출처", "source_confidence": conf}


# ---------------------------------------------------------------- 무사건 해: 관측 누락과 확인된 무사건을 구분
def fake_pred(tones, dom="career"):
    return {"years": [{"year": y, "domain": dom, "daeun_change": False, "has_limits": True, "domains": {dom: {"tone": t, "S": 1, "T": 1, "headline": "h", "has_counter": True, "story": "s"}}} for y, t in tones.items()]}


def test_years_outside_the_declared_observation_are_not_treated_as_negative():
    tones = {y: "opportunity" for y in range(2000, 2020)}
    events = [ev(2005), ev(2012)]
    inside = {"from": 2000, "to": 2009, "complete_domains": ["career"]}
    t = C.detection_table([{"predictions": fake_pred(tones), "events": events, "observation": inside}], "career", "strong", n_perm=10)
    assert t["event_years"] == 1 and t["non_event_years"] == 9 and t["cases_scored"] == 1      # 2012 사건과 2010~2019 는 관측 범위 밖 → 제외


def test_case_without_observation_or_with_other_domains_is_excluded_not_counted_as_negative():
    tones = {y: "opportunity" for y in range(2000, 2010)}
    none_obs = {"predictions": fake_pred(tones), "events": [ev(2003)], "observation": None}
    other = {"predictions": fake_pred(tones), "events": [ev(2003)], "observation": {"from": 2000, "to": 2009, "complete_domains": ["wealth"]}}
    t = C.detection_table([none_obs, other], "career", "strong", n_perm=10)
    assert t["cases_scored"] == 0 and t["cases_not_observed"] == 2 and t["event_years"] == 0 and t["non_event_years"] == 0


def test_report_is_unevaluated_when_no_case_declares_an_observation_range():
    part = {"primary_cases": 3, "detection": {"career": {"strong": {"cases_scored": 0, "sufficient": False, "p_perm": None, "lift": None}}}}
    j = C.judge(part, False)
    assert j["status"] == "미평가" and "관측 범위" in j["reason"] and "사건 없음" in j["reason"]


def test_observation_validation():
    base = rec(1)
    for bad in ({"from": 2020, "to": 2010, "complete_domains": ["career"]}, {"from": 2010, "to": 2020, "complete_domains": []}, {"from": 2010, "to": 2020, "complete_domains": ["lottery"]}, {"to": 2020}):
        with pytest.raises(C.CaseError):
            C.validate_case(base | {"observation": bad})
    assert C.validate_case(base | {"observation": None})["observation"] is None


# ---------------------------------------------------------------- 합성/실제 분리
def test_synthetic_cases_never_count_as_real_validation_or_performance(st):
    st.add_case(rec(1, kind="synthetic"), [ev(2020)])
    st.freeze("SYN-001", today=TODAY)
    s = CE.cmd_status(st)
    assert s["real_cases"] == 0 and s["synthetic_cases(도구 검증용)"] == 1 and "미검증" in s["real_case_validation"]
    rep = C.build_report(st)
    assert rep["skipped"]["synthetic_excluded"] == 1 and rep["split"]["dev"]["cases"] + rep["split"]["validation"]["cases"] == 0
    assert C.build_report(st, include_synthetic=True)["includes_synthetic"] is True


def test_real_kind_requires_explicit_choice_and_rejects_unknown_kinds(st):
    with pytest.raises(C.CaseError, match="kind"):
        st.add_case(rec(1, kind="fake"), [])
    assert st.add_case(rec(2, kind="real"), [])["kind"] == "real"
    assert CE.cmd_status(st)["real_cases"] == 1 and "미검증" not in CE.cmd_status(st)["real_case_validation"]


# ---------------------------------------------------------------- 중복·품질
def test_duplicate_birth_data_is_detected_unless_explicitly_allowed(st):
    st.add_case(rec(3), [])
    dup = rec(3) | {"case_id": "SYN-903"}
    with pytest.raises(C.CaseError, match="중복"):
        st.add_case(dup, [])
    assert st.add_case(dup, [], allow_duplicate=True)["case_id"] == "SYN-903"      # 쌍둥이 등 명시한 경우만
    blob = b"".join(f.read_bytes() for f in st.dir.glob("*.enc"))
    assert birth(1993, 4, 5).encode() not in blob                                    # 중복 검사용 지문도 암호화 파일 안에만 있다


def test_same_event_recorded_twice_is_rejected(st):
    with pytest.raises(C.CaseError, match="두 번"):
        st.add_case(rec(4), [ev(2020), ev(2020)])
    assert st.case_ids() == []


def test_event_quality_report_counts_problems_without_personal_data(st):
    st.add_case(rec(5), [ev(2020, month=None), ev(2021, month=1), ev(2022, conf="low"), ev(2005), ev(2018, "wealth")])
    st.add_case(rec(6, obs=False), [ev(2019)])
    q = st.event_quality()
    assert q["events"] == 6 and q["by_source_confidence"]["low"] == 1 and q["month_missing_share"] == pytest.approx(1 / 6, abs=0.001)
    assert q["ipchun_boundary(점수 제외)"] == 1 and q["outside_declared_observation"] == 1 and q["events_of_cases_without_observation"] == 1 and q["outside_analysis_window"] >= 1
    text = json.dumps(q, ensure_ascii=False)
    assert "SYN-" not in text and "서울" not in text


# ---------------------------------------------------------------- 결과 표현
def test_report_vocabulary_is_limited_and_never_says_accuracy(st):
    allowed = {"미평가", "표본 부족", "예비 단서(재현 필요)", "구별 능력 미확인"}
    big = {"career": {"strong": {"cases_scored": 5, "sufficient": True, "p_perm": 0.3, "lift": 1.0}}}
    for part in ({"primary_cases": 0, "detection": {}}, {"primary_cases": 3, "detection": {"career": {"strong": {"cases_scored": 0, "sufficient": False, "p_perm": None, "lift": None}}}},
                 {"primary_cases": 3, "detection": {"career": {"strong": {"cases_scored": 3, "sufficient": False, "p_perm": 0.01, "lift": 3}}}}, {"primary_cases": 30, "detection": big},
                 {"primary_cases": 30, "detection": {"career": {"strong": {"cases_scored": 30, "sufficient": True, "p_perm": 0.01, "lift": 2}}}}):
        j = C.judge(part, False)
        assert j["status"] in allowed
        assert not re.search(r"적중률|정확도가|정확도는", j["status"] + j["reason"].replace("예측 정확도로 해석하지", "").replace("예측 정확도라고", ""))
    rep = C.build_report(st)
    assert "최종 검증 성능이 아니다" in rep["note"]


def test_dev_and_validation_results_are_reported_separately_with_dev_not_called_validation(st):
    st.add_case(rec(7, scope="dev"), [ev(2019)])
    st.add_case(rec(8, scope="validation"), [ev(2019)])
    for cid in st.case_ids():
        st.freeze(cid, today=TODAY)
    rep = C.build_report(st, include_synthetic=True)
    assert set(rep["split"]) == {"dev", "validation"} and rep["split"]["dev"]["cases"] == 1 and rep["split"]["validation"]["cases"] == 1


# ---------------------------------------------------------------- 삭제·동의
def test_consent_withdrawal_removes_everything_including_fingerprint_and_events(st):
    st.add_case(rec(9), [ev(2020)])
    st.freeze("SYN-009", today=TODAY)
    assert st.remove_case("SYN-009") and st.case_ids() == [] and st._read("events", {}) == {} and st.frozen() == {}
    assert st.add_case(rec(9), [])["case_id"] == "SYN-009"                          # 지문도 사라져 같은 데이터를 다시 넣을 수 있다(동의 철회 후 재동의)
    blob = b"".join(f.read_bytes() for f in st.dir.glob("*.enc"))
    assert b"SYN-009" not in blob


# ---------------------------------------------------------------- 출생 시각 신뢰도
def test_time_confidence_secondary_cases_are_reported_but_excluded_from_primary_detection(st):
    st.add_case(rec(10, tc="A"), [ev(2019)])
    st.add_case(rec(11, tc="C"), [ev(2019)])
    for cid in st.case_ids():
        st.freeze(cid, today=TODAY)
    rep = C.build_report(st, include_synthetic=True)
    dev_val = [rep["split"][s] for s in ("dev", "validation")]
    assert sum(p["primary_cases"] for p in dev_val) == 1
    assert sum(p["secondary_cases(시각 C·D, 1차 제외)"] for p in dev_val) == 1
