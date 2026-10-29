from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

from .astro_core import TimeProfile, calculate_chart
from .mingli import analyze_chart_variants, analyze_periods

app = FastAPI(title="Myeongri Atelier API", version="0.1.0", description="Prototype: Astro-Core calendar engine (V1 not yet granted); rule engine not implemented")

class BirthInput(BaseModel):
    calendar: Literal['solar','lunar'] = 'solar'
    birth_date: str = Field(examples=['2000-01-01'])
    birth_time: str | None = Field(default=None, examples=['19:25'])
    birth_place: str = '서울특별시'
    gender: Literal['male','female']
    is_leap_month: bool = False
    calculation_profile: Literal['standard','mean_solar','apparent_solar'] = 'standard'

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
