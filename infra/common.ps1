# Shared by setup.ps1 and deploy.ps1: tool paths, infra/demo.env, and runners that fail loudly.
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$Root = Split-Path $PSScriptRoot -Parent
$EnvFile = Join-Path $PSScriptRoot 'demo.env'

# The Google Cloud and Firebase tools may live in ~\dev (unzipped, not on PATH). Use them if present.
foreach ($dir in "$env:USERPROFILE\dev\google-cloud-sdk\bin", "$env:USERPROFILE\dev\firebase-tools\node_modules\.bin", "$env:USERPROFILE\dev\flutter\bin") {
  if ((Test-Path $dir) -and ($env:PATH -notlike "*$dir*")) { $env:PATH = "$dir;$env:PATH" }
}

function Read-DemoEnv {
  if (-not (Test-Path $EnvFile)) { throw 'Create infra/demo.env from infra/demo.env.example first.' }
  $cfg = @{}
  foreach ($line in Get-Content $EnvFile) {
    if ($line -match '^\s*([A-Z0-9_]+)\s*=(.*)$') { $cfg[$Matches[1]] = $Matches[2].Trim() }
  }
  return $cfg
}

# Writes KEY=value into infra/demo.env (git-ignored), replacing the line if the key is already there.
function Set-DemoEnv([string]$Key, [string]$Value) {
  $out = New-Object System.Collections.Generic.List[string]
  $found = $false
  foreach ($line in Get-Content $EnvFile) {
    if ($line -match "^\s*$([regex]::Escape($Key))\s*=") { $out.Add("$Key=$Value"); $found = $true } else { $out.Add($line) }
  }
  if (-not $found) { $out.Add("$Key=$Value") }
  [IO.File]::WriteAllLines($EnvFile, $out, (New-Object Text.UTF8Encoding($false)))
}

function Invoke-Checked {
  param([string]$What, [scriptblock]$Cmd)
  Write-Host "==> $What" -ForegroundColor Cyan
  & $Cmd
  if ($LASTEXITCODE -ne 0) { throw "$What failed" }
}

# True when the command exits 0. Runs through cmd so that a tool writing to stderr does not stop the script.
function Test-Quiet([string]$CommandLine) {
  cmd /c "$CommandLine >nul 2>&1"
  return ($LASTEXITCODE -eq 0)
}

function Assert-Tools([string[]]$Names) {
  foreach ($tool in $Names) { if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "$tool is not installed or not on PATH" } }
}

# The Google account gcloud is signed in as, or a stop with what to run.
function Get-SignedInAccount {
  $account = gcloud auth list --filter 'status:ACTIVE' --format 'value(account)' | Select-Object -First 1
  if (-not $account) { throw 'gcloud is not signed in. Run:  gcloud auth login' }
  return $account
}
