"""UI 캡처·측정 도구(개발용, 로컬 서버 전용). 임시 계정을 만들어 5개 폭에서 결과 화면을 캡처하고 지표를 JSON 으로 남긴 뒤 계정을 삭제한다.
사용: python -m tools.ux_capture --out data_private/ux/before [--base http://127.0.0.1:8765] [--years r5]
저장 위치는 gitignored(data_private). 파일명에 개인정보를 넣지 않는다. 입력값은 서버의 로컬 기본값 설정을 그대로 쓴다."""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import urllib.request as U
from pathlib import Path

WIDTHS = [(360, 800), (768, 1024), (1024, 768), (1440, 900), (1920, 1080)]
METRICS_JS = """() => {
  const out = document.querySelector('#out'); const r = out.getBoundingClientRect();
  const vis = [...document.querySelectorAll('#out *')].filter(e => e.offsetParent !== null);
  const text = (document.querySelector('#out').innerText || '');
  const concl = document.querySelector('#verdict .vprofile .verdict-a, #verdict .dash-conclusion .concl-text');
  const vw = document.documentElement.clientWidth;
  return {viewport_w: vw, page_height: document.documentElement.scrollHeight, out_width: Math.round(r.width), width_ratio: +(r.width / vw).toFixed(3),
          overflow_x: document.documentElement.scrollWidth > vw, visible_chars: text.replace(/\s+/g, '').length,
          sections: document.querySelectorAll('#verdict section').length, details_closed: document.querySelectorAll('#verdict details:not([open])').length,
          conclusion_top: concl ? Math.round(concl.getBoundingClientRect().top + scrollY) : null,
          conclusion_bottom: concl ? Math.round(concl.getBoundingClientRect().bottom + scrollY) : null}
}"""


def main(argv):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    ap.add_argument("--years", default="r5", choices=["year", "r5", "r10"])
    a = ap.parse_args(argv)
    key = Path.home() / ".myeongri" / "app_data_key.txt"
    os.environ.setdefault("APP_DATA_KEY", key.read_text().strip())
    os.environ.setdefault("DATABASE_URL", "postgresql://myeongri:local-dev-only@127.0.0.1:55498/myeongri")
    from tools import create_owner
    from playwright.sync_api import sync_playwright
    email, pw = "ux-" + secrets.token_hex(4) + "@example.com", "Aa1-" + secrets.token_urlsafe(12)
    create_owner.create(email, pw)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    res = {}
    try:
        with sync_playwright() as pw_:
            b = pw_.chromium.launch()
            for w, h in WIDTHS:
                p = b.new_page(viewport={"width": w, "height": h})
                p.goto(a.base + "/consult.html")
                p.fill("#acct-mail", email); p.fill("#acct-pw", pw); p.click("#acct-login"); p.wait_for_selector("#acct-in:not([hidden])")
                p.wait_for_function("document.getElementById('date').value!==''")
                p.select_option("#pk", a.years)
                for cb in p.query_selector_all("#doms input"):
                    want = cb.get_attribute("value") in ("overall", "wealth", "career", "love_marriage", "family")
                    if cb.is_checked() != want:
                        cb.set_checked(want)
                p.click("#f button[type=submit]")
                try:
                    p.wait_for_selector("#verdict", timeout=8000)
                except Exception:
                    vb = p.get_by_role("button", name=__import__("re").compile(r"^v1"))
                    if vb.count():
                        vb.first.click()
                    p.wait_for_selector("#verdict", timeout=60000)
                p.wait_for_timeout(400)
                res[str(w)] = p.evaluate(METRICS_JS)
                p.screenshot(path=str(out / f"result_{w}_full.png"), full_page=True)
                p.evaluate("document.querySelector('#out').scrollIntoView()")
                p.screenshot(path=str(out / f"result_{w}_fold.png"))
                if p.locator("#mylist li button:has-text('삭제')").count():
                    p.click("#mylist li button:has-text('삭제')"); p.wait_for_function("document.getElementById('acct-n').textContent==='0'")
                p.close()
            b.close()
    finally:
        def post(path, body, tok=None, m="POST"):
            h = {"Content-Type": "application/json"}
            if tok:
                h["Authorization"] = "Bearer " + tok
            return U.urlopen(U.Request(a.base + path, data=json.dumps(body).encode(), headers=h, method=m)).read()
        tok = json.loads(post("/api/v1/auth/login", {"email": email, "password": pw}))["token"]
        post("/api/v1/me", {"password": pw}, tok, "DELETE")
    (out / "metrics.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for w, m in res.items():
        print(w, m)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
