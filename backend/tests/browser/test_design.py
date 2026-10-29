"""v6.7 디자인 검증: 랜딩/의뢰/리포트/기록 화면 구조, 360·768·1440 반응형, 팔레트, 금지 카피. 모든 입력은 가상 값."""
import re

import pytest

pytestmark = pytest.mark.browser

SIZES = {"360": (360, 800), "768": (768, 1024), "1440": (1440, 900)}
BANNED_COPY = ["AI 분석", "인사이트", "예측 정확도", "성공 확률", "운명을 바꾼다", "적중률"]
PALETTE = {"paper": "rgb(247, 244, 238)", "ink": "rgb(31, 26, 23)"}


def hue_sat(rgb):
    r, g, b = [int(float(x)) / 255 for x in re.findall(r"[\d.]+", rgb)[:3]]
    mx, mn = max(r, g, b), min(r, g, b)
    if mx == mn:
        return 0, 0
    d = mx - mn
    h = ((g - b) / d % 6 if mx == r else ((b - r) / d + 2 if mx == g else (r - g) / d + 4)) * 60
    return h, d / (1 - abs(mx + mn - 1)) if 0 < mx + mn < 2 else 0


@pytest.mark.parametrize("size", list(SIZES))
def test_landing_structure_and_no_overflow(browser, env, size):
    w, h = SIZES[size]
    ctx = browser.new_context(viewport={"width": w, "height": h})
    p = ctx.new_page()
    p.goto(env.web + "/index.html")
    assert "명리 明理" in p.inner_text(".brand")
    assert p.get_attribute("a.btn:not(.ghost)", "href") == "consult.html"  # 분석 시작
    assert p.get_attribute("a.btn.ghost", "href") == "#example"           # 예시 리포트 보기
    assert "합성 예시" in p.inner_text("#example") and "실제 분석 결과가 아닙니다" in p.inner_text("#example")
    assert p.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    assert p.evaluate("getComputedStyle(document.body).backgroundColor") == PALETTE["paper"]
    assert p.evaluate("getComputedStyle(document.body).color") == PALETTE["ink"]
    text = p.inner_text("body")
    assert not [b for b in BANNED_COPY if b in text]
    assert p.evaluate("document.querySelectorAll('input,button,form').length") == 0  # 공개 시안은 입력을 받지 않는다
    ctx.close()


@pytest.mark.parametrize("size", list(SIZES))
def test_consult_form_responsive_and_report_chapters(browser, env, size):
    w, h = SIZES[size]
    ctx = browser.new_context(viewport={"width": w, "height": h})
    p = ctx.new_page()
    p.goto(env.web + "/consult.html")
    p.fill("#api", env.api)
    assert p.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    assert "관심 분야" in p.get_attribute("#doms", "aria-label")
    for label in ("생년월일", "출생 시각", "달력", "출생지", "해설의 깊이"):
        assert p.locator(f"text={label}").count() >= 1, label
    p.fill("#date", "1984-06-15")  # 가상 입력
    p.select_option("#depth", "expert")
    p.click("#f button[type=submit]")
    p.wait_for_selector("#session:not([hidden])", timeout=60000)
    nos = [t.strip() for t in p.eval_on_selector_all(".chapter > .no, #cover .kicker", "els=>els.map(e=>e.textContent)")]
    chap = [n for n in nos if re.match(r"제\d+장", n)]
    order = [int(re.match(r"제(\d+)장", n).group(1)) for n in chap]
    assert order == sorted(order) and order[0] == 1 and order[-1] == 11 and set(order) == set(range(1, 12)), order
    assert p.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    # 챗 버블 형태가 아님: 기록은 문서 블록(record)
    p.fill("#q2", "사업은 어떨까요?")
    p.click("#askb")
    p.wait_for_selector("#out .record")
    assert p.evaluate("getComputedStyle(document.querySelector('#out .record')).borderTopLeftRadius") in ("2px", "0px")
    ctx.close()


def test_depth_modes_are_visually_separated_and_palette_has_no_blue_or_mint(sess):
    sess.open()
    p = sess.page
    sess.fill_birth()
    sess.set_domains(["overall"])
    p.select_option("#depth", "summary")
    sess.start()
    assert p.locator("#out .expert-only").count() == 0 and "요약 모드에서는 학파별 차이를 접어" in p.inner_text("#out")
    p.select_option("#depth", "expert")
    p.click("#f button[type=submit]")
    p.wait_for_function("document.querySelectorAll('#out .expert-only').length>=1")
    assert "전문가용 상세" in p.evaluate("getComputedStyle(document.querySelector('#out .expert-only'),'::before').content")
    bad = p.evaluate("""()=>{const out=[];for(const e of document.querySelectorAll('body *')){const c=getComputedStyle(e);for(const k of ['color','backgroundColor','borderTopColor']){if(c[k]&&c[k]!=='rgba(0, 0, 0, 0)')out.push(c[k])}}return [...new Set(out)]}""")
    offenders = []
    for c in bad:
        h, s = hue_sat(c)
        if s > 0.2 and 150 <= h <= 270:
            offenders.append(c)
    assert offenders == [], offenders  # 민트/블루 계열 없음
    text = p.inner_text("body")
    assert not [b for b in BANNED_COPY if b in text]
    # 상태는 색만으로 구분하지 않는다: 검증 배지에 글자와 기호가 있다
    assert p.locator(".pill.off, .badge.off").first.inner_text().strip() != ""
    assert p.evaluate("getComputedStyle(document.querySelector('.badge.off'),'::before').content") in ('"✕ "', '"✕"') or "검증 전" in p.inner_text("#status")
