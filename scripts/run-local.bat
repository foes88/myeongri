@echo off
chcp 65001 >nul
rem 개인용 로컬 실행: Postgres(Docker, 127.0.0.1:55498) + API + 웹(127.0.0.1:%PORT%, 기본 8765). 가입은 닫혀 있다(소유자 계정: scripts\create-owner.bat).
cd /d "%~dp0.."
call scripts\_personal_env.bat || exit /b 1
docker compose up -d db || (echo Docker 가 필요합니다. & pause & exit /b 1)
netstat -ano | findstr /R /C:"127.0.0.1:%PORT% .*LISTENING" >nul && (echo [오류] 포트 %PORT% 가 이미 사용 중입니다. set PORT=다른번호 후 다시 실행하세요. & pause & exit /b 1)
cd backend
python -m pip install -q -r ..\requirements.txt
echo 접속: http://127.0.0.1:%PORT%/consult.html   (종료: Ctrl+C)
python -m uvicorn app.main:app --host 127.0.0.1 --port %PORT% --log-level warning
