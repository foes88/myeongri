"""v11.2b 텍스트 밀도 축소 회귀: 기본 화면은 요약만, 상세는 접힘(원문 보존). 요약은 기존 원문의 문장이거나 구간 수 같은 사실일 뿐 새 판정·주장이 아니다. 합성 입력만 사용."""
import re

import pytest

from tests.browser.test_dashboard import analyze
from tests.browser.test_motion import settle
from tests.browser.test_oneshot_ui import fill, one, open_page  # noqa: F401
from tests.browser.test_v112_report import capture_analysis, norm

pytestmark = pytest.mark.browser
SENT = re.compile(r"[.!?](\s|$)")


def n_sent(t):
    return len(SENT.findall(t.strip()))


def test_hero_is_one_sentence_plus_a_short_helper_and_the_full_original_is_one_click_away(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    box = capture_analysis(p)
    analyze(p)
    settle(p)
    v = box["a"]["verdict"]
    head = next(b for b in v["detail"]["2027"]["blocks"] if b["domain"] == "overall")["headline"]
    lead, sub = p.inner_text(".concl-text"), p.inner_text(".hero-sub")
    assert n_sent(lead) == 1 and n_sent(sub) <= 1 and norm(lead) in norm(head) and norm(sub) in norm(head)                  # 새 문장을 만들지 않는다(원문의 앞 두 문장)
    assert p.evaluate("(()=>{const e=document.querySelector('.hero-sub');return e.scrollHeight<=e.clientHeight+1})()")      # 보조 설명은 두 줄 이내에 모두 들어온다
    assert p.evaluate("document.querySelector('.hero-more').open") is False
    p.click(".hero-more summary")
    assert norm(head) in norm(p.inner_text(".hero-extra"))                                                                 # 핵심 해석 전문(원문 그대로)
    ctx.close()


def test_changes_are_three_items_of_title_plus_one_sentence_and_summaries_are_existing_text_or_facts(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    box = capture_analysis(p)
    analyze(p)
    settle(p)
    a = box["a"]
    v = a["verdict"]
    items = p.locator(".dash-changes .chg-item")
    assert 1 <= items.count() <= 3
    row = next(r for r in v["period"]["years"] if r["year"] == 2027)
    ow = next(b for b in v["detail"]["2027"]["blocks"] if b["domain"] == "overall")
    theme = next((z["theme"] for z in v["profile"]["sipsung"]["years"] if z["year"] == 2027), "")
    sources = [row.get("change") or "", row.get("caution") or "", theme] + list((ow.get("why") or {}).get("against") or [])
    seg_n = len(v["segments"]["2027"])
    for i in range(items.count()):
        it = items.nth(i)
        assert it.locator("h3").count() == 1 and it.locator(":scope > p").count() == 1                                      # 제목 1개 + 요약 1문장
        one_line = it.locator(":scope > p").inner_text()
        assert n_sent(one_line) <= 1
        ok = re.fullmatch(rf"이 해는 {seg_n}개 구간으로 나뉩니다\.", one_line) or any(norm(one_line) in norm(s) for s in sources if s)
        assert ok, one_line                                                                                                 # 원문의 문장이거나 구간 수(사실)
    # 접힌 상세는 모두 원문이며 기본으로는 보이지 않는다
    assert p.locator(".dash-changes .chg-more[open]").count() == 0
    ctx.close()


def test_domain_panel_has_summary_then_topics_then_a_folded_source_area(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    for dom in ("overall", "wealth", "career"):
        p.locator(f"#verdict .dtab[data-domain={dom}]").click()
        head = p.inner_text("#dash-dom-panel .dp-headline")
        assert head and n_sent(head) <= 2                                                                                   # A: 핵심 요약 최대 2문장
        assert p.evaluate("+getComputedStyle(document.querySelector('#dash-dom-panel .dp-headline')).fontWeight") <= 500   # 문장 전체를 굵게 하지 않는다
        topics = p.locator("#dash-dom-panel .dp-topics > .dp-topic")                                                        # B: 기본으로 보이는 주제(중요한 것만, 없으면 만들지 않는다)
        for i in range(topics.count()):
            t = topics.nth(i)
            assert t.locator("h4").count() == 1 and len(t.locator("h4").inner_text()) >= 4
            body = " ".join(x.inner_text() for x in t.locator("p, li").all())
            assert 1 <= n_sent(body) <= 5
        assert p.locator("#dash-dom-panel .dp-more").evaluate("e=>e.open") is False                                         # C: 원문과 근거는 접힘
        assert "전체 해석과 근거 보기" in p.locator("#dash-dom-panel .dp-more > summary").text_content()
        p.locator("#dash-dom-panel .dp-more > summary").click()
        heads = p.evaluate("[...document.querySelectorAll('#dash-dom-panel .dp-more .dp-src h4')].map(h=>h.textContent)")
        assert heads and set(heads) <= {"전체 해석", "명리 용어 설명", "해석 근거", "상반되는 근거와 한계"}                      # 비어 있는 항목은 만들지 않는다
    ctx.close()


def test_flow_legend_status_and_evidence_are_folded_and_key_years_come_first(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    assert p.locator(".legend-fold").evaluate("e=>e.open") is False and not p.locator(".dlegend").is_visible()               # 범례·긴 안내는 접힘
    assert p.locator("#dash-months-body").evaluate("e=>e.hidden") is True                                                    # 월별 상세 접힘
    assert p.locator("#status details").evaluate("e=>e.open") is False and "계산 상태" in p.inner_text("#status summary")     # 계산 상태는 한 줄 요약 + 접힘
    assert p.locator("#dash-evidence").evaluate("e=>e.open") is False
    keys = p.locator(".key-years .keyyear")
    assert 1 <= keys.count() <= 3                                                                                           # 먼저 볼 시기 최대 3개
    y = int(keys.last.inner_text().replace("년", ""))
    keys.last.click()
    assert p.locator("#verdict .tl-node[aria-pressed=true]").get_attribute("data-year") == str(y)                           # 눌러서 그 해를 선택
    ctx.close()


@pytest.mark.parametrize("size", ["360", "1440"])
def test_question_is_reachable_from_the_first_screen_and_sits_before_save_and_status(browser, one, size):
    ctx, p, reqs, console = open_page(browser, one, size)
    analyze(p)
    settle(p)
    vh = p.evaluate("innerHeight")
    btn = p.locator(".hero-ask")
    bb = btn.bounding_box()
    assert btn.is_visible() and 0 <= bb["y"] and bb["y"] + bb["height"] <= vh and bb["height"] >= 44                         # 첫 화면에 보이고 터치 영역 충분
    order = p.evaluate("['#session','#acct','#status'].map(s=>document.querySelector(s).getBoundingClientRect().top+scrollY)")
    assert order == sorted(order)                                                                                           # 질문 → 저장 → 계산 상태(한 줄 요약)
    btn.click()
    p.wait_for_function("document.activeElement && document.activeElement.id==='q2'", timeout=3000)                          # 눌러서 질문창으로 이동·입력 가능
    p.wait_for_function("(()=>{const r=document.getElementById('q2').getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight})()", timeout=5000)   # 부드럽게 이동한 뒤 질문창이 화면 안에 온다
    assert not p.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    ctx.close()


def test_visible_text_volume_stays_low_by_default(browser, one):
    """기본 화면(접힘 상태)에 보이는 글자 수가 늘지 않게 하는 상한(합성 5년 기준 측정값 1,200자 수준에 여유)."""
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    n = p.evaluate("""()=>{const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let t=0,n;while(n=w.nextNode()){const e=n.parentElement;if(!e||!e.checkVisibility())continue;t+=n.textContent.replace(/\\s+/g,'').length}return t}""")
    assert n <= 1900, n                                                                                                    # v11.3: 주제별 해석이 기본으로 보이므로 상한을 1,900자로(측정값은 docs/41)
    ctx.close()
