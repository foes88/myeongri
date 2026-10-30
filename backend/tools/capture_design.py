"""디자인 확인용 캡처(로컬 전용). 합성/가상 입력만 사용하며 이미지는 backend/data_private/design/ (gitignored)에 저장한다.
장면: main, example, input, y1(1년), y5(5년), y10(10년), domains(분야별 상세 펼침), record(상담 기록), edit(입력 수정), evidence(근거 상세 펼침).
각 해상도(360/768/1440)에서 가로 넘침·접기/펼치기 동작을 함께 검사한다. 실행: python -m tools.capture_design
"""
import json
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


def overflow(pg):
    return pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def analyze(pg, kind, q, doms=("overall", "wealth", "career")):
    if pg.locator("#formbar").is_visible():
        pg.click("#formedit")
    pg.fill("#date", "1984-06-15")  # 가상 입력
    pg.fill("#time", "10:00")
    pg.select_option("#pk", kind)
    pg.fill("#y1", "2027" if kind != "year" else "2030")
    for cb in pg.query_selector_all("#doms input"):
        want = cb.get_attribute("value") in doms
        if cb.is_checked() != want:
            cb.set_checked(want)
    pg.fill("#q", q)
    pg.click("#f button[type=submit]")
    pg.wait_for_selector("#formbar:not([hidden])", timeout=60000)  # 새 결과가 그려지고 입력란이 접힌 뒤


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    api_p, web_p = free_port(), free_port()
    api, web = f"http://127.0.0.1:{api_p}", f"http://127.0.0.1:{web_p}"
    import tempfile
    env = dict(os.environ, CONSULT_DIR=tempfile.mkdtemp(), CORS_ORIGINS=web, PYTHONIOENCODING="utf-8")
    pa = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(api_p), "--host", "127.0.0.1", "--log-level", "warning"], cwd=BACKEND, env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import re
    import shutil
    live = Path(tempfile.mkdtemp()) / "web"  # 라이브(저장형 상담) 모드 사본으로 캡처
    shutil.copytree(WEB, live, ignore=shutil.ignore_patterns("src"))
    cf = live / "consult.html"
    cf.write_text(re.sub(r'name="mingli-mode" content="[a-z-]+"', 'name="mingli-mode" content="live"', cf.read_text(encoding="utf-8")), encoding="utf-8")
    pw_ = subprocess.Popen([sys.executable, "-m", "http.server", str(web_p), "--bind", "127.0.0.1", "--directory", str(live)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    report = {}
    try:
        wait(api + "/api/v1/health")
        wait(web + "/index.html")
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            for name, (w, h) in SIZES.items():
                ctx = b.new_context(viewport={"width": w, "height": h})
                pg = ctx.new_page()
                r = report[name] = {}
                pg.goto(web + "/index.html")
                pg.screenshot(path=str(OUT / f"main_{name}.png"))
                pg.goto(web + "/index.html#example")
                pg.screenshot(path=str(OUT / f"example_{name}.png"), full_page=True)
                pg.goto(web + "/consult.html")
                pg.fill("#api", api)
                pg.screenshot(path=str(OUT / f"input_{name}.png"), full_page=True)
                r["form_height"] = pg.evaluate("document.getElementById('f').offsetHeight")
                for scene, kind, q in (("y1", "year", "2030년 재물과 직업·승진운이 궁금합니다"), ("y5", "r5", "앞으로 5년의 흐름이 궁금합니다"), ("y10", "r10", "앞으로 10년의 큰 흐름이 궁금합니다")):
                    analyze(pg, kind, q)
                    pg.screenshot(path=str(OUT / f"{scene}_{name}.png"), full_page=True)
                    r[scene] = {"overflow": overflow(pg), "page_height": pg.evaluate("document.documentElement.scrollHeight"),
                                "first_screen_h2": pg.evaluate("document.querySelector('#keypoints').offsetHeight"),
                                "folds_closed": pg.locator("#more details.fold[open]").count() == 0, "form_hidden": pg.is_hidden("#f"), "formbar": pg.is_visible("#formbar")}
                    if scene == "y5":
                        # 연도별 한 줄 → 연도 자세히 펼침/접힘 동작
                        yd = pg.locator("#keypoints details.yd").first
                        yd.locator("summary").click()
                        r["year_detail_opens"] = yd.evaluate("e=>e.open")
                        yd.locator("summary").click()
                        r["year_detail_closes"] = not yd.evaluate("e=>e.open")
                    if scene == "y1":
                        pg.fill("#q2", "사업 쪽은 어떻게 보이나요?")
                        pg.click("#askb")
                        pg.wait_for_function("document.querySelectorAll('#out .record').length>=1")
                        pg.locator("#out .record").first.screenshot(path=str(OUT / f"record_{name}.png"))
                        pg.locator("#session").screenshot(path=str(OUT / f"session_{name}.png"))
                        # 분야별 상세 펼침
                        pg.locator("#more details.fold >> nth=2").locator("summary").click()
                        pg.locator("#more details.fold >> nth=2").screenshot(path=str(OUT / f"domains_{name}.png"))
                        # 근거 상세 펼침(대운·세운 표, 고전 근거 포함 전부)
                        pg.evaluate("document.querySelectorAll('#more details').forEach(d=>d.open=true)")
                        pg.locator("#more").screenshot(path=str(OUT / f"evidence_{name}.png"))
                        r["evidence_overflow"] = overflow(pg)
                        # 표(한자·구간)가 가로로 넘치지 않거나 표 래퍼 안에서만 스크롤되는지
                        r["table_wrap_ok"] = pg.evaluate("[...document.querySelectorAll('#more table')].every(t=>t.closest('.tw'))")
                        pg.evaluate("document.querySelectorAll('#more details').forEach(d=>d.open=false)")
                # 입력 수정
                pg.click("#formedit")
                pg.screenshot(path=str(OUT / f"edit_{name}.png"))
                r["edit_form_visible"] = pg.is_visible("#f") and pg.is_hidden("#formbar")
                print(name, json.dumps(r, ensure_ascii=False))
                ctx.close()
            b.close()
    finally:
        for p in (pa, pw_):
            p.terminate()
    (OUT / "capture_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved to", OUT)


if __name__ == "__main__":
    main()
