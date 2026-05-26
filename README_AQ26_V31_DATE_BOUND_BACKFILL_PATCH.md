# AQ26 WeeklyV2 V3.1 Date-Bound Backfill Patch

Upload/merge the contents of this ZIP into the root of `AirQuality26_v2`.

## Files included

- `scripts/aq26_weeklyv2_collect.py`
  - Adds `--start-date` and `--end-date` so historical backfill runs are genuinely date-bound.
  - Supports environment date overrides used by the workflow.
  - Uses safer source-record CSV quoting.
  - Accepts common secret aliases including `NEWSAPI_KEY`, `NEWSDATA_API_KEY`, and `CAMS_ENDPOINT`.
  - Updates the default Gemini model to `gemini-1.5-flash-latest`.

- `scripts/aq26_weeklyv2_history_v3.py`
  - Replaces V3 with V3.1.
  - Excludes generated aggregate files such as `weekly_index.json`, `latest_summary.json`, chart feeds and source-record tables from historical ingestion.
  - Builds exactly the requested weekly archive length.
  - Writes one immutable history file per processed window under `site_public/data/history/` and `outputs/10_historical_backfill/history/`.
  - Produces validated chart feeds under `site_public/data/charts/`.
  - Adds stricter validation for duplicate windows, row-count mismatch, harvested-zero rows, generated aggregate recursion, bad JSON/CSV and missing linked data/assets/downloads.

- `.github/workflows/aq26_weeklyv2_backfill_v3.yml`
  - Replaces the backfill workflow with V3.1.
  - Runs controlled date-bound batches.
  - Defaults to strict validation.
  - Commits generated immutable history and chart/site data back to `main`.

- `.github/workflows/aq26_weekly_v2_sccnexus_website.yml`
  - Keeps the production website workflow but adds a V3.1 canonical site-data step after site build.
  - Uses `requirements.txt` plus required Google/HTML/Parquet dependencies.

- `configs/aq26_weeklyv2_history_v3.yml`
  - Documents the historical-backfill policy, exclusions and validation gates.

- `requirements.txt`
  - Adds explicit dependencies used by the weekly/backfill workflows.

## First safe run

After committing the patch, run:

`Actions → AQ26 WeeklyV2 Historical Backfill V3.1 → Run workflow`

Recommended first settings:

- `backfill_start_date`: `2024-05-27`
- `backfill_end_date`: `2026-05-25`
- `backfill_limit_windows`: `1`
- `history_weeks`: `104`
- `strict_validation`: `true`
- `force`: `false`

If that passes, run again with `backfill_limit_windows: 4`.

## Expected improvement

The generated `site_public/data/weekly_index.json` should have exactly 104 rows for a 104-week archive. It should not ingest its own earlier `weekly_index.json`. Each successful backfill week should produce an immutable file like:

`site_public/data/history/week_2024-05-27_2024-06-03.json`

External submission readiness remains false until the science gates pass.
