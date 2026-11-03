"""일회성 분석 모드(mingli-mode=oneshot) 브라우저 검증: 같은 출처 API(SERVE_WEB), 저장 없음, 토큰·번호 없음, 입력은 가상 값."""
import json
import os
import re
import shutil
import subprocess
import sys

import pytest
from .conftest import assert_verdict_layout, expanded_text, show_form

from .conftest import BACKEND, OUT, free_port, wait_http

pytestmark = pytest.mark.browser
WEB = BACKEND.parent / "web"
SIZES = {"360": (360, 800), "768": (768, 1024), "1024": (1024, 768), "1440": (1440, 900), "1920": (1920, 1080)}


@pytest.fixture(scope="module")
def one(tmp_path_factory):
    d = tmp_path_factory.mktemp("oneshot")
    shutil.copytree(WEB, d / "web", ignore=shutil.ignore_patterns("src"))
    f = d / "web" / "consult.html"
    f.write_text(re.sub(r'name="mingli-mode" content="[a-z-]+"', 'name="mingli-mode" content="oneshot"', f.read_text(encoding="utf-8")), encoding="utf-8")
    consult_dir = d / "consult"
    pg_schema = None
    if os.environ.get("PG_TEST_URL"):  # Postgres 로 회원 흐름 검증: 테스트마다 별도 스키마
        pg_schema = "b_" + os.urandom(5).hex()
    port = free_port()
    env = dict(os.environ, SERVE_WEB=str(d / "web"), CONSULT_DIR=str(consult_dir), APP_DB=str(d / "app.sqlite3"), APP_DATA_KEY="dGVzdC1rZXktMzItYnl0ZXMtbG9uZy10ZXN0LWtleSE=", PYTHONIOENCODING="utf-8")
    if pg_schema:
        env.update(DATABASE_URL=os.environ["PG_TEST_URL"], DATABASE_SCHEMA=pg_schema)
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--host", "127.0.0.1", "--log-level", "warning"], cwd=BACKEND, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_http(f"http://127.0.0.1:{port}/api/v1/health")
        yield {"base": f"http://127.0.0.1:{port}", "consult_dir": consult_dir}
    finally:
        p.terminate()
        if pg_schema:
            from app.accounts.pg_repo import PostgresRepo
            PostgresRepo(os.environ["PG_TEST_URL"], schema=pg_schema).drop_schema()


def open_page(browser, one, size="1440"):
    w, h = SIZES[size]
    ctx = browser.new_context(viewport={"width": w, "height": h})
    pg = ctx.new_page()
    reqs, console = [], []
    pg.on("request", lambda r: reqs.append((r.method, r.url, r.post_data)))
    pg.on("console", lambda m: console.append(m.text))
    pg.on("pageerror", lambda e: console.append("PAGEERROR " + str(e)))
    pg.goto(one["base"] + "/consult.html")
    return ctx, pg, reqs, console


def fill(pg, date="1984-06-15", time_="10:00"):  # 가상 입력
    pg.fill("#date", date)
    pg.fill("#time", time_)


def test_oneshot_ui_hides_storage_features_and_states_no_storage(browser, one):
    ctx, p, reqs, console = open_page(browser, one)
    assert "저장하지 않는 일회성 분석" in p.inner_text("#staticbanner")
    assert p.is_hidden(".devline") and p.is_hidden("#reopenbox") and p.is_hidden("#store")
    assert p.is_enabled("#date") and p.is_enabled("#f button[type=submit]")  # 실제 입력 가능
    ctx.close()


def test_oneshot_full_flow_without_any_storage(browser, one):
    ctx, p, reqs, console = open_page(browser, one)
    fill(p)
    p.fill("#q", "2030년에 이직을 생각합니다")
    p.click("#f button[type=submit]")
    p.wait_for_selector("#session:not([hidden])", timeout=60000)
    assert "저장되지 않는 일회성 분석" in p.inner_text("#cover")
    assert "상담 번호" not in p.inner_text("#cover") and p.locator("#status table.pillars").count() == 1
    assert_verdict_layout(p)
    assert p.is_hidden("#f") and p.is_visible("#dash-edit")  # 분석 후 긴 입력란은 접히고 컨트롤 바에 입력 수정 버튼이 있다
    # 후속 질문
    p.fill("#q2", "사업은 어떨까요?")
    p.click("#askb")
    p.wait_for_selector("#out .record")
    assert p.is_hidden("#evt") and p.is_hidden("#hist")  # 개발용 도구는 사용자 화면에 없다
    # 요청: 같은 출처 oneshot API 만, 토큰/번호/저장 API 호출 없음
    api = [(m, u) for m, u, pd in reqs if "/api/" in u and not u.endswith("/api/v1/local-defaults")]     # 로컬 기본값 조회(GET, 개인 정보 전송 없음)는 제외
    api = [(m, u) for m, u in api if not (m == "GET" and u.endswith("/api/v1/health"))]  # 회원 기능 사용 가능 여부 확인(개인정보 없음)
    assert api and all(m == "POST" and "/api/v1/oneshot/" in u and u.startswith(one["base"]) for m, u in api), api
    assert not [u for m, u, pd in reqs if "/consultations" in u]
    assert all("?" not in u for m, u, pd in reqs if "/api/" in u)  # 쿼리스트링에 개인정보 없음
    # 저장 없음: 브라우저 저장소 비어 있음, 서버 저장 디렉터리 없음/비어 있음
    assert p.evaluate("Object.keys(localStorage).length") == 0 and p.evaluate("Object.keys(sessionStorage).length") == 0 and p.evaluate("document.cookie") == ""
    cd = one["consult_dir"]
    assert not cd.exists() or not list(cd.iterdir())
    assert not [c for c in console if "PAGEERROR" in c or "Content Security" in c]
    ctx.close()


def test_oneshot_variant_selection_and_errors(browser, one):
    ctx, p, reqs, console = open_page(browser, one)
    fill(p, "2000-01-01", "19:25")  # 가상 입력: 명식이 갈리는 사례
    p.click("#f button[type=submit]")
    p.wait_for_selector("#variants:not([hidden]) button")
    assert "자동 선택하지 않음" in p.inner_text("#variants")
    p.locator("#variants button").last.click()
    p.wait_for_selector("#session:not([hidden])", timeout=60000)
    p.reload()
    fill(p, "1850-01-01", "10:00")
    p.click("#f button[type=submit]")
    p.wait_for_function("document.querySelector('#out .bad')")
    assert "지원 범위" in expanded_text(p, "#out")
    ctx.close()


@pytest.mark.parametrize("size", list(SIZES))
def test_oneshot_responsive_and_captures(browser, one, size):
    ctx, p, reqs, console = open_page(browser, one, size)
    OUT.mkdir(parents=True, exist_ok=True)
    cap = OUT / "oneshot"
    cap.mkdir(exist_ok=True)
    assert p.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    p.screenshot(path=str(cap / f"input_{size}.png"), full_page=True)
    fill(p)
    p.click("#f button[type=submit]")
    p.wait_for_selector("#session:not([hidden])", timeout=60000)
    assert p.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    p.screenshot(path=str(cap / f"result_{size}.png"), full_page=True)
    ctx.close()


def test_place_list_has_cities_and_custom_longitude(browser, one):
    ctx, p, reqs, console = open_page(browser, one)
    vals = p.eval_on_selector_all("#place option", "els=>els.map(e=>e.value)")
    assert len(vals) >= 150 and "경기도 수원시" in vals and "강원특별자치도 강릉시" in vals and "__custom__" in vals
    assert p.is_hidden("#lon")
    p.select_option("#place", "경기도 수원시")
    fill(p)
    p.click("#f button[type=submit]")
    p.wait_for_selector("#session:not([hidden])", timeout=60000)
    body = next(__import__("json").loads(pd) for m, u, pd in reqs if m == "POST" and u.endswith("/oneshot/analyze"))
    assert body["birth_place"] == "경기도 수원시" and body["longitude"] is None
    show_form(p)
    p.select_option("#place", "__custom__")
    p.fill("#lon", "127.5")
    p.click("#f button[type=submit]")
    p.wait_for_function("document.querySelectorAll('#out section').length>0")
    body2 = [__import__("json").loads(pd) for m, u, pd in reqs if m == "POST" and u.endswith("/oneshot/analyze")][-1]
    assert body2["longitude"] == 127.5
    ctx.close()



def _login_ui(p, email, pw="correct-horse-9", register=False):
    p.fill("#acct-mail", email)
    p.fill("#acct-pw", pw)
    p.click("#acct-reg" if register else "#acct-login")
    p.wait_for_selector("#acct-in:not([hidden])")


def test_member_flow_save_reopen_follow_up_export_isolation_and_delete(browser, one):
    ctx, p, reqs, console = open_page(browser, one)
    assert p.is_visible("#acct")
    assert p.evaluate("Object.keys(sessionStorage).length") == 0  # 로그인 전에는 저장소 사용 없음
    _login_ui(p, "ui-user@example.com", register=True)
    assert p.evaluate("document.cookie") == ""  # 쿠키 미사용
    fill(p)
    p.fill("#q", "2030년 재물과 직업이 궁금합니다")
    p.click("#f button[type=submit]")
    p.wait_for_selector("#session:not([hidden])", timeout=60000)
    assert "저장되었습니다" in p.inner_text("#cover") and "저장되지 않는" not in p.inner_text("#cover")
    p.wait_for_function("document.querySelectorAll('#mylist li button').length>=3")
    assert p.inner_text("#acct-n") == "1"
    posts = [u for m, u, pd in reqs if m == "POST"]
    assert any(u.endswith("/api/v1/reports") for u in posts) and not any("/oneshot/" in u for u in posts)
    assert all("1984-06-15" not in (u or "") for m, u, pd in reqs)  # 쿼리스트링에 출생 정보 없음
    # 후속 질문(서버가 맥락 유지) → 새로고침 → 로그인 → 열기 → 기록 복원
    p.fill("#q2", "사업 쪽은 어떻게 보이나요?")
    p.click("#askb")
    p.wait_for_selector("#out .record")
    p.reload()
    p.wait_for_selector("#acct-in:not([hidden])")  # 같은 탭에서는 세션 유지(패널은 서버 확인 후 표시되므로 기다린다)
    p.wait_for_selector("#mylist li button:has-text('열기')")
    p.click("#mylist li button:has-text('열기')")
    p.wait_for_selector("#out .record", timeout=30000)
    assert "사업" in p.inner_text("#out .record") and "다시 열었습니다" in p.inner_text("#cover")
    # 내보내기
    with p.expect_download() as dl:
        p.click("#mylist li button:has-text('내보내기')")
    txt = open(dl.value.path(), encoding="utf-8").read()
    assert "후속 질문 1" in txt and "1984-06-15" not in txt
    # 다른 회원은 이 리포트를 볼 수 없다
    p.click("#acct-logout")
    p.wait_for_selector("#acct-out:not([hidden])")
    assert p.evaluate("Object.keys(sessionStorage).length") == 0
    # 로그아웃하면 이전 사용자의 리포트·목록이 화면에서 사라진다
    assert p.is_hidden("#report") and p.inner_text("#out") == "" and p.inner_text("#acct-n") == "0" and p.locator("#mylist li").count() == 0
    _login_ui(p, "ui-other@example.com", register=True)
    assert p.inner_text("#acct-n") == "0"
    p.click("#acct-logout")
    # 원래 회원: 리포트 삭제 → 계정 삭제
    _login_ui(p, "ui-user@example.com")
    p.click("#mylist li button:has-text('삭제')")
    p.wait_for_function("document.getElementById('acct-n').textContent==='0'")
    p.click("#acct-in details summary")
    p.fill("#delpw", "correct-horse-9")
    p.click("#delacct")
    p.wait_for_selector("#acct-out:not([hidden])")
    p.fill("#acct-mail", "ui-user@example.com")
    p.fill("#acct-pw", "correct-horse-9")
    p.click("#acct-login")
    p.wait_for_function("document.getElementById('acct-msg').textContent.includes('올바르지')")
    assert not [c for c in console if "PAGEERROR" in c or "Content Security" in c]
    ctx.close()


def test_member_panel_errors_are_shown_and_anonymous_oneshot_unchanged(browser, one):
    ctx, p, reqs, console = open_page(browser, one)
    p.fill("#acct-mail", "nobody@example.com")
    p.fill("#acct-pw", "wrong-pass-123")
    p.click("#acct-login")
    p.wait_for_function("document.getElementById('acct-msg').textContent.length>0")
    assert "올바르지" in p.inner_text("#acct-msg") and p.is_hidden("#acct-in")
    p.fill("#acct-pw", "short")
    p.click("#acct-reg")
    p.wait_for_function("document.getElementById('acct-msg').textContent.includes('10자')")
    fill(p)
    p.click("#f button[type=submit]")
    p.wait_for_selector("#session:not([hidden])", timeout=60000)
    assert "저장되지 않는 일회성 분석" in p.inner_text("#cover")  # 비로그인 흐름은 기존 그대로
    assert any(u.endswith("/oneshot/analyze") for m, u, pd in reqs if m == "POST")
    assert p.evaluate("Object.keys(sessionStorage).length") == 0 and p.evaluate("Object.keys(localStorage).length") == 0
    ctx.close()


# ---------------------------------------------------------------- v8.0 MVP: 사람이 쓰는 순서대로
def test_mvp_first_screen_puts_the_birth_form_first_and_hides_technical_options(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "360")
    assert p.is_visible("#date") and p.is_visible("#submitb")
    assert p.evaluate("document.getElementById('adv').open") is False and p.is_hidden("#prof") and p.is_hidden("#depth")  # 기술 옵션은 접혀 있다
    assert p.is_hidden(".devline") and p.is_hidden("#store")
    y = lambda sel: p.evaluate(f"document.querySelector('{sel}').getBoundingClientRect().top + window.scrollY")
    assert y("#date") < y("#submitb") < y("#acct")  # 생년월일 → 분석 버튼 → (그 아래) 회원 패널
    assert p.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    # 모바일(360x800) 첫 화면 안에 생년월일 입력이 들어온다: 안내문이 입력을 밀어내지 않는다
    assert p.evaluate("document.getElementById('date').getBoundingClientRect().bottom") < 800
    p.locator("#adv summary").click()
    assert p.is_visible("#prof") and p.is_hidden("#depth")  # 해설 깊이 선택은 없다(결론형 한 가지)
    ctx.close()


def test_mvp_human_flow_loading_year_switch_multi_year_follow_up(browser, one):
    ctx, p, reqs, console = open_page(browser, one)
    import time

    def slow(route):  # 응답을 늦춰 로딩 상태를 관찰한다
        time.sleep(0.8)
        route.continue_()
    p.route("**/api/v1/oneshot/analyze", slow)
    p.select_option("#place", "경기도 수원시")
    p.fill("#date", "1984-06-15")  # 가상 입력
    p.fill("#time", "10:00")
    p.fill("#y1", "2030")
    for cb in p.query_selector_all("#doms input"):
        want = cb.get_attribute("value") in ("overall", "wealth", "career")
        if cb.is_checked() != want:
            cb.set_checked(want)
    p.click("#submitb")
    p.wait_for_function("!document.getElementById('busy').hidden")
    assert "분석 중" in p.inner_text("#busy") and p.is_disabled("#submitb")  # 로딩 표시 + 중복 제출 방지
    p.wait_for_selector("#verdict .dash-conclusion .concl-text", timeout=60000)
    assert p.is_enabled("#submitb") and p.is_hidden("#busy")
    # 첫 화면: 핵심 해석이 먼저, 상세는 접힘, 기술 로그 없음
    assert p.is_visible("#verdict .concl-text")
    top = lambda sel: p.evaluate(f"document.querySelector('{sel}').getBoundingClientRect().top + window.scrollY")
    assert top("#verdict") < top("#acct")  # 결과가 먼저, 회원 패널은 결과 아래
    assert p.locator("#verdict details[open]").count() == 0
    head2030 = p.inner_text("#verdict")
    body = next(json.loads(pd) for m, u, pd in reqs if m == "POST" and u.endswith("/oneshot/analyze"))
    assert body["birth_place"] == "경기도 수원시" and body["years"] == [2030] and body["birth_time"] == "10:00"
    # 다른 연도 재분석: 입력을 다시 쓰지 않고 한 번에
    p.click("#dash-next")
    p.wait_for_function("document.getElementById('formsum').textContent.includes('2031')", timeout=60000)
    bodies = [json.loads(pd) for m, u, pd in reqs if m == "POST" and u.endswith("/oneshot/analyze")]
    assert bodies[-1]["years"] == [2031] and bodies[-1]["birth_date"] == "1984-06-15"
    head2031 = p.inner_text("#verdict")
    assert head2031 != head2030  # 연도를 바꾸면 해설도 달라진다(같은 문장을 연도만 바꿔 되풀이하지 않는다)
    # 5년 범위: 정보 구조가 달라진다(기간 핵심 흐름 + 연도별 한 줄)
    p.click("#dash-to5")
    p.wait_for_selector("#verdict .timeline .tl-node", timeout=60000)
    assert p.locator("#verdict .tl-node").count() == 5 and bodies is not None
    # 연도를 고르면 그 해의 풀이가 해 패널과 분야 상세에 나타난다
    p.locator("#verdict .tl-node >> nth=2").click()
    p.wait_for_function("document.querySelector('#dash-year-panel h3').textContent==='2033년'")
    assert p.is_visible("#dash-dom-panel .dp-headline")
    assert_verdict_layout(p)
    # 후속 질문
    p.fill("#q2", "사업 쪽은 어떻게 보이나요?")
    p.click("#askb")
    p.wait_for_selector("#out .record")
    assert "사업" in p.inner_text("#out .record")
    assert all(("?" not in u) for m, u, pd in reqs if "/api/" in u)  # 쿼리스트링에 출생 정보 없음
    assert not [c for c in console if "PAGEERROR" in c]
    ctx.close()


def test_mvp_errors_explain_cause_and_next_step(browser, one):
    ctx, p, reqs, console = open_page(browser, one)
    p.click("#submitb")  # 생년월일 없이
    assert "생년월일을 입력" in p.inner_text("#busy") and p.evaluate("document.activeElement.id") == "date"
    p.fill("#date", "1984-06-15")  # 가상 입력
    p.fill("#y1", "1800")
    p.click("#submitb")
    assert "1901~2049" in p.inner_text("#busy") and p.evaluate("document.activeElement.id") == "y1"
    p.fill("#y1", "2030")
    # 서버 연결 실패
    p.route("**/api/v1/oneshot/analyze", lambda r: r.abort())
    p.click("#submitb")
    p.wait_for_function("document.getElementById('busy').textContent.includes('연결할 수 없습니다')")
    assert "다시 시도" in p.inner_text("#busy") and p.is_enabled("#submitb") and p.is_visible("#f")  # 입력은 남아 있고 다시 누를 수 있다
    # 서버 오류(500)
    p.unroute("**/api/v1/oneshot/analyze")
    p.route("**/api/v1/oneshot/analyze", lambda r: r.fulfill(status=500, content_type="application/json", body='{"detail":"x"}'))
    p.click("#submitb")
    p.wait_for_function("document.getElementById('busy').textContent.includes('분석을 마치지 못했습니다')")
    # 존재하지 않는 날짜(2월 30일) → 원인과 해결 방법
    p.unroute("**/api/v1/oneshot/analyze")
    p.select_option("#cal", "lunar")  # 음력인데 존재하지 않는 윤달을 고른 경우
    p.select_option("#leap", "true")
    p.fill("#date", "1984-03-15")  # 가상 입력
    p.click("#submitb")
    p.wait_for_function("document.getElementById('busy').textContent.includes('음력')")
    assert p.is_visible("#f") and "달력·윤달" in p.inner_text("#busy")  # 원인(존재하지 않는 음력 날짜)과 해결 방법(달력·윤달 확인)
    ctx.close()


def test_mvp_loading_animation_shows_while_analysis_runs_and_respects_reduced_motion(browser, one):
    import time
    ctx, p, reqs, console = open_page(browser, one)
    p.route("**/api/v1/oneshot/analyze", lambda r: (time.sleep(1.2), r.continue_()))
    fill(p)
    p.click("#submitb")
    p.wait_for_function("!document.getElementById('progress').hidden", timeout=5000)  # 0.25초 뒤 상단 진행 막대
    assert p.is_visible("#busy .spin") and p.get_attribute("body", "aria-busy") == "true"
    anim = p.evaluate("[getComputedStyle(document.querySelector('#busy .spin')).animationName, getComputedStyle(document.getElementById('progress'),'::after').animationName]")
    assert anim == ["spin", "prog"]
    p.wait_for_selector("#verdict .dash-conclusion .concl-text", timeout=60000)
    assert p.is_hidden("#progress") and p.get_attribute("body", "aria-busy") is None  # 끝나면 사라진다
    ctx.close()
    # 움직임 줄이기 설정: 애니메이션 없음(표시는 남음)
    ctx2 = browser.new_context(reduced_motion="reduce")
    p2 = ctx2.new_page()
    p2.goto(one["base"] + "/consult.html")
    p2.route("**/api/v1/oneshot/analyze", lambda r: (time.sleep(1.2), r.continue_()))
    fill(p2)
    p2.click("#submitb")
    p2.wait_for_function("!document.getElementById('progress').hidden", timeout=5000)
    assert p2.evaluate("[getComputedStyle(document.querySelector('#busy .spin')).animationName, getComputedStyle(document.getElementById('progress'),'::after').animationName]") == ["none", "none"]
    ctx2.close()


def test_fast_responses_do_not_flash_the_progress_bar(browser, one):
    ctx, p, reqs, console = open_page(browser, one)
    p.evaluate("window.__shown=0;new MutationObserver(()=>{if(!document.getElementById('progress').hidden)window.__shown++}).observe(document.getElementById('progress'),{attributes:true})")
    p.fill("#acct-mail", "x@example.com")
    p.fill("#acct-pw", "wrong-pass-123")
    p.click("#acct-login")  # 빠르게 끝나는 호출
    p.wait_for_function("document.getElementById('acct-msg').textContent.length>0")
    assert p.evaluate("window.__shown") == 0
    ctx.close()


def test_user_screen_and_api_expose_no_internal_information(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "360")
    fill(p)
    p.fill("#y1", "2030")      # 기본 연도는 '내년'이므로 질문의 연도와 맞춰 한 해만 본다
    p.fill("#q", "2030년 재물과 직업이 궁금합니다")
    for cb in p.query_selector_all("#doms input"):
        want = cb.get_attribute("value") in ("overall", "wealth", "career")
        if cb.is_checked() != want:
            cb.set_checked(want)
    p.click("#submitb")
    p.wait_for_selector("#verdict .dash-conclusion .concl-text", timeout=60000)
    assert_verdict_layout(p)
    # 분야 탭 순서: 종합운이 먼저. 선택한 분야는 결론 → 쉬운 설명 → 현실에서 생각해 볼 점 순서
    names = p.eval_on_selector_all("#verdict .dtab .dn", "els=>els.map(e=>e.textContent)")
    assert names == ["종합운", "재물운", "직업·승진운"]
    # 분야마다 이유 보기(쉬운 말)를 펼쳐도 전문 용어·번호가 없다
    for i in range(3):
        p.locator("#verdict .dtab").nth(i).click()
        order = p.evaluate("[...document.querySelector('#dash-dom-panel').children].map(c=>c.className||c.tagName)")
        assert order[0] == "dp-head" and order[1].startswith("dp-headline") and order[2] == "dp-cols"
        p.locator("#dash-dom-panel .fold summary").click()
    assert_verdict_layout(p)
    assert p.locator("#dash-dom-panel details[open]").count() == 1
    # 모바일 가독성: 가로 넘침 없고 핵심 결론이 360px 첫 화면(800px) 안에 온전히 보인다
    assert p.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    p.evaluate("window.scrollTo(0,0)")
    box = p.locator("#verdict .concl-text").bounding_box()
    assert box["y"] >= 0 and box["y"] + box["height"] <= 800, box
    # API 응답: 사용자용 키만, 내부 근거 문자열 없음
    body = next(json.loads(pd) for m, u, pd in reqs if m == "POST" and u.endswith("/oneshot/analyze"))
    raw = p.evaluate("async (b) => (await fetch('/api/v1/oneshot/analyze', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(b)})).text()", body)
    d = json.loads(raw)
    assert set(d["answer"]) == {"refused", "years", "domains", "verdict", "qa"} and "internal" not in d["answer"]["verdict"] and set(d["precommit"]) == {"pillars", "years", "domains", "calc"}
    leak = re.findall(r"L\d-[A-Z0-9-]+|claim\w*|natal_structure|synthesis|ruleset|content_hash|식상생재|지장간", raw)
    assert not leak, leak[:5]
    ctx.close()


@pytest.mark.parametrize("size", ["360", "1440"])
def test_v83_one_five_ten_year_views_and_year_comparison(browser, one, size):
    ctx, p, reqs, console = open_page(browser, one, size)
    fill(p)
    p.fill("#y1", "2027")
    for cb in p.query_selector_all("#doms input"):
        want = cb.get_attribute("value") in ("overall", "wealth", "career")
        if cb.is_checked() != want:
            cb.set_checked(want)
    # 1년
    p.click("#submitb")
    p.wait_for_selector("#verdict .dash-conclusion .concl-text", timeout=60000)
    assert_verdict_layout(p)
    assert p.locator("#verdict .dtab").count() == 3 and p.locator("#verdict .tl-node").count() == 1
    # 5년
    p.click("#dash-to5")
    p.wait_for_function("document.querySelectorAll('#verdict .tl-node').length===5", timeout=60000)
    assert_verdict_layout(p)
    # 10년: 연도 노드 10개(촘촘한 보기), 선택한 해 패널이 하나
    p.click("#dash-to10")
    p.wait_for_function("document.querySelectorAll('#verdict .tl-node').length===10", timeout=60000)
    assert p.locator("#verdict .timeline.compact").count() == 1 and p.locator("#dash-year-panel h3").count() == 1
    assert_verdict_layout(p)
    # 연도 비교(추천 질문 칩): 두 해를 함께 답한다
    chip = p.locator("#chips .chipq", has_text="어떤 차이가 있어")
    assert chip.count() == 1
    chip.click()
    p.wait_for_selector("#out .record")
    rec = p.locator("#out .record").last.inner_text()
    assert "2027년" in rec and "2028년" in rec and ("우열이 아니라" in rec or "크지 않" in rec or "어렵" in rec)
    assert not re.search(r"원국|대운|세운|(?:^|[\s(·])지지|천간|식상|재성|관성|인성|L\d-", rec)
    # 연도 이유 질문: 추적된 이유로 답한다
    p.fill("#q2", "2031년은 왜 달라지는 해야?")
    p.click("#askb")
    p.wait_for_function("document.querySelectorAll('#out .record').length>=2")
    why = p.locator("#out .record").last.inner_text()
    assert "2031년" in why and ("10월 2일" in why or "두드러지는 해로 뽑지 않았습니다" in why)
    assert p.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    assert not [c for c in console if "PAGEERROR" in c]
    ctx.close()
