@echo off
set LAUNCHER_VER=2026-10-02e
echo [duetfolio launcher %LAUNCHER_VER%] %~f0
REM duetfolio one-click launcher (Windows).
REM Starts the backend, which also serves the built frontend dashboard.
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
  echo [1/4] Creating virtual environment...
  call python -m venv .venv
)
call .venv\Scripts\activate.bat
echo [2/4] Installing backend dependencies (slow on first run)...
call python -m pip install -q -r requirements.txt

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
  echo [3/4] Installing frontend dependencies (slow on first run)...
  call npm install
  if not exist "node_modules\.bin\vite.cmd" (
    echo [ERROR] npm install did not finish correctly. Check your network,
    echo   then double-click start.bat again (or run "npm install" manually).
    pause
    exit /b 1
  )
)
if not exist "dist\index.html" (
  echo [4/4] Building frontend (one-time, ~30 seconds)...
  call npm run build
)

echo.
echo Starting duetfolio (single window). Opening the dashboard:
echo   http://127.0.0.1:8000
echo.
echo API docs: http://127.0.0.1:8000/docs
echo For East Money real-time quotes, close this window and run in PowerShell instead:
echo   $env:MARKET_PROVIDER="eastmoney"
echo   .\start.bat
echo.
echo Keep this window open while using the app. Close it to stop.
timeout /t 3 /nobreak >nul
start http://127.0.0.1:8000
cd /d "%~dp0backend"
call .venv\Scripts\activate.bat
echo Starting server (this window stays open)...
call python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
echo.
echo [stopped] The server has exited. Press any key to close this window.
pause >nul
