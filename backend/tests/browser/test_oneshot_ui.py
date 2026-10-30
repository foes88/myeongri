"""일회성 분석 모드(mingli-mode=oneshot) 브라우저 검증: 같은 출처 API(SERVE_WEB), 저장 없음, 토큰·번호 없음, 입력은 가상 값."""
import os
import re
import shutil
import subprocess
import sys

import pytest
from .conftest import assert_report_order, expanded_text, show_form

from .conftest import BACKEND, OUT, free_port, wait_http

pytestmark = pytest.mark.browser
WEB = BACKEND.parent / "web"
SIZES = {"360": (360, 800), "768": (768, 1024), "1440": (1440, 900)}


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
    assert_report_order(p)
    assert p.is_hidden("#f") and p.is_visible("#formbar")  # 분석 후 긴 입력란은 접힌다
    # 후속 질문·현실 사건·기록 목록
    p.fill("#q2", "사업은 어떨까요?")
    p.click("#askb")
    p.wait_for_selector("#out .record")
    p.select_option("#evt", "취업·이직")
    p.click("#evb")
    p.wait_for_function("document.querySelector('#evr').textContent.includes('분류:')")
    p.click("#hist")
    assert p.locator("#histout details").count() >= 2
    # 요청: 같은 출처 oneshot API 만, 토큰/번호/저장 API 호출 없음
    api = [(m, u) for m, u, pd in reqs if "/api/" in u]
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
