"""골든 케이스 실행 → golden/report.json. 불일치는 삭제·완화하지 않고 그대로 기록한다.
실행: python -m tools.run_golden
"""
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.astro_core import DaeunProfile, TimeProfile, ZiProfile, calculate_chart
from app.astro_core import ephemeris as eph

from tools.paths import EXT_CASES, EXT_REPORT, EXT_TERM_ANALYSIS, GOLDEN as G
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


def run_all(cases, judge):
    results, by_cat, by_src, fails = [], defaultdict(Counter), defaultdict(Counter), []
    for c in cases:
        ok, detail = run_case(c)
        st = "PASS" if ok else ("MISMATCH_EXPLAINED" if c["test_id"] in judge else "FAIL")
        by_cat[c["category"]][st] += 1
        for ref in c["references"]:
            by_src[ref["tool"]][st] += 1
        results.append({"test_id": c["test_id"], "status": st, "detail": detail})
        if not ok:
            fails.append({"test_id": c["test_id"], "expect": c["expect"], "detail": detail, "input": c["input"],
                          "judgement": judge.get(c["test_id"], "UNEXPLAINED")})
    return results, by_cat, by_src, fails


def main():
    data = json.loads((G / "cases.json").read_text(encoding="utf-8"))
    sources = json.loads((G / "sources.json").read_text(encoding="utf-8"))
    results, by_cat, by_src, fails = run_all(data["cases"], JUDGE)
    ext = {"present": EXT_CASES.exists(), "total": 0, "categories": []}
    if EXT_CASES.exists():  # 비공개 외부 자료 파생 케이스: 집계만 공개 보고서에 반영하고 케이스별 결과는 비공개 파일에만 둔다
        ecases = json.loads(EXT_CASES.read_text(encoding="utf-8"))["cases"]
        eres, ecat, esrc, efails = run_all(ecases, JUDGE)
        EXT_REPORT.write_text(json.dumps({"results": eres, "failures": efails}, ensure_ascii=False, indent=1), encoding="utf-8")
        for k, v in ecat.items():
            by_cat[k] = v
        for k, v in esrc.items():
            by_src[k].update(v)
        fails += [dict(f, input="(비공개)", private=True) for f in efails]
        ext = {"present": True, "total": len(ecases), "categories": sorted(ecat)}
    # 절기 오차 분석: 공개본은 요약 수치만 (행 단위 HKO 파생 값은 비공개)
    analysis = json.loads((G / "term_analysis.json").read_text(encoding="utf-8"))
    report = {
        "generated": datetime.now(timezone.utc).isoformat(), "total": len(results), "total_with_external": len(results) + ext["total"],
        "external": dict(ext, note="외부 자료(HKO/KASI) 파생 케이스는 data_private/ 에 있어 공개 저장소에 없다. 이 집계는 로컬에서 tools.fetch_* 후 재현해야 한다."),
        "by_category": {k: dict(v) for k, v in by_cat.items()}, "by_source": {k: dict(v) for k, v in by_src.items()},
        "failures": fails, "results": results,
        "sources": {k: {"status": v["status"], "license": v.get("license")} for k, v in sources.items() if isinstance(v, dict)},
        "term_error": {"vs_lunar_python_max_s": analysis["vs_lunar_python"]["max_s"],
                       "vs_lunar_python_max_abs_s_by_decade": analysis["vs_lunar_python"]["max_abs_s_by_decade"],
                       "vs_hko_minutes_max_s": analysis["vs_hko_minutes_2026_2028"]["max_abs_s"],
                       "hko_date_mismatches": analysis["vs_hko_date_1901_2050"]["count"]},
    }
    (G / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(report["total"], "+", ext["total"], "external;", {k: dict(v) for k, v in by_cat.items()})
    for f in fails[:15]:
        print(f["test_id"], f["expect"], f["detail"])


if __name__ == "__main__":
    main()
