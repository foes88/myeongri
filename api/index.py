"""Vercel 서버리스 진입점: FastAPI 앱(일회성 분석 API)을 노출한다. 저장소 쓰기 없음(읽기 전용 파일시스템 전제)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.main import app  # noqa: E402,F401  (Vercel 이 ASGI 변수 app 을 사용)
