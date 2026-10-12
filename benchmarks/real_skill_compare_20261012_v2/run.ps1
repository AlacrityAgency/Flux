param([ValidateSet('live','analyze','audit','report','selfcheck')][string]$Mode='analyze')
$ErrorActionPreference='Stop'
$taskPython=Join-Path $PSScriptRoot '..\..\experiments\flux_laya_policy_20261006\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Existing Laya Python environment missing; see environment.json.' }
switch ($Mode) {
  'live' { & $taskPython -X utf8 (Join-Path $PSScriptRoot 'benchmark.py') live }
  'analyze' { & $taskPython -X utf8 (Join-Path $PSScriptRoot 'benchmark.py') analyze }
  'audit' { & $taskPython -X utf8 (Join-Path $PSScriptRoot 'audit_harness.py') }
  'report' { & $taskPython -X utf8 (Join-Path $PSScriptRoot 'make_report.py') }
  'selfcheck' { & $taskPython -X utf8 (Join-Path $PSScriptRoot 'benchmark.py') selfcheck }
}
if ($LASTEXITCODE -ne 0) { throw "Benchmark command failed: $LASTEXITCODE" }
