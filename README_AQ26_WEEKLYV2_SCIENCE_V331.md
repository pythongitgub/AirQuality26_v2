# AQ26 WeeklyV2 Science Backfill V3.3.1

This replacement patch hardens V3.3 after the latest run.

## Do not delete CDSE secrets

Keep all four existing CDSE secrets. The collector now tries them safely in this order:

1. `CDSE_USERNAME` + `CDSE_PASSWORD` using the public `cdse-public` password-flow client.
2. `CDSE_USERNAME` + `CDSE_PASSWORD` using `CDSE_ID` as client id, only if route 1 fails.
3. `CDSE_ID` + `CDSE_SECRET` client credentials, only if password flow fails.

No token is written to evidence files. Only readiness metadata is stored.

## Main fixes

- Adds Google Drive Python dependencies to `requirements.txt`.
- Makes CDSE username/password the first authentication route.
- Prevents `CDSE_ID` / `CDSE_SECRET` from breaking password-flow auth.
- Adds temporal evidence classification to every source record.
- Marks current/live API calls as `current_context_only`, not historical observations.
- Adds `observed_start`, `observed_end`, `evidence_window_start`, `evidence_window_end`.
- Adds stricter science validation warnings for current-context feeds and Drive readiness.
- Keeps `external_submission_ready` fail-closed.

## Recommended run

Re-run the partial V3.3 weeks first:

```text
backfill_start_date: 2024-07-22
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
force: true
```

Then continue with:

```text
backfill_start_date: auto
auto_mode: earliest_missing
backfill_limit_windows: 4
force: false
```
