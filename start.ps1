# duetfolio one-click launcher (PowerShell).
# Put this file in the duetfolio folder (next to start.bat), then
# right-click -> "Run with PowerShell". Single window: backend serves the frontend.
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "[duetfolio launcher ps1] $root"

if (!(Test-Path "$root\backend") -or !(Test-Path "$root\frontend")) {
  Write-Host ""
  Write-Host "[ERROR] backend/ and frontend/ not found next to this script."
  Write-Host "Move start.ps1 into the duetfolio folder (the one containing start.bat),"
  Write-Host "then right-click -> 'Run with PowerShell' again."
  Read-Host "Press Enter to close"
  exit 1
}

try {
  Set-Location "$root\backend"
  if (!(Test-Path .venv)) {
    Write-Host "[1/4] Creating virtual environment..."
    python -m venv .venv
  }
  Write-Host "[2/4] Installing backend dependencies (slow on first run)..."
  & .\.venv\Scripts\python.exe -m pip install -q -r requirements.txt

  Set-Location "$root\frontend"
  if (!(Test-Path node_modules\.bin\vite.cmd)) {
    Write-Host "[3/4] Installing frontend dependencies (slow on first run)..."
    npm install
  }
  if (!(Test-Path dist\index.html)) {
    Write-Host "[4/4] Building frontend (one-time)..."
    npm run build
  }

  Set-Location "$root\backend"
  Write-Host ""
  Write-Host "Starting duetfolio (single window): http://127.0.0.1:8000"
  Write-Host "Keep this window open while using the app. Close it to stop."
  Start-Sleep -Seconds 2
  Start-Process "http://127.0.0.1:8000"
  & .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
}
catch {
  Write-Host ""
  Write-Host "[ERROR] $($_.Exception.Message)"
  Read-Host "Press Enter to close"
}
