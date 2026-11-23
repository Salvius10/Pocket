<#
Deploys Pocket to Google Cloud (Mumbai): core-api and agent on Cloud Run, web build on Firebase Hosting.

Before running (once):
  1. gcloud auth login --update-adc     (or: gcloud auth login, then firebase login)
  2. Copy infra/demo.env.example to infra/demo.env; set BILLING_ACCOUNT (and GEMINI_API_KEY if you have one).
  3. ./infra/setup.ps1          creates the project, links the credit, adds Firebase, fills in the rest of demo.env

Usage:  ./infra/deploy.ps1              # everything
        ./infra/deploy.ps1 -Only web    # backend | web
        ./infra/deploy.ps1 -Only warm   # demo day: keep one instance of each service running (uses credit while on)
        ./infra/deploy.ps1 -Only cool   # back to sleeping when idle
        ./infra/deploy.ps1 -Only pulse  # build today's Pulse (two Gemini calls in live mode)

Cost. Both services sleep when nobody is using them (min instances 0) and are billed only while they
handle a request, which a demo's traffic keeps inside Cloud Run's monthly free allowance. core-api is
capped at one instance and the agent at two, so a flood of traffic cannot multiply the bill.
With no DATABASE_URL, core-api keeps its data in SQLite inside the instance: it is gone when the
instance sleeps (about 15 minutes idle), and the app then sends the visitor back to pick a persona.
`-Only warm` stops that for a demo by keeping the instances up.

Secrets (GEMINI_API_KEY, INTERNAL_TOKEN, DATABASE_URL) are set as Cloud Run environment variables
and never written into the repo, the images or the web build.
#>
param([ValidateSet('all', 'backend', 'web', 'warm', 'cool', 'pulse')][string]$Only = 'all')
. "$PSScriptRoot\common.ps1"
Assert-Tools 'gcloud', 'uv'
$cfg = Read-DemoEnv
if ($cfg.WEB_HOST -ne 'cloudrun') { Assert-Tools 'firebase' }
foreach ($k in 'PROJECT_ID', 'INTERNAL_TOKEN') { if (-not $cfg[$k]) { throw "infra/demo.env is missing $k (run ./infra/setup.ps1 first)" } }

$project = $cfg.PROJECT_ID
$region = if ($cfg.REGION) { $cfg.REGION } else { 'asia-south1' }
$repo = "$region-docker.pkg.dev/$project/pocket"
$geminiMode = if ($cfg.GEMINI_API_KEY) { 'live' } else { 'fake' }

# Empty when the service is not deployed yet.
function Get-ServiceUrl([string]$Name) {
  return "$(cmd /c "gcloud run services describe $Name --project $project --region $region --format=value(status.url) 2>nul")".Trim()
}

# Environment variables reach Cloud Run through a temporary YAML file, so no secret sits on a command line.
function New-EnvVarsFile([hashtable]$Vars) {
  $path = [IO.Path]::GetTempFileName()
  $lines = foreach ($k in $Vars.Keys) { '{0}: "{1}"' -f $k, ("$($Vars[$k])" -replace '\\', '\\' -replace '"', '\"') }
  [IO.File]::WriteAllLines($path, [string[]]$lines, (New-Object Text.UTF8Encoding($false)))
  return $path
}

if ($Only -in 'all', 'backend') {
  if (-not $cfg.FIREBASE_PROJECT_ID) { throw 'infra/demo.env is missing FIREBASE_PROJECT_ID (run ./infra/setup.ps1 first)' }
  $null = Get-SignedInAccount
  Invoke-Checked 'Enable APIs' { gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com --project $project }
  if (-not (Test-Quiet "gcloud artifacts repositories describe pocket --project $project --location $region")) {
    Invoke-Checked 'Create image repository' { gcloud artifacts repositories create pocket --project $project --location $region --repository-format docker }
  }

  Push-Location $Root
  try {
    Invoke-Checked 'Build core-api' { gcloud builds submit . --project $project --config infra/cloudbuild.yaml --substitutions "_SERVICE=core_api,_IMAGE=$repo/core-api" }
    Invoke-Checked 'Build agent' { gcloud builds submit . --project $project --config infra/cloudbuild.yaml --substitutions "_SERVICE=agent,_IMAGE=$repo/agent" }
  } finally { Pop-Location }

  # Sleep when idle, bill per request, give start-up extra CPU so waking is quick. Run as the no-role identity if setup made one.
  $shared = @('--project', $project, '--region', $region, '--allow-unauthenticated', '--memory', '1Gi', '--cpu', '1', '--cpu-throttling', '--cpu-boost', '--min-instances', '0')
  $sa = "pocket-run@$project.iam.gserviceaccount.com"
  if (Test-Quiet "gcloud iam service-accounts describe $sa --project $project") { $shared += @('--service-account', $sa) }

  # core-api first (the agent needs its URL). On a first deploy the agent's URL is filled in afterwards.
  $agentUrlBefore = Get-ServiceUrl 'agent'
  $coreVars = @{ ENV = 'demo'; AUTH_MODE = 'firebase'; FIREBASE_PROJECT_ID = $cfg.FIREBASE_PROJECT_ID; INTERNAL_TOKEN = $cfg.INTERNAL_TOKEN; POCKET_TODAY = $cfg.POCKET_TODAY }
  if ($agentUrlBefore) { $coreVars.AGENT_URL = $agentUrlBefore }
  $coreArgs = @('run', 'deploy', 'core-api', '--image', "$repo/core-api") + $shared
  if ($cfg.DATABASE_URL) {
    $coreVars.DATABASE_URL = $cfg.DATABASE_URL
    if ($cfg.CLOUD_SQL_INSTANCE) { $coreArgs += @('--add-cloudsql-instances', $cfg.CLOUD_SQL_INSTANCE) }
    $coreArgs += @('--max-instances', '3')
  } else {
    # No database configured: SQLite inside the instance, so exactly one instance.
    $coreArgs += @('--max-instances', '1')
  }
  $coreFile = New-EnvVarsFile $coreVars
  try { Invoke-Checked 'Deploy core-api' { gcloud @coreArgs --env-vars-file $coreFile } } finally { Remove-Item $coreFile -Force -ErrorAction SilentlyContinue }
  $coreUrl = Get-ServiceUrl 'core-api'

  $agentVars = @{
    ENV = 'demo'; CORE_API_URL = $coreUrl; INTERNAL_TOKEN = $cfg.INTERNAL_TOKEN; GEMINI_MODE = $geminiMode; GEMINI_API_KEY = $cfg.GEMINI_API_KEY
    MODEL_LIVE = 'gemini-3.8-live'; MODEL_FLASH = 'gemini-3.8-flash'; MODEL_FLASH_FALLBACK = $cfg.MODEL_FLASH_FALLBACK
  }
  $agentFile = New-EnvVarsFile $agentVars
  try {
    Invoke-Checked 'Deploy agent' {
      gcloud run deploy agent --image "$repo/agent" @shared --max-instances 2 --timeout 3600 --session-affinity --env-vars-file $agentFile
    }
  } finally { Remove-Item $agentFile -Force -ErrorAction SilentlyContinue }
  $agentUrl = Get-ServiceUrl 'agent'
  if ($agentUrl -ne $agentUrlBefore) {
    Invoke-Checked 'Point core-api at the agent' { gcloud run services update core-api --project $project --region $region --update-env-vars "AGENT_URL=$agentUrl" }
  }
  Write-Host "`ncore-api: $coreUrl`nagent:    $agentUrl  (GEMINI_MODE=$geminiMode)" -ForegroundColor Green
}

if ($Only -in 'all', 'web') {
  $coreUrl = Get-ServiceUrl 'core-api'
  $agentUrl = Get-ServiceUrl 'agent'
  if (-not $coreUrl -or -not $agentUrl) { throw 'Deploy the backend first:  ./infra/deploy.ps1 -Only backend' }
  foreach ($k in 'FIREBASE_API_KEY', 'FIREBASE_APP_ID', 'FIREBASE_PROJECT_ID') { if (-not $cfg[$k]) { throw "infra/demo.env is missing $k (run ./infra/setup.ps1 first)" } }
  $env:API_BASE = $coreUrl; $env:AGENT_BASE = $agentUrl
  $env:GOOGLE_CLOUD_QUOTA_PROJECT = $project  # needed when the Firebase tool runs on gcloud's sign-in (see setup.ps1)
  foreach ($k in 'FIREBASE_API_KEY', 'FIREBASE_APP_ID', 'FIREBASE_PROJECT_ID', 'FIREBASE_AUTH_DOMAIN', 'FIREBASE_MESSAGING_SENDER_ID') { Set-Item "env:$k" $cfg[$k] }
  Push-Location $Root
  try { Invoke-Checked 'Build web app' { uv run python scripts/tasks.py web } } finally { Pop-Location }

  if ($cfg.WEB_HOST -eq 'cloudrun') {
    # No Firebase project: a small nginx service on Cloud Run serves the build. It sleeps when idle like the others.
    $stage = Join-Path $env:TEMP 'pocket-web-image'
    if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
    New-Item -ItemType Directory $stage | Out-Null
    Copy-Item (Join-Path $PSScriptRoot 'web\*') $stage
    Copy-Item (Join-Path $Root 'apps\mobile\build\web') (Join-Path $stage 'web') -Recurse
    Invoke-Checked 'Build web image' { gcloud builds submit $stage --project $project --config (Join-Path $stage 'cloudbuild.yaml') --substitutions "_IMAGE=$repo/web" }
    $webArgs = @('run', 'deploy', 'pocket', '--image', "$repo/web", '--project', $project, '--region', $region, '--allow-unauthenticated',
      '--memory', '256Mi', '--cpu', '1', '--cpu-throttling', '--min-instances', '0', '--max-instances', '2')
    $sa = "pocket-run@$project.iam.gserviceaccount.com"
    if (Test-Quiet "gcloud iam service-accounts describe $sa --project $project") { $webArgs += @('--service-account', $sa) }
    Invoke-Checked 'Deploy web' { gcloud @webArgs }
    Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "`nweb app: $(Get-ServiceUrl 'pocket')" -ForegroundColor Green
  } else {
    Push-Location $Root
    try { Invoke-Checked 'Deploy to Firebase Hosting' { firebase deploy --only hosting --project $cfg.FIREBASE_PROJECT_ID } } finally { Pop-Location }
    Write-Host "`nweb app: https://$($cfg.FIREBASE_PROJECT_ID).web.app" -ForegroundColor Green
  }
}

if ($Only -in 'warm', 'cool') {
  $min = if ($Only -eq 'warm') { '1' } else { '0' }
  foreach ($svc in 'core-api', 'agent') {
    Invoke-Checked "Set $svc to at least $min running instance(s)" { gcloud run services update $svc --project $project --region $region --min-instances $min }
  }
  if ($Only -eq 'warm') { Write-Host "`nBoth services now stay up and use credit all day. Run  ./infra/deploy.ps1 -Only cool  after the demo." -ForegroundColor Yellow }
}

if ($Only -eq 'pulse') {
  $agentUrl = Get-ServiceUrl 'agent'
  if (-not $agentUrl) { throw 'The agent is not deployed yet.' }
  Write-Host "==> Build today's Pulse (GEMINI_MODE=$geminiMode)" -ForegroundColor Cyan
  Invoke-RestMethod -Method Post -Uri "$agentUrl/internal/jobs/pulse" -Headers @{ 'X-Internal-Token' = $cfg.INTERNAL_TOKEN } -TimeoutSec 180 | ConvertTo-Json -Compress
}
