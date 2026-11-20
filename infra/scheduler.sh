#!/usr/bin/env bash
# Cloud Scheduler jobs (ARCHITECTURE.md §7.5), all in IST. Run once after the services are deployed.
#   PROJECT_ID=... INTERNAL_TOKEN=... ./infra/scheduler.sh
set -euo pipefail
REGION="${REGION:-asia-south1}"
CORE=$(gcloud run services describe core-api --project "$PROJECT_ID" --region "$REGION" --format 'value(status.url)')
AGENT=$(gcloud run services describe agent --project "$PROJECT_ID" --region "$REGION" --format 'value(status.url)')

job() { # name, cron, url
  gcloud scheduler jobs delete "$1" --project "$PROJECT_ID" --location "$REGION" --quiet 2>/dev/null || true
  gcloud scheduler jobs create http "$1" --project "$PROJECT_ID" --location "$REGION" --schedule "$2" --time-zone "Asia/Kolkata" \
    --uri "$3" --http-method POST --headers "X-Internal-Token=${INTERNAL_TOKEN},Content-Type=application/json" --message-body '{}'
}

job pocket-nav      "30 23 * * *" "$CORE/internal/jobs/nav"        # AMFI NAV ingest
job pocket-insights "0 6 * * *"   "$CORE/internal/jobs/insights"   # insight run
job pocket-pulse    "0 7 * * *"   "$AGENT/internal/jobs/pulse"     # Pulse build
job pocket-nudges   "0 * * * *"   "$CORE/internal/jobs/nudges"     # nudge planning, hourly
job pocket-drip     "30 0 * * *"  "$CORE/internal/jobs/drip"       # synthetic drip: yesterday's transactions, as SMS through the parser
# The monthly report needs no job: it is computed when the screen asks for it.
