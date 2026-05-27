# AQ26 WeeklyV2 Stage2 Evidence Lake Follow-on

This patch is designed to follow on from **AQ26 WeeklyV2 Science Backfill V3.3.1** rather than replace it.

## What it does

1. Optionally runs the existing V3.3.1 weekly science backfill first.
2. Runs NASA Earthdata Stage2 CMR candidate scorecard.
3. Runs controlled LAQN historical backfill using known validated pairs.
4. Builds a Stage2 integrated summary/report from:
   - `site_public/data/weekly_index.json`
   - `outputs/99_integrity/AQ26_WEEKLYV2_SCIENCE_V33_VALIDATION.json`
   - `outputs/34_earthdata_stage2/earthdata_stage2_summary.json`
   - `outputs/35_laqn_backfill/laqn_backfill_summary.json`
5. Optionally uploads outputs to Google Drive using:
   - `GDRIVE_SERVICE_ACCOUNT`
   - `GDRIVE_FOLDER_ID`

## Secrets used

The workflow maps the existing repository secrets you listed:

- `OPENAQ_API_KEY`
- `WAQI_TOKEN`
- `OPENWEATHER_KEY`
- `PURPLE_AIR_API_KEY`
- `METOFFICE_API_KEY`
- `MET_OFFICE_API_KEY`
- `MET_OFFICE_LAND_OBSERVATIONS`
- `NEWS_API_KEY`
- `NEWS_DATA_IO_KEY`
- `SERPAPI_API_KEY`
- `CAMS_API_KEY`
- `EARTHDATA_USERNAME`
- `EARTHDATA_PASSWORD`
- `EARTHDATA_TOKEN`
- `EARTH_DATA_API_KEY`
- `CDSE_USERNAME`
- `CDSE_PASSWORD`
- `CDSE_ID`
- `CDSE_SECRET`
- `GDRIVE_FOLDER_ID`
- `GDRIVE_SERVICE_ACCOUNT`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `MAIL_FROM`
- `MAIL_TO`
- `SMTP_*`
- `HOSTINGER_PUBLIC_HTML_DIR`
- `SCCNEXUS_SSH_*`

It does not print secret values.

## First recommended run

Use:

- `run_v331_first`: false
- `run_earthdata_stage2`: true
- `run_laqn_backfill`: true
- `laqn_max_pairs`: 6
- `upload_to_gdrive`: false
- `commit_outputs`: true

This verifies the stage without writing to Drive.

## Second run

After the first run passes:

- `upload_to_gdrive`: true

This uploads provider output folders to the Google Drive folder configured by `GDRIVE_FOLDER_ID`.

## Important caveat

NASA Earthdata Stage2 is still discovery/scoring only. It is not yet a validated satellite observation extraction. The next stage should be a product-specific tiny MERRA-2 subset test, not bulk download.
