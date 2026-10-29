"""일회성 분석 모드(mingli-mode=oneshot) 브라우저 검증: 같은 출처 API(SERVE_WEB), 저장 없음, 토큰·번호 없음, 입력은 가상 값."""
import os
import re
import shutil
import subprocess
import sys

import pytest

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
    port = free_port()
    env = dict(os.environ, SERVE_WEB=str(d / "web"), CONSULT_DIR=str(consult_dir), PYTHONIOENCODING="utf-8")
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--host", "127.0.0.1", "--log-level", "warning"], cwd=BACKEND, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_http(f"http://127.0.0.1:{port}/api/v1/health")
        yield {"base": f"http://127.0.0.1:{port}", "consult_dir": consult_dir}
    finally:
        p.terminate()


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
    nos = [t.strip() for t in p.eval_on_selector_all(".chapter > .no", "els=>els.map(e=>e.textContent)")]
    assert "제3장" in nos and nos[-1] == "제11장"
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
    assert "지원 범위" in p.inner_text("#out")
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
