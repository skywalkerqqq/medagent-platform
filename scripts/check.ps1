# 质量检查（PowerShell）：接口测试 + 前端 JS 语法
$ErrorActionPreference = "Continue"
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
$node = $env:DSH_NODE
if (-not $node) {
    $candidates = @(
        "C:\Users\fan\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe",
        (Join-Path $env:USERPROFILE ".dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe")
    )
    foreach ($candidate in $candidates) { if (Test-Path $candidate) { $node = $candidate; break } }
}

Write-Host "=== 接口验收测试 ===" -ForegroundColor Cyan
& $py tests/test_api.py
& $py tests/test_llm_live.py
$testCode = $LASTEXITCODE

Write-Host "=== 前端 JS 语法 ===" -ForegroundColor Cyan
if ($node) {
    & $node --check web/app.js
    $jsCode = $LASTEXITCODE
} else {
    Write-Host "未找到 node，跳过 JS 语法检查" -ForegroundColor Yellow
    $jsCode = 0
}

Write-Host ""
if ($testCode -eq 0 -and $jsCode -eq 0) {
    Write-Host "全部检查通过" -ForegroundColor Green
    Pop-Location
    exit 0
} else {
    Write-Host "检查失败：tests=$testCode js=$jsCode" -ForegroundColor Red
    Pop-Location
    exit 1
}

