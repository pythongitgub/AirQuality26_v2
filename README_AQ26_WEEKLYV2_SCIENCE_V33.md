# AQ26 WeeklyV2 Science Backfill V3.3

This patch adds a stricter, science-oriented historical backfill runner for AQ26.
It is designed to keep testing and retesting the platform until it is strong enough
for controlled review by organisations such as WHO, UNEP, EEA and C40 Cities, and
for scrutiny by leading air-quality and environmental-health experts.

## Files in this patch

```text
scripts/aq26_weeklyv2_science_backfill_v33.py
scripts/aq26_weeklyv2_collect.py
.github/workflows/aq26_weeklyv2_science_backfill_v33.yml
configs/aq26_weeklyv2_science_v33.yml
requirements.txt
README_AQ26_WEEKLYV2_SCIENCE_V33.md
```

Upload/merge the **contents** of the ZIP into the root of the GitHub repository.
Do not upload the ZIP itself as a repository file.

## Why this is different from V3.2.1

V3.3 adds:

- `auto_mode: earliest_missing` so backfill continues chronologically by default.
- Date-window exact-match validation so current-window contamination cannot pass silently.
- `status` and `backfill_status` aliases in every weekly row.
- `latest_backfill_summary.json` selection by completed run timestamp/date.
- CDSE alias handling with username/password retained as the first authentication path.
- Gemini model alias handling: `GEMINI_MODEL` -> `AQ26_GEMINI_MODEL`.
- NewsAPI and NewsData disabled by default during historical backfill.
- GDELT throttled to 8 seconds and limited to two contextual queries.
- Drive inventory truncation metadata fields.
- Null readiness values for unharvested weeks, rather than misleading zeroes.
- Strict validation for duplicate windows, harvested-zero records, JSON/CSV readability,
  secret-like public output leaks and unsafe external-submission readiness.

## Recommended first V3.3 run

Go to GitHub Actions and run:

```text
AQ26 WeeklyV2 Science Backfill V3.3
```

Use:

```text
backfill_start_date: auto
auto_mode: earliest_missing
backfill_end_date: 2026-05-25
backfill_limit_windows: 4
history_end_date: 2026-05-25
history_weeks: 104
newsapi_enabled: false
newsdata_enabled: false
gdelt_enabled: true
gemini_enabled: false
strict_validation: true
external_grade_validation: false
force: false
```

This should pick the earliest missing four weekly windows. Based on the prior state,
that should continue from the first unharvested gap rather than jumping to the latest
missing weeks.

## Local run example

```bash
python scripts/aq26_weeklyv2_science_backfill_v33.py run-batch \
  --repo-root . \
  --collector-script scripts/aq26_weeklyv2_collect.py \
  --config configs/aq26_weekly_v2_sources.yml \
  --output-root outputs \
  --site-root site_public \
  --history-end-date 2026-05-25 \
  --history-weeks 104 \
  --backfill-start-date auto \
  --auto-mode earliest_missing \
  --backfill-end-date 2026-05-25 \
  --backfill-limit-windows 4 \
  --strict
```

## Scientific caution

This patch does **not** make external submission ready. It keeps
`external_submission_ready` fail-closed until the required science gates pass,
including satellite extraction, CAMS data readiness, target/control comparison,
official-document review, uncertainty review and confounder handling.

## Important output files

```text
site_public/data/history/week_YYYY-MM-DD_YYYY-MM-DD.json
site_public/data/weekly_index.json
site_public/data/latest_backfill_summary.json
site_public/data/source_records_latest.json
site_public/data/charts/*.json
site_public/data/science_validation_latest.json
outputs/99_integrity/AQ26_WEEKLYV2_SCIENCE_V33_VALIDATION.json
```

## How to interpret validation

- `ok: true` means there are no blocking validation errors.
- Warnings still matter for scientific review.
- `external_grade_validation: true` makes harvested weeks with source errors fail.
- Null readiness values mean a gate was not measured for that week; this is not the same as false.

## Next scientific phase after stable backfill

Once the archive has enough clean harvested weeks, the next work should populate:

```text
pollutant_timeseries.json
facility_control_comparison.json
satellite_products_by_week.json
official_filings.json
```

Those are the datasets needed for stronger Newhaven/control-site analysis, satellite
extraction interpretation, official-document provenance, and eventual expert review.
