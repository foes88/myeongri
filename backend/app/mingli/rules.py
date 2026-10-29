"""Mingli-Graph 1·2층 규칙 레지스트리.

source 는 저장소 knowledge/ 문서 위치만 가리킨다. 고전 원문(子平真詮·滴天髓 등) 대조는 '미완료'이며 classical_verification 에
그대로 기록한다. 원전 검증 전에는 이 규칙을 '고전이 이렇게 말한다'로 표현하지 않는다(해석 구조 규칙으로만 사용).
"""
from __future__ import annotations

RULESET_VERSION = "mingli-l12-0.1.0"


def _src(file: str, loc: str = "") -> list[dict]:
    return [{"type": "repo_knowledge", "file": f"knowledge/{file}", "location": loc, "classical_verification": "pending"}]


_K04, _K06, _K13, _K15 = ("04_적천수_기세_왕쇠_통근.md", "06_자평진전_월령_격국_용신.md", "13_합충형파해_우선순위.md", "15_논쟁_불충분근거_목록.md")

RULES: dict[str, dict] = {
    "MG-L1-WOLRYEONG": {"school_id": "common", "name": "월령(월지) 확인", "sources": _src(_K04, "월령과 기세의 우선순위"),
                        "formula": "month_branch → season, element, hidden stems(본·중·여기)"},
    "MG-L1-DEUKRYEONG-BONGI": {"school_id": "common_bongi", "name": "득령(월지 본기 기준)", "sources": _src(_K06, "월령에서 용신 구함"),
                               "formula": "월지 본기가 일간의 비겁/인성이면 득령 근거, 중기·여기만이면 부분(논쟁), 아니면 실령 후보"},
    "MG-L1-DEUKRYEONG-SEASON": {"school_id": "common_season", "name": "득령(계절 오행 기준)", "sources": _src(_K04, "월령과 기세의 우선순위"),
                                "formula": "월지 오행이 일간 오행과 같거나 이를 생하면 득령 근거"},
    "MG-L1-HIDDEN-ROLE": {"school_id": "common", "name": "본기·중기·여기 구분", "sources": _src(_K15, "I07 지장간 표 이견"),
                          "formula": "프로필 문자열 순서 = 본기·중기·여기 (표는 판본마다 다름)"},
    "MG-L1-TONGGEUN": {"school_id": "jeokcheonsu", "name": "통근", "sources": _src(_K04, "통근"),
                       "formula": "천간과 같은 간(엄격) 또는 같은 오행(관대)이 지지 지장간에 있을 때 뿌리. 점수식은 원전에 없음"},
    "MG-L1-TUGAN": {"school_id": "zipyeong_jinjeon", "name": "투간(투출)", "sources": _src(_K06, "월지 지장간 투출"),
                    "formula": "월지 지장간의 글자가 천간(연·월·시)에 나타남. 일간은 별도 표기"},
    "MG-L1-SUPPORT-ORDINAL": {"school_id": "eokbu", "name": "일간 도움 구조(순서형 후보)", "sources": _src(_K04, "월령/뿌리/도움/제어·소모·설기"),
                              "formula": "득령 + 엄격 통근 + 천간 도움(비겁·인성)으로 강/약/중간 후보. 수치 가중치 없음"},
    "MG-L2-STEM-HAP": {"school_id": "common", "name": "천간합 존재", "sources": _src(_K13, "검토 순서"),
                       "formula": "甲己 乙庚 丙辛 丁壬 戊癸"},
    "MG-L2-HAP-HWA": {"school_id": "common", "name": "합화 성립 조건(후보 판정만)", "sources": _src(_K13, "절대규칙 금지"),
                      "formula": "인접·월령 뒷받침·화신 뿌리/투출·경합 없음·극신 없음. 어느 조건도 '반드시 化' 로 쓰지 않음"},
    "MG-L2-BRANCH-YUKHAP": {"school_id": "common", "name": "지지 육합", "sources": _src(_K13), "formula": "子丑 寅亥 卯戌 辰酉 巳申 午未"},
    "MG-L2-SAMHAP": {"school_id": "common", "name": "지지 삼합/반합/공합", "sources": _src(_K13), "formula": "申子辰 亥卯未 寅午戌 巳酉丑"},
    "MG-L2-BANGHAP": {"school_id": "common", "name": "지지 방합", "sources": _src(_K13), "formula": "寅卯辰 巳午未 申酉戌 亥子丑"},
    "MG-L2-CHUNG": {"school_id": "common", "name": "지지 충", "sources": _src(_K13, "합성 예"), "formula": "子午 丑未 寅申 卯酉 辰戌 巳亥"},
    "MG-L2-HYUNG": {"school_id": "common", "name": "지지 형", "sources": _src(_K13, "형·파·해의 학파별 차이"), "formula": "寅巳申 丑戌未 子卯 자형(辰午酉亥)"},
    "MG-L2-PA": {"school_id": "common", "name": "지지 파", "sources": _src(_K13), "formula": "子酉 丑辰 寅亥 卯午 巳申 未戌"},
    "MG-L2-HAE": {"school_id": "common", "name": "지지 해", "sources": _src(_K13), "formula": "子未 丑午 寅巳 卯辰 申亥 酉戌"},
    "MG-L2-GOGO": {"school_id": "common", "name": "개고·입묘 후보", "sources": _src(_K13, "합충형파해"), "formula": "辰=水庫 戌=火庫 丑=金庫 未=木庫"},
    "MG-L2-COMPETITION": {"school_id": "common", "name": "합충 경합(탐합망충 등) 검토", "sources": _src(_K13, "검토 순서"),
                          "formula": "한 글자가 합과 충 양쪽에 걸리면 어느 작용이 우선하는지 학파 논쟁으로 기록"},
}
_K07, _K08, _K09, _K12, _K03 = ("07_자평진전_성격_파격_구응.md", "08_궁통보감_조후_한난조습.md", "09_연해자평_십성_전통격.md", "12_대운_세운_전통과_계산.md", "03_일간_월령_십성_기초.md")
RULES.update({
    "MG-L3-SIKSANG-SAENGJAE": {"school_id": "common", "name": "식상생재", "sources": _src(_K09, "십성 전통격"), "formula": "식상(食神·傷官) → 재성 경로의 출현 정도"},
    "MG-L3-JAE-SAENGGWAN": {"school_id": "common", "name": "재생관", "sources": _src(_K09, "십성 전통격"), "formula": "재성 → 관성 경로의 출현 정도"},
    "MG-L3-GWAN-INSAENG": {"school_id": "common", "name": "관인상생", "sources": _src(_K09, "십성 전통격"), "formula": "관성 → 인성 경로의 출현 정도"},
    "MG-L3-SAL-INSAENG": {"school_id": "common", "name": "살인상생", "sources": _src(_K09, "십성 전통격"), "formula": "七殺 → 인성 경로의 출현 정도"},
    "MG-L3-SANGGWAN-GYEONGWAN": {"school_id": "common", "name": "상관견관", "sources": _src(_K07, "성패와 구응"), "formula": "傷官과 正官의 동시 출현(충돌형)"},
    "MG-L3-GUNGEOP-JAENGJAE": {"school_id": "common", "name": "군겁쟁재", "sources": _src(_K09, "십성 전통격"), "formula": "비겁 2개 이상(본기 이상)과 재성"},
    "MG-L3-CHAIN": {"school_id": "common", "name": "생극 경로 연쇄", "sources": _src(_K07, "성패와 구응"), "formula": "인접 구조가 모두 존재하면 연쇄 후보 간선을 남김"},
    "MG-L4-GYEOKGUK-CAND": {"school_id": "zipyeong_jinjeon", "name": "월령 격국 후보", "sources": _src(_K06, "월령에서 용신 구함"),
                            "formula": "월지 지장간 중 투출한 글자 우선(본기→중기→여기), 투출 없으면 본기. 본기 중심 설과 병렬 기록"},
    "MG-L4-GYEOKGUK-BONGI": {"school_id": "bongi_centered", "name": "격국 후보(본기 중심 병렬)", "sources": _src(_K06, "월령에서 용신 구함"), "formula": "월지 본기의 십성으로 격 이름"},
    "MG-L4-SEONGPA": {"school_id": "zipyeong_jinjeon", "name": "성격·파격·구응 후보", "sources": _src(_K07, "성패와 구응"),
                      "formula": "격별 성격/파격/구응 조건표(구현자 단순화, 원전 조건과 동일하다고 주장하지 않음)"},
    "MG-L4-GEUKGUK-YONGSHIN": {"school_id": "zipyeong_jinjeon", "name": "격국용신 후보", "sources": _src(_K06, "월령에서 용신 구함"), "formula": "성격 요소 또는 구응 요소의 십성군"},
    "MG-L4-EOKBU-YONGSHIN": {"school_id": "eokbu", "name": "억부용신 후보", "sources": _src(_K04, "월령/뿌리/도움/제어·소모·설기"), "formula": "일간 강/약 후보에 따른 십성군 방향"},
    "MG-L4-JOHU-DIRECTION": {"school_id": "gungtongbogam", "name": "조후 방향(한난조습)", "sources": _src(_K08, "한난조습의 공통 원칙"),
                             "formula": "월지 계절의 한·난 방향과 오행 집계. 일간×월지 궁통보감 개별 표는 미구현"},
    "MG-L4-YONGSHIN-CONFLICT": {"school_id": "common", "name": "용신 후보 간 충돌 기록", "sources": _src(_K08, "한난조습의 공통 원칙"), "formula": "격국·억부·조후 후보가 겹치지 않으면 하나로 합치지 않고 충돌로 기록"},
    "MG-L5-LUCK-STEM": {"school_id": "common", "name": "운 천간 십성·합", "sources": _src(_K12, "해석 순서"), "formula": "운 천간의 일간 기준 십성과 원국 천간과의 합"},
    "MG-L5-LUCK-BRANCH": {"school_id": "common", "name": "운 지지와 원국 지지의 관계", "sources": _src(_K13, "검토 순서"), "formula": "육합·충·형·파·해, 삼합/방합 완성 후보"},
    "MG-L5-STRUCTURE-DELTA": {"school_id": "common", "name": "원국 대비 구조 변화", "sources": _src(_K12, "해석 순서"), "formula": "운 글자를 추가해 Layer 3 구조 순위가 바뀌는지 비교"},
    "MG-L5-SEGMENT": {"school_id": "common", "name": "대운 교체·입춘 구간 분리", "sources": _src(_K12, "경계 시험"), "formula": "대운 교체일과 입춘(세운 경계)으로 한 해를 구간 분리"},
    "MG-L5-COMPARE": {"school_id": "common", "name": "복수 연도 비교 데이터", "sources": _src(_K12, "해석 순서"), "formula": "연도별 특징을 점수 없이 나란히 제시"},
})
for _id, _r in RULES.items():
    _r.setdefault("version", RULESET_VERSION)


# ---------------------------------------------------------------------------------------------
# v6.5: 고전 원문 검증 상태 연결 (golden/classical_verification.json → classical.py)
#  text_confirmed          : 표시한 범위에서 원문이 규칙 내용을 뒷받침함을 사람이 읽고 확인(scope_note 필수)
#  location_confirmed      : 출처 장·핵심어 위치만 확인. 규칙 내용이 원문에 있다고 주장하지 않음
#  implementer_convention  : 고전 주장 없음(구현자 규약) — 고전 원문으로 위장하지 않는다
#  pending                 : 확인 못함(fail-closed 기본값)
CLASSICAL_STATES = ("text_confirmed", "location_confirmed", "implementer_convention", "pending")

# 원문(또는 후대 주석)과 구현이 어떻게 다른지. kind: conflict(원문과 충돌) / simplified(구현 단순화) / later_concept(후대 개념을 원문에 투사) / partial(일부만 대응)
ENGINE_VS_CLASSICAL = {
    "MG-L2-PA": {"kind": "conflict", "note": "三命通會는 寅亥·巳申을 三合/六合으로 보아 破로 취하지 않음 — 구현 破 표(6쌍)의 두 쌍과 충돌", "profile": "pa_profile"},
    "MG-L2-HYUNG": {"kind": "partial", "note": "子平真詮 저자가 三刑을 闕疑(보류)로 둠 — 구현은 형을 '존재 후보'로만 기록하고 작용을 확정하지 않음. 자형은 profiles.hyung=no_self 로 제외 가능(任氏曰 俗謬)"},
    "MG-L2-HAE": {"kind": "partial", "note": "任氏曰이 害(穿)에 회의적이고 寅亥·寅巳 분류가 자료마다 다름 — 구현은 존재만 기록"},
    "MG-L2-HAP-HWA": {"kind": "partial", "note": "間隔·원격(半合)·得時乘令/局全은 원문 확인 후 v6.6 구현 반영. 쟁합·극신 조건은 원문 대응 미확인(구현자 보강)"},
    "MG-L2-BANGHAP": {"kind": "partial", "note": "3글자 方(寅卯辰 등 4조)은 滴天髓 方局論·任氏曰로 확인. 2글자 부분 방합은 원문 없음(엔진은 contested 기록만)"},
    "MG-L1-DEUKRYEONG-BONGI": {"kind": "later_concept", "note": "'본기가 비겁·인성이면 득령'은 후대 신강약 개념. 원문은 得令 개념어까지만 확인"},
    "MG-L1-DEUKRYEONG-SEASON": {"kind": "later_concept", "note": "계절 오행 기준 득령은 원문 대응 미확인(寒暖論 위치만)"},
    "MG-L4-GYEOKGUK-BONGI": {"kind": "partial", "note": "'甲為本主'만 확인. 본기 중심 격국은 구현상 병렬 대안이며 원문은 투출 우선에 가까움"},
    "MG-L4-SEONGPA": {"kind": "simplified", "note": "원문 成敗救應 절의 조건표를 구현자가 단순화함 — 동일하지 않음"},
    "MG-L4-EOKBU-YONGSHIN": {"kind": "school_variant", "note": "억부는 滴天髓 衰旺論·徐樂吾 評註 계통의 학파 입장(沈孝瞻 격국론과 묻는 질문이 다름)"},
    "MG-L1-TONGGEUN": {"kind": "partial", "note": "寅卯=木 통근 개념은 주석(任氏曰)에서 확인. 엄격/관대·강중약 등급은 구현 규약. 十二運 기준은 profiles.tonggeun=twelve_stage 로 선택"},
    "MG-L2-SAMHAP": {"kind": "partial", "note": "원문은 申子辰을 '三會'라 부름(용어 차이). 반합·공합 구분은 구현 확장"},
    "MG-L2-COMPETITION": {"kind": "partial", "note": "합이 충을 푼다는 입장(합 우선설)만 직접 뒷받침. 충 우선설 등은 구현이 병렬로 남김"},
}
PROFILES = {"pa_profile": {"modern_6": "현대 통용 破 6쌍(子酉 丑辰 寅亥 卯午 巳申 未戌)", "sanmyeongtonghoe_4": "三命通會: 寅亥·巳申은 합으로 보아 破에서 제외(4쌍)"}}


def _merge_classical() -> None:
    from . import classical
    for rid, r in RULES.items():
        e = classical.entry(rid)
        st = classical.classical_status(rid)
        label = "implementer_convention" if st == "implementation_convention" else st
        r["classical_status"] = label
        for src in r["sources"]:
            src["classical_verification"] = label
        r["classical_claim"] = label in ("text_confirmed", "location_confirmed")
        if r["classical_claim"] and e:
            r["sources"].append({"type": "classical_text", "work": e.get("work"), "section": e.get("section"), "url": e.get("url"),
                                 "accessed": e.get("accessed"), "status": label, "original_excerpt": e.get("original_excerpt"),
                                 "commentary_excerpt": e.get("commentary_excerpt"), "scope_note": e.get("scope_note"),
                                 "classical_verification": label})
        r["school_conditions"] = e.get("school_conditions")
        r["engine_vs_classical"] = ENGINE_VS_CLASSICAL.get(rid)


def detect_conflicts() -> list[dict]:
    """원문(또는 후대 주석)과 구현이 충돌·단순화·후대 개념 투사인 규칙을 찾는다. 구현자 규약은 대상이 아니다(고전 주장이 없으므로)."""
    out = []
    for rid, r in RULES.items():
        ev = r.get("engine_vs_classical")
        if ev and r.get("classical_claim"):
            out.append({"rule_id": rid, "kind": ev["kind"], "note": ev["note"], "classical_status": r["classical_status"]})
    return out


_merge_classical()
