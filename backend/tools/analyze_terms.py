"""절기 시각 오차 분석: Skyfield(DE421) vs lunar-python(전 구간) vs HKO(2026~28 분 단위, 1901~2050 날짜 단위).
실행: python -m tools.analyze_terms  → golden/term_analysis.json
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean

from lunar_python import Solar

from app.astro_core import ephemeris as eph

G = Path(__file__).resolve().parents[1] / "golden"
HKT = timezone(timedelta(hours=8))
HKO = json.loads((G / "sources" / "hko_lunar_terms.json").read_text(encoding="utf-8"))


def lp_times(y):
    out = []
    for o in Solar.fromYmd(y, 6, 1).getLunar().getJieQiTable().values():
        out.append(datetime(o.getYear(), o.getMonth(), o.getDay(), o.getHour(), o.getMinute(), o.getSecond(), tzinfo=HKT))
    return out


def main():
    diffs = []  # (year, k, seconds ours - lp)
    for y in range(1902, 2050):
        others = lp_times(y)
        for t, k in eph.solar_terms_in_utc_year(y):
            o = min(others, key=lambda x: abs((t - x).total_seconds()))
            diffs.append((y, k, (t - o).total_seconds()))
    ad = [abs(d) for _, _, d in diffs]
    by_decade = {}
    for y, k, d in diffs:
        by_decade.setdefault(y // 10 * 10, []).append(d)
    worst = max(diffs, key=lambda x: abs(x[2]))
    # HKO 분 단위 (2026~2028)
    hm = []
    for ys, rows in HKO["terms_hm"].items():
        y = int(ys)
        ev = sorted(eph.solar_terms_in_utc_year(y))
        # HKO 24개 행은 소한부터 대한...동지 순서. 우리 이벤트도 같은 해의 시간순 24개
        for (t, k), (mo, d, h, mi) in zip(ev, rows):
            ref = datetime(y, mo, d, h, mi, tzinfo=HKT)
            hm.append({"year": y, "term_index": k, "diff_seconds": (t - ref).total_seconds()})
    # HKO 날짜 단위 (1901~2050): HKT 달력일 일치
    date_miss = []
    for ys, v in HKO["lunar"].items():
        y = int(ys)
        ev = sorted(eph.solar_terms_in_utc_year(y))
        # HKT 기준 해가 다를 수 있어 날짜로 매칭
        ours = {t.astimezone(HKT).date().isoformat() for t, _ in ev}
        for dstr, name in v["terms"]:
            if dstr not in ours:
                # 가장 가까운 우리 절기 시각의 HKT 자정 거리
                near = min(ev, key=lambda e: abs((e[0].astimezone(HKT).replace(hour=0, minute=0, second=0, microsecond=0)
                                                  - datetime.fromisoformat(dstr).replace(tzinfo=HKT)).total_seconds()))
                date_miss.append({"year": y, "hko_date": dstr, "name": name, "ours_hkt": near[0].astimezone(HKT).isoformat()})
    out = {
        "vs_lunar_python": {"n": len(ad), "max_s": max(ad), "mean_s": mean(ad), "worst": {"year": worst[0], "k": worst[1], "diff_s": worst[2]},
                            "mean_signed_s_by_decade": {str(k): round(mean(v), 1) for k, v in sorted(by_decade.items())},
                            "max_abs_s_by_decade": {str(k): round(max(abs(x) for x in v), 1) for k, v in sorted(by_decade.items())},
                            "n_over_10s": sum(a > 10 for a in ad), "n_over_30s": sum(a > 30 for a in ad)},
        "vs_hko_minutes_2026_2028": {"n": len(hm), "max_abs_s": max(abs(r["diff_seconds"]) for r in hm),
                                     "within_60s": sum(abs(r["diff_seconds"]) <= 60 for r in hm), "rows": hm},
        "vs_hko_date_1901_2050": {"hko_terms": sum(len(v["terms"]) for v in HKO["lunar"].values()), "date_mismatches": date_miss},
    }
    (G / "term_analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "rows"} for k, v in out.items()}, ensure_ascii=False, indent=1)[:3500])


main()
