@echo off
REM duetfolio one-click launcher (Windows): starts backend + frontend, opens the dashboard.
REM Just double-click this file. (English-only on purpose: zero encoding issues on any Windows.)

cd /d "%~dp0backend"
where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found on PATH.
  echo   Install Python 3.10+ from https://www.python.org/downloads/
  echo   and tick "Add python.exe to PATH" during installation.
  echo   Then double-click start.bat again.
  pause
  exit /b 1
)
if not exist .venv (
  echo [backend 1/3] Creating virtual environment...
  python -m venv .venv
)
call .venv\Scripts\activate.bat
echo [backend 2/3] Installing dependencies (slow on first run)...
pip install -q -r requirements.txt
echo [backend 3/3] Starting backend in a new window...
start "duetfolio-backend" cmd /k "call .venv\Scripts\activate.bat && uvicorn app.main:app --reload"

cd /d "%~dp0frontend"
where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js not found on PATH.
  echo   Install Node.js 18+ from https://nodejs.org/
  echo   Then double-click start.bat again.
  pause
  exit /b 1
)
if not exist "node_modules\.bin\vite.cmd" (
  echo [frontend 1/2] Installing dependencies (slow on first run, needs Node.js 18+)...
  call npm install
  if not exist "node_modules\.bin\vite.cmd" (
    echo [ERROR] npm install did not finish correctly. Check your network,
    echo   then double-click start.bat again (or run "npm install" manually).
    pause
    exit /b 1
  )
)
echo [frontend 2/2] Starting frontend in a new window...
start "duetfolio-frontend" cmd /k "npm run dev"

echo.
echo Waiting ~10 seconds, then opening the dashboard:
echo   http://127.0.0.1:5173
echo.
echo API docs: http://127.0.0.1:8000/docs
echo For East Money real-time quotes, close both windows and run in PowerShell instead:
echo   $env:MARKET_PROVIDER="eastmoney"
echo   .\start.bat
timeout /t 10 /nobreak >nul
start http://127.0.0.1:5173
