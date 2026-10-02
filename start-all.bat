@echo off
REM duetfolio 一键启动全部（Windows）：后端 + 前端
REM 双击运行，两个窗口分别启动，浏览器打开 http://127.0.0.1:5173

cd /d "%~dp0backend"
if not exist .venv (
  echo [backend 1/3] 正在创建虚拟环境...
  python -m venv .venv
)
call .venv\Scripts\activate.bat
echo [backend 2/3] 正在安装依赖（首次较慢）...
pip install -q -r requirements.txt
echo [backend 3/3] 正在启动后端（新窗口）...
start "duetfolio-backend" cmd /k "call .venv\Scripts\activate.bat && uvicorn app.main:app --reload"

cd /d "%~dp0frontend"
if not exist node_modules (
  echo [frontend 1/2] 正在安装依赖（首次较慢）...
  call npm install
)
echo [frontend 2/2] 正在启动前端（新窗口）...
start "duetfolio-frontend" cmd /k "npm run dev"

echo.
echo 全部启动中，稍等 10 秒后浏览器打开：
echo   前端界面 http://127.0.0.1:5173
echo   API 文档   http://127.0.0.1:8000/docs
echo.
echo 如需东方财富实时行情：关闭两个窗口，改用 PowerShell：
echo   $env:MARKET_PROVIDER="eastmoney"
echo   .\start-all.bat
pause
