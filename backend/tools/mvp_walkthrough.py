"""MVP 실사용 점검(로컬, 가상 입력): 서버(Postgres 연결 가능)를 띄우고 사람이 쓰는 순서대로 따라가며 화면·응답 시간·오류를 기록한다.
흐름: 첫 화면 → 분석 시작 → 입력(출생지 선택) → 분석 → 결과 → 다음 해 → 5년 → 후속 질문 → 회원 가입·저장 → 새로고침 후 재열람 → 로그아웃.
실행: python -m tools.mvp_walkthrough [--pg postgresql://…]   결과: data_private/mvp/ (PNG + report.json, gitignored)"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BACKEND = Path(__file__).resolve().parents[1]
WEB = BACKEND.parent / "web"
OUT = BACKEND / "data_private" / "mvp"
SIZES = {"360": (360, 800), "1440": (1440, 900)}


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
        except Exception:
            time.sleep(0.3)
    raise RuntimeError(url)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pg", default=os.environ.get("DATABASE_URL"))
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    d = Path(tempfile.mkdtemp())
    shutil.copytree(WEB, d / "web", ignore=shutil.ignore_patterns("src"))
    port = free_port()
    env = dict(os.environ, SERVE_WEB=str(d / "web"), PYTHONIOENCODING="utf-8", APP_DB=str(d / "app.sqlite3"))
    if a.pg:
        env["DATABASE_URL"] = a.pg
        env["DATABASE_SCHEMA"] = "walk_" + os.urandom(4).hex()
    srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--host", "127.0.0.1", "--log-level", "warning"], cwd=BACKEND, env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    rep = {"base": base, "db": "postgres" if a.pg else "sqlite", "sizes": {}}
    try:
        wait(base + "/api/v1/health")
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            for name, (w, h) in SIZES.items():
                ctx = b.new_context(viewport={"width": w, "height": h})
                p = ctx.new_page()
                probs, api_ms = [], {}
                p.on("console", lambda m: probs.append(f"console {m.type}: {m.text}") if m.type in ("error", "warning") else None)
                p.on("pageerror", lambda e: probs.append("pageerror " + str(e)))
                p.on("requestfailed", lambda r: probs.append("requestfailed " + r.url))
                t = {}

                def timed(resp):
                    if "/api/" in resp.url:
                        api_ms.setdefault(resp.url.replace(base, "") + f" [{resp.status}]", []).append(round(resp.request.timing["responseEnd"]) if resp.request.timing else None)
                p.on("response", timed)
                r = rep["sizes"][name] = {}
                p.goto(base + "/index.html")
                p.screenshot(path=str(OUT / f"01_landing_{name}.png"))
                p.click("a.btn:has-text('분석 시작')")
                p.wait_for_selector("#date")
                r["first_screen_form_visible"] = p.is_visible("#date") and p.is_visible("#submitb")
                r["advanced_closed"] = not p.evaluate("document.getElementById('adv').open")
                p.screenshot(path=str(OUT / f"02_form_{name}.png"))
                p.select_option("#place", "경기도 수원시")
                p.fill("#date", "1984-06-15")  # 가상 입력
                p.fill("#time", "10:00")
                for cb in p.query_selector_all("#doms input"):
                    want = cb.get_attribute("value") in ("overall", "wealth", "career")
                    if cb.is_checked() != want:
                        cb.set_checked(want)
                t0 = time.time()
                p.click("#submitb")
                p.wait_for_selector("#formbar:not([hidden])", timeout=60000)
                r["analysis_seconds"] = round(time.time() - t0, 2)
                p.screenshot(path=str(OUT / f"03_result_{name}.png"), full_page=True)
                r["overflow"] = p.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                r["first_screen_chars"] = len(p.inner_text("#verdict"))
                r["no_accordion_open"] = p.locator("#verdict details[open]").count() == 0 and p.locator("details.fold").count() == 0
                t0 = time.time()
                p.click("#ynext")
                p.wait_for_function("document.getElementById('formsum').textContent.includes('2031')", timeout=60000)
                r["year_switch_seconds"] = round(time.time() - t0, 2)
                p.click("#to5")
                p.wait_for_selector("#verdict .vperiod", timeout=60000)
                p.screenshot(path=str(OUT / f"04_5years_{name}.png"), full_page=True)
                p.fill("#q2", "사업 쪽은 어떻게 보이나요?")
                t0 = time.time()
                p.click("#askb")
                p.wait_for_selector("#out .record")
                r["follow_up_seconds"] = round(time.time() - t0, 2)
                p.locator("#out .record").first.screenshot(path=str(OUT / f"05_followup_{name}.png"))
                if p.is_visible("#acct"):
                    p.fill("#acct-mail", f"walk-{name}-{os.urandom(3).hex()}@example.com")
                    p.fill("#acct-pw", "walkthrough-pass-9")
                    p.click("#acct-reg")
                    p.wait_for_selector("#acct-in:not([hidden])")
                    p.click("#formedit")
                    p.click("#submitb")
                    p.wait_for_selector("#mylist li button:has-text('열기')", timeout=60000)
                    p.screenshot(path=str(OUT / f"06_saved_{name}.png"))
                    p.reload()
                    p.wait_for_selector("#mylist li button:has-text('열기')")
                    p.click("#mylist li button:has-text('열기')")
                    p.wait_for_selector("#verdict", timeout=30000)
                    r["reopen_ok"] = "다시 열었습니다" in p.inner_text("#cover")
                    p.screenshot(path=str(OUT / f"07_reopened_{name}.png"), full_page=True)
                    p.click("#acct-logout")
                    p.wait_for_selector("#acct-out:not([hidden])")
                    r["logout_clears_screen"] = p.is_hidden("#report") and p.inner_text("#out") == ""
                else:
                    r["member_panel"] = "숨김(회원 기능 비활성)"
                r["problems"] = probs
                r["storage_keys"] = p.evaluate("Object.keys(localStorage).concat(Object.keys(sessionStorage))")
                ctx.close()
            b.close()
    finally:
        srv.terminate()
        if a.pg:
            try:
                from app.accounts.pg_repo import PostgresRepo
                PostgresRepo(a.pg, schema=env["DATABASE_SCHEMA"]).drop_schema()
            except Exception as e:  # noqa
                print("schema cleanup failed:", e)
    (OUT / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
