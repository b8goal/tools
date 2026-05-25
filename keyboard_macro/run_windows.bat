@echo off
cd /d %~dp0

py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 (
  echo Python 3.11 or newer is required.
  echo Install it with: winget install --id Python.Python.3.11 -e
  pause
  exit /b 1
)

if exist .venv (
  .venv\Scripts\python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
  if errorlevel 1 (
    echo Recreating .venv with Python 3.11...
    rmdir /s /q .venv
  )
)

if not exist .venv (
  py -3.11 -m venv .venv
)

call .venv\Scripts\activate
python -m pip install -U pip
pip install -r requirements.txt
python run_app.py
pause
