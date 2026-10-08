# Flux Desktop Installer (PowerShell)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Flux Desktop Installer for Windows" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) {
    $PythonExe = (Get-Command py -ErrorAction SilentlyContinue).Source
}

if (-not $PythonExe) {
    Write-Host "[ERROR] Python was not found in PATH." -ForegroundColor Red
    Write-Host "Please install Python 3.10+ and ensure Add Python to PATH is checked." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[*] Python executable: $PythonExe" -ForegroundColor Green
Write-Host "[*] Installing Flux..." -ForegroundColor Gray
Write-Host ""

& $PythonExe "$ScriptDir\tools\installer.py"

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Read-Host "Press Enter to exit"
