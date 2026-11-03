"""v11.0 연도·월·분야·후속 질문 통합 흐름. 화면에서 고른 월이 질문 맥락이 되고, 질문에 적은 연도·월이 화면 선택보다 우선한다. 합성 입력만 사용."""
import pytest

from tests.browser.test_dashboard import analyze
from tests.browser.test_motion import settle
from tests.browser.test_oneshot_ui import fill, one, open_page  # noqa: F401

pytestmark = pytest.mark.browser


def open_months(p):
    p.click("#dash-months-toggle")
    p.wait_for_selector("#dash-months-body .mcell")


def test_selected_month_becomes_the_follow_up_context(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    open_months(p)
    p.locator("#dash-months-body .mcell").nth(3).click()
    span = p.inner_text("#dash-months-body .mcell[aria-pressed=true] .mspan")
    assert span in p.inner_text("#ctxline")                                              # 지금 보고 있는 월이 맥락 줄에 표시
    p.locator("#chips .chipq", has_text="이 달에는 무엇이 달라지나요").click()
    p.wait_for_selector("#out .record")
    rec = p.inner_text("#out .record >> nth=-1")
    assert "구간" in rec and "좋고 나쁨을 가르는 판정은 하지 않습니다" in rec and "참고로" in rec   # 월별 사실 + 판정 없음 + 해 전체 해석 구분
    ctx.close()


def test_question_year_and_month_override_the_screen_selection(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    p.locator("#verdict .tl-node[data-year='2029']").click()
    p.fill("#q2", "2028년 5월은 어떤가요?")
    p.click("#askb")
    p.wait_for_selector("#out .record")
    rec = p.inner_text("#out .record >> nth=-1")
    assert "2028년" in rec and "입하 구간" in rec                                       # 화면은 2029인데 질문의 2028년 5월이 우선
    ctx.close()


def test_next_and_previous_month_cross_year_boundaries(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    open_months(p)
    n = p.locator("#dash-months-body .mcell").count()
    p.locator("#dash-months-body .mcell").nth(n - 1).click()
    assert "2028년 첫 달" in p.inner_text("#dash-month-detail .mnav")
    p.click("#dash-month-detail .mnav .navbtn >> nth=1")
    assert p.inner_text("#dash-year-panel h3") == "2028년"
    assert p.get_attribute("#dash-months-body .mgrid", "aria-label").startswith("2028")
    assert "선택됨" in p.inner_text("#dash-months-body .mcell >> nth=0")
    p.click("#dash-month-detail .mnav .navbtn >> nth=0")                               # 2028 첫 달 → 2027 마지막 달
    assert p.inner_text("#dash-year-panel h3") == "2027년"
    last = p.locator("#dash-months-body .mcell").count() - 1
    assert "선택됨" in p.inner_text(f"#dash-months-body .mcell >> nth={last}")
    ctx.close()


def test_mobile_month_chips_and_no_overflow(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "360")
    analyze(p)
    settle(p)
    open_months(p)
    p.locator("#dash-months-body .mcell").nth(2).click()
    assert p.locator("#chips .chipq", has_text="이 달과 지난달은 무엇이 다른가요").count() == 1
    assert not p.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    ctx.close()
