"""web/consult.html 브라우저 통합·접근성 테스트. 모든 입력은 가상 값. 실행: python -m pytest -m browser tests/browser -q"""
import json
import re

import pytest

from .conftest import OUT

pytestmark = pytest.mark.browser

ALL_DOMS = ["overall", "wealth", "career", "business", "docs_realestate", "real_estate", "job_change", "love_marriage", "family", "health_traditional", "luck"]


def lum(hexc):
    h = hexc.lstrip("#")
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    la, lb = sorted([lum(a), lum(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


def rgb2hex(s):
    m = re.findall(r"[\d.]+", s)
    return "#%02x%02x%02x" % tuple(int(float(x)) for x in m[:3])


def test_01_birth_input_and_status_panel(sess, results):
    sess.open()
    sess.fill_birth(cal="solar", prof="mean_solar")
    sess.set_domains(["overall", "wealth"])
    sess.start()
    st = sess.page.inner_text("#status")
    assert "검증 상태" in st and "판정: V" in st and "계산 프로필" in st and "기록 해시" in st
    assert "CORE_VALIDATED" in st and "TIME_PROFILE_VALIDATED" in st and "LUNAR_KR" in st and "고전 원문 대조 전 규칙" in st
    assert "검증이 끝나지 않은 범위" in st
    results["01_status_panel"] = "pass"


def test_01b_lunar_leap_input(sess):
    sess.open()
    sess.fill_birth(date="2012-04-21", cal="lunar", leap="true")  # 가상 입력(음력 입력 값: 연-월-일)
    sess.page.fill("#date", "2012-03-01")
    sess.set_domains(["overall"])
    sess.start()
    assert "LUNAR_KR" in sess.page.inner_text("#status")


@pytest.mark.parametrize("kind,years", [("year", [2030]), ("r5", [2030, 2031, 2032, 2033, 2034]), ("cmp", [2030, 2033])])
def test_02_period_selection_sent_values(sess, kind, years, results):
    sess.open()
    sess.fill_birth()
    sess.set_domains(["overall"])
    sess.page.select_option("#pk", kind)
    sess.page.fill("#y1", "2030")
    if kind == "cmp":
        sess.page.fill("#y2", "2033")
    assert ", ".join(map(str, years)) in sess.page.inner_text("#pdesc")
    sess.start()
    body = next(json.loads(pd) for m, u, pd in sess.requests if m == "POST" and u.endswith("/api/v1/consultations"))
    assert body["years"] == years
    results[f"02_period_{kind}"] = "pass"


def test_02b_ten_year_range(sess):
    sess.open()
    sess.fill_birth()
    sess.set_domains(["overall"])
    sess.page.select_option("#pk", "r10")
    sess.page.fill("#y1", "2030")
    sess.start()
    body = next(json.loads(pd) for m, u, pd in sess.requests if m == "POST" and u.endswith("/api/v1/consultations"))
    assert body["years"] == list(range(2030, 2040))


def test_03_all_domains_and_depths(sess, results):
    sess.open()
    sess.fill_birth()
    sess.set_domains(ALL_DOMS)
    sess.page.select_option("#depth", "expert")
    sess.start()
    out = sess.page.inner_text("#out")
    for name in ["재물운", "직업·승진운", "사업운", "연애·결혼운", "가족·인간관계운", "건강 관련 전통 해석", "이직·취업운", "부동산운"]:
        assert name in out, name
    assert "전문가: 규칙 ID·고전 대조" in out and "학파별 차이" in out
    assert "의료진과 상담" in out  # 건강 전통 해석의 의료 고지
    results["03_all_domains_expert"] = "pass"
    for d in ("summary", "detailed"):
        s2 = sess.page
        s2.select_option("#depth", d)
        s2.click("#f button[type=submit]")
        s2.wait_for_function("document.querySelectorAll('#out section').length>=1")
        assert ("전문가: 규칙 ID" in s2.inner_text("#out")) is False


def test_04_followup_event_reanalyze_history(sess, results):
    sess.open()
    sess.fill_birth()
    sess.set_domains(["career", "job_change"])
    sess.page.fill("#q", "2030년에 이직을 생각합니다")
    sess.start()
    p = sess.page
    n0 = len(p.query_selector_all("#out section"))
    p.fill("#q2", "사업은 어떨까요?")
    p.click("#askb")
    p.wait_for_function(f"document.querySelectorAll('#out section').length>{n0}")
    assert "사업" in p.inner_text("#out") or "사전 분석 기록에 포함되지" in p.inner_text("#out")
    p.select_option("#evt", "취업·이직")
    p.fill("#evy", "2030")
    p.click("#evb")
    p.wait_for_function("document.getElementById('evr').textContent.includes('분류')")
    assert re.search(r"분류: (consistent|inconsistent|not_judged)", p.inner_text("#evr"))
    h0 = re.search(r"기록 해시: (\w{12})", p.inner_text("#status")).group(1)
    p.select_option("#pap", "sanmyeongtonghoe_4")
    p.click("#reb")
    p.wait_for_function("document.getElementById('rer').textContent.includes('재분석 기록')")
    assert h0 in p.inner_text("#rer")
    p.click("#hist")
    p.wait_for_function("document.querySelectorAll('#histout details').length>=3")
    hist = p.inner_text("#histout")
    assert "답변" in hist and "현실 사건" in hist and "재분석" in hist
    results["04_followup_event_reanalyze_history"] = "pass"


def test_05_variant_selection(sess, results):
    sess.open()
    sess.fill_birth(date="2000-01-01", time_="19:25")  # 가상 입력: 시간 보정에 따라 명식이 갈리는 사례
    sess.set_domains(["overall"])
    sess.page.click("#f button[type=submit]")
    sess.page.wait_for_selector("#variants:not([hidden]) button")
    assert "자동 선택하지 않음" in sess.page.inner_text("#variants")
    btns = sess.page.query_selector_all("#variants button")
    assert len(btns) >= 2
    btns[-1].click()
    sess.page.wait_for_selector("#session:not([hidden])", timeout=60000)
    assert "명식이" in sess.page.inner_text("#status")
    results["05_variant_selection"] = "pass"


def test_06_token_and_access(sess, env, results):
    sess.open()
    sess.fill_birth()
    sess.set_domains(["overall"])
    sess.start()
    txt = sess.page.inner_text("#cover")
    tid = re.search(r"상담 번호: (\w{32})", txt).group(1)
    # 토큰은 화면에 표시되지 않고(번호만 표시), JS 변수에만 있다
    tok = sess.page.evaluate("token")
    assert tok and tok not in txt and tok not in sess.page.url
    assert tok not in json.dumps(sess.page.evaluate("Object.assign({},localStorage)"))
    assert tok not in json.dumps(sess.page.evaluate("Object.assign({},sessionStorage)")), "sessionStorage 에 토큰이 남아 있다"
    assert tok not in " ".join(sess.console)
    assert all(tok not in u for m, u, pd in sess.requests)  # URL 에 토큰 없음(헤더로만)
    # 잘못된 토큰 → 실패 메시지
    p2 = sess.page.context.new_page()
    s2 = type(sess)(p2, env)
    s2.open()
    p2.fill("#rt", tid)
    p2.fill("#rk", "wrong-token")
    p2.click("#reopen")
    p2.wait_for_selector("#out .bad")
    assert "재열람 실패" in p2.inner_text("#out") and "권한" in p2.inner_text("#out")
    p2.fill("#rk", tok)
    p2.click("#reopen")
    p2.wait_for_selector("#session:not([hidden])")
    assert "재열람" in p2.inner_text("#status")
    p2.wait_for_function("document.querySelectorAll('#histout details').length>=1")
    results["06_token"] = {"storage": "JS 변수(메모리)만; localStorage/sessionStorage/URL/콘솔에 없음", "reopen_wrong": "403 메시지", "reopen_ok": "pass"}


def test_07_error_screens(sess, env, results):
    sess.open(api="http://127.0.0.1:1")  # 닫힌 포트
    sess.fill_birth()
    sess.set_domains(["overall"])
    sess.page.click("#f button[type=submit]")
    sess.page.wait_for_selector("#out .bad")
    assert "연결할 수 없습니다" in sess.page.inner_text("#out")
    sess.page.fill("#api", env.api)
    sess.page.fill("#date", "1850-01-01")  # 범위 밖 → 422
    sess.page.click("#f button[type=submit]")
    sess.page.wait_for_function("document.querySelector('#out .bad') && document.querySelector('#out').textContent.includes('지원 범위')")
    results["07_errors"] = "연결 실패/422 메시지 표시 확인"


def test_08_no_birth_in_url_console_or_storage(sess, results):
    sess.open()
    sess.fill_birth(date="1984-06-15", time_="10:00")  # 가상 입력
    sess.set_domains(["overall"])
    sess.page.fill("#q", "내 사주가 궁금해요")
    sess.start()
    for m, u, pd in sess.requests:
        assert "1984" not in u and "birth" not in u and "?" not in u.split("/consult.html")[0].replace(sess.env.api, "") or m == "GET" and u.endswith("consult.html")
    assert not any("1984-06-15" in c for c in sess.console)
    ls = sess.page.evaluate("Object.assign({},localStorage)")
    assert list(ls.keys()) == ["api"], ls
    assert "1984" not in sess.page.url
    results["08_privacy_exposure"] = {"localStorage_keys": list(ls.keys()), "birth_in_url": False, "birth_in_console": False}


def test_09_mobile_360_layout_and_touch_targets(browser, env, results):
    ctx = browser.new_context(viewport={"width": 360, "height": 740})
    page = ctx.new_page()
    page.goto(env.web + "/consult.html")
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), "가로 스크롤 발생"
    small = page.evaluate("""[...document.querySelectorAll('button,select,input:not([type=checkbox]),summary')].filter(e=>e.offsetParent!==null).map(e=>[e.id||e.tagName,e.getBoundingClientRect().height]).filter(x=>x[1]<36)""")
    assert small == [], small
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / "consult_360.png"), full_page=True)
    ctx.close()
    results["09_mobile_360"] = "가로 스크롤 없음, 컨트롤 높이 ≥36px"


def test_09b_keyboard_only_flow(sess, results):
    sess.open()
    p = sess.page
    p.fill("#date", "1984-06-15")  # 가상 입력
    p.focus("#date")
    order = []
    for _ in range(40):
        p.keyboard.press("Tab")
        order.append(p.evaluate("document.activeElement.id || document.activeElement.tagName"))
        if order[-1] == "q":
            break
    assert "time" in order and "gender" in order and "depth" in order and order[-1] == "q"
    p.keyboard.press("Tab")  # store 체크박스
    p.keyboard.press("Space")
    p.keyboard.press("Tab")  # submit 버튼
    assert p.evaluate("document.activeElement.type") == "submit"
    p.keyboard.press("Enter")
    p.wait_for_selector("#session:not([hidden])", timeout=60000)
    # 포커스 표시: 포커스된 컨트롤에 눈에 띄는 outline
    p.focus("#askb")
    ol = p.evaluate("getComputedStyle(document.activeElement).outlineStyle+' '+getComputedStyle(document.activeElement).outlineWidth")
    assert not ol.startswith("none")
    # details/summary 키보드 펼치기
    p.focus("#out details summary")
    was = p.evaluate("document.activeElement.parentElement.open")
    p.keyboard.press("Enter")
    assert p.evaluate("document.activeElement.parentElement.open") != was
    results["09b_keyboard"] = {"tab_order_head": order[:8], "focus_outline": ol, "details_toggle": "Enter"}


def test_09c_labels_and_live_regions(sess, results):
    sess.open()
    p = sess.page
    unl = p.evaluate("""[...document.querySelectorAll('input,select,textarea')].filter(e=>{
        if(e.type==='hidden')return false; if(e.labels&&e.labels.length)return false; return !e.getAttribute('aria-label')&&!e.getAttribute('aria-labelledby')}).map(e=>e.id)""")
    assert unl == [], unl
    assert p.get_attribute("html", "lang") == "ko"
    for sel in ("#out", "#status", "#evr", "#rer", "#variants"):
        assert p.get_attribute(sel, "aria-live") in ("polite", "assertive") or p.get_attribute(sel, "role") in ("status", "alert"), sel
    assert p.get_attribute("#doms", "role") == "group" and p.get_attribute("#doms", "aria-label")
    results["09c_labels"] = "모든 입력에 label, 결과 영역 aria-live 확인"


def test_09d_color_contrast(sess, results):
    sess.open()
    p = sess.page
    rows = {}
    checks = {"본문": "body", "작은 설명 .small": ".small", "일반 버튼": "#f button[type=submit]", "보조 버튼": "button.sec", "h2": "h2", "경고 .bad": None}
    for name, sel in checks.items():
        if not sel:
            continue
        fg, bg = p.evaluate("""s=>{const e=document.querySelector(s);const c=getComputedStyle(e);let b=c.backgroundColor,n=e;while((b==='rgba(0, 0, 0, 0)'||b==='transparent')&&n.parentElement){n=n.parentElement;b=getComputedStyle(n).backgroundColor}return [c.color,b]}""", sel)
        rows[name] = round(contrast(rgb2hex(fg), rgb2hex(bg)), 2)
    # 동적 요소(.cid, .badge, .bad)를 DOM 에 넣어 실제 계산
    p.evaluate("""()=>{const d=document.createElement('div');d.className='card';d.id='probe';d.innerHTML='<span class=cid>cid</span><span class="badge">b</span><span class="badge off">b</span><p class=bad>bad</p>';document.body.append(d)}""")
    for name, sel in {"claim id .cid": "#probe .cid", "배지": "#probe .badge:not(.off)", "경고 배지": "#probe .badge.off", "오류 .bad": "#probe .bad"}.items():
        fg, bg = p.evaluate("""s=>{const e=document.querySelector(s);const c=getComputedStyle(e);let b=c.backgroundColor,n=e;while((b==='rgba(0, 0, 0, 0)'||b==='transparent')&&n.parentElement){n=n.parentElement;b=getComputedStyle(n).backgroundColor}return [c.color,b]}""", sel)
        rows[name] = round(contrast(rgb2hex(fg), rgb2hex(bg)), 2)
    results["09d_contrast"] = rows
    low = {k: v for k, v in rows.items() if v < 4.5}
    assert not low, low
