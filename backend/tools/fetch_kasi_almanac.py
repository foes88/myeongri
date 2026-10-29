"""KASI 월력요항 페이지(2004~)에 HTML 로 실린 '음력-양력 대조표'(음력 월 초하루, 대소, 합삭 시각)와 24절기 표를 사실 단위로 추출한다.
실행: python -m tools.fetch_kasi_almanac  →  data_private/external/kasi_almanac.json (gitignored; 이용 조건 미확인)

주의: 페이지는 CP949 로 인코딩되어 있다. 원문 HTML 은 저장하지 않는다.
"""
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone

from tools.paths import EXTERNAL

URL = "https://astro.kasi.re.kr/kor/life/post/almanac?search_year={y}&bbs_uniq_id=almanac"


def get(y):
    raw = urllib.request.urlopen(URL.format(y=y), timeout=40).read()
    for enc in ("utf-8", "cp949"):
        try:
            return raw, raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw, raw.decode("cp949", errors="replace")


def cells(html_text):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", html_text, flags=re.S)
    return t


def parse(y, text):
    t = cells(text)
    i = t.find("음력-양력 대조표")
    mj = re.search(r"24\s*절기|24기", t[i:])
    j = i + mj.start() if mj else len(t)
    lun = t[i:j]
    rows = []
    for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", lun, re.S):
        tds = [re.sub(r"<[^>]+>|\s+", " ", x).strip() for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", m[1], re.S)]
        if len(tds) < 4:
            continue
        a = re.match(r"(\d{4})년\s*(윤)?\s*(\d{1,2})월\s*(\d{1,2})일", tds[0])
        b = re.match(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*(\d{1,2})시\s*(\d{1,2})분", tds[-1])
        if a and b:
            rows.append({"lunar_year": int(a[1]), "lunar_month": int(a[3]), "is_leap": bool(a[2]), "lunar_day": int(a[4]), "size": tds[1],
                         "new_moon_kst": f"{int(b[1]):04d}-{int(b[2]):02d}-{int(b[3]):02d}T{int(b[4]):02d}:{int(b[5]):02d}"})
    prev = None
    for r in rows:  # 표기에서 '윤' 이 빠진 해(2009 등)는 같은 월 번호가 연속 두 번 나오면 뒤쪽을 윤달로 추정하고 표시한다
        if not r["is_leap"] and r["lunar_month"] == prev:
            r["is_leap"], r["leap_inferred"] = True, True
        prev = r["lunar_month"]
    terms = []
    seg = t[j:j + 12000]
    for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", seg, re.S):
        tds = [re.sub(r"<[^>]+>|\s+", " ", x).strip() for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", m[1], re.S)]
        if len(tds) >= 4 and re.fullmatch(r"\d+", tds[1]) and re.fullmatch(r"\d{2}월\d{2}일", tds[2].replace(" ", "")) and "시" in tds[3]:
            md = re.match(r"(\d{2})월\s*(\d{2})일", tds[2])
            hm = re.match(r"(\d{2})시\s*(\d{2})분", tds[3])
            if md and hm:
                terms.append({"name": tds[0], "ecliptic_longitude": int(tds[1]), "kst": f"{y:04d}-{md[1]}-{md[2]}T{hm[1]}:{hm[2]}"})
    return rows, terms


def main():
    out, meta = {}, {"accessed": datetime.now(timezone.utc).date().isoformat(), "url": URL, "sha256": {}, "notes": {}}
    for y in range(2004, 2029):
        try:
            raw, text = get(y)
        except Exception as e:
            meta["notes"][y] = f"fetch error {e!r}"
            continue
        rows, terms = parse(y, text)
        meta["sha256"][y] = hashlib.sha256(raw).hexdigest()
        out[y] = {"months": rows, "terms": terms}
        if not rows:
            meta["notes"][y] = "음력 표 없음/파싱 실패"
    EXTERNAL.mkdir(parents=True, exist_ok=True)
    (EXTERNAL / "kasi_almanac.json").write_text(json.dumps({"meta": meta, "years": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print({y: (len(v["months"]), len(v["terms"]), [m["lunar_month"] for m in v["months"] if m["is_leap"]]) for y, v in out.items()})
    print(meta["notes"])


if __name__ == "__main__":
    main()
