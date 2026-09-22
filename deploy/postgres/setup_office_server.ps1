# Office-LAN helper: firewall port + print this PC's IPv4.
# Run in PowerShell as Administrator for the firewall line.
# Safe to re-run.

$ErrorActionPreference = "Continue"
Write-Host "=== PersianLedger — آماده‌سازی رایانه سرور دفتر ==="
Write-Host ""

Write-Host "۱) نشانی این رایانه در شبکه داخلی (نه VPN):"
Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -ne $null -and $_.NetAdapter.Status -eq "Up" } | ForEach-Object {
    $ip = $_.IPv4Address.IPAddress
    if ($ip -like "10.*") { return }
    Write-Host ("   " + $_.InterfaceAlias + "  →  " + $ip)
}
Write-Host ""

$ruleName = "PersianLedger-PostgreSQL-5432"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "۲) قانون فایروال از قبل وجود دارد: $ruleName"
} else {
    try {
        New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort 5432 -Action Allow -Profile Private,Domain | Out-Null
        Write-Host "۲) پورت 5432 برای شبکه خصوصی باز شد ($ruleName)."
    } catch {
        Write-Host "۲) باز کردن فایروال نیاز به «اجرا به‌عنوان Administrator» دارد."
        Write-Host "   PowerShell را راست‌کلیک کنید → Run as administrator، بعد همین فایل را دوباره اجرا کنید."
        Write-Host "   یا دستی: Windows Security → Firewall → Advanced settings → Inbound Rules → New Rule → Port → TCP 5432 → Allow → Private."
    }
}

Write-Host ""
Write-Host "۳) PostgreSQL 16 را نصب کنید (اگر نصب نیست)."
Write-Host "   بعد فایل deploy\postgres\init_db.sql را در pgAdmin یا psql اجرا کنید و رمز CHANGE_ME را عوض کنید."
Write-Host "   در postgresql.conf مقدار listen_addresses را روی * بگذارید."
Write-Host "   در pg_hba.conf یک خط host برای شبکه دفتر اضافه کنید (نمونه در همان پوشه است)."
Write-Host ""
Write-Host "تمام."
