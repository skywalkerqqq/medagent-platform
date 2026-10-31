# 启动 MediAgent v1.1（PowerShell）
param(
    [int]$Port = 8090,
    [switch]$Reset
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
$py = $env:DSH_PYTHON
if (-not $py) {
    $candidates = @(
        "C:\Users\fan\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe",
        (Join-Path $env:USERPROFILE ".dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe")
    )
    foreach ($candidate in $candidates) { if (Test-Path $candidate) { $py = $candidate; break } }
}
if (-not $py) { $py = "python" }
$db = Join-Path $root "data\medagent.db"
$args = @("server/app.py", "--port", $Port, "--db", $db)
if ($Reset) { $args += "--reset" }
Write-Host "启动 MediAgent：http://127.0.0.1:$Port （登录 u_creator / medagent123）" -ForegroundColor Cyan
& $py @args
Pop-Location

