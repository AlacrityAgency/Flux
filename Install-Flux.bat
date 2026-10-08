@echo off
setlocal
cd /d "%~dp0"

title Flux Desktop Installer

echo ========================================================
echo   Flux Desktop Installer for Windows
echo ========================================================
echo(

set PY_CMD=
where python >nul 2>&1
if %ERRORLEVEL% equ 0 set PY_CMD=python
if "%PY_CMD%"=="" (
    where py >nul 2>&1
    if %ERRORLEVEL% equ 0 set PY_CMD=py
)

if "%PY_CMD%"=="" (
    echo [ERROR] Python was not found in your system PATH!
    echo Please install Python 3.10+ and ensure "Add Python to PATH" is checked.
    echo(
    pause
    exit /b 1
)

echo [*] Python detected: %PY_CMD%
echo [*] Installing Flux to your Windows system...
echo(

"%PY_CMD%" "%~dp0tools\installer.py"
if %ERRORLEVEL% equ 0 (
    echo(
    echo ========================================================
    echo   Installation completed successfully!
    echo   You can now launch Flux from your Desktop or Start Menu.
    echo ========================================================
) else (
    echo(
    echo ========================================================
    echo   Installation encountered an error.
    echo ========================================================
)

echo(
echo Press any key to exit...
pause >nul
