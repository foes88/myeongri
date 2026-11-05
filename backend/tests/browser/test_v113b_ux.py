"""v11.3b 감사 후속: 핵심 판정·주의사항이 잘리지 않음, 구조화된 신호(좋은 흐름/조심할 점)가 응답과 일치, A/B/C 한 문장은 한 번만, 중요 주제만 기본 표시, 키보드 조작, '원문' 표현 정정. 합성 입력만 사용."""
import re

import pytest

from tests.browser.test_dashboard import analyze
from tests.browser.test_motion import settle
from tests.browser.test_oneshot_ui import fill, one, open_page  # noqa: F401
from tests.browser.test_v112_report import capture_analysis, norm

pytestmark = pytest.mark.browser
LONG_CAUTION = "다만 가까운 관계에서는 서로의 기대가 어긋나기 쉬워 말과 일정을 미리 맞추고, 큰 지출이나 계약은 조건과 기간을 문서로 확인한 뒤 진행하는 편이 좋습니다."


def long_headline_route(p):
    """합성 응답의 종합운 머리 문장 뒤에 긴 주의 문장을 붙여, 어느 폭에서도 잘리지 않는지 확인한다(표시 계층 검증용 대역)."""
    def handler(route):
        resp = route.fetch()
        body = resp.json()
        for d in (((body.get("answer") or {}).get("verdict") or {}).get("detail") or {}).values():
            for blk in d["blocks"]:
                if blk["domain"] == "overall":
                    blk["headline"] = blk["headline"].rstrip() + " " + LONG_CAUTION
        route.fulfill(response=resp, json=body)
    p.route("**/api/v1/oneshot/analyze", handler)


@pytest.mark.parametrize("size", ["360", "768", "1440"])
def test_the_hero_never_clips_the_key_judgement_or_the_caution(browser, one, size):
    ctx, p, reqs, console = open_page(browser, one, size)
    long_headline_route(p)
    analyze(p)
    settle(p)
    sub = p.locator(".hero-sub")
    assert LONG_CAUTION in sub.inner_text()                                                                                  # 주의 문장이 접힘으로 밀려나지 않고 첫 화면 본문에 있다
    st = p.evaluate("(()=>{const e=document.querySelector('.hero-sub'),c=getComputedStyle(e);return [e.scrollHeight<=e.clientHeight+1,c.overflow,c.webkitLineClamp||c.getPropertyValue('-webkit-line-clamp'),c.display]})()")
    assert st[0] is True and st[1] == "visible" and st[2] in ("none", "", "unset") and st[3] == "block"                    # 줄 수 제한(line-clamp)이 없다
    assert not p.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    ctx.close()


def test_hero_shows_the_whole_headline_of_the_engine_not_only_two_sentences(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "360")
    box = capture_analysis(p)
    analyze(p)
    settle(p)
    v = box["a"]["verdict"]
    for y in (2027, 2028):
        p.locator(f"#verdict .tl-node[data-year='{y}']").click()
        head = next(b for b in v["detail"][str(y)]["blocks"] if b["domain"] == "overall")["headline"]
        shown = norm(p.inner_text(".concl-text") + p.inner_text(".hero-sub"))
        assert norm(head) == shown, (y, head[:50])                                                                           # 머리 문장 전체가 핵심 해석에 보인다
    ctx.close()


def test_good_and_caution_signals_are_the_engines_structured_data_and_never_invented(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    box = capture_analysis(p)
    analyze(p)
    settle(p)
    v = box["a"]["verdict"]
    for y in (2027, 2028, 2029):
        p.locator(f"#verdict .tl-node[data-year='{y}']").click()
        sig = next(b for b in v["detail"][str(y)]["blocks"] if b["domain"] == "overall")["signals"]
        rows = p.evaluate("[...document.querySelectorAll('.hero-signals > div')].map(r=>[r.querySelector('dt').textContent,r.querySelector('dd').textContent])")
        for label, text in rows:
            src = sig["support"] if label == "좋은 흐름" else sig["tension"]
            assert all(item in src for item in text.split(", ")), (y, label, text, sig)                                    # 화면의 항목은 응답의 신호에서만 온다
        if not sig["support"] and not sig["tension"]:
            assert p.locator(".hero-signals").is_hidden()                                                                    # 신호가 없으면 만들지 않는다
    ctx.close()


def test_each_original_sentence_appears_once_among_summary_topics_and_full_interpretation(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    box = capture_analysis(p)
    analyze(p)
    settle(p)
    v = box["a"]["verdict"]
    for y in (2027, 2029):
        p.locator(f"#verdict .tl-node[data-year='{y}']").click()
        for dom in ("overall", "wealth", "career"):
            p.locator(f"#verdict .dtab[data-domain={dom}]").click()
            b = next(x for x in v["detail"][str(y)]["blocks"] if x["domain"] == dom)
            body = norm(p.evaluate("document.getElementById('dash-dom-panel').textContent"))
            for pt in b["story_parts"]:
                if pt["kind"] == "counter":
                    continue
                assert body.count(norm(pt["text"])) == 1, (y, dom, pt["kind"], pt["text"][:40])                              # B 와 C 에 같은 문장이 되풀이되지 않는다
    ctx.close()


def test_only_important_topics_are_visible_by_default_and_no_empty_heading_is_made(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    for dom in ("overall", "wealth", "career", "love_marriage", "family"):
        p.locator(f"#verdict .dtab[data-domain={dom}]").click()
        assert p.locator("#dash-dom-panel .dp-fold").count() in (0, 1)
        if p.locator("#dash-dom-panel .dp-fold").count():
            assert p.locator("#dash-dom-panel .dp-fold").evaluate("e=>e.open") is False                                      # 나머지 주제는 접힘
            assert p.locator("#dash-dom-panel .dp-fold > summary .sum-hint").inner_text().strip()                           # 안에 무엇이 있는지 예고
        for h in p.locator("#dash-dom-panel .dp-topics > .dp-topic").all():
            assert h.locator("p, li").count() >= 1                                                                         # 내용 없는 제목은 없다
        vis = p.evaluate("[...document.querySelectorAll('#dash-dom-panel .dp-topics > .dp-topic:not(.dp-think) h4')].map(h=>h.textContent)")
        assert set(vis) <= {"함께 고려할 점", "시기 참고"}
    ctx.close()


def test_folds_open_with_enter_and_space_and_wording_does_not_call_it_a_classical_source(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    p.locator("#verdict .dtab[data-domain=wealth]").click()
    for sel in ("#dash-dom-panel .dp-fold", "#dash-dom-panel .dp-more", ".hero-more", "#dash-evidence"):
        if not p.locator(sel).count():
            continue
        summ = p.locator(f"{sel} > summary").first
        for key in ("Enter", "Space"):
            summ.focus()
            p.keyboard.press(key)
            assert p.locator(sel).first.evaluate("e=>e.open") is True, (sel, key)
            p.keyboard.press(key)
            assert p.locator(sel).first.evaluate("e=>e.open") is False, (sel, key)
    labels = p.evaluate("[...document.querySelectorAll('#dash summary, #dash h3, #dash h4')].map(e=>e.textContent).join(' | ')")
    assert "원문" not in labels                                                                                              # 제목·접힘 머리글에 ‘원문’을 쓰지 않는다(고전 원문으로 오해되므로 ‘전체 해석’)
    assert "전체 해석과 근거 보기" in labels
    ctx.close()
