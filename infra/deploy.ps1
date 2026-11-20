<#
Deploys Pocket to Google Cloud (Mumbai): core-api and agent on Cloud Run, web build on Firebase Hosting.

Before running:
  1. gcloud auth login; gcloud config set project <PROJECT_ID>
  2. firebase login          (npm i -g firebase-tools)
  3. Copy infra/demo.env.example to infra/demo.env and fill it in. infra/demo.env is git-ignored.

Usage:  ./infra/deploy.ps1            # everything
        ./infra/deploy.ps1 -Only web  # backend | web

Secrets (GEMINI_API_KEY, INTERNAL_TOKEN, DATABASE_URL) are set as Cloud Run environment variables
and never written into the repo, the images or the web build.
#>
param([ValidateSet('all', 'backend', 'web')][string]$Only = 'all')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
# The Google Cloud and Firebase tools may live in ~\dev (unzipped, not on PATH). Use them if present.
foreach ($dir in "$env:USERPROFILE\dev\google-cloud-sdk\bin", "$env:USERPROFILE\dev\firebase-tools\node_modules\.bin", "$env:USERPROFILE\dev\flutter\bin") {
  if ((Test-Path $dir) -and ($env:PATH -notlike "*$dir*")) { $env:PATH = "$dir;$env:PATH" }
}
foreach ($tool in 'gcloud', 'firebase', 'uv') { if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "$tool is not installed or not on PATH" } }
$envFile = Join-Path $PSScriptRoot 'demo.env'
if (-not (Test-Path $envFile)) { throw "Create infra/demo.env from infra/demo.env.example first." }
$cfg = @{}
Get-Content $envFile | Where-Object { $_ -match '^\s*[^#].*=' } | ForEach-Object { $k, $v = $_ -split '=', 2; $cfg[$k.Trim()] = $v.Trim() }
foreach ($k in 'PROJECT_ID', 'INTERNAL_TOKEN') { if (-not $cfg[$k]) { throw "infra/demo.env is missing $k" } }

$project = $cfg.PROJECT_ID
$region = if ($cfg.REGION) { $cfg.REGION } else { 'asia-south1' }
$repo = "$region-docker.pkg.dev/$project/pocket"
$geminiMode = if ($cfg.GEMINI_API_KEY) { 'live' } else { 'fake' }

function Invoke-Checked { param([string]$What, [scriptblock]$Cmd) Write-Host "==> $What" -ForegroundColor Cyan; & $Cmd; if ($LASTEXITCODE -ne 0) { throw "$What failed" } }
function Get-ServiceUrl([string]$name) { (gcloud run services describe $name --project $project --region $region --format 'value(status.url)') }

if ($Only -in 'all', 'backend') {
  Invoke-Checked 'Enable APIs' { gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com cloudscheduler.googleapis.com --project $project }
  gcloud artifacts repositories describe pocket --project $project --location $region 2>$null | Out-Null
  if ($LASTEXITCODE -ne 0) { Invoke-Checked 'Create image repository' { gcloud artifacts repositories create pocket --project $project --location $region --repository-format docker } }

  Push-Location $root
  try {
    Invoke-Checked 'Build core-api' { gcloud builds submit . --project $project --config infra/cloudbuild.yaml --substitutions "_SERVICE=core_api,_IMAGE=$repo/core-api" }
    Invoke-Checked 'Build agent' { gcloud builds submit . --project $project --config infra/cloudbuild.yaml --substitutions "_SERVICE=agent,_IMAGE=$repo/agent" }
  } finally { Pop-Location }

  # core-api first (the agent needs its URL). The agent URL is filled in on the second pass below.
  $coreEnv = "ENV=demo,AUTH_MODE=firebase,FIREBASE_PROJECT_ID=$($cfg.FIREBASE_PROJECT_ID),INTERNAL_TOKEN=$($cfg.INTERNAL_TOKEN),POCKET_TODAY=$($cfg.POCKET_TODAY)"
  $coreArgs = @('run', 'deploy', 'core-api', '--project', $project, '--region', $region, '--image', "$repo/core-api", '--allow-unauthenticated', '--memory', '1Gi', '--cpu', '1')
  if ($cfg.DATABASE_URL) {
    $coreEnv += ",DATABASE_URL=$($cfg.DATABASE_URL)"
    if ($cfg.CLOUD_SQL_INSTANCE) { $coreArgs += @('--add-cloudsql-instances', $cfg.CLOUD_SQL_INSTANCE) }
    $coreArgs += @('--min-instances', '0', '--max-instances', '3')
  } else {
    # No database configured: SQLite inside one always-on instance. Data resets when the instance restarts.
    $coreArgs += @('--min-instances', '1', '--max-instances', '1', '--no-cpu-throttling')
  }
  Invoke-Checked 'Deploy core-api' { gcloud @coreArgs --set-env-vars $coreEnv }
  $coreUrl = Get-ServiceUrl 'core-api'

  $agentEnv = "ENV=demo,CORE_API_URL=$coreUrl,INTERNAL_TOKEN=$($cfg.INTERNAL_TOKEN),GEMINI_MODE=$geminiMode,GEMINI_API_KEY=$($cfg.GEMINI_API_KEY),MODEL_LIVE=gemini-3.8-live,MODEL_FLASH=gemini-3.8-flash,MODEL_FLASH_FALLBACK=$($cfg.MODEL_FLASH_FALLBACK)"
  Invoke-Checked 'Deploy agent' {
    gcloud run deploy agent --project $project --region $region --image "$repo/agent" --allow-unauthenticated --memory 1Gi --cpu 1 `
      --min-instances 1 --max-instances 3 --timeout 3600 --session-affinity --no-cpu-throttling --set-env-vars $agentEnv
  }
  $agentUrl = Get-ServiceUrl 'agent'
  Invoke-Checked 'Point core-api at the agent' { gcloud run services update core-api --project $project --region $region --update-env-vars "AGENT_URL=$agentUrl" }
  Invoke-Checked 'Build today''s Pulse' { curl.exe -sS -X POST "$agentUrl/internal/jobs/pulse" -H "X-Internal-Token: $($cfg.INTERNAL_TOKEN)" -H 'Content-Length: 0' }
  Write-Host "`ncore-api: $coreUrl`nagent:    $agentUrl  (GEMINI_MODE=$geminiMode)" -ForegroundColor Green
}

if ($Only -in 'all', 'web') {
  $coreUrl = Get-ServiceUrl 'core-api'
  $agentUrl = Get-ServiceUrl 'agent'
  foreach ($k in 'FIREBASE_API_KEY', 'FIREBASE_APP_ID', 'FIREBASE_PROJECT_ID') { if (-not $cfg[$k]) { throw "infra/demo.env is missing $k (Firebase console > Project settings > Your apps > Web app)" } }
  $env:API_BASE = $coreUrl; $env:AGENT_BASE = $agentUrl
  foreach ($k in 'FIREBASE_API_KEY', 'FIREBASE_APP_ID', 'FIREBASE_PROJECT_ID', 'FIREBASE_AUTH_DOMAIN', 'FIREBASE_MESSAGING_SENDER_ID') { Set-Item "env:$k" $cfg[$k] }
  Push-Location $root
  try {
    Invoke-Checked 'Build web app' { uv run python scripts/tasks.py web }
    Invoke-Checked 'Deploy to Firebase Hosting' { firebase deploy --only hosting --project $cfg.FIREBASE_PROJECT_ID }
  } finally { Pop-Location }
}
