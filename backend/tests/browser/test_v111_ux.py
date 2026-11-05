"""v11.1 최종 UI/UX 회귀: 한 페이지 스크롤(내부 세로 스크롤 없음), 1·5·10년 화면 구성, 모드 전환 시 맥락 유지, 중복 제거가 정보를 지우지 않음, 오행 도식·데이터 일치, 본문 타이포. 합성 입력만 사용."""
import pytest

from tests.browser.test_dashboard import analyze
from tests.browser.test_motion import settle
from tests.browser.test_oneshot_ui import fill, one, open_page  # noqa: F401

pytestmark = pytest.mark.browser
SIZES = ["360", "768", "1024", "1440", "1920"]


@pytest.mark.parametrize("size", SIZES)
def test_no_independent_vertical_scroll_and_left_panel_is_not_fixed(browser, one, size):
    ctx, p, reqs, console = open_page(browser, one, size)
    analyze(p)
    settle(p)
    assert p.evaluate("document.getElementById('dash-evidence').open") is False and p.is_visible("#dash-evidence > summary")   # 해석의 근거: 기본 접힘, 열기 쉬움
    p.click("#dash-evidence > summary")
    p.click("#dash-months-toggle")
    p.wait_for_selector("#dash-months-body .mcell")
    bad = p.evaluate("""()=>[...document.querySelectorAll('#dash *')].filter(e=>{const c=getComputedStyle(e);
      return (c.overflowY==='auto'||c.overflowY==='scroll') && e.scrollHeight>e.clientHeight+2}).map(e=>e.className||e.tagName)""")
    assert bad == []                                                                                                     # 페이지 안의 또 다른 세로 스크롤 영역이 없다
    st = p.evaluate("(()=>{const c=getComputedStyle(document.querySelector('.dash-me'));return [c.position,c.maxHeight,c.overflowY]})()")
    assert st[0] == "static" and st[1] == "none" and st[2] == "visible"                                                  # 고정·높이 제한·스크롤 없음
    assert not p.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    ctx.close()


def test_one_year_has_no_timeline_or_single_column_table_but_five_and_ten_keep_comparison(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p, kind="year")
    settle(p)
    assert p.locator("#verdict .tl-node").count() == 0 and p.locator("#verdict .dgrid").count() == 0 and p.locator("#verdict .timeline").count() == 0
    assert p.inner_text("#h-flow").endswith("시기별 흐름") and p.is_visible("#dash-months-toggle")                        # 한 해는 월별 흐름으로 이어진다
    assert p.locator("#verdict .dtab").count() == 5
    p.click("#dash-to5")
    p.wait_for_function("document.querySelectorAll('#verdict .tl-node').length===5", timeout=60000)
    assert p.locator("#verdict .dgrid").count() == 1 and p.inner_text("#h-flow").endswith("시기별 흐름")
    p.click("#dash-to10")
    p.wait_for_function("document.querySelectorAll('#verdict .tl-node').length===10", timeout=60000)
    assert p.locator("#verdict .timeline.compact").count() == 1 and p.locator("#verdict .dgrid").count() == 1
    ctx.close()


def test_mode_switch_keeps_year_domain_and_month_context(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    p.locator("#verdict .tl-node[data-year='2029']").click()
    p.locator("#verdict .dtab[data-domain=career]").click()
    p.click("#dash-months-toggle")
    p.wait_for_selector("#dash-months-body .mcell")
    p.locator("#dash-months-body .mcell").nth(4).click()
    before = p.evaluate("window.MingliSel")
    p.click("#dash-to10")
    p.wait_for_function("document.querySelectorAll('#verdict .tl-node').length===10", timeout=60000)
    after = p.evaluate("window.MingliSel")
    assert after["year"] == 2029 and after["domain"] == "career" and after["month"] == before["month"]                  # 연도·분야·월 유지
    assert p.is_visible("#dash-month-detail")                                                                            # 열어 둔 월별 흐름도 유지
    p.click("#dash-to1")
    p.wait_for_function("document.querySelectorAll('#verdict .tl-node').length===0", timeout=60000)
    one_y = p.evaluate("window.MingliSel")
    assert one_y["year"] == 2029 and one_y["domain"] == "career"
    assert "2029년" in p.inner_text("#ctxline")
    ctx.close()


def test_dedup_never_drops_a_sentence_that_is_not_shown_in_the_hero_or_changes(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    for y in (2027, 2028, 2029):
        p.locator(f"#verdict .tl-node[data-year='{y}']").click()
        for dom in ("overall", "wealth", "career", "love_marriage", "family"):
            p.locator(f"#verdict .dtab[data-domain={dom}]").click()
            res = p.evaluate("""()=>{const pn=document.querySelector('#dash-dom-panel'),yp=(document.querySelector('.dash-conclusion').textContent+document.querySelector('.dash-changes').textContent).replace(/\\s+/g,'');
              const keys=(pn.dataset.dropkeys||'').split('|').filter(Boolean);return {n:+pn.dataset.deduped,missing:keys.filter(k=>yp.indexOf(k)<0)}}""")
            assert res["missing"] == [], (y, dom, res)                                                                     # 지운 문장은 모두 해 패널에 그대로 있다
            if dom != "overall":
                assert res["n"] == 0                                                                                       # 종합운 외 분야는 아무 것도 지우지 않는다
    ctx.close()


def test_five_elements_bars_are_default_wheel_is_a_folded_aid_and_numbers_match(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    p.click("#dash-evidence > summary")                                                                                  # 오행은 해석의 근거 안에 있다
    assert p.is_visible(".ebars") and p.get_attribute(".wheel-fold", "open") is None
    assert not p.is_visible(".wheel")                                                                                    # 순환도는 접힌 보조 설명
    assert "오행이 서로 돕는 관계 알아보기" in p.inner_text(".wheel-fold summary")
    assert "강약이나 운세 점수가 아니며" in p.inner_text(".me-elements")                                                  # 숫자가 무엇을 세는지·오해 방지
    bars = p.evaluate("[...document.querySelectorAll('.ebars .ecol')].map(c=>[c.querySelector('.ename').textContent,+c.querySelector('.enum').textContent])")
    p.click(".wheel-fold summary")
    wheel = p.evaluate("[...document.querySelectorAll('.wheel .wnode')].map(g=>[g.querySelector('.wname').textContent,+g.querySelector('.wnum').textContent])")
    assert dict(bars) == dict(wheel) and len(bars) == 5                                                                  # 막대와 순환도의 값이 같다
    han = p.evaluate("document.querySelectorAll('#status table.pillars td.g').length")
    assert sum(v for _, v in bars) == han                                                                                # 센 글자 수 = 네 기둥 글자 수
    assert len(set(p.evaluate("[...document.querySelectorAll('.wheel .wc')].map(c=>c.getAttribute('r'))"))) == 1         # 원 크기 동일
    ctx.close()


@pytest.mark.parametrize("size", ["360", "1440"])
def test_body_typography_is_readable_and_has_no_forced_breaks(browser, one, size):
    ctx, p, reqs, console = open_page(browser, one, size)
    analyze(p)
    settle(p)
    f = p.evaluate("""()=>{const q=s=>getComputedStyle(document.querySelector(s));const px=v=>parseFloat(v);
      const b=q('.yp-para span'),l=px(b.lineHeight)/px(b.fontSize);return {body:px(b.fontSize),lh:l,concl:px(q('.concl-text').fontSize),yp:px(q('.yp-core .yp-change').fontSize),
        dom:px(q('.dp-story').fontSize),sec:px(q('.dash-flow h2').fontSize),gap:px(q('.yp-para').marginTop),sub:px(q('.hero-sub').fontSize),chg:px(q('.chg-item p').fontSize)}}""")
    assert 16 <= f["body"] <= 18 and 1.65 <= f["lh"] <= 1.85 and f["dom"] >= 16                                         # 본문 16px 전후, 행간 1.65~1.8
    assert f["concl"] >= 26 and f["sub"] >= 17 and f["chg"] >= 16 and f["sec"] >= 24 and f["gap"] >= 14                  # 핵심 해석 26px 이상(가장 큰 글자), 보조 17px, 제목 24px 이상, 문단 간격
    assert p.evaluate("document.querySelectorAll('#dash br').length") == 0
    ctx.close()


def test_table_cell_click_brings_the_domain_panel_into_view(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    p.evaluate("window.scrollTo(0, document.querySelector('.dash-flow').offsetTop)")
    p.locator("#verdict .dgrid .cell[data-year='2028'][data-domain='wealth']").click()
    p.wait_for_function("(()=>{const r=document.querySelector('.dash-domains').getBoundingClientRect();return r.top<innerHeight&&r.bottom>0})()", timeout=4000)
    assert p.locator("#verdict .dtab[aria-selected=true]").get_attribute("data-domain") == "wealth" and p.inner_text("#dash-dom-panel .dp-head h3") == "재물운"
    ctx.close()
    ctx, p, reqs, console = open_page(browser, one, "1440", reduced="reduce")
    analyze(p)
    p.evaluate("window.scrollTo(0, document.querySelector('.dash-flow').offsetTop)")
    p.locator("#verdict .dgrid .cell[data-year='2029'][data-domain='career']").click()
    p.wait_for_function("(()=>{const r=document.querySelector('.dash-domains').getBoundingClientRect();return r.top<innerHeight&&r.bottom>0})()", timeout=2000)   # 움직임 줄이기: 즉시 이동
    ctx.close()
