param([string]$InstallDir)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms

if (-not $InstallDir) {
    $picker = New-Object System.Windows.Forms.FolderBrowserDialog
    $picker.Description = "پوشه نصب فعلی دفتر مالی را انتخاب کنید"
    $picker.ShowNewFolderButton = $false
    $defaultInstall = Join-Path $env:ProgramFiles "PersianLedger"
    if (Test-Path -LiteralPath $defaultInstall -PathType Container) {
        $picker.SelectedPath = $defaultInstall
    }
    if ($picker.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
        exit 1
    }
    $InstallDir = $picker.SelectedPath
}

$exe = Join-Path $InstallDir "PersianLedger.exe"
$internal = Join-Path $InstallDir "_internal"
if (-not (Test-Path -LiteralPath $exe -PathType Leaf) -or
    -not (Test-Path -LiteralPath $internal -PathType Container)) {
    [System.Windows.Forms.MessageBox]::Show(
        "پوشه انتخاب‌شده، پوشه برنامه دفتر مالی نیست.",
        "به‌روزرسانی دفتر مالی",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
    exit 2
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    $quotedScript = '"' + $PSCommandPath.Replace('"', '\"') + '"'
    $quotedInstall = '"' + $InstallDir.Replace('"', '\"') + '"'
    $arguments = "-NoProfile -ExecutionPolicy Bypass -STA -File $quotedScript -InstallDir $quotedInstall"
    $child = Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList $arguments -Wait -PassThru
    exit $child.ExitCode
}

$updater = Join-Path $PSScriptRoot "update_portable.ps1"
& $updater -InstallDir $InstallDir -UpdateDir $PSScriptRoot

[System.Windows.Forms.MessageBox]::Show(
    "به‌روزرسانی انجام شد. دیتابیس و تنظیمات اتصال قبلی حفظ شدند.",
    "به‌روزرسانی دفتر مالی",
    [System.Windows.Forms.MessageBoxButtons]::OK,
    [System.Windows.Forms.MessageBoxIcon]::Information
) | Out-Null

