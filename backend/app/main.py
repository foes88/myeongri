import os

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Literal

from .astro_core import TimeProfile, calculate_chart
from .consult import agent as consult_agent
from .consult import store as consult_store
from .mingli import analyze_chart_variants, analyze_periods

import logging

consult_log = logging.getLogger('myeongri.consult')  # 식별자·상태만 기록. 명식·출생정보·질문 원문·토큰은 절대 기록하지 않는다

app = FastAPI(title="Myeongri Atelier API", version="0.1.0", description="Prototype: Astro-Core calendar engine (V1 not yet granted); rule engine not implemented")

class BirthInput(BaseModel):
    calendar: Literal['solar','lunar'] = 'solar'
    birth_date: str = Field(examples=['2000-01-01'])
    birth_time: str | None = Field(default=None, examples=['19:25'])
    birth_place: str = '서울특별시'
    gender: Literal['male','female']
    is_leap_month: bool = False
    calculation_profile: Literal['standard','mean_solar','apparent_solar'] = 'standard'

app.add_middleware(CORSMiddleware, allow_origins=[o for o in os.environ.get('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if o],
                   allow_methods=['GET', 'POST', 'DELETE'], allow_headers=['Content-Type', 'X-Consult-Token'])

@app.get('/api/v1/health')
def health():
    return {'status':'ok', 'calendar_verified':False, 'calendar_engine':'astro-core-0.1.0'}

_TIME_PROFILE = {'standard': TimeProfile.CIVIL_TIME, 'mean_solar': TimeProfile.LOCAL_MEAN_SOLAR_TIME,
                 'apparent_solar': TimeProfile.LOCAL_APPARENT_SOLAR_TIME}

@app.post('/api/v1/calendar/calculate')
def calendar(b: BirthInput):
    """결정론적 만세력(Astro-Core). 개인정보는 저장·로그하지 않는다. verification.status 가 V1 이 아니면 확정 명식이 아니다."""
    try:
        y, m, d = (int(x) for x in b.birth_date.split('-'))
        hh = mm = None
        if b.birth_time:
            hh, mm = (int(x) for x in b.birth_time.split(':'))
        return calculate_chart(year=y, month=m, day=d, hour=hh, minute=mm or 0, gender=b.gender, calendar=b.calendar,
                               is_leap_month=b.is_leap_month, place=b.birth_place,
                               time_profile=_TIME_PROFILE[b.calculation_profile]).to_dict()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@app.post('/api/v1/analysis/structure')
def structure(b: BirthInput):
    """Mingli-Graph 1·2층(세력·간지 관계). 사실과 후보만 반환하며 길흉·미래 예측은 하지 않는다."""
    chart = calendar(b)
    return {'chart': chart, 'structure': analyze_chart_variants(chart)}

class PeriodRequest(BirthInput):
    years: list[int] = Field(examples=[[2030]], min_length=1, max_length=10)
    variant_id: str = 'v1'

@app.post('/api/v1/analysis/periods')
def periods(b: PeriodRequest):
    """특정 연도·복수 연도의 대운·세운 구조 변화(대운 교체·입춘 구간 분리). 사건 예측이 아니다."""
    chart = calendar(b)
    try:
        return analyze_periods(chart, b.years, b.variant_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@app.post('/api/v1/interpretations')
def interpret():
    raise HTTPException(status_code=501, detail='규칙 엔진/근거 검증/AI 해석이 아직 연결되지 않았습니다.')


# ---------------------------------------------------------------- 상담 (Consult-Agent, 결정론적 템플릿; LLM 미사용)
class ConsultCreate(BirthInput):
    years: list[int] = Field(default_factory=list, max_length=10)
    domains: list[str] = Field(default_factory=lambda: ['overall'])
    depth: Literal['summary', 'detailed', 'expert'] = 'summary'
    variant_id: str | None = None
    store_birth: bool = False
    first_question: str = ''


class AskBody(BaseModel):
    question: str = Field(max_length=500)
    domains: list[str] = []
    years: list[int] = Field(default_factory=list, max_length=10)
    depth: Literal['summary', 'detailed', 'expert'] | None = None


class RealityBody(BaseModel):
    kind: Literal['event', 'condition'] = 'event'
    type: str = ''
    year: int | None = None
    note: str = Field(default='', max_length=500)


def _auth(tid: str, token: str | None):
    if not consult_store.check_token(tid, token):
        raise HTTPException(status_code=403, detail='상담 접근 권한이 없습니다')


@app.post('/api/v1/consultations')
def consult_create(b: ConsultCreate):
    """사전 분석 기록(precommit)을 먼저 만들어 고정한 뒤 상담을 시작한다. 사용자의 현실 정보는 이 단계에서 받지 않는다."""
    from .consult import domains as D
    bad = [d for d in b.domains if d not in D.DOMAINS]
    if bad:
        raise HTTPException(status_code=422, detail=f'알 수 없는 분야: {bad}')
    chart = calendar(b)
    if len(chart['variants']) > 1 and not b.variant_id:
        raise HTTPException(status_code=409, detail={'code': 'VARIANT_REQUIRED', 'variants': chart['variants'],
                                                      'message': '프로필에 따라 명식이 여러 개로 갈립니다. variant_id 를 선택하세요(자동 선택하지 않음)'})
    try:
        pre = consult_agent.build_precommit(chart, variant_id=b.variant_id or chart['variants'][0]['variant_id'], years=sorted(set(b.years)), domains=b.domains,
                                            depth=b.depth, input_fingerprint=b.model_dump(exclude={'first_question', 'store_birth'}), store_birth=b.store_birth)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    pre['content_hash'] = consult_store.sha256({k: v for k, v in pre.items() if k != 'content_hash'})
    token, th = consult_store.new_token()
    tid = consult_store.create_thread(pre, th, {'created_at': pre['generated_at']})
    first = consult_agent.answer(pre, b.first_question or '종합 상담을 시작합니다', domains_=b.domains, years=b.years)
    consult_store.append_turn(tid, {'kind': 'answer', 'question': b.first_question, 'answer': first})
    consult_log.info('consult.create thread=%s depth=%s domains=%d years=%d', tid, b.depth, len(b.domains), len(b.years))
    return {'thread_id': tid, 'access_token': token, 'precommit': {k: pre[k] for k in ('content_hash', 'generated_at', 'ruleset_version', 'engine_version',
            'model_version', 'calculation_profile_id', 'variant_id', 'variants_count', 'verification', 'domains', 'years', 'depth')}, 'answer': first}


@app.post('/api/v1/consultations/{tid}/ask')
def consult_ask(tid: str, b: AskBody, x_consult_token: str | None = Header(default=None)):
    _auth(tid, x_consult_token)
    try:
        pre = consult_store.read_precommit(tid)
    except consult_store.TamperError as e:
        raise HTTPException(status_code=500, detail=str(e))
    ans = consult_agent.answer(pre, b.question, domains_=b.domains, years=b.years, depth=b.depth)
    consult_store.append_turn(tid, {'kind': 'answer', 'question': b.question, 'answer': ans})
    consult_log.info('consult.ask thread=%s refused=%s', tid, bool(ans.get('refused')))
    return ans


@app.post('/api/v1/consultations/{tid}/reality')
def consult_reality(tid: str, b: RealityBody, x_consult_token: str | None = Header(default=None)):
    """현실 사건/조건 입력. 사전 분석 기록은 바뀌지 않으며, 부합/불일치/미판단/조건변경으로만 분류한다."""
    _auth(tid, x_consult_token)
    pre = consult_store.read_precommit(tid)
    res = consult_agent.classify_event(pre, b.model_dump())
    consult_store.append_turn(tid, {'kind': 'reality_input', 'event': b.model_dump(), 'classification': res})
    consult_log.info('consult.reality thread=%s outcome=%s', tid, res['outcome'])
    return res


@app.get('/api/v1/consultations/{tid}')
def consult_get(tid: str, x_consult_token: str | None = Header(default=None)):
    _auth(tid, x_consult_token)
    pre = consult_store.read_precommit(tid)
    return {'thread_id': tid, 'precommit_summary': {k: pre[k] for k in ('content_hash', 'generated_at', 'ruleset_version', 'calculation_profile_id', 'variant_id',
            'verification', 'domains', 'years', 'depth', 'disclaimer')}, 'turns': consult_store.read_turns(tid)}


class ReanalyzeBody(BaseModel):
    reason: str = Field(max_length=200)
    pa_profile: Literal['modern_6', 'sanmyeongtonghoe_4'] = 'modern_6'


@app.post('/api/v1/consultations/{tid}/reanalyze')
def consult_reanalyze(tid: str, b: ReanalyzeBody, x_consult_token: str | None = Header(default=None)):
    """규칙 버전·학파 프로필이 바뀐 재분석을 새 기록(revision)으로 추가한다. 원본 사전 분석 기록은 그대로 보존된다."""
    _auth(tid, x_consult_token)
    base = consult_store.read_precommit(tid)
    new, diff = consult_agent.reanalyze(base, reason=b.reason, profiles={'pa': b.pa_profile})
    n = consult_store.add_revision(tid, new, b.reason, diff)
    consult_store.append_turn(tid, {'kind': 'revision', 'revision': n, 'reason': b.reason, 'diff': diff})
    consult_log.info('consult.reanalyze thread=%s revision=%d', tid, n)
    return {'revision': n, 'original_hash': base['content_hash'], 'diff': diff}


@app.get('/api/v1/consultations/{tid}/revisions')
def consult_revisions(tid: str, x_consult_token: str | None = Header(default=None)):
    _auth(tid, x_consult_token)
    return {'original_hash': consult_store.read_precommit(tid)['content_hash'], 'revisions': consult_store.read_revisions(tid)}


@app.delete('/api/v1/consultations/{tid}', status_code=204)
def consult_delete(tid: str, x_consult_token: str | None = Header(default=None)):
    _auth(tid, x_consult_token)
    consult_store.delete_thread(tid)
