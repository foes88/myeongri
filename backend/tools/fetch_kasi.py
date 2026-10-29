"""KASI 달력자료(2021~2028)에서 음력 월 시작일·대소·월건·일진·24절기 '사실'만 추출해 저장한다. 실행: python -m tools.fetch_kasi

주의
- 이 자료는 KASI 가 "공식 발표 자료가 아니다(월력요항이 공식)"라고 명시한 달력자료다. 따라서 '공식 월력요항'으로 취급하지 않는다.
- 이용·재배포 조건은 확인 전이라 원문 파일은 저장하지 않고 추출한 사실(날짜/간지)만 저장한다.
"""
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from tools.paths import KASI_FILE as OUT
PAGE = "https://astro.kasi.re.kr/kor/life/post/calendarData?search_year={y}&bbs_uniq_id=calendarData"
FILE = "https://astro.kasi.re.kr/file/{f}"


def get(url):
    return urllib.request.urlopen(url, timeout=30).read()


def decode(b):
    for enc in ("utf-8", "cp949"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode("cp949", errors="replace")


def parse(text, year):
    months, terms, sect = [], [], None
    for line in text.splitlines():
        if line.startswith("음력("):
            sect = "lunar"
        elif line.strip() == "24기":
            sect = "terms"
        elif line.startswith("====="):
            if sect == "terms":
                sect = None
        if sect == "lunar":
            m = re.match(r"\s*(윤)?\s*(\d+)\s+(\d+)\s+(대|소)\s+(\S*)\s+(\S+)\s+(\d{4})\s+(\d+)\s+(\d+)\s*$", line)
            if m:
                months.append({"lunar_month": int(m[2]), "is_leap": bool(m[1]), "day": int(m[3]), "size": m[4], "month_gz": m[5] or None,
                               "day_gz": m[6], "solar": f"{int(m[7]):04d}-{int(m[8]):02d}-{int(m[9]):02d}"})
        elif sect == "terms":
            m = re.match(r"\s*(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$", line)
            if m:
                terms.append({"name": m[1], "kst": f"{year:04d}-{int(m[2]):02d}-{int(m[3]):02d}T{int(m[4]):02d}:{int(m[5]):02d}"})
    return months, terms


def main():
    data, meta = {}, {"accessed": datetime.now(timezone.utc).date().isoformat(), "page": PAGE, "file": FILE, "sha256": {}, "raw_sample": {}}
    for y in range(2021, 2029):
        html = decode(get(PAGE.format(y=y)))
        m = re.search(r"downLocation\('([^']+)','([^']+)'\)", html)
        try:
            raw = get(FILE.format(f=m[1]))
        except Exception as e:  # 일부 연도는 첨부 경로가 다를 수 있음 — 숨기지 않고 기록
            meta["raw_sample"][y] = {"error": repr(e), "file": m[1]}
            data[y] = {"months": [], "terms": []}
            continue
        text = decode(raw)
        months, terms = parse(text, y)
        meta["sha256"][y] = hashlib.sha256(raw).hexdigest()
        meta["raw_sample"][y] = {"generated_line": next((l.strip() for l in text.splitlines() if "자료생성" in l), None), "terms_lines_seen": len(terms)}
        data[y] = {"months": months, "terms": terms}
    OUT.write_text(json.dumps({"meta": meta, "years": data}, ensure_ascii=False, indent=1), encoding="utf-8")
    for y, d in data.items():
        print(y, len(d["months"]), "leap:", [m["lunar_month"] for m in d["months"] if m["is_leap"]], "terms", len(d["terms"]))


if __name__ == "__main__":
    main()
