param(
    [string]$PgBin,
    [string]$Database = "persianledger",
    [string]$User = "persianledger",
    [string]$Dump
)
$restore = Join-Path $PgBin "pg_restore.exe"
& $restore --clean --if-exists --no-owner --no-privileges -U $User -d $Database $Dump
