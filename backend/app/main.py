from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

app = FastAPI(title="Myeongri Atelier API", version="0.1.0", description="Prototype: calendar engine intentionally not implemented")

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
    return {'status':'ok', 'calendar_verified':False}

@app.post('/api/v1/calendar/calculate')
def calendar(_:BirthInput):
    raise HTTPException(status_code=501, detail='검증된 만세력 계산 엔진이 아직 연결되지 않았습니다. 계산 결과를 임의로 생성하지 않습니다.')

@app.post('/api/v1/interpretations')
def interpret():
    raise HTTPException(status_code=501, detail='규칙 엔진/근거 검증/AI 해석이 아직 연결되지 않았습니다.')
