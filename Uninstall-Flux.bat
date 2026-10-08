@echo off
setlocal
cd /d "%~dp0"

title Uninstall Flux Desktop

echo ========================================================
echo   Flux Desktop Uninstaller (Windows)
echo ========================================================
echo.

set "INSTALLED_UNINSTALL=%LOCALAPPDATA%\Programs\Flux\uninstall.bat"
if exist "%INSTALLED_UNINSTALL%" (
    call "%INSTALLED_UNINSTALL%"
) else (
    taskkill /F /IM Flux.exe /T >nul 2>&1
    taskkill /F /IM FluxDemo.exe /T >nul 2>&1
    del /f /q "%USERPROFILE%\Desktop\Flux.lnk" 2>nul
    rd /s /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Flux" 2>nul
    reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\Flux" /f >nul 2>&1
    rd /s /q "%LOCALAPPDATA%\Programs\Flux" 2>nul
    echo Flux desktop shortcuts and files removed.
)

echo.
echo Press any key to exit...
pause >nul
