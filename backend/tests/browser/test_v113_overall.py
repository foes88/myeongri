"""v11.3 종합운 화면: 핵심 요약(굵지 않게, 최대 2문장) → 실제로 있는 주제만 → 원문·근거 접힘. 주제는 엔진이 문장을 만든 칸에서만 오며 새로 만들지 않는다. 합성 입력만 사용."""
import re

import pytest

from tests.browser.test_dashboard import analyze
from tests.browser.test_motion import settle
from tests.browser.test_oneshot_ui import fill, one, open_page  # noqa: F401
from tests.browser.test_v112_report import capture_analysis, norm

pytestmark = pytest.mark.browser
TITLES = {"natal": "타고난 모습", "period": "이 해에 달라지는 조건", "relation": "관계와 변화", "contrast": "함께 고려할 점", "counter": "다른 견해", "timing": "시기 참고",
          "cross": "다른 분야와의 연결", "emphasis": "무게가 실린 쪽", "where": "나타나는 영역", "where2": "나타나는 영역"}
GODS = ("표현·기술의 기운", "재물·현실 자원의 기운", "직책·규율의 기운", "압박·경쟁의 기운", "배움·보호의 기운")


def test_topics_come_only_from_kinds_the_engine_produced_and_keep_every_sentence(browser, one):
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
            expect = list(dict.fromkeys(TITLES[pt["kind"]] for pt in b["story_parts"]))
            shown = p.evaluate("[...document.querySelectorAll('#dash-dom-panel .dp-topic:not(.dp-think) h4')].map(h=>h.textContent)")
            assert shown == expect, (y, dom, shown, expect)                                                                 # 데이터에 있는 주제만, 같은 순서
            body = norm(p.evaluate("document.getElementById('dash-dom-panel').textContent"))
            assert all(norm(pt["text"]) in body for pt in b["story_parts"])                                                 # 문장은 쪼개거나 바꾸지 않았다
    ctx.close()


def test_summary_is_not_bold_has_no_repeated_sentence_and_the_period_sentence_has_no_repeated_gods(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "360")
    analyze(p)
    settle(p)
    for dom in ("overall", "wealth"):
        p.locator(f"#verdict .dtab[data-domain={dom}]").click()
        assert p.evaluate("+getComputedStyle(document.querySelector('#dash-dom-panel .dp-headline')).fontWeight") <= 500
        vis = p.evaluate("[...document.querySelectorAll('#dash-dom-panel .dp-headline, #dash-dom-panel .dp-topic p, #dash-dom-panel .dp-topic li')].filter(e=>e.checkVisibility()).map(e=>e.textContent)")
        sents = [s.strip() for t in vis for s in re.split(r"(?<=[.!?])\s+", t) if len(s.strip()) > 8]
        assert len(sents) == len(set(sents)), [s for s in sents if sents.count(s) > 1][:2]                                    # 화면에 보이는 문장이 되풀이되지 않는다
        for t in vis:
            if "들여온" in t:
                assert all(t.count(g) <= 1 for g in GODS), t[:100]
    assert not p.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    ctx.close()


def test_older_saved_reports_without_story_parts_still_render_and_keep_the_original(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")

    def strip(route):
        resp = route.fetch()
        body = resp.json()
        for d in (((body.get("answer") or {}).get("verdict") or {}).get("detail") or {}).values():
            for blk in d["blocks"]:
                blk.pop("story_parts", None)
        route.fulfill(response=resp, json=body)

    p.route("**/api/v1/oneshot/analyze", strip)
    box = capture_analysis(p)
    analyze(p)
    settle(p)
    p.locator("#verdict .dtab[data-domain=wealth]").click()
    assert p.locator("#dash-dom-panel .dp-topic").count() >= 1 and "원문과 해석 근거 보기" in p.inner_text("#dash-dom-panel .dp-more summary")
    p.locator("#dash-dom-panel .dp-more > summary").click()
    assert "상세 해석 원문" in p.inner_text("#dash-dom-panel .dp-more")                                                      # 칸 정보가 없어도 원문은 그대로
    ctx.close()


def test_caution_topics_are_marked_by_color_and_by_words_in_the_title(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    titles = p.evaluate("[...document.querySelectorAll('#dash-dom-panel .dp-topic.caution h4')].map(h=>h.textContent)")
    assert titles and all(t in ("관계와 변화", "함께 고려할 점", "다른 견해") for t in titles)                               # 색만이 아니라 제목 글자로도 구분
    ctx.close()
