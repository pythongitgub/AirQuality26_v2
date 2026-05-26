# AQ26 WeeklyV2 V3.2.1 Secret Aliases + Auto Backfill Patch

This patch is a small compatibility and usability upgrade on top of V3.2.

## What it changes

1. Adds `backfill_start_date: auto` support for the historical workflow.
   - The runner scans `site_public/data/history/` and selects the next missing weekly slots from the canonical 104-week spine.
   - Existing weeks are skipped before the batch limit is applied, so accidental repeat starts no longer waste a run.

2. Preserves the known-working CDSE username/password path.
   - The CDSE auth probe now tries `CDSE_USERNAME` + `CDSE_PASSWORD` first.
   - It tries `cdse-public` as the public password-flow client, then any supplied `CDSE_ID`.

3. Adds CDSE alias support.
   - `CDSE_ID` aliases to `CDSE_CLIENT_ID`.
   - `CDSE_SECRET` aliases to `CDSE_CLIENT_SECRET`.
   - The script reads both old and new names.

4. Adds Gemini model alias support.
   - `GEMINI_MODEL` aliases to `AQ26_GEMINI_MODEL`.
   - Default remains `gemini-3.5-flash`.

5. Adds News API alias support.
   - `NEWS_API_KEY` aliases to `NEWSAPI_KEY`.
   - `NEWS_DATA_IO_KEY` aliases to `NEWSDATA_API_KEY` and `NEWSDATA_KEY`.

## Files included

- `scripts/aq26_weeklyv2_collect.py`
- `scripts/aq26_weeklyv2_history_v3.py`
- `.github/workflows/aq26_weeklyv2_backfill_v3.yml`
- `.github/workflows/aq26_weekly_v2_sccnexus_website.yml`
- `configs/aq26_weeklyv2_history_v3.yml`
- `requirements.txt`

## Recommended next workflow run

Use the V3.2.1 workflow with:

```text
backfill_start_date: auto
backfill_end_date: 2026-05-25
backfill_limit_windows: 4
history_weeks: 104
strict_validation: true
force: false
newsapi_enabled: false
gdelt_enabled: true
gemini_enabled: false
```

If the previous successful run reached `2024-08-19`, the auto selector should pick the next missing four weeks automatically.

## Notes

- No new GitHub secrets are required.
- This patch uses the existing repository secret names Scott listed.
- Gemini remains optional and disabled by default during backfill.
- CDSE product extraction is still a separate future science gate; this patch only improves auth-readiness probing.
