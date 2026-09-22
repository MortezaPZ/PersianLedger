# Capture a single window with PrintWindow (no overlapping Cursor chrome).
param(
    [Parameter(Mandatory = $true)][string]$TitleMatch,
    [Parameter(Mandatory = $true)][string]$OutFile,
    [int]$Width = 980,
    [int]$Height = 720,
    [string]$Exclude = ""
)

Add-Type -AssemblyName System.Drawing
if (-not ([System.Management.Automation.PSTypeName]'WinCap').Type) {
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class WinCap {
  public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint f);
  [StructLayout(LayoutKind.Sequential)]
  public struct RECT { public int L; public int T; public int R; public int B; }
  public static IntPtr Find(string needle, string exclude) {
    IntPtr found = IntPtr.Zero;
    EnumWindows((h, l) => {
      if (!IsWindowVisible(h)) return true;
      var sb = new StringBuilder(512);
      GetWindowText(h, sb, 512);
      string t = sb.ToString();
      if (t.IndexOf(needle, StringComparison.OrdinalIgnoreCase) < 0) return true;
      if (!string.IsNullOrEmpty(exclude) && t.IndexOf(exclude, StringComparison.OrdinalIgnoreCase) >= 0) return true;
      found = h; return false;
    }, IntPtr.Zero);
    return found;
  }
}
"@
}

$hwnd = [WinCap]::Find($TitleMatch, $Exclude)
if ($hwnd -eq [IntPtr]::Zero) { throw "window not found: $TitleMatch" }

$hwndTopMost = [IntPtr](-1)
[WinCap]::ShowWindow($hwnd, 9) | Out-Null
[WinCap]::SetWindowPos($hwnd, $hwndTopMost, 40, 40, $Width, $Height, 0x0040) | Out-Null
Start-Sleep -Milliseconds 600
[WinCap]::SetForegroundWindow($hwnd) | Out-Null
Start-Sleep -Milliseconds 400

$r = New-Object WinCap+RECT
[WinCap]::GetWindowRect($hwnd, [ref]$r) | Out-Null
$w = [Math]::Max(100, $r.R - $r.L)
$h = [Math]::Max(100, $r.B - $r.T)
$bmp = New-Object System.Drawing.Bitmap $w, $h
$g = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $g.GetHdc()
# 2 = PW_RENDERFULLCONTENT
$ok = [WinCap]::PrintWindow($hwnd, $hdc, 2)
if (-not $ok) { [WinCap]::PrintWindow($hwnd, $hdc, 0) | Out-Null }
$g.ReleaseHdc($hdc)

function Test-MostlyBlack([System.Drawing.Bitmap]$img) {
  $n = 0; $dark = 0
  for ($i = 0; $i -lt 40; $i++) {
    $x = [int](($img.Width - 1) * (($i * 17) % 100) / 100)
    $y = [int](($img.Height - 1) * (($i * 29) % 100) / 100)
    $c = $img.GetPixel($x, $y)
    $n++
    if (($c.R + $c.G + $c.B) -lt 30) { $dark++ }
  }
  return ($dark -ge [int]($n * 0.85))
}

if (Test-MostlyBlack $bmp) {
  $g.CopyFromScreen($r.L, $r.T, 0, 0, (New-Object System.Drawing.Size $w, $h))
}

$dir = Split-Path $OutFile
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$bmp.Save($OutFile, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Host "$OutFile $((Get-Item $OutFile).Length) ${w}x${h}"
