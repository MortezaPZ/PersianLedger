param(
    [string]$ScriptPath = (Join-Path $PSScriptRoot "backup.ps1"),
    [string]$PgBin,
    [string]$OutDir
)
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -File `"$ScriptPath`" -PgBin `"$PgBin`" -OutDir `"$OutDir`""
$trigger = New-ScheduledTaskTrigger -Daily -At 23:00
Register-ScheduledTask -TaskName "PersianLedger Backup" -Action $action -Trigger $trigger -Force
