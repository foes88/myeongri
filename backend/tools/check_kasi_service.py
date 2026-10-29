"""KASI 웹 음양력 변환 서비스(/life/solc, /life/lunc) 응답과 우리 엔진·라이브러리를 대조한다.
- 월력요항 PDF/HWP 가 아니라 KASI 웹 서비스의 응답이다(공식 사이트 제공, 이용 조건 미확인). 요청 수를 제한하고 간격을 둔다.
- 응답 원문은 data_private/external/kasi_service.json 에만 저장(gitignored). 공개 집계는 golden/kasi_service_check.json
실행: python -m tools.check_kasi_service
"""
import json
import random
import re
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta

from korean_lunar_calendar import KoreanLunarCalendar

from app.astro_core import calculate_chart, engine
from tools.paths import EXTERNAL, GOLDEN

BASE = "https://astro.kasi.re.kr"
CACHE = EXTERNAL / "kasi_service.json"
cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
calls = 0


def q(path, **kw):
    global calls
    key = path + "?" + urllib.parse.urlencode(sorted(kw.items()))
    if key not in cache:
        time.sleep(0.2)
        calls += 1
        raw = urllib.request.urlopen(f"{BASE}{path}?{urllib.parse.urlencode(kw)}", timeout=30).read().decode("utf-8")
        cache[key] = json.loads(raw) if raw.strip() else None
    return cache[key]


def hanja(s):
    m = re.search(r"\((.{2})\)", s or "")
    return m[1] if m else None


def solc(d):
    return q("/life/solc", yyyy=d.year, mm=f"{d.month:02d}", dd=f"{d.day:02d}")


def lunc(y, m, d=1):
    r = q("/life/lunc", yyyy=y, mm=f"{m:02d}", dd=f"{d:02d}")
    return r if isinstance(r, list) else ([r] if r else [])


def klc_start(y, m, leap):
    c = KoreanLunarCalendar()
    return date(c.solarYear, c.solarMonth, c.solarDay) if c.setLunarDate(y, m, 1, leap) else None


def main():
    res = {"focus_cases": {}, "newyear_checked": 0, "newyear_mismatch": [], "leap_checked": 0, "leap_mismatch": [], "day_pillar_checked": 0,
           "day_pillar_mismatch": [], "range": [1901, 2050]}
    # 1) 불일치 5건: 공식 서비스 응답
    for tag, d in (("2001-04-24", date(2001, 4, 24)), ("2001-04-23", date(2001, 4, 23)), ("2012-04-21", date(2012, 4, 21)), ("2012-05-21", date(2012, 5, 21)),
                   ("2017-06-24", date(2017, 6, 24)), ("2017-07-23", date(2017, 7, 23))):
        r = solc(d)
        res["focus_cases"][tag] = {"lunar": f"{r['LUNC_YYYY']}-{'윤' if r['LUNC_LEAP_MM'] == '윤' else ''}{r['LUNC_MM']}-{r['LUNC_DD']}", "iljin": hanja(r["LUNC_ILJIN"])}
    # 2) 음력 1월 1일(설날): 1901~2050 전 구간
    for y in range(1901, 2051):
        k = klc_start(y, 1, False)
        r = lunc(y, 1, 1)
        res["newyear_checked"] += 1
        got = {date(int(x["SOLC_YYYY"]), int(x["SOLC_MM"]), int(x["SOLC_DD"])) for x in r if x["LUNC_LEAP_MM"] != "윤"}
        if k not in got:
            res["newyear_mismatch"].append([y, str(k), sorted(map(str, got))])
    # 3) 윤달: 한국 라이브러리가 윤달이라고 하는 달 + 서비스가 그 달에 윤달을 반환하는지(전 구간)
    for y in range(1901, 2051):
        for m in range(1, 13):
            k = klc_start(y, m, True)
            if k is None:
                continue
            r = [x for x in lunc(y, m, 1) if x["LUNC_LEAP_MM"] == "윤"]
            res["leap_checked"] += 1
            got = {date(int(x["SOLC_YYYY"]), int(x["SOLC_MM"]), int(x["SOLC_DD"])) for x in r}
            if k not in got:
                res["leap_mismatch"].append([y, m, str(k), sorted(map(str, got))])
    # 4) 일주: 무작위 150일 — 엔진(정오, 시계 시각) vs KASI 일진
    rng = random.Random(65)
    for _ in range(150):
        d = date(1901, 1, 1) + timedelta(days=rng.randrange(0, 365 * 149))
        r = solc(d)
        ch = calculate_chart(year=d.year, month=d.month, day=d.day, hour=12, minute=0, gender="male").pillars["day"]
        res["day_pillar_checked"] += 1
        if hanja(r["LUNC_ILJIN"]) != ch:
            res["day_pillar_mismatch"].append([str(d), hanja(r["LUNC_ILJIN"]), ch])
    # 5) 연주: KASI 세차(LUNC_PRCN, 음력 설날 기준) vs 엔진 연주(입춘 기준). 설날·입춘이 모두 지난 3~12월 날짜만 비교 가능
    res["year_pillar_checked"], res["year_pillar_mismatch"] = 0, []
    for _ in range(100):
        d = date(1901, 3, 1) + timedelta(days=rng.randrange(0, 365 * 149))
        if d.month < 3:
            d = d.replace(month=3, day=min(d.day, 28))
        r = solc(d)
        yp = calculate_chart(year=d.year, month=d.month, day=d.day, hour=12, minute=0, gender="male").pillars["year"]
        res["year_pillar_checked"] += 1
        if hanja(r["LUNC_PRCN"]) != yp:
            res["year_pillar_mismatch"].append([str(d), hanja(r["LUNC_PRCN"]), yp])
    res["year_pillar_scope"] = "3~12월 날짜만(세차는 음력 설날 기준이라 1~2월은 입춘 기준 연주와 다를 수 있어 제외)"
    res["requests_this_run"] = calls
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    (GOLDEN / "kasi_service_check.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False)[:2500])


main()
