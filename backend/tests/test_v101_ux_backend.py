"""v10.1 UX 리디자인의 백엔드 보조 필드 테스트: 연도별 실제 구간(공개)과 화면 선택(연도·분야) 맥락. 판정·해석에는 영향이 없다. 합성 입력만 사용."""
import pytest
from fastapi.testclient import TestClient

from app import cases as C
from app.accounts import api as A
from app.accounts.ratelimit import RateLimiter
from app.accounts.repo import SqliteRepo
from app.consult import agent, qa as QA, verdict as V
from app.main import app
from tests.test_v72_accounts import REQ, reg
from tools.bias_probe import charts

DOMS = ["overall", "wealth", "career"]


@pytest.fixture(scope="module")
def sample():
    ci = next(iter(charts(1, seed=44)))
    pre, _ = C.pre_for(ci, [2027])
    return ci, pre


def test_public_segments_mirror_engine_periods_and_are_consistent(sample):
    ci, pre = sample
    ys = list(range(2027, 2037))
    a = agent.answer(pre, "종합 상담을 시작합니다", domains_=DOMS, years=ys, depth="detailed")
    seg = a["verdict"]["segments"]
    assert set(seg) == {str(y) for y in ys}
    luck_notes = 0
    for y in ys:
        rows = seg[str(y)]
        assert rows[0]["from"] == f"{y}-01-01" and rows[-1]["to"] == f"{y}-12-31"
        assert abs(sum(r["share"] for r in rows) - 1) < 0.01 and sum(r["days"] for r in rows) in (365, 366)
        for prev, cur in zip(rows, rows[1:]):                           # 구간은 빈틈 없이 이어진다
            import datetime
            assert datetime.date.fromisoformat(cur["from"]) == datetime.date.fromisoformat(prev["to"]) + datetime.timedelta(days=1)
        assert all(r["label"].count("~") == 1 and "월" in r["label"] for r in rows)
        assert all(r["note"] for r in rows[1:])                           # 둘째 구간부터는 왜 나뉘는지(입춘/큰 흐름 교체)가 적혀 있다
        luck_notes += sum("10년 큰 흐름이 바뀜" in (r["note"] or "") for r in rows)
    assert luck_notes >= 1                                              # 10년 안에는 큰 흐름이 바뀌는 해가 있다
    assert any(r["note"] == "입춘 전: 전해의 기운이 적용되는 기간" for y in ys for r in seg[str(y)])


def test_segments_are_public_and_have_no_internal_terms(sample):
    ci, pre = sample
    a = agent.answer(pre, "종합 상담을 시작합니다", domains_=DOMS, years=[2028], depth="detailed")
    pub = V.public_view(a)["verdict"]
    assert "segments" in pub and "internal" not in pub
    text = str(pub["segments"])
    for w in ("sewun", "luck", "claim", "rule", "丁", "戊"):
        assert w not in text


def test_segments_do_not_change_any_judgement(sample, monkeypatch):
    ci, pre = sample
    run = lambda: agent.answer(pre, "종합 상담을 시작합니다", domains_=DOMS, years=[2028, 2029], depth="detailed")["verdict"]
    base = run()
    monkeypatch.setattr(V, "segments_public", lambda p: [])
    other = run()
    strip = lambda v: {k: x for k, x in v.items() if k != "segments"}
    assert strip(base) == strip(other)


# ---------------------------------------------------------------- 화면 선택 맥락
def test_focus_context_validates_and_drops_unknown_values():
    assert QA.focus_context([2027, 2028], 2028, "career") == {"year": 2028, "domain": "career"}
    assert QA.focus_context([2027, 2028], 2035, "career") == {"domain": "career"}          # 분석 범위 밖 연도는 버린다
    assert QA.focus_context([2027], 2027, "lottery") == {"year": 2027}                      # 모르는 분야는 버린다
    assert QA.focus_context([2027], None, "luck") == {}
    assert QA.focus_context([], 2027, None) == {}


def test_focus_fills_missing_year_and_domain_in_the_question_but_never_overrides_it(sample):
    ci, pre = sample
    ys = [2027, 2028, 2029]
    ask = lambda q, **ctx: agent.answer(pre, q, domains_=DOMS, years=ys, depth="detailed", context=ctx)["qa"]
    r = ask("이 시기에 주의할 점은?", year=2029, domain="wealth")
    assert r["kind"] in ("consider", "detail", "advice") and r.get("domain") == "wealth" and r.get("year") == 2029
    r2 = ask("2028년 직업 고려할 점은?", year=2029, domain="wealth")            # 질문에 연도·분야가 있으면 질문이 우선
    assert r2.get("domain") == "career" and r2.get("year") == 2028


def test_oneshot_ask_accepts_focus_and_it_does_not_change_the_analysis():
    c = TestClient(app)
    body = {"calendar": "solar", "birth_date": f"{1990:04d}-{5:02d}-{6:02d}", "birth_time": f"{10:02d}:{0:02d}", "gender": "female", "birth_place": "서울특별시",
            "years": [2027, 2028, 2029], "domains": DOMS, "question": "이 시기에 주의할 점은?"}
    plain = c.post("/api/v1/oneshot/ask", json=body)
    foc = c.post("/api/v1/oneshot/ask", json={**body, "focus_year": 2029, "focus_domain": "wealth"})
    assert plain.status_code == foc.status_code == 200
    assert foc.json()["verdict"] == plain.json()["verdict"]                       # 풀이 본문은 같다
    assert foc.json()["qa"].get("year") == 2029 and foc.json()["qa"].get("domain") == "wealth"
    bad = c.post("/api/v1/oneshot/ask", json={**body, "focus_year": 1800})
    assert bad.status_code == 422


def test_member_ask_uses_focus_over_previous_turn_context():
    A.configure(SqliteRepo(":memory:"), RateLimiter())
    c = TestClient(app)
    h = reg(c)
    rid = c.post("/api/v1/reports", json={"title": "x", "request": {**REQ, "years": [2027, 2028, 2029], "domains": ["overall", "wealth", "career"]}}, headers=h).json()["id"]
    first = c.post(f"/api/v1/reports/{rid}/ask", json={"question": "2027년 재물운 자세히 알려줘"}, headers=h).json()["answer"]["qa"]
    assert first["domain"] == "wealth" and first["year"] == 2027
    r = c.post(f"/api/v1/reports/{rid}/ask", json={"question": "이 시기에 고려할 점은?", "focus_year": 2029, "focus_domain": "career"}, headers=h).json()["answer"]["qa"]
    assert r["domain"] == "career" and r["year"] == 2029                          # 직전 답변(재물·2027)보다 화면 선택이 우선
