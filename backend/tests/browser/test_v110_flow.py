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
    assert "구간" in rec and "좋고 나쁨을 가르는 판정은 하지 않습니다" in rec and "참고로" not in rec   # 월별 사실 + 판정 없음, 연간 해석은 섞지 않는다
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
    assert p.inner_text("#h-concl") == "2028년의 흐름"
    assert p.get_attribute("#dash-months-body .mgrid", "aria-label").startswith("2028")
    assert "선택됨" in p.inner_text("#dash-months-body .mcell >> nth=0")
    p.click("#dash-month-detail .mnav .navbtn >> nth=0")                               # 2028 첫 달 → 2027 마지막 달
    assert p.inner_text("#h-concl") == "2027년의 흐름"
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


def test_no_forced_line_breaks_in_rendered_text_and_korean_wraps_naturally(browser, one):
    """한 줄 길이 제한은 CSS 본문 폭(max-width, em 단위)으로만 한다. 문장 중간에 개행·<br> 을 넣지 않아 복사·저장·읽어 주기에 영향이 없다."""
    ctx, p, reqs, console = open_page(browser, one, "360")
    analyze(p)
    settle(p)
    p.click("#dash-months-toggle")
    p.wait_for_selector("#dash-months-body .mcell")
    assert p.evaluate("document.querySelectorAll('#dash br').length") == 0
    assert p.evaluate("[...document.querySelectorAll('#dash p, #dash li, #dash .yp-para span, #dash .mv')].filter(e=>e.textContent.includes(String.fromCharCode(10))).length") == 0
    assert p.evaluate("getComputedStyle(document.querySelector('.yp-para span')).wordBreak") == "keep-all"            # 한국어는 어절 단위로 줄바꿈
    mw = p.evaluate("getComputedStyle(document.querySelector('.yp-para')).maxWidth")
    assert mw.endswith("px") and float(mw[:-2]) >= 300                                                                  # em 기반 폭 제한(약 40자)
    assert p.evaluate("[...document.querySelectorAll('#dash p, #dash li')].every(e=>e.getBoundingClientRect().right<=document.documentElement.clientWidth+1)")
    # 결론 글은 모바일에서 인장 때문에 좁아지지 않는다(본문 폭을 거의 다 쓴다)
    w = p.evaluate("(()=>{const c=document.querySelector('.concl-text').getBoundingClientRect(),b=document.querySelector('.dash-conclusion').getBoundingClientRect();return c.width/b.width})()")
    assert w > 0.85
    ctx.close()


def test_empty_month_state_is_explained_not_blank(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")

    def strip_months(route):
        resp = route.fetch()
        body = resp.json()
        ((body.get("answer") or {}).get("verdict") or {}).pop("months", None)
        route.fulfill(response=resp, json=body)

    p.route("**/api/v1/oneshot/analyze", strip_months)
    analyze(p)
    settle(p)
    assert p.locator(".dash-months").is_visible()
    assert "월별 흐름이 들어 있지 않습니다" in p.inner_text(".dash-months")
    assert not p.is_visible("#dash-months-toggle")                                                                       # 열 수 없는 버튼을 보여 주지 않는다
    assert not p.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    ctx.close()


def test_month_changes_are_not_listed_twice_for_overall(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    p.click("#dash-months-toggle")
    p.wait_for_selector("#dash-month-detail")
    for i in range(p.locator("#dash-months-body .mcell").count()):
        p.locator("#dash-months-body .mcell").nth(i).click()
        items = p.evaluate("[...document.querySelectorAll('#dash-month-detail .mrow')].filter(r=>r.textContent.startsWith('달라지는 점')).flatMap(r=>[...r.querySelectorAll('li')].map(l=>l.textContent.split(' — ')[0]))")
        assert len(items) == len(set(items)), items                                                                      # 같은 문구가 분야마다 반복되지 않는다
    ctx.close()


def test_no_identical_advice_sentence_appears_twice_on_one_screen(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    for dom in ("overall", "wealth", "career", "love_marriage", "family"):
        p.locator(f"#verdict .dtab[data-domain={dom}]").click()
        top = p.evaluate("[...document.querySelectorAll('#dash-year-panel .yp-think li')].map(l=>l.textContent)")
        low = p.evaluate("[...document.querySelectorAll('#dash-dom-panel .dp-side li')].map(l=>l.textContent)")
        assert not (set(top) & set(low)), (dom, set(top) & set(low))
    ctx.close()
