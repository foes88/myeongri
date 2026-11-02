"""v9.0 Personal Alpha 실사용 E2E(실제 브라우저, 가상 입력). 새 명식 → 기본 풀이 → 계산 상태 → 연도 이동(재입력 없음) → 5년 → 후속 3회(맥락) →
내 평가 → 새로고침·재로그인·이전 상담 열기 → 열린 상태에서 연도 이동 → 내보내기 → 삭제. 360px·1440px."""
import re

import pytest

from tests.browser.test_oneshot_ui import _login_ui, fill, one, open_page  # noqa: F401  (fixture 재사용)

pytestmark = pytest.mark.browser


def _ask(p, q):
    before = p.locator("#out .record").count()
    p.fill("#q2", q)
    p.click("#askb")
    p.wait_for_function(f"document.querySelectorAll('#out .record').length>{before}", timeout=60000)
    return p.locator("#out .record").last.inner_text()


@pytest.mark.parametrize("size", ["360", "1440"])
def test_personal_end_to_end(browser, one, size):
    ctx, p, reqs, console = open_page(browser, one, size)
    email = f"me-{size}@example.com"
    _login_ui(p, email, register=True)
    fill(p)
    p.fill("#q", "2028년 재물과 직업이 궁금합니다")
    p.click("#f button[type=submit]")
    p.wait_for_selector("#session:not([hidden])", timeout=60000)
    # STEP2 기본 풀이 + 계산 상태(쉬운 말, 내부 등급 비노출)
    body = p.inner_text("#report")
    calc = p.locator("#status [data-calc]")
    assert calc.count() == 1 and "계산 상태" in calc.inner_text()
    assert not any(w in body for w in ("PILLARS_VERIFIED", "ASTRO_VERIFIED", "lunar-python", "golden"))
    assert p.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    # v9.3: 명식 전체 종합(핵심 결론 → 현실 참고, 근거·조건은 접힘)
    pf = p.locator("#verdict .vprofile")
    assert pf.count() == 1 and "이 사주에서 중요하게 읽히는 것" in pf.inner_text()
    assert pf.locator("details[open]").count() == 0 and pf.locator("details").count() == 2
    assert not any(w in pf.inner_text() for w in ("격국", "용신", "식상생재", "claim", "대운", "세운"))
    # STEP3 연도 이동: 폼을 건드리지 않고 저장된 명식으로 다시 풀이
    posts_before = len([1 for m, u, pd in reqs if m == "POST" and u.endswith("/api/v1/reports")])
    p.click("#ynext")
    p.wait_for_function("document.getElementById('cover').innerText.includes('저장된 명식으로')", timeout=60000)
    assert "2029" in p.inner_text("#cover")
    p.click("#to5")
    p.wait_for_function("document.getElementById('cover').innerText.includes('2029~2033')", timeout=60000)
    assert len([1 for m, u, pd in reqs if m == "POST" and u.endswith("/api/v1/reports")]) == posts_before   # 새 리포트를 만들지 않는다
    assert any(u.endswith("/analyze") for m, u, pd in reqs if m == "POST")
    assert all("1984-06-15" not in (pd or "") for m, u, pd in reqs if u.endswith("/analyze"))                # 출생 정보 재전송 없음
    # STEP4 후속 질문 3회(맥락 유지)
    t1 = _ask(p, "2030년 재물운 자세히 알려줘")
    t2 = _ask(p, "앞에서 말한 결론은 왜 그렇게 판단했어?")
    assert "재물" in t2 and "이유" in t2 or "판단" in t2
    t3 = _ask(p, "2030년 이직 고려할 점은?")
    assert "보장하지 않" in t3 and "2030" in t3
    assert not any(w in (t1 + t2 + t3) for w in ("반드시", "틀림없", "claim_id", "rule_id"))
    # 내 평가
    p.click("#fbk button[aria-label='4점']")
    p.wait_for_function("document.getElementById('fbm').textContent.includes('저장')")
    # STEP5 새로고침 → 재로그인 → 이전 상담 열기
    p.reload()
    p.wait_for_selector("#acct-in:not([hidden])")
    p.click("#mylist li button:has-text('열기')")
    p.wait_for_function("document.getElementById('cover').innerText.includes('다시 열었습니다')", timeout=30000)
    assert p.locator("#out .record").count() >= 3 and "이직" in p.inner_text("#out")
    # 열린 저장본에서도 입력 폼 없이 연도 이동이 된다(입력란은 비어 있음)
    assert p.input_value("#date") == ""
    p.click("#ynext")
    p.wait_for_function("document.getElementById('cover').innerText.includes('저장된 명식으로')", timeout=60000)
    # 내보내기에 출생 정보 없음 → 삭제
    with p.expect_download() as dl:
        p.click("#mylist li button:has-text('내보내기')")
    txt = open(dl.value.path(), encoding="utf-8").read()
    assert "1984-06-15" not in txt and "10:00" not in txt and "다시 풀이" in txt  # 가상 입력
    p.click("#mylist li button:has-text('삭제')")
    p.wait_for_function("document.getElementById('acct-n').textContent==='0'")
    assert p.is_hidden("#report") and p.inner_text("#out") == ""   # 열려 있던 리포트를 지우면 화면에서도 사라진다
    assert not [c for c in console if "PAGEERROR" in c or "Content Security" in c]
    ctx.close()


@pytest.mark.parametrize("size", ["360", "1440"])
def test_v10_screen_answers_the_six_questions_without_expanding_anything(browser, one, size):
    """v10.0: 접힌 것을 펼치지 않아도 (1)중요하게 읽히는 것 (2)달라지는 조건 (3)직업·재물 의미 (4)주목할 해 (5)이유로 가는 길 (6)근거 부족한 부분이 화면에 있다."""
    ctx, p, reqs, console = open_page(browser, one, size)
    _login_ui(p, f"v10-{size}@example.com", register=True)
    fill(p)
    p.fill("#y1", "2027")
    p.select_option("#pk", "r5")
    for cb in p.query_selector_all("#doms input"):
        want = cb.get_attribute("value") in ("overall", "wealth", "career", "job_change", "family")
        if cb.is_checked() != want:
            cb.set_checked(want)
    p.click("#f button[type=submit]")
    p.wait_for_selector("#verdict .vprofile", timeout=60000)
    vis = p.inner_text("#verdict")
    pf = p.locator("#verdict .vprofile")
    assert "이 사주에서 중요하게 읽히는 것" in pf.inner_text()                                   # (1)
    assert "선택한 시기에 달라지는 조건" in pf.inner_text()                                      # (2) 접힌 상자 밖에 있다
    assert pf.locator("details[open]").count() == 0 and pf.locator("details summary", has_text="왜 그렇게 읽나요?").count() == 1   # (5)
    assert pf.locator("details summary", has_text="판단이 달라질 수 있는 조건").count() == 1       # (6) 조건·유보 설명으로 가는 길
    assert p.locator("#verdict .vperiod").count() == 1 and "2027" in p.locator("#verdict .vperiod").inner_text()     # (4) 시기별 요약·두드러지는 해
    # (3) 분야별 풀이는 연도 상세 안에 있으므로 첫 해를 펼치면 직업·재물이 따로 보인다
    p.get_by_role("button", name="2027년 자세히 보기").click()
    names = p.eval_on_selector_all("#verdict .vblock h2", "els=>els.map(e=>e.textContent)")
    assert "재물운" in names and "직업·승진운" in names
    assert not any(w in vis for w in ("claim_id", "ruleset", "격국", "용신", "식상생재", "judge-"))
    assert p.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    assert not [c for c in console if "PAGEERROR" in c or "Content Security" in c]
    ctx.close()


@pytest.mark.parametrize("size", ["360", "1440"])
def test_v10_visuals_heatmap_and_element_bars(browser, one, size):
    """도식: 분야×연도 한눈표(색+기호+글자)와 기운 분포 막대. 가로 넘침 없음, 색에만 의존하지 않음, 확률이 아님을 밝힘."""
    ctx, p, reqs, console = open_page(browser, one, size)
    _login_ui(p, f"vis-{size}@example.com", register=True)
    fill(p)
    p.fill("#y1", "2027")
    p.select_option("#pk", "r5")
    for cb in p.query_selector_all("#doms input"):
        want = cb.get_attribute("value") in ("overall", "wealth", "career", "family")
        if cb.is_checked() != want:
            cb.set_checked(want)
    p.click("#f button[type=submit]")
    p.wait_for_selector("#verdict .heat", timeout=60000)
    rows = p.locator("#verdict .heat tbody tr").count()
    cols = p.locator("#verdict .heat thead th").count() - 1
    assert rows == 4 and cols == 5 and p.locator("#verdict .heat tbody td").count() == 20
    cells = p.locator("#verdict .heat tbody td")
    for i in range(cells.count()):
        c = cells.nth(i)
        assert c.locator(".sym").inner_text().strip() and c.locator(".lab").inner_text().strip() and c.get_attribute("aria-label")      # 색 이외의 기호·글자
    assert "확률도 아닙니다" in p.inner_text("#verdict .heatwrap") and p.locator("#verdict .heatlegend span").count() == 6
    bars = p.locator("#verdict .vstorycard .elrow")
    assert bars.count() == 5 and "개를 다섯 가지 기운으로 센 것" in p.inner_text("#verdict .vstorycard .elwrap")
    total = sum(int(bars.nth(i).locator(".elnum").inner_text().replace("개", "")) for i in range(5))
    assert total == 8                                                      # 네 기둥 여덟 글자
    assert p.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    p.screenshot(path=f"data_private/browser/visual_{size}.png", full_page=False)
    assert not [c for c in console if "PAGEERROR" in c or "Content Security" in c]
    ctx.close()


@pytest.mark.parametrize("size", ["360", "1440"])
def test_first_screen_is_a_story_not_a_structure_label(browser, one, size):
    """첫 장면: 자연물 비유 제목 + 흐름순 문장 + 필요한 기운이 들어오는 때. 비유임을 밝히고, 성격·사건을 단정하지 않는다."""
    ctx, p, reqs, console = open_page(browser, one, size)
    _login_ui(p, f"story-{size}@example.com", register=True)
    fill(p)
    p.fill("#y1", "2027")
    p.select_option("#pk", "r5")
    p.click("#f button[type=submit]")
    p.wait_for_selector("#verdict .vstorycard", timeout=60000)
    card = p.locator("#verdict .vstorycard")
    assert p.locator("#verdict > section").first.get_attribute("data-story") == "1"            # 가장 먼저 보이는 것이 이야기 카드
    title = card.locator(".storytitle").inner_text()
    assert re.search(r"(봄|여름|가을|겨울)에 선 ", title) and "이 사주를 자연에 빗대면" in card.inner_text()
    assert card.locator("ol.beats li").count() >= 2 and card.locator(".elrow").count() == 5
    assert "비유" in card.inner_text() or "빗대" in card.inner_text()
    assert "성격이나 일어날 일을 말하는 것이 아니며" in card.inner_text()
    txt = card.inner_text()
    assert not re.search(r"[一-鿿]|격국|용신|claim|반드시|틀림없|운명", txt)
    if card.locator(".needcell").count():
        assert card.locator(".needcell").count() == 5 and all(card.locator(".needcell").nth(i).get_attribute("aria-label") for i in range(5))
    box = card.bounding_box()
    assert box["y"] < 700 and p.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    p.screenshot(path=f"data_private/browser/story_{size}.png")
    ctx.close()
