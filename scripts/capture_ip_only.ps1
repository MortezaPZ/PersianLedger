param([string]$OutDir)
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class Cap {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [StructLayout(LayoutKind.Sequential)]
  public struct RECT { public int L; public int T; public int R; public int B; }
}
"@
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$lan = (Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -ne $null -and $_.NetAdapter.Status -eq "Up" } |
    ForEach-Object { $_.IPv4Address.IPAddress } | Where-Object { $_ -notlike "10.*" } | Select-Object -First 1)
$form = New-Object System.Windows.Forms.Form
$form.Text = "LAN IPv4"
$form.Width = 760
$form.Height = 400
$form.StartPosition = "Manual"
$form.Left = 40
$form.Top = 40
$form.BackColor = [System.Drawing.Color]::White
$l = New-Object System.Windows.Forms.Label
$l.Dock = "Fill"
$l.Font = New-Object System.Drawing.Font "Tahoma", 18
$l.Padding = New-Object System.Windows.Forms.Padding 28
$l.Text = "نشانی این رایانه در شبکه دفتر (Wi-Fi)`r`n`r`n$lan`r`n`r`nهمین عدد را در برنامه بنویسید.`r`nاز عدد 10.x (VPN) استفاده نکنید."
$form.Controls.Add($l)
$form.Add_Shown({
    $form.Activate()
    Start-Sleep -Milliseconds 800
    [Cap]::SetForegroundWindow($form.Handle) | Out-Null
    $r = New-Object Cap+RECT
    [Cap]::GetWindowRect($form.Handle, [ref]$r) | Out-Null
    $w = $r.R - $r.L; $h = $r.B - $r.T
    $bmp = New-Object System.Drawing.Bitmap $w, $h
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($r.L, $r.T, 0, 0, (New-Object System.Drawing.Size $w, $h))
    $bmp.Save((Join-Path $OutDir "ip-lan.png"), [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    $form.Close()
})
[System.Windows.Forms.Application]::Run($form)
Write-Host ((Get-Item (Join-Path $OutDir "ip-lan.png")).Length)
