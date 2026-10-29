"""HKO 공개 자료(음양력 변환표 1901~2050, 24절기 시각 2026~2028)를 내려받아 '사실'만 추출해 저장한다.
원문 페이지 전체는 저장하지 않는다(저작권/이용조건 미확인). 실행: python -m tools.fetch_hko
"""
import hashlib, json, re, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.request import urlopen

from tools.paths import EXTERNAL as OUT
LUNAR_URL = "https://www.hko.gov.hk/en/gts/time/calendar/text/files/T{y}e.txt"
TERM_URL = "https://www.hko.gov.hk/en/gts/astronomy/data/files/24SolarTerms_{y}.xml"
ORD = {"1st": 1, "2nd": 2, "3rd": 3}


def get(url):
    with urlopen(url, timeout=30) as r:
        return r.read()


def parse_lunar(y):
    raw = get(LUNAR_URL.format(y=y))
    months, terms, prev = [], [], None
    for line in raw.decode("latin1").splitlines():
        m = re.match(r"(\d{4})/(\d+)/(\d+)\s+(\S.*?)\s{2,}(\w+day)\s*(.*)$", line)
        if not m:
            continue
        d = date(int(m[1]), int(m[2]), int(m[3])).isoformat()
        mm = re.match(r"(\d+)(?:st|nd|rd|th) Lunar Month", m[4], re.I)
        if mm:
            n = int(mm[1])
            months.append([d, n, n == prev])  # 같은 달 번호가 연속 두 번이면 뒤쪽이 윤달
            prev = n
        if m[6].strip():
            terms.append([d, m[6].strip()])
    return y, {"months": months, "terms": terms}, hashlib.sha256(raw).hexdigest()


def parse_terms(y):
    raw = get(TERM_URL.format(y=y))
    rows = re.findall(rb"<M>(\d+)</M>\s*<D>(\d+)</D>\s*<hm>(\d+):(\d+)</hm>", raw)
    return y, [[int(a), int(b), int(c), int(d)] for a, b, c, d in rows], hashlib.sha256(raw).hexdigest()


if __name__ == "__main__":
    with ThreadPoolExecutor(8) as ex:
        lunar = list(ex.map(parse_lunar, range(1901, 2051)))
        terms = list(ex.map(parse_terms, (2026, 2027, 2028)))
    meta = {"accessed": datetime.now(timezone.utc).date().isoformat(), "lunar_url": LUNAR_URL, "term_url": TERM_URL,
            "lunar_sha256": {y: h for y, _, h in lunar}, "term_sha256": {y: h for y, _, h in terms},
            "time_zone_of_terms": "HKT (UTC+8)", "term_time_resolution": "minute"}
    (OUT / "hko_lunar_terms.json").write_text(json.dumps({"meta": meta, "lunar": {y: d for y, d, _ in lunar},
                                                          "terms_hm": {y: d for y, d, _ in terms}}, ensure_ascii=False), encoding="utf-8")
    bad = [y for y, d, _ in lunar if not d["months"] or len(d["terms"]) != 24] + [y for y, d, _ in terms if len(d) != 24]
    print("done; years with parse problems:", bad)
