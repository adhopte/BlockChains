@echo off
REM ============================================================
REM  EU PID Issuer – Environment checker
REM  Run this first if run.bat doesn't work.
REM  It checks everything needed and tells you what to fix.
REM ============================================================
setlocal
title PID Issuer – Environment Check
set PASS=0
set FAIL=0

echo.
echo  ============================================================
echo   EU PID Issuer – Environment Check
echo  ============================================================
echo.

REM ── Python ───────────────────────────────────────────────────
echo Checking Python...
python --version >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo   [OK] %%v
    set /a PASS+=1
) else (
    echo   [FAIL] Python not found in PATH
    echo          Fix: Install from https://www.python.org/downloads/
    echo          Tick "Add Python to PATH" during install
    set /a FAIL+=1
)

REM ── pip ──────────────────────────────────────────────────────
echo Checking pip...
python -m pip --version >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=*" %%v in ('python -m pip --version 2^>^&1') do echo   [OK] %%v
    set /a PASS+=1
) else (
    echo   [FAIL] pip not available
    echo          Fix: python -m ensurepip
    set /a FAIL+=1
)

REM ── Required modules ─────────────────────────────────────────
echo Checking required packages...

for %%m in (flask cryptography qrcode PIL watchdog) do (
    python -c "import %%m" >nul 2>&1
    if not errorlevel 1 (
        echo   [OK] %%m
        set /a PASS+=1
    ) else (
        echo   [MISSING] %%m  ^(will be installed by run.bat^)
    )
)

REM ── Port 8080 ─────────────────────────────────────────────────
echo Checking port 8080...
netstat -an 2>nul | findstr ":8080 " | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo   [WARN] Port 8080 is already in use
    echo          Fix: stop the other program or change ISSUER_PORT in run.bat
) else (
    echo   [OK] Port 8080 is free
    set /a PASS+=1
)

REM ── Watch folder ─────────────────────────────────────────────
echo Checking watch folder...
if exist "C:\icvs-local-exports" (
    echo   [OK] C:\icvs-local-exports exists
    set /a PASS+=1
) else (
    echo   [INFO] C:\icvs-local-exports does not exist yet
    echo          It will be created automatically when IDEMIA exports a file,
    echo          or create it manually: mkdir C:\icvs-local-exports
)

REM ── Network ───────────────────────────────────────────────────
echo Checking network...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    set IP=%%a
    set IP=!IP: =!
    echo   [OK] Local IP: !IP!  ^(use this on the Android wallet if localhost doesn't work^)
    set /a PASS+=1
    goto :ip_done
)
:ip_done

REM ── Summary ───────────────────────────────────────────────────
echo.
echo  ============================================================
echo   Result: %PASS% checks passed, %FAIL% failed
if %FAIL% GTR 0 (
    echo   Fix the [FAIL] items above then run run.bat
) else (
    echo   Everything looks good! Run run.bat to start the service.
)
echo  ============================================================
echo.
pause
