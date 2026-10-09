# Office-LAN helper: firewall port + print this PC's IPv4.
# Run in PowerShell as Administrator for the firewall line.
# Safe to re-run.

$ErrorActionPreference = "Continue"
Write-Host "=== PersianLedger — prepare the office server ==="
Write-Host ""

Write-Host "1) This computer's address on the office network (not the VPN):"
Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -ne $null -and $_.NetAdapter.Status -eq "Up" } | ForEach-Object {
    $ip = $_.IPv4Address.IPAddress
    if ($ip -like "10.*") { return }
    Write-Host ("   " + $_.InterfaceAlias + "  →  " + $ip)
}
Write-Host ""

$ruleName = "PersianLedger-PostgreSQL-5432"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($existing) {
        Write-Host "2) Firewall rule already exists: $ruleName"
} else {
    try {
        New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort 5432 -Action Allow -Profile Private,Domain | Out-Null
        Write-Host "2) Port 5432 is open on the private network ($ruleName)."
    } catch {
        Write-Host "2) Opening the firewall requires Run as administrator."
        Write-Host "   Right-click PowerShell, choose Run as administrator, and run this file again."
        Write-Host "   Or do it by hand: Windows Security, Firewall, Advanced settings, Inbound Rules, New Rule, Port, TCP 5432, Allow, Private."
    }
}

Write-Host ""
Write-Host "3) Install PostgreSQL 16 if it is not installed."
Write-Host "   Then run deploy\postgres\init_db.sql in pgAdmin or psql and change the CHANGE_ME password."
Write-Host "   In postgresql.conf set listen_addresses to *."
Write-Host "   In pg_hba.conf add a host line for the office network. A sample is in the same folder."
Write-Host ""
Write-Host "Done."
