# AQ26 sccairquality.com production replacement pack

This pack replaces the production workflow/scripts/configs so deployment uses only the production Hostinger secrets for sccairquality.com:

- SCCAIRQUALITY_SSH_HOST
- SCCAIRQUALITY_SSH_USERNAME
- SCCAIRQUALITY_SSH_PASSWORD
- SCCAIRQUALITY_SSH_PORT
- AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR
- SCC_UNREDACTED_PASSWORD

The semi-redundant/test-domain SCCNEXUS_* and HOSTINGER_PUBLIC_HTML_DIR secrets are not used by this workflow.

Google Drive upload remains available, but the workflow input defaults to false because Google returned `Service Accounts do not have storage quota`. Re-enable only when GDRIVE_FOLDER_ID points to a Shared Drive folder where the service account is a member.

Recommended first run:

- deploy_to_hostinger: false
- dry_run: true
- send_email: false
- upload_to_drive: false
- historical_backfill_weeks: 4

Then test production deploy as a dry run:

- deploy_to_hostinger: true
- dry_run: true
- send_email: false
- upload_to_drive: false
- historical_backfill_weeks: 4

Only after dry-run is clean:

- deploy_to_hostinger: true
- dry_run: false
- send_email: true
- upload_to_drive: false
- historical_backfill_weeks: 4
