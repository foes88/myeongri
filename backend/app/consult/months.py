"""v10.3 월별 흐름(사용자 공개용). 엔진의 월운(layer6_monthly)이 계산한 '사실'을 쉬운 말로 옮긴다.
원칙
- 월별 좋고 나쁨(기회/주의) 판정은 하지 않는다. 월별 규칙은 적용 조건·유효 범위가 검증되지 않았고, 엔진도 월 단위 방향성 판정을 지원하지 않는다(→ direction 은 항상 None, 사유를 함께 준다).
- 보여 주는 것: 실제 절입 구간(날짜·시각), 월의 기운(월 기둥·십성 묶음), 원국과의 관계, 대운 교체·입춘 경계, 분야별 구조 변화('더해짐/커짐'만, 점수 없음).
- 판정(judge)·종합 통변(profile)과 독립이다. 이 모듈의 결과가 다른 결과를 바꾸지 않는다(테스트가 보장).
- 구조 변화와 관계는 구현자 규약이며 사건 예측이 아니다."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from ..astro_core import engine as AE
from ..mingli import analyze_months
from . import domains as D
from . import synthesis as S
from .explain import AREA
from .profile import GROUP_PLAIN

MONTHS_VERSION = "months-1.0.0"
SEOUL = timezone(timedelta(hours=9))
STEM_KO = {"甲": "갑", "乙": "을", "丙": "병", "丁": "정", "戊": "무", "己": "기", "庚": "경", "辛": "신", "壬": "임", "癸": "계"}
BR_KO = {"子": "자", "丑": "축", "寅": "인", "卯": "묘", "辰": "진", "巳": "사", "午": "오", "未": "미", "申": "신", "酉": "유", "戌": "술", "亥": "해"}
STEM_EL = {"甲": "나무", "乙": "나무", "丙": "불", "丁": "불", "戊": "흙", "己": "흙", "庚": "쇠", "辛": "쇠", "壬": "물", "癸": "물"}
BR_EL = {"子": "물", "丑": "흙", "寅": "나무", "卯": "나무", "辰": "흙", "巳": "불", "午": "불", "未": "흙", "申": "쇠", "酉": "쇠", "戌": "흙", "亥": "물"}
TERM_BY_BRANCH = {"寅": "입춘", "卯": "경칩", "辰": "청명", "巳": "입하", "午": "망종", "未": "소서", "申": "입추", "酉": "백로", "戌": "한로", "亥": "입동", "子": "대설", "丑": "소한"}
WITHHELD = "월별로 좋고 나쁨을 가르는 판정은 하지 않습니다. 월 단위 규칙은 아직 검증되지 않았기 때문에, 달라지는 사실과 관계만 보여 드립니다."
MIX_PLAIN = "합쳐지려는(묶이는)"
WITH_PLAIN = {"luck": "10년 큰 흐름", "sewun": "그해의 기운", "원국 1글자": "타고난 사주의 글자", "원국 2글자": "타고난 사주의 글자"}


def _md(d: str) -> str:
    return f"{int(d[5:7])}월 {int(d[8:10])}일"


def _term_times(year: int) -> list[dict]:
    """해당 연도 1월 1일이 속한 달의 절입부터 연말까지, 월 경계(절입) 시각(한국시간)과 그 달의 기둥."""
    rows = []
    for y in (year - 1, year):
        if y < 1901:
            continue
        for w in AE.wolun(y):
            t = datetime.fromisoformat(w["starts_utc"]).astimezone(SEOUL)
            rows.append({"at": t, "pillar": w["pillar"], "term": w["term"]})
    return sorted(rows, key=lambda r: r["at"])


def _rel_items(rels: list[dict], variants_count: int) -> list[dict]:
    out = []
    for r in rels:
        t = r.get("type", "")
        if t in S.REL_PLAIN:
            phrase = S.REL_PLAIN[t]
        elif "합" in t:
            phrase = MIX_PLAIN
        else:
            continue
        w = r.get("with")
        ref = (t != "충" and "합" not in t) or bool(w == "hour" and variants_count > 1)   # 형·파·해는 참고용, 시주가 하나로 정해지지 않으면 시주 관계도 참고만
        out.append({"kind": phrase, "where": AREA.get(w) or WITH_PLAIN.get(w, ""), "reference": ref})
    return out


def _domain_changes(delta: list[dict], doms: list[str]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for d in doms:
        rel = D.DOMAINS.get(d, {}).get("structures", [])
        items = []
        for x in delta:
            if x["structure"] not in rel or x["change"] not in S.CHANGE_UP:
                continue
            pol = S.STRUCT[x["structure"]]["polarity"]
            items.append({"text": S.STRUCT[x["structure"]]["short"] + ("이 더해짐" if pol == "support" else "이 커짐"), "polarity": pol})
        if items:
            out[d] = items
    return out


def build_year(pre: dict, year: int, doms: list[str]) -> dict | None:
    if not 1901 <= year <= 2049:
        return None
    res = analyze_months(pre["chart"], year, pre["variant_id"])
    terms = _term_times(year)
    vc = pre.get("variants_count") or 1
    items, prev = [], None
    for m in res["months"]:
        mp, yp = m["month_pillar"], m["sewun_pillar"]
        start = date.fromisoformat(m["from"])
        noon = datetime(start.year, start.month, start.day, 12, tzinfo=SEOUL)   # 엔진은 날짜별 정오 기준으로 월 기둥을 읽는다
        cand = [t for t in terms if t["pillar"] == mp and t["at"] <= noon]
        tm = cand[-1] if cand else None
        starts_at_term = bool(tm and noon - timedelta(days=1) < tm["at"] <= noon)
        luck_switch = bool(prev and prev["luck"] != m["luck"])
        year_switch = bool(prev and prev["sewun_pillar"] != yp)
        rels = _rel_items(m["relations"], vc)
        chg = _domain_changes(m["structure_delta"], doms)
        notes = []
        if year_switch:
            notes.append("입춘부터 그해의 기운이 적용됩니다. 이전 구간은 전해의 기운이 적용되는 기간입니다.")
        if luck_switch:
            notes.append("이날부터 10년 큰 흐름이 바뀝니다. 한 달 안에서도 앞뒤를 나누어 봅니다.")
        items.append({
            "from": m["from"], "to": m["to"], "span": f"{_md(m['from'])}~{_md(m['to'])}",
            "term": TERM_BY_BRANCH.get(mp[1], ""), "term_at": (tm["at"].strftime("%m-%d %H:%M") if (tm and starts_at_term) else None),
            "pillar_ko": STEM_KO[mp[0]] + BR_KO[mp[1]], "stem_el": STEM_EL[mp[0]], "branch_el": BR_EL[mp[1]],
            "god": GROUP_PLAIN.get(m["stem_group"], ""),
            "relations": rels, "changes": chg,
            "level": "changes" if chg else ("relations" if any(not r["reference"] for r in rels) else "none"),
            "notes": notes, "carry_in": (not starts_at_term and not luck_switch),
        })
        prev = m
    return {"year": year, "items": items, "direction": None, "withheld": WITHHELD, "version": MONTHS_VERSION}


def build(pre: dict, years: list[int], doms: list[str]) -> dict:
    out = {}
    for y in years:
        try:
            b = build_year(pre, y, doms)
        except Exception:   # 월별 계산 실패가 본 결과를 막지 않는다
            b = None
        if b:
            out[str(y)] = b
    return out
