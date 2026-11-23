<#
One-time set-up of the Google Cloud project that hosts the demo. Safe to run again: every step looks
before it creates.

Before running:
  1. Sign in (opens a browser), with the Google account that owns the billing account:
         gcloud auth login --update-adc        (one sign-in for both tools)
     or  gcloud auth login   and   firebase login
  2. Copy infra/demo.env.example to infra/demo.env and set BILLING_ACCOUNT (Billing > Account ID).

Then:   ./infra/setup.ps1                and after it     ./infra/deploy.ps1
        ./infra/setup.ps1 -NoFirebase    if the Google account has not accepted Firebase's terms

What it does:
  - creates a new project (unless PROJECT_ID is already set) and links it to BILLING_ACCOUNT. A new
    project keeps the hosting bill apart from any other project, such as the one a Gemini key lives in.
  - turns on the APIs the deploy needs
  - adds a budget alert on the billing account (e-mail at 25%, 50% and 90% of BUDGET_USD, credits counted
    as spend). An alert does not stop spending; the deploy's own limits do that (see deploy.ps1).
  - creates a service identity with no roles for the services to run as
  - sign-in and web hosting, one of:
      default      adds Firebase and registers a web app; the page goes on Firebase Hosting
      -NoFirebase  uses Identity Platform on the Cloud project with a browser key limited to the
                   sign-in APIs; the page is served by a small Cloud Run service (WEB_HOST=cloudrun)
  - turns on anonymous sign-in, and writes PROJECT_ID, FIREBASE_* and WEB_HOST into infra/demo.env
#>
param([switch]$NoFirebase)
. "$PSScriptRoot\common.ps1"
Assert-Tools 'gcloud'
if (-not $NoFirebase) { Assert-Tools 'firebase' }
$cfg = Read-DemoEnv
$billing = $cfg.BILLING_ACCOUNT
if (-not $billing) { throw 'infra/demo.env is missing BILLING_ACCOUNT (Google Cloud console > Billing > Account ID).' }
$budgetUsd = if ($cfg.BUDGET_USD) { $cfg.BUDGET_USD } else { '5' }

$account = Get-SignedInAccount
Write-Host "Signed in to gcloud as $account" -ForegroundColor Green

# --- billing account: must be visible to this sign-in, and open ---
$open = gcloud billing accounts describe $billing --format 'value(open)'
if ($LASTEXITCODE -ne 0) { throw "This Google account cannot see billing account $billing. Sign in with the account that owns it:  gcloud auth login" }
if ("$open".Trim() -ne 'True') { throw "Billing account $billing is closed (credit used up or expired), so nothing can be hosted on it." }

# --- project ---
$project = $cfg.PROJECT_ID
if (-not $project) {
  $letters = 'abcdefghijklmnopqrstuvwxyz0123456789'
  $project = 'pocket-demo-' + (-join (1..6 | ForEach-Object { $letters[(Get-Random -Maximum $letters.Length)] }))
  # Recorded before the create call, so a run that is interrupted does not make a second project next time.
  Set-DemoEnv 'PROJECT_ID' $project
  Invoke-Checked "Create project $project" { gcloud projects create $project --name 'Pocket demo' --quiet }
} elseif (-not (Test-Quiet "gcloud projects describe $project")) {
  throw "Project $project (PROJECT_ID in infra/demo.env) does not exist, or this account cannot see it."
}

$linked = "$(gcloud billing projects describe $project --format 'value(billingAccountName)')".Trim()
if ($linked -and $linked -ne "billingAccounts/$billing") { throw "Project $project is already billed to $linked. Not moving it." }
if (-not $linked) { Invoke-Checked 'Link the project to the billing account' { gcloud billing projects link $project --billing-account $billing } }

Invoke-Checked 'Turn on the APIs' {
  gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com iam.googleapis.com `
    cloudresourcemanager.googleapis.com serviceusage.googleapis.com identitytoolkit.googleapis.com billingbudgets.googleapis.com --project $project
}

# --- budget alert (best effort: some credit accounts do not let their user create one) ---
$budgetName = 'pocket-demo-credit'
$existing = gcloud billing budgets list --billing-account $billing --billing-project $project --format 'value(displayName)'
if ($LASTEXITCODE -eq 0 -and (@($existing) -notcontains $budgetName)) {
  Write-Host "==> Budget alert at 25%, 50% and 90% of `$$budgetUsd" -ForegroundColor Cyan
  gcloud billing budgets create --billing-account $billing --billing-project $project --display-name $budgetName `
    --budget-amount "${budgetUsd}USD" --credit-types-treatment exclude-all-credits `
    --threshold-rule percent=0.25 --threshold-rule percent=0.5 --threshold-rule percent=0.9 | Out-Null
}
if ($LASTEXITCODE -ne 0) { Write-Warning 'No budget alert was set (on a new project this can need a few minutes; run setup again). Until then watch the spend on the Billing page.' }

# --- the identity the services run as: no roles, because no service calls a Google Cloud API ---
$sa = "pocket-run@$project.iam.gserviceaccount.com"
if (-not (Test-Quiet "gcloud iam service-accounts describe $sa --project $project")) {
  Invoke-Checked 'Create the service identity' { gcloud iam service-accounts create pocket-run --project $project --display-name 'Pocket services' }
}

if ($NoFirebase) {
  # --- sign-in on the Cloud project itself, with a browser key that can call only the sign-in APIs ---
  Invoke-Checked 'Turn on the API-key service' { gcloud services enable apikeys.googleapis.com --project $project }
  $listKey = "gcloud services api-keys list --project $project --filter=displayName=pocket-web --format=value(name) 2>nul"
  $keyName = "$(cmd /c $listKey)".Trim()
  if (-not $keyName) {
    Write-Host '==> Create the browser key' -ForegroundColor Cyan
    $made = Test-Quiet "gcloud services api-keys create --project $project --display-name=pocket-web --api-target=service=identitytoolkit.googleapis.com --api-target=service=securetoken.googleapis.com"
    $keyName = "$(cmd /c $listKey)".Trim()
    if (-not $made -or -not $keyName) { throw 'Could not create the browser key.' }
  }
  $apiKey = "$(cmd /c "gcloud services api-keys get-key-string $keyName --format=value(keyString) 2>nul")".Trim()
  if (-not $apiKey) { throw 'Could not read the browser key.' }
  $number = "$(gcloud projects describe $project --format 'value(projectNumber)')".Trim()
  $appId = "1:${number}:web:0000000000000000000000"  # the sign-in SDK wants an app id; without Firebase there is none, and sign-in does not use it
  $authDomain = "$project.firebaseapp.com"
  $senderId = $number
  Set-DemoEnv 'WEB_HOST' 'cloudrun'
} else {
  # --- Firebase: project, web app, config ---
  Invoke-Checked 'Turn on the Firebase APIs' { gcloud services enable firebase.googleapis.com firebasehosting.googleapis.com --project $project }
  # Without `firebase login` the Firebase tool uses gcloud's application-default sign-in
  # (`gcloud auth login --update-adc`), and Google then needs to be told which project the calls count against.
  $env:GOOGLE_CLOUD_QUOTA_PROJECT = $project
  function Invoke-FirebaseJson([string[]]$FbArgs) {
    $raw = (& firebase @FbArgs --json | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "firebase $($FbArgs -join ' ') failed:`n$raw" }
    return ($raw | ConvertFrom-Json).result
  }
  $fbProjects = @(Invoke-FirebaseJson @('projects:list'))
  if (-not ($fbProjects | Where-Object { $_.projectId -eq $project })) {
    Write-Host '==> Add Firebase to the project' -ForegroundColor Cyan
    firebase projects:addfirebase $project
    if ($LASTEXITCODE -ne 0) {
      throw 'Firebase refused the project. If this Google account has never used Firebase, open https://console.firebase.google.com once and accept its terms, or run:  ./infra/setup.ps1 -NoFirebase'
    }
  }
  $app = @(Invoke-FirebaseJson @('apps:list', 'WEB', '--project', $project)) | Where-Object { $_.appId } | Select-Object -First 1
  if (-not $app) {
    Write-Host '==> Register the web app' -ForegroundColor Cyan
    $app = Invoke-FirebaseJson @('apps:create', 'WEB', 'Pocket', '--project', $project)
  }
  $appId = $app.appId
  if (-not $appId) { throw 'Could not read the web app id from Firebase.' }

  # The config is printed as JSON in some CLI versions and as a JS snippet in others; read the fields from either.
  $sdk = (& firebase apps:sdkconfig WEB $appId --project $project --json | Out-String)
  if ($LASTEXITCODE -ne 0) { throw "firebase apps:sdkconfig failed:`n$sdk" }
  function Find-ConfigValue([string]$Name) {
    if ($sdk -match ('\\?"' + $Name + '\\?"\s*:\s*\\?"([^"\\]+)')) { return $Matches[1] }
    return ''
  }
  $apiKey = Find-ConfigValue 'apiKey'
  if (-not $apiKey) { throw 'Could not read the web config from Firebase.' }
  $authDomain = Find-ConfigValue 'authDomain'
  $senderId = Find-ConfigValue 'messagingSenderId'
  Set-DemoEnv 'WEB_HOST' 'firebase'
}
# These are public identifiers (they ship inside every web build), not secrets.
Set-DemoEnv 'FIREBASE_PROJECT_ID' $project
Set-DemoEnv 'FIREBASE_API_KEY' $apiKey
Set-DemoEnv 'FIREBASE_APP_ID' $appId
Set-DemoEnv 'FIREBASE_AUTH_DOMAIN' $authDomain
Set-DemoEnv 'FIREBASE_MESSAGING_SENDER_ID' $senderId

# --- anonymous sign-in (the app's demo sign-in) ---
$headers = @{ Authorization = "Bearer $(gcloud auth print-access-token | Select-Object -First 1)"; 'x-goog-user-project' = $project }
$idp = 'https://identitytoolkit.googleapis.com'
$hasAuth = $true
try { Invoke-RestMethod -Uri "$idp/admin/v2/projects/$project/config" -Headers $headers | Out-Null } catch { $hasAuth = $false }
if (-not $hasAuth) {
  Write-Host '==> Turn on sign-in for the project' -ForegroundColor Cyan
  Invoke-RestMethod -Method Post -Uri "$idp/v2/projects/${project}/identityPlatform:initializeAuth" -Headers $headers -ContentType 'application/json' -Body '{}' | Out-Null
}
Write-Host '==> Allow anonymous sign-in' -ForegroundColor Cyan
Invoke-RestMethod -Method Patch -Uri "$idp/admin/v2/projects/$project/config?updateMask=signIn.anonymous.enabled" -Headers $headers `
  -ContentType 'application/json' -Body '{"signIn":{"anonymous":{"enabled":true}}}' | Out-Null

Write-Host "`nProject $project is ready and billed to $billing. Next:  ./infra/deploy.ps1" -ForegroundColor Green
