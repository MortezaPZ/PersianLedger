param([string]$OutDir)
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class NativeWin2 {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
  [StructLayout(LayoutKind.Sequential)]
  public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
}
"@

function Save-Handle([IntPtr]$Handle, [string]$Path) {
    Start-Sleep -Milliseconds 600
    [NativeWin2]::ShowWindow($Handle, 9) | Out-Null
    [NativeWin2]::SetForegroundWindow($Handle) | Out-Null
    Start-Sleep -Milliseconds 400
    $rect = New-Object NativeWin2+RECT
    [NativeWin2]::GetWindowRect($Handle, [ref]$rect) | Out-Null
    $w = [Math]::Max(50, $rect.Right - $rect.Left)
    $h = [Math]::Max(50, $rect.Bottom - $rect.Top)
    if ($w -gt 4000 -or $h -gt 3000) { throw "bad rect $w x $h" }
    $bmp = New-Object System.Drawing.Bitmap $w, $h
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($rect.Left, $rect.Top, 0, 0, (New-Object System.Drawing.Size $w, $h))
    $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
}

# IP form with the real LAN address
$lan = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -ne $null -and $_.NetAdapter.Status -eq "Up" } |
    ForEach-Object { $_.IPv4Address.IPAddress } |
    Where-Object { $_ -notlike "10.*" -and $_ -notlike "127.*" } |
    Select-Object -First 1
if (-not $lan) { $lan = "192.168.1.x" }

$form = New-Object System.Windows.Forms.Form
$form.Text = "Office LAN IPv4"
$form.Width = 720
$form.Height = 380
$form.StartPosition = "Manual"
$form.Left = 60
$form.Top = 60
$box = New-Object System.Windows.Forms.Label
$box.Dock = "Fill"
$box.Font = New-Object System.Drawing.Font "Segoe UI", 16
$box.Padding = New-Object System.Windows.Forms.Padding 24
$box.Text = @"
نشانی این رایانه در شبکه دفتر

Wi-Fi IPv4:
$lan

همین عدد را در برنامه، در «نشانی سرور» بنویسید.
عدد 10.x مربوط به VPN است؛ از آن استفاده نکنید.
"@
$form.Controls.Add($box)
$form.Add_Shown({ $form.Activate() })
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 1200
$timer.Add_Tick({
    $timer.Stop()
    Save-Handle $form.Handle (Join-Path $OutDir "w01-ip.png")
    $form.Close()
})
$timer.Start()
[System.Windows.Forms.Application]::Run($form)

# Explorer
$portable = "F:\Code\PersianLedger-0.5.0-portable\dist\PersianLedger"
Start-Process explorer.exe $portable
Start-Sleep -Seconds 3
$shell = New-Object -ComObject Shell.Application
foreach ($w in @($shell.Windows())) {
    try {
        $p = [string]$w.Document.Folder.Self.Path
        if ($p -like "*PersianLedger") {
            Save-Handle ([IntPtr]$w.HWND) (Join-Path $OutDir "w02-explorer.png")
            $w.Quit()
            break
        }
    } catch {}
}

# Firewall advanced only
Get-Process mmc -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
$mmc = Start-Process "wf.msc" -PassThru
Start-Sleep -Seconds 4
$p = Get-Process mmc | Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero } | Select-Object -First 1
if ($p) { Save-Handle $p.MainWindowHandle (Join-Path $OutDir "w04-wf-msc.png") }
Get-Process mmc -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Get-ChildItem $OutDir | ForEach-Object { Write-Host "$($_.Name) $($_.Length)" }
