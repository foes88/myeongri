from fastapi.testclient import TestClient

from app.main import app

c = TestClient(app)


def test_calculate_endpoint_returns_unverified_chart():
    r = c.post("/api/v1/calendar/calculate", json={"birth_date": "2000-01-01", "birth_time": "19:25", "gender": "male"})  # 가상 입력
    assert r.status_code == 200
    j = r.json()
    assert j["pillars"]["day"] == "戊午" and j["verification"]["may_claim_verified"] is False


def test_calculate_endpoint_rejects_invalid():
    r = c.post("/api/v1/calendar/calculate", json={"birth_date": "1850-01-01", "gender": "male"})
    assert r.status_code == 422
