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
# Not scheduled yet: the synthetic daily drip (00:30) and the monthly report (1st, 08:00). See DECISIONS_LOG.md.
