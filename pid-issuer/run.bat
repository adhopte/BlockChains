@echo off
REM ============================================================
REM  EU PID Issuer Station – Windows launcher
REM ============================================================
setlocal

REM ── Optional overrides ──────────────────────────────────────
REM Uncomment and edit these lines to customise behaviour:

REM set WATCH_PATH=C:\icvs-local-exports
REM set ISSUER_PORT=8080
REM set ISSUER_COUNTRY=BE
REM set ISSUER_AUTHORITY=My National Registry

REM ── Auto-detect python ──────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: python not found. Install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

REM ── Create / activate venv ──────────────────────────────────
if not exist ".venv\Scripts\activate.bat" (
    echo Creating virtual environment…
    python -m venv .venv
)
call .venv\Scripts\activate.bat

REM ── Install dependencies ────────────────────────────────────
echo Installing / checking dependencies…
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt

REM ── Launch ──────────────────────────────────────────────────
echo.
echo Starting EU PID Issuer Station…
echo Open your browser at http://localhost:8080
echo.
start "" "http://localhost:8080"
python app.py

pause
