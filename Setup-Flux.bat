@echo off
setlocal
cd /d "%~dp0"

title Flux v0.7.0 Setup & Quickstart

echo ========================================================
echo   Flux v0.7.0 Open-Source Setup & Quickstart Wizard
echo ========================================================
echo.

set PY_CMD=
where python >nul 2>&1
if %ERRORLEVEL% equ 0 set PY_CMD=python
if "%PY_CMD%"=="" (
    where py >nul 2>&1
    if %ERRORLEVEL% equ 0 set PY_CMD=py
)

if exist "dist\local-agents\Flux.exe" (
    echo [*] Standalone desktop binary found: dist\local-agents\Flux.exe
)
if exist "dist\Flux.exe" (
    echo [*] Standalone desktop binary found: dist\Flux.exe
)

echo.
echo Select an option:
echo   [1] Full Windows Desktop Installation (Desktop & Start Menu Shortcuts)
echo   [2] Launch Setup Web Wizard (Interactive Browser Setup)
echo   [3] Start Flux Engine Server (http://127.0.0.1:8000)
echo   [4] Install Python Dependencies (pip install -e .)
echo   [5] Uninstall Flux from Windows
echo.
set /p CHOICE="Enter choice (1-5, default 1): "
if "%CHOICE%"=="" set CHOICE=1

if "%CHOICE%"=="1" (
    call "%~dp0Install-Flux.bat"
    goto end
)
if "%CHOICE%"=="2" (
    echo [*] Launching Setup Wizard in your default browser...
    start "" "%~dp0src\flux\static\setup.html"
    goto end
)
if "%CHOICE%"=="3" (
    echo [*] Starting Flux server on port 8000...
    if not "%PY_CMD%"=="" (
        "%PY_CMD%" -m flux serve --port 8000
    ) else (
        if exist "dist\Flux.exe" (
            start "" "dist\Flux.exe"
        ) else (
            echo [ERROR] Python not found and dist\Flux.exe missing!
        )
    )
    goto end
)
if "%CHOICE%"=="4" (
    if "%PY_CMD%"=="" (
        echo [ERROR] Python not found in PATH!
        goto end
    )
    "%PY_CMD%" -m pip install -e ".[agentic,dev]"
    goto end
)
if "%CHOICE%"=="5" (
    call "%~dp0Uninstall-Flux.bat"
    goto end
)

:end
echo.
pause

