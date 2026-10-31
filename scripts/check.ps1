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
$testCode = 0
$suites = @(
    "tests/test_api.py",
    "tests/test_llm_live.py",
    "tests/test_dify.py",
    "tests/test_notify.py",
    "tests/test_production_import.py",
    "tests/test_pg_migration.py"
)
foreach ($suite in $suites) {
    & $py $suite
    if ($LASTEXITCODE -ne 0) { $testCode = 1 }
}
& $py -m py_compile production/app.py production/migrate_to_pg.py
if ($LASTEXITCODE -ne 0) { $testCode = 1 }

Write-Host "=== 前端 JS 语法 ===" -ForegroundColor Cyan
if ($node) {
    & $node --check web/app.js
    $miniprogramBad = 0
    Get-ChildItem -Recurse miniprogram -Filter *.js | ForEach-Object {
        & $node --check $_.FullName 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { $miniprogramBad++ }
    }
    if ($miniprogramBad -gt 0) { Write-Host "小程序 JS 语法失败: $miniprogramBad" -ForegroundColor Red }
    $jsCode = if ($miniprogramBad -gt 0 -or $LASTEXITCODE -ne 0) { 1 } else { 0 }
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






