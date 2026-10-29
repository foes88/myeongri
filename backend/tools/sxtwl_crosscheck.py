"""sxtwl(WSL) 독립 검산. prepare → (WSL 실행) → compare.  python -m tools.sxtwl_crosscheck prepare|compare"""
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from app.astro_core import ephemeris as eph

G = Path(__file__).resolve().parents[1] / "golden"
KST, BJ = ZoneInfo("Asia/Seoul"), timezone(timedelta(hours=8))
CATS = ("GEN", "TERM", "ZI", "SOLAR")
SX_TO_K = None  # sxtwl 절기 index(0=冬至) → skyfield index(0=春分): sx 3=立春=skyfield 21


def prepare():
    cases = json.loads((G / "cases.json").read_text(encoding="utf-8"))["cases"]
    items = []
    for c in cases:
        if c["category"] not in CATS:
            continue
        i = c["input"]
        naive = datetime(i["year"], i["month"], i["day"], i["hour"], i["minute"])
        bj = naive.replace(tzinfo=KST).astimezone(BJ)
        clock = datetime.fromisoformat(c["expect"]["pillar_time"]) if "pillar_time" in c["expect"] else naive
        items.append({"id": c["test_id"], "bj": [bj.year, bj.month, bj.day, bj.hour, bj.minute, bj.second],
                      "clock": [clock.year, clock.month, clock.day, clock.hour, clock.minute, clock.second], "zi": c["profile"]["zi_profile"]})
    (G / "_wsl").mkdir(exist_ok=True)
    (G / "_wsl" / "sx_input.json").write_text(json.dumps({"items": items}), encoding="utf-8")
    print(len(items), "items")


def run_wsl():
    cmd = ["wsl", "-d", "Ubuntu", "--", "/home/lou/sxvenv/bin/python", "/mnt/c/dev/myeongri/backend/tools/wsl/sxtwl_run.py",
           "/mnt/c/dev/myeongri/backend/golden/_wsl/sx_input.json", "/mnt/c/dev/myeongri/backend/golden/_wsl/sx_output.json"]
    subprocess.run(cmd, check=True, env={**__import__("os").environ, "MSYS_NO_PATHCONV": "1"})


def compare():
    out = json.loads((G / "_wsl" / "sx_output.json").read_text(encoding="utf-8"))
    cases = {c["test_id"]: c for c in json.loads((G / "cases.json").read_text(encoding="utf-8"))["cases"]}
    # 1) 절기 시각: sxtwl(북경시) vs Skyfield
    diffs, worst = [], (0, None)
    for ys, rows in out["terms"].items():
        y = int(ys)
        ours = [(t, k) for t, k in eph.solar_terms_in_utc_year(y)]
        for idx, Y, M, D, h, m, s in rows:
            t = datetime(int(Y), int(M), int(D), int(h), int(m), int(s), tzinfo=BJ) + timedelta(seconds=s - int(s))
            near = min(ours, key=lambda o: abs((o[0] - t).total_seconds()), default=None)
            if near is None:
                continue
            d = (near[0] - t).total_seconds()
            if abs(d) < 86400 * 3:
                diffs.append(abs(d))
                if abs(d) > worst[0]:
                    worst = (abs(d), (y, idx))
    # 2) 간지: sxtwl vs 골든 기대값(lunar-python)
    agree = dis = 0
    dis_rows = []
    for cid, p in out["cases"].items():
        exp = cases[cid]["expect"].get("pillars", {})
        for k, v in p.items():
            if k in exp:
                if exp[k] == v:
                    agree += 1
                else:
                    dis += 1
                    dis_rows.append({"id": cid, "field": k, "sxtwl": v, "lunar_python": exp[k]})
    rep = {"sxtwl_version": out["version"], "terms_compared": len(diffs), "terms_max_abs_s_vs_skyfield": max(diffs), "terms_mean_abs_s": sum(diffs) / len(diffs),
           "worst": worst, "pillar_fields_agree_with_lunar_python": agree, "pillar_fields_disagree": dis, "disagreements": dis_rows}
    (G / "sxtwl_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print({k: v for k, v in rep.items() if k != "disagreements"}, dis_rows[:6])


if __name__ == "__main__":
    {"prepare": prepare, "compare": lambda: (run_wsl(), compare()), "run": run_wsl, "cmp": compare}[sys.argv[1]]()
