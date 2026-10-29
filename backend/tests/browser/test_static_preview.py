"""정적 미리보기 모드(디자인 확인 전용) 검증. API 서버 없이 web/ 사본(메타 mingli-mode=static-preview)만 서빙한다.
검증: 입력 비활성화, 네트워크 전송 없음(정적 파일 GET 외 요청 없음), 저장 없음, 합성 데모 표시, 360/768/1440 레이아웃."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from .conftest import BACKEND, OUT, free_port, wait_http

pytestmark = pytest.mark.browser
WEB = BACKEND.parent / "web"
SIZES = {"360": (360, 800), "768": (768, 1024), "1440": (1440, 900)}


@pytest.fixture(scope="module")
def static_web(tmp_path_factory):
    d = tmp_path_factory.mktemp("static_web")
    shutil.copytree(WEB, d / "web", ignore=shutil.ignore_patterns("src"))
    f = d / "web" / "consult.html"
    html = f.read_text(encoding="utf-8")
    f.write_text(re.sub(r'name="mingli-mode" content="[a-z-]+"', 'name="mingli-mode" content="static-preview"', html), encoding="utf-8")
    port = free_port()
    p = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(d / "web")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_http(f"http://127.0.0.1:{port}/consult.html")
        yield f"http://127.0.0.1:{port}"
    finally:
        p.terminate()


def open_static(browser, base, size="1440"):
    w, h = SIZES[size]
    ctx = browser.new_context(viewport={"width": w, "height": h})
    page = ctx.new_page()
    reqs, console = [], []
    page.on("request", lambda r: reqs.append((r.method, r.url, r.post_data)))
    page.on("console", lambda m: console.append(m.text))
    page.on("pageerror", lambda e: console.append("PAGEERROR " + str(e)))
    page.add_init_script("window.__fetchCalls=0;const _f=window.fetch;window.fetch=function(){window.__fetchCalls++;return _f.apply(this,arguments)};"
                         "window.__xhr=0;const _o=XMLHttpRequest.prototype.open;XMLHttpRequest.prototype.open=function(){window.__xhr++;return _o.apply(this,arguments)}")
    page.goto(base + "/consult.html")
    return ctx, page, reqs, console


def test_static_banner_and_disabled_inputs(browser, static_web):
    ctx, p, reqs, console = open_static(browser, static_web)
    assert "정적 미리보기" in p.inner_text("#staticbanner") and "전송되거나 저장되지 않습니다" in p.inner_text("#staticbanner")
    assert p.evaluate("[...document.querySelectorAll('#f input,#f select,#f textarea,#f button')].every(e=>e.matches(':disabled'))")
    assert p.is_hidden(".devline") and p.is_hidden("#reopenbox")  # API 주소·재열람 입력 없음
    with pytest.raises(Exception):
        p.fill("#date", "1984-06-15", timeout=1500)  # 가상 입력 시도: 비활성화되어 입력 불가
    p.keyboard.press("Enter")
    assert p.evaluate("window.__fetchCalls")==0
    ctx.close()


@pytest.mark.parametrize("depth", ["summary", "detailed", "expert"])
def test_demo_report_renders_without_any_network_send(browser, static_web, depth):
    ctx, p, reqs, console = open_static(browser, static_web)
    p.wait_for_function("typeof window.MINGLI_DEMO==='object'")
    p.select_option("#demodepth", depth)
    p.click("#demobtn")
    p.wait_for_selector("#session:not([hidden])")
    text = p.inner_text("#report")
    assert "합성 데모" in text and "실제 분석 결과가 아닙니다" in text
    nos = [t.strip() for t in p.eval_on_selector_all(".chapter > .no", "els=>els.map(e=>e.textContent)")]
    assert nos[-1] == "제11장" and "제3장" in nos
    assert ("전문가용 상세" in p.evaluate("(()=>{const e=document.querySelector('#out .expert-only');return e?getComputedStyle(e,'::before').content:''})()")) == (depth == "expert")
    # 명식 표, 대운·세운 구간 표, 고전 근거 상세
    assert p.locator("#status table.pillars").count() == 1 and p.locator("#out table").count() >= 1
    assert "고전 근거" in text and p.locator("#out details summary").count() >= 3
    # 기록 UI
    p.click("#demoask")
    p.wait_for_selector("#out .record")
    assert "기록 1" in p.inner_text("#out .record")
    # 네트워크: 정적 파일 GET 외 요청 없음, fetch/XHR 0건, 저장 없음
    assert all(m == "GET" and u.startswith(static_web) for m, u, pd in reqs), [r for r in reqs if not (r[0] == "GET" and r[1].startswith(static_web))]
    assert p.evaluate("window.__fetchCalls") == 0 and p.evaluate("window.__xhr") == 0
    assert p.evaluate("Object.keys(localStorage).length") == 0 and p.evaluate("Object.keys(sessionStorage).length") == 0
    assert p.evaluate("document.cookie") == ""
    assert not [c for c in console if "PAGEERROR" in c]
    ctx.close()


@pytest.mark.parametrize("size", list(SIZES))
def test_static_preview_layout_and_captures(browser, static_web, size):
    ctx, p, reqs, console = open_static(browser, static_web, size)
    OUT.mkdir(parents=True, exist_ok=True)
    cap = OUT / "preview"
    cap.mkdir(exist_ok=True)
    assert p.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    p.screenshot(path=str(cap / f"input_{size}.png"), full_page=True)
    p.wait_for_function("typeof window.MINGLI_DEMO==='object'")
    p.select_option("#demodepth", "detailed")
    p.click("#demobtn")
    p.wait_for_selector("#session:not([hidden])")
    p.click("#demoask")
    p.wait_for_selector("#out .record")
    assert p.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    wide = p.evaluate("[...document.querySelectorAll('#report *')].filter(e=>e.scrollWidth>e.clientWidth+1&&getComputedStyle(e).overflowX==='visible'&&e.tagName!=='TABLE').map(e=>e.tagName+'.'+e.className).slice(0,5)")
    assert wide == [], wide
    p.screenshot(path=str(cap / f"result_{size}.png"), full_page=True)
    p.locator("#status").screenshot(path=str(cap / f"status_{size}.png"))
    p.locator("#out .record").first.screenshot(path=str(cap / f"record_{size}.png"))
    p.locator("#session").screenshot(path=str(cap / f"session_{size}.png"))
    ctx.close()


def test_landing_is_static_and_links_to_consult(browser, static_web):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    p = ctx.new_page()
    p.goto(static_web + "/index.html")
    assert p.get_attribute("a.btn:not(.ghost)", "href") == "consult.html"
    cap = OUT / "preview"
    cap.mkdir(parents=True, exist_ok=True)
    for size, (w, h) in SIZES.items():
        p.set_viewport_size({"width": w, "height": h})
        assert p.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        p.screenshot(path=str(cap / f"main_{size}.png"))
        p.goto(static_web + "/index.html#example")
        p.screenshot(path=str(cap / f"example_{size}.png"), full_page=True)
        p.goto(static_web + "/index.html")
    ctx.close()


def test_vercel_config_blocks_network_and_forms_if_present():
    cfg = json.loads((WEB.parent / "vercel.json").read_text(encoding="utf-8"))
    heads = {h["key"]: h["value"] for r in cfg.get("headers", []) for h in r["headers"]}
    assert heads.get("X-Robots-Tag") == "noindex"
    csp = heads.get("Content-Security-Policy")
    if csp is None:
        pytest.skip("CSP 는 미리보기 브랜치(preview/*) 설정에서만 요구")
    assert "connect-src 'self'" in csp and "form-action 'none'" in csp and "frame-ancestors 'none'" in csp


@pytest.fixture(scope="module")
def header_web(tmp_path_factory):
    """vercel.json 헤더(CSP 등)를 그대로 적용한 서버."""
    d = tmp_path_factory.mktemp("hdr_web")
    shutil.copytree(WEB, d / "web", ignore=shutil.ignore_patterns("src"))
    f = d / "web" / "consult.html"
    f.write_text(re.sub(r'name="mingli-mode" content="[a-z-]+"', 'name="mingli-mode" content="static-preview"', f.read_text(encoding="utf-8")), encoding="utf-8")
    port = free_port()
    p = subprocess.Popen([sys.executable, str(Path(__file__).with_name("serve_with_headers.py")), str(d / "web"), str(port), str(WEB.parent / "vercel.json")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_http(f"http://127.0.0.1:{port}/consult.html")
        yield f"http://127.0.0.1:{port}"
    finally:
        p.terminate()


def test_csp_headers_allow_demo_but_block_external_network_send(browser, header_web):
    cfg = json.loads((WEB.parent / "vercel.json").read_text(encoding="utf-8"))
    if not any(h["key"] == "Content-Security-Policy" for r in cfg.get("headers", []) for h in r["headers"]):
        pytest.skip("CSP 미설정(라이브 개발 브랜치)")
    ctx = browser.new_context(viewport={"width": 1100, "height": 900})
    p = ctx.new_page()
    console = []
    p.on("console", lambda m: console.append(m.text))
    p.on("pageerror", lambda e: console.append("PAGEERROR " + str(e)))
    p.goto(header_web + "/consult.html")
    p.wait_for_function("typeof window.MINGLI_DEMO==='object'")  # 정적 스크립트는 허용
    p.click("#demobtn")
    p.wait_for_selector("#session:not([hidden])")
    assert "합성 데모" in p.inner_text("#report")
    # 외부 출처로의 fetch 는 CSP(connect-src 'self')로 차단된다. 정적 모드 코드는 같은 출처 호출도 하지 않는다(위 테스트에서 fetch 0건 확인)
    res2 = p.evaluate("fetch('https://example.com/x',{method:'POST',body:'x'}).then(()=>'sent').catch(e=>'blocked')")
    assert res2 == "blocked"
    assert not [c for c in console if "PAGEERROR" in c]
    # 폼 제출 차단(form-action 'none') + 프레임 삽입 금지
    assert p.evaluate("new Promise(r=>{const f=document.createElement('form');f.action='https://example.com';f.method='post';document.body.append(f);try{f.submit()}catch(e){};setTimeout(()=>r(location.href),400)})").startswith(header_web)
    ctx.close()
