# 备份 SQLite（单文件 + WAL）。生产建议先停写或使用在线备份窗口。
# 用法：powershell -File deploy/backup.ps1 [-Source data/medagent.db] [-OutDir data/backups]
param(
  [string]$Source = "data/medagent.db",
  [string]$OutDir = "data/backups"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (-not (Test-Path $Source)) { throw "源数据库不存在：$Source" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$target = Join-Path $OutDir "medagent-$stamp.db"
$sourceFull = (Resolve-Path $Source).Path
$targetFull = (Resolve-Path $OutDir).Path + "\medagent-$stamp.db"
$py = if ($env:MEDAGENT_PYTHON) { $env:MEDAGENT_PYTHON } else { "python" }
& $py -c "import sqlite3,sys; src=sqlite3.connect(sys.argv[1]); dst=sqlite3.connect(sys.argv[2]); src.backup(dst); dst.close(); src.close()" $sourceFull $targetFull
if (-not (Test-Path $targetFull)) { throw "备份失败" }
$hash = (Get-FileHash -Algorithm SHA256 $targetFull).Hash
"$hash  $targetFull" | Out-File -Append -Encoding utf8 (Join-Path $OutDir "SHA256SUMS.txt")
Write-Host "备份完成：$targetFull"
Write-Host "SHA256：$hash"
