"""브라우저 통합 테스트 fixture. 마커 browser; playwright/chromium 이 없으면 skip. 로컬 127.0.0.1 서버만 사용한다."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
WEB = BACKEND.parent / "web"
OUT = BACKEND / "data_private" / "browser"   # 스크린샷·결과(gitignored)

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover
    sync_playwright = None


def pytest_configure(config):
    config.addinivalue_line("markers", "browser: 실제 브라우저(Playwright) 테스트 — 기본 실행에서는 -m browser 로만 선택")


def pytest_collection_modifyitems(config, items):
    if "browser" in (config.getoption("-m") or ""):
        return
    skip = pytest.mark.skip(reason="브라우저 테스트: python -m pytest -m browser tests/browser (playwright+chromium 필요)")
    for it in items:
        if "browser" in it.keywords:
            it.add_marker(skip)


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def wait_http(url, timeout=40):
    t = time.time()
    while time.time() - t < timeout:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except Exception as e:
            if getattr(e, "code", None):
                return
            time.sleep(0.4)
    raise RuntimeError(f"서버 시작 실패: {url}")


class Env:
    pass


@pytest.fixture(scope="session")
def env(tmp_path_factory):
    if sync_playwright is None:
        pytest.skip("playwright 미설치")
    e = Env()
    e.api_port, e.web_port = free_port(), free_port()
    e.api, e.web = f"http://127.0.0.1:{e.api_port}", f"http://127.0.0.1:{e.web_port}"
    e.consult_dir = tmp_path_factory.mktemp("consult")
    envv = dict(os.environ, CONSULT_DIR=str(e.consult_dir), CORS_ORIGINS=e.web, PYTHONIOENCODING="utf-8")
    e.p_api = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(e.api_port), "--host", "127.0.0.1", "--log-level", "warning"],
                               cwd=BACKEND, env=envv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import re as _re
    import shutil
    live = tmp_path_factory.mktemp("live_web") / "web"
    shutil.copytree(WEB, live, ignore=shutil.ignore_patterns("src"))
    cf = live / "consult.html"
    cf.write_text(_re.sub(r'name="mingli-mode" content="[a-z-]+"', 'name="mingli-mode" content="live"', cf.read_text(encoding="utf-8")), encoding="utf-8")  # 라이브(저장형 상담) 모드로 검증
    e.p_web = subprocess.Popen([sys.executable, "-m", "http.server", str(e.web_port), "--bind", "127.0.0.1", "--directory", str(live)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_http(e.api + "/api/v1/health")
        wait_http(e.web + "/consult.html")
        yield e
    finally:
        for p in (e.p_api, e.p_web):
            p.terminate()
            try:
                p.wait(timeout=10)
            except Exception:
                p.kill()


@pytest.fixture(scope="session")
def browser():
    if sync_playwright is None:
        pytest.skip("playwright 미설치")
    pw = sync_playwright().start()
    try:
        b = pw.chromium.launch()
    except Exception as ex:
        pw.stop()
        pytest.skip(f"chromium 실행 불가: {ex}")
    yield b
    b.close()
    pw.stop()


class Session:
    def __init__(self, page, env):
        self.page, self.env = page, env
        self.console, self.requests = [], []
        page.on("console", lambda m: self.console.append(m.text))
        page.on("pageerror", lambda e: self.console.append("PAGEERROR " + str(e)))
        page.on("request", lambda r: self.requests.append((r.method, r.url, r.post_data)))

    def open(self, api=None):
        self.page.goto(self.env.web + "/consult.html")
        self.page.fill("#api", api or self.env.api)

    def fill_birth(self, date="1984-06-15", time_="10:00", gender="male", cal="solar", leap="false", prof="standard"):  # 가상 입력
        p = self.page
        p.fill("#date", date)
        p.fill("#time", time_)
        p.select_option("#gender", gender)
        p.select_option("#cal", cal)
        p.select_option("#leap", leap)
        p.select_option("#prof", prof)

    def set_domains(self, doms):
        for cb in self.page.query_selector_all("#doms input"):
            want = cb.get_attribute("value") in doms
            if cb.is_checked() != want:
                cb.set_checked(want)

    def start(self):
        self.page.click("#f button[type=submit]")
        self.page.wait_for_selector("#session:not([hidden])", timeout=60000)


@pytest.fixture()
def sess(browser, env):
    ctx = browser.new_context(viewport={"width": 1100, "height": 900})
    page = ctx.new_page()
    s = Session(page, env)
    yield s
    ctx.close()


@pytest.fixture(scope="session")
def results():
    r = {}
    yield r
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "browser_results.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
