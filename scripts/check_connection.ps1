# Safe connectivity check — laptop to Mi TV (read-only, no changes to TV)
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Adb = Join-Path $Root "tools\platform-tools\adb.exe"
$Config = Join-Path $Root "config\tv.json"

Write-Host "`n=== Mi TV connection check ===" -ForegroundColor Cyan

if (-not (Test-Path $Config)) {
    Write-Host "Missing config/tv.json — copy from config/tv.json.example and set your TV IP." -ForegroundColor Yellow
    exit 1
}

$cfg = Get-Content $Config | ConvertFrom-Json
$host_ip = $cfg.host
$port = $cfg.port

Write-Host "`n1. Laptop WiFi"
Get-NetIPConfiguration -InterfaceAlias "Wi-Fi" -ErrorAction SilentlyContinue |
    Select-Object @{N='IP';E={$_.IPv4Address.IPAddress}}, @{N='Gateway';E={$_.IPv4DefaultGateway.NextHop}} |
    Format-List

Write-Host "2. Ping TV ($host_ip)"
ping -n 2 $host_ip

Write-Host "`n3. ADB port ($port)"
$t = Test-NetConnection $host_ip -Port $port -WarningAction SilentlyContinue
Write-Host "   Ping: $($t.PingSucceeded)  TCP: $($t.TcpTestSucceeded)"

Write-Host "`n4. ADB connect"
& $Adb connect "${host_ip}:${port}"
Write-Host "`n5. ADB devices"
& $Adb devices -l

if ($t.TcpTestSucceeded) {
    Write-Host "`nOK — TV port is open. Run: python -m tv_remote.cli" -ForegroundColor Green
} else {
    Write-Host "`nTV not reachable yet. On Mi TV enable USB + Network debugging and confirm IP in Settings -> Network." -ForegroundColor Yellow
}
