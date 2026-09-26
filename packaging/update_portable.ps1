# Replace the portable program files and leave the data folder untouched.
# Usage:
#   powershell -ExecutionPolicy Bypass -File packaging\update_portable.ps1 -InstallDir D:\PersianLedger -UpdateDir D:\PersianLedger-new
param(
    [Parameter(Mandatory = $true)][string]$InstallDir,
    [Parameter(Mandatory = $true)][string]$UpdateDir,
    [switch]$SimulateFailure
)

$ErrorActionPreference = "Stop"

function Resolve-ExistingDir([string]$Path, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$Label folder was not found: $Path"
    }
    return (Resolve-Path -LiteralPath $Path).Path.TrimEnd("\")
}

function Test-PathInside([string]$Parent, [string]$Child) {
    $prefix = $Parent.TrimEnd("\") + "\"
    return $Child.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
}

$install = Resolve-ExistingDir $InstallDir "Install"
$update = Resolve-ExistingDir $UpdateDir "Update"

if ($install.Equals($update, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "InstallDir and UpdateDir are the same folder."
}
if ((Test-PathInside $install $update) -or (Test-PathInside $update $install)) {
    throw "The update folder must not be inside the install folder, or the other way around."
}

$newExe = Join-Path $update "PersianLedger.exe"
$newInternal = Join-Path $update "_internal"
if (-not (Test-Path -LiteralPath $newExe -PathType Leaf)) {
    throw "PersianLedger.exe is missing in the update folder."
}
if (-not (Test-Path -LiteralPath $newInternal -PathType Container)) {
    throw "_internal is missing in the update folder."
}

$exePath = Join-Path $install "PersianLedger.exe"
$running = Get-Process -Name "PersianLedger" -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -and (
        $_.Path.Equals($exePath, [System.StringComparison]::OrdinalIgnoreCase) -or
        $_.Path.StartsWith($install + "\", [System.StringComparison]::OrdinalIgnoreCase)
    )
}
if ($running) {
    throw "PersianLedger.exe in the install folder is still running. Close it and run the update again."
}

$data = Join-Path $install "data"
$before = $null
if (Test-Path -LiteralPath $data) {
    $before = @(Get-ChildItem -LiteralPath $data -Recurse -File | ForEach-Object {
        "{0}|{1}|{2}" -f $_.FullName.Substring($data.Length), $_.Length, $_.LastWriteTimeUtc.Ticks
    })
}

$liveInternal = Join-Path $install "_internal"
$backup = Join-Path $install "_internal.prev"
$exeBackup = Join-Path $install "PersianLedger.exe.prev"
if (Test-Path -LiteralPath $liveInternal) {
    if (Test-Path -LiteralPath $backup) {
        Remove-Item -LiteralPath $backup -Recurse -Force
    }
    Rename-Item -LiteralPath $liveInternal -NewName "_internal.prev"
}
if (Test-Path -LiteralPath $exePath) {
    Copy-Item -LiteralPath $exePath -Destination $exeBackup -Force
}

try {
    Copy-Item -LiteralPath $newExe -Destination $exePath -Force
    if ($SimulateFailure) {
        throw "Simulated failure after replacing the executable."
    }
    Copy-Item -LiteralPath $newInternal -Destination $liveInternal -Recurse -Force
    Get-ChildItem -LiteralPath $update -Force | ForEach-Object {
        if ($_.Name -in @("PersianLedger.exe", "_internal", "data")) {
            return
        }
        $dest = Join-Path $install $_.Name
        if ($_.PSIsContainer) {
            if (Test-Path -LiteralPath $dest) {
                Remove-Item -LiteralPath $dest -Recurse -Force
            }
            Copy-Item -LiteralPath $_.FullName -Destination $dest -Recurse -Force
        }
        else {
            Copy-Item -LiteralPath $_.FullName -Destination $dest -Force
        }
    }
}
catch {
    if (Test-Path -LiteralPath $liveInternal) {
        Remove-Item -LiteralPath $liveInternal -Recurse -Force
    }
    if (Test-Path -LiteralPath $backup) {
        Rename-Item -LiteralPath $backup -NewName "_internal"
    }
    if (Test-Path -LiteralPath $exeBackup) {
        Copy-Item -LiteralPath $exeBackup -Destination $exePath -Force
        Remove-Item -LiteralPath $exeBackup -Force
    }
    throw
}

if (Test-Path -LiteralPath $backup) {
    Remove-Item -LiteralPath $backup -Recurse -Force
}
if (Test-Path -LiteralPath $exeBackup) {
    Remove-Item -LiteralPath $exeBackup -Force
}

if ($null -ne $before) {
    $after = @(Get-ChildItem -LiteralPath $data -Recurse -File | ForEach-Object {
        "{0}|{1}|{2}" -f $_.FullName.Substring($data.Length), $_.Length, $_.LastWriteTimeUtc.Ticks
    })
    if ($before.Count -ne $after.Count) {
        throw "The data folder changed during the update. Stop and restore it from a copy."
    }
    if ($before.Count -gt 0) {
        $diff = Compare-Object -ReferenceObject $before -DifferenceObject $after
        if ($diff) {
            throw "The data folder changed during the update. Stop and restore it from a copy."
        }
    }
}

Write-Output "Update applied. The data folder was not changed: $data"
