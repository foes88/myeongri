@echo off
chcp 65001 >nul
rem 개인용 공통 환경(run-local.bat / create-owner.bat 이 호출). 키 원문은 화면에 출력하지 않는다.
set "MYEONGRI_HOME=%USERPROFILE%\.myeongri"
set "KEYFILE=%MYEONGRI_HOME%\app_data_key.txt"
if not exist "%MYEONGRI_HOME%" mkdir "%MYEONGRI_HOME%"
if not exist "%KEYFILE%" (
  python -c "from cryptography.fernet import Fernet; open(r'%KEYFILE%','w').write(Fernet.generate_key().decode())"
  echo [안내] 암호화 키를 새로 만들었습니다: %KEYFILE%
  echo        이 파일을 잃어버리면 저장된 상담을 복호화할 수 없습니다. 비밀번호 관리자나 외장 저장소에 따로 백업하세요. Git/클라우드 동기화 폴더에 두지 마세요.
)
set /p APP_DATA_KEY=<"%KEYFILE%"
if not defined APP_DATA_KEY (echo [오류] 키 파일을 읽지 못했습니다. & exit /b 1)
set ACCOUNTS_ENABLED=1
set ACCOUNTS_REGISTRATION=closed
if not defined PORT set PORT=8765
set DATABASE_URL=postgresql://myeongri:local-dev-only@127.0.0.1:55498/myeongri
set "SERVE_WEB=%~dp0..\web"
