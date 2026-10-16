#!/usr/bin/env bash
# One-time setup for daily automated Firestore backups (managed export).
# Run this yourself with `gcloud` authenticated against the real Firebase/GCP
# project — it needs credentials this assistant does not have.
#
# See docs/adr/0010-shared-dev-prod-environment.md for why this exists: dev
# and prod share one Firebase project with no isolation, so backups are the
# cheap insurance against a bad script wiping real data.
set -euo pipefail

PROJECT_ID="${1:?Usage: setup-firestore-backups.sh <gcp-project-id> <backup-gcs-bucket>}"
BUCKET="${2:?Usage: setup-firestore-backups.sh <gcp-project-id> <backup-gcs-bucket>}"

# Grants the Firestore service agent permission to write exports to the bucket.
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:service-$PROJECT_ID@gcp-sa-firestore.iam.gserviceaccount.com" \
  --role="roles/datastore.importExportAdmin"

# Cloud Scheduler job: triggers a Firestore export to the bucket every day at 03:00.
gcloud scheduler jobs create http firestore-daily-backup \
  --schedule="0 3 * * *" \
  --uri="https://firestore.googleapis.com/v1/projects/$PROJECT_ID/databases/(default):exportDocuments" \
  --message-body="{\"outputUriPrefix\":\"gs://$BUCKET/firestore-backups\"}" \
  --oauth-service-account-email="$PROJECT_ID@appspot.gserviceaccount.com" \
  --time-zone="UTC"

echo "Daily Firestore export scheduled: gs://$BUCKET/firestore-backups at 03:00 UTC."
