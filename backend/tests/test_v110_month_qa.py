"""v11.0 월 단위 후속 질문 테스트. 월별 좋고 나쁨 판정이 없으므로 월 질문은 '사실·관계'와 '해 전체 해석'을 구분해 답해야 하며, 질문에 없는 월을 만들지 않는다. 합성 입력만 사용."""
import pytest
from fastapi.testclient import TestClient

from app import cases as C
from app.consult import agent, qa as QA
from app.main import app
from tools.bias_probe import charts

DOMS = ["overall", "wealth", "career"]
YEARS = [2027, 2028, 2029]


@pytest.fixture(scope="module")
def pre():
    ci = next(iter(charts(1, seed=44)))
    p, _ = C.pre_for(ci, [2027])
    return p


def ask(pre, q, ctx=None, years=YEARS, doms=DOMS):
    a = agent.answer(pre, q, domains_=doms, years=years, depth="detailed", context=ctx or {})
    return a["qa"]


def text(r):
    return r["text"] + " " + " ".join(r["points"])


def test_explicit_month_and_year_answer_with_facts_not_a_luck_verdict(pre):
    r = ask(pre, "2028년 5월은 어떤가요?")
    assert r["kind"] == "month" and r["year"] == 2028
    t = text(r)
    assert "입하 구간" in t and "좋고 나쁨을 가르는 판정은 하지 않습니다" in t
    assert "참고로" not in t and "해 전체 흐름은 이 답변에 섞지 않았습니다" in t       # 월 질문에 연간 해석을 섞지 않는다(월운의 빈자리를 연간 해석으로 채우지 않는다)
    r2 = ask(pre, "2028년 5월과 2028년 전체를 비교해 주세요")
    assert "해 전체 해석" in text(r2) and "월별 판정이 아니라" in text(r2)               # 연간 비교를 요청한 경우에만 연간 해석을 별도로 제공


def test_calendar_month_spanning_two_solar_terms_is_explained_honestly(pre):
    r = ask(pre, "2027년 3월에는 무엇이 달라지나요?")
    t = text(r)
    assert r["kind"] == "month" and "두 구간에 걸쳐" in t and "입춘 구간" in t and "경칩 구간" in t


def test_month_domain_priority_question_over_screen_over_none(pre):
    r = ask(pre, "5월 재물운을 설명해 주세요", ctx={"year": 2027, "domain": "career"})
    assert r["domain"] == "wealth" and r["year"] == 2027                              # 질문의 분야(재물)가 화면 분야(직업)보다 우선
    r2 = ask(pre, "5월은 어때요?", ctx={"year": 2029, "domain": "career"})
    assert r2["year"] == 2029 and r2["domain"] == "career"                            # 질문에 없으면 화면 맥락
    r3 = ask(pre, "2028년 5월은 어때요?", ctx={"year": 2029})
    assert r3["year"] == 2028                                                          # 질문의 연도가 화면보다 우선


def test_this_and_previous_month_use_the_selected_month_and_never_invent_one(pre):
    r = ask(pre, "이 달과 지난달은 무엇이 다른가요?", ctx={"year": 2027, "month": "2027-03-06"})
    t = text(r)
    assert r["kind"] == "month" and "경칩 구간" in t and "입춘 구간" in t
    none = ask(pre, "이 달은 어때요?", ctx={"year": 2027})
    assert none["kind"] == "unsupported" and "월을 선택" in none["text"]              # 선택한 월이 없으면 임의의 월을 만들지 않는다
    edge = ask(pre, "지난달은요?", ctx={"year": 2027, "month": "2027-01-02"})
    assert edge["kind"] == "unsupported"                                               # 해의 첫 구간 이전은 범위 밖


def test_month_without_a_year_in_a_multi_year_view_asks_for_the_year(pre):
    r = ask(pre, "3월은 어때요?")
    assert r["kind"] == "unsupported" and "연도" in r["text"]


def test_ipchun_boundary_and_luck_change_are_stated(pre):
    r = ask(pre, "2027년 2월은 어떤가요?")
    assert "입춘부터 그해의 기운이 적용됩니다" in text(r)


def test_unsupported_year_for_months_is_declared(pre):
    r = ask(pre, "2060년 3월은 어때요?")
    assert r["kind"] == "unsupported"                                                  # 분석 가능 범위(1901~2049) 밖이면 월을 만들지 않는다
    ok = ask(pre, "2040년 3월은 어때요?")
    assert ok["kind"] == "month" and ok["year"] == 2040                                # 범위 안의 연도는 질문에 적으면 함께 분석한다


def test_focus_month_only_used_when_it_matches_a_real_segment(pre):
    assert QA.focus_context(YEARS, 2027, "wealth", "2027-03-06")["month"] == "2027-03-06"
    assert "month" not in QA.focus_context(YEARS, 2027, None, "방금; drop table")
    r = ask(pre, "이 달은 어때요?", ctx={"year": 2027, "month": "2031-09-09"})
    assert r["kind"] == "unsupported"


def test_months_do_not_alter_year_answers(pre):
    r = ask(pre, "2027년 재물운을 자세히 알려줘")
    assert r["kind"] == "detail"                                                         # 월 언급이 없으면 기존 동작


def test_api_accepts_focus_month_and_does_not_change_the_analysis():
    c = TestClient(app)
    body = {"calendar": "solar", "birth_date": f"{1990:04d}-{5:02d}-{6:02d}", "birth_time": f"{10:02d}:{0:02d}", "gender": "female", "birth_place": "서울특별시",
            "years": [2027, 2028], "domains": DOMS, "question": "이 달은 무엇이 달라지나요?"}
    a = c.post("/api/v1/oneshot/ask", json={**body, "focus_year": 2027, "focus_month": "2027-03-06"})
    assert a.status_code == 200 and a.json()["qa"]["kind"] == "month"
    b = c.post("/api/v1/oneshot/ask", json={**body, "focus_year": 2027, "focus_month": "2027-03-06", "question": "종합 상담을 시작합니다"})
    c2 = c.post("/api/v1/oneshot/ask", json={**body, "question": "종합 상담을 시작합니다"})
    assert b.json()["verdict"]["blocks"] == c2.json()["verdict"]["blocks"] if "blocks" in b.json()["verdict"] else b.json()["verdict"]["period"] == c2.json()["verdict"]["period"]


def test_member_month_question_with_screen_month_survives_reopen_and_stays_isolated():
    from app.accounts import api as A
    from app.accounts.ratelimit import RateLimiter
    from app.accounts.repo import SqliteRepo
    from tests.test_v72_accounts import REQ, reg
    A.configure(SqliteRepo(":memory:"), RateLimiter())
    c = TestClient(app)
    h = reg(c)
    rid = c.post("/api/v1/reports", json={"title": "x", "request": {**REQ, "years": [2027, 2028, 2029], "domains": ["overall", "wealth", "career"]}}, headers=h).json()["id"]
    r = c.post(f"/api/v1/reports/{rid}/ask", json={"question": "이 달에는 무엇이 달라지나요?", "focus_year": 2028, "focus_month": "2028-05-06", "focus_domain": "wealth"}, headers=h)
    qa = r.json()["answer"]["qa"]
    assert qa["kind"] == "month" and qa["year"] == 2028 and qa["domain"] == "wealth"
    assert "입하 구간" in qa["text"] + " ".join(qa["points"])
    # 후속 질문이 이어지고(직전 답변 맥락), 월 질문 기록이 저장·재열람된다
    r2 = c.post(f"/api/v1/reports/{rid}/ask", json={"question": "그럼 지난달과는 무엇이 다른가요?", "focus_year": 2028, "focus_month": "2028-05-06"}, headers=h)
    assert r2.json()["answer"]["qa"]["kind"] == "month"
    got = c.get(f"/api/v1/reports/{rid}", headers=h)
    assert got.status_code == 200 and "입하" in got.text and "month" in got.text      # 재열람해도 월 질문 기록이 남아 있다
    # 다른 사용자는 접근할 수 없다
    other = reg(c, "other@example.com")
    assert c.post(f"/api/v1/reports/{rid}/ask", json={"question": "이 달은?", "focus_year": 2028, "focus_month": "2028-05-06"}, headers=other).status_code == 404
    assert c.get(f"/api/v1/reports/{rid}", headers=other).status_code == 404
