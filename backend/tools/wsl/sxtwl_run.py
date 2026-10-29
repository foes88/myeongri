"""WSL(Linux) 전용: sxtwl 2.0.7 로 절기 시각과 간지를 계산한다. 서비스 코드가 아니다.
사용: ~/sxvenv/bin/python sxtwl_run.py <input.json> <output.json>
sxtwl 은 寿星万年历(허수성) 계열 알고리즘이며 lunar-python 과 같은 계열일 가능성이 있다(독립성은 별도 평가).
"""
import json
import sys

import sxtwl

GAN, ZHI = "甲乙丙丁戊己庚辛壬癸", "子丑寅卯辰巳午未申酉戌亥"
gz = lambda g: GAN[g.tg] + ZHI[g.dz]


def t2jd(Y, M, D, h, m, s):
    T = sxtwl.Time()
    T.Y, T.M, T.D, T.h, T.m, T.s = Y, M, D, h, m, s
    return sxtwl.toJD(T)


def day_after(d, n=1):
    return d.after(n)


def pillars(item):
    y, m, d, h, mi, s = item["bj"]
    day = sxtwl.fromSolar(y, m, d)
    jd = t2jd(y, m, d, h, mi, s)
    ref = day
    if day.hasJieQi() and day.getJieQi() % 2 == 1 and jd < day.getJieQiJD():  # 절(節)일 당일 절입 이전 → 전날 월주
        prev = day.before(1)
        yp = prev.getYearGZ()
        mp = prev.getMonthGZ()
    else:
        yp, mp = day.getYearGZ(), day.getMonthGZ()
    cy, cm, cd, ch, cmi, cs = item["clock"]
    cday = sxtwl.fromSolar(cy, cm, cd)
    dayp = cday.after(1) if (ch >= 23 and item["zi"] == "ZI_2300_DAY_CHANGE") else cday
    out = {"year": gz(yp), "month": gz(mp), "day": gz(dayp.getDayGZ())}
    if ch < 23:
        out["hour"] = gz(cday.getHourGZ(ch))
    return out


def main():
    inp = json.load(open(sys.argv[1], encoding="utf-8"))
    res = {"version": "sxtwl 2.0.7", "terms": {}, "cases": {}}
    for y in range(1901, 2051):
        rows = []
        for x in sxtwl.getJieQiByYear(y):
            T = sxtwl.JD2DD(x.jd)
            rows.append([x.jqIndex, T.Y, T.M, T.D, T.h, T.m, T.s])
        res["terms"][y] = rows
    for it in inp["items"]:
        res["cases"][it["id"]] = pillars(it)
    json.dump(res, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)


main()
