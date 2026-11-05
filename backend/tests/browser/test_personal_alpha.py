"""v9.0 Personal Alpha 실사용 E2E(실제 브라우저, 가상 입력). 새 명식 → 기본 풀이 → 계산 상태 → 연도 이동(재입력 없음) → 5년 → 후속 3회(맥락) →
내 평가 → 새로고침·재로그인·이전 상담 열기 → 열린 상태에서 연도 이동 → 내보내기 → 삭제. 360px·1440px."""
import json
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
    p.fill("#y1", "2028")
    p.fill("#q", "2028년 재물과 직업이 궁금합니다")
    p.click("#f button[type=submit]")
    p.wait_for_selector("#session:not([hidden])", timeout=60000)
    # STEP2 기본 풀이 + 계산 상태(쉬운 말, 내부 등급 비노출)
    body = p.inner_text("#report")
    calc = p.locator("#status [data-calc]")
    assert calc.count() == 1 and "계산 상태" in calc.inner_text()
    assert not any(w in body for w in ("PILLARS_VERIFIED", "ASTRO_VERIFIED", "lunar-python", "golden"))
    assert p.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    # v10.1: 핵심 결론(특징·변화·관점 3칸, 근거·조건은 접힘)
    hero = p.locator("#verdict .dash-conclusion")
    assert hero.count() == 1 and hero.locator(".concl-text").inner_text().startswith(str(p.evaluate("window.MingliSel.year")))   # v11.2: 첫 화면은 그 해의 핵심 해석
    p.click("#dash-evidence > summary")                                                                               # 사주 구조 요약(특징·변화·관점)은 해석의 근거 안에 있다
    pf = p.locator("#dash-evidence .ev-natal")
    assert pf.count() == 1 and "이 사주의 가장 뚜렷한 특징" in pf.inner_text() and pf.locator(".trio-item").count() == 3
    assert hero.locator("details[open]").count() == 0
    assert not any(w in pf.inner_text() + hero.inner_text() for w in ("격국", "용신", "식상생재", "claim", "대운", "세운"))
    # STEP3 연도 이동: 폼을 건드리지 않고 저장된 명식으로 다시 풀이
    posts_before = len([1 for m, u, pd in reqs if m == "POST" and u.endswith("/api/v1/reports")])
    p.click("#dash-next")
    p.wait_for_function("document.getElementById('cover').innerText.includes('저장된 명식으로')", timeout=60000)
    assert "2029" in p.inner_text("#cover") and "2029" in p.inner_text("#dash-span")
    p.click("#dash-to5")
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
    p.click("#dash-next")
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


def test_year_defaults_to_next_year_and_personal_defaults_prefill_only_when_provided(browser, one):
    """분석 연도는 항상 내년이 기본. 개인용 기본 입력값(서버가 로컬 설정에서 줄 때만)은 폼을 채우되 이미 입력한 값은 덮어쓰지 않는다. 설정이 없으면 빈 폼."""
    import datetime
    ny = datetime.date.today().year + 1
    # 설정이 없는 서버(공개 배포와 같은 상태): 출생 정보는 비어 있고 연도만 내년
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    p = ctx.new_page()
    p.goto(one["base"] + "/consult.html")
    p.wait_for_load_state("networkidle")
    assert p.input_value("#date") == "" and p.input_value("#y1") == str(ny) and p.input_value("#y2") == str(ny + 1)
    assert str(ny) in p.inner_text("#pdesc")
    ctx.close()
    # 로컬 기본값이 있을 때(가상 값): 생년월일·시각·성별·출생지가 채워진다
    vals = {"calendar": "solar", "birth_date": f"{1990:04d}-{2:02d}-{3:02d}", "birth_time": f"{4:02d}:{5:02d}", "gender": "female", "birth_place": "경기도 수원시"}
    ctx = browser.new_context(viewport={"width": 360, "height": 800})
    p = ctx.new_page()
    p.route("**/api/v1/local-defaults", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(vals, ensure_ascii=False)))
    p.goto(one["base"] + "/consult.html")
    p.wait_for_function("document.getElementById('date').value !== ''")
    assert p.input_value("#date") == vals["birth_date"] and p.input_value("#time") == vals["birth_time"] and p.input_value("#gender") == "female"
    assert p.input_value("#place") == "경기도 수원시" and p.input_value("#y1") == str(ny)
    ctx.close()
    # 이미 입력한 값은 덮어쓰지 않는다(응답이 늦게 와도)
    ctx = browser.new_context()
    p = ctx.new_page()
    p.route("**/api/v1/local-defaults", lambda r: (__import__("time").sleep(0.6), r.fulfill(status=200, content_type="application/json", body=json.dumps(vals)))[1])
    p.goto(one["base"] + "/consult.html")
    p.fill("#date", f"{1975:04d}-{6:02d}-{7:02d}")
    p.wait_for_timeout(1500)
    assert p.input_value("#date") == f"{1975:04d}-{6:02d}-{7:02d}"
    ctx.close()
