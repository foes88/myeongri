"""v10.1 대시보드형 결과 화면 브라우저 테스트(합성 입력). 레이아웃(5개 폭)·선택 상태 동기화·키보드·후속 질문 맥락·구간 표시."""
import json

import pytest

from tests.browser.test_oneshot_ui import _login_ui, fill, one, open_page  # noqa: F401  (fixture 재사용)

pytestmark = pytest.mark.browser
DOMS5 = ("overall", "wealth", "career", "love_marriage", "family")


def analyze(p, kind="r5", doms=DOMS5, y1="2027"):
    fill(p)
    p.fill("#y1", y1)
    p.select_option("#pk", kind)
    for cb in p.query_selector_all("#doms input"):
        want = cb.get_attribute("value") in doms
        if cb.is_checked() != want:
            cb.set_checked(want)
    p.click("#f button[type=submit]")
    p.wait_for_selector("#verdict .dash-conclusion .concl-text", timeout=60000)
    p.wait_for_function("document.querySelectorAll('#dash-dom-panel .dp-headline').length===1")


def box(p, sel):
    return p.evaluate("s=>{const r=document.querySelector(s).getBoundingClientRect();return {x:r.x,y:r.y+scrollY,w:r.width,h:r.height,b:r.bottom+scrollY}}", sel)


@pytest.mark.parametrize("size", ["360", "768", "1024", "1440", "1920"])
def test_layout_at_five_widths(browser, one, size):
    ctx, p, reqs, console = open_page(browser, one, size)
    analyze(p)
    vw, vh = p.evaluate("[document.documentElement.clientWidth, innerHeight]")
    assert not p.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")           # 가로 넘침 없음
    d = box(p, "#dash")
    assert d["w"] <= 1520                                                                                           # 최대 콘텐츠 폭
    if vw >= 1440:
        assert d["w"] / vw >= 0.72                                                                                  # 데스크톱 가로폭 활용
    c = box(p, "#verdict .concl-text")                                                                              # 핵심 결론이 첫 화면 안에 온전히 보인다
    assert c["y"] >= 0 and c["b"] <= vh, (c, vh)
    me, fl = box(p, ".dash-me"), box(p, ".dash-flow")
    if vw >= 1100:
        assert me["x"] < fl["x"] and abs(me["y"] - fl["y"]) < 80 and me["w"] / (me["w"] + fl["w"]) < 0.45             # 2열: 왼쪽이 더 좁다
    else:
        assert fl["y"] >= me["b"] - 5                                                                               # 1열로 쌓인다
    order = p.evaluate("['.dash-bar','.dash-conclusion','.dash-grid','.dash-domains'].map(s=>document.querySelector(s).getBoundingClientRect().top+scrollY)")
    assert order == sorted(order)                                                                                   # 컨트롤 바 → 결론 → 내 사주|시기 → 분야
    assert not [x for x in console if "PAGEERROR" in x or "Content Security" in x]
    ctx.close()


def test_timeline_selection_syncs_every_region(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    nodes = p.locator("#verdict .tl-node")
    assert nodes.count() == 5 and nodes.first.get_attribute("aria-pressed") == "true"                              # 처음에는 첫 해
    nodes.nth(3).click()                                                                                            # 2030
    pressed = p.locator("#verdict .tl-node[aria-pressed=true]")
    assert pressed.count() == 1 and pressed.get_attribute("data-year") == "2030"
    assert p.inner_text("#dash-year-panel h3") == "2030년"
    assert p.inner_text("#dash-dom-sub").startswith("2030년 기준")
    assert p.locator("#verdict .dgrid th.selcol").inner_text() == "2030"
    assert p.locator("#verdict .dgrid td.selcell").get_attribute("data-year") == "2030"
    assert p.inner_text("#ctxline") == "지금 보고 있는 것: 2030년 · 종합운"
    assert p.evaluate("window.MingliSel.year") == 2030 and p.evaluate("window.MingliSel.domain") == "overall"
    ctx.close()


def test_grid_cell_click_selects_year_and_domain_everywhere(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    p.locator("#verdict .dgrid .cell[data-year='2029'][data-domain='wealth']").click()
    assert p.locator("#verdict .dtab[aria-selected=true]").get_attribute("data-domain") == "wealth"
    assert p.inner_text("#dash-dom-panel .dp-head h3") == "재물운" and p.inner_text("#dash-year-panel h3") == "2029년"
    assert p.locator("#verdict .tl-node[aria-pressed=true]").get_attribute("data-year") == "2029"
    assert p.locator("#verdict .dgrid .cell[aria-pressed=true]").count() == 1
    assert p.inner_text("#ctxline") == "지금 보고 있는 것: 2029년 · 재물운"
    cell_label = p.inner_text("#verdict .dgrid .cell[data-year='2029'][data-domain='wealth'] .lab")             # 표 셀과 상세의 상태 표시가 같다
    assert cell_label in p.inner_text("#dash-dom-panel .dp-head .chip")
    ctx.close()


def test_domain_tabs_follow_arrow_keys_and_roles(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    assert p.get_attribute("#verdict .dtabs", "role") == "tablist" and p.locator("#verdict .dtab[role=tab]").count() == 5
    assert p.locator("#dash-dom-panel[role=tabpanel]").count() == 1
    p.locator("#verdict .dtab").first.focus()
    p.keyboard.press("ArrowRight")
    assert p.locator("#verdict .dtab[aria-selected=true]").get_attribute("data-domain") == "wealth"
    p.keyboard.press("End")
    assert p.locator("#verdict .dtab[aria-selected=true]").get_attribute("data-domain") == "family"
    p.keyboard.press("Home")
    assert p.locator("#verdict .dtab[aria-selected=true]").get_attribute("data-domain") == "overall"
    ctx.close()


def test_every_status_is_symbol_plus_text_not_color_only(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    for sel in ("#verdict .tl-node .tl-sym", "#verdict .dgrid .cell"):
        n = p.locator(sel).count()
        assert n >= 5
        for i in range(n):
            e = p.locator(sel).nth(i)
            assert e.locator(".sym").inner_text().strip() and e.locator(".lab").inner_text().strip()
    assert p.locator("#verdict .dlegend span").count() == 6 and "확률이나 점수도 아닙니다" in p.inner_text("#verdict .dgrid-wrap")
    ctx.close()


def test_one_year_and_five_year_views_agree_on_the_same_year(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)                                                                                                       # 5년: 2027~2031
    p.locator("#verdict .dgrid .cell[data-year='2028'][data-domain='wealth']").click()
    five = {"label": p.inner_text("#verdict .dgrid .cell[data-year='2028'][data-domain='wealth'] .lab"), "head": p.inner_text("#dash-dom-panel .dp-headline"),
            "overall": p.inner_text("#verdict .dgrid .cell[data-year='2028'][data-domain='overall'] .lab")}
    p.click("#dash-to1")
    p.wait_for_function("document.querySelectorAll('#verdict .tl-node').length===1", timeout=60000)
    p.click("#dash-next")                                                                                            # 2028 한 해만
    p.wait_for_function("(document.getElementById('dash-span')||{}).textContent==='2028년'", timeout=60000)
    p.locator("#verdict .dtab[data-domain=wealth]").click()
    one_y = {"label": p.inner_text("#verdict .dgrid .cell[data-year='2028'][data-domain='wealth'] .lab"), "head": p.inner_text("#dash-dom-panel .dp-headline"),
             "overall": p.inner_text("#verdict .dgrid .cell[data-year='2028'][data-domain='overall'] .lab")}
    assert one_y == five                                                                                             # 같은 해의 결론이 보기 범위와 무관하게 같다
    ctx.close()


def test_period_buttons_reflect_current_range_and_year_move(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    assert p.get_attribute("#dash-to5", "aria-pressed") == "true" and p.get_attribute("#dash-to1", "aria-pressed") == "false"
    assert p.inner_text("#dash-span") == "2027–2031년"
    p.click("#dash-next")
    p.wait_for_function("(document.getElementById('dash-span')||{}).textContent==='2028–2032년'", timeout=60000)
    p.click("#dash-prev")
    p.wait_for_function("(document.getElementById('dash-span')||{}).textContent==='2027–2031년'", timeout=60000)
    p.click("#dash-to10")
    p.wait_for_function("(document.getElementById('dash-span')||{}).textContent==='2027–2036년'", timeout=60000)
    assert p.get_attribute("#dash-to10", "aria-pressed") == "true" and p.locator("#verdict .tl-node").count() == 10
    p.click("#dash-edit")                                                                                            # 입력 수정: 폼이 다시 열린다
    p.wait_for_selector("#f", state="visible")
    ctx.close()


def test_followup_uses_the_year_and_domain_being_viewed(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    p.locator("#verdict .dgrid .cell[data-year='2029'][data-domain='wealth']").click()
    assert "재물운" in " ".join(p.locator("#chips .chipq").all_inner_texts())                                       # 추천 질문에 선택한 분야가 반영
    p.fill("#q2", "이 시기에 고려할 점은?")
    p.click("#askb")
    p.wait_for_selector("#out .record")
    ask = [pd for m, u, pd in reqs if m == "POST" and u.endswith("/oneshot/ask")][-1]
    b = json.loads(ask)
    assert b["focus_year"] == 2029 and b["focus_domain"] == "wealth"
    rec = p.locator("#out .record").last.inner_text()
    assert "2029" in rec and "재물" in rec
    ctx.close()


def test_split_year_shows_real_segments_with_boundaries(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    p.locator("#verdict .tl-node[data-year='2027']").click()
    panel = p.inner_text("#dash-year-panel")
    assert "이 해의 구간" in panel and "1월 1일~2월 3일" in panel and "입춘 전" in panel and "2월 4일~12월 31일" in panel
    assert "한 해 전체의 특징으로 읽지 않습니다" in panel
    assert p.locator("#verdict .tl-node[data-year='2027'] .tl-seg .segpart").count() == 2                            # 노드의 구간 막대
    grows = p.evaluate("[...document.querySelectorAll(\"#verdict .tl-node[data-year='2027'] .segpart\")].map(e=>+e.style.flexGrow)")
    assert abs(grows[0] - 0.093) < 0.01 and abs(grows[1] - 0.907) < 0.01                                             # 엔진의 일수 비율(34일 : 331일)
    ctx.close()


def test_keyboard_focus_is_visible_on_every_kind_of_control(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    for sel in ("#dash-to5", "#verdict .tl-node", "#verdict .dgrid .cell", "#verdict .dtab", "#verdict .fold summary"):
        p.locator(sel).first.focus()
        p.keyboard.press("Shift+Tab")
        p.keyboard.press("Tab")
        style = p.evaluate("(()=>{const s=getComputedStyle(document.activeElement);return [s.outlineStyle,parseFloat(s.outlineWidth)]})()")
        assert style[0] != "none" and style[1] >= 2, (sel, style)
    ctx.close()


def test_mobile_timeline_scrolls_inside_and_page_never_overflows(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "360")
    analyze(p, kind="r10")
    assert p.locator("#verdict .tl-node").count() == 10 and p.locator("#verdict .timeline.compact").count() == 1
    assert p.evaluate("(()=>{const t=document.querySelector('#verdict .timeline');return t.scrollWidth>t.clientWidth})()")           # 타임라인 자체가 가로 스크롤
    assert p.evaluate("(()=>{const t=document.querySelector('#verdict .dgrid-scroll');return t.scrollWidth>t.clientWidth})()")        # 표도 자체 스크롤
    assert not p.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    for sel in ("#dash-to5", "#dash-next", "#verdict .tl-node", "#verdict .dtab", "#verdict .dgrid .cell"):                         # 터치 영역 44px 이상
        assert p.locator(sel).first.bounding_box()["height"] >= 44, sel
    ctx.close()


def test_new_analysis_starts_from_first_year_and_overall(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    p.locator("#verdict .dgrid .cell[data-year='2030'][data-domain='career']").click()
    p.click("#dash-next")
    p.wait_for_function("(document.getElementById('dash-span')||{}).textContent==='2028–2032년'", timeout=60000)
    assert p.locator("#verdict .tl-node[aria-pressed=true]").get_attribute("data-year") == "2028"                    # 새 분석은 첫 해·종합에서 시작
    assert p.locator("#verdict .dtab[aria-selected=true]").get_attribute("data-domain") == "overall"
    ctx.close()
