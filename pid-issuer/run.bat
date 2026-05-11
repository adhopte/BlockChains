@echo off
REM ============================================================
REM  EU PID Issuer Station – Windows launcher
REM  Double-click this file to start the service.
REM ============================================================
setlocal enabledelayedexpansion
title EU PID Issuer Station

echo.
echo  ============================================================
echo   EU PID Issuer Station
echo  ============================================================
echo.

REM ── Optional overrides (uncomment to customise) ──────────────
REM set WATCH_PATH=C:\icvs-local-exports
REM set ISSUER_PORT=8080
REM set ISSUER_COUNTRY=BE
REM set ISSUER_AUTHORITY=My National Registry

REM ── Defaults ─────────────────────────────────────────────────
if not defined WATCH_PATH  set WATCH_PATH=C:\icvs-local-exports
if not defined ISSUER_PORT set ISSUER_PORT=8080

REM ── Step 1: Locate Python ────────────────────────────────────
echo [1/4] Checking Python...

REM Try plain 'python' first
python --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON=python
    goto :python_ok
)

REM Try 'python3'
python3 --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON=python3
    goto :python_ok
)

REM Try Windows Store / py launcher
py --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON=py
    goto :python_ok
)

echo.
echo  ERROR: Python not found.
echo.
echo  Install Python 3.11 or newer from:
echo    https://www.python.org/downloads/
echo.
echo  IMPORTANT: During installation, tick the box:
echo    "Add Python to PATH"
echo.
echo  After installing, re-run this file.
pause
exit /b 1

:python_ok
for /f "tokens=*" %%v in ('%PYTHON% --version 2^>^&1') do set PY_VER=%%v
echo  Found: %PY_VER%

REM Check version is 3.11+
%PYTHON% -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python 3.11+ is required. You have %PY_VER%.
    echo  Download the latest version from https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM ── Step 2: Virtual environment ──────────────────────────────
echo [2/4] Setting up virtual environment...

if not exist ".venv\Scripts\activate.bat" (
    echo  Creating .venv ...
    %PYTHON% -m venv .venv
    if errorlevel 1 (
        echo.
        echo  ERROR: Could not create virtual environment.
        echo  Try running: %PYTHON% -m venv .venv
        echo.
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo.
    echo  ERROR: Could not activate virtual environment.
    echo  Delete the .venv folder and run this file again.
    echo.
    pause
    exit /b 1
)
echo  Virtual environment ready.

REM ── Step 3: Install dependencies ─────────────────────────────
echo [3/4] Installing dependencies (first run may take 1-2 minutes)...

python -m pip install --upgrade pip --quiet 2>nul
python -m pip install -r requirements.txt --quiet 2>nul

REM pip exit codes are unreliable on Windows - verify imports directly instead
python -c "import flask, cryptography, qrcode, PIL, watchdog" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  Some packages are missing. Retrying with verbose output...
    echo.
    python -m pip install -r requirements.txt
    python -c "import flask, cryptography, qrcode, PIL, watchdog" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo  ERROR: Could not import required packages after install.
        echo.
        echo  Try running this command manually in Command Prompt:
        echo    pip install flask cryptography "qrcode[pil]" Pillow watchdog
        echo.
        pause
        exit /b 1
    )
)
echo  Dependencies OK.

REM ── Step 4: Check port ───────────────────────────────────────
echo [4/4] Checking port %ISSUER_PORT%...

netstat -an 2>nul | findstr ":%ISSUER_PORT% " | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo.
    echo  WARNING: Port %ISSUER_PORT% is already in use.
    echo  Either:
    echo    - Stop the other program using that port, or
    echo    - Edit this file and change ISSUER_PORT to e.g. 8081
    echo.
    set /p CONTINUE="Continue anyway? (y/n): "
    if /i not "!CONTINUE!"=="y" exit /b 1
)

REM ── Launch ───────────────────────────────────────────────────
echo.
echo  ============================================================
echo   Starting server...
echo.
echo   Watch folder : %WATCH_PATH%
echo   Browser URL  : http://localhost:%ISSUER_PORT%
echo.
echo   To stop: close this window or press Ctrl+C
echo  ============================================================
echo.

REM Open browser after 2 second delay (gives Flask time to start)
start "" cmd /c "timeout /t 2 >nul && start http://localhost:%ISSUER_PORT%"

python app.py
if errorlevel 1 (
    echo.
    echo  The server stopped with an error (see above).
    echo.
)

pause
