"""디자인 확인용 캡처(로컬 전용). 합성/가상 입력만 사용하며 이미지는 backend/data_private/design/ (gitignored)에 저장한다.
실행: python -m tools.capture_design [--only main,input,result,record]
"""
import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BACKEND = Path(__file__).resolve().parents[1]
WEB = BACKEND.parent / "web"
OUT = BACKEND / "data_private" / "design"
SIZES = {"360": (360, 800), "768": (768, 1024), "1440": (1440, 900)}


def free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def wait(url):
    import urllib.request
    for _ in range(80):
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except Exception as e:
            if getattr(e, "code", None):
                return
            time.sleep(0.3)
    raise RuntimeError(url)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    api_p, web_p = free_port(), free_port()
    api, web = f"http://127.0.0.1:{api_p}", f"http://127.0.0.1:{web_p}"
    import tempfile
    env = dict(os.environ, CONSULT_DIR=tempfile.mkdtemp(), CORS_ORIGINS=web, PYTHONIOENCODING="utf-8")
    pa = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(api_p), "--host", "127.0.0.1", "--log-level", "warning"], cwd=BACKEND, env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pw_ = subprocess.Popen([sys.executable, "-m", "http.server", str(web_p), "--bind", "127.0.0.1", "--directory", str(WEB)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait(api + "/api/v1/health")
        wait(web + "/index.html")
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            for name, (w, h) in SIZES.items():
                ctx = b.new_context(viewport={"width": w, "height": h})
                pg = ctx.new_page()
                pg.goto(web + "/index.html")
                pg.screenshot(path=str(OUT / f"main_{name}.png"), full_page=False)
                pg.goto(web + "/index.html#example")
                pg.screenshot(path=str(OUT / f"example_{name}.png"), full_page=True)
                pg.goto(web + "/consult.html")
                pg.fill("#api", api)
                pg.screenshot(path=str(OUT / f"input_{name}.png"), full_page=True)
                pg.fill("#date", "1984-06-15")  # 가상 입력
                pg.fill("#time", "10:00")
                for cb in pg.query_selector_all("#doms input"):
                    want = cb.get_attribute("value") in ("overall", "wealth", "career", "love_marriage")
                    if cb.is_checked() != want:
                        cb.set_checked(want)
                pg.fill("#q", "2030년에 이직을 생각하고 있습니다")
                pg.click("#f button[type=submit]")
                pg.wait_for_selector("#session:not([hidden])", timeout=60000)
                pg.screenshot(path=str(OUT / f"result_{name}.png"), full_page=True)
                pg.fill("#q2", "사업 쪽은 어떻게 보이나요?")
                pg.click("#askb")
                pg.wait_for_function("document.querySelectorAll('#out .record').length>=1")
                pg.click("#hist")
                pg.wait_for_function("document.querySelectorAll('#histout details').length>=2")
                pg.locator("#out .record").first.screenshot(path=str(OUT / f"record_{name}.png"))
                pg.locator("#session").screenshot(path=str(OUT / f"session_{name}.png"))
                overflow = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                print(name, "horizontal overflow px:", overflow)
                ctx.close()
            b.close()
    finally:
        for p in (pa, pw_):
            p.terminate()
    print("saved to", OUT)


if __name__ == "__main__":
    main()
