param(
    [string]$PgBin,
    [string]$Database = "persianledger",
    [string]$User = "persianledger",
    [string]$OutDir,
    [int]$KeepDays = 30
)
$ErrorActionPreference = "Stop"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = Join-Path $OutDir "backup-$Database-$stamp.pgdump"
$log = Join-Path $OutDir "backup.log"
$dump = Join-Path $PgBin "pg_dump.exe"
& $dump -Fc --no-owner --no-privileges -U $User -d $Database -f $dest
Get-ChildItem $OutDir -Filter "*.pgdump" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$KeepDays) } | Remove-Item
Add-Content $log "$(Get-Date -Format o) wrote $dest"
