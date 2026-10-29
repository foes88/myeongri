"""KASI 월력요항(2004~2017 inline 표)과 우리 계산·라이브러리 대조. 실행: python -m tools.check_kasi_almanac → golden/kasi_official_check.json (집계만 공개)"""
import json
from datetime import datetime, timedelta, timezone

from korean_lunar_calendar import KoreanLunarCalendar

from app.astro_core import ephemeris as eph
from tools.lunar_astro import lunar_year_months, new_moons
from tools.paths import EXTERNAL, GOLDEN, HKO_FILE

KAL = json.loads((EXTERNAL / "kasi_almanac.json").read_text(encoding="utf-8"))["years"]
HKO = json.loads(HKO_FILE.read_text(encoding="utf-8"))["lunar"] if HKO_FILE.exists() else {}
KST = timezone(timedelta(hours=9))


def klc_start(y, m, leap):
    c = KoreanLunarCalendar()
    return f"{c.solarYear:04d}-{c.solarMonth:02d}-{c.solarDay:02d}" if c.setLunarDate(y, m, 1, leap) else None


def main():
    res = {"years": [], "klc_vs_kasi_mismatch": [], "derived_kst_vs_kasi_mismatch": [], "hko_vs_kasi_mismatch_years": [],
           "newmoon_max_diff_minutes": 0.0, "newmoon_compared": 0, "terms_compared": 0, "terms_max_diff_s": 0.0, "months_compared": 0,
           "leap_months_official": {}}
    nms = [t.astimezone(KST) for t in new_moons(2003, 2019)]
    for ys, v in sorted(KAL.items()):
        y = int(ys)
        if not v["months"]:
            continue
        res["years"].append(y)
        kasi = {(m["lunar_month"], m["is_leap"]): m["new_moon_kst"] for m in v["months"] if m["lunar_year"] == y}
        # 우리 계산 vs KASI 월 시작일: KASI 의 합삭 시각의 KST 날짜 = 초하루
        for (mo, lp), nm in kasi.items():
            res["months_compared"] += 1
            kdate = nm[:10]
            if klc_start(y, mo, lp) != kdate:
                res["klc_vs_kasi_mismatch"].append([y, mo, lp])
            # 합삭 시각 차이 (분)
            t = datetime.fromisoformat(nm).replace(tzinfo=KST)
            near = min(nms, key=lambda x: abs((x - t).total_seconds()))
            d = abs((near - t).total_seconds()) / 60
            res["newmoon_compared"] += 1
            res["newmoon_max_diff_minutes"] = max(res["newmoon_max_diff_minutes"], d)
        lm = [m for m in v["months"] if m["is_leap"] and m["lunar_year"] == y]
        if lm:
            res["leap_months_official"][y] = {"month": lm[0]["lunar_month"], "start": lm[0]["new_moon_kst"][:10], "inferred": bool(lm[0].get("leap_inferred"))}
        d9 = {m[2].isoformat(): (m[0], m[1]) for m in lunar_year_months(y, 9) if m[2].year in (y, y + 1)}
        off = {m["new_moon_kst"][:10]: (m["lunar_month"], m["is_leap"]) for m in v["months"] if m["lunar_year"] == y}
        if any(d9.get(d) != x for d, x in off.items()):
            res["derived_kst_vs_kasi_mismatch"].append(y)
        if HKO:
            h = {d: (m, lp) for d, m, lp in HKO[str(y)]["months"]}
            hm = {d: x for d, x in off.items() if d.startswith(str(y))}
            if any(h.get(d) != x for d, x in hm.items()):
                res["hko_vs_kasi_mismatch_years"].append(y)
        ev = sorted(eph.solar_terms_in_utc_year(y))
        for i, t in enumerate(v["terms"]):
            if len(v["terms"]) != 24:
                break
            ref = datetime.fromisoformat(t["kst"]).replace(tzinfo=KST)
            diff = abs((ev[i][0] - ref).total_seconds())
            res["terms_compared"] += 1
            res["terms_max_diff_s"] = max(res["terms_max_diff_s"], diff)
    (GOLDEN / "kasi_official_check.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False)[:1800])


main()
