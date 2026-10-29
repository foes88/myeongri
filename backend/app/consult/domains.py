"""상담 분야 정의, 자유 질문 라우팅, 사건 유형 판단 규약, 금지 질문 거절.

사건 유형 ↔ 구조 대응은 구현자 규약(고전 원문 대조 전)이다. 사전 분석 기록(precommit)에 들어간 유형만 판단 대상이 되며,
상담 중에 새로운 사건 유형을 사후에 추가해 '적중'으로 세지 않는다.
"""
from __future__ import annotations

import re

DOMAINS = {
    "overall": {"name": "종합운", "structures": ["식상생재", "재생관", "관인상생", "살인상생", "상관견관", "군겁쟁재"], "events": []},
    "wealth": {"name": "재물운", "structures": ["식상생재", "재생관", "군겁쟁재"], "events": ["자산 취득", "수입 변화", "재무 손실"]},
    "career": {"name": "직업·승진운", "structures": ["재생관", "관인상생", "살인상생", "상관견관"], "events": ["취업·이직", "직무 변화", "평가·승진 관련 변화"]},
    "business": {"name": "사업운", "structures": ["식상생재", "군겁쟁재", "상관견관"], "events": ["사업 시작", "사업 확장·축소"]},
    "docs_realestate": {"name": "문서·부동산운", "structures": ["관인상생", "살인상생"], "events": ["계약·문서 변화", "부동산 거래"]},
    "luck": {"name": "대운·세운", "structures": [], "events": []},
    # v6.6: 궁위·십성 신호 기반 분야(생극제화 구조 대신 compose_domains.domain_extra 사용)
    "job_change": {"name": "이직·취업운", "structures": ["재생관", "관인상생", "살인상생"], "events": ["취업·이직"], "kind": "palace"},
    "love_marriage": {"name": "연애·결혼운", "structures": [], "events": ["연애·결혼 관련 변화"], "kind": "palace"},
    "family": {"name": "가족·인간관계운", "structures": [], "events": ["가족·관계 변화"], "kind": "palace"},
    "health_traditional": {"name": "건강 관련 전통 해석", "structures": [], "events": [], "kind": "palace"},
    "real_estate": {"name": "부동산운", "structures": ["식상생재", "관인상생"], "events": ["부동산 거래"], "kind": "palace"},
}
SPECIAL_EVENTS = ("연애·결혼 관련 변화", "가족·관계 변화")
EVENT_RULE = {  # 사건 유형 → (근거 구조들, 보조 십성군)
    "자산 취득": (["식상생재", "재생관"], ["재성"]), "수입 변화": (["식상생재", "재생관"], ["재성"]), "재무 손실": (["군겁쟁재"], []),
    "취업·이직": (["재생관", "관인상생", "살인상생"], ["관성"]), "직무 변화": (["재생관", "관인상생", "살인상생"], ["관성", "인성"]),
    "평가·승진 관련 변화": (["관인상생", "재생관"], ["관성", "인성"]),
    "사업 시작": (["식상생재"], ["식상"]), "사업 확장·축소": (["식상생재", "군겁쟁재"], ["식상", "재성"]),
    "계약·문서 변화": (["관인상생", "살인상생"], ["인성"]), "부동산 거래": (["식상생재", "관인상생"], ["재성", "인성"]),
    "연애·결혼 관련 변화": ([], []), "가족·관계 변화": ([], []),  # 궁위·십성 신호로 별도 판단(special_event_state)
}
ROUTES = [
    ("wealth", r"재물|돈|재산|수입|월급|저축|빚|손실|투자"), ("career", r"직업|직장|취업|이직|승진|회사|커리어|퇴사"),
    ("business", r"사업|창업|장사|가게|동업"), ("docs_realestate", r"문서|계약|부동산|집|전세|매매|이사|토지"),
    ("luck", r"대운|세운|올해|내년|\b20[2-4]\d\b|년운|운세 흐름"),
    ("job_change", r"이직|취업|퇴사|구직|전직"), ("love_marriage", r"연애|결혼|배우자|이성|애인|짝|소개팅"),
    ("family", r"가족|부모|자녀|아이|형제|인간관계|동료|친구|시댁|처가"), ("health_traditional", r"건강운|건강 흐름|컨디션|체력"),
    ("real_estate", r"부동산|집 구|집을|전세|매매|토지|이사"),
]
REFUSALS = [
    (r"사망|죽을|수명|언제 죽", "death", "수명이나 사망 시기는 명리 해석으로 다루지 않습니다."),
    (r"암|병에|질병|진단|수술|아프", "health", "건강 상태의 진단이나 예측은 제공하지 않습니다. 건강이 걱정되면 의료진과 상담하세요."),
    (r"수익.{0,6}보장|무조건 오|반드시 오|로또|당첨|코인.{0,6}(오를|대박)|주식.{0,6}(오를|사야)", "investment", "투자 수익이나 당첨을 보장하거나 특정 종목을 권하는 해석은 하지 않습니다."),
    (r"확실히 승진|무조건 승진|승진 확정|합격 확정", "certainty", "승진·합격 같은 결과를 확정하는 해석은 하지 않습니다."),
]


def route(question: str, chosen: list[str] | None) -> list[str]:
    out = list(chosen or [])
    for dom, pat in ROUTES:
        if re.search(pat, question or "") and dom not in out:
            out.append(dom)
    return out or ["overall"]


def refusal(question: str) -> dict | None:
    for pat, kind, msg in REFUSALS:
        if re.search(pat, question or ""):
            return {"kind": kind, "message": msg, "alternative": "원국 구조와 대운·세운의 전통 해석을 쉬운 말로 설명해 드릴 수 있습니다."}
    return None


def extract_years(question: str) -> list[int]:
    return sorted({int(y) for y in re.findall(r"(20[2-4]\d)\s*년?", question or "")})


GLOSSARY = {
    "식상생재": "식신·상관(표현·기술의 기운)이 재성(재물·현실 자원의 기운)을 돕는 구조를 말하는 전통 용어",
    "재생관": "재성이 관성(직책·규율의 기운)을 돕는 구조", "관인상생": "관성이 인성(학문·문서·보호의 기운)을 돕는 구조",
    "살인상생": "칠살(강한 압박의 기운)을 인성이 누그러뜨려 도와주는 구조", "상관견관": "상관과 정관이 함께 있어 부딪히는 구조(통관·제어 여부를 따로 봄)",
    "군겁쟁재": "비겁(나와 같은 기운)이 여럿이어서 재성을 나누어 가진다고 보는 구조", "대운": "10년 단위로 바뀌는 큰 흐름의 기둥",
    "세운": "해마다 바뀌는 기둥(입춘을 기준으로 바뀜)", "격국": "월령에서 취한 십성 구조의 틀", "용신": "명식의 균형에 필요하다고 보는 기운(학파별로 정의가 다름)",
    "통근": "천간이 지지에 뿌리를 두었다고 보는 것",
}
