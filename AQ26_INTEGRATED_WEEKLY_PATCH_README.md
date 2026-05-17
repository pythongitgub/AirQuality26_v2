# AQ26 GitHub Integrated Weekly Evidence Harvest Patch V2

For the GitHub repository only.

Adds a scripts-only weekly workflow that harvests live/current AQ, weather, news, official filing candidates, satellite catalogue metadata, and optionally snapshots a shared Google Drive / Colab evidence folder by service account.

## Google Drive secrets

This patch supports any one of these secret names for the service-account JSON:

- `GDRIVE_SERVICE_ACCOUNT_JSON`
- `GDRIVE_CREDENTIALS`
- `GDRIVE_SERVICE_ACCOUNT`

Also add:

- `GDRIVE_FOLDER_ID`

Share the Drive folder with the service account email. Viewer is enough for metadata snapshotting.

## Run

Actions -> AQ26 Weekly Integrated Evidence Harvest -> Run workflow

Suggested first run:
- lookback_days: 14
- download_official_files: true
- sync_google_drive: true
- send_email: true

The redaction audit must report leak_count = 0 before sharing artifacts externally.
