"""운영 주소 점검(가상 입력만 사용): 일회성 분석 흐름, 네트워크 요청, 콘솔 오류, 저장소 사용, 반응형 캡처. 실행: python -m tools.check_production [URL]"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = (sys.argv[1] if len(sys.argv) > 1 else "https://myeongri-tau.vercel.app").rstrip("/")
OUT = Path(__file__).resolve().parents[1] / "data_private" / "production"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    res = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for size, (w, h) in {"360": (360, 800), "768": (768, 1024), "1440": (1440, 900)}.items():
            ctx = b.new_context(viewport={"width": w, "height": h})
            p = ctx.new_page()
            reqs, console = [], []
            p.on("request", lambda r: reqs.append((r.method, r.url)))
            p.on("console", lambda m: console.append(f"{m.type}: {m.text}"))
            p.on("pageerror", lambda e: console.append("PAGEERROR " + str(e)))
            p.goto(URL + "/")
            p.screenshot(path=str(OUT / f"main_{size}.png"))
            p.goto(URL + "/consult")
            assert p.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), "overflow input " + size
            p.screenshot(path=str(OUT / f"input_{size}.png"), full_page=True)
            p.fill("#date", "1984-06-15")  # 가상 입력
            p.fill("#time", "10:00")
            p.fill("#q", "2030년 재물과 직업의 흐름이 궁금합니다")
            for cb in p.query_selector_all("#doms input"):
                want = cb.get_attribute("value") in ("overall", "wealth", "career")
                if cb.is_checked() != want:
                    cb.set_checked(want)
            p.click("#f button[type=submit]")
            p.wait_for_selector("#session:not([hidden])", timeout=60000)
            assert p.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), "overflow result " + size
            p.screenshot(path=str(OUT / f"result_{size}.png"), full_page=True)
            p.fill("#q2", "사업 쪽은 어떻게 보이나요?")
            p.click("#askb")
            p.wait_for_selector("#out .record")
            p.screenshot(path=str(OUT / f"record_{size}.png"), full_page=True)
            api = [(m, u) for m, u in reqs if "/api/" in u]
            res[size] = {"api_calls": [f"{m} {u.replace(URL, '')}" for m, u in api], "console_problems": [c for c in console if c.startswith(("error", "PAGEERROR", "warning"))],
                         "localStorage": p.evaluate("Object.keys(localStorage)"), "sessionStorage": p.evaluate("Object.keys(sessionStorage)"), "cookie": p.evaluate("document.cookie"),
                         "has_token_or_thread_text": "상담 번호" in p.inner_text("#cover"), "banner": p.inner_text("#staticbanner")[:30]}
            ctx.close()
        b.close()
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
