"""골든 케이스 실행 → golden/report.json. 불일치는 삭제·완화하지 않고 그대로 기록한다.
실행: python -m tools.run_golden
"""
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.astro_core import DaeunProfile, TimeProfile, ZiProfile, calculate_chart
from app.astro_core import ephemeris as eph

G = Path(__file__).resolve().parents[1] / "golden"
HKT = timezone(timedelta(hours=8))
JUDGE = json.loads((G / "judgements.json").read_text(encoding="utf-8"))["judgements"]
KW = {"calendar", "is_leap_month", "place", "gender", "year", "month", "day", "hour", "minute"}


def run_case(c):
    exp, prof, inp = c["expect"], c["profile"], c["input"]
    if c["category"] == "TERMTIME":
        y = inp["year"]
        ev = sorted(eph.solar_terms_in_utc_year(y))[inp["ordinal_in_year"]][0]
        mo, d, h, mi = exp["term_hkt"][1:]
        diff = (ev - datetime(y, mo, d, h, mi, tzinfo=HKT)).total_seconds()
        return abs(diff) <= 60, {"diff_seconds": diff}
    if c["category"] == "KASITERM":
        y = inp["year"]
        ev = sorted(eph.solar_terms_in_utc_year(y))[inp["ordinal_in_year"]][0]
        ref = datetime.fromisoformat(exp["term_kst"]).replace(tzinfo=timezone(timedelta(hours=9)))
        diff = (ev - ref).total_seconds()
        return abs(diff) <= 60, {"diff_seconds": diff}
    kw = {k: v for k, v in inp.items() if k in KW}
    kw["time_profile"] = TimeProfile(prof.get("time_profile", "CIVIL_TIME"))
    kw["zi_profile"] = ZiProfile(prof.get("zi_profile", "ZI_2300_DAY_CHANGE"))
    try:
        r = calculate_chart(**kw).to_dict()
    except ValueError as e:
        return ("error" in exp and exp["error"] in str(e)), {"raised": str(e)}
    if "error" in exp:
        return False, {"raised": None}
    detail = {}
    ok = True
    if "pillars" in exp:
        got = {p: r["pillars"].get(p) for p in exp["pillars"]}
        ok &= got == exp["pillars"]
        detail["got"] = got
    if "pillar_time" in exp:
        d = abs((datetime.fromisoformat(r["time_profile"]["pillar_time_local"]) - datetime.fromisoformat(exp["pillar_time"])).total_seconds())
        ok &= d <= 30
        detail["pillar_time_diff_s"] = d
    if "utc_offset_minutes" in exp:
        ok &= r["normalized"]["utc_offset_minutes"] == exp["utc_offset_minutes"]
        detail["got_offset"] = r["normalized"]["utc_offset_minutes"]
    if "solar_date" in exp:
        ok &= r["normalized"]["solar_date"] == exp["solar_date"]
        detail["got_solar_date"] = r["normalized"]["solar_date"]
    if "warning" in exp:
        ok &= any(exp["warning"] in w for w in r["warnings"])
    if "direction" in exp:
        s = r["daeun"]["start_age"]
        mine, ref = s["years"] * 360 + s["months"] * 30 + s["days"], sum(a * b for a, b in zip(exp["start_age"], (360, 30, 1)))
        ok &= r["daeun"]["direction"] == exp["direction"] and abs(mine - ref) <= 1
        detail.update(got_direction=r["daeun"]["direction"], start_day_diff=mine - ref)
    if "boundary_side" in exp:
        detail["ambiguous"] = bool(r["verification"].get("ambiguity", {}).get("ambiguous"))
    return bool(ok), detail


def main():
    data = json.loads((G / "cases.json").read_text(encoding="utf-8"))
    sources = json.loads((G / "sources.json").read_text(encoding="utf-8"))
    results, by_cat, by_src, fails = [], defaultdict(Counter), defaultdict(Counter), []
    for c in data["cases"]:
        ok, detail = run_case(c)
        st = "PASS" if ok else ("MISMATCH_EXPLAINED" if c["test_id"] in JUDGE else "FAIL")
        by_cat[c["category"]][st] += 1
        for ref in c["references"]:
            by_src[ref["tool"]][st] += 1
        results.append({"test_id": c["test_id"], "status": st, "detail": detail})
        if not ok:
            fails.append({"test_id": c["test_id"], "expect": c["expect"], "detail": detail, "input": c["input"],
                          "judgement": JUDGE.get(c["test_id"], "UNEXPLAINED")})
    analysis = json.loads((G / "term_analysis.json").read_text(encoding="utf-8"))
    report = {
        "generated": datetime.now(timezone.utc).isoformat(), "total": len(results),
        "by_category": {k: dict(v) for k, v in by_cat.items()}, "by_source": {k: dict(v) for k, v in by_src.items()},
        "failures": fails, "results": results,
        "sources": {k: {"status": v["status"], "license": v.get("license")} for k, v in sources.items() if isinstance(v, dict)},
        "term_error": {"vs_lunar_python_max_s": analysis["vs_lunar_python"]["max_s"],
                       "vs_lunar_python_max_abs_s_by_decade": analysis["vs_lunar_python"]["max_abs_s_by_decade"],
                       "vs_hko_minutes_max_s": analysis["vs_hko_minutes_2026_2028"]["max_abs_s"],
                       "hko_date_mismatches": len(analysis["vs_hko_date_1901_2050"]["date_mismatches"])},
    }
    (G / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(report["total"], {k: dict(v) for k, v in by_cat.items()})
    for f in fails[:15]:
        print(f["test_id"], f["expect"], f["detail"])


if __name__ == "__main__":
    main()
