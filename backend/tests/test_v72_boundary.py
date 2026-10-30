"""시(時) 경계 근접 안내 테스트. 가상 입력."""
from datetime import datetime

import pytest

from app.astro_core import calculate_chart
from app.astro_core.engine import HOUR_NEAR_MINUTES, TimeProfile, hour_boundary_notice


def chart(h, m, **kw):  # 가상 입력
    return calculate_chart(year=1990, month=6, day=15, hour=h, minute=m, gender="male", **kw)


@pytest.mark.parametrize("h,m,near", [(12, 59, True), (13, 0, True), (13, 5, True), (13, 30, False), (14, 0, False), (14, 52, True), (0, 55, True)])
def test_notice_flags_only_near_odd_hour_boundaries(h, m, near):
    pt = datetime(1990, 6, 15, h, m)
    assert hour_boundary_notice(pt, True, "user", 127.0)["near"] is near


def test_unknown_hour_has_no_notice_and_threshold_is_symmetric():
    assert hour_boundary_notice(datetime(1990, 6, 15, 12), False, "table:x", 127.0) == {"near": False, "minutes_to_boundary": None, "messages": []}
    a = hour_boundary_notice(datetime(1990, 6, 15, 12, 60 - HOUR_NEAR_MINUTES), True, "user", 127.0)
    b = hour_boundary_notice(datetime(1990, 6, 15, 13, HOUR_NEAR_MINUTES), True, "user", 127.0)
    assert a["near"] and b["near"] and not hour_boundary_notice(datetime(1990, 6, 15, 13, HOUR_NEAR_MINUTES + 1), True, "user", 127.0)["near"]


def test_chart_exposes_notice_without_changing_status_and_mentions_table_coordinates():
    base = chart(13, 2)
    hb = base.verification["hour_boundary"]
    assert hb["near"] and any("다시 확인" in m for m in hb["messages"]) and any("근사값" in m and "직접 입력" in m for m in hb["messages"])
    user = chart(13, 2, longitude=127.4, latitude=36.5)  # 경도를 직접 입력하면 좌표 근사 안내는 빠지고 시각 안내만 남는다
    assert user.verification["hour_boundary"]["near"] and not any("근사값" in m for m in user.verification["hour_boundary"]["messages"])
    far = chart(14, 0)
    assert not far.verification["hour_boundary"]["near"]
    assert base.verification["status"] == chart(13, 40).verification["status"]  # 등급 판정은 영향 없음


def test_solar_profile_shift_moves_the_boundary_distance():
    civil = chart(13, 2)
    mean = chart(13, 2, time_profile=TimeProfile.LOCAL_MEAN_SOLAR_TIME)
    assert civil.verification["hour_boundary"]["minutes_to_boundary"] != mean.verification["hour_boundary"]["minutes_to_boundary"]


def test_status_matrix_follows_gates_and_never_overclaims(monkeypatch):
    from app.astro_core import status_matrix as SM
    from app.astro_core import verification_levels as vl
    m = {r["element"]: r for r in SM.matrix("solar")}
    sc = vl.scope_status("solar")
    assert (m["양력 입력의 연·월·일주(절기 경계 포함)"]["status"] == "VERIFIED") == sc["CORE_VALIDATED"]["granted"]
    assert m["대운 방향·시작 시점"]["status"] == ("VERIFIED" if sc["DAEUN_PROFILE_VALIDATED"]["granted"] else "PARTIAL")
    assert m["시주(시지·오서둔)"]["status"] != "VERIFIED" and m["한국 역사적 표준시·서머타임"]["status"] == "CONFLICT"
    for r in m.values():
        assert r["commercial_guarantee"] == (r["status"] == "VERIFIED")  # 보증은 VERIFIED 만
        assert r["evidence"] and (r["status"] == "VERIFIED" or r["blockers"])  # 미검증에는 사유가 있다
    s = SM.summary("solar")
    assert not s["v1_granted"] and s["v1_blockers"] and sum(s["counts"].values()) == len(s["elements"])


def test_matrix_endpoint_and_gate_change_propagates(monkeypatch):
    from fastapi.testclient import TestClient

    from app.astro_core import verification_levels as vl
    from app.main import app
    c = TestClient(app)
    r = c.get("/api/v1/verification/matrix").json()
    assert r["counts"]["CONFLICT"] >= 1 and r["elements"]
    real = vl.scope_status

    def granted_all(cal, year=None):
        s = real(cal, year)
        s["DAEUN_PROFILE_VALIDATED"] = dict(s["DAEUN_PROFILE_VALIDATED"], granted=True, blockers=[])
        return s
    monkeypatch.setattr(vl, "scope_status", granted_all)
    assert {e["element"]: e["status"] for e in c.get("/api/v1/verification/matrix").json()["elements"]}["대운 방향·시작 시점"] == "VERIFIED"
