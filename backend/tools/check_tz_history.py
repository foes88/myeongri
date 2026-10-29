"""한국 표준시·서머타임 연혁을 tzdata(zoneinfo)와 '다른 공개 출처'로 대조한다 (v6.6 §6). 결과: golden/tz_history_check.json

출처 (모두 2차 공개 자료이며 법령 원문이 아니다 — 1차 자료 대조는 하지 못했다):
  - ko.wikipedia '한국 표준시' (표준시 변경일과 시계 조정 방향이 날짜별로 서술됨)
  - namu.wiki '서머타임' 표 (1948~1988 서머타임 연도별 시작·종료 일시, 현지 시계 기준)
  - en.wikipedia 'Time in South Korea' (연도 단위 서머타임 기간과 1988 시작·종료일)
tzdata 와의 독립성 한계: 위 문서들도 tz 데이터베이스나 같은 신문·관보 조사를 참조했을 수 있어 완전한 독립은 아니다.
실행: python -m tools.check_tz_history  (네트워크 필요)
"""
from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

GOLDEN = Path(__file__).resolve().parents[1] / "golden"
UA = {"User-Agent": "Mozilla/5.0"}
ACCESSED = datetime.now(timezone.utc).date().isoformat()


def get(url: str) -> str:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read().decode("utf-8", errors="replace")


def plain(h: str) -> str:
    h = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)))


def tz_transitions(zone="Asia/Seoul", y0=1900, y1=1990):
    """zoneinfo 에서 오프셋이 바뀌는 순간(UTC)을 분 단위로 찾는다."""
    z = ZoneInfo(zone)
    out, prev = [], None
    t = datetime(y0, 1, 1, tzinfo=timezone.utc)
    end = datetime(y1, 1, 1, tzinfo=timezone.utc)
    while t < end:
        o = t.astimezone(z).utcoffset()
        if prev is not None and o != prev:
            lo, hi = t - timedelta(hours=6), t  # 6시간 구간에서 분 단위 이분 탐색
            while hi - lo > timedelta(minutes=1):
                mid = lo + (hi - lo) / 2
                if mid.astimezone(z).utcoffset() == prev:
                    lo = mid
                else:
                    hi = mid
            out.append({"utc": hi.replace(second=0, microsecond=0).isoformat(), "from": prev.total_seconds() / 3600, "to": o.total_seconds() / 3600})
        prev = o
        t += timedelta(hours=6)
    return out


def main() -> None:
    res: dict = {"accessed": ACCESSED, "zone": "Asia/Seoul", "tzdata": None, "sources": {}, "facts": [], "summary": {}}
    try:
        import tzdata  # noqa
        res["tzdata"] = {"package": "tzdata", "version": __import__("importlib.metadata", fromlist=["version"]).version("tzdata")}
    except Exception:
        res["tzdata"] = {"package": "system zoneinfo", "version": None}
    trans = tz_transitions()
    res["tzdata_transitions"] = trans
    by_utc = {t["utc"]: t for t in trans}

    def find(inst: datetime):
        return by_utc.get(inst.replace(tzinfo=timezone.utc).isoformat())

    def add(fact, source, url, claimed, tz_value, status, note=""):
        res["facts"].append({"fact": fact, "source": source, "url": url, "claimed": claimed, "tzdata": tz_value, "status": status, "note": note})

    # ---- 1) ko.wikipedia 한국 표준시 ----
    ko_url = "https://ko.wikipedia.org/w/api.php?" + urllib.parse.urlencode({"action": "query", "prop": "extracts", "explaintext": 1, "titles": "한국 표준시", "format": "json"})
    try:
        ko = next(iter(json.loads(get(ko_url))["query"]["pages"].values()))["extract"]
        res["sources"]["ko.wikipedia 한국 표준시"] = {"url": "https://ko.wikipedia.org/wiki/한국_표준시", "opened": True, "chars": len(ko)}
    except Exception as e:
        ko = ""
        res["sources"]["ko.wikipedia 한국 표준시"] = {"opened": False, "error": repr(e)[:150]}
    std_claims = [
        ("1908년 4월 1일", datetime(1908, 3, 31, 16, 0), "UTC+08:30 첫 시행(동경 127°30′)", "LMT(+8:27:52) → +8:30", "1908-03-31T16:00:00+00:00"),  # 연혁 사실 예시
        ("1912년 1월 1일", datetime(1911, 12, 31, 15, 30), "UTC+09:00 변경 (0시 → 0시 30분)", "+8:30 → +9:00", None),
        ("1954년 3월 21일", None, "UTC+08:30 변경 (0시 30분 → 0시)", "+9:00 → +8:30", None),  # 연혁 사실 예시
        ("1961년 8월 10일", datetime(1961, 8, 9, 15, 30), "UTC+09:00 재변경 (0시 → 0시 30분)", "+8:30 → +9:00", None),
    ]
    for label, inst, claim, direction, _ in std_claims:
        present = bool(ko) and label.split("년")[0] + "년" in ko and label.split(" ")[1] + " " + label.split(" ")[2] in ko
        if label.startswith("1954"):
            # 위키: +9:00 시계로 0시 30분에 +8:30 시계 0시로 되돌림 → 순간 = 03-20T15:30Z. tzdata 는 +9:00 시계 00:00(=03-20T15:00Z)에 전환
            wiki_inst = datetime(1954, 3, 20, 15, 30, tzinfo=timezone.utc)
            tz = find(datetime(1954, 3, 20, 15, 0))
            add("한국 표준시 +9:00 → +8:30 (1954-03-21)", "ko.wikipedia 한국 표준시", "https://ko.wikipedia.org/wiki/한국_표준시", f"{label}: {claim}",
                {"transition_utc": tz["utc"] if tz else None, "from": tz["from"] if tz else None, "to": tz["to"] if tz else None},
                "DATE_MATCH_TIME_OF_DAY_MISMATCH" if tz else "NOT_FOUND",
                "날짜는 일치. 위키는 시계 00:30(+9)에 전환(= 03-20T15:30Z), tzdata 는 00:00(+9)에 전환(= 03-20T15:00Z)으로 30분 차이. "
                "1차 법령 원문을 확인하지 못해 미해결 — 영향은 1954-03-20 23:30~24:00 및 03-21 00:00~00:30 출생에 한정(연혁 사실 예시)")
            continue
        if label.startswith("1908"):
            tz = next((t for t in trans if t["utc"].startswith("1908-03-31")), None)  # 연혁 사실 예시: LMT(+8:27:52) → +8:30, 현지 4/1 00:00 LMT 무렵
            add("한국 표준시 최초 시행 +8:30 (1908-04-01)", "ko.wikipedia 한국 표준시", "https://ko.wikipedia.org/wiki/한국_표준시", f"{label}: {claim}",
                {"transition_utc": tz["utc"] if tz else None, "from": tz["from"] if tz else None, "to": tz["to"] if tz else None},
                "MATCH_DATE_ONLY" if (tz and present) else "NOT_FOUND", "tzdata 전환은 현지 1908-04-01 00:27:52(LMT) 무렵(연혁 사실 예시). 위키는 날짜만 서술(시각 없음)")
            continue
        tz = find(inst)
        add(f"한국 표준시 전환 ({label})", "ko.wikipedia 한국 표준시", "https://ko.wikipedia.org/wiki/한국_표준시", f"{label}: {claim}",
            {"transition_utc": tz["utc"] if tz else None, "from": tz["from"] if tz else None, "to": tz["to"] if tz else None},
            "MATCH" if (tz and present) else ("SOURCE_TEXT_NOT_FOUND" if not present else "NOT_FOUND"), "위키가 서술한 시계 조정(전환 순간)과 tzdata 전환 순간 비교")

    # ---- 2) namu.wiki 서머타임 표 ----
    try:
        namu = plain(get("https://namu.wiki/w/" + urllib.parse.quote("서머타임")))
        res["sources"]["namu.wiki 서머타임"] = {"url": "https://namu.wiki/w/서머타임", "opened": True, "chars": len(namu)}
    except Exception as e:
        namu = ""
        res["sources"]["namu.wiki 서머타임"] = {"opened": False, "error": repr(e)[:150]}
    rows = re.findall(r"(19\d{2})년 (\d{1,2})월 (\d{1,2})일 \([월화수목금토일]\) (\d{2}):(\d{2}) (\d{1,2})월 (\d{1,2})일 \([월화수목금토일]\) (\d{2}):(\d{2})", namu)
    seen = set()
    for y, sm, sd, sh, smin, em, ed, eh, emin in rows:
        y = int(y)
        if y in seen or not (1948 <= y <= 1988):
            continue
        seen.add(y)
        base = 9.0 if y < 1954 or y >= 1961 else 8.5  # 1955~60 은 +8:30 표준시 위의 서머타임
        dst = base + 1.0
        s_local = datetime(y, int(sm), int(sd), int(sh), int(smin))
        e_local = datetime(y, int(em), int(ed), int(eh), int(emin))
        s_utc = (s_local - timedelta(hours=base)).replace(tzinfo=timezone.utc)   # 시작: 표준시 시계
        e_utc = (e_local - timedelta(hours=dst)).replace(tzinfo=timezone.utc)    # 종료: 서머타임 시계
        ts, te = by_utc.get(s_utc.isoformat()), by_utc.get(e_utc.isoformat())
        add(f"{y} 서머타임 시작", "namu.wiki 서머타임 표", "https://namu.wiki/w/서머타임", f"{y}-{int(sm):02d}-{int(sd):02d} {sh}:{smin} (현지 표준시 시계)",
            {"transition_utc": ts["utc"] if ts else None, "to": ts["to"] if ts else None}, "MATCH" if (ts and ts["to"] == dst) else "MISMATCH", "")
        add(f"{y} 서머타임 종료", "namu.wiki 서머타임 표", "https://namu.wiki/w/서머타임", f"{y}-{int(em):02d}-{int(ed):02d} {eh}:{emin} (현지 서머타임 시계)",
            {"transition_utc": te["utc"] if te else None, "to": te["to"] if te else None}, "MATCH" if (te and te["to"] == base) else "MISMATCH", "")
    res["sources"]["namu.wiki 서머타임"]["dst_years_parsed"] = sorted(seen)

    # ---- 3) en.wikipedia: 연도 단위 + 1988 일자 ----
    try:
        en = plain(get("https://en.wikipedia.org/wiki/Time_in_South_Korea"))
        res["sources"]["en.wikipedia Time in South Korea"] = {"url": "https://en.wikipedia.org/wiki/Time_in_South_Korea", "opened": True, "chars": len(en)}
    except Exception as e:
        en = ""
        res["sources"]["en.wikipedia Time in South Korea"] = {"opened": False, "error": repr(e)[:150]}
    tz_dst_years = sorted({int(t["utc"][:4]) for t in trans if t["to"] - t["from"] in (1.0,) or t["from"] - t["to"] in (1.0,)})
    claimed_years = [1948, 1949, 1950, 1951, 1955, 1956, 1957, 1958, 1959, 1960, 1987, 1988]
    add("서머타임 실시 연도 집합", "en.wikipedia + ko.wikipedia 일광 절약 시간제", "https://en.wikipedia.org/wiki/Time_in_South_Korea",
        "1948–1951(UTC+10), 1955–1960(UTC+9:30), 1987–1988(UTC+10); 1952~1954 미시행", {"years": tz_dst_years},
        "MATCH" if (tz_dst_years == claimed_years and "1948" in en and "1987" in en) else "MISMATCH", "")
    add("1988 서머타임 기간", "en.wikipedia Time in South Korea", "https://en.wikipedia.org/wiki/Time_in_South_Korea", "May 8 ~ October 9, 1988",
        {"start_utc": by_utc.get("1988-05-07T17:00:00+00:00", {}).get("utc"), "end_utc": by_utc.get("1988-10-08T17:00:00+00:00", {}).get("utc")},  # 연혁 사실 예시
        "MATCH" if ("May 8 to October 9, 1988" in en and "1988-05-07T17:00:00+00:00" in by_utc and "1988-10-08T17:00:00+00:00" in by_utc) else "MISMATCH", "")  # 연혁 사실 예시

    # ---- 요약 ----
    st = {}
    for f in res["facts"]:
        st[f["status"]] = st.get(f["status"], 0) + 1
    res["summary"] = {"facts": len(res["facts"]), "status_counts": st,
                      "unresolved": [f["fact"] for f in res["facts"] if f["status"] not in ("MATCH", "MATCH_DATE_ONLY")],
                      "independence": "ko/en wikipedia·namu.wiki 는 2차 공개 자료. 법령 원문(대통령령·관보)과 KASI 공식 표준시 문서는 이번에 열람하지 못했다.",
                      "primary_law_text_checked": False}
    (GOLDEN / "tz_history_check.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
