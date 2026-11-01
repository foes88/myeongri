@echo off
chcp 65001 >nul
rem 소유자(본인) 계정 만들기. 사용: scripts\create-owner.bat 내이메일@주소  (비밀번호는 입력창에서 입력, 기록되지 않음)
cd /d "%~dp0.."
if "%~1"=="" (echo 사용: scripts\create-owner.bat 이메일 & exit /b 2)
call scripts\_personal_env.bat || exit /b 1
docker compose up -d db || exit /b 1
cd backend
python -m tools.create_owner %1
