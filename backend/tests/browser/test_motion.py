"""v10.2 움직임 계층 테스트. 움직임은 읽는 순서를 안내하는 용도이며 내용·판정과 무관하다. 끝나면 흔적(인라인 스타일)이 없어야 하고,
'움직임 줄이기'와 라이브러리 로드 실패에서는 아무 것도 움직이지 않아도 화면이 완전해야 한다. 합성 입력만 사용."""
import hashlib
from pathlib import Path

import pytest

from tests.browser.test_dashboard import analyze
from tests.browser.test_oneshot_ui import fill, one, open_page  # noqa: F401  (fixture 재사용)

pytestmark = pytest.mark.browser
WEB = Path(__file__).resolve().parents[3] / "web"
PINNED_SHA256 = "08423884b313dacbd12fdaff2d002a5b862c8009c17da285a8460efad98d63c3"        # motion@14.9.0 dist/motion.js (npm 배포본)
LEFTOVER = "[...document.querySelectorAll('#dash *')].filter(e=>e.style && (e.style.opacity!=='' || e.style.transform!=='' || e.style.willChange!=='')).length"


def settle(p, timeout=6000):
    p.wait_for_function("document.getAnimations().filter(a=>a.playState==='running' && a.effect && a.effect.getTiming().iterations!==Infinity).length===0", timeout=timeout)


def test_vendored_motion_is_pinned_unmodified_and_licensed():
    f = WEB / "assets" / "vendor" / "motion-14.9.0.js"
    assert hashlib.sha256(f.read_bytes()).hexdigest() == PINNED_SHA256                                              # 변조·교체 방지
    lic = (WEB / "assets" / "vendor" / "motion-LICENSE.md").read_text(encoding="utf-8")
    assert "MIT License" in lic and "Motion" in lic                                                                  # 라이선스 표기 동봉
    src = f.read_text(encoding="utf-8")
    assert "eval(" not in src and "new Function" not in src                                                          # CSP(unsafe-eval 없음)와 충돌하지 않는다
    assert "assets/vendor/motion-14.9.0.js" in (WEB / "consult.html").read_text(encoding="utf-8")


def test_motion_loads_from_same_origin_only_and_runs_without_errors(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    assert p.evaluate("typeof Motion === 'object' && typeof Motion.animate === 'function'") and p.evaluate("MingliMotion.enabled()") is True
    analyze(p)
    assert [u for m, u, pd in reqs if "motion" in u and u.endswith(".js")] and all(u.startswith(one["base"]) or u.startswith("data:") for m, u, pd in reqs)   # 외부 요청 없음
    assert not [c for c in console if "PAGEERROR" in c or "Content Security" in c or "Refused" in c]
    ctx.close()


def test_results_animate_in_reading_order_and_leave_no_inline_residue(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    fill(p)
    p.fill("#y1", "2027")
    p.select_option("#pk", "r5")
    p.click("#f button[type=submit]")
    p.wait_for_selector("#verdict .dash-conclusion", timeout=60000)
    # 시작 직후에는 움직임이 실제로 돌고 있고, 결론 영역이 가장 먼저 시작한다
    p.wait_for_function("document.getAnimations().length>0", timeout=3000)
    first = p.evaluate("(()=>{const c=document.querySelector('.dash-conclusion'),f=document.querySelector('.dash-flow .tl-node');return [+getComputedStyle(c).opacity,+getComputedStyle(f).opacity]})()")
    assert first[0] >= first[1]                                                                                      # 결론이 시기 노드보다 먼저(또는 같이) 나타난다
    settle(p)
    p.wait_for_timeout(150)
    assert p.evaluate(LEFTOVER) == 0                                                                                 # 끝나면 인라인 opacity/transform 이 남지 않는다
    # 오행 막대는 글자 수에 비례하는 최종 높이로 끝난다(가장 큰 값이 100%)
    heights = p.evaluate("[...document.querySelectorAll('.me-elements .efill')].map(e=>e.style.height)")
    assert len(heights) == 5 and "100%" in heights and all(h.endswith("%") for h in heights)
    counts = p.evaluate("[...document.querySelectorAll('.me-elements .enum')].map(e=>+e.textContent)")
    mx = max(counts)
    assert [round(float(h[:-1])) for h in heights] == [round(max(c / mx * 100, 12 if c else 0)) for c in counts]      # 값과 막대 높이가 일치(움직임이 값을 바꾸지 않음)
    # 구간 막대의 비율(엔진 일수 비율)도 그대로
    grows = p.evaluate("[...document.querySelectorAll(\"#verdict .tl-node[data-year='2027'] .segpart\")].map(e=>+e.style.flexGrow)")
    assert abs(grows[0] - 0.093) < 0.01 and abs(grows[1] - 0.907) < 0.01
    ctx.close()


def test_selection_changes_content_immediately_and_only_the_changed_panel_transitions(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    p.locator("#verdict .tl-node[data-year='2029']").click()
    assert p.inner_text("#h-concl") == "2029년의 흐름"                                                          # 텍스트는 즉시 바뀐다(애니메이션을 기다리지 않는다)
    p.wait_for_function("document.querySelector('.concl-text').getAnimations().length>0 || document.querySelector('.concl-text').style.opacity!==''", timeout=1500)
    settle(p)
    p.wait_for_timeout(100)
    assert p.evaluate(LEFTOVER) == 0
    # 같은 연도에서 분야만 바꾸면 해 패널은 전환하지 않는다
    p.evaluate("window.__yp = document.querySelector('.concl-text')")
    p.locator("#verdict .dtab[data-domain=wealth]").click()
    assert p.evaluate("window.__yp.getAnimations().length===0 && window.__yp.style.opacity===''")
    assert p.inner_text("#dash-dom-panel .dp-head h3") == "재물운"
    ctx.close()


def test_reduced_motion_preference_disables_every_animation(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440", reduced="reduce")
    assert p.evaluate("MingliMotion.enabled()") is False
    fill(p)
    p.fill("#y1", "2027")
    p.select_option("#pk", "r5")
    p.click("#f button[type=submit]")
    p.wait_for_selector("#verdict .dash-conclusion", timeout=60000)
    # 처음부터 최종 상태: 움직임 없음, 인라인 흔적 없음, 막대는 바로 최종 높이
    assert p.evaluate("document.getAnimations().filter(a=>a.effect && a.effect.getTiming().iterations!==Infinity).length") == 0
    assert p.evaluate(LEFTOVER) == 0
    assert p.evaluate("[...document.querySelectorAll('.me-elements .efill')].some(e=>e.style.height==='100%')")
    p.locator("#verdict .tl-node").nth(2).click()
    assert p.evaluate("document.getAnimations().filter(a=>a.effect && a.effect.getTiming().iterations!==Infinity).length") == 0
    assert p.inner_text("#h-concl") == "2029년의 흐름"
    # CSS 전환·누름 피드백도 꺼진다
    assert p.evaluate("getComputedStyle(document.querySelector('.tl-node')).transitionDuration") in ("0s", "0s, 0s", "0s, 0s, 0s, 0s")
    ctx.close()


def test_page_is_complete_when_the_motion_library_fails_to_load(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440", block="**/vendor/motion-*.js")
    assert p.evaluate("typeof Motion") == "undefined" and p.evaluate("MingliMotion.enabled()") is False
    analyze(p)
    assert p.locator("#verdict .tl-node").count() == 5 and p.locator("#verdict .dtab").count() == 5
    assert p.evaluate(LEFTOVER) == 0 and p.inner_text("#h-concl") == "2027년의 흐름"
    assert not [c for c in console if "PAGEERROR" in c]                                                              # 로드 실패가 오류로 번지지 않는다
    ctx.close()


def test_new_follow_up_record_fades_in_and_settles(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    p.fill("#q2", "이 시기에 고려할 점은?")
    p.click("#askb")
    p.wait_for_selector("#out .record")
    settle(p)
    p.wait_for_timeout(100)
    assert p.evaluate("(()=>{const r=document.querySelector('#out .record');return r.style.opacity==='' && r.style.transform===''})()")
    ctx.close()


def test_control_bar_gets_a_shadow_only_after_content_scrolls_under_it(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    p.evaluate("window.scrollTo(0, 0)")
    top_bar = p.evaluate("document.querySelector('.dash-bar').getBoundingClientRect().top")
    p.evaluate("window.scrollBy(0, 900)")
    p.wait_for_function("document.querySelector('.dash-bar').classList.contains('stuck')", timeout=2000)
    p.evaluate("window.scrollTo(0, 0)")
    p.wait_for_function("!document.querySelector('.dash-bar').classList.contains('stuck')", timeout=2000)
    assert top_bar > 0
    ctx.close()


def test_input_screen_intro_ends_clean(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    p.wait_for_timeout(200)
    settle(p)
    p.wait_for_timeout(100)
    assert p.evaluate("[...document.querySelectorAll('main > h1, main > p.lead, main > ol.steps, #f > fieldset')].every(e=>e.style.opacity==='' && e.style.transform==='')")
    assert p.is_visible("#date") and p.is_visible("#f button[type=submit]")                                           # 입력 구역은 항상 사용할 수 있다
    ctx.close()


def test_identity_effects_slide_and_hero_transition_end_clean(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    assert p.locator("#verdict .dash-conclusion .stamp").count() == 0 and p.locator(".brush").count() == 0           # v11.2: 장식(인장·붓 밑줄)은 걷어 냈다
    settle(p)
    p.wait_for_timeout(150)
    assert p.evaluate(LEFTOVER) == 0 and p.evaluate("document.querySelectorAll('.tl-ghost').length") == 0
    p.locator("#verdict .tl-node[data-year='2029']").click()
    p.wait_for_function("document.querySelectorAll('.tl-ghost').length===1", timeout=1500)                           # 선택 표시가 이동 중
    assert p.inner_text("#h-concl") == "2029년의 흐름"                                                              # 텍스트는 기다리지 않고 바뀐다
    settle(p)
    p.wait_for_timeout(150)
    assert p.evaluate("document.querySelectorAll('.tl-ghost').length") == 0
    assert p.evaluate(LEFTOVER) == 0
    assert not p.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    ctx.close()


def test_identity_effects_are_off_with_reduced_motion(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440", reduced="reduce")
    analyze(p)
    p.locator("#verdict .tl-node[data-year='2029']").click()
    assert p.evaluate("document.querySelectorAll('.tl-ghost').length") == 0
    assert p.evaluate("document.querySelector('#dash-year-panel').style.clipPath") == "" and p.evaluate(LEFTOVER) == 0
    ctx.close()


def test_final_polish_equal_circles_single_highlight_and_visible_selected_state(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    p.wait_for_timeout(200)
    p.click("#dash-evidence > summary")                                                                                  # v11.2: 해석의 근거(접힘)를 열고
    p.click(".wheel-fold summary")                                                                                      # 순환도(접힌 보조 설명)를 펼쳐서 확인
    p.wait_for_timeout(300)
    radii = p.evaluate("[...document.querySelectorAll('.wheel .wc')].map(c=>c.getAttribute('r'))")
    assert len(radii) == 5 and len(set(radii)) == 1                                                                   # 원 크기는 모두 같다(강약 표현 아님)
    assert "크기는 모두 같" in p.inner_text(".wheel-note")
    assert p.locator(".dash-conclusion .hl").count() <= 1                                                            # 형광펜은 결론에서 한 구절만
    labels = p.evaluate("[...document.querySelectorAll('.wheel .wname')].map(t=>t.getBoundingClientRect()).map(r=>[r.left,r.top,r.right,r.bottom])")
    circles = p.evaluate("[...document.querySelectorAll('.wheel .wc')].map(c=>c.getBoundingClientRect()).map(r=>[r.left,r.top,r.right,r.bottom])")
    for l in labels:
        for c in circles:
            assert l[2] < c[0] or l[0] > c[2] or l[3] < c[1] or l[1] > c[3]                                          # 라벨이 원과 겹치지 않는다
    # 호버 없이도 선택 상태가 글자로 구분된다
    p.mouse.move(0, 0)
    assert "선택" in p.evaluate("getComputedStyle(document.querySelector('.tl-node[aria-pressed=true] .tl-year'),'::after').content")
    ctx.close()


def test_changes_section_shows_existing_changes_and_the_domain_judgement_summary(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    n = p.locator(".dash-changes .chg-item").count()
    assert 1 <= n <= 3                                                                                               # 주요 변화는 2~3개 이내(데이터가 없으면 더 적음)
    assert p.inner_text("#h-chg") == "2027년의 주요 변화"
    tones = p.inner_text(".chg-tones")
    assert "분야별 판정 요약" in tones and "종합운" in tones and any(w in tones for w in ("기회", "주의", "양면", "안정", "근거 부족", "변화 없음"))   # 기존 판정을 기호+글자로 요약
    p.locator("#verdict .dtab[data-domain=career]").click()
    assert p.inner_text("#dash-dom-panel .dp-head h3") == "직업·승진운"
    assert p.locator("#verdict .dtab[aria-selected=true]").count() == 1
    ctx.close()


def test_hero_leads_with_the_year_and_the_detail_fold_has_the_full_year_reading(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    assert p.inner_text("#h-concl") == "2027년의 흐름" and p.locator(".concl-text").inner_text().startswith("2027년")  # 첫 화면의 답: 이 해는 어떤 해인가
    assert p.locator(".hero-more").evaluate("e=>e.open") is False and "자세한 해석 보기" in p.inner_text(".hero-more summary")
    p.click(".hero-more summary")
    heads = p.evaluate("[...document.querySelectorAll('#dash-year-panel h4')].map(h=>h.textContent)")
    assert "자세한 풀이" in heads
    txt = p.inner_text("#dash-year-panel")
    assert "반대로 보는 근거와 한계" in txt and "보장하지 않습니다" in txt
    ctx.close()


def test_monthly_flow_toggle_select_navigate_and_withheld_notice(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    assert p.is_visible("#dash-months-toggle") and not p.is_visible("#dash-months-body")                            # 기본은 접힘
    p.click("#dash-months-toggle")
    p.wait_for_selector("#dash-months-body .mcell")
    n = p.locator("#dash-months-body .mcell").count()
    assert 12 <= n <= 14                                                                                             # 12개월(+이어지는 구간·큰 흐름 교체 분할)
    assert p.locator("#dash-months-body .mcell[aria-pressed=true]").count() == 1
    assert "선택됨" in p.inner_text("#dash-months-body .mcell[aria-pressed=true]")                                  # 선택 상태는 글자로도 구분
    d = p.inner_text("#dash-month-detail")
    assert "적용 기간" in d and "절입" in d and "이 달의 기운" in d and "타고난 사주와의 관계" in d
    assert "좋고 나쁨을 가르는 판정은 하지 않습니다" in d                                                          # 월별 방향 판정 유보 명시
    assert not any(sym in d for sym in "▲▽◆") and "▲" not in p.inner_text("#dash-months-body")                         # 월별에는 기회·주의 판정 기호가 없다
    first = p.inner_text("#dash-month-detail .mhead h4")
    p.click("#dash-month-detail .mnav .navbtn >> text=다음 달")
    assert p.inner_text("#dash-month-detail .mhead h4") != first
    p.locator("#dash-months-body .mcell").nth(1).click()
    assert p.locator("#dash-months-body .mcell[aria-pressed=true]").count() == 1
    ip = p.locator("#dash-months-body .mcell", has_text="입춘")
    ip.first.click()
    assert "입춘부터 그해의 기운이 적용됩니다" in p.inner_text("#dash-month-detail")
    assert not p.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    ctx.close()


def test_monthly_flow_follows_year_selection_and_domain(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "360")
    analyze(p)
    settle(p)
    p.click("#dash-months-toggle")
    p.wait_for_selector("#dash-months-body .mcell")
    assert not p.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    y1 = p.inner_text("#dash-months-body .mcell >> nth=0")
    p.locator("#verdict .tl-node[data-year='2029']").click()
    p.wait_for_function("document.querySelector('#h-months') && document.querySelector('#dash-months-body .mcell')")
    assert p.get_attribute("#dash-months-body .mgrid", "aria-label").startswith("2029")                              # 선택한 해의 월
    p.locator("#verdict .dtab[data-domain=wealth]").click()
    assert "재물운" in p.inner_text("#dash-month-detail") or "달라지는" in p.inner_text("#dash-month-detail")
    ctx.close()
