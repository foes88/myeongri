"""web/src 의 템플릿과 상담 데이터로 web/index.html 을 만든다.

사실표(analysis)는 backend.app.chart_analysis 가 간지에서 재계산해 주입하므로 손으로 고치지 않는다.
사용: python scripts/build_web.py [--check]   (--check: 파일을 바꾸지 않고 최신 여부만 확인)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.chart_analysis import analyze_chart  # noqa: E402


def build_html() -> str:
    report = json.loads((ROOT / "web/src/sample_report.json").read_text(encoding="utf-8"))
    pillars = {k: v["stem"] + v["branch"] for k, v in report["chart"]["pillars"].items()}
    report["analysis"] = analyze_chart(pillars)
    blob = json.dumps(report, ensure_ascii=False, indent=1).replace("</", "<\\/")
    tpl = (ROOT / "web/src/template.html").read_text(encoding="utf-8")
    return tpl.replace("__REPORT_JSON__", blob)


if __name__ == "__main__":
    out = ROOT / "web/index.html"
    html = build_html()
    if "--check" in sys.argv:
        sys.exit(0 if out.exists() and out.read_text(encoding="utf-8") == html else 1)
    out.write_text(html, encoding="utf-8", newline="\n")
    print(f"wrote {out} ({len(html)} chars)")
