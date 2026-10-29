"""천문 유도 음력 vs HKO(UTC+8) vs korean_lunar_calendar(UTC+9 기준) vs KASI 달력자료. 실행: python -m tools.check_lunar"""
import json
from pathlib import Path

from korean_lunar_calendar import KoreanLunarCalendar

from tools.lunar_astro import lunar_year_months

G = Path(__file__).resolve().parents[1] / "golden"
from tools.paths import HKO_FILE, KASI_FILE
HKO = json.loads(HKO_FILE.read_text(encoding="utf-8"))["lunar"]
KASI = json.loads(KASI_FILE.read_text(encoding="utf-8"))["years"]


def klc_month_starts(Y):
    out = {}
    for m in range(1, 13):
        for leap in (False, True):
            c = KoreanLunarCalendar()
            if c.setLunarDate(Y, m, 1, leap):
                out[f"{c.solarYear:04d}-{c.solarMonth:02d}-{c.solarDay:02d}"] = (m, leap)
    return out


def hko_starts(Y):
    return {d: (m, lp) for d, m, lp in HKO[str(Y)]["months"]}


def derived_lunar_year(Y, hours):
    ms = lunar_year_months(Y, hours)
    first = next(i for i, m in enumerate(ms) if m[0] == 1 and not m[1])
    return {m[2].isoformat(): (m[0], m[1]) for m in ms[first:]}


def klc_lunar_year(Y):
    return {d: v for d, v in klc_month_starts(Y).items()}


def main():
    res = {"hko_vs_derived8_mismatch_years": [], "klc_vs_derived9_mismatch_years": [], "kasi_vs_klc": {}, "kasi_vs_derived9": {}, "detail_focus": {}}
    for Y in range(1963, 2050):
        d8 = {m[2].isoformat(): (m[0], m[1]) for m in lunar_year_months(Y, 8) if m[2].year == Y}
        d9 = derived_lunar_year(Y, 9)
        h = {d: v for d, v in hko_starts(Y).items() if d.startswith(str(Y))}
        k = klc_lunar_year(Y)
        if d8 != h:
            res["hko_vs_derived8_mismatch_years"].append(Y)
        if d9 != k:
            res["klc_vs_derived9_mismatch_years"].append(Y)
        if Y in (2001, 2012, 2017):
            res["detail_focus"][Y] = {"derived_kst_leap": [d for d, v in d9.items() if v[1]], "klc_leap": [d for d, v in k.items() if v[1]],
                                      "hko_leap": [d for d, v in h.items() if v[1]], "derived_cst_leap": [d for d, v in d8.items() if v[1]]}
    for ys, v in KASI.items():
        if not v["months"]:
            continue
        Y = int(ys)
        ks = {m["solar"]: (m["lunar_month"], m["is_leap"]) for m in v["months"]}
        res["kasi_vs_klc"][Y] = ks == klc_lunar_year(Y)
        res["kasi_vs_derived9"][Y] = ks == derived_lunar_year(Y, 9)
    (G / "lunar_check.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, default=str)[:2500])


main()
