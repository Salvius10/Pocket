<#
Runs the test APK on a phone plugged in by USB, talking to core-api and the agent on this laptop.

The cable carries the traffic (`adb reverse`), so it works on any network: no Wi-Fi sharing, no
firewall change, nothing exposed. The APK must be the USB test build (API_BASE=http://127.0.0.1:8080).

On the phone, once: Settings > About phone > tap "Build number" 7 times, then
Settings > Developer options > USB debugging = on. Plug in and accept the "Allow USB debugging?" prompt.

Usage:  ./scripts/phone.ps1                 # forward ports and install the APK
        ./scripts/phone.ps1 -NoInstall      # only forward ports (after replugging the cable)
#>
param([string]$Apk = "$env:USERPROFILE\dev\pocket-apk\pocket-usb-test.apk", [switch]$NoInstall)
$ErrorActionPreference = 'Stop'
$adb = Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe'
if (-not (Test-Path $adb)) { throw "adb not found at $adb" }

$devices = (& $adb devices) | Select-Object -Skip 1 | Where-Object { $_ -match '\S' }
if (-not $devices) { throw "No phone found. Plug it in, turn on USB debugging, and accept the prompt on the phone." }
if ($devices -match 'unauthorized') { throw "The phone is connected but has not allowed USB debugging. Accept the prompt on its screen and run this again." }

foreach ($port in 8080, 8081) {
  & $adb reverse "tcp:$port" "tcp:$port" | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Could not forward port $port" }
}
Write-Host "Ports 8080 and 8081 on the phone now reach this laptop." -ForegroundColor Green

if (-not $NoInstall) {
  if (-not (Test-Path $Apk)) { throw "APK not found: $Apk" }
  & $adb install -r $Apk
  if ($LASTEXITCODE -ne 0) { throw "Install failed" }
  & $adb shell monkey -p in.pocket.mvp -c android.intent.category.LAUNCHER 1 | Out-Null
  Write-Host "Pocket is installed and open on the phone." -ForegroundColor Green
}
