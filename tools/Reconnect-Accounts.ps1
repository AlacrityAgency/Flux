param([ValidateSet('gemini','gapcode')][string]$Provider)
$ErrorActionPreference = 'Stop'
$scriptPath = Join-Path $PSScriptRoot 'connect_account_clis.py'
$pythonPath = (Get-Command python.exe -CommandType Application).Source
Write-Host "Flux: reconnect $Provider using its official browser sign-in." -ForegroundColor Cyan
& $pythonPath -X utf8 $scriptPath $Provider
Write-Host "Sign-in process exited with code $LASTEXITCODE. You can close this window."
