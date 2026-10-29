@echo off
cd /d "%~dp0..\backend"
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
pause
