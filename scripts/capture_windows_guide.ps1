# Capture specific windows for the beginner network guide.
param(
    [Parameter(Mandatory = $true)]
    [string]$OutDir
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class NativeWin {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
  [StructLayout(LayoutKind.Sequential)]
  public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
}
"@

function Save-WindowShot {
    param([IntPtr]$Handle, [string]$Path, [int]$WaitMs = 800)
    Start-Sleep -Milliseconds $WaitMs
    [NativeWin]::ShowWindow($Handle, 9) | Out-Null
    [NativeWin]::SetForegroundWindow($Handle) | Out-Null
    Start-Sleep -Milliseconds 400
    $rect = New-Object NativeWin+RECT
    [NativeWin]::GetWindowRect($Handle, [ref]$rect) | Out-Null
    $w = [Math]::Max(200, $rect.Right - $rect.Left)
    $h = [Math]::Max(200, $rect.Bottom - $rect.Top)
    $bmp = New-Object System.Drawing.Bitmap $w, $h
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($rect.Left, $rect.Top, 0, 0, (New-Object System.Drawing.Size $w, $h))
    $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose()
    $bmp.Dispose()
}

function Wait-MainHandle {
    param($Proc, [int]$TimeoutMs = 8000)
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.ElapsedMilliseconds -lt $TimeoutMs) {
        $Proc.Refresh()
        if ($Proc.MainWindowHandle -ne [IntPtr]::Zero) { return $Proc.MainWindowHandle }
        Start-Sleep -Milliseconds 200
    }
    return [IntPtr]::Zero
}

# --- LAN IPv4 in a console window ---
$ipCmd = @'
$cfg = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -ne $null -and $_.NetAdapter.Status -eq "Up" }
Write-Host ""
Write-Host "========================================"
Write-Host "  نشانی این رایانه در شبکه دفتر"
Write-Host "========================================"
foreach ($c in $cfg) {
  $ip = $c.IPv4Address.IPAddress
  if ($ip -like "10.*" ) { continue }
  Write-Host ""
  Write-Host ("آداپتور: " + $c.InterfaceAlias)
  Write-Host ("IPv4:    " + $ip)
}
Write-Host ""
Write-Host "همین عدد را در برنامه، در قسمت نشانی سرور بنویسید."
Write-Host "پنجره را باز بگذارید تا عکس گرفته شود."
Start-Sleep -Seconds 20
'@
$ipFile = Join-Path $env:TEMP "pl-show-ip.ps1"
Set-Content -Path $ipFile -Value $ipCmd -Encoding UTF8
$ipProc = Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-File",$ipFile) -PassThru
$h = Wait-MainHandle $ipProc
if ($h -ne [IntPtr]::Zero) {
    [NativeWin]::SetWindowPos($h, [IntPtr]::Zero, 80, 80, 900, 520, 0x0040) | Out-Null
    Save-WindowShot -Handle $h -Path (Join-Path $OutDir "w01-ip.png")
}
Stop-Process -Id $ipProc.Id -Force -ErrorAction SilentlyContinue

# --- Explorer on the portable folder ---
$portable = "F:\Code\PersianLedger-0.5.0-portable\dist\PersianLedger"
if (Test-Path $portable) {
    $ex = Start-Process "explorer.exe" -ArgumentList $portable -PassThru
    Start-Sleep -Seconds 2
    $shell = New-Object -ComObject Shell.Application
    $win = $shell.Windows() | Where-Object { $_.Document.Folder.Self.Path -eq $portable } | Select-Object -First 1
    if ($win) {
        Save-WindowShot -Handle ([IntPtr]$win.HWND) -Path (Join-Path $OutDir "w02-explorer.png")
        $win.Quit()
    }
}

# --- Firewall control panel ---
$fw = Start-Process "firewall.cpl" -PassThru
Start-Sleep -Seconds 2
Get-Process | Where-Object { $_.MainWindowTitle -match "Firewall|Windows Defender|wf.msc" } | ForEach-Object {
    if ($_.MainWindowHandle -ne [IntPtr]::Zero) {
        Save-WindowShot -Handle $_.MainWindowHandle -Path (Join-Path $OutDir "w03-firewall-cpl.png")
    }
}
# Fallback: any mmc or rundll
if (-not (Test-Path (Join-Path $OutDir "w03-firewall-cpl.png"))) {
    Get-Process | Where-Object { $_.ProcessName -match "mmc|rundll32|control" -and $_.MainWindowHandle -ne [IntPtr]::Zero } | Select-Object -First 1 | ForEach-Object {
        Save-WindowShot -Handle $_.MainWindowHandle -Path (Join-Path $OutDir "w03-firewall-cpl.png")
    }
}

# --- Advanced firewall ---
$wf = Start-Process "wf.msc" -PassThru
Start-Sleep -Seconds 3
Get-Process mmc -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.MainWindowHandle -ne [IntPtr]::Zero) {
        Save-WindowShot -Handle $_.MainWindowHandle -Path (Join-Path $OutDir "w04-wf-msc.png")
    }
}

# Close snap-ins so we don't leave them on the desktop
Get-Process mmc -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process | Where-Object { $_.MainWindowTitle -match "Firewall|Windows Defender" } | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "shots in $OutDir"
Get-ChildItem $OutDir | ForEach-Object { Write-Host ($_.Name + " " + $_.Length) }
