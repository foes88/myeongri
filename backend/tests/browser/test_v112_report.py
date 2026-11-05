"""v11.2 결과 화면 재구성 회귀: 기존 해석 원문 보존(요약만 먼저, 원문은 펼치기), 판정 결과 불변, 읽기 순서, 키보드·접근성, 모바일. 합성 입력만 사용."""
import json

import pytest

from tests.browser.test_dashboard import analyze
from tests.browser.test_motion import settle
from tests.browser.test_oneshot_ui import fill, one, open_page  # noqa: F401

pytestmark = pytest.mark.browser
DOMS = ("overall", "wealth", "career", "love_marriage", "family")


def norm(t):
    return "".join(str(t).split())


def capture_analysis(p):
    box = {}

    def on_response(r):
        if r.url.endswith("/api/v1/oneshot/analyze") and r.request.method == "POST":
            try:
                box["a"] = r.json()["answer"]
            except Exception:
                pass
    p.on("response", on_response)
    return box


def test_every_original_sentence_of_the_selected_year_and_domain_is_still_on_the_page(browser, one):
    """요약을 먼저 보이고 원문은 펼치기로 옮겼을 뿐, 어떤 원문 문장도 사라지지 않는다(접힌 안에 있어도 화면에 존재해야 함)."""
    ctx, p, reqs, console = open_page(browser, one, "1440")
    box = capture_analysis(p)
    analyze(p)
    settle(p)
    v = box["a"]["verdict"]
    for y in (2027, 2029):
        p.locator(f"#verdict .tl-node[data-year='{y}']").click()
        for dom in DOMS:
            p.locator(f"#verdict .dtab[data-domain={dom}]").click()
            page_text = norm(p.evaluate("document.getElementById('dash').textContent"))
            blocks = {b["domain"]: b for b in v["detail"][str(y)]["blocks"]}
            for d in ("overall", dom):
                b = blocks[d]
                texts = [b["headline"]]                                                                                    # 다른 분야를 보는 중에도 그 해의 종합 한 줄(핵심 해석)은 첫 화면에 있다
                if d == dom:                                                                                               # 선택한 분야의 원문은 모두 화면에 있다(접힘 포함). 다른 분야의 본문은 그 분야 탭에 있다
                    texts += list(b["story"]) + [c for c in list(b.get("counter") or [])[:2] if c] + [t for t in b["think"]]
                missing = [t for t in texts if norm(t) not in page_text and norm(t)[:18] not in page_text]
                assert missing == [], (y, dom, d, missing[:2])
            # 분야 근거(왜 그렇게 해석하나요)의 원문도 접힌 안에 그대로 있다
            why = blocks[dom].get("why") or {}
            for t in (why.get("natal") or []) + (why.get("period") or []) + (why.get("against") or []):
                assert norm(t)[:18] in page_text, (y, dom, t[:30])
    ctx.close()


def test_judgement_labels_shown_match_the_api_tones_for_every_year_and_domain(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    box = capture_analysis(p)
    analyze(p)
    settle(p)
    v = box["a"]["verdict"]
    labels = {"opportunity": "기회", "cautious": "주의", "mixed": "양면", "thin": "근거 부족", "quiet": "변화 없음", "steady": "안정"}
    for y in (2027, 2028, 2030):
        for b in v["detail"][str(y)]["blocks"]:
            cell = p.locator(f"#verdict .dgrid .cell[data-year='{y}'][data-domain='{b['domain']}'] .lab").inner_text()
            assert cell == labels[b["tone"]], (y, b["domain"], b["tone"], cell)                                        # 화면의 판정 = 기존 판정
    ctx.close()


@pytest.mark.parametrize("size", ["360", "768", "1440"])
def test_the_first_screen_answers_what_kind_of_year_this_is(browser, one, size):
    ctx, p, reqs, console = open_page(browser, one, size)
    analyze(p)
    settle(p)
    vh = p.evaluate("innerHeight")
    box = p.evaluate("(()=>{const r=document.querySelector('.concl-text').getBoundingClientRect();return [r.top,r.bottom]})()")
    assert 0 <= box[0] and box[1] <= vh                                                                                  # 핵심 해석이 첫 화면 안에 온전히 보인다
    big = p.evaluate("[...document.querySelectorAll('#dash h1,#dash h2,#dash h3,#dash p')].filter(e=>e.offsetParent!==null).map(e=>[parseFloat(getComputedStyle(e).fontSize),e.className]).sort((a,b)=>b[0]-a[0])[0][1]")
    assert "concl-text" in big                                                                                           # 화면에서 가장 큰 글자는 핵심 해석
    assert p.locator(".hero-sub").inner_text().count("。") == 0 and len(p.locator(".hero-sub").inner_text()) < 200      # 보조 설명은 짧게(상세는 펼치기)
    order = p.evaluate("['.dash-bar','.dash-conclusion','.dash-changes','.dash-domains','.dash-flow','#dash-evidence'].map(s=>document.querySelector(s).getBoundingClientRect().top+scrollY)")
    assert order == sorted(order)                                                                                        # 핵심 해석 → 주요 변화 → 분야별 해석 → 시기별 흐름 → 해석의 근거
    ctx.close()


def test_folds_open_with_the_keyboard_and_expose_their_state(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    for sel in (".hero-more", "#dash-evidence", ".dp-more"):
        summ = p.locator(f"{sel} > summary").first
        assert p.locator(sel).first.evaluate("e=>e.open") is False
        summ.focus()
        p.keyboard.press("Enter")
        assert p.locator(sel).first.evaluate("e=>e.open") is True, sel                                                   # 키보드(Enter)로 펼쳐진다
        p.keyboard.press("Enter")
        assert p.locator(sel).first.evaluate("e=>e.open") is False
    marks = p.evaluate("""()=>[...document.querySelectorAll('.hero-more>summary,#dash-evidence>summary')].map(s=>getComputedStyle(s,'::before').content)""")
    assert all("▸" in m for m in marks)                                                                                  # 접힘 표시(▸) 가 보인다
    ctx.close()


def test_save_area_states_that_login_is_required_and_follow_up_explains_its_context(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    assert "저장하려면 로그인이 필요합니다" in p.inner_text("#acct")
    assert "지금 보고 있는 연도·월·분야 기준으로 답하며" in p.inner_text("#session")
    assert "질문에 적은 연도·월이 우선합니다" in p.inner_text("#session")
    ctx.close()
