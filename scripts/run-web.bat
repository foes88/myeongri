@echo off
cd /d "%~dp0.."
echo Open http://localhost:5173
python -m http.server 5173 --directory web
pause
