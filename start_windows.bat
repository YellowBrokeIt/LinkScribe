@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creating Python environment...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo Python 3.10+ is required. Install Python from python.org.
    pause
    exit /b 1
  )
)
echo Installing or checking dependencies...
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed.
  pause
  exit /b 1
)
echo.
echo LinkScribe starts at http://127.0.0.1:8765
start "" "http://127.0.0.1:8765"
.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8765
pause
