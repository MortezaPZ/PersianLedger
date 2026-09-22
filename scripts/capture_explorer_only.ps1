param([string]$OutDir)
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class Cap2 {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [StructLayout(LayoutKind.Sequential)]
  public struct RECT { public int L; public int T; public int R; public int B; }
}
"@
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$path = "F:\Code\PersianLedger-0.5.0-portable\dist\PersianLedger"
Start-Process explorer.exe $path
Start-Sleep -Seconds 3
$shell = New-Object -ComObject Shell.Application
$saved = $false
foreach ($w in @($shell.Windows())) {
    try {
        $p = [string]$w.Document.Folder.Self.Path
        if ($p -eq $path) {
            $hwnd = [IntPtr]$w.HWND
            [Cap2]::SetForegroundWindow($hwnd) | Out-Null
            Start-Sleep -Milliseconds 400
            $r = New-Object Cap2+RECT
            [Cap2]::GetWindowRect($hwnd, [ref]$r) | Out-Null
            $ww = $r.R - $r.L; $hh = $r.B - $r.T
            $bmp = New-Object System.Drawing.Bitmap $ww, $hh
            $g = [System.Drawing.Graphics]::FromImage($bmp)
            $g.CopyFromScreen($r.L, $r.T, 0, 0, (New-Object System.Drawing.Size $ww, $hh))
            $bmp.Save((Join-Path $OutDir "explorer-portable.png"), [System.Drawing.Imaging.ImageFormat]::Png)
            $g.Dispose(); $bmp.Dispose()
            $w.Quit()
            $saved = $true
            break
        }
    } catch {}
}
if (-not $saved) { throw "explorer window not found" }
Write-Host ((Get-Item (Join-Path $OutDir "explorer-portable.png")).Length)
