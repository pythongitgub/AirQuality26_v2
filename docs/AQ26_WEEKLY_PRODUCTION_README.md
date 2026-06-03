# AQ26 weekly production workflow

This patch adds one authoritative GitHub-first production path for AirQuality26:

- `.github/workflows/aq26_weekly_production.yml`
- `scripts/aq26_production_pipeline.py`
- `scripts/aq26_upload_to_gdrive.py`
- `scripts/aq26_send_production_email.py`
- `configs/aq26_production.yml`
- `requirements.txt`

It is designed to reduce workflow confusion. Keep older workflows while testing, but treat this as the preferred production workflow once it passes.

## What it builds

Every weekly run creates:

- redacted public site in `site_public/`
- password-protected unredacted payload in `site_unredacted/`
- `outputs/aq26_production/<RUN_TS>/LATEST_WEEKLYV2.json`
- `source_index.jsonl`
- `AQ26_SHA256_LEDGER.csv`
- `AQ26_FINAL_ZIP_LEDGER.csv`
- `redaction_audit.json`
- `gdrive_recursive_inventory.json`
- `missing_date_backfill_plan.json`
- `evidence_priority_scores.json`
- `evidence_readiness_gates.json`
- `official_filing_index.json`
- `satellite_catalogue_metadata.json`
- `anomaly_alerts.json`
- Markdown and PDF weekly reports
- final validated evidence ZIP
- public and unredacted site ZIPs

## Run order

1. Commit this patch.
2. Run **AQ26 Weekly Production Evidence, Website, Drive and Deploy** manually.
3. First run with:
   - `deploy_to_hostinger=false`
   - `dry_run=true`
   - `send_email=true`
   - `upload_to_drive=true`
   - `historical_backfill_weeks=4`
4. Inspect the artifact and `redaction_audit.json`.
5. If clean, rerun with `deploy_to_hostinger=true`, `dry_run=true`.
6. If the rsync dry run is clean, rerun with `deploy_to_hostinger=true`, `dry_run=false`.

## Required secrets

Minimum for deploy and email:

- `HOSTINGER_PUBLIC_HTML_DIR`
- `SCCNEXUS_SSH_HOST`
- `SCCNEXUS_SSH_PORT`
- `SCCNEXUS_SSH_USERNAME`
- `SCCNEXUS_SSH_PASSWORD`
- `SCC_UNREDACTED_PASSWORD`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `MAIL_FROM`
- `MAIL_TO`

Minimum for Drive backup:

- `GDRIVE_FOLDER_ID`
- `GDRIVE_SERVICE_ACCOUNT`

Optional provider keys read if present:

- `OPENAQ_API_KEY`
- `WAQI_TOKEN`
- `METOFFICE_API_KEY`
- `MET_OFFICE_API_KEY`
- `OPENWEATHER_KEY`
- `PURPLE_AIR_API_KEY`
- `CDSE_ID`
- `CDSE_USERNAME`
- `CDSE_PASSWORD`
- `CDSE_SECRET`
- `CAMS_API_KEY`
- `EARTHDATA_USERNAME`
- `EARTHDATA_PASSWORD`
- `EARTHDATA_TOKEN`
- `EARTH_DATA_API_KEY`
- `NEWS_API_KEY`
- `NEWS_DATA_IO_KEY`
- `SERPAPI_API_KEY`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`

## Hard gates

The workflow fails if:

- a required output is missing;
- any JSON or CSV output is not machine-readable;
- `.htpasswd` appears before deployment;
- the redaction audit detects a secret leak;
- core site pages are blank or missing.

## Scientific/public-language gates

The workflow deliberately keeps:

- `external_submission_ready=false`
- `public_release_ready=false`
- `satellite_extraction_ready=false`

until the scientific chain is stronger: historical backfill, ground AQ QA, satellite extraction, wind/source-receptor checks and official-document review.

## Important housekeeping recommendation

The repository currently has many overlapping workflows. After this production workflow passes, disable old patch/test workflows by moving them to `.github/workflows_disabled/` or renaming them to `.disabled`. Keep provider probes such as UK-AIR SOS and LAQN as separate controlled development workflows until their observation harvesters are fully validated.
