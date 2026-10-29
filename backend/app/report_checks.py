"""knowledge/17 §5.1 자동 검사 L01~L12 (결정론적, LLM 미사용).

계산 엔진이 아니다: 이미 주어진 간지/주장과 보고서 텍스트의 정합성만 검사한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"

STEMS = "甲乙丙丁戊己庚辛壬癸"
_ELEMENT = {s: e for s, e in zip(STEMS, "木木火火土土金金水水")}
_GENERATES = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
_CONTROLS = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

# 지장간 표는 판본/학파 차이가 있다(15 I07). 아래는 검사용 '프로필' 하나이며 고전 확정값이 아니다.
HIDDEN_STEMS_PROFILE = {
    "子": "癸", "丑": "己癸辛", "寅": "甲丙戊", "卯": "乙", "辰": "戊乙癸", "巳": "丙庚戊",
    "午": "丁己", "未": "己丁乙", "申": "庚壬戊", "酉": "辛", "戌": "戊辛丁", "亥": "壬甲",
}

FIXED_DISCLAIMER = "명리학은 과학적으로 검증된 미래 예측 방법이 아닙니다"
CLAIM_LABELS = ("[검증]", "[원전]", "[주석]", "[전통해석]", "[현대추론]", "[일반 상식]", "[합성]")
DOMAIN_HEADINGS = ("성격", "재물", "직업", "문서", "가족", "건강", "대운")
QUOTE_HOLD_FILES = ("05_적천수_청탁_순역_원류_통관.md",)  # 원문 인용 보류 (L10)

FORBIDDEN_PATTERNS = [
    r"반드시", r"틀림없이", r"할 것입니다", r"하게 됩니다\.", r"액운", r"큰 화를", r"살이 끼",
    r"부적", r"굿이 필요", r"사망", r"이혼(하게|합니다|할 )", r"암에? 걸", r"파산(합니다|할 것)",
]
VERIFY_CLAIMS = re.compile(r"(검산(을|이)? (완료|끝)|계산(이|을)? (완료|끝났|정확)|만세력으로 (확인|검증)했)")
LUCK_NUMBER = re.compile(r"(대운[^\n]{0,30}?\d{1,2}\s*세|\d{1,2}\s*세(부터|에)[^\n]{0,15}대운)")


@dataclass
class Finding:
    check: str
    ok: bool
    detail: str = ""


def ten_god(day_stem: str, other: str) -> str:
    d, o = _ELEMENT[day_stem], _ELEMENT[other]
    same = (STEMS.index(day_stem) % 2) == (STEMS.index(other) % 2)
    if d == o:
        return "比肩" if same else "劫財"
    if _GENERATES[o] == d:
        return "偏印" if same else "正印"
    if _GENERATES[d] == o:
        return "食神" if same else "傷官"
    if _CONTROLS[d] == o:
        return "偏財" if same else "正財"
    if _CONTROLS[o] == d:
        return "七殺" if same else "正官"
    raise ValueError("unreachable")


def l01_ten_gods(day_stem: str, claimed: dict[str, str]) -> Finding:
    bad = {s: (c, ten_god(day_stem, s)) for s, c in claimed.items() if ten_god(day_stem, s) != c}
    return Finding("L01", not bad, f"불일치(주장,재계산)={bad}" if bad else "")


def l02_hidden_stems(claimed: dict[str, str]) -> Finding:
    bad = {b: (c, HIDDEN_STEMS_PROFILE[b]) for b, c in claimed.items() if HIDDEN_STEMS_PROFILE.get(b) != c}
    return Finding("L02", not bad, f"불일치={bad}" if bad else "")


BRANCH_SEASON = {"寅": "봄", "卯": "봄", "辰": "봄", "巳": "여름", "午": "여름", "未": "여름",
                 "申": "가을", "酉": "가을", "戌": "가을", "亥": "겨울", "子": "겨울", "丑": "겨울"}

# 계산 오류(L01~L03 등)와 해석 오류를 분리 기록하기 위한 분류 (보강 지시 §3)
CALC_CHECKS = {"L01", "L02", "L03", "X05", "X06"}


def error_kind(check_id: str) -> str:
    return "calculation" if check_id in CALC_CHECKS else "interpretation"


def l03_month_season(month_branch: str, claimed_season: str) -> Finding:
    season = BRANCH_SEASON[month_branch]
    return Finding("L03", season == claimed_season, f"정답={season}, 주장={claimed_season}")


def l04_verification_claims(text: str, status: str) -> Finding:
    if status == "V1":
        return Finding("L04", True)
    hit = VERIFY_CLAIMS.search(text)
    return Finding("L04", hit is None, f"{status}인데 '{hit.group(0)}'" if hit else "")


def l05_luck_numbers(text: str, luck_profile: str) -> Finding:
    if luck_profile != "unset":
        return Finding("L05", True)
    hit = LUCK_NUMBER.search(text)
    return Finding("L05", hit is None, f"프로필 미설정인데 '{hit.group(0)}'" if hit else "")


def l06_three_yongshin(text: str) -> Finding:
    missing = [k for k in ("격국용신", "억부용신", "조후용신") if k not in text]
    return Finding("L06", not missing, f"누락={missing}" if missing else "")


def l07_forbidden(text: str) -> Finding:
    hits = [p for p in FORBIDDEN_PATTERNS if re.search(p, text)]
    return Finding("L07", not hits, f"금지표현={hits}" if hits else "")


def l08_labels(text: str) -> Finding:
    """도메인 제목 아래 섹션마다 라벨이 하나 이상 있는지."""
    sections = re.split(r"^#{2,4}\s+", text, flags=re.M)[1:]
    missing = []
    for sec in sections:
        title = sec.splitlines()[0]
        if any(d in title for d in DOMAIN_HEADINGS) and not any(l in sec for l in CLAIM_LABELS):
            missing.append(title.strip())
    return Finding("L08", not missing, f"라벨 없음={missing}" if missing else "")


def allowed_quotes() -> set[str]:
    """knowledge/*.md 의 「」 인용(보류 표기 제외)."""
    out: set[str] = set()
    for f in KNOWLEDGE_DIR.glob("*.md"):
        if f.name.startswith(("16_", "17_")):
            continue
        out.update(q for q in re.findall(r"「([^」]+)」", f.read_text(encoding="utf-8")) if "보류" not in q)
    return out


def l09_quotes(text: str, allowed: set[str] | None = None) -> Finding:
    allowed = allowed_quotes() if allowed is None else allowed
    bad = [q for q in re.findall(r"「([^」]+)」", text) if q not in allowed]
    return Finding("L09", not bad, f"허용 목록에 없는 인용={bad}" if bad else "")


def l10_held_quotes(text: str) -> Finding:
    """05 청탁·원류·통관 항목에는 인용이 없어야 하므로 해당 용어 근처 한문 인용을 금지."""
    pat = re.compile(r"(청탁|淸濁|清濁|원류|源流|통관|通關)[^\n]{0,80}「[^」]+」")
    hit = pat.search(text)
    return Finding("L10", hit is None, f"인용 보류 항목에 인용: {hit.group(0)[:40]}" if hit else "")


def l11_source_refs(text: str) -> Finding:
    """'근거: NN 항목명' 의 NN 파일이 존재하고 항목명이 해당 파일에 있는지."""
    bad = []
    for num, title in re.findall(r"근거:\s*(\d{2})\s+([^)\n·,;]+)", text):
        files = list(KNOWLEDGE_DIR.glob(f"{num}_*.md"))
        title = title.strip()
        if not files or title not in files[0].read_text(encoding="utf-8"):
            bad.append(f"{num} {title}")
    return Finding("L11", not bad, f"존재하지 않는 근거={bad}" if bad else "")


def l12_disclaimer(text: str) -> Finding:
    return Finding("L12", FIXED_DISCLAIMER in text)


def run_text_checks(text: str, status: str, luck_profile: str) -> list[Finding]:
    return [
        l04_verification_claims(text, status), l05_luck_numbers(text, luck_profile),
        l06_three_yongshin(text), l07_forbidden(text), l08_labels(text),
        l09_quotes(text), l10_held_quotes(text), l11_source_refs(text), l12_disclaimer(text),
    ]
