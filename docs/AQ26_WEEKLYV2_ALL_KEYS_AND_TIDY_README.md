# AQ26 WeeklyV2 all-keys integration and repository tidy audit

This patch keeps `AQ26 WeeklyV2 Evidence Harvest` as the primary GitHub-only weekly workflow and integrates the currently available keys safely.

## Keys now mapped in the workflow

- `CAMS_API_KEY`
- `CDSE_ID`
- `CDSE_PASSWORD`
- `CDSE_SECRET`
- `CDSE_USERNAME`
- `EARTH_DATA_API_KEY`
- `GDRIVE_FOLDER_ID`
- `GDRIVE_SERVICE_ACCOUNT`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `MAIL_FROM`
- `MAIL_TO`
- `METOFFICE_API_KEY`
- `MET_OFFICE_API_KEY`
- `MET_OFFICE_LAND_OBSERVATIONS`
- `NEWS_API_KEY`
- `NEWS_DATA_IO_KEY`
- `OPENAQ_API_KEY`
- `OPENWEATHER_KEY`
- `PURPLE_AIR_API_KEY`
- `SERPAPI_API_KEY`
- `SMTP_HOST`
- `SMTP_PASSWORD`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `WAQI_TOKEN`

## New optional streams

- PurpleAir regional low-cost sensor context, recorded as contextual only.
- SerpAPI official/news discovery context.
- NASA Earthdata CMR discovery/readiness.
- CDSE authentication readiness probe without storing tokens.
- Gemini metadata-only neutral summary.
- Repository tidy audit, no deletion/moving.

## Safety constraints

- OpenAQ remains deliberately low-rate.
- No secret values are written to logs, URLs, JSON, CSV, Markdown, PDF or ZIP.
- Gemini receives only metadata counts/readiness, never raw evidence or keys.
- CDSE access tokens are never stored.
- PurpleAir is marked as contextual low-cost sensor data until calibration/siting QA is proven.
- External submission remains false until scientific evidence gates pass.

## Repository tidy

This patch does not delete notebooks or historical workflows. It adds a tidy audit output:

`outputs/13_repo_tidy/repo_tidy_audit.json`

Use that audit to decide what to archive later.
