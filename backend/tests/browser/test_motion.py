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
    assert p.inner_text("#dash-year-panel h3") == "2029년"                                                          # 텍스트는 즉시 바뀐다(애니메이션을 기다리지 않는다)
    p.wait_for_function("document.querySelector('#dash-year-panel').getAnimations().length>0 || document.querySelector('#dash-year-panel').style.opacity!==''", timeout=1500)
    settle(p)
    p.wait_for_timeout(100)
    assert p.evaluate(LEFTOVER) == 0
    # 같은 연도에서 분야만 바꾸면 해 패널은 전환하지 않는다
    p.evaluate("window.__yp = document.querySelector('#dash-year-panel')")
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
    assert p.inner_text("#dash-year-panel h3") == "2029년"
    # CSS 전환·누름 피드백도 꺼진다
    assert p.evaluate("getComputedStyle(document.querySelector('.tl-node')).transitionDuration") in ("0s", "0s, 0s", "0s, 0s, 0s, 0s")
    ctx.close()


def test_page_is_complete_when_the_motion_library_fails_to_load(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440", block="**/vendor/motion-*.js")
    assert p.evaluate("typeof Motion") == "undefined" and p.evaluate("MingliMotion.enabled()") is False
    analyze(p)
    assert p.locator("#verdict .tl-node").count() == 5 and p.locator("#verdict .dtab").count() == 5
    assert p.evaluate(LEFTOVER) == 0 and p.inner_text("#dash-year-panel h3") == "2027년"
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
