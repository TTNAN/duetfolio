@echo off
REM duetfolio 一键启动（Windows）
REM 双击运行：自动创建虚拟环境、安装依赖、启动后端
cd /d "%~dp0backend"
if not exist .venv (
  echo [1/3] 正在创建虚拟环境...
  python -m venv .venv
)
call .venv\Scripts\activate.bat
echo [2/3] 正在安装依赖（首次较慢）...
pip install -q -r requirements.txt
echo [3/3] 正在启动 duetfolio 后端...
echo.
echo 启动成功后，浏览器打开 http://127.0.0.1:8000/docs
echo 如需东方财富实时行情，关闭本窗口，用 PowerShell 执行：
echo   $env:MARKET_PROVIDER="eastmoney"
echo   .\start.bat
echo.
uvicorn app.main:app --reload
pause
