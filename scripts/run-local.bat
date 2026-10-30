@echo off
rem 로컬에서 회원 기능까지 포함해 실행: Postgres(Docker) + API + 웹(같은 주소). http://127.0.0.1:8000/consult.html
cd /d "%~dp0.."
docker compose up -d db || (echo Docker 가 필요합니다. & pause & exit /b 1)
set DATABASE_URL=postgresql://myeongri:local-dev-only@127.0.0.1:55498/myeongri
set SERVE_WEB=%CD%\web
cd backend
python -m pip install -r ..\requirements.txt
echo 접속: http://127.0.0.1:8000/consult.html  (점검: python -m tools.smoke_member http://127.0.0.1:8000)
python -m uvicorn app.main:app --port 8000
