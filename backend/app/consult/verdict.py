"""결론형 상담(사용자용 계층). 엔진의 구조·시기 변화를 '그래서 어떤가'에 답하는 문장으로 바꾼다.

- 사용자 문장에는 전문 용어·규칙 번호·claim_id·한자를 쓰지 않는다. 근거는 answer["verdict"]["internal"] 에 그대로 보존한다(사용자 응답에서는 제외).
- 어조(tone)는 엔진이 실제로 계산한 구조 변화에서 정한다: 돕는 흐름이 커지는가(S), 부딪히거나 나누는 흐름이 커지는가(T).
  이 점수화는 구현자 규약이며(고전 원문 규칙 아님) 사용자 문장에도 '읽는 방식'이라고 밝힌다.
- 근거가 없으면 만들어 내지 않고 '근거 부족'이라고 말한다. 사건·수입·승진·계약 결과를 단정하지 않는다.
- 분야마다 문장 틀·관점·반대 근거가 다르다(같은 문장에서 분야 이름만 바꾸지 않는다).
"""
from __future__ import annotations

import hashlib

from . import compose_domains as CD
from . import explain as E
from . import facts as FA
from . import domains as D
from . import months as MO
from . import judge as JD
from . import profile as PF
from . import readings as R
from . import synthesis as S

VERDICT_VERSION = "verdict-0.2.0"
TONE_SHORT = {"opportunity": "기회를 살리기 좋은 흐름", "mixed": "기회와 점검할 점이 함께 오는 흐름", "cautious": "서두르기보다 다지는 흐름", "quiet": "큰 변화 없이 이어지는 흐름",
              "thin": "말할 근거가 부족한 흐름", "steady": "안정적으로 이어지는 흐름", "balance": "생활 균형을 돌아보는 흐름"}

# 분야별로 구조를 부르는 쉬운 말(전문 용어 없음)
THEMES = {
    "overall": {"식상생재": "능력이 수입으로 이어지는 흐름", "재생관": "쌓은 기반이 직책·평가로 이어지는 흐름", "관인상생": "조직 안에서 신뢰와 도움을 얻는 흐름",
              "살인상생": "압박을 준비와 조력으로 풀어 가는 흐름", "상관견관": "자기 주장이 규칙·조직과 부딪히기 쉬운 흐름", "군겁쟁재": "이익을 나누거나 다투기 쉬운 흐름"},
    "wealth": {"식상생재": "능력이 수입으로 이어지는 흐름", "재생관": "수입 기반이 안정된 자리로 이어지는 흐름", "군겁쟁재": "수입을 나누거나 새어 나가기 쉬운 흐름"},
    "career": {"재생관": "쌓은 실적이 직책·평가로 이어지는 흐름", "관인상생": "조직 안에서 신뢰와 도움을 얻는 흐름", "살인상생": "압박을 준비와 조력으로 풀어 가는 흐름",
             "상관견관": "자기 주장이 조직의 규칙과 부딪히기 쉬운 흐름"},
    "business": {"식상생재": "아이디어·기술이 수익으로 이어지는 흐름", "군겁쟁재": "동업·경쟁 상대와 이익을 나누기 쉬운 흐름", "상관견관": "자기 방식이 거래처·제도와 부딪히기 쉬운 흐름"},
    "job_change": {"재생관": "쌓은 실적이 새 자리의 평가로 이어지는 흐름", "관인상생": "새 조직에서도 신뢰와 도움을 얻는 흐름", "살인상생": "환경 변화의 압박을 준비로 풀어 가는 흐름"},
    "docs_realestate": {"관인상생": "계약·문서가 제도 안에서 안정적으로 처리되는 흐름", "살인상생": "까다로운 절차를 준비와 도움으로 넘기는 흐름"},
    "real_estate": {"식상생재": "능력이 자산 형성으로 이어지는 흐름", "관인상생": "거래·문서가 안정적으로 처리되는 흐름"},
}
PAL_PLAIN = {"year": "태어난 해의 자리(어린 시절·집안)", "month": "태어난 달의 자리(사회·직업)", "day": "태어난 날의 자리(자기 자신·배우자)", "hour": "태어난 시의 자리(자녀·말년)"}
PAL_DOM = CD.DOMAIN_PALACES

HEAD = {
    "wealth": {
        "opportunity": "{w}은 능력이 수입으로 이어지기 쉬운 흐름이 보이는 시기입니다. 재물 면에서 기회를 살펴볼 만합니다.",
        "mixed": "{w}에는 수입으로 이어질 기회와 함께 나누거나 새어 나가기 쉬운 부분도 커집니다. 버는 것만큼 지키는 것을 살펴볼 시기로 읽힙니다.",
        "cautious": "{w}은 재물 면에서 무리하게 늘리기보다 점검하고 정리하기에 어울리는 흐름으로 읽힙니다.",
        "quiet": "{w}은 재물 흐름이 타고난 모습에서 크게 달라지지 않는 시기입니다. 큰 기회나 큰 위험이 두드러지지는 않습니다.",
        "thin": "이 사주에서는 {w} 재물 흐름에 대해 뚜렷하게 말할 수 있는 근거가 부족합니다."},
    "career": {
        "opportunity": "{w}은 노력이 평가와 자리로 이어지기 쉬운 흐름이 보이는 시기입니다. 직장·승진 문제를 적극적으로 살펴볼 만합니다.",
        "mixed": "{w}에는 평가와 자리로 이어질 기회와 함께 조직과 부딪히기 쉬운 부분도 커집니다. 실적을 쌓으면서 관계를 조율하는 균형이 중요한 시기로 읽힙니다.",
        "cautious": "{w}은 직장에서 서두르기보다 지금 자리를 다지고 준비하는 쪽이 어울리는 흐름으로 읽힙니다.",
        "quiet": "{w}은 직업 흐름이 타고난 모습에서 크게 달라지지 않는 시기입니다.",
        "thin": "이 사주에서는 {w} 직업·승진 흐름에 대해 뚜렷하게 말할 수 있는 근거가 부족합니다."},
    "business": {
        "opportunity": "{w}은 아이디어와 기술이 수익으로 이어지기 쉬운 흐름이 보이는 시기입니다. 사업을 구상하거나 넓히는 일을 살펴볼 만합니다.",
        "mixed": "{w}에는 수익 기회와 함께 동업·경쟁 상대와 이익을 나누기 쉬운 부분도 커집니다. 확장보다 조건과 배분을 분명히 하는 쪽이 어울립니다.",
        "cautious": "{w}은 사업을 크게 벌이기보다 구조를 점검하고 지키는 쪽이 어울리는 흐름으로 읽힙니다.",
        "quiet": "{w}은 사업 흐름이 타고난 모습에서 크게 달라지지 않는 시기입니다.",
        "thin": "이 사주에서는 {w} 사업 흐름에 대해 뚜렷하게 말할 수 있는 근거가 부족합니다."},
    "job_change": {
        "opportunity": "{w}은 자리를 옮기더라도 신뢰와 평가가 이어지기 쉬운 흐름이 보입니다. 이직은 살펴볼 만한 선택지로 읽히지만, 이직을 권한다는 뜻은 아닙니다.",
        "mixed": "{w}에는 이직을 뒷받침하는 흐름과 함께 환경 변화에 부담이 생기기 쉬운 부분도 있습니다. 옮기는 이유와 조건을 충분히 따져 볼 시기로 읽힙니다.",
        "cautious": "{w}은 이직처럼 큰 변화를 서두르기보다 지금 자리에서 준비를 갖추는 쪽이 어울리는 흐름으로 읽힙니다.",
        "quiet": "{w}은 이직과 관련해 뚜렷한 변화 신호가 두드러지지 않는 시기입니다. 이직 여부는 현실 조건이 더 큰 기준이 됩니다.",
        "thin": "이 사주에서는 {w} 이직 흐름에 대해 뚜렷하게 말할 수 있는 근거가 부족합니다."},
    "docs_realestate": {
        "opportunity": "{w}은 계약과 문서 일이 제도 안에서 비교적 순조롭게 처리되기 쉬운 흐름이 보입니다.",
        "mixed": "{w}에는 계약·문서 일이 순조로울 수 있는 흐름과 함께 절차에서 부딪히기 쉬운 부분도 있습니다. 조건과 서류를 꼼꼼히 확인할 시기로 읽힙니다.",
        "cautious": "{w}은 계약·문서 일을 서두르기보다 확인과 준비에 시간을 쓰는 쪽이 어울리는 흐름으로 읽힙니다.",
        "quiet": "{w}은 계약·문서 흐름이 타고난 모습에서 크게 달라지지 않는 시기입니다.",
        "thin": "이 사주에서는 {w} 계약·문서 흐름에 대해 뚜렷하게 말할 수 있는 근거가 부족합니다."},
    "real_estate": {
        "opportunity": "{w}은 능력과 노력이 자산을 쌓는 쪽으로 이어지기 쉬운 흐름이 보입니다. 부동산 문제를 차분히 살펴볼 만합니다.",
        "mixed": "{w}에는 자산을 쌓을 기회와 함께 절차나 조건에서 점검할 부분도 커집니다. 거래 조건과 서류를 꼼꼼히 확인할 시기로 읽힙니다.",
        "cautious": "{w}은 부동산 거래를 서둘러 결정하기보다 조건을 비교하고 준비하는 쪽이 어울리는 흐름으로 읽힙니다.",
        "quiet": "{w}은 부동산과 거처에 관한 흐름이 타고난 모습에서 크게 달라지지 않는 시기입니다.",
        "thin": "이 사주에서는 {w} 부동산 흐름에 대해 뚜렷하게 말할 수 있는 근거가 부족합니다."},
    "love_marriage": {
        "steady": "{w}은 가까운 관계가 비교적 안정적으로 이어지기 쉬운 흐름으로 읽힙니다.",
        "mixed": "{w}에는 관계를 이어 주는 요소와 함께 마찰이 생기기 쉬운 요소도 있습니다. 서로의 기대를 말로 맞추는 일이 중요한 시기로 읽힙니다.",
        "cautious": "{w}은 가까운 관계에서 부딪힘이나 거리감이 생기기 쉬운 흐름이 보입니다. 감정이 앞설 때 잠시 쉬어 가는 관점이 도움이 될 수 있습니다.",
        "quiet": "{w}은 연애·결혼 흐름이 타고난 모습에서 크게 달라지지 않는 시기입니다.",
        "thin": "이 사주에서는 {w} 연애·결혼 흐름에 대해 뚜렷하게 말할 수 있는 근거가 부족합니다."},
    "family": {
        "steady": "{w}은 가족·가까운 사람들과의 관계가 비교적 안정적으로 이어지기 쉬운 흐름으로 읽힙니다.",
        "mixed": "{w}에는 서로 의지가 되는 요소와 함께 의견이 엇갈리기 쉬운 요소도 있습니다. 거리와 역할을 조율하는 일이 중요한 시기로 읽힙니다.",
        "cautious": "{w}은 가족·주변 관계에서 오해나 부담이 쌓이기 쉬운 흐름이 보입니다. 서운함을 미루지 않고 이야기해 보는 관점이 도움이 될 수 있습니다.",
        "quiet": "{w}은 가족·인간관계 흐름이 타고난 모습에서 크게 달라지지 않는 시기입니다.",
        "thin": "이 사주에서는 {w} 가족·인간관계 흐름에 대해 뚜렷하게 말할 수 있는 근거가 부족합니다."},
    "health_traditional": {
        "balance": "건강은 이 해석으로 판단하거나 예측할 수 없습니다. 아래 내용은 생활 리듬과 균형을 돌아보는 참고일 뿐이며, 몸에 걱정되는 점은 의료진과 상의하세요."},
}
THINK = {
    "wealth": {
        "opportunity": ["일이나 기술을 수입으로 연결할 방법(성과급, 부수입, 새 수입원 등)을 구체적으로 점검해 볼 수 있습니다.", "기회가 보일수록 지출 계획을 함께 세워 두면 균형을 잡는 데 도움이 될 수 있습니다."],
        "mixed": ["수입을 늘리는 일과 함께 고정 지출, 동업·보증처럼 나누는 구조를 먼저 점검해 볼 수 있습니다.", "큰 결정은 한 번에 하기보다 나누어 진행하는 관점이 참고가 될 수 있습니다."],
        "cautious": ["새 투자나 확장보다 지금의 수입과 지출 구조를 정리해 보는 관점이 참고가 될 수 있습니다.", "다른 사람과 이익을 나누는 조건은 문서로 분명히 해 두는 것을 생각해 볼 수 있습니다."],
        "quiet": ["큰 변화가 없는 시기에는 장기 계획과 저축 습관을 다듬는 데 시간을 쓰는 관점을 생각해 볼 수 있습니다."],
        "thin": ["사주만으로 말할 수 있는 것이 적으니 실제 재무 상황과 계획을 우선 기준으로 삼는 편이 좋습니다."]},
    "career": {
        "opportunity": ["지금까지 쌓은 실적과 평판을 정리해 두고 인사·평가 시기에 맞춰 보여 줄 방법을 생각해 볼 수 있습니다.", "윗사람이나 선배의 조언을 구하는 일이 도움이 될 수 있습니다."],
        "mixed": ["성과를 내는 일과 함께 상사·동료와 의견을 조율하는 방식을 점검해 볼 수 있습니다.", "자기 주장을 전달할 때 시기와 방식을 고르는 관점이 참고가 될 수 있습니다."],
        "cautious": ["새 직무나 큰 변화를 서두르기보다 자격·경력을 보강하는 준비에 시간을 쓰는 관점을 생각해 볼 수 있습니다.", "조직의 규칙과 부딪히는 지점이 있다면 미리 정리해 두면 도움이 될 수 있습니다."],
        "quiet": ["뚜렷한 변화가 없는 시기에는 현재 일의 완성도를 높이는 데 집중하는 관점을 생각해 볼 수 있습니다."],
        "thin": ["사주만으로 말할 수 있는 것이 적으니 회사의 실제 상황과 본인의 계획을 우선 기준으로 삼는 편이 좋습니다."]},
    "business": {
        "opportunity": ["아이디어를 작게 시험해 보고 반응을 확인하는 방식으로 접근해 볼 수 있습니다.", "수익이 커질 때 비용과 세금 구조를 함께 점검해 두면 도움이 될 수 있습니다."],
        "mixed": ["동업이나 거래 조건(지분, 정산 방식)을 처음부터 문서로 분명히 해 두는 것을 생각해 볼 수 있습니다.", "확장은 단계를 나누어 진행하는 관점이 참고가 될 수 있습니다."],
        "cautious": ["규모를 키우기보다 현금 흐름과 거래처 구조를 점검하는 관점을 생각해 볼 수 있습니다."],
        "quiet": ["큰 변화가 없는 시기에는 운영 방식을 다듬고 기반을 넓히는 일에 시간을 쓰는 관점을 생각해 볼 수 있습니다."],
        "thin": ["사주만으로 말할 수 있는 것이 적으니 시장 상황과 자금 사정을 우선 기준으로 삼는 편이 좋습니다."]},
    "job_change": {
        "opportunity": ["옮기고 싶은 이유와 새 자리에서 얻고 싶은 것을 먼저 적어 보는 관점이 도움이 될 수 있습니다.", "현재 자리에서 쌓은 실적을 새 자리에서 어떻게 설명할지 정리해 볼 수 있습니다."],
        "mixed": ["이직의 좋은 점과 환경 변화의 부담을 나란히 놓고 비교해 보는 관점이 참고가 될 수 있습니다.", "새 조직의 규칙과 문화가 자신의 방식과 맞는지 미리 알아보는 일을 생각해 볼 수 있습니다."],
        "cautious": ["서둘러 옮기기보다 현재 자리에서 경력과 자격을 보강하며 선택지를 넓혀 두는 관점을 생각해 볼 수 있습니다."],
        "quiet": ["뚜렷한 신호가 없으니 연봉·성장·근무 조건 같은 현실 기준을 중심으로 판단하는 편이 좋습니다."],
        "thin": ["사주만으로 말할 수 있는 것이 적으니 현실의 제안 조건을 우선 기준으로 삼는 편이 좋습니다."]},
    "docs_realestate": {
        "opportunity": ["계약 전 조건과 서류를 정리해 두면 순조로운 흐름을 살리는 데 도움이 될 수 있습니다."],
        "mixed": ["계약서의 세부 조건(기간, 비용, 해지 조건)을 꼼꼼히 확인하는 관점이 참고가 될 수 있습니다.", "중요한 서류는 전문가의 확인을 받아 보는 것을 생각해 볼 수 있습니다."],
        "cautious": ["결정을 서두르기보다 여러 조건을 비교하고 충분히 확인한 뒤 진행하는 관점을 생각해 볼 수 있습니다."],
        "quiet": ["뚜렷한 변화가 없으니 일정과 조건을 차분히 정리하며 진행해 볼 수 있습니다."],
        "thin": ["사주만으로 말할 수 있는 것이 적으니 계약의 실제 조건을 우선 기준으로 삼는 편이 좋습니다."]},
    "real_estate": {
        "opportunity": ["자금 계획과 대출 조건을 미리 정리해 두면 기회를 살피는 데 도움이 될 수 있습니다."],
        "mixed": ["거래 조건과 비용(세금·수수료·대출 이자)을 함께 놓고 점검해 보는 관점이 참고가 될 수 있습니다."],
        "cautious": ["서둘러 결정하기보다 시세와 조건을 충분히 비교해 보는 관점을 생각해 볼 수 있습니다."],
        "quiet": ["뚜렷한 변화가 없으니 현재의 거처와 자산 계획을 차분히 점검해 볼 수 있습니다."],
        "thin": ["사주만으로 말할 수 있는 것이 적으니 시세와 자금 사정을 우선 기준으로 삼는 편이 좋습니다."]},
    "love_marriage": {
        "steady": ["안정적인 흐름일수록 서로의 일상과 기대를 자주 나누는 관점이 도움이 될 수 있습니다."],
        "mixed": ["서운함이나 기대를 미루지 않고 말로 확인하는 관점이 참고가 될 수 있습니다.", "중요한 결정(동거·결혼 등)은 서로의 현실 조건을 충분히 이야기한 뒤 정해 보는 것을 생각해 볼 수 있습니다."],
        "cautious": ["감정이 격해질 때는 결론을 내리기보다 시간을 두고 다시 이야기해 보는 관점을 생각해 볼 수 있습니다."],
        "quiet": ["큰 변화 신호가 없으니 관계를 가꾸는 일상의 노력에 시간을 쓰는 관점을 생각해 볼 수 있습니다."],
        "thin": ["사주만으로 말할 수 있는 것이 적으니 두 사람의 실제 상황과 대화를 우선 기준으로 삼는 편이 좋습니다."]},
    "family": {
        "steady": ["가까운 사람들과 연락과 역할을 나누는 일을 꾸준히 이어 가는 관점이 도움이 될 수 있습니다."],
        "mixed": ["돌봄·비용·역할처럼 의견이 갈리기 쉬운 주제는 미리 이야기해 두는 관점이 참고가 될 수 있습니다."],
        "cautious": ["오해가 쌓이기 쉬운 시기이니 중요한 이야기는 직접, 차분히 나누는 관점을 생각해 볼 수 있습니다."],
        "quiet": ["큰 변화 신호가 없으니 정기적인 만남과 연락으로 관계를 유지하는 관점을 생각해 볼 수 있습니다."],
        "thin": ["사주만으로 말할 수 있는 것이 적으니 가족의 실제 상황을 우선 기준으로 삼는 편이 좋습니다."]},
    "health_traditional": {"balance": ["수면·식사·운동 같은 생활 리듬을 규칙적으로 돌아보는 일상적 관점으로만 참고해 주세요."]},
    "overall": {
        "opportunity": ["직업·재물·관계 중 지금 가장 중요한 한 가지를 정해 그쪽에 힘을 모아 보는 관점을 생각해 볼 수 있습니다.", "좋은 흐름일수록 무리한 확장보다 꾸준히 이어 가는 방식이 참고가 될 수 있습니다."],
        "mixed": ["기회와 부담이 함께 있는 시기이니 한 번에 여러 결정을 하기보다 순서를 정해 하나씩 진행하는 관점을 생각해 볼 수 있습니다."],
        "cautious": ["큰 결정은 서두르지 말고 준비와 점검에 시간을 쓰는 관점을 생각해 볼 수 있습니다."],
        "quiet": ["큰 변화가 두드러지지 않는 시기이니 평소의 습관과 관계를 다지는 데 시간을 쓰는 관점을 생각해 볼 수 있습니다."],
        "thin": ["사주만으로 말할 수 있는 것이 적으니 현실의 상황과 계획을 우선 기준으로 삼는 편이 좋습니다."]},
}
MIXED_FLAT = {
    "wealth": "{w}은 재물 흐름이 타고난 모습에서 크게 달라지지 않는 시기입니다. 타고난 대로 수입으로 이어질 기회와 나누거나 새어 나가기 쉬운 부분이 함께 있으니, 버는 것만큼 지키는 것을 살펴볼 만합니다.",
    "career": "{w}은 직업 흐름이 타고난 모습에서 크게 달라지지 않는 시기입니다. 타고난 대로 평가와 자리로 이어질 기회와 조직과 부딪히기 쉬운 부분이 함께 있습니다.",
    "business": "{w}은 사업 흐름이 타고난 모습에서 크게 달라지지 않는 시기입니다. 타고난 대로 수익 기회와 이익을 나누기 쉬운 부분이 함께 있습니다.",
    "job_change": "{w}은 이직과 관련한 흐름이 타고난 모습에서 크게 달라지지 않는 시기입니다. 타고난 대로 뒷받침하는 요소와 부담이 되는 요소가 함께 있어, 이직 여부는 현실 조건이 더 큰 기준이 됩니다.",
    "docs_realestate": "{w}은 계약·문서 흐름이 타고난 모습에서 크게 달라지지 않는 시기입니다. 타고난 대로 순조로운 면과 절차에서 부딪히기 쉬운 면이 함께 있습니다.",
    "real_estate": "{w}은 부동산 흐름이 타고난 모습에서 크게 달라지지 않는 시기입니다. 타고난 대로 자산을 쌓을 기회와 점검할 부분이 함께 있습니다.",
}
OVERALL_FLAT_MIXED = "{w}은 큰 변화 없이 타고난 흐름이 이어지는 시기로 읽힙니다. 타고난 대로 기회와 점검할 점이 함께 있습니다."
DOM_COUNTER_EXCLUDE = {"career": ("이익",), "job_change": ("이익",), "docs_realestate": ("이익",), "real_estate": ("이익",)}  # 돈 이야기가 아닌 분야에는 돈 관련 반대 견해를 붙이지 않는다
OVERALL_HEAD = {"opportunity": "{w}은 전반적으로 기회를 살리기 좋은 흐름으로 읽힙니다.", "mixed": "{w}은 기회와 점검할 점이 함께 오는 시기로 읽힙니다.",
                "cautious": "{w}은 서두르기보다 다지고 준비하는 쪽이 어울리는 시기로 읽힙니다.", "quiet": "{w}은 큰 변화 없이 타고난 흐름이 이어지는 시기로 읽힙니다.",
                "thin": "이 사주에서는 {w}에 대해 뚜렷하게 말할 수 있는 근거가 부족합니다."}
TIER_WORD = {1: "약하게", 2: "어느 정도", 3: "뚜렷하게"}


def when_phrase(years: list[int]) -> str:
    if not years:
        return "타고난 흐름"
    return f"{years[0]}년" if len(years) == 1 else f"{years[0]}~{years[-1]}년"


def _theme(dom: str, name: str) -> str:
    return THEMES.get(dom, THEMES["overall"]).get(name) or THEMES["overall"].get(name) or S.STRUCT[name]["short"]


def _join(items: list[str], limit: int = 2) -> str:
    items = list(dict.fromkeys(items))[:limit]
    return items[0] if len(items) == 1 else (", ".join(items) if items else "")


def _date_plain(iso: str) -> str:
    return f"{int(iso[5:7])}월 {int(iso[8:10])}일"


# ------------------------------------------------------------------ 변주·구체 문장 재료
def _h(key: str, n: int) -> int:
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) % n


def _pick(opts: list[str], key: str) -> str:
    return opts[_h(key, len(opts))]


def _rng(rngs) -> str:
    a, b = FA.merged_range(rngs)
    return f"{int(a[5:7])}월 {int(a[8:10])}일~{int(b[5:7])}월 {int(b[8:10])}일"


NAT = {3: ["{t}이 이 사주의 뚜렷한 특징입니다.", "이 사주는 {t}이 분명하게 드러나는 편입니다."],
       2: ["타고난 사주에는 {t}이 어느 정도 갖춰져 있습니다.", "{t}이 무난하게 자리 잡고 있는 사주입니다."],
       1: ["{t}의 바탕은 있지만 아직 두드러지지는 않습니다.", "타고난 사주에는 {t}이 약하게 숨어 있는 정도입니다."]}
NAT_NONE = ["타고난 사주에는 이 분야와 곧바로 이어지는 뚜렷한 흐름이 많지 않습니다.", "이 분야는 타고난 사주에서 특별히 앞서는 흐름이 보이지 않는 편입니다."]
P_SUP = ["{w}에는 {t}이 타고난 모습보다 더 뚜렷해집니다.", "{w} 동안 {t}이 한층 살아나는 쪽으로 움직입니다."]
P_FLAT = ["{w}에는 이 분야의 흐름이 타고난 모습에서 크게 달라지지 않습니다.", "{w}은 이 분야에서 눈에 띄게 달라지는 점이 없는 해입니다."]
CONTRAST = ["타고난 사주에는 {t}도 함께 있어, 좋은 면만 보고 판단하지는 않습니다.", "한편 이 사주에는 {t}도 자리하고 있어 균형을 함께 봅니다.", "다만 {t}도 타고난 부분이라 같이 살펴야 합니다."]
SKELETON = {"wealth": ["period", "emphasis", "relation", "natal", "contrast", "counter", "timing"], "career": ["emphasis", "relation", "period", "natal", "contrast", "timing", "counter"],
            "business": ["period", "contrast", "natal", "relation", "timing"], "job_change": ["relation", "period", "natal", "contrast", "timing"],
            "docs_realestate": ["relation", "natal", "period", "contrast", "timing"], "real_estate": ["natal", "period", "relation", "contrast", "timing"]}
IMPL_BAD = {"wealth": "수입·지출 구조나 재정 환경이 바뀌는 일을 점검해 볼 만합니다", "career": "직장 환경이나 맡은 역할이 바뀌는 일에 민감할 수 있습니다",
            "business": "사업 구조와 협업 관계를 점검해 볼 만합니다", "job_change": "직장 환경의 변화가 이직 고민으로 이어지기 쉬운 시기로 볼 수 있습니다",
            "docs_realestate": "계약 조건이나 절차가 바뀌는 일을 유의해 볼 만합니다", "real_estate": "거래 조건이나 거처가 바뀌는 일을 유의해 볼 만합니다",
            "overall": "그 영역에서 변화나 마찰이 생기는지 살펴볼 만합니다"}
IMPL_GOOD = {"wealth": "수입과 관련한 인연이나 기회가 묶여 들어오는 쪽으로 읽을 수 있습니다", "career": "조직과 인연이 맺어지는 쪽으로 읽을 수 있습니다",
             "business": "협업이나 거래 인연이 맺어지는 쪽으로 읽을 수 있습니다", "job_change": "새로운 자리와 인연이 닿는 쪽으로 읽을 수 있습니다",
             "docs_realestate": "계약이나 문서 일이 맞물려 진행되는 쪽으로 읽을 수 있습니다", "real_estate": "거래나 거처와 인연이 닿는 쪽으로 읽을 수 있습니다",
             "overall": "그 영역에서 인연이 묶이는 쪽으로 읽을 수 있습니다"}


def _areas_of(palaces) -> str:
    return " · ".join(E.AREA[p] for p in list(dict.fromkeys(palaces))[:2])


def relation_sentence(dom: str, prels: list[dict], w: str, with_luck: bool = True, year: int | None = None) -> str | None:
    """그해(세운)·10년 큰 흐름(대운)이 이 분야 궁위와 맺는 관계를 사실대로 한 문장으로. 해 절반 미만 구간의 관계는 기간을 밝힌다."""
    yb = [r for r in prels if r["who"] == "year" and r["polarity"] == "bad"]
    yg = [r for r in prels if r["who"] == "year" and r["polarity"] == "good"]
    lb = [r for r in prels if r["who"] == "luck" and r["polarity"] == "bad"]
    parts = []
    main_b = [r for r in yb if r["frac"] >= FA.MAJOR_FRAC]
    part_b = [r for r in yb if r["frac"] < FA.MAJOR_FRAC]
    main_g = [r for r in yg if r["frac"] >= FA.MAJOR_FRAC]
    impl_b, impl_g = IMPL_BAD.get(dom, IMPL_BAD["overall"]), IMPL_GOOD.get(dom, IMPL_GOOD["overall"])
    if main_b:
        parts.append(f"{w}에는 그해의 기운이 {_areas_of([r['palace'] for r in main_b])}에 부딪히거나 흐트러지는 관계로 들어와, {impl_b}.")
    elif part_b:
        rr = [x for r in part_b for x in r["ranges"]]
        pre_ipchun = year is not None and min(a for a, _ in rr) == f"{year}-01-01" and max(b for _, b in rr) < f"{year}-02-10"
        parts.append(f"{_rng(rr)}{'(입춘 전이라 전해의 기운이 적용되는 기간)' if pre_ipchun else ''}에는 그해의 기운이 {_areas_of([r['palace'] for r in part_b])}에 부딪히는 관계로 잠시 들어와, {impl_b}.")
    if main_g and not main_b:
        parts.append(f"{w}에는 그해의 기운이 {_areas_of([r['palace'] for r in main_g])}에 맞물려 묶이는 관계로 들어와, {impl_g}.")
    if lb and with_luck:
        parts.append(f"10년 단위 큰 흐름도 {_areas_of([r['palace'] for r in lb])}에 부딪히는 관계를 이어 가고 있습니다.")
    return " ".join(parts[:2]) if parts else None


def _first_sentence(t: str) -> str:
    i = t.find(". ")
    return t if i < 0 else t[:i + 1]


def _headline(dom: str, tone: str, w: str, t: dict, flat: bool, base_tpl: str | None, weak: bool = False) -> str:
    """결론(A): 어조 문장(분야별 틀) + 이 사주의 실제 구조 내용을 담은 한 문장. 같은 어조라도 구조가 다르면 결론이 달라진다."""
    tpl = base_tpl or HEAD["wealth"]["thin"]
    head = tpl.format(w=w)
    th = lambda names: _join([_theme(dom, n) for n in names], 2)
    if weak:
        return f"{_first_sentence(head)} 다만 이 분야를 뒷받침하는 구조가 겉으로 드러나지 않고 속에 숨은 정도로만 있어, 뚜렷한 결론은 내리지 않았습니다."
    nat_sup = sorted(t.get("natal_support", []), key=lambda n: -t["present"][n]) if t.get("present") else []
    nat_ten = sorted(t.get("natal_tension", []), key=lambda n: -t["present"][n]) if t.get("present") else []
    if flat and nat_sup and nat_ten:
        return (f"{_first_sentence(head)} 타고난 대로 {th(nat_sup[:1])}은 {TIER_WORD[t['present'][nat_sup[0]]]}, "
                f"{th(nat_ten[:1])}은 {TIER_WORD[t['present'][nat_ten[0]]]} 자리하고 있습니다.")
    if tone == "opportunity" and t.get("sup_up"):
        return f"{_first_sentence(head)} 특히 {th(t['sup_up'])}이 눈에 띕니다."
    if tone == "mixed" and t.get("sup_up") and t.get("ten_up"):
        return f"{_first_sentence(head)} {th(t['sup_up'])} 쪽은 힘을 받고, {th(t['ten_up'])} 쪽은 점검이 필요합니다."
    if tone == "cautious" and (t.get("ten_up") or nat_ten):
        return f"{_first_sentence(head)} 특히 {th((t.get('ten_up') or nat_ten)[:1])}에 유의가 필요합니다."
    return head


def _structs(pre: dict) -> dict:
    return {s["name"]: s for s in pre["natal_structure"]["layer3"]["structures"]}


def _rule_ids(names: list[str]) -> list[str]:
    return [S.RULE_OF[n] for n in names if n in S.RULE_OF]


# ------------------------------------------------------------------ 어조 정하기
def tone_for(pre: dict, dom: str, yr: dict | None, nm: dict, common_bad: list[str] | None = None) -> dict:
    """구조 분야: 돕는 흐름(S)과 부딪히거나 나누는 흐름(T)의 크기로 정한다. 그해 변화는 기간 가중(해의 절반 이상을 덮는 구간만 '그해의 변화', 짧은 구간은 절반 점수)."""
    if D.DOMAINS[dom].get("kind") == "palace":
        return _tone_palace(pre, dom, yr, nm)
    sc = _struct_scores(pre, dom, yr, nm)
    cl = JD.classify(sc["S"], sc["T"], sc["has_basis"], bool(sc["sup_up"] or sc["ten_up"]))   # judge-2.0.0: 방향성(A)/충돌(B)/근거 부족(C)
    return {**sc, "tone": cl["tone"], "cls": cl["cls"], "reason": cl["reason"]}


def _struct_scores(pre: dict, dom: str, yr: dict | None, nm: dict) -> dict:
    """구조(식상생재·재생관 등)의 돕는 흐름 S 와 부딪히는 흐름 T. 그해 변화는 기간 가중(절반 이상=2, 일부=1, 대운 지속=1), 원국 배경은 최대 1."""
    rel = D.DOMAINS[dom]["structures"] or list(S.STRUCT)
    present = {n: nm[n]["rank"] for n in rel if n in nm and nm[n]["rank"] > 0}
    sup_n = [n for n in present if S.STRUCT[n]["polarity"] == "support"]
    ten_n = [n for n in present if S.STRUCT[n]["polarity"] == "tension"]
    ups = [n for n in (yr or {}).get("ups", []) if n in rel]
    part = [n for n in (yr or {}).get("ups_partial", []) if n in rel]
    pers = [n for n in (yr or {}).get("ups_persistent", []) if n in rel]
    sup_up = [n for n in ups if S.STRUCT[n]["polarity"] == "support"]
    ten_up = [n for n in ups if S.STRUCT[n]["polarity"] == "tension"]
    sup_part = [n for n in part if S.STRUCT[n]["polarity"] == "support"]
    ten_part = [n for n in part if S.STRUCT[n]["polarity"] == "tension"]
    sup_pers = [n for n in pers if S.STRUCT[n]["polarity"] == "support"]
    ten_pers = [n for n in pers if S.STRUCT[n]["polarity"] == "tension"]
    bad = (yr or {}).get("bad", [])  # 같은 해는 어느 범위로 보든 같은 결론이어야 하므로 선택 범위와 무관한 절대 기준만 쓴다
    s_score = 2 * len(sup_up) + len(sup_part) + len(sup_pers) + (1 if any(present[n] >= 3 for n in sup_n) or sum(present[n] for n in sup_n) >= 4 else 0)
    t_score = 2 * len(ten_up) + len(ten_part) + len(ten_pers) + (1 if any(present[n] >= 2 for n in ten_n) else 0) + (1 if len(bad) >= 3 else 0)
    return {"S": s_score, "T": t_score, "natal_support": sup_n, "natal_tension": ten_n, "sup_up": sup_up, "ten_up": ten_up, "sup_part": sup_part, "ten_part": ten_part, "sup_pers": sup_pers, "ten_pers": ten_pers,
            "present": present, "bad": bad, "has_basis": bool(present or ups or part or pers)}


def _tone_palace(pre: dict, dom: str, yr: dict | None, nm: dict | None = None) -> dict:
    """궁위 분야 톤. 근거 수집은 judge.palace_scores(원문 확인 규칙만 방향에 반영, 같은 관계 한 번만, 없음은 반대 근거 아님)."""
    if dom == "health_traditional":
        return {"tone": "balance", "S": 0, "T": 0, "cls": "none", "reason": "not_judged"}
    ex = CD.domain_extra(dom, pre) or {"evidence_for": [], "evidence_against": []}
    base = _struct_scores(pre, dom, yr, nm or {}) if D.DOMAINS[dom]["structures"] else None   # 분야가 선언한 구조(이직: 재생관·관인상생·살인상생)를 함께 본다
    sc = JD.palace_scores(pre, dom, (yr or {}).get("_segments", []), ex, PAL_DOM.get(dom, ()), CD._rels_at, FA.MAJOR_FRAC, FA.palace_relations, base)
    cl = JD.classify(sc["S"], sc["T"], sc["has_basis"], sc["year_change"])
    tone = cl["tone"]
    if tone == "quiet" and (sc["pos"] >= 1 or sc["palace_good"] >= 1):
        tone = "steady"   # 근거가 있고 이 해에 달라지는 것이 없으면(합은 방향이 아니라 '이어짐·묶임' 신호) '안정적으로 이어짐'
    return {"tone": tone, "cls": cl["cls"], "reason": cl["reason"], "S": sc["S"], "T": sc["T"], "palace_bad": sc["palace_bad"], "palace_good": sc["palace_good"], "pos": sc["pos"], "neg": sc["neg"],
            "reference": sc["reference"], "hour_excluded": sc["hour_excluded"], **({k: base[k] for k in ("natal_support", "natal_tension", "sup_up", "ten_up", "sup_part", "ten_part", "sup_pers", "ten_pers", "present", "bad")} if base else {})}


# ------------------------------------------------------------------ 분야별 한 덩어리
def _where_sentence(s: dict, theme: str | None = None) -> str | None:
    ev = E._parse(s.get("supporting", []))
    areas = list(dict.fromkeys(p["area"] for p in ev if p["area"]))
    if not areas:
        return None
    return f"{theme}은 주로 {' · '.join(areas[:2])}에서 나타납니다." if theme else f"이 흐름은 주로 {' · '.join(areas[:2])}에서 나타납니다."


EMPHASIS_CAREER = {"재생관": ("쌓은 실적이 직책·평가로 이어지는 쪽", "성과가 눈에 보이는 일에서 평가받기 쉬운 구조로 읽습니다."),
                   "관인상생": ("조직 안에서 신뢰와 도움을 얻는 쪽", "윗사람·조직의 신뢰와 자격·문서 같은 후원이 자리를 지켜 주는 구조로 읽습니다."),
                   "살인상생": ("압박을 준비와 조력으로 풀어 가는 쪽", "압박이 큰 환경에서 준비와 도움으로 버티며 인정받는 구조로 읽습니다.")}


def _emphasis(dom: str, present: dict) -> str | None:
    """이 분야에서 이 사주의 근거가 어느 쪽에 무게가 실려 있는지(구조 간 강약 차이). 분야마다 비교하는 갈래가 다르다."""
    if dom == "wealth":
        a, b = present.get("식상생재", 0), present.get("재생관", 0)
        if a and b and a > b:
            return "재물은 ‘직접 버는 힘’(능력이 수입으로 이어지는 쪽)에 무게가 실리고, 안정된 자리에서 나오는 수입은 상대적으로 약하게 읽힙니다."
        if a and b and b > a:
            return "재물은 ‘안정된 자리에서 나오는 수입’(기반이 직책·평가로 이어지는 쪽)에 무게가 실리고, 직접 버는 힘은 상대적으로 약하게 읽힙니다."
        if a and b:
            return "재물은 ‘직접 버는 힘’과 ‘안정된 자리에서 나오는 수입’이 비슷한 비중으로 읽힙니다."
        if a or b:
            return "재물 흐름은 " + ("‘직접 버는 힘’" if a else "‘안정된 자리에서 나오는 수입’") + " 한 갈래에 기대는 구조로 읽힙니다."
    if dom == "career":
        cand = {n: present[n] for n in EMPHASIS_CAREER if present.get(n)}
        if cand:
            top = max(cand.values())
            lead = [n for n, v in cand.items() if v == top]
            if len(lead) == 1:
                th, imp = EMPHASIS_CAREER[lead[0]]
                return f"직업에서는 ‘{th}’에 무게가 실립니다. {imp}"
            return "직업에서는 " + " 그리고 ".join(f"‘{EMPHASIS_CAREER[n][0]}’" for n in lead[:2]) + "이 비슷한 비중으로 자리합니다."
    if dom == "business":
        a, b = present.get("식상생재", 0), present.get("군겁쟁재", 0)
        if a and b:
            return "사업은 ‘아이디어·기술이 수익으로 이어지는 힘’과 ‘동업·경쟁에서 이익을 나누는 부담’이 함께 읽혀, 수익 구조와 배분 조건을 같이 보게 됩니다."
    return None


def _change_sentences(dom: str, w: str, yr: dict, t: dict, years: list[int], key: str, covered: set[str]) -> tuple[str, list[str]]:
    """그해의 구조 변화를 대표 변화(year) / 이어지는 변화(persistent) / 일부 기간(partial)으로 나누어 서술한다. 결론이 이미 말한 변화는 원인 글자(새 정보)로 설명한다."""
    parts: list[str] = []
    reasons: list[str] = []
    det = yr["ups_detail"]
    th = lambda names: _join([_theme(dom, n) for n in names])
    if t["sup_up"] and t["ten_up"]:
        parts.append(f"{w}에는 {th(t['sup_up'])}이 더 뚜렷해지지만, 동시에 {th(t['ten_up'])}도 커집니다.")
    elif t["sup_up"]:
        parts.append(_pick(P_SUP, key + "p").format(w=w, t=th(t["sup_up"])))
    elif t["ten_up"]:
        parts.append(("한편 " if t["natal_support"] else "") + f"{w}에는 {th(t['ten_up'])}이 타고난 모습보다 커집니다.")
    pers = [n for n in yr["ups_persistent"] if n in t.get("sup_pers", []) + t.get("ten_pers", [])]
    if pers:
        start = det[pers[0]]["ranges"][0][0]
        note = " (교체일은 3일=1년 환산이라 며칠~몇 주 달라질 수 있습니다)" if det[pers[0]]["luck_edge"] else ""
        parts.append(f"{_date_plain(start)}부터는 {th(pers)}이 더 뚜렷해지는데, 이는 10년 큰 흐름이 바뀐 영향이라 다음 해에도 이어질 수 있습니다{note}.")
    part_names = t["sup_part"] + t["ten_part"]
    if part_names:
        d0 = det[part_names[0]]
        pre = d0["ranges"][0][0].endswith("-01-01") and d0["ranges"][0][1] < f"{years[0]}-02-10"
        year_wide = bool(t["sup_up"] or t["ten_up"])  # 해 전체의 변화가 따로 있으면 '크게 달라지지 않는다'고 말하지 않는다
        if year_wide:
            why_short = " 입춘 전이라 전해의 기운이 적용되는 기간입니다." if pre else ""
        else:
            why_short = " 입춘 전이라 전해의 기운이 적용되는 기간이며, 해 전체의 흐름은 크게 달라지지 않습니다." if pre else " 해 전체의 흐름은 크게 달라지지 않습니다."
        kind = "새로 나타납니다" if "신규 출현" in d0["kinds"] else "잠시 더해집니다"
        parts.append(f"{_rng(d0['ranges'])} 동안에는 {th(part_names)}이 {kind}.{why_short}")
    if not parts:
        parts.append(_pick(P_FLAT, key + "p").format(w=w))
    # 결론이 이미 말한 변화는 풀이에서 '무엇이 들어와 만들었는지'(새 정보)로 설명한다
    for n in yr["ups"] + yr["ups_persistent"] + yr["ups_partial"]:
        r = E.period_reason(None, n, _theme(dom, n), det[n], yr["_segments"])
        if r:
            reasons.append(r)
    sent = " ".join(parts)
    if covered & set(yr["ups"]) and reasons:
        sent = reasons[0] if not (yr["ups_persistent"] or yr["ups_partial"]) else sent
    return sent, reasons


def domain_block(pre: dict, dom: str, years: list[int], period: dict | None, nm: dict, luck_date: str | None, salt: int = 0, show_timing: bool = True) -> dict:
    w = when_phrase(years)
    spec = D.DOMAINS[dom]
    name = spec["name"]
    rel = spec["structures"] or list(S.STRUCT)
    yr = FA.year_reading(period, rel) if period else None
    t = tone_for(pre, dom, yr, nm)
    tone = t["tone"]
    head_tpl = HEAD.get(dom, {}).get(tone)
    think_tone = tone
    key = f"{pre['natal_structure']['pillars']}|{dom}|{years}|{salt}"
    flat = False
    if tone == "mixed" and yr is not None and spec.get("kind") != "palace" and not t["sup_up"] and not t["ten_up"] and dom in MIXED_FLAT:  # 해 전체의 변화가 없으면(일부 기간·이어지는 변화만 있어도) 결론에서 '커집니다'라고 말하지 않는다
        flat = True
        tone, think_tone, head_tpl = "quiet", "mixed", MIXED_FLAT[dom]
    if spec.get("kind") == "palace":
        return _palace_block(pre, dom, w, name, period, yr, t, tone, head_tpl, luck_date if show_timing else None)
    layer3 = _structs(pre)
    nat_sup = sorted(t["natal_support"], key=lambda n: -t["present"][n])
    nat_ten = sorted(t["natal_tension"], key=lambda n: -t["present"][n])
    changed = bool(yr and (yr["ups"] or yr["ups_persistent"] or yr["ups_partial"]))
    weak = bool(t["present"]) and max(t["present"].values()) <= 1 and not changed
    # 결론(A)이 이미 말하는 구조 → 풀이(B)는 같은 말을 되풀이하지 않고 새 정보(나타나는 삶의 영역, 변화를 만든 글자)를 준다
    covered: set[str] = set()
    if flat and nat_sup and nat_ten:
        covered = {nat_sup[0], nat_ten[0]}
    elif tone == "opportunity" and t["sup_up"]:
        covered = set(t["sup_up"])
    elif tone == "mixed" and t["sup_up"] and t["ten_up"]:
        covered = set(t["sup_up"]) | set(t["ten_up"])
    elif tone == "cautious" and (t["ten_up"] or nat_ten):
        covered = {(t["ten_up"] or nat_ten)[0]}
    slots: dict[str, str] = {}
    why = {"natal": [], "period": [], "against": [], "nature": ""}
    if nat_sup:
        n = nat_sup[0]
        wh = _where_sentence(layer3[n], _theme(dom, n))
        if n in covered:
            if wh:
                slots["where"] = wh                      # 결론이 강약을 말했으므로 풀이는 '어디에서 나타나는지'를 말한다(시기 사실보다 뒤)
        else:
            slots["natal"] = _pick(NAT[t["present"][n]], key + "n").format(t=_theme(dom, n))
            if wh:
                slots["where"] = wh
    elif t["present"] == {} and not changed:
        slots["natal"] = "이 사주에는 이 분야와 곧바로 이어지는 짜임이 보이지 않고, 이 시기의 운에서도 새로 생기는 변화가 없어 말씀드릴 근거가 부족합니다."
    else:
        slots["natal"] = _pick(NAT_NONE, key + "n")
    if weak:
        slots["natal"] = "이 분야와 이어지는 짜임은 있지만 겉으로 드러나지 않고 속에 숨어 있어 힘이 약합니다. 그래서 뚜렷한 결론은 내리지 않았습니다."
    elif tone == "thin" and t.get("reason") == "weak_evidence":   # judge-2.0.0: 돕는 쪽과 부딪히는 쪽의 차이가 작거나 뒷받침이 약해 한쪽으로 정하지 않은 경우
        slots["natal"] = (f"{name}과 이어지는 짜임과 이 시기의 변화가 있지만, 돕는 쪽과 부딪히는 쪽의 차이가 크지 않아 한쪽으로 결론을 내리지 않았습니다." if t["S"] and t["T"]
                          else f"{name}과 이어지는 짜임과 이 시기의 변화가 있지만 뒷받침이 약해 말씀드릴 근거가 부족합니다. 그래서 한쪽으로 결론을 내리지 않았습니다.")
    for n in (nat_sup[:2] + nat_ten[:1]):
        r = E.natal_reason(layer3[n], _theme(dom, n))
        if r:
            why["natal"].append(r)
    emph = _emphasis(dom, t["present"])
    if emph:
        slots["emphasis"] = emph
        why["natal"].append(emph)
    if yr is not None:
        slots["period"], reasons = _change_sentences(dom, w, yr, t, years, key, covered)
        why["period"] += reasons
        if not (yr["ups"] or yr["ups_persistent"] or yr["ups_partial"]):
            why["period"].append(f"{w}에는 이 분야의 흐름을 바꾸는 운의 글자가 새로 들어오지 않아, 타고난 모습 그대로 이어지는 것으로 읽습니다.")
        palaces = PAL_DOM.get(dom, ())
        prels = FA.palace_relations(period, palaces) if palaces else []
        rs = relation_sentence(dom, prels, w, with_luck=show_timing, year=years[0])
        if rs:
            flat_year = tone == "quiet" and not (t["sup_up"] or t["ten_up"])
            slots["relation"] = ("구조 변화와는 별개로, " + rs) if flat_year else rs
            why["period"].append(rs)
    if t["T"] > 0 and not t["ten_up"]:
        if nat_ten:
            n = nat_ten[0]
            if n in covered:
                wh = _where_sentence(layer3[n], _theme(dom, n))
                if wh:
                    slots["where2"] = wh
            else:
                slots["contrast"] = _pick(CONTRAST, key + "c").format(t=_theme(dom, n))
        elif len(t["bad"]) >= 3:
            slots["contrast"] = "또한 타고난 사주와 부딪히거나 흐트러지는 관계가 여러 개 들어와, 흐름이 매끄럽게만 이어지지는 않을 수 있습니다."
    counter = []
    for n in nat_sup[:2]:
        counter += S._counters_plain({"counter": layer3[n]["counter"]}, "support")
    for n in (t["ten_up"] or nat_ten)[:1]:
        counter += S._counters_plain({"counter": layer3[n]["counter"]}, "tension")[:1]
    counter = [c for c in dict.fromkeys(counter) if not any(x in c for x in DOM_COUNTER_EXCLUDE.get(dom, ()))][:2]
    if counter:
        slots["counter"] = counter[0]
    why["against"] = [c.rstrip(".") + "." for c in counter] or ["이 흐름에 대해 눈에 띄는 반대 견해는 확인되지 않았습니다."]
    if luck_date and yr is not None and yr["luck_split"] and show_timing:  # 교체 시점은 종합운과 첫 분야에서만 말한다
        slots["timing"] = f"{_date_plain(luck_date)} 무렵 10년 단위로 바뀌는 큰 흐름이 바뀌므로, 그 전과 후를 나누어 보는 편이 좋습니다. 교체일은 3일=1년 환산이라 며칠~몇 주 달라질 수 있습니다."
    why["nature"] = E.nature_note(_rule_ids(nat_sup + nat_ten + t["sup_up"] + t["ten_up"] + t["sup_part"] + t["ten_part"] + t["sup_pers"] + t["ten_pers"]))
    skeleton = list(SKELETON.get(dom, ["period", "natal", "contrast", "counter", "timing"]))
    if "emphasis" not in skeleton:
        skeleton = skeleton[:2] + ["emphasis"] + skeleton[2:]
    skeleton += [k for k in ("where", "where2") if k not in skeleton]
    explain_missing = weak or tone == "thin" or (t["present"] == {} and not changed)  # 근거가 약하거나 없으면 '왜 결론을 내리지 않는지'를 반드시 말한다
    story = _compose(dom, slots, must=["period", "contrast", "timing"] + (["natal"] if explain_missing else []), skeleton=skeleton)
    headline = _headline(dom, tone, w, t, flat, head_tpl, weak)
    think = list(THINK.get(dom, {}).get(think_tone, THINK["overall"]["thin"]))[:2]
    claim_ids = [layer3[n]["claim_id"] for n in nat_sup + nat_ten] + (yr["claim_ids"] if yr else [])
    return {"domain": dom, "name": name, "tone": tone, "tone_label": TONE_SHORT[tone], "headline": headline, "story": story, "think": think, "counter": counter, "why": why,
            "scores": {"S": t["S"], "T": t["T"]}, "_claims": claim_ids}


def _compose(dom: str, slots: dict[str, str], must: list[str], skeleton: list[str], cap: int = 4) -> list[str]:
    """분야마다 다른 순서(skeleton)로 문장을 놓는다. 반드시 말해야 하는 것(must: 시기 변화·반대 근거·교체 시점)을 먼저 확보하고 남는 자리를 순서대로 채운다."""
    chosen = [k for k in must if k in slots]
    for k in skeleton:
        if len(chosen) >= cap:
            break
        if k in slots and k not in chosen:
            chosen.append(k)
    out = []
    prev_lead = ""
    for k in [x for x in skeleton if x in chosen] + [x for x in chosen if x not in skeleton]:
        s = slots[k]
        if k == "counter":
            lead = "또한 " if prev_lead == "다만" or (out and out[-1].startswith("다만")) else "다만 "
            s = lead + s.rstrip(".") + "."
        out.append(s)
        prev_lead = "다만" if s.startswith("다만") else ""
    return out


def _palace_block(pre, dom, w, name, period, yr, t, tone, head_tpl, luck_date) -> dict:
    key = f"{pre['natal_structure']['pillars']}|{dom}|{w}"
    pr = R.palace_readings(pre, [{"domain": dom, "name": name}])
    rd = pr[0] if pr else None
    ex = CD.domain_extra(dom, pre) or {"evidence_for": [], "evidence_against": []}
    facts = [R.natural(x) for x in ex["evidence_for"]][:2]
    story: list[str] = []
    LEAD = {"love_marriage": "배우자와의 인연을 보는 자리에서는, ", "family": "가까운 사람들과의 자리를 보면, ", "job_change": "직업 자리를 보면, ", "real_estate": "재물·문서·거처 쪽을 보면, "}
    if dom != "health_traditional":
        if facts and not (rd and rd.get("thin")):
            story.append(LEAD.get(dom, "") + " ".join(facts))
        elif rd:
            story.append(rd["meaning"])
    else:
        story.append("오행(목·화·토·금·수)의 분포와 태어난 계절의 한난을 '균형의 상징'으로만 살펴보는 영역이며, 증상이나 질환과 연결하지 않습니다.")
        if facts:
            story.append(" ".join(facts))
    why = {"natal": ([rd["meaning"]] if rd and dom != "health_traditional" else []) + [R.natural(x) for x in ex["evidence_for"]][:3], "period": [], "against": [], "nature": "이 분야의 읽는 기준은 이 서비스가 정한 방식이며 고전 원문 대조 전 단계입니다. 결과나 사건을 말하는 것이 아닙니다."}
    if period is not None and dom != "health_traditional":
        prels = FA.palace_relations(period, PAL_DOM.get(dom, ()))
        rs = relation_sentence(dom, prels, w, with_luck=False, year=(period or {}).get("year"))
        if rs:
            story.append(rs)
            why["period"].append(rs)
        else:
            why["period"].append(f"{w}에는 이 분야의 자리에 새로 닿는 관계가 확인되지 않았습니다.")
    counter = [R.natural(x) for x in ex["evidence_against"]][:2]
    why["against"] = counter or ["눈에 띄는 반대 근거는 확인되지 않았습니다."]
    if luck_date and yr is not None and yr["luck_split"] and dom != "health_traditional":
        story.append(f"{_date_plain(luck_date)} 무렵 10년 단위로 바뀌는 큰 흐름이 바뀌므로, 그 전과 후를 나누어 보는 편이 좋습니다.")
    for c in counter[:1]:
        story.append(c)
    story = story[:4]
    if head_tpl:
        headline = head_tpl.format(w=w)
    elif tone == "steady":   # 분야별 문구가 없는 톤은 다른 분야(재물) 문장을 빌리지 않고 이 분야 이름으로 쓴다
        headline = f"{w}은 {name}이 큰 기복 없이 안정적으로 이어지는 흐름으로 읽힙니다. 다만 사주만으로 단정하지는 않습니다."
    elif tone == "balance":
        headline = f"{w}은 {name}에서 생활의 균형을 돌아보기 좋은 흐름으로 읽힙니다. 결과를 보장하는 해석은 아닙니다."
    else:
        headline = f"이 사주에서는 {w} {name}에 대해 뚜렷하게 말할 수 있는 근거가 부족합니다."
    think = list(THINK.get(dom, {}).get(tone, THINK["overall"]["thin"]))[:2]
    return {"domain": dom, "name": name, "tone": tone, "tone_label": TONE_SHORT[tone], "headline": headline, "story": story, "think": think, "counter": counter, "why": why,
            "scores": {"S": t["S"], "T": t["T"]}, "_claims": []}


# ------------------------------------------------------------------ 종합운
def overall_block(pre: dict, years: list[int], period: dict | None, nm: dict, luck_date: str | None, others: list[dict], salt: int = 0) -> dict:
    w = when_phrase(years)
    rel = list(S.STRUCT)
    yr = FA.year_reading(period, rel) if period else None
    t = tone_for(pre, "overall", yr, nm)
    tone = t["tone"]
    flat_mixed = tone == "mixed" and yr is not None and not (t["sup_up"] or t["ten_up"])
    layer3 = _structs(pre)
    key = f"{pre['natal_structure']['pillars']}|overall|{years}|{salt}"
    nat_sup = sorted(t["natal_support"], key=lambda n: -t["present"][n])
    nat_ten = sorted(t["natal_tension"], key=lambda n: -t["present"][n])
    # 결론이 말하는 것: 구조 강약(flat) 또는 그해 변화. 풀이는 같은 말을 반복하지 않는다.
    head = (OVERALL_FLAT_MIXED if flat_mixed else OVERALL_HEAD[tone]).format(w=w)
    covered: set[str] = set()
    if flat_mixed and nat_sup and nat_ten:
        head = (f"{_first_sentence(head)} 타고난 대로 {_theme('overall', nat_sup[0])}은 {TIER_WORD[t['present'][nat_sup[0]]]}, "
                f"{_theme('overall', nat_ten[0])}은 {TIER_WORD[t['present'][nat_ten[0]]]} 자리하고 있습니다.")
        covered = {nat_sup[0], nat_ten[0]}
    elif tone == "opportunity" and t["sup_up"]:
        head = f"{_first_sentence(head)} 특히 {_join([_theme('overall', n) for n in t['sup_up']], 2)}이 눈에 띕니다."
        covered = set(t["sup_up"])
    elif tone == "mixed" and t["sup_up"] and t["ten_up"]:
        head = f"{_first_sentence(head)} {_join([_theme('overall', n) for n in t['sup_up']], 2)} 쪽은 힘을 받고, {_join([_theme('overall', n) for n in t['ten_up']], 2)} 쪽은 점검이 필요합니다."
        covered = set(t["sup_up"]) | set(t["ten_up"])
    slots: dict[str, str] = {}
    why = {"natal": [], "period": [], "against": [], "nature": ""}
    if nat_sup:
        n = nat_sup[0]
        wh = _where_sentence(layer3[n], _theme("overall", n))
        if n in covered:
            if wh:
                slots["where"] = wh
        else:
            slots["natal"] = _pick(["타고난 사주는 {t}이 중심에 놓인 구조입니다.", "이 사주의 중심 줄기는 {t}입니다.", "{t}이 이 사주를 이끄는 가장 큰 특징으로 보입니다."], key + "n").format(t=_theme("overall", n))
    elif nat_ten:
        slots["natal"] = f"타고난 사주에서는 돕는 흐름보다 {_theme('overall', nat_ten[0])}이 먼저 보여, 조건을 가려 가며 읽어야 하는 구조입니다."
    else:
        slots["natal"] = "타고난 사주에서는 뚜렷하게 앞서는 흐름이 많지 않은 편입니다."
    for n in (nat_sup[:2] + nat_ten[:1]):
        r = E.natal_reason(layer3[n], _theme("overall", n))
        if r:
            why["natal"].append(r)
    if yr is not None:
        slots["period"], reasons = _change_sentences("overall", w, yr, t, years, key, covered)
        if not (yr["ups"] or yr["ups_persistent"] or yr["ups_partial"]):
            slots["period"] = f"{w}에는 구조상 눈에 띄는 변화가 없어, 타고난 흐름이 대체로 이어지는 시기입니다."
        why["period"] += reasons
        if t["ten_up"]:
            slots["contrast"] = f"한편 {_join([_theme('overall', n) for n in t['ten_up']], 3)}도 함께 커져, 좋은 흐름이 그대로 매끄럽게 이어지지는 않을 수 있습니다."
        elif t["T"] > 0:
            if nat_ten:
                n = nat_ten[0]
                if n in covered:
                    wh = _where_sentence(layer3[n], _theme("overall", n))
                    if wh:
                        slots["where2"] = wh
                else:
                    slots["contrast"] = _pick(CONTRAST, key + "c").format(t=_theme("overall", n))
            elif len(t["bad"]) >= 3:
                slots["contrast"] = "또한 타고난 사주와 부딪히거나 흐트러지는 관계가 여러 개 들어와, 흐름이 매끄럽게만 이어지지는 않을 수 있습니다."
        if not (yr["ups"] or yr["ups_persistent"] or yr["ups_partial"]):
            why["period"].append(f"{w}에는 구조를 바꾸는 운의 글자가 새로 들어오지 않아, 타고난 모습 그대로 이어지는 것으로 읽습니다.")
        rs = relation_sentence("overall", FA.palace_relations(period, ("year", "month", "day", "hour")), w, with_luck=True, year=years[0])
        if rs:
            slots["relation"] = ("구조 변화와는 별개로, " + rs) if flat_mixed or not (t["sup_up"] or t["ten_up"]) else rs
            why["period"].append(rs)
    if luck_date and yr is not None and yr["luck_split"]:
        slots["timing"] = f"{_date_plain(luck_date)} 무렵 10년 단위로 바뀌는 큰 흐름이 바뀌어, 그 전과 후의 분위기가 달라질 수 있습니다. 교체일은 3일=1년 환산이라 며칠~몇 주 달라질 수 있습니다."
    cons = [x for x in others if x["domain"] != "overall"]
    hi = [x for x in cons if x["tone"] in ("opportunity", "steady")]
    lo = [x for x in cons if x["tone"] in ("cautious", "mixed")]
    if hi and lo:
        slots["cross"] = f"선택하신 분야 중에서는 {_join([x['name'] for x in hi], 2)} 쪽이 상대적으로 순조롭게, {_join([x['name'] for x in lo], 2)} 쪽은 조율이 필요하게 읽힙니다."
    why["against"] = [f"타고난 사주에 {_theme('overall', n)}이 있어 한쪽으로만 읽지 않습니다." for n in nat_ten[:2]] or ["눈에 띄는 반대 근거는 확인되지 않았습니다."]
    why["nature"] = E.nature_note(_rule_ids(nat_sup + nat_ten + t["sup_up"] + t["ten_up"]))
    story = _compose("overall", slots, must=["natal", "period", "contrast", "timing", "cross"], skeleton=["natal", "period", "relation", "contrast", "timing", "cross", "where", "where2"], cap=5)
    think_tone = tone
    if flat_mixed:
        tone = "quiet"
    return {"domain": "overall", "name": "종합운", "tone": tone, "tone_label": TONE_SHORT[tone], "headline": head, "story": story, "think": list(THINK["overall"][think_tone])[:2], "counter": [],
            "why": why, "scores": {"S": t["S"], "T": t["T"]}, "_claims": [layer3[n]["claim_id"] for n in nat_sup + nat_ten] + (yr["claim_ids"] if yr else [])}


# ------------------------------------------------------------------ 한계(D)
def limits_for(pre: dict, years: list[int], blocks: list[dict], multi_flat: bool = False) -> list[str]:
    w = when_phrase(years)
    out = [f"이 풀이는 전통 명리학의 해석 틀로 읽은 것이며, {w}의 결과를 예측하거나 보장하지 않습니다. 실제 결정은 현실 조건을 기준으로 해 주세요."]
    v = pre["verification"]
    sc = v.get("scope", {})
    not_ok = []
    if not sc.get("CORE_VALIDATED", {}).get("granted"):
        not_ok.append("연·월·일 기둥")
    if not sc.get("TIME_PROFILE_VALIDATED", {}).get("granted"):
        not_ok.append("태어난 시각에 따른 보정")
    if not sc.get("DAEUN_PROFILE_VALIDATED", {}).get("granted"):
        not_ok.append("10년 단위 큰 흐름의 시작 시점")
    if not_ok:
        out.append("사주 계산 중 " + ", ".join(not_ok) + " 부분은 아직 독립 검증을 마치지 않아 참고용으로 보셔야 합니다.")
    hb = (v.get("hour_boundary") or {})
    if hb.get("near"):
        out.append("태어난 시각이 시(2시간 단위) 경계 가까이에 있어, 시각이나 출생지가 조금만 달라도 사주의 시 부분이 바뀔 수 있습니다.")
    if pre.get("variants_count", 1) > 1:
        out.append("시간 보정 방식에 따라 사주가 여러 개로 갈리며, 지금 보시는 것은 선택한 하나입니다. 다른 방식으로 읽으면 일부 해석이 달라질 수 있습니다.")
    if any(b["tone"] == "thin" for b in blocks):
        out.append("근거가 부족한 분야는 억지로 말을 만들지 않았습니다.")
    if multi_flat:
        out.append("선택한 기간 안에서 해마다 뚜렷하게 구별되는 구조 변화가 없어, 연도별 결론이 비슷하게 나옵니다.")
    out.append("‘기회’·‘점검’ 같은 결론은 사주의 구조 변화를 읽는 한 가지 방식(이 서비스가 정한 규칙이며 고전 원문으로 확정된 것이 아닙니다)에 따른 것이며, 해석하는 방식에 따라 달라질 수 있습니다.")
    return out


# ------------------------------------------------------------------ 기간(5년·10년)
def period_block(pre: dict, years: list[int], periods: dict[int, dict], yrs: dict[int, dict], doms: list[str], nm: dict, luck_changes: list[dict], primary: str) -> dict:
    rel_all = S._relevant(doms)
    names = list(years)
    common_ups = [n for n in rel_all if all(n in yrs[y]["ups"] for y in names)]
    common_bad = [k for k in yrs[names[0]]["bad"] if all(k in yrs[y]["bad"] for y in names)]
    dev = {}
    for y in names:
        r = yrs[y]
        dev[y] = 2 * len([n for n in r["ups"] if n not in common_ups]) + 2 * len([n for n in common_ups if n not in r["ups"]]) + len(r["ups_partial"]) + len(r["ups_persistent"]) + len(r["downs"]) + \
            len([k for k in r["bad"] if k not in common_bad]) + (2 if r["luck_split"] else 0)
    top = max(dev.values())
    standout = [y for y in names if dev[y] == top][:3] if (top > min(dev.values()) and top >= 2) else []
    rows, tones = [], {}
    for y in names:
        r = yrs[y]
        ld = next((c["date"] for c in luck_changes if c["date"][:4] == str(y)), None)
        blk = domain_block(pre, primary, [y], periods[y], nm, ld)
        tones[y] = blk["tone"]
        extra_up = [n for n in r["ups"] if n not in common_ups]
        diff = []
        if extra_up:
            diff.append(_join([_theme(primary, n) for n in extra_up], 2) + "이 더해짐")
        for n in r["ups_persistent"]:
            det = r["ups_detail"][n]
            diff.append(f"{_date_plain(det['ranges'][0][0])}부터 {_theme(primary, n)}이 더해지고 이후로 이어질 수 있음(10년 큰 흐름 교체 영향)")
        for n in r["ups_partial"]:
            det = r["ups_detail"][n]
            diff.append(f"{_rng(det['ranges'])} 동안에만 {_theme(primary, n)}이 " + ("새로 나타남" if "신규 출현" in det["kinds"] else "잠시 더해짐"))
        if r["luck_split"] and ld:
            diff.append(f"{_date_plain(ld)} 무렵 큰 흐름이 바뀜")
        t_up = [n for n in r["ups"] if S.STRUCT[n]["polarity"] == "tension" and n not in common_ups]
        caution = (_theme(primary, t_up[0]) + "에 유의") if t_up else ""
        why = ""
        if y in standout:
            reasons = []
            if r["luck_split"] and ld:
                reasons.append(f"{_date_plain(ld)} 무렵 10년 단위 큰 흐름이 바뀌어 그 전후의 구조가 달라지기 때문입니다.")
            for n in extra_up[:1]:
                x = E.period_reason(periods[y], n, _theme(primary, n), r["ups_detail"][n])
                if x:
                    reasons.append(x)
            if r["ups_partial"] and not reasons:
                n = r["ups_partial"][0]
                reasons.append(f"{_rng(r['ups_detail'][n]['ranges'])} 동안 일시적으로 {_theme(primary, n)}이 더해지기 때문입니다(해 전체의 변화는 아님).")
            why = " ".join(reasons) or "다른 해와 구조가 달라지는 정도가 가장 크기 때문입니다."
        rows.append({"year": y, "tone": blk["tone"], "line": TONE_SHORT[blk["tone"]], "change": "; ".join(diff) if diff else "다른 해와 구별되는 구조 변화는 없음", "caution": caution,
                     "standout": y in standout, "why": why})
    uniq = len(set(tones.values()))
    sentences = []
    span = when_phrase(names)
    c_sup = [n for n in common_ups if S.STRUCT[n]["polarity"] == "support"]
    c_ten = [n for n in common_ups if S.STRUCT[n]["polarity"] == "tension"]
    if c_sup and c_ten:
        sentences.append(f"{span} 동안 전반적으로 {_join([_theme(primary, n) for n in c_sup], 2)}이 타고난 모습보다 더 뚜렷한 쪽으로 이어지지만, {_join([_theme(primary, n) for n in c_ten], 2)}도 함께 커져 있어 계속 유의할 점으로 남습니다.")
    elif c_sup or c_ten:
        sentences.append(f"{span} 동안 전반적으로 {_join([_theme(primary, n) for n in (c_sup or c_ten)], 2)}이 타고난 모습보다 더 커진 채로 이어집니다.")
    else:
        sentences.append(f"{span} 동안 타고난 흐름이 전반적으로 비슷하게 이어집니다.")
    if standout:
        sentences.append(f"가장 달라지는 해는 {', '.join(str(y) + '년' for y in standout)}입니다. 이는 변화가 크다는 뜻이지 좋거나 나쁜 일이 일어난다는 뜻은 아닙니다.")
    else:
        part_notes = [(y, n) for y in names for n in yrs[y]["ups_partial"]]
        sentences.append("해마다 뚜렷하게 구별되는 구조 변화는 없어, 연도별 결론이 비슷하게 나옵니다." + (
            f" 다만 {part_notes[0][0]}년 {_rng(yrs[part_notes[0][0]]['ups_detail'][part_notes[0][1]]['ranges'])} 동안에만 잠시 달라지는 구간이 있습니다." if part_notes else ""))
    if luck_changes:
        c0 = luck_changes[0]
        sentences.append(f"{c0['date'][:4]}년 {_date_plain(c0['date'])} 무렵 10년 단위로 바뀌는 큰 흐름이 바뀌므로, 그 전후를 나누어 보는 것이 좋습니다.")
    return {"span": span, "summary": sentences[:4], "years": rows, "standout": standout, "flat": uniq == 1 and not standout, "primary_domain": primary, "_dev": dev}


# ------------------------------------------------------------------ 전체 조립
def _dedupe_across_blocks(blocks: list[dict]) -> list[dict]:
    """같은 답변 안에서 앞 블록이 이미 한 문장을 뒤 블록이 되풀이하지 않게 한다. 한 블록은 최소 2문장을 유지하고, 결론(headline)·반대 근거 문장은 건드리지 않는다."""
    seen: set[str] = set()
    for b in blocks:
        keep = []
        for sent in b["story"]:
            if sent in seen and len([x for x in b["story"] if x not in seen]) >= 2:  # 이미 말한 문장이고, 빼도 새 문장이 2개 이상 남을 때만 뺀다
                continue
            keep.append(sent)
        b["story"] = keep
        seen.update(keep)
    return blocks


def segments_public(period: dict) -> list[dict]:
    """한 해 안의 실제 구간(입춘·10년 큰 흐름 교체)을 화면용으로. 엔진이 나눈 구간을 그대로 옮기며 새로 판단하지 않는다.
    share=그 구간이 해에서 차지하는 비율(일수 기준)."""
    segs = period.get("segments") or []
    total = sum(FA._days(s) for s in segs) or 1
    out = []
    for i, s in enumerate(segs):
        note = None
        if i == 0 and len(segs) > 1 and s["from"].endswith("-01-01") and s["sewun"] != segs[-1]["sewun"] and s["luck"] == segs[1]["luck"]:
            note = "입춘 전: 전해의 기운이 적용되는 기간"
        elif i > 0 and s["luck"] != segs[i - 1]["luck"]:
            note = "이 날부터 10년 큰 흐름이 바뀜"
        elif i > 0 and s["sewun"] != segs[i - 1]["sewun"]:
            note = "입춘부터 그해의 기운이 적용"
        out.append({"from": s["from"], "to": s["to"], "days": FA._days(s), "share": round(FA._days(s) / total, 3), "label": f"{S._md(s['from'])}~{S._md(s['to'])}", "note": note})
    return out


def build(pre: dict, ans: dict, question: str = "") -> dict:
    """answer() 가 끝난 뒤 호출. ans: blocks, periods, domains, years, synthesis 를 가진 답변."""
    base = pre["natal_structure"]
    nm = S._natal_map(base)
    years = list(ans.get("years") or [])
    doms = [d for d in ans["domains"] if d != "luck"] or ["overall"]
    periods = ans.get("periods") or []
    P = {p["year"]: p for p in periods}
    rel_all = S._relevant(doms)
    lc = S.luck_change(periods) if periods else []
    yrs = {y: FA.year_reading(P[y], rel_all) for y in P}
    sel = [d for d in doms if d != "overall"]
    primary = sel[0] if sel else "overall"

    def blocks_for(y: int | None) -> list[dict]:
        ld = next((c["date"] for c in lc if y is not None and c["date"][:4] == str(y)), None)
        has_overall = "overall" in doms or not sel
        db = [domain_block(pre, d, [y] if y is not None else [], P.get(y) if y is not None else None, nm, ld, salt=i + 1, show_timing=(i == 0 and not has_overall)) for i, d in enumerate(sel)]
        blocks = ([overall_block(pre, [y] if y is not None else [], P.get(y) if y is not None else None, nm, ld, db, salt=0)] + db) if ("overall" in doms or not db) else db
        return _dedupe_across_blocks(blocks)

    mode = "none" if not years else ("single" if len(years) == 1 else "multi")
    result: dict = {"version": VERDICT_VERSION, "mode": mode, "years": years, "domains": doms}
    if mode in ("none", "single"):
        blocks = blocks_for(years[0] if years else None)
        result["blocks"] = blocks
        result["limits"] = limits_for(pre, years, blocks)
    else:
        period = period_block(pre, years, P, yrs, doms, nm, lc, primary)
        period_dev = period.pop("_dev")  # 내부 추적용(사용자 응답에는 없음)
        result["period"] = period
        detail = {str(y): {"blocks": blocks_for(y)} for y in years}
        result["detail"] = detail
        result["blocks"] = []
        flat_blocks = [b for y in years for b in detail[str(y)]["blocks"]]
        result["limits"] = limits_for(pre, years, flat_blocks, multi_flat=period["flat"])
    allb = result["blocks"] or [b for d in result["detail"].values() for b in d["blocks"]]
    focus_blocks = result["blocks"] if mode != "multi" else result["detail"][str(years[0])]["blocks"]
    cn = calc_notice({"verification": pre["verification"], "variants_count": pre.get("variants_count")}) or {}
    result["segments"] = {str(y): segments_public(P[y]) for y in years if P.get(y)}
    result["months"] = MO.build(pre, years, doms) if years else {}   # v10.3 월별 흐름(사실·관계만, 방향 판정 없음). 다른 결과에 영향 없음   # 화면의 기간 구간 표시용(엔진 구간을 그대로)
    result["profile"] = PF.build(pre, P, years, focus_blocks, cn.get("alerts", []))   # v9.3: 명식 전체 종합 통변(사용자용). 내부 근거는 internal.profile 로
    profile_internal = result["profile"].pop("internal")
    syn = ans.get("synthesis") or {}
    internal_claims = {}
    for b in allb:
        internal_claims.setdefault(b["domain"], [])
        internal_claims[b["domain"]] = sorted(set(internal_claims[b["domain"]]) | set(b.pop("_claims", [])))
    if mode == "multi":
        for b in result["blocks"]:
            b.pop("_claims", None)
    result["internal"] = {"claim_ids": syn.get("claim_ids", []), "block_claim_ids": internal_claims, "ruleset_version": pre["ruleset_version"], "verification_status": pre["verification"]["status"],
                          "scores": {b["domain"]: b["scores"] for b in allb}, "tones": {b["domain"]: b["tone"] for b in allb},
                          "profile": profile_internal, "judge": {"version": JD.JUDGE_VERSION, "consistent": all(JD.consistent(b["tone"], b["scores"]["S"], b["scores"]["T"]) for b in allb)},
                          "counter_evidence": {b["domain"]: b["counter"] for b in allb},
                          "trace": {str(y): E.trace_year(pre, ans, y, doms) for y in years}, "period_dev": ({str(k): v for k, v in period_dev.items()} if mode == "multi" else {}),
                          "conditions": ["어조는 구조 변화(돕는 흐름 S, 부딪히거나 나누는 흐름 T)의 크기로 정한 구현자 규약", "해의 절반 이상을 덮는 구간만 '그해의 변화'로 셈(구현자 규약)", "고전 원문 대조 전 규칙 포함"],
                          "verdict_version": VERDICT_VERSION}
    return result


# ------------------------------------------------------------------ 사용자 응답(내부 근거 제외)
INTERNAL_KEYS = ("internal",)


def public_view(ans: dict) -> dict:
    """사용자에게 내보내는 답변. 규칙 번호·근거 번호·구조 이름·원시 근거·검증기 내부 정보는 포함하지 않는다(엔진 내부와 저장본에는 그대로 있다)."""
    if ans.get("refused"):
        return {"refused": True, "message": ans.get("message"), "alternative": ans.get("alternative")}
    v = {k: val for k, val in ans["verdict"].items() if k not in INTERNAL_KEYS}
    return {"refused": False, "years": ans.get("years", []), "domains": ans.get("domains", []), "verdict": v, "qa": ans.get("qa")}


def _span(minutes: float) -> str:
    if minutes < 60:
        return f"약 {max(1, int(minutes))}분"
    if minutes < 2880:
        return f"약 {int(minutes // 60)}시간"
    return f"약 {int(minutes // 1440)}일"


def calc_notice(summary: dict) -> dict | None:
    """계산 신뢰 상태를 쉬운 말로. level: ok(참고) / check(입력 확인 권장) / caution(다른 계산과 불일치). 검증 등급·도구명 같은 내부 값은 내보내지 않는다."""
    ver = summary.get("verification")
    if not ver:
        return None
    items, level, alerts = [], "ok", []
    cross = ver.get("independent_crosscheck") or {}
    if cross and cross.get("agree") is False:
        level = "caution"
        items.append("다른 계산 방식과 비교했을 때 네 기둥 중 일부가 다르게 나왔습니다. 출생 정보를 다시 확인하고, 이 결과는 참고로만 봐 주세요.")
        alerts.append(items[-1])
    elif cross:
        items.append("다른 계산 방식으로 다시 계산해 보아도 네 기둥이 같게 나왔습니다.")
    near = ver.get("nearest_jie_minutes")
    amb = (ver.get("ambiguity") or {}).get("ambiguous")
    if amb or (near is not None and near < 1440):
        if level == "ok":
            level = "check"
        items.append("태어난 시각이 달이 바뀌는 날(절기) 경계" + (f"에서 {_span(near)} 이내" if near is not None else "에 가깝") + "라서, 시각이 조금만 달라도 월 기둥이 바뀔 수 있습니다. 출생 시각을 다시 확인해 보세요.")
        alerts.append(items[-1])
    elif near is not None:
        items.append("달이 바뀌는 날(절기)과 충분히 떨어져 있어 날짜·시각이 조금 달라도 월 기둥은 바뀌지 않습니다.")
    if (summary.get("variants_count") or 1) > 1:
        if level == "ok":
            level = "check"
        items.append("입력 조건(출생 시각 처리 방식 등)에 따라 달라질 수 있는 명식이 있습니다. 결과 화면의 다른 명식도 함께 확인해 보세요.")
        alerts.append(items[-1])
    if not ver.get("may_claim_verified"):
        items.append("공식 자료와의 대조가 모두 끝난 계산은 아니어서 ‘검증 완료’라고 표시하지 않습니다. 계산 결과는 참고용입니다.")
    title = {"ok": "계산 상태: 참고할 수 있습니다", "check": "계산 상태: 입력을 한 번 더 확인해 주세요", "caution": "계산 상태: 다른 계산과 달라 주의가 필요합니다"}[level]
    return {"level": level, "title": title, "items": items, "alerts": alerts}


def public_precommit(summary: dict) -> dict:
    """사전 분석 기록 요약에서 사용자에게 필요한 것만: 네 기둥과 분석 범위, 계산 상태(쉬운 말). 계산 프로필·해시·규칙 버전·검증 세부는 제외."""
    return {"pillars": summary.get("pillars"), "years": summary.get("years", []), "domains": summary.get("domains", []), "calc": calc_notice(summary)}


REALITY_PLAIN = {"consistent": "처음 해석에서 이 주제와 이어지는 흐름이 있다고 읽었던 기록과 부합합니다. 다만 흐름이 있다는 것과 실제 사건은 다르며, 적중으로 세지 않습니다.",
                 "inconsistent": "처음 해석에서는 이 주제와 이어지는 흐름이 뚜렷하지 않다고 읽었습니다. 기록은 고치지 않고 해석 틀의 한계로 남깁니다.",
                 "not_judged": "처음 해석에서 다루지 않은 주제나 기간이라 판단하지 않습니다.",
                 "condition_changed": "입력 조건이 바뀌면 처음 해석을 고치지 않고 새로 분석해야 합니다."}


def public_reality(res: dict) -> dict:
    """현실 사건 분류 결과에서 구조 이름·근거를 걷어내고 쉬운 설명만 돌려준다."""
    return {"outcome": res["outcome"], "explanation": REALITY_PLAIN.get(res["outcome"], "")}


def public_turn(t: dict) -> dict:
    b = t["body"]
    if t["kind"] == "answer":
        return {"n": t["n"], "created_at": t["created_at"], "kind": "answer", "body": {"question": b["question"], "view": bool(b.get("view")), "answer": public_view(b["answer"])}}
    if t["kind"] == "feedback":
        return {"n": t["n"], "created_at": t["created_at"], "kind": "feedback", "body": {"rating": b.get("rating"), "target": b.get("target"), "note": b.get("note", "")}}
    return {"n": t["n"], "created_at": t["created_at"], "kind": "reality", "body": {"event": b["event"], "result": public_reality(b["result"])}}
