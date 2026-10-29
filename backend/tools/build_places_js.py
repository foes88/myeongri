"""app/places.py → web/assets/places.js (화면 출생지 목록; 단일 출처). 실행: python -m tools.build_places_js"""
import json
from pathlib import Path

from app.places import PROVINCES, SPECIAL

OUT = Path(__file__).resolve().parents[2] / "web" / "assets" / "places.js"
groups = [{"group": "특별시·광역시·특별자치시", "items": [[n, n] for n, _, _ in SPECIAL]}]
for prov, items in PROVINCES.items():
    groups.append({"group": prov, "items": [[n, f"{prov} {n}" if prov != "제주특별자치도" else f"{prov} {n}"] for n, _, _ in items]})
OUT.write_text("/* 자동 생성: python -m tools.build_places_js */\nwindow.MINGLI_PLACES=" + json.dumps(groups, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
print("wrote", OUT, sum(len(g["items"]) for g in groups), "places")
