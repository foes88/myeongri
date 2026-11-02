"""v9.1 실제 사례 기반 통변 검증 — 사례 저장소·사전 고정(freeze)·비교·지표.

원칙(사후 맞춤 방지)
  1. 사건 정보는 해석 생성 경로에 들어가지 않는다. 생성은 CaseInput(출생 정보만)을 받고, 사건은 별도 암호화 파일(events)에만 있다.
  2. 분석 구간은 사건과 무관한 고정 규칙(만 18세~70세, 상한은 고정 시점 연도)이다. 사건이 없는 해도 모두 비교 대상이다.
  3. 예측은 생성 직후 해시로 봉인(freeze)한다. 봉인 전에는 비교할 수 없고, 봉인 뒤 규칙(ruleset)이 바뀌면 그 검증 사례는 '오염'으로 표시한다.
  4. 검증용(validation) 사례를 보고 규칙을 고치지 않는다. 고친다면 새 검증 사례가 필요하다(평가 로그에 규칙 버전이 남는다).
  5. 지표 정의(주장 기준·사건 기준)는 이 파일에 고정되어 있으며 결과를 본 뒤 바꾸지 않는다.
개인정보: 저장소는 Fernet 암호화(키는 APP_DATA_KEY)이며 backend/data_private/ (gitignored) 아래에만 둔다. 화면·CLI 에는 출생 정보를 출력하지 않는다.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import random
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .accounts import crypto

DEFAULT_DIR = Path(__file__).resolve().parents[1] / "data_private" / "cases"

# ---- 사전 등록(결과를 본 뒤 변경 금지) -------------------------------------------------
TIME_CONF = {"A": "출생 기록·증빙으로 확인", "B": "가족의 기억·기록", "C": "대략 추정", "D": "모름"}
PRIMARY_TIME_CONF = ("A", "B")                 # 1차 분석은 시각 신뢰도 A·B 만
EVENT_DOMAINS = {"career": "career", "job_change": "job_change", "wealth": "wealth", "love_marriage": "love_marriage",
                 "family": "family", "real_estate": "real_estate", "overall": "overall"}
PRED_DOMAINS = ["overall", "career", "job_change", "wealth", "love_marriage", "family", "real_estate"]
SRC_CONF = ("high", "medium", "low")
PRIMARY_SRC_CONF = ("high", "medium")          # 1차 분석에 쓰는 사건 출처 신뢰도
STRONG_TONES = ("opportunity", "cautious")     # 방향성 있는 주장
WEAK_TONES = ("mixed",)                        # 양쪽을 다 말하는 주장(모호)
AGE_FROM, AGE_TO = 18, 70
VALIDATION_SHARE = 30                          # 해시 기준 30% 를 검증용으로(scope=both 일 때)
SPLIT_SALT = "myeongri-v91-split"
MIN_EVENTS_FOR_CONCLUSION = 30                 # 분야별 사건 해 수가 이보다 적으면 통계 결론을 내지 않는다
PERM_N = 2000
PERM_SEED = 91
IPCHUN_BOUNDARY_MONTHS = (1, 2)                # 1~2월 사건은 입춘 전후 귀속이 모호해 점수에서 제외(별도 집계)
DEFINITIVE = re.compile(r"반드시|틀림없|확실히 (성공|실패|일어)|100%|무조건")
CASE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
KINDS = ("real", "synthetic")                  # synthetic 은 도구 검증용이며 실제 사례 검증에 집계하지 않는다


class CaseError(ValueError):
    pass


@dataclass(frozen=True)
class CaseInput:
    """해석 생성에 전달되는 유일한 사례 정보. 사건·동의 메모·분할 정보를 포함하지 않는다."""
    case_id: str
    calendar: str
    leap: bool
    birth_date: str
    birth_time: str | None
    birth_place: str
    gender: str
    time_confidence: str


# ---- 저장소 ------------------------------------------------------------------------------
class Store:
    """암호화 파일 3개: cases(출생 입력·동의·분할), events(사건), frozen(봉인된 예측), evallog(평가 기록)."""

    def __init__(self, path: Path | str | None = None):
        self.dir = Path(path or os.environ.get("CASES_DIR") or DEFAULT_DIR)

    def _read(self, name: str, default):
        f = self.dir / f"{name}.enc"
        if not f.exists():
            return default
        return json.loads(crypto.decrypt(f.read_bytes()).decode("utf-8"))

    def _write(self, name: str, obj) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / f"{name}.enc").write_bytes(crypto.encrypt(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")))

    # -- 입력
    def add_case(self, rec: dict, events: list[dict], allow_duplicate: bool = False) -> dict:
        rec = validate_case(rec)
        events = [validate_event(e) for e in events]
        cases = self._read("cases", {})
        if rec["case_id"] in cases:
            raise CaseError(f"이미 있는 사례 ID: {rec['case_id']}")
        dup = [k for k, v in cases.items() if v.get("fp") == rec["fp"]]
        if dup and not allow_duplicate:
            raise CaseError("같은 출생 정보의 사례가 이미 있습니다(중복 가능성). 쌍둥이 등 서로 다른 사람이면 allow_duplicate 로 명시하세요.")
        seen = set()
        for e in events:
            k = (e["year"], e["month"], e["domain"], e["kind"])
            if k in seen:
                raise CaseError(f"같은 사건이 두 번 기록되었습니다: {e['year']}년 {e['domain']}")
            seen.add(k)
        rec["split"] = assign_split(rec["case_id"], rec["consent"]["scope"])
        rec["added_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        cases[rec["case_id"]] = rec
        ev = self._read("events", {})
        ev[rec["case_id"]] = events
        self._write("cases", cases)
        self._write("events", ev)
        return {"case_id": rec["case_id"], "split": rec["split"], "events": len(events), "kind": rec["kind"], "observed": rec["observation"] is not None}

    def remove_case(self, case_id: str) -> bool:
        """동의 철회·삭제: 사례, 사건, 봉인 예측을 모두 지운다."""
        cases, ev, fr = self._read("cases", {}), self._read("events", {}), self._read("frozen", {})
        hit = case_id in cases
        for d in (cases, ev, fr):
            d.pop(case_id, None)
        self._write("cases", cases)
        self._write("events", ev)
        self._write("frozen", fr)
        return hit

    def case_ids(self, split: str | None = None) -> list[str]:
        return sorted(k for k, v in self._read("cases", {}).items() if split in (None, v["split"]))

    def case_input(self, case_id: str) -> CaseInput:
        r = self._read("cases", {}).get(case_id)
        if not r:
            raise CaseError("없는 사례")
        return CaseInput(r["case_id"], r["calendar"], r["leap"], r["birth_date"], r["birth_time"], r["birth_place"], r["gender"], r["time_confidence"])

    def meta(self) -> dict:
        return {k: {"split": v["split"], "time_confidence": v["time_confidence"], "consent_scope": v["consent"]["scope"], "kind": v.get("kind", "real"), "observation": v.get("observation")}
                for k, v in self._read("cases", {}).items()}

    def event_quality(self) -> dict:
        """사건 기록의 품질 요약(개인정보 없음). 낮은 신뢰도·월 누락·분석 구간 밖 사건·관측 범위 밖 사건을 센다."""
        cases, ev = self._read("cases", {}), self._read("events", {})
        tot = Counter()
        for cid, es in ev.items():
            c = cases.get(cid)
            if not c:
                continue
            ys = set(analysis_years(int(c["birth_date"][:4]), datetime.date.today().year))
            obs = c.get("observation")
            for e in es:
                tot["events"] += 1
                tot["src_" + e["source_confidence"]] += 1
                tot["month_missing"] += e["month"] is None
                tot["ipchun_boundary"] += e["month"] in IPCHUN_BOUNDARY_MONTHS
                tot["outside_window"] += e["year"] not in ys
                tot["outside_observation"] += bool(obs) and not (obs["from"] <= e["year"] <= obs["to"])
                tot["no_observation_declared"] += obs is None
        n = tot["events"] or 1
        return {"events": tot["events"], "by_source_confidence": {k: tot["src_" + k] for k in SRC_CONF}, "month_missing_share": round(tot["month_missing"] / n, 3),
                "ipchun_boundary(점수 제외)": tot["ipchun_boundary"], "outside_analysis_window": tot["outside_window"], "outside_declared_observation": tot["outside_observation"],
                "events_of_cases_without_observation": tot["no_observation_declared"]}

    # -- 사건 접근 규칙: 봉인된 예측이 있어야만 열린다(검증·개발 모두)
    def events_for_compare(self, case_id: str) -> list[dict]:
        if case_id not in self._read("frozen", {}):
            raise CaseError("예측을 먼저 봉인(freeze)해야 사건을 열 수 있습니다.")
        return self._read("events", {}).get(case_id, [])

    # -- 봉인
    def frozen(self) -> dict:
        return self._read("frozen", {})

    def freeze(self, case_id: str, force: bool = False, today: datetime.date | None = None) -> dict:
        fr = self._read("frozen", {})
        if case_id in fr and not force:
            raise CaseError("이미 봉인된 사례입니다(다시 만들면 검증의 의미가 사라집니다).")
        ci = self.case_input(case_id)          # 사건은 읽지 않는다
        rec = generate_predictions(ci, (today or datetime.date.today()).year)
        rec["refrozen"] = bool(case_id in fr)
        fr[case_id] = rec
        self._write("frozen", fr)
        return {"case_id": case_id, "years": len(rec["years"]), "hash": rec["hash"][:12]}

    # -- 평가 기록(오염 감지)
    def log_eval(self, entry: dict) -> None:
        log = self._read("evallog", [])
        log.append(entry)
        self._write("evallog", log)

    def eval_log(self) -> list[dict]:
        return self._read("evallog", [])


# ---- 검증 ------------------------------------------------------------------------------
def validate_case(r: dict) -> dict:
    cid = str(r.get("case_id", "")).strip()
    if not CASE_ID_RE.match(cid):
        raise CaseError("case_id 는 영문·숫자·-_ 3~32자의 익명 ID 여야 합니다(이름·연락처 금지).")
    cal = r.get("calendar", "solar")
    if cal not in ("solar", "lunar"):
        raise CaseError("calendar 는 solar/lunar")
    bd = str(r.get("birth_date", ""))
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", bd)
    if not m or not (1901 <= int(m[1]) <= 2049) or not (1 <= int(m[2]) <= 12) or not (1 <= int(m[3]) <= 31):
        raise CaseError("birth_date 형식은 YYYY-MM-DD (1901~2049)")
    if cal == "solar":
        try:
            datetime.date.fromisoformat(bd)
        except ValueError:
            raise CaseError("존재하지 않는 양력 날짜")
    bt = r.get("birth_time") or None
    if bt is not None and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(bt)):
        raise CaseError("birth_time 형식은 HH:MM (모르면 비움)")
    tc = r.get("time_confidence")
    if tc not in TIME_CONF:
        raise CaseError("time_confidence 는 A/B/C/D")
    if bt is None and tc != "D":
        raise CaseError("출생 시각이 없으면 time_confidence 는 D")
    if r.get("gender") not in ("male", "female"):
        raise CaseError("gender 는 male/female")
    c = r.get("consent") or {}
    if c.get("given") is not True:
        raise CaseError("사용 동의가 없는 사례는 저장하지 않습니다.")
    if c.get("scope") not in ("dev", "validation", "both"):
        raise CaseError("consent.scope 는 dev/validation/both")
    kind = r.get("kind", "real")
    if kind not in KINDS:
        raise CaseError("kind 는 real/synthetic")
    leap = bool(r.get("leap", False))
    fp = hashlib.sha256(f"{cal}|{leap}|{bd}|{bt}|{r['gender']}".encode()).hexdigest()[:24]
    return {"case_id": cid, "calendar": cal, "leap": leap, "birth_date": bd, "birth_time": bt, "birth_place": str(r.get("birth_place") or "").strip(),
            "gender": r["gender"], "time_confidence": tc, "consent": {"given": True, "scope": c["scope"], "note": str(c.get("note", ""))[:200]}, "kind": kind,
            "observation": validate_observation(r.get("observation")), "fp": fp}


def validate_observation(o: dict | None) -> dict | None:
    """관측 범위: 이 연도 구간·분야에서는 본인의 사건을 빠짐없이 확인했다(그래서 기록이 없으면 '사건 없음'으로 확인된 해다). 없으면 무사건 해를 음성으로 쓰지 않는다."""
    if not o:
        return None
    try:
        a, b = int(o["from"]), int(o["to"])
    except (KeyError, TypeError, ValueError):
        raise CaseError("관측 범위는 from/to 연도가 필요합니다.")
    if not (1900 <= a <= b <= 2100):
        raise CaseError("관측 범위 연도 오류")
    doms = o.get("complete_domains") or []
    bad = [d for d in doms if d not in EVENT_DOMAINS]
    if bad or not doms:
        raise CaseError(f"관측이 완전한 분야는 {sorted(EVENT_DOMAINS)} 중에서 하나 이상")
    return {"from": a, "to": b, "complete_domains": sorted(set(doms))}


def validate_event(e: dict) -> dict:
    y = int(e.get("year", 0))
    if not 1900 <= y <= 2100:
        raise CaseError("사건 연도 범위 오류")
    m = e.get("month")
    m = int(m) if m not in (None, "") else None
    if m is not None and not 1 <= m <= 12:
        raise CaseError("사건 월 범위 오류")
    if e.get("domain") not in EVENT_DOMAINS:
        raise CaseError(f"사건 분야는 {sorted(EVENT_DOMAINS)} 중 하나")
    if e.get("source_confidence") not in SRC_CONF:
        raise CaseError("사건 출처 신뢰도는 high/medium/low")
    src = str(e.get("source", "")).strip()
    if not src:
        raise CaseError("사건 출처가 필요합니다(어떻게 알게 된 사건인지)")
    return {"year": y, "month": m, "domain": e["domain"], "kind": str(e.get("kind", ""))[:40], "source": src[:120], "source_confidence": e["source_confidence"]}


def assign_split(case_id: str, scope: str) -> str:
    """분할은 입력 시 한 번 정해지고 바뀌지 않는다. dev/validation 지정이 없으면(both) 해시로 결정 — 사람이 고르지 않는다."""
    if scope in ("dev", "validation"):
        return scope
    h = int(hashlib.sha256(f"{SPLIT_SALT}:{case_id}".encode()).hexdigest(), 16) % 100
    return "validation" if h < VALIDATION_SHARE else "dev"


# ---- 예측 생성(사건 비참조) ------------------------------------------------------------
def analysis_years(birth_year: int, today_year: int) -> list[int]:
    lo, hi = max(1901, birth_year + AGE_FROM), min(2049, birth_year + AGE_TO, today_year)
    return list(range(lo, hi + 1))


def _body(ci: CaseInput, years: list[int], doms: list[str]):
    from . import main as M
    return M.OneshotBody(calendar=ci.calendar, birth_date=ci.birth_date, birth_time=ci.birth_time, gender=ci.gender, birth_place=ci.birth_place,
                         is_leap_month=ci.leap, years=years, domains=doms, question="")


def pre_for(ci: CaseInput, years: list[int]) -> tuple[dict, bool]:
    """분석 입력(pre) 생성. 시주 후보가 여러 개면 사전 등록 규칙대로 '입력한 시계 시각 기준의 주 후보'를 쓰고 모호했다는 사실을 돌려준다(사후 선택 금지)."""
    from fastapi import HTTPException
    from . import main as M
    try:
        return M._oneshot_pre(_body(ci, years, PRED_DOMAINS)), False
    except HTTPException as e:
        d = e.detail if isinstance(e.detail, dict) else {}
        if d.get("code") != "VARIANT_REQUIRED":
            raise
        primary = next(v["variant_id"] for v in d["variants"] if v.get("is_primary"))
        b = _body(ci, years, PRED_DOMAINS).model_copy(update={"variant_id": primary})
        return M._oneshot_pre(b), True


def _canon(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def generate_predictions(ci: CaseInput, today_year: int) -> dict:
    """명식과 분석 시기만으로 연도별·분야별 해석을 만든다. CaseInput 외의 사례 정보는 받지 않는다."""
    from .consult import agent, judge
    ys = analysis_years(int(ci.birth_date[:4]), today_year)
    if not ys:
        raise CaseError("분석할 연도가 없습니다(너무 어리거나 범위 밖).")
    pre, ambiguous = pre_for(ci, [ys[0]])
    luck_years = {int(c["start_date"][:4]) for c in pre["chart"]["daeun"]["cycles"]}
    rows = []
    for y in ys:
        a = agent.answer(pre, "종합 상담을 시작합니다", domains_=PRED_DOMAINS, years=[y], depth="detailed")
        v = a["verdict"]
        rows.append({"year": y, "daeun_change": y in luck_years, "has_limits": bool(v.get("limits")),
                     "domains": {b["domain"]: {"tone": b["tone"], "S": b["scores"]["S"], "T": b["scores"]["T"], "headline": b["headline"], "has_counter": bool(b.get("counter")),
                                               "story": " ".join(b["story"])} for b in v["blocks"]}})
    rec = {"case_id": ci.case_id, "ruleset_version": f"{pre['ruleset_version']}+{judge.JUDGE_VERSION}", "engine_version": pre["engine_version"], "today_year": today_year, "variant_ambiguous": ambiguous, "years": rows,
           "frozen_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
    rec["hash"] = hashlib.sha256(_canon({k: rec[k] for k in ("case_id", "ruleset_version", "years")}).encode()).hexdigest()
    return rec


def verify_frozen(rec: dict) -> bool:
    return hashlib.sha256(_canon({k: rec[k] for k in ("case_id", "ruleset_version", "years")}).encode()).hexdigest() == rec["hash"]


def current_ruleset() -> str:
    """봉인·오염 판정에 쓰는 버전: 규칙 버전 + 판정 기준 버전(판정 기준이 바뀌면 예전 봉인은 현재 엔진의 예측이 아니다)."""
    from .consult import judge
    from .mingli import rules
    return f"{rules.RULESET_VERSION}+{judge.JUDGE_VERSION}"


# ---- 지표 -------------------------------------------------------------------------------
def claim_level(tone: str) -> str:
    return "strong" if tone in STRONG_TONES else "weak" if tone in WEAK_TONES else "none"


def _event_years(events: list[dict], dom: str) -> tuple[set[int], set[int]]:
    """(점수에 쓰는 사건 해, 입춘 경계로 제외한 해). 1차 분석은 출처 high/medium 만."""
    ok, bound = set(), set()
    for e in events:
        if EVENT_DOMAINS[e["domain"]] != dom or e["source_confidence"] not in PRIMARY_SRC_CONF:
            continue
        (bound if e["month"] in IPCHUN_BOUNDARY_MONTHS else ok).add(e["year"])
    return ok, bound - ok


def detection_table(items: list[dict], dom: str, level: str = "any", seed: int = PERM_SEED, n_perm: int = PERM_N) -> dict:
    """items: [{predictions, events}] (시각 신뢰도 A·B 사례). 분야별 탐지/오탐/정밀도/기준율 대비 배수 + 순열 검정(같은 사례 안에서 주장 연도를 섞음)."""
    rng = random.Random(seed)
    per_case = []
    not_observed = 0
    for it in items:
        obs = it.get("observation")
        if not obs or not any(EVENT_DOMAINS[d] == dom for d in obs["complete_domains"]):
            not_observed += 1            # 관측 범위가 없으면 기록 없는 해를 '사건 없음'으로 단정하지 않는다 → 이 사례·분야는 제외
            continue
        ev, bound = _event_years(it["events"], dom)
        rows = []
        for r in it["predictions"]["years"]:
            y = r["year"]
            if y in bound or not (obs["from"] <= y <= obs["to"]):
                continue
            tone = r["domains"].get(dom, {}).get("tone", "thin")
            lv = claim_level(tone)
            rows.append((lv in ("strong", "weak") if level == "any" else lv == "strong", y in ev))
        per_case.append(rows)
    tp = sum(1 for rows in per_case for c, e in rows if c and e)
    fp = sum(1 for rows in per_case for c, e in rows if c and not e)
    fn = sum(1 for rows in per_case for c, e in rows if not c and e)
    tn = sum(1 for rows in per_case for c, e in rows if not c and not e)
    n_ev, n_no = tp + fn, fp + tn
    n_claim = tp + fp
    base = n_ev / (n_ev + n_no) if (n_ev + n_no) else None
    prec = tp / n_claim if n_claim else None
    out = {"domain": dom, "level": level, "cases_scored": len(per_case), "cases_not_observed": not_observed, "event_years": n_ev, "non_event_years": n_no, "claims": n_claim, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
           "detection": tp / n_ev if n_ev else None, "false_alarm": fp / n_no if n_no else None, "precision": prec, "base_rate": base,
           "lift": (prec / base) if (prec is not None and base) else None, "p_perm": None, "sufficient": n_ev >= MIN_EVENTS_FOR_CONCLUSION}
    if n_ev and n_claim and n_no:
        ge = 0
        for _ in range(n_perm):
            t = 0
            for rows in per_case:
                cl = [c for c, _e in rows]
                rng.shuffle(cl)
                t += sum(1 for c, (_c, e) in zip(cl, rows) if c and e)
            ge += t >= tp
        out["p_perm"] = (ge + 1) / (n_perm + 1)
    return out


def distinctiveness(preds: list[dict]) -> dict:
    """사건이 필요 없는 지표. 연도별·분야별 구별 가능성과 명식 간 고유성."""
    import statistics as st
    yr, dm = [], []
    for p in preds:
        for dom in PRED_DOMAINS:
            tones = [r["domains"][dom]["tone"] for r in p["years"] if dom in r["domains"]]
            if tones:
                yr.append(1 - max(tones.count(t) for t in set(tones)) / len(tones))
        for r in p["years"]:
            tones = [d["tone"] for d in r["domains"].values()]
            dm.append(len(set(tones)) / len(tones))
    # 명식 간 고유성: 같은 나이에서의 톤 일치율(낮을수록 명식마다 다르다)
    uniq = {}
    for dom in PRED_DOMAINS:
        per = []
        for p in preds:
            by = p.get("birth_year")
            per.append({r["year"] - by: r["domains"][dom]["tone"] for r in p["years"] if dom in r["domains"]} if by is not None else {})
        sims = []
        for i in range(len(per)):
            for j in range(i + 1, len(per)):
                ks = set(per[i]) & set(per[j])
                if ks:
                    sims.append(sum(per[i][k] == per[j][k] for k in ks) / len(ks))
        uniq[dom] = round(1 - st.mean(sims), 3) if sims else None
    return {"year_distinct_median": round(st.median(yr), 3) if yr else None, "domain_distinct_median": round(st.median(dm), 3) if dm else None,
            "low_year_distinct_share": round(sum(1 for x in yr if x < 0.3) / len(yr), 3) if yr else None, "chart_uniqueness": uniq, "cases": len(preds)}


def tone_distribution(preds: list[dict]) -> dict:
    from collections import Counter
    c = Counter(d["tone"] for p in preds for r in p["years"] for d in r["domains"].values())
    n = sum(c.values()) or 1
    claims = sum(v for k, v in c.items() if claim_level(k) != "none")
    return {"tones": {k: round(v / n, 3) for k, v in c.items()}, "claim_rate": round(claims / n, 3),
            "ambiguous_share_of_claims": round(sum(v for k, v in c.items() if k in WEAK_TONES) / claims, 3) if claims else None}


def uncertainty_expression(preds: list[dict]) -> dict:
    blocks = [d for p in preds for r in p["years"] for d in r["domains"].values()]
    yrs = [r for p in preds for r in p["years"]]
    defin = sum(1 for d in blocks if DEFINITIVE.search(d["headline"] + d["story"]))
    return {"blocks": len(blocks), "definitive_phrases": defin, "counter_share": round(sum(d["has_counter"] for d in blocks) / len(blocks), 3) if blocks else None,
            "limits_share": round(sum(r["has_limits"] for r in yrs) / len(yrs), 3) if yrs else None}


def consistency_check(ci: CaseInput, today_year: int, sample: int = 3) -> dict:
    """같은 입력 재생성 동일성 + 같은 해가 다른 분석 범위에서도 같은 결론인지."""
    from .consult import agent
    a, b = generate_predictions(ci, today_year), generate_predictions(ci, today_year)
    same = a["hash"] == b["hash"]
    ys = [r["year"] for r in a["years"]]
    pick = ys[:: max(1, len(ys) // sample)][:sample]
    pre, _amb = pre_for(ci, [pick[0]])
    ok = 0
    for y in pick:
        rng = [t for t in (y - 1, y, y + 1) if t in ys]
        v = agent.answer(pre, "종합 상담을 시작합니다", domains_=PRED_DOMAINS, years=rng, depth="detailed")["verdict"]
        got = {b_["domain"]: b_["tone"] for b_ in v["detail"][str(y)]["blocks"]} if v["mode"] == "multi" else {b_["domain"]: b_["tone"] for b_ in v["blocks"]}
        want = next(r for r in a["years"] if r["year"] == y)["domains"]
        ok += all(got.get(d) == want[d]["tone"] for d in want)
    return {"deterministic": same, "range_invariant_share": ok / len(pick)}


# ---- 보고 -------------------------------------------------------------------------------
def build_report(store: Store, baseline: dict | None = None, include_synthetic: bool = False) -> dict:
    """include_synthetic=False(기본): 합성 사례는 실제 사례 성능에 넣지 않는다(도구 검증 전용). 개발(dev) 사례의 결과는 최종 검증 성능이 아니다."""
    cases, fr, meta = store._read("cases", {}), store.frozen(), store.meta()
    rs_now = current_ruleset()
    sets: dict[str, list[dict]] = {"dev": [], "validation": []}
    skipped = {"not_frozen": 0, "ruleset_changed": 0, "tampered": 0, "synthetic_excluded": 0}
    for cid, m in meta.items():
        if m["kind"] == "synthetic" and not include_synthetic:
            skipped["synthetic_excluded"] += 1
            continue
        rec = fr.get(cid)
        if not rec:
            skipped["not_frozen"] += 1
            continue
        if not verify_frozen(rec):
            skipped["tampered"] += 1
            continue
        if rec["ruleset_version"] != rs_now:
            skipped["ruleset_changed"] += 1
            continue
        p = dict(rec, birth_year=int(cases[cid]["birth_date"][:4]))
        sets[m["split"]].append({"id": cid, "time_conf": m["time_confidence"], "predictions": p, "events": store.events_for_compare(cid), "observation": m["observation"]})
    log = store.eval_log()
    contaminated = any(e["ruleset_version"] != rs_now for e in log if e.get("split") == "validation")
    out: dict = {"ruleset_version": rs_now, "skipped": skipped, "validation_contaminated": contaminated, "includes_synthetic": include_synthetic, "split": {},
                 "note": "개발(dev) 결과는 규칙을 고치는 데 쓴 사례의 결과이므로 최종 검증 성능이 아니다. 검증(validation) 결과만 일반화 논의에 쓸 수 있다."}
    for sp, items in sets.items():
        prim = [i for i in items if i["time_conf"] in PRIMARY_TIME_CONF]
        sec = [i for i in items if i["time_conf"] not in PRIMARY_TIME_CONF]
        part = {"cases": len(items), "primary_cases": len(prim), "secondary_cases(시각 C·D, 1차 제외)": len(sec),
                "distinct": distinctiveness([i["predictions"] for i in items]) if items else None,
                "tones": tone_distribution([i["predictions"] for i in items]) if items else None,
                "uncertainty": uncertainty_expression([i["predictions"] for i in items]) if items else None,
                "detection": {dom: {lv: detection_table(prim, dom, lv) for lv in ("any", "strong")} for dom in PRED_DOMAINS} if prim else {}}
        if baseline and prim:
            for dom, t in part["detection"].items():
                rate = baseline.get(dom)
                for lv, tab in t.items():
                    tab["lift_vs_population"] = (tab["precision"] / rate) if (rate and tab["precision"] is not None) else None
        part["verdict"] = judge(part, baseline is not None)
        out["split"][sp] = part
        if sp == "validation" and items:
            store.log_eval({"split": "validation", "ruleset_version": rs_now, "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "cases": len(items)})
    return out


def judge(part: dict, has_baseline: bool) -> dict:
    """결과 문장. 사건 구별 능력이 확인되지 않으면 그대로 '미확인'이라고 쓴다(실패가 아니라 결과). 예측 정확도라고 부르지 않는다."""
    det = part.get("detection") or {}
    if not part["primary_cases"]:
        return {"status": "미평가", "reason": "1차 분석 사례(시각 신뢰도 A·B)가 없습니다."}
    if not any(t["strong"]["cases_scored"] for t in det.values()):
        return {"status": "미평가", "reason": "관측 범위(사건을 빠짐없이 확인한 연도·분야)가 선언된 사례가 없어, 기록 없는 해를 '사건 없음'으로 쓸 수 없습니다."}
    enough = [(d, t["strong"]) for d, t in det.items() if t["strong"]["sufficient"]]
    if not enough:
        return {"status": "표본 부족", "reason": f"분야별 사건 해가 {MIN_EVENTS_FOR_CONCLUSION}개 미만이라 사건 구별 능력에 대한 결론을 내지 않습니다. 이 숫자를 예측 정확도로 해석하지 마세요."}
    hit = [d for d, t in enough if t["p_perm"] is not None and t["p_perm"] < 0.05 and (t["lift"] or 0) > 1]
    if hit:
        return {"status": "예비 단서(재현 필요)", "domains": hit, "reason": "해당 분야에서 무작위 배치보다 높은 일치가 관찰되었으나 표본이 작고 검증용 재현 전에는 일반화할 수 없습니다."}
    return {"status": "구별 능력 미확인", "reason": "충분한 표본에서도 무작위 배치와 구별되는 일치가 관찰되지 않았습니다. 이 경우 사건 예측이 아니라 전통 해석을 통한 자기 이해·상담 용도로 위치를 정하는 것이 타당합니다."}
